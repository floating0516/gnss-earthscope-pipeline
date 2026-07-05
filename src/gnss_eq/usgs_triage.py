from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from gnss_eq import monitor, usgs_watcher

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DB = usgs_watcher.DEFAULT_STATE_DB

TRIAGE_FIELDS = [
    "kind",
    "ok",
    "source",
    "priority",
    "suggested_action",
    "event_id",
    "event_time_utc",
    "first_seen_utc",
    "last_seen_utc",
    "usgs_updated_utc",
    "magnitude",
    "mag_type",
    "latitude",
    "longitude",
    "depth_km",
    "region",
    "scope",
    "stations_200km",
    "stations_300km",
    "availability_status",
    "workflow_status",
    "place",
    "title",
    "usgs_url",
    "detail",
    "suggested_command",
    "reason",
    "recommended_source",
    "routing_reason",
    "processable_by_earthscope",
    "processable_by_geonet",
    "research_candidate_cddis",
    "parked_source_candidate",
]

PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "SKIP": 3, "UNKNOWN": 4}
SOUTH_AMERICA_PLACE_TERMS = (
    "argentina",
    "bolivia",
    "brazil",
    "chile",
    "colombia",
    "ecuador",
    "falkland",
    "french guiana",
    "guyana",
    "paraguay",
    "peru",
    "suriname",
    "uruguay",
    "venezuela",
)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _connect_readonly(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    uri = f"file:{path.resolve(strict=False)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def _coerce_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode()
    return value


def _coerce_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: _coerce_value(row[key]) for key in row.keys()}


def _empty_counts() -> dict[str, int]:
    return {
        "total": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "skip": 0,
        "needs_availability": 0,
        "workflow_exists": 0,
        "check_local_db": 0,
    }


def _event_text(event: dict[str, Any]) -> str:
    return " ".join(str(event.get(key) or "") for key in ("place", "title")).lower()


def _event_float(event: dict[str, Any], key: str) -> float | None:
    try:
        return float(event.get(key))
    except (TypeError, ValueError):
        return None


def _is_south_america_event(event: dict[str, Any]) -> bool:
    text = _event_text(event)
    if any(term in text for term in SOUTH_AMERICA_PLACE_TERMS):
        return True
    latitude = _event_float(event, "latitude")
    longitude = _event_float(event, "longitude")
    if latitude is None or longitude is None:
        return False
    return -60.0 <= latitude <= 5.0 and -82.0 <= longitude <= -34.0


def processing_source_for_event(event: dict[str, Any]) -> str:
    region = str(event.get("region") or "")
    if region == "new_zealand":
        return "geonet"
    if region == "americas":
        if _is_south_america_event(event):
            return "unsupported_south_america"
        return "earthscope"
    return "unknown"


def source_routing_for_event(event: dict[str, Any], source: str | None = None) -> dict[str, Any]:
    source = source or processing_source_for_event(event)
    if source == "earthscope":
        return {
            "recommended_source": "earthscope",
            "routing_reason": "americas_supported_by_earthscope",
            "processable_by_earthscope": True,
            "processable_by_geonet": False,
            "research_candidate_cddis": False,
            "parked_source_candidate": False,
        }
    if source == "geonet":
        return {
            "recommended_source": "geonet",
            "routing_reason": "new_zealand_supported_by_geonet",
            "processable_by_earthscope": False,
            "processable_by_geonet": True,
            "research_candidate_cddis": False,
            "parked_source_candidate": False,
        }
    if source == "unsupported_south_america":
        return {
            "recommended_source": "cddis_research",
            "routing_reason": "south_america_outside_earthscope_production",
            "processable_by_earthscope": False,
            "processable_by_geonet": False,
            "research_candidate_cddis": True,
            "parked_source_candidate": False,
        }
    return {
        "recommended_source": "manual_review",
        "routing_reason": "region_not_mapped_to_production_source",
        "processable_by_earthscope": False,
        "processable_by_geonet": False,
        "research_candidate_cddis": False,
        "parked_source_candidate": True,
    }


def _source_region_filter(source: str) -> tuple[str, ...]:
    if source == "earthscope":
        return ("americas",)
    if source == "geonet":
        return ("new_zealand",)
    return ("americas", "new_zealand")


