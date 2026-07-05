#!/usr/bin/env python3
"""Export the USGS watcher sqlite state to JSONL for review handoff."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class ExportError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise ExportError(f"watcher database not found: {path}")
    uri = f"file:{path.resolve(strict=False)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def require_tables(conn: sqlite3.Connection, tables: Iterable[str]) -> None:
    missing = [table for table in tables if not table_exists(conn, table)]
    if missing:
        raise ExportError(f"watcher database is missing required tables: {', '.join(missing)}")


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def fetch_event_rows(conn: sqlite3.Connection, *, include_raw_json: bool) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
          FROM usgs_watcher_events
         ORDER BY event_time_utc, event_id
        """
    ).fetchall()
    events = []
    for row in rows:
        payload = row_dict(row)
        if not include_raw_json:
            payload.pop("raw_json", None)
        events.append({"kind": "event", **payload})
    return events


def fetch_poll_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
          FROM usgs_watcher_polls
         ORDER BY poll_id
        """
    ).fetchall()
    return [{"kind": "poll", **row_dict(row)} for row in rows]


def fetch_state_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
          FROM usgs_watcher_state
         ORDER BY key
        """
    ).fetchall()
    return [{"kind": "state", **row_dict(row)} for row in rows]


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        tmp_path = Path(handle.name)
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    tmp_path.replace(path)


def export_watcher_state(db: Path, out: Path, *, include_raw_json: bool = False) -> dict[str, Any]:
    db = Path(db)
    out = Path(out)
    try:
        conn = connect_readonly(db)
        try:
            require_tables(conn, ("usgs_watcher_events", "usgs_watcher_polls", "usgs_watcher_state"))
            event_rows = fetch_event_rows(conn, include_raw_json=include_raw_json)
            poll_rows = fetch_poll_rows(conn)
            state_rows = fetch_state_rows(conn)
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ExportError(f"failed to read watcher database {db}: {exc}") from exc

    summary = {
        "source_db": str(db),
        "exported_at": utc_now(),
        "include_raw_json": include_raw_json,
        "counts": {
            "events": len(event_rows),
            "polls": len(poll_rows),
            "state": len(state_rows),
        },
    }
    rows = [*event_rows, *poll_rows, *state_rows, {"kind": "summary", **summary}]
    write_jsonl_atomic(out, rows)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="USGS watcher sqlite database")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL path")
    parser.add_argument("--include-raw-json", action="store_true", help="Include raw USGS JSON payloads in event rows")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = export_watcher_state(args.db, args.out, include_raw_json=args.include_raw_json)
    except ExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    counts = summary["counts"]
    print(
        "exported watcher state: "
        f"events={counts['events']} polls={counts['polls']} state={counts['state']} out={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
