#!/usr/bin/env python3
"""
DamascusTransit — Supabase Database Restore
Restores tables from a JSON backup directory.
Requires: SUPABASE_URL, SUPABASE_SERVICE_KEY in environment.
Usage: python scripts/restore-db.py --backup-dir ./backup [--tables routes,stops] [--dry-run]

WARNING: This UPSERTS rows (insert or replace by primary key).
         It does NOT truncate tables first. Run truncate manually if a clean
         restore is required. See DR.md for the full procedure.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# FK-safe restore order (parents before children)
RESTORE_ORDER = [
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

BATCH_SIZE = 500  # rows per upsert request


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERROR: {key} is not set", file=sys.stderr)
        sys.exit(1)
    return val


def upsert_batch(client: httpx.Client, table: str, rows: list) -> None:
    resp = client.post(
        f"/rest/v1/{table}",
        json=rows,
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    resp.raise_for_status()


def restore_table(
    client: httpx.Client, table: str, backup_dir: Path, dry_run: bool
) -> int:
    table_file = backup_dir / f"{table}.json"
    if not table_file.exists():
        print(f"  {table}: no backup file, skipping")
        return 0

    rows = json.loads(table_file.read_text(encoding="utf-8"))
    if not rows:
        print(f"  {table}: 0 rows (empty backup)")
        return 0

    if dry_run:
        print(f"  {table}: DRY RUN — would restore {len(rows)} rows")
        return len(rows)

    restored = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        upsert_batch(client, table, batch)
        restored += len(batch)

    print(f"  {table}: restored {restored} rows")
    return restored


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore Supabase tables from JSON backup"
    )
    parser.add_argument("--backup-dir", required=True, help="Backup directory path")
    parser.add_argument(
        "--tables",
        help="Comma-separated table names (default: all in restore order)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate backup files without writing to DB",
    )
    args = parser.parse_args()

    url = get_env("SUPABASE_URL")
    key = get_env("SUPABASE_SERVICE_KEY")
    base_url = url.rstrip("/").removesuffix("/rest/v1")

    backup_dir = Path(args.backup_dir)
    if not backup_dir.exists():
        print(f"ERROR: backup directory not found: {backup_dir}", file=sys.stderr)
        sys.exit(1)

    manifest_file = backup_dir / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text())
        print(f"Backup created: {manifest.get('created_at', 'unknown')}")
        print(f"Source:         {manifest.get('supabase_url', 'unknown')}")
    else:
        print("WARN: manifest.json not found, proceeding without metadata")

    tables = args.tables.split(",") if args.tables else RESTORE_ORDER
    tables = [t.strip() for t in tables]

    if args.dry_run:
        print("\nDRY RUN — no data will be written\n")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    total_rows = 0
    errors = []

    with httpx.Client(base_url=base_url, headers=headers, timeout=120.0) as client:
        for table in tables:
            try:
                count = restore_table(client, table, backup_dir, args.dry_run)
                total_rows += count
            except httpx.HTTPStatusError as exc:
                errors.append(
                    f"{table}: HTTP {exc.response.status_code} — {exc.response.text[:200]}"
                )
                print(f"  {table}: ERROR — {exc}", file=sys.stderr)

    print(f"\nTotal rows {'to restore' if args.dry_run else 'restored'}: {total_rows}")

    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("Restore completed successfully.")


if __name__ == "__main__":
    main()
