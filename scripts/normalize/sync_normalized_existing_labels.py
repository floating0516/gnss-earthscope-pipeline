#!/usr/bin/env python3
"""Label USGS events that already exist in the normalized GNSS dataset."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
DEFAULT_NORMALIZED_ROOT = ROOT.parent / "openclaw-gnss-collector-agent" / "data" / "gnss_data" / "normalized"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--normalized-root", default=str(DEFAULT_NORMALIZED_ROOT))
    parser.add_argument("--reset", action="store_true", help="Clear existing normalized labels before applying labels.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(usgs_m6plus_events_usa)")}
    columns = {
        "existing_data_status": "TEXT NOT NULL DEFAULT ''",
        "existing_data_source": "TEXT",
        "existing_dataset_dir": "TEXT",
        "existing_station_count": "INTEGER NOT NULL DEFAULT 0",
        "existing_waveform_file": "TEXT",
        "existing_event_file": "TEXT",
        "existing_updated_at": "TEXT",
    }
    for name, declaration in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE usgs_m6plus_events_usa ADD COLUMN {name} {declaration}")


def reset_labels(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE usgs_m6plus_events_usa
        SET existing_data_status = '',
            existing_data_source = NULL,
            existing_dataset_dir = NULL,
            existing_station_count = 0,
            existing_waveform_file = NULL,
            existing_event_file = NULL,
            existing_updated_at = NULL
        """
    )


def count_station_rows(stations_csv: Path) -> int:
    if not stations_csv.exists():
        return 0
    with stations_csv.open(newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def count_waveform_rows(waveform_file: Path) -> int:
    if not waveform_file.exists():
        return 0
    opener = gzip.open if waveform_file.suffix == ".gz" else open
    with opener(waveform_file, "rt", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def discover(normalized_root: Path) -> list[dict[str, object]]:
    labels: list[dict[str, object]] = []
    for event_file in sorted(normalized_root.glob("*/event.json")):
        dataset_dir = event_file.parent
        try:
            event = json.loads(event_file.read_text())
        except json.JSONDecodeError:
            continue
        event_id = str(event.get("usgs_event_id") or "").strip()
        if not event_id:
            continue
        stations_csv = dataset_dir / "stations.csv"
        waveform_file = dataset_dir / "waveforms.csv.gz"
        station_count = int(event.get("stations") or 0) or count_station_rows(stations_csv)
        labels.append(
            {
                "event_id": event_id,
                "existing_data_status": "HAS_NORMALIZED",
                "existing_data_source": "normalized_gnss_data",
                "existing_dataset_dir": str(dataset_dir),
                "existing_station_count": station_count,
                "existing_waveform_file": str(waveform_file) if waveform_file.exists() else "",
                "existing_event_file": str(event_file),
                "waveform_rows": count_waveform_rows(waveform_file),
            }
        )
    return labels


def apply_labels(conn: sqlite3.Connection, labels: list[dict[str, object]], dry_run: bool) -> tuple[int, int]:
    current_ids = {row[0] for row in conn.execute("SELECT event_id FROM usgs_m6plus_events_usa")}
    matched = [label for label in labels if label["event_id"] in current_ids]
    unmatched = len(labels) - len(matched)
    if dry_run:
        return len(matched), unmatched

    updated_at = utc_now()
    with conn:
        for label in matched:
            conn.execute(
                """
                UPDATE usgs_m6plus_events_usa
                SET existing_data_status = ?,
                    existing_data_source = ?,
                    existing_dataset_dir = ?,
                    existing_station_count = ?,
                    existing_waveform_file = ?,
                    existing_event_file = ?,
                    existing_updated_at = ?
                WHERE event_id = ?
                """,
                (
                    label["existing_data_status"],
                    label["existing_data_source"],
                    label["existing_dataset_dir"],
                    label["existing_station_count"],
                    label["existing_waveform_file"],
                    label["existing_event_file"],
                    updated_at,
                    label["event_id"],
                ),
            )
    return len(matched), unmatched


def main() -> int:
    args = parse_args()
    normalized_root = Path(args.normalized_root).expanduser()
    if not normalized_root.exists():
        raise SystemExit(f"normalized root not found: {normalized_root}")

    conn = sqlite3.connect(args.db)
    try:
        ensure_columns(conn)
        if args.reset and not args.dry_run:
            with conn:
                reset_labels(conn)
        labels = discover(normalized_root)
        matched, unmatched = apply_labels(conn, labels, args.dry_run)
        current_ids = {row[0] for row in conn.execute("SELECT event_id FROM usgs_m6plus_events_usa")}
        for label in labels:
            match_status = "MATCHED" if label["event_id"] in current_ids else "UNMATCHED"
            print(
                f"{match_status}\t{label['event_id']}\t{label['existing_data_status']}\t"
                f"stations={label['existing_station_count']}\twaveform_rows={label['waveform_rows']}\t"
                f"{label['existing_dataset_dir']}"
            )
        print(
            f"SUMMARY\tdiscovered={len(labels)}\tmatched={matched}\tunmatched={unmatched}\tdry_run={int(args.dry_run)}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
