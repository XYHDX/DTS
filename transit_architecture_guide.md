# Enterprise Architecture Guide: Cellular Transit Telematics at Scale (100,000+ Vehicles)

This document outlines the end-to-end architectural design, edge firmware strategies, ingestion pipelines, and analytical processing structures required to run a real-time transit telemetry platform scaling to **100,000 active vehicles**.

---

## 1. Edge & Firmware Best Practices (The Device)

At 100,000 devices, firmware bugs or inefficient transmission patterns will result in massive cellular data costs, network congestion, or device battery drains.

### A. Real-Time Parsing & Data Filtering
* **Doppler Speed Extraction:** Read speed directly from the GPS NMEA sentences (`$GPRMC` or `$GPVTG` standard fields) instead of calculating $\Delta d / \Delta t$ on the server. GPS modules calculate speed using the Doppler shift of satellite signals, which is highly accurate and immune to server-side latency.
* **Intelligent Heartbeats (Adaptive Rate):** Do not send pings at a fixed interval (e.g., every 5 seconds). Use an state-driven frequency:
  * **Moving (Speed > 5 km/h):** Send every 10–15 seconds.
  * **Stationary / Idling (Speed < 5 km/h, Engine On):** Send every 60 seconds.
  * **Parked (Engine Off):** Send every 10–30 minutes (or enter sleep mode and wake up only on vibration/accelerometer trigger).

### B. Offline Queueing (Flash/EEPROM Buffer)
Network drops are inevitable. A robust device must not lose data during cellular outages.
* **Local FIFO Buffer:** Store telemetry logs on an external SPI Flash memory (e.g., W25QXX series) or internal EEPROM using a First-In-First-Out (FIFO) queue.
* **Timestamping at Edge:** Always timestamp the data at the exact moment of collection using the GPS UTC time, not when it arrives at the server.
* **Batch Uploading:** When network connectivity is restored, publish stored data in batches using a dedicated historical topic (e.g., `vehicles/+/history`) so the real-time processing engine does not get throttled.

### C. Hardware Watchdog & Power Management
* **Hardware Watchdog:** Enable the microcontroller’s hardware Watchdog Timer (WDT). If the cellular module hangs (a common occurrence with SIM900A during cell tower handovers), the WDT must reset the MCU and power-cycle the SIM module via a transistor/MOSFET on its power line.
* **Ignition Sense (ACC):** Connect the vehicle's ignition line (ACC) through an optocoupler to a digital interrupt pin on the MCU. This allows the MCU to instantly detect engine shutdown, write state to flash, and enter a low-power deep sleep mode to prevent draining the vehicle's battery.

---

## 2. Network Protocol & Payload Optimization

At 100,000 devices, transmitting verbose formats like JSON will significantly inflate data plans and increase packet fragmentation.

```
Comparison of 10-Second Telemetry Ping over 1 Month (100,000 Vehicles):
JSON (180 bytes)  =======> ~4.6 Terabytes of Data
Protobuf (35 bytes) =====> ~0.9 Terabytes of Data (80% cost reduction)
```

### A. Protocol Selection
* **Do Not Use:** HTTP/S Webhooks. The overhead of TLS handshakes and HTTP headers (often >500 bytes per request) is too high.
* **Use:** **MQTT (Message Queuing Telemetry Transport)** over TCP/TLS.
  * **QoS 0 (At Most Once):** Use for standard periodic GPS pings where losing a single coordinate is acceptable.
  * **QoS 1 (At Least Once):** Use for critical events (e.g., Engine Start/Stop, Geofence breach, Panic Button, Crash detection).
  * **Keep-Alive:** Set the MQTT keep-alive interval to 60–120 seconds. This keeps the NAT table mappings active in the cellular provider's network without consuming excessive bandwidth.

### B. Protocol Buffer (Protobuf) Schema
Define your payload using Google Protocol Buffers for maximum efficiency. Below is a production-ready `.proto` schema:

```protobuf
syntax = "proto3";

package telematics;

message VehicleStatus {
  string vehicle_id = 1;      // Unique Identifier (e.g., IMEI)
  uint64 timestamp = 2;       // Epoch time in milliseconds (GPS Time)
  
  double latitude = 3;        // GPS Latitude
  double longitude = 4;       // GPS Longitude
  float speed_gps = 5;        // Speed in km/h from NMEA $GPVTG
  float heading = 6;          // Heading/Direction in degrees
  
  bool engine_state = 7;      // True = Engine running, False = Off
  float fuel_level = 8;       // Smoothed fuel percentage (0.0 to 100.0)
  
  enum EventType {
    PERIODIC = 0;
    IGNITION_ON = 1;
    IGNITION_OFF = 2;
    GEOFENCE_ENTER = 3;
    GEOFENCE_EXIT = 4;
    HARSH_BRAKING = 5;
  }
  EventType trigger_event = 9;
}
```

---

## 3. High-Throughput Ingestion Pipeline (The Backend)