def _list_watched_events(conn: sqlite3.Connection, *, source: str, min_magnitude: float, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(conn, "usgs_watcher_events"):
        return []
    regions = _source_region_filter(source)
    placeholders = ",".join("?" for _ in regions)
    rows = conn.execute(
        f"""
        SELECT event_id,
               event_time_utc,
               first_seen_utc,
               last_seen_utc,
               usgs_updated_utc,
               latitude,
               longitude,
               depth_km,
               magnitude,
               mag_type,
               place,
               title,
               usgs_url,
               detail_url,
               scope,
               region
          FROM usgs_watcher_events
         WHERE region IN ({placeholders})
           AND COALESCE(magnitude, 0) >= ?
         ORDER BY first_seen_utc DESC, event_time_utc DESC, event_id DESC
         LIMIT ?
        """,
        (*regions, min_magnitude, limit),
    ).fetchall()
    return [_coerce_row(row) for row in rows]


def _database_error(source: str, path: Path, code: str = "DATABASE_NOT_FOUND") -> dict[str, Any]:
    return {
        "source": source,
        "ok": False,
        "error_code": code,
        "error": f"Database not found: {_display_path(path)}" if code == "DATABASE_NOT_FOUND" else f"Database unavailable: {_display_path(path)}",
        "db": _display_path(path),
    }


def _earthscope_index_for_db(path: Path, event_table: str, subset: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    conn = _connect_readonly(path)
    if conn is None:
        return {}, [_database_error("earthscope", path)]
    try:
        if not _table_exists(conn, event_table) or not _table_exists(conn, "event_earthscope_station_candidates"):
            return {}, []
        rows = conn.execute(
            f"""
            SELECT e.event_id,
                   COALESCE(e.existing_data_status, '') AS existing_data_status,
                   COALESCE(e.existing_station_count, 0) AS existing_station_count,
                   COALESCE(SUM(CASE WHEN c.radius_km = 200 THEN 1 ELSE 0 END), 0) AS stations_200km,
                   COALESCE(SUM(CASE WHEN c.radius_km = 300 THEN 1 ELSE 0 END), 0) AS stations_300km
              FROM {event_table} e
              LEFT JOIN event_earthscope_station_candidates c
                ON c.event_id = e.event_id
               AND c.radius_km IN (200, 300)
             GROUP BY e.event_id
            """
        ).fetchall()
    finally:
        conn.close()

    index = {}
    for row in rows:
        event = _coerce_row(row)
        event["source"] = "earthscope"
        event["earthscope_subset"] = subset
        event["db"] = _display_path(path)
        event["availability_status"] = "AVAILABLE"
        index[str(event["event_id"])] = event
    return index, []


def _earthscope_availability_index(earthscope_db: Path, earthscope_nonconus_db: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    configs = [
        (earthscope_db, "usgs_m6plus_events_usa", "usa"),
        (earthscope_nonconus_db, "usgs_m6plus_events_earthscope_nonconus", "nonconus"),
    ]
    index: dict[str, dict[str, Any]] = {}
    errors = []
    for path, table, subset in configs:
        current, current_errors = _earthscope_index_for_db(path, table, subset)
        index.update(current)
        errors.extend(current_errors)
    return index, errors


def _geonet_availability_index(geonet_db: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    conn = _connect_readonly(geonet_db)
    if conn is None:
        return {}, [_database_error("geonet", geonet_db)]
    try:
        if not _table_exists(conn, "geonet_m6plus_events_nz"):
            return {}, []
        if _table_exists(conn, "event_highrate_day_availability"):
            rows = conn.execute(
                """
                SELECT e.event_id,
                       COALESCE(e.existing_data_status, '') AS existing_data_status,
                       COALESCE(e.existing_station_count, 0) AS existing_station_count,
                       COALESCE(a.candidate_200km_station_count, 0) AS stations_200km,
                       COALESCE(a.candidate_300km_station_count, 0) AS stations_300km,
                       COALESCE(a.has_1hz, 0) AS has_1hz,
                       COALESCE(a.file_count, 0) AS file_count,
                       COALESCE(a.station_count, 0) AS available_station_count,
                       COALESCE(a.candidate_300km_with_data_count, 0) AS candidate_300km_with_data_count
                  FROM geonet_m6plus_events_nz e
                  LEFT JOIN event_highrate_day_availability a ON a.event_id = e.event_id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT event_id,
                       COALESCE(existing_data_status, '') AS existing_data_status,
                       COALESCE(existing_station_count, 0) AS existing_station_count,
                       0 AS stations_200km,
                       0 AS stations_300km,
                       0 AS has_1hz,
                       0 AS file_count,
                       0 AS available_station_count,
                       0 AS candidate_300km_with_data_count
                  FROM geonet_m6plus_events_nz
                """
            ).fetchall()
    finally:
        conn.close()

    index = {}
    for row in rows:
        event = _coerce_row(row)
        available = int(event.get("candidate_300km_with_data_count") or 0)
        if available:
            event["stations_200km"] = available
        event["source"] = "geonet"
        event["db"] = _display_path(geonet_db)
        event["availability_status"] = "AVAILABLE"
        index[str(event["event_id"])] = event
    return index, []


def _priority(source: str, stations_200km: int, workflow_status: str, existing_data_status: str) -> str:
    if source == "unsupported_south_america":
        return "SKIP"
    if workflow_status == "WORKFLOW_EXISTS" or existing_data_status == "HAS_NORMALIZED":
        return "SKIP"
    if stations_200km >= 20:
        return "HIGH"
    if stations_200km >= 5:
        return "MEDIUM"
    return "LOW"


def _suggested_action(priority: str, workflow_status: str, availability: dict[str, Any] | None, db_available: bool, source: str) -> str:
    if source == "unsupported_south_america":
        return "CHECK_CDDIS_OR_OTHER_SOURCE"
    if workflow_status == "WORKFLOW_EXISTS":
        return "SKIP_WORKFLOW_EXISTS"
    if not db_available:
        return "CHECK_LOCAL_DB"
    if availability is None:
        return "UPDATE_AVAILABILITY_THEN_REVIEW"
    if priority in {"HIGH", "MEDIUM"}:
        return "REVIEW_PREPARE_BATCH"
    return "LOW_PRIORITY_REVIEW"


def _workflow_status(event_id: str, workflow_ids: set[str]) -> str:
    return "WORKFLOW_EXISTS" if event_id in workflow_ids else "MISSING"


def _reason(event: dict[str, Any]) -> str:
    action = event.get("suggested_action")
    if action == "CHECK_CDDIS_OR_OTHER_SOURCE":
        return "South America is outside the current EarthScope processing coverage; review CDDIS or another global source"
    if action == "SKIP_WORKFLOW_EXISTS":
        return "workflow output already exists"
    if action == "CHECK_LOCAL_DB":
        return "local availability database is unavailable"
    if action == "UPDATE_AVAILABILITY_THEN_REVIEW":
        return "event is not present in the local availability database yet"
    if action == "REVIEW_PREPARE_BATCH":
        return f"candidate stations at 200km: {event.get('stations_200km', 0)}"
    return f"low station count at 200km: {event.get('stations_200km', 0)}"


def _suggested_commands(event: dict[str, Any]) -> list[str]:
    event_id = str(event.get("event_id") or "")
    source = str(event.get("source") or "")
    action = str(event.get("suggested_action") or "")
    if action == "SKIP_WORKFLOW_EXISTS":
        return [f"ls runs/{event_id}"]
    if source == "earthscope":
        commands = ["gnss-eq monitor --source earthscope --format tsv", "scripts/workflows/current_pipeline.sh list-events"]
        if action == "REVIEW_PREPARE_BATCH":
            commands.extend(
                [
                    f"scripts/workflows/current_pipeline.sh export-batch --event-id {event_id} --radius-km 200",
                    f"scripts/workflows/current_pipeline.sh run-batch --csv data/batches/{event_id}-200km.csv --timeout 3600",
                ]
            )
        return commands
    if source == "geonet":
        return [
            "gnss-eq monitor --source geonet --format tsv",
            "scripts/workflows/run_geonet_event_1hz_pride_workflow.sh --help",
            "scripts/workflows/run_geonet_batch_workflow.sh --help",
        ]
    if source == "unsupported_south_america":
        return [
            "python3 scripts/database/import_usgs_events_to_cddis.py --min-magnitude 6.0",
            f"python3 scripts/availability/rebuild_cddis_event_station_candidates.py --event-id {event_id} --clear-event",
            "scripts/workflows/run_cddis_event_batch_workflow.sh --help",
        ]
    return ["gnss-eq monitor --source all --format tsv"]


def _triage_event(
    event: dict[str, Any],
    *,
    earthscope_index: dict[str, dict[str, Any]],
    geonet_index: dict[str, dict[str, Any]],
    db_available: dict[str, bool],
    workflow_ids: set[str],
) -> dict[str, Any]:
    source = processing_source_for_event(event)
    routing = source_routing_for_event(event, source)
    availability = None
    if source == "earthscope":
        availability = earthscope_index.get(str(event["event_id"]))
    elif source == "geonet":
        availability = geonet_index.get(str(event["event_id"]))

    workflow_status = _workflow_status(str(event["event_id"]), workflow_ids)
    stations_200km = int((availability or {}).get("stations_200km") or 0)
    stations_300km = int((availability or {}).get("stations_300km") or 0)
    existing_data_status = str((availability or {}).get("existing_data_status") or "")
    priority = _priority(source, stations_200km, workflow_status, existing_data_status)
    action = _suggested_action(priority, workflow_status, availability, db_available.get(source, False), source)
    triaged = {
        **event,
        **routing,
        "source": source,
        "priority": priority,
        "suggested_action": action,
        "stations_200km": stations_200km,
        "stations_300km": stations_300km,
        "availability_status": "FOUND" if availability else "MISSING",
        "workflow_status": workflow_status,
        "detail": event.get("detail_url", ""),
    }
    triaged["reason"] = _reason(triaged)
    triaged["suggested_commands"] = _suggested_commands(triaged)
    triaged["suggested_command"] = triaged["suggested_commands"][0] if triaged["suggested_commands"] else ""
    return triaged


def _filter_source(events: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    if source == "all":
        return events
    return [event for event in events if event.get("source") == source]


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda event: (
            PRIORITY_RANK.get(str(event.get("priority", "UNKNOWN")), 99),
            str(event.get("first_seen_utc") or ""),
            str(event.get("event_time_utc") or ""),
        ),
        reverse=False,
    )


def _build_summary_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = _empty_counts()
    counts["total"] = len(events)
    for event in events:
        priority = str(event.get("priority") or "").lower()
        if priority in {"high", "medium", "low", "skip"}:
            counts[priority] += 1
        action = str(event.get("suggested_action") or "")
        if action == "UPDATE_AVAILABILITY_THEN_REVIEW":
            counts["needs_availability"] += 1
        if action == "SKIP_WORKFLOW_EXISTS":
            counts["workflow_exists"] += 1
        if action == "CHECK_LOCAL_DB":
            counts["check_local_db"] += 1
    return counts


def build_triage_report(
    *,
    state_db: Path = DEFAULT_STATE_DB,
    source: str = "all",
    limit: int = 20,
    min_magnitude: float = 6.0,
    earthscope_db: Path = monitor.DEFAULT_EARTHSCOPE_DB,
    earthscope_nonconus_db: Path = monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB,
    geonet_db: Path = monitor.DEFAULT_GEONET_DB,
    runs_root: Path = monitor.DEFAULT_RUNS_ROOT,
) -> dict[str, Any]:
    if source not in {"all", "earthscope", "geonet"}:
        raise ValueError("source must be one of: all, earthscope, geonet")
    if limit < 1:
        raise ValueError("limit must be a positive integer")

    state_db = Path(state_db)
    conn = _connect_readonly(state_db)
    if conn is None:
        error = _database_error("watcher", state_db)
        return {
            "ok": False,
            "read_only": True,
            "source": source,
            "limit": limit,
            "state_db": _display_path(state_db),
            "counts": _empty_counts(),
            "events": [],
            "errors": [error],
        }

    try:
        watched_events = _list_watched_events(conn, source=source, min_magnitude=min_magnitude, limit=limit * 3)
    finally:
        conn.close()

    earthscope_index, earthscope_errors = _earthscope_availability_index(Path(earthscope_db), Path(earthscope_nonconus_db))
    geonet_index, geonet_errors = _geonet_availability_index(Path(geonet_db))
    errors = earthscope_errors + geonet_errors
    db_available = {
        "earthscope": bool(earthscope_index) or not all(error.get("source") == "earthscope" for error in earthscope_errors),
        "geonet": bool(geonet_index) or not any(error.get("source") == "geonet" for error in geonet_errors),
        "unknown": False,
    }
    workflow_ids = monitor.workflow_event_ids(Path(runs_root))
    triaged_events = [
        _triage_event(
            event,
            earthscope_index=earthscope_index,
            geonet_index=geonet_index,
            db_available=db_available,
            workflow_ids=workflow_ids,
        )
        for event in watched_events
    ]
    triaged_events = _sort_events(_filter_source(triaged_events, source))[:limit]
    counts = _build_summary_counts(triaged_events)
    return {
        "ok": True,
        "read_only": True,
        "source": source,
        "limit": limit,
        "min_magnitude": min_magnitude,
        "state_db": _display_path(state_db),
        "availability_dbs": {
            "earthscope": [_display_path(Path(earthscope_db)), _display_path(Path(earthscope_nonconus_db))],
            "geonet": _display_path(Path(geonet_db)),
        },
        "runs_root": _display_path(Path(runs_root)),
        "counts": counts,
        "events": triaged_events,
        "errors": errors,
    }


def _tsv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")


def _write_tsv_row(row: dict[str, Any]) -> None:
    print("\t".join(_tsv_value(row.get(field, "")) for field in TRIAGE_FIELDS))


def write_triage_tsv(report: dict[str, Any]) -> None:
    print("\t".join(TRIAGE_FIELDS))
    counts = report.get("counts", {})
    _write_tsv_row(
        {
            "kind": "SUMMARY",
            "ok": report.get("ok"),
            "source": report.get("source"),
            "reason": (
                f"total={counts.get('total', 0)} high={counts.get('high', 0)} medium={counts.get('medium', 0)} "
                f"low={counts.get('low', 0)} needs_availability={counts.get('needs_availability', 0)}"
            ),
        }
    )
    for error in report.get("errors", []):
        _write_tsv_row(
            {
                "kind": "ERROR",
                "ok": False,
                "source": error.get("source"),
                "reason": error.get("error_code") or error.get("error"),
            }
        )
    for event in report.get("events", []):
        _write_tsv_row(
            {
                "kind": "EVENT",
                "ok": True,
                "source": event.get("source"),
                "priority": event.get("priority"),
                "suggested_action": event.get("suggested_action"),
                "event_id": event.get("event_id"),
                "event_time_utc": event.get("event_time_utc"),
                "first_seen_utc": event.get("first_seen_utc"),
                "last_seen_utc": event.get("last_seen_utc"),
                "usgs_updated_utc": event.get("usgs_updated_utc"),
                "magnitude": event.get("magnitude"),
                "mag_type": event.get("mag_type"),
                "latitude": event.get("latitude"),
                "longitude": event.get("longitude"),
                "depth_km": event.get("depth_km"),
                "region": event.get("region"),
                "scope": event.get("scope"),
                "stations_200km": event.get("stations_200km"),
                "stations_300km": event.get("stations_300km"),
                "availability_status": event.get("availability_status"),
                "workflow_status": event.get("workflow_status"),
                "place": event.get("place"),
                "title": event.get("title"),
                "usgs_url": event.get("usgs_url"),
                "detail": event.get("detail"),
                "suggested_command": event.get("suggested_command"),
                "reason": event.get("reason"),
                "recommended_source": event.get("recommended_source"),
                "routing_reason": event.get("routing_reason"),
                "processable_by_earthscope": event.get("processable_by_earthscope"),
                "processable_by_geonet": event.get("processable_by_geonet"),
                "research_candidate_cddis": event.get("research_candidate_cddis"),
                "parked_source_candidate": event.get("parked_source_candidate"),
            }
        )


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key not in {"raw_json"}}


def write_triage_json(report: dict[str, Any]) -> None:
    payload = {**report, "events": [_public_event(event) for event in report.get("events", [])]}
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
