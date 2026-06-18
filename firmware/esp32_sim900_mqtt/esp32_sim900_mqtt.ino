/* ============================================================================
 *  Damascus Transit — GPS tracker prototype  (ESP32 + SIM900 2G + NEO-6M GPS)
 *  TRANSPORT: MQTT  (publishes to the self-hosted Mosquitto broker)
 * ----------------------------------------------------------------------------
 *  Flow:
 *    NEO-6M (GPS) ─► ESP32 ─► SIM900 (2G/GPRS) ─► Mosquitto broker
 *                                                     │
 *                                       api.workers.mqtt_consumer (subscriber)
 *                                                     │
 *                                       vehicle_positions  +  live map
 *
 *  The device publishes ONE compact JSON object per fix to:
 *        vehicles/<VEHICLE_ID>/status
 *  matching the server's _PartialDecode shape (api/routers/mqtt_ingest.py),
 *  so the MQTT path reuses the exact same ingest pipeline as the HTTP bridge.
 *
 *  Security model (prototype): the broker authenticates the device
 *  (username/password, and TLS in production). On a trusted/VPN network the
 *  dev broker accepts anonymous connections — see docs/MQTT_INGEST.md.
 *
 *  Libraries (Arduino Library Manager):
 *    - TinyGSM            (Volodymyr Shymanskyy)   — 2G/GPRS data layer
 *    - PubSubClient       (Nick O'Leary)           — MQTT client
 *    - TinyGPSPlus        (Mikal Hart)             — NMEA parser
 *
 *  SIM900 is a classic 2G GSM/GPRS module and speaks the standard SIMCom AT
 *  set, so TinyGSM's SIM800 profile drives it unchanged.
 * ========================================================================== */

#define TINY_GSM_MODEM_SIM800      // SIM900 is command-compatible with SIM800
#define TINY_GSM_RX_BUFFER 1024

#include <TinyGsmClient.h>
#include <PubSubClient.h>
#include <TinyGPSPlus.h>

/* ---------------------------------------------------------------------------
 *  1) CONFIG — edit these for your unit / operator / broker
 * ------------------------------------------------------------------------- */
// Identity — this is the ID published in the topic vehicles/<VEHICLE_ID>/status.
const char* VEHICLE_ID  = "DTS002";
// Your operator UUID (the default seeded "damascus" operator; change if yours differs).
const char* OPERATOR_ID = "00000000-0000-0000-0000-000000000001";

// Cellular data plan APN (ask your SIM operator — examples for Syria):
const char* APN      = "internet";   // Syriatel / MTN: usually "internet"
const char* GPRS_USER = "";
const char* GPRS_PASS = "";

// Mosquitto broker the device connects to. Over 2G this must be a PUBLIC IP/host
// (a laptop on localhost is NOT reachable from cellular — see notes at the end).
const char* MQTT_HOST = "YOUR_BROKER_IP";  // <-- set to your broker's public host/IP
const uint16_t MQTT_PORT = 1883;           // 1883 plain · 8883 TLS (see notes)
const char* MQTT_USER = "";               // set if the broker requires auth
const char* MQTT_PASS = "";

const uint32_t PUBLISH_EVERY_MS = 10000;  // one fix every 10 s

/* ---------------------------------------------------------------------------
 *  2) WIRING  (matches the SIM700/SIM800 prototype guides)
 *     SIM900  TXD -> GPIO26 (ESP32 RX1) , RXD -> GPIO27 (ESP32 TX1)
 *     NEO-6M  TX  -> GPIO16 (ESP32 RX2) , RX  -> GPIO17 (ESP32 TX2)
 *     Power the SIM900 from a dedicated 5V/2A supply (NOT the ESP32 3V3 pin),
 *     common GND with the ESP32.
 * ------------------------------------------------------------------------- */
#define MODEM_RX 26
#define MODEM_TX 27
#define GPS_RX   16
#define GPS_TX   17

HardwareSerial SerialAT(1);    // UART1 -> SIM900
HardwareSerial SerialGPS(2);   // UART2 -> NEO-6M

TinyGsm        modem(SerialAT);
TinyGsmClient  gsmClient(modem);          // plain TCP. For TLS see notes below.
PubSubClient   mqtt(gsmClient);
TinyGPSPlus    gps;

char topic[64];
char payload[256];
uint32_t lastPublish = 0;

