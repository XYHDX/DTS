"""
Tests for GTFS static feed endpoints and Google Maps compatibility.

Validates:
- All 7 required GTFS files served via /api/gtfs/static/{filename}
- ZIP bundle at /api/gtfs/feed.zip contains all required files
- 8 Damascus routes present
- 42 stops with valid coordinate ranges
- Referential integrity (trips→routes, stop_times→stops/trips)
- stop_times time format and sequence validity
- 404 for unknown files (path traversal prevention)
- ZIP bundle referential integrity
"""

import csv
import io
import os
import zipfile

import pytest

os.environ.setdefault("SUPABASE_URL", "http://mock-supabase.local")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock-anon-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only-xxxxxxxxxxxxxx")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


@pytest.fixture(scope="module")
def client():
    from api.index import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


REQUIRED_FILES = [
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
    "feed_info.txt",
]


def _read_csv_from_text(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


class TestGTFSStaticFiles:
    """Each required GTFS file is served correctly."""

    @pytest.mark.parametrize("filename", REQUIRED_FILES)
    def test_static_file_returns_200(self, client, filename):
        resp = client.get(f"/api/gtfs/static/{filename}")
        assert resp.status_code == 200, f"{filename} returned {resp.status_code}"

    @pytest.mark.parametrize("filename", REQUIRED_FILES)
    def test_static_file_content_type(self, client, filename):
        resp = client.get(f"/api/gtfs/static/{filename}")
        assert "text/plain" in resp.headers["content-type"]

    def test_unknown_file_returns_404(self, client):
        resp = client.get("/api/gtfs/static/unknown.txt")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client):
        resp = client.get("/api/gtfs/static/../requirements.txt")
        assert resp.status_code in (404, 422)

    def test_routes_has_eight_damascus_routes(self, client):
        resp = client.get("/api/gtfs/static/routes.txt")
        rows = _read_csv_from_text(resp.text)
        assert len(rows) == 8, f"Expected 8 routes, got {len(rows)}"

    def test_routes_have_required_fields(self, client):
        resp = client.get("/api/gtfs/static/routes.txt")
        rows = _read_csv_from_text(resp.text)
        required = {
            "route_id",
            "agency_id",
            "route_short_name",
            "route_long_name",
            "route_type",
        }
        assert required <= set(rows[0].keys())

    def test_routes_are_bus_type(self, client):
        resp = client.get("/api/gtfs/static/routes.txt")
        rows = _read_csv_from_text(resp.text)
        for r in rows:
            assert r["route_type"] == "3", f"Route {r['route_id']} is not bus type 3"

    def test_stops_has_42_stops(self, client):
        resp = client.get("/api/gtfs/static/stops.txt")
        rows = _read_csv_from_text(resp.text)
        assert len(rows) == 42, f"Expected 42 stops, got {len(rows)}"

    def test_stops_have_required_fields(self, client):
        resp = client.get("/api/gtfs/static/stops.txt")
        rows = _read_csv_from_text(resp.text)
        required = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
        assert required <= set(rows[0].keys())

    def test_stops_coordinates_in_damascus_range(self, client):
        """All stops must fall within the greater Damascus area."""
        resp = client.get("/api/gtfs/static/stops.txt")
        rows = _read_csv_from_text(resp.text)
        out_of_range = []
        for s in rows:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
            if not (33.0 <= lat <= 34.0 and 35.5 <= lon <= 37.0):
                out_of_range.append(f"{s['stop_id']}: ({lat}, {lon})")
        assert not out_of_range, f"Stops outside Damascus range: {out_of_range}"

    def test_trips_reference_valid_routes(self, client):
        routes_resp = client.get("/api/gtfs/static/routes.txt")
        trips_resp = client.get("/api/gtfs/static/trips.txt")
        route_ids = {r["route_id"] for r in _read_csv_from_text(routes_resp.text)}
        trips = _read_csv_from_text(trips_resp.text)
        bad = [t["trip_id"] for t in trips if t["route_id"] not in route_ids]
        assert not bad, f"Trips with unknown route_id: {bad}"

    def test_trips_reference_valid_service_ids(self, client):
        calendar_resp = client.get("/api/gtfs/static/calendar.txt")
        trips_resp = client.get("/api/gtfs/static/trips.txt")
        service_ids = {r["service_id"] for r in _read_csv_from_text(calendar_resp.text)}
        trips = _read_csv_from_text(trips_resp.text)
        bad = [t["trip_id"] for t in trips if t["service_id"] not in service_ids]
        assert not bad, f"Trips with unknown service_id: {bad}"

    def test_stop_times_reference_valid_trips(self, client):
        trips_resp = client.get("/api/gtfs/static/trips.txt")
        st_resp = client.get("/api/gtfs/static/stop_times.txt")
        trip_ids = {t["trip_id"] for t in _read_csv_from_text(trips_resp.text)}
        stop_times = _read_csv_from_text(st_resp.text)
        bad = {st["trip_id"] for st in stop_times if st["trip_id"] not in trip_ids}
        assert not bad, f"stop_times referencing unknown trip_ids: {bad}"

    def test_stop_times_reference_valid_stops(self, client):
        stops_resp = client.get("/api/gtfs/static/stops.txt")
        st_resp = client.get("/api/gtfs/static/stop_times.txt")
        stop_ids = {s["stop_id"] for s in _read_csv_from_text(stops_resp.text)}
        stop_times = _read_csv_from_text(st_resp.text)
        bad = {st["stop_id"] for st in stop_times if st["stop_id"] not in stop_ids}
        assert not bad, f"stop_times referencing unknown stop_ids: {bad}"

    def test_stop_times_time_format(self, client):
        """All times must match HH:MM:SS format."""
        import re

        time_re = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
        resp = client.get("/api/gtfs/static/stop_times.txt")
        stop_times = _read_csv_from_text(resp.text)
        bad = []
        for st in stop_times:
            for field in ("arrival_time", "departure_time"):
                if not time_re.match(st[field]):
                    bad.append(
                        f"{st['trip_id']}:{st['stop_sequence']} {field}={st[field]}"
                    )
        assert not bad, f"Invalid time formats: {bad[:5]}"

    def test_each_trip_has_at_least_two_stops(self, client):
        from collections import Counter

        resp = client.get("/api/gtfs/static/stop_times.txt")
        counts = Counter(st["trip_id"] for st in _read_csv_from_text(resp.text))
        short = [tid for tid, c in counts.items() if c < 2]
        assert not short, f"Trips with < 2 stops: {short}"