100,000 vehicles sending updates every 10 seconds results in **10,000 writes/second** average, with peak surges much higher. The backend must be horizontally scalable and decoupled.

```
[Vehicles] 
    │ (MQTT / TCP)
    ▼
[MQTT Broker Cluster (EMQX / HiveMQ)]
    │ (High-speed Rule Engine / Pub-Sub)
    ▼
[Distributed Log/Queue (Kafka / Redpanda)]
    │
    ├─► [Real-Time Consumer] ──► [Redis Geo Cache] ──► [Web Sockets / Live UI]
    │
    └─► [Analytics/Ingest Consumer] ──► [TimescaleDB / ClickHouse]
```

### A. Ingestion Tier: MQTT Broker
* Use a distributed broker cluster such as **EMQX (Open Source)** or **HiveMQ**.
* EMQX is capable of handling millions of concurrent connections and features a built-in SQL-like Rule Engine to route messages directly to Kafka without writing custom middleware.

### B. Streaming Tier: Message Queue
* Deploy **Apache Kafka** or **Redpanda** as the primary buffer.
* **Partitioning Strategy:** Partition the Kafka topics by `vehicle_id`. This guarantees that all telemetry for a specific vehicle is processed in strict chronological order by the downstream workers.

### C. Storage Tier: Time-Series Databases
* **Do not use standard relational databases (MySQL/PostgreSQL) or general NoSQL databases (MongoDB) for raw telemetry storage.** They will degrade in performance as tables grow to billions of rows.
* **Use:** 
  * **TimescaleDB:** (PostgreSQL extension for time-series) If you require complex SQL joins with business metadata (driver profiles, routing shifts).
  * **ClickHouse:** (Columnar database) Ideal if you require ultra-fast, petabyte-scale analytics and historical aggregations.

---

## 4. Telematics Analytics & Calculations

### A. Live Geofencing
Checking 100,000 coordinates against thousands of polygonal geofences every second requires highly optimized spatial indexing.
* **Low-Latency Checks (Redis Geo):** 
  * For simple circular geofences, store geofence centers in **Redis** using Geospatial indexes (`GEOADD`).
  * Check vehicle coordinates using `GEORADIUS` or `GEOSHIFT`. This runs in memory ($O(\log(N))$ complexity) and takes less than a millisecond.
* **Complex Polygons (PostGIS):**
  * Store custom geofence boundaries as polygons in **PostGIS** with a spatial index (`GIST`).
  * To avoid hitting the database for every single GPS ping, use **spatial filtering (Bounding Box)** first. Only run the expensive `ST_Contains` or `ST_Within` polygon check if the coordinate lies inside the bounding box of the geofence.

### B. Fuel & Gas Consumption
* **Fuel Level Smoothing (Edge):** Microcontrollers must read analog fuel sensors (float arms) or OBD-II fuel level data and apply an **Exponential Moving Average (EMA)** filter to remove spikes caused by fuel sloshing in the tank during acceleration, braking, or hills:
  $$S_t = \alpha \cdot Y_t + (1 - \alpha) \cdot S_{t-1}$$
  *(Where $Y_t$ is the raw sensor reading, $S_{t-1}$ is the previous smoothed value, and $\alpha \approx 0.1$ is the smoothing factor)*
* **Consumption Computations (Cloud):** 
  * Rather than trusting raw delta values, compute fuel consumption by correlating GPS speed, RPM (if OBD-II is available), and changes in the smoothed fuel level. 
  * Detect refuel and theft events by calculating sudden positive or negative steps in fuel volume while the engine state is off.

---

## 5. SIM900A MVP Integration Reference

For your immediate MVP, here is the robust AT command sequence to initialize GPRS and connect to your MQTT server/endpoint:

```ini
; 1. Reset and check module status
AT
AT+CFUN=1          ; Set full phone functionality
AT+CPIN?           ; Verify SIM card status (should return READY)

; 2. Configure GPRS connection
AT+CGATT=1         ; Attach to GPRS service
AT+SAPBR=3,1,"CONTYPE","GPRS"
AT+SAPBR=3,1,"APN","YOUR_SIM_APN"  ; Replace with your cellular provider APN
AT+SAPBR=1,1       ; Open bearer profile
AT+SAPBR=2,1       ; Query bearer profile IP (verify GPRS is active)

; 3. Use TCP to connect to your MQTT Broker
AT+CIPSTART="TCP","mqtt.yourbroker.com","1883"
; Wait for "CONNECT OK" response

; 4. Send raw MQTT Connect & Publish packets (via binary transmission)
AT+CIPSEND
; [Send your binary MQTT packet here]
; Send Ctrl+Z (0x1A) to execute transmission
```

> [!TIP]
> While the SIM900A has a built-in HTTP client (`AT+HTTPINIT`), it is highly unstable for continuous data streaming. For the MVP, establishing a raw TCP connection via `AT+CIPSTART` and handling the MQTT protocol header over that TCP socket is significantly more reliable.
