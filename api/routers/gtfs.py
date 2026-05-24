import io
import os
import time
import zipfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from api.core.cache import RATE_LIMIT_READ, _get_client_ip, _rate_limit_check
from api.core.database import _supabase_get
from api.core.geo import parse_location
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

GTFS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "db", "gtfs")

# In-memory GTFS-RT cache (15-second TTL)
_GTFS_RT_CACHE_TTL = 15
_gtfs_rt_cache: dict = {"data": None, "timestamp": 0.0, "content_type": None}


def _gtfs_rt_occupancy_status(occupancy_pct, pb_cls):
    """Map 0-100 occupancy percentage to GTFS-RT OccupancyStatus enum."""
    if occupancy_pct is None:
        return None
    if occupancy_pct <= 0:
        return pb_cls.EMPTY
    if occupancy_pct <= 25:
        return pb_cls.MANY_SEATS_AVAILABLE
    if occupancy_pct <= 50:
        return pb_cls.FEW_SEATS_AVAILABLE
    if occupancy_pct <= 75:
        return pb_cls.STANDING_ROOM_ONLY
    return pb_cls.FULL


# Maps our alert_type to GTFS-RT Alert Cause/Effect
_ALERT_CAUSE_MAP = {
    "speed_violation": "OTHER_CAUSE",
    "route_deviation": "CONSTRUCTION",
    "geofence_exit": "OTHER_CAUSE",
    "breakdown": "TECHNICAL_PROBLEM",
    "delay": "OTHER_CAUSE",
    "sos": "OTHER_CAUSE",
    "maintenance_due": "MAINTENANCE",
    "connection_lost": "TECHNICAL_PROBLEM",
}

_ALERT_EFFECT_MAP = {
    "speed_violation": "UNKNOWN_EFFECT",
    "route_deviation": "DETOUR",
    "geofence_exit": "UNKNOWN_EFFECT",
    "breakdown": "NO_SERVICE",
    "delay": "SIGNIFICANT_DELAYS",
    "sos": "NO_SERVICE",
    "maintenance_due": "REDUCED_SERVICE",
    "connection_lost": "UNKNOWN_EFFECT",
}

_SEVERITY_TO_LEVEL = {
    "critical": "SEVERE",
    "warning": "WARNING",
    "info": "INFO",
}