class TestGTFSFeedZip:
    """ZIP bundle endpoint for Google Maps compatibility."""

    def test_zip_returns_200(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        assert resp.status_code == 200

    def test_zip_content_type(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        assert resp.headers["content-type"] == "application/zip"

    def test_zip_has_content_disposition(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_zip_contains_all_required_files(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            names = set(z.namelist())
        missing = set(REQUIRED_FILES) - names
        assert not missing, f"ZIP missing: {missing}"

    def test_zip_routes_count(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            rows = _read_csv_from_text(z.read("routes.txt").decode())
        assert len(rows) == 8

    def test_zip_stops_count(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            rows = _read_csv_from_text(z.read("stops.txt").decode())
        assert len(rows) == 42

    def test_zip_referential_integrity(self, client):
        resp = client.get("/api/gtfs/feed.zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            routes = _read_csv_from_text(z.read("routes.txt").decode())
            trips = _read_csv_from_text(z.read("trips.txt").decode())
            stops = _read_csv_from_text(z.read("stops.txt").decode())
            stop_times = _read_csv_from_text(z.read("stop_times.txt").decode())

        route_ids = {r["route_id"] for r in routes}
        stop_ids = {s["stop_id"] for s in stops}
        trip_ids = {t["trip_id"] for t in trips}

        bad_trips = [t["trip_id"] for t in trips if t["route_id"] not in route_ids]
        assert not bad_trips

        bad_st_trips = {
            st["trip_id"] for st in stop_times if st["trip_id"] not in trip_ids
        }
        assert not bad_st_trips

        bad_st_stops = {
            st["stop_id"] for st in stop_times if st["stop_id"] not in stop_ids
        }
        assert not bad_st_stops
