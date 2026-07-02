#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gnss_eq import usgs_triage, usgs_watcher  # noqa: E402

EXPECTED_SOURCE_BY_EVENT = {
    "smoke-mexico": "earthscope",
    "smoke-geonet": "geonet",
    "smoke-chile": "unsupported_south_america",
    "smoke-venezuela": "unsupported_south_america",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic USGS processing-source routing smoke check.")
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Optional directory for the synthetic watcher DB and temporary triage inputs.",
    )
    return parser.parse_args(argv)


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    event_time_utc: str,
    latitude: float,
    longitude: float,
    magnitude: float,
    place: str,
    region: str,
) -> None:
    conn.execute(
        """
        INSERT INTO usgs_watcher_events(
            event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
            latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
            detail_url, scope, region, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_time_utc,
            "2026-07-02T00:00:00Z",
            "2026-07-02T00:00:00Z",
            "2026-07-02T00:00:00Z",
            latitude,
            longitude,
            10.0,
            magnitude,
            "mww",
            place,
            f"M {magnitude:.1f} - {place}",
            f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
            f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={event_id}&format=geojson",
            "americas,nz",
            region,
            "{}",
        ),
    )


def seed_fixture_state_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        usgs_watcher.init_db(conn)
        _insert_event(
            conn,
            event_id="smoke-mexico",
            event_time_utc="2026-07-02T00:00:00Z",
            latitude=24.8239,
            longitude=-108.9285,
            magnitude=6.0,
            place="75 km SSW of El Progreso, Mexico",
            region="americas",
        )
        _insert_event(
            conn,
            event_id="smoke-chile",
            event_time_utc="2026-07-02T00:01:00Z",
            latitude=-30.0,
            longitude=-71.0,
            magnitude=7.0,
            place="near the coast of central Chile",
            region="americas",
        )
        _insert_event(
            conn,
            event_id="smoke-venezuela",
            event_time_utc="2026-07-02T00:02:00Z",
            latitude=10.4351,
            longitude=-68.4716,
            magnitude=7.5,
            place="28 km SE of Yumare, Venezuela",
            region="americas",
        )
        _insert_event(
            conn,
            event_id="smoke-geonet",
            event_time_utc="2026-07-02T00:03:00Z",
            latitude=-27.1921,
            longitude=-177.7691,
            magnitude=6.3,
            place="Kermadec Islands region",
            region="new_zealand",
        )
        conn.commit()
    finally:
        conn.close()


def _triage_report(work_dir: Path, state_db: Path, source: str) -> dict[str, Any]:
    return usgs_triage.build_triage_report(
        state_db=state_db,
        source=source,
        earthscope_db=work_dir / "missing-earthscope.sqlite",
        earthscope_nonconus_db=work_dir / "missing-earthscope-nonconus.sqlite",
        geonet_db=work_dir / "missing-geonet.sqlite",
        runs_root=work_dir / "runs",
        limit=10,
    )


def run_smoke(work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    state_db = work_dir / "usgs-routing-smoke.sqlite"
    seed_fixture_state_db(state_db)

    report_all = _triage_report(work_dir, state_db, "all")
    report_earthscope = _triage_report(work_dir, state_db, "earthscope")
    source_by_event = {
        str(event["event_id"]): str(event["source"])
        for event in report_all["events"]
        if str(event.get("event_id") or "").startswith("smoke-")
    }
    earthscope_event_ids = [
        str(event["event_id"])
        for event in report_earthscope["events"]
        if str(event.get("event_id") or "").startswith("smoke-")
    ]
    counts_by_source: dict[str, int] = {}
    for source in source_by_event.values():
        counts_by_source[source] = counts_by_source.get(source, 0) + 1

    errors = []
    for event_id, expected_source in EXPECTED_SOURCE_BY_EVENT.items():
        actual_source = source_by_event.get(event_id)
        if actual_source != expected_source:
            errors.append(f"{event_id}: expected {expected_source}, got {actual_source}")
    if earthscope_event_ids != ["smoke-mexico"]:
        errors.append(f"earthscope view expected smoke-mexico only, got {','.join(earthscope_event_ids)}")

    return {
        "ok": not errors,
        "errors": errors,
        "source_by_event": source_by_event,
        "earthscope_event_ids": earthscope_event_ids,
        "counts_by_source": counts_by_source,
        "state_db": str(state_db),
    }


def _format_summary(result: dict[str, Any]) -> str:
    counts = result["counts_by_source"]
    status = "OK" if result["ok"] else "FAIL"
    parts = [
        "USGS_ROUTING_SMOKE",
        status,
        f"earthscope={counts.get('earthscope', 0)}",
        f"geonet={counts.get('geonet', 0)}",
        f"unsupported_south_america={counts.get('unsupported_south_america', 0)}",
        f"earthscope_events={','.join(result['earthscope_event_ids'])}",
    ]
    if result["errors"]:
        parts.append(f"errors={';'.join(result['errors'])}")
    return "\t".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.work_dir is not None:
        result = run_smoke(Path(args.work_dir))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_smoke(Path(tmp))
    print(_format_summary(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