/* ---------------------------------------------------------------------------
 *  Build a UTC epoch (ms) from the GPS clock — no RTC needed.
 * ------------------------------------------------------------------------- */
static uint64_t gpsEpochMillis() {
  if (!gps.date.isValid() || !gps.time.isValid()) return 0;
  static const int cum[] = {0,31,59,90,120,151,181,212,243,273,304,334};
  int y = gps.date.year(), m = gps.date.month(), d = gps.date.day();
  long days = (y - 1970) * 365 + (y - 1969) / 4;   // leap days since 1970
  days += cum[m - 1] + (d - 1);
  if (m > 2 && (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0))) days += 1;
  uint64_t secs = (uint64_t)days * 86400ULL
                + (uint64_t)gps.time.hour() * 3600ULL
                + (uint64_t)gps.time.minute() * 60ULL
                + (uint64_t)gps.time.second();
  return secs * 1000ULL;
}

/* ---------------------------------------------------------------------------
 *  Connect (or reconnect) GPRS + the MQTT broker.
 * ------------------------------------------------------------------------- */
bool ensureNetwork() {
  if (!modem.isNetworkConnected()) {
    Serial.println("[net] waiting for 2G network...");
    if (!modem.waitForNetwork(60000L)) { Serial.println("[net] no network"); return false; }
  }
  if (!modem.isGprsConnected()) {
    Serial.print("[net] GPRS connect... ");
    if (!modem.gprsConnect(APN, GPRS_USER, GPRS_PASS)) { Serial.println("fail"); return false; }
    Serial.println("ok");
  }
  return true;
}

bool ensureMqtt() {
  if (mqtt.connected()) return true;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(384);
  String clientId = String("dts-") + VEHICLE_ID;
  Serial.print("[mqtt] connect... ");
  bool ok = (MQTT_USER && MQTT_USER[0])
              ? mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)
              : mqtt.connect(clientId.c_str());
  Serial.println(ok ? "ok" : "fail");
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX);
  SerialGPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  Serial.println("\n[boot] starting SIM900 modem...");
  modem.restart();                       // power-cycle the modem
  snprintf(topic, sizeof(topic), "vehicles/%s/status", VEHICLE_ID);
  Serial.print("[boot] publishing to "); Serial.println(topic);
}

void loop() {
  // Feed the GPS parser continuously.
  while (SerialGPS.available()) gps.encode(SerialGPS.read());
  mqtt.loop();

  if (millis() - lastPublish < PUBLISH_EVERY_MS) return;
  lastPublish = millis();

  if (!gps.location.isValid()) { Serial.println("[gps] no fix yet"); return; }
  if (!ensureNetwork())        { return; }
  if (!ensureMqtt())           { return; }

  // Build the JSON frame — matches _PartialDecode (snake_case field names).
  uint64_t ts = gpsEpochMillis();
  int n = snprintf(payload, sizeof(payload),
    "{\"vehicle_id\":\"%s\",\"operator_id\":\"%s\",\"timestamp\":%llu,"
    "\"latitude\":%.6f,\"longitude\":%.6f,\"speed_kph\":%.1f,"
    "\"heading\":%.1f,\"engine_state\":true}",
    VEHICLE_ID, OPERATOR_ID, (unsigned long long)ts,
    gps.location.lat(), gps.location.lng(),
    gps.speed.isValid() ? gps.speed.kmph() : 0.0,
    gps.course.isValid() ? gps.course.deg() : 0.0);

  if (n > 0 && mqtt.publish(topic, payload)) {
    Serial.print("[pub] "); Serial.println(payload);
  } else {
    Serial.println("[pub] publish failed");
  }
}

/* ============================================================================
 *  NOTES
 *  ----
 *  • TLS (port 8883): replace `TinyGsmClient` with `TinyGsmClientSecure` and
 *    `mqtt.setServer(MQTT_HOST, 8883)`. 2G TLS on SIM900 is slow/limited; for a
 *    reliable prototype keep plain MQTT on a trusted network/VPN, or bench-test
 *    over the ESP32's built-in WiFi (swap gsmClient for WiFiClientSecure).
 *  • operator_id is required for the LIVE MAP (Redis geo). The position is
 *    still stored in vehicle_positions even if you omit it.
 *  • 2G is being wound down globally — use this for the bench/field prototype,
 *    and a 4G+GPS board (e.g. LilyGO T-SIM7600) for the real fleet. The broker,
 *    topic, and payload are identical; only the modem changes.
 * ========================================================================== */