def _parse_iso_timestamp(iso_str: Optional[str]) -> Optional[int]:
    """Convert ISO-8601 string to UNIX timestamp."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return None


@router.get("/api/gtfs/static/{filename}", tags=["gtfs"])
async def get_gtfs_static_file(raw_request: Request, filename: str):
    """Serve individual GTFS static feed files."""
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"gtfs:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    allowed = {
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "calendar.txt",
        "feed_info.txt",
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="File not found")

    filepath = os.path.join(GTFS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{filename} not found")


@router.get("/api/gtfs/feed.zip", tags=["gtfs"])
async def get_gtfs_zip(raw_request: Request):
    """Download full GTFS static feed as a ZIP archive (Google Maps compatible)."""
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"gtfs:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )
    files = [
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "calendar.txt",
        "feed_info.txt",
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            filepath = os.path.join(GTFS_DIR, name)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    zf.writestr(name, f.read())
            except FileNotFoundError:
                raise HTTPException(
                    status_code=500, detail=f"GTFS file missing: {name}"
                )
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=gtfs_feed.zip"},
    )


async def _build_gtfs_rt_feed():
    """Build the GTFS-RT feed with VehiclePositions, TripUpdates, and Alerts."""

    positions = await _supabase_get(
        "vehicle_positions_latest"
        "?select=vehicle_id,location,speed_kmh,heading,"
        "occupancy_pct,recorded_at"
    )
    positions = positions or []

    vehicles_raw = await _supabase_get(
        "vehicles?select=id,vehicle_id,name,assigned_route_id"
    )
    vehicles_by_uuid = {v["id"]: v for v in (vehicles_raw or [])}

    routes_raw = await _supabase_get("routes?select=id,route_id")
    route_id_by_uuid = {r["id"]: r["route_id"] for r in (routes_raw or [])}

    trips_raw = await _supabase_get(
        "trips?select=id,vehicle_id,route_id,actual_start&status=eq.in_progress"
    )
    trips_by_vehicle = {t["vehicle_id"]: t for t in (trips_raw or [])}

    alerts_raw = await _supabase_get(
        "alerts?is_resolved=eq.false"
        "&select=id,vehicle_id,alert_type,severity,title,title_ar,"
        "description,created_at"
        "&order=created_at.desc&limit=50"
    )
    alerts_raw = alerts_raw or []

    # Fetch route_stops for TripUpdate StopTimeUpdates
    route_stops_raw = await _supabase_get(
        "route_stops?select=route_id,stop_id,stop_sequence,"
        "typical_arrival_offset_min&order=stop_sequence.asc"
    )
    stops_by_route: dict = {}
    for rs in route_stops_raw or []:
        rid = rs["route_id"]
        stops_by_route.setdefault(rid, []).append(rs)

    try:
        from google.transit import gtfs_realtime_pb2  # type: ignore

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET
        feed.header.timestamp = int(time.time())

        # --- VehiclePosition entities ---
        for pos in positions:
            lat, lon = parse_location(pos.get("location"))
            if lat is None or lon is None:
                continue

            vehicle = vehicles_by_uuid.get(pos.get("vehicle_id"))
            if not vehicle:
                continue

            trip = trips_by_vehicle.get(pos["vehicle_id"])
            route_text_id = route_id_by_uuid.get(
                vehicle.get("assigned_route_id", ""), ""
            )

            entity = feed.entity.add()
            entity.id = f"vp_{pos['vehicle_id']}"

            vp = entity.vehicle
            vp.vehicle.id = vehicle["vehicle_id"]
            vp.vehicle.label = vehicle.get("name", "")

            if trip:
                vp.trip.trip_id = trip["id"]
            if route_text_id:
                vp.trip.route_id = route_text_id

            vp.position.latitude = float(lat)
            vp.position.longitude = float(lon)

            if pos.get("speed_kmh") is not None:
                vp.position.speed = float(pos["speed_kmh"]) / 3.6
            if pos.get("heading") is not None:
                vp.position.bearing = float(pos["heading"])

            ts = _parse_iso_timestamp(pos.get("recorded_at"))
            if ts:
                vp.timestamp = ts

            occ = _gtfs_rt_occupancy_status(
                pos.get("occupancy_pct"), gtfs_realtime_pb2.VehiclePosition
            )
            if occ is not None:
                vp.occupancy_status = occ

        # --- TripUpdate entities with StopTimeUpdates ---
        for trip in trips_raw or []:
            vehicle = vehicles_by_uuid.get(trip["vehicle_id"])
            route_text_id = route_id_by_uuid.get(trip.get("route_id", ""), "")

            entity = feed.entity.add()
            entity.id = f"tu_{trip['id']}"

            tu = entity.trip_update
            tu.trip.trip_id = trip["id"]
            if route_text_id:
                tu.trip.route_id = route_text_id

            if vehicle:
                tu.vehicle.id = vehicle["vehicle_id"]
                tu.vehicle.label = vehicle.get("name", "")

            ts = _parse_iso_timestamp(trip.get("actual_start"))
            if ts:
                tu.timestamp = ts

            # Add StopTimeUpdates from route_stops schedule offsets
            route_uuid = trip.get("route_id")
            route_stops = stops_by_route.get(route_uuid, [])
            if route_stops and ts:
                for rs in route_stops:
                    offset_min = rs.get("typical_arrival_offset_min")
                    if offset_min is None:
                        continue
                    stu = tu.stop_time_update.add()
                    stu.stop_sequence = rs["stop_sequence"]
                    stu.stop_id = rs["stop_id"]
                    stu.arrival.time = ts + (int(offset_min) * 60)

        # --- Alert entities ---
        for alert_row in alerts_raw:
            entity = feed.entity.add()
            entity.id = f"al_{alert_row['id']}"

            al = entity.alert

            # Map cause
            cause_name = _ALERT_CAUSE_MAP.get(
                alert_row.get("alert_type", ""), "UNKNOWN_CAUSE"
            )
            al.cause = getattr(
                gtfs_realtime_pb2.Alert,
                cause_name,
                gtfs_realtime_pb2.Alert.UNKNOWN_CAUSE,
            )

            # Map effect
            effect_name = _ALERT_EFFECT_MAP.get(
                alert_row.get("alert_type", ""), "UNKNOWN_EFFECT"
            )
            al.effect = getattr(
                gtfs_realtime_pb2.Alert,
                effect_name,
                gtfs_realtime_pb2.Alert.UNKNOWN_EFFECT,
            )

            # Severity level
            severity_name = _SEVERITY_TO_LEVEL.get(
                alert_row.get("severity", ""), "INFO"
            )
            severity_val = getattr(gtfs_realtime_pb2.Alert, severity_name, None)
            if severity_val is not None:
                al.severity_level = severity_val

            # Header text (English + Arabic)
            header = al.header_text.translation.add()
            header.language = "en"
            header.text = alert_row.get("title", "")

            if alert_row.get("title_ar"):
                header_ar = al.header_text.translation.add()
                header_ar.language = "ar"
                header_ar.text = alert_row["title_ar"]

            # Description text
            if alert_row.get("description"):
                desc = al.description_text.translation.add()
                desc.language = "en"
                desc.text = alert_row["description"]

            # Active period
            created_ts = _parse_iso_timestamp(alert_row.get("created_at"))
            if created_ts:
                period = al.active_period.add()
                period.start = created_ts

            # Informed entity — link to the affected vehicle's route
            vehicle = vehicles_by_uuid.get(alert_row.get("vehicle_id"))
            if vehicle:
                ie = al.informed_entity.add()
                route_text_id = route_id_by_uuid.get(
                    vehicle.get("assigned_route_id", ""), ""
                )
                if route_text_id:
                    ie.route_id = route_text_id

        return (
            feed.SerializeToString(),
            "application/x-protobuf",
        )

    except ImportError:
        # Fallback: JSON representation when protobuf bindings not installed
        feed_json = {
            "header": {
                "gtfs_realtime_version": "2.0",
                "incrementality": "FULL_DATASET",
                "timestamp": int(time.time()),
            },
            "entity": [],
        }
        for p in positions:
            p_lat, p_lon = parse_location(p.get("location"))
            if p_lat is None or p_lon is None:
                continue
            vehicle = vehicles_by_uuid.get(p.get("vehicle_id"))
            if not vehicle:
                continue
            route_text_id = route_id_by_uuid.get(
                vehicle.get("assigned_route_id", ""), ""
            )
            feed_json["entity"].append(
                {
                    "id": f"vp_{p['vehicle_id']}",
                    "vehicle": {
                        "vehicle": {
                            "id": vehicle["vehicle_id"],
                            "label": vehicle.get("name", ""),
                        },
                        "trip": {"route_id": route_text_id},
                        "position": {
                            "latitude": p_lat,
                            "longitude": p_lon,
                            "speed": (p.get("speed_kmh") or 0.0) / 3.6,
                        },
                        "timestamp": int(time.time()),
                    },
                }
            )
        for alert_row in alerts_raw:
            feed_json["entity"].append(
                {
                    "id": f"al_{alert_row['id']}",
                    "alert": {
                        "cause": _ALERT_CAUSE_MAP.get(
                            alert_row.get("alert_type", ""), "UNKNOWN_CAUSE"
                        ),
                        "effect": _ALERT_EFFECT_MAP.get(
                            alert_row.get("alert_type", ""), "UNKNOWN_EFFECT"
                        ),
                        "header_text": alert_row.get("title", ""),
                        "description_text": alert_row.get("description", ""),
                    },
                }
            )

        import json

        return (
            json.dumps(feed_json).encode(),
            "application/json",
        )


@router.get("/api/gtfs/realtime", tags=["gtfs"])
@router.get("/api/public/gtfs-rt", tags=["gtfs"])
async def get_gtfs_realtime(raw_request: Request):
    """GTFS-Realtime feed (VehiclePositions + TripUpdates + Alerts).

    Returns a binary protobuf FeedMessage (GTFS-RT 2.0).
    Cached in-memory for 15 seconds.
    Falls back to JSON when gtfs-realtime-bindings is not installed.
    """
    client_ip = _get_client_ip(raw_request)
    max_req, window = RATE_LIMIT_READ
    if not await _rate_limit_check(f"gtfs:{client_ip}", max_req, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(window)},
        )

    # Serve from in-memory cache if fresh
    now = time.time()
    if (
        _gtfs_rt_cache["data"] is not None
        and (now - _gtfs_rt_cache["timestamp"]) < _GTFS_RT_CACHE_TTL
    ):
        return Response(
            content=_gtfs_rt_cache["data"],
            media_type=_gtfs_rt_cache["content_type"],
            headers={"X-GTFS-RT-Version": "2.0", "X-Cache": "HIT"},
        )

    try:
        data, content_type = await _build_gtfs_rt_feed()

        # Update in-memory cache
        _gtfs_rt_cache["data"] = data
        _gtfs_rt_cache["timestamp"] = time.time()
        _gtfs_rt_cache["content_type"] = content_type

        return Response(
            content=data,
            media_type=content_type,
            headers={"X-GTFS-RT-Version": "2.0", "X-Cache": "MISS"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
