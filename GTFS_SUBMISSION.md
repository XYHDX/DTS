# Google Maps Transit Partner Submission Guide

## Overview

This document describes how to submit the Damascus Transit System GTFS feed to
Google Maps Transit. Once accepted, Damascus bus routes and stop information will
appear natively in Google Maps for passengers.

---

## Feed Endpoints

| Purpose | URL |
|---|---|
| GTFS Static ZIP (Google Maps upload) | `GET /api/gtfs/feed.zip` |
| Individual static files | `GET /api/gtfs/static/{filename}` |
| GTFS-Realtime (VehiclePositions + TripUpdates) | `GET /api/gtfs/realtime` |
| GTFS-RT alias | `GET /api/public/gtfs-rt` |

All endpoints are publicly accessible (no auth required).

---

## Feed Contents

| File | Description | Status |
|---|---|---|
| `agency.txt` | Damascus Transit operator info | ✅ |
| `routes.txt` | 8 Damascus bus routes (R001–R008) | ✅ |
| `stops.txt` | 42 stops with Arabic names and GPS coordinates | ✅ |
| `trips.txt` | 24 trips (3 per route, weekday service) | ✅ |
| `stop_times.txt` | Timetabled arrival/departure times | ✅ |
| `calendar.txt` | Weekday (WD) and weekend (WE) service patterns | ✅ |
| `feed_info.txt` | Feed publisher metadata | ✅ |

---

## Submission Steps

### 1. Validate the Feed

Before submitting, run the full validation suite locally:

```bash
# API-level tests (endpoint + referential integrity)
pytest tests/test_gtfs_static.py tests/test_gtfs_rt.py -v

# Official MobilityData canonical validator (requires Java 11+)
# Download: https://github.com/MobilityData/gtfs-validator/releases
cd db/gtfs
zip -j ../../gtfs_feed.zip agency.txt stops.txt routes.txt trips.txt stop_times.txt calendar.txt feed_info.txt
cd ../..
java -jar gtfs-validator.jar --input gtfs_feed.zip --output_base gtfs_out --country_code sy
```

The CI workflow (`.github/workflows/gtfs-validate.yml`) runs both validators
automatically on every push that touches GTFS files.

### 2. Apply to Google Maps Transit Partner Program

1. Go to the [Google Transit Partner Program](https://maps.google.com/landing/transit/partners/index.html)
2. Click **Apply Now** → fill in the agency form:
   - Agency name: **Damascus Transit System**
   - Country: **Syria**
   - Language: **Arabic (ar)**
   - Time zone: **Asia/Damascus**
3. When asked for the feed URL, provide the hosted ZIP endpoint:
   ```
   https://syrian-transit-system.vercel.app/api/gtfs/feed.zip
   ```
4. For real-time data, provide:
   ```
   https://syrian-transit-system.vercel.app/api/gtfs/realtime
   ```
5. Accept the Data Sharing Agreement.
6. Google review typically takes **2–6 weeks**.

### 3. After Approval

- Google will ingest the feed automatically on a regular schedule (typically daily).
- Monitor feed health via the **Google Transit Partner Portal** once access is
  granted.
- To update routes/stops/times, update the files in `db/gtfs/` and push to
  `main` — CI validates and deploys automatically.

---

## Feed Maintenance

### Adding or Changing Routes

1. Edit the relevant files in `db/gtfs/`:
   - New route: add a row to `routes.txt`
   - New stops: add rows to `stops.txt`
   - New trips + timetables: add to `trips.txt` and `stop_times.txt`
2. Run `pytest tests/test_gtfs_static.py -v` to verify counts and integrity.
3. Commit and push — CI validates and deploys.

### Updating Schedules

Edit `stop_times.txt` and, if service patterns change, `calendar.txt`. All times
must use `HH:MM:SS` format (24-hour). Times after midnight may exceed `24:00:00`
(e.g. `25:30:00` for 1:30 AM of the following service day).

### GTFS-RT Feed

The real-time feed is generated dynamically from the live database
(`vehicle_positions_latest` and `trips` tables). No manual updates are needed
for real-time data — it reflects current vehicle positions and in-progress trips
automatically.

---

## Validation Reference

The following checks run automatically in CI:

| Check | Test |
|---|---|
| All 7 required files present | `test_static_file_returns_200` |
| 8 routes, all type=3 (bus) | `test_routes_has_eight_damascus_routes` |
| 42 stops in Damascus lat/lon range | `test_stops_has_42_stops`, `test_stops_coordinates_in_damascus_range` |
| Trips reference valid routes + service_ids | `test_trips_reference_valid_routes/service_ids` |
| stop_times reference valid trips + stops | `test_stop_times_reference_valid_*` |
| Time format `HH:MM:SS` | `test_stop_times_time_format` |
| Each trip has ≥ 2 stops | `test_each_trip_has_at_least_two_stops` |
| ZIP bundle integrity | `TestGTFSFeedZip` |
| GTFS-RT protobuf valid | `TestGTFSRealtime` |
| Canonical MobilityData validator (no ERRORs) | CI workflow |

---

## Contacts

- **Feed owner:** Damascus Transit System Engineering
- **Technical contact:** Platform Engineer (Paperclip agent `platform-engineer`)
- **Submission tracker:** [DAM-306](/DAM/issues/DAM-306)
