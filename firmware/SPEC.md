# DamascusTransit — edge firmware specification

> Step S6.1 of `Scale_100k_Roadmap.md`. Companion to `docs/transit_architecture_guide.md` §1 + §5. This document is **for firmware authors**. The reference C++ implementation will live under `firmware/sim900a-reference/` once written.

## Target hardware

| Component | Recommended part | Notes |
|---|---|---|
| MCU | STM32F4 (Cortex-M4) or ESP32-S3 | Both have a hardware watchdog, SPI master, multiple UARTs, and external flash interface. |
| Cellular modem | SIM900A (MVP) → Quectel BG95-M3 or SIMCom A7670 (production) | SIM900A is fine for the pilot. The Quectel modules are LTE-Cat M1 + NB-IoT and survive Damascus' patchy coverage better. |
| GPS module | u-blox NEO-6M / NEO-M9N | NEO-M9N gives sub-3 m HDOP. NMEA at 9600 baud is enough. |
| External flash | Winbond W25Q64 (8 MB SPI) | For the FIFO offline buffer per §1.B. 8 MB stores ~200,000 telemetry frames. |
| Power management | TPS5430 + LM2596 step-downs; supercap on the modem rail | Survives the brown-outs of an old bus battery during cranking. |
| Ignition sense | PC817 optocoupler on the ACC line → MCU GPIO with falling-edge IRQ | §1.C. The optocoupler keeps a 12 V vehicle line from frying a 3.3 V MCU. |
| SIM reset | AO3401 P-MOSFET on the modem Vbat | The WDT cuts modem power if the AT bus hangs (§1.C). |
| Backup battery | 1S LiPo with TP4056 charger | Powers the device for ~8 hours after ignition off, enough to send the IGNITION_OFF event and any remaining FIFO. |

## Wire format

Everything goes over **Protobuf** as defined in `schemas/telematics.proto`. The same `VehicleStatus` message is used for periodic pings and for trigger events — the `trigger_event` field distinguishes them.

**Field-numbering policy:** fields 1–15 carry the hot-path payload and pack into 1-byte tags. Fields 16+ are optional context.

**Target payload size:** 35–50 bytes per periodic ping (vs ~180 bytes JSON). At 100k vehicles × 6 pings/min × 30 days that's 0.9 TB egress per month — about 80% less than JSON.

## Adaptive heartbeat tiers

Per §1.A. State machine, evaluated every second:

| State | Condition | Interval |
|---|---|---|
| MOVING | Doppler speed > 5 km/h | **10 s** (15 s on poor signal) |
| IDLING | Engine ON, speed < 5 km/h | **60 s** |
| PARKED | Engine OFF | **enter deep sleep**, wake on accelerometer or after 30 min |

Transitions emit an immediate frame regardless of the interval (with `trigger_event = IGNITION_ON/OFF` or similar).

## Position reading

- Speed comes from the GPS NMEA `$GPVTG` sentence directly. **Never** compute speed server-side from `Δd / Δt`; the guide is explicit about this (§1.A).
- Timestamp comes from the GPS UTC fix, not from the modem clock. The modem clock drifts.
- Reject readings with HDOP > 5 or fewer than 4 satellites — they fail the indoor-or-tunnel check.

## Offline FIFO buffer

Per §1.B. On every periodic frame:

1. Try to publish via MQTT (or the HTTP bridge during phase S2).
2. On success: nothing else.
3. On failure: append the frame to the FIFO buffer in W25Q64, increment the buffer head pointer.
4. On reconnect: drain the FIFO in batches of up to 64 frames, each wrapped in `VehicleStatusBatch` with `is_replay = true`. Pause for 100 ms between batches so the broker rule engine isn't slammed.

Buffer occupancy is exposed as a custom metric — see "Health breadcrumbs" below.

## Hardware watchdog + ignition

