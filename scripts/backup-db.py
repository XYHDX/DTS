#!/usr/bin/env python3
"""
DamascusTransit — Supabase Database Backup
Exports all tables to JSON via the Supabase REST API.
Requires: SUPABASE_URL, SUPABASE_SERVICE_KEY in environment.
Usage: python scripts/backup-db.py [--output-dir ./backup]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Tables in FK-safe restore order (parents before children)
TABLES = [
    "users",
    "routes",
    "stops",
    "route_stops",
    "vehicles",
    "geofences",
    "trips",
    "schedules",
    "alerts",
    "audit_log",
    "vehicle_positions",
    "vehicle_positions_latest",
]

# Rows per page (Supabase REST API default max is 1000)
PAGE_SIZE = 1000


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERROR: {key} is not set", file=sys.stderr)
        sys.exit(1)
    return val


def export_table(client: httpx.Client, table: str, output_dir: Path) -> int:
    rows = []
    offset = 0
    while True:
        resp = client.get(
            f"/rest/v1/{table}",
            params={
                "select": "*",
                "limit": PAGE_SIZE,
                "offset": offset,
                "order": "created_at.asc.nullslast",
            },
        )
        if resp.status_code in (400, 404):
            # Table may not have created_at or may not support ordering; retry without
            resp = client.get(
                f"/rest/v1/{table}",
                params={"select": "*", "limit": PAGE_SIZE, "offset": offset},
            )
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    out_file = output_dir / f"{table}.json"
    out_file.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Supabase tables to JSON")
    parser.add_argument("--output-dir", default="./backup", help="Output directory")
    args = parser.parse_args()

    url = get_env("SUPABASE_URL")
    key = get_env("SUPABASE_SERVICE_KEY")

    # Normalize URL: strip /rest/v1 suffix if present, ensure no trailing slash
    base_url = url.rstrip("/").removesuffix("/rest/v1")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "count=none",
    }

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "supabase_url": base_url,
        "tables": {},
    }

    with httpx.Client(base_url=base_url, headers=headers, timeout=60.0) as client:
        for table in TABLES:
            try:
                count = export_table(client, table, output_dir)
                manifest["tables"][table] = {"rows": count, "status": "ok"}
                print(f"  {table}: {count} rows")
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 404:
                    manifest["tables"][table] = {"rows": 0, "status": "not_found"}
                    print(f"  {table}: not found (skipped)")
                else:
                    manifest["tables"][table] = {
                        "rows": 0,
                        "status": "error",
                        "detail": str(exc),
                    }
                    print(f"  {table}: ERROR {status} — {exc}", file=sys.stderr)

    manifest_file = output_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nBackup written to: {output_dir}")
    print(f"Manifest: {manifest_file}")

    errors = [t for t, v in manifest["tables"].items() if v["status"] == "error"]
    if errors:
        print(f"WARN: {len(errors)} tables had errors: {errors}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