- Configure the MCU's independent watchdog timer for a 30-second timeout. Pet it at the top of the main loop. If the AT bus hangs the WDT resets the MCU, which during boot also pulls the modem Vbat low for 1 s before re-energising it (§1.C).
- The optocoupler-driven IRQ on the ACC line fires on engine off. The IRQ handler:
  1. Writes the current GPS fix + uptime to flash.
  2. Sends an `IGNITION_OFF` frame with QoS 1.
  3. Enters STOP2 sleep on STM32 (or deep-sleep on ESP32-S3) after 60 s grace.

## Health breadcrumbs

Populate fields 20–24 of `VehicleStatus` on **every** frame. They're cheap (under 10 bytes total) and turn debugging from a session into a glance:

- `satellite_count` — when this drops below 4, the position is suspect.
- `hdop` — sanity gate before persisting on the server.
- `cell_signal_dbm` — for ops to map coverage holes.
- `firmware_version` — packed semver, makes A/B firmware rollouts measurable.
- `battery_mv` — the backup battery, not the vehicle battery.

## SIM900A MVP — AT command sequence

Lift directly from §5 of the architecture guide
(`docs/transit_architecture_guide.md`). Broker host/port and topic layout:
`instructions/HARDWARE_SETUP.md` §2. Verbatim:

```
AT
AT+CFUN=1
AT+CPIN?
AT+CGATT=1
AT+SAPBR=3,1,"CONTYPE","GPRS"
AT+SAPBR=3,1,"APN","YOUR_SIM_APN"
AT+SAPBR=1,1
AT+SAPBR=2,1
AT+CIPSTART="TCP","mqtt.damascustransit.sy","8883"
;  -- wait CONNECT OK --
AT+CIPSEND
;  -- send binary MQTT CONNECT packet, then Ctrl+Z (0x1A) --
```

After CONNECT, the device:

1. Sends MQTT SUBSCRIBE to `vehicles/<vehicle_id>/ack` with QoS 1 to get receipts (per the `Ack` message in `schemas/telematics.proto`).
2. Begins publishing periodic frames at the adaptive heartbeat rate, to topic `vehicles/<vehicle_id>/status`.
3. Sends critical events to `vehicles/<vehicle_id>/event` with QoS 1.

## Security on-device

- Each device has its own X.509 client certificate provisioned at flashing time. Stored on the SIM module's secure element if available (BG95 has one), in the flash header otherwise.
- The MQTT broker pins client certificates per `vehicle_id` so a stolen device cannot impersonate another.
- HMAC for the HTTP bridge path: `DEVICE_INGEST_SECRET` is unique per device, baked into flash at provisioning, never transmitted over the air after provisioning.

## CI for the firmware

When the reference firmware lands:

- Build a docker image with the STM32CubeMX toolchain + PlatformIO.
- A GitHub Actions workflow `firmware.yml` does `pio run -e sim900a` and uploads the `.bin` as an artefact.
- A second workflow runs `cppcheck` and `clang-tidy` on every PR.
- Unit-test the FIFO logic with a host build target (`pio run -e native`) so the algorithm is exercised without hardware.

## Pre-deployment checklist

Before flashing the first 100 devices:

- [ ] WDT verified to actually fire under simulated AT-bus hang.
- [ ] FIFO survives a power cycle mid-write (atomic page commit).
- [ ] X.509 client certificate present and tested against the production broker.
- [ ] OTA update path tested at least once (`AT+FSCREATE`, then verify checksum).
- [ ] `firmware_version` field is correct and matches the `git tag` of the binary.
- [ ] Cell signal-loss test: drive into an underground parking and back out; FIFO must drain on reconnect.
- [ ] Ignition-off path: verify the MCU writes state to flash and the IGNITION_OFF frame lands with QoS 1.

## What does *not* belong on the device

For clarity — the architecture guide explicitly recommends *against* doing these on the edge:

- ❌ Computing speed from positions (use NMEA Doppler).
- ❌ Computing fuel consumption (only smooth raw level, send up to the cloud).
- ❌ Geofence membership checks — the cloud has the polygon shapes.
- ❌ Trip stitching — that's a cloud worker.
- ❌ JSON encoding — Protobuf only.

Keep the device dumb, ordered, and reliable. Everything else is the cloud's job.
