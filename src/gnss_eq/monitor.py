from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EARTHSCOPE_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
DEFAULT_EARTHSCOPE_NONCONUS_DB = ROOT / "data" / "earthscope_availability" / "earthscope_nonconus_1hz.sqlite"
DEFAULT_GEONET_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"
DEFAULT_RUNS_ROOT = ROOT / "runs"

MONITOR_FIELDS = [
    "kind",
    "source",
    "ok",
    "total",
    "missing",
    "high",
    "medium",
    "low",
    "workflow_done",
    "workflow_attempted",
    "workflow_normalized_ok",
    "failed_retryable",
    "collected_normalized",
    "both",
    "priority",
    "coverage_status",
    "event_id",
    "magnitude",
    "event_date",
    "stations_200km",
    "stations_300km",
    "place",
    "detail",
]

STATUS_KEYS = {
    "MISSING": "missing",
    "WORKFLOW_DONE": "workflow_done",
    "WORKFLOW_ATTEMPTED": "workflow_attempted",
    "WORKFLOW_NORMALIZED_OK": "workflow_normalized_ok",
    "FAILED_RETRYABLE": "failed_retryable",
    "COLLECTED_NORMALIZED": "collected_normalized",
    "BOTH": "both",
}
PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "SKIP": 3}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _coerce_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode()
    return value


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _coerce_value(value) for key, value in row.items()}


def _connect_db(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def workflow_event_ids(runs_root: Path) -> set[str]:
    if not runs_root.exists():
        return set()
    return {
        path.name
        for path in runs_root.iterdir()
        if path.is_dir() and any(child.is_dir() and child.name.startswith("workflow-") for child in path.iterdir())
    }


def workflow_status_by_event(runs_root: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    if not runs_root.exists():
        return statuses

    failing_values = {
        "FAIL",
        "BLOCKED_OBS_VALIDATION",
        "SKIPPED_NO_KIN",
        "SKIPPED_WORKFLOW_FAILED",
        "SKIPPED_QUALITY_FAIL",
    }
    for summary in sorted(runs_root.glob("*/workflow-*/reports/workflow-summary.json")):
        event_id = summary.parts[-4]
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            statuses[event_id] = {"state": "WORKFLOW_ATTEMPTED", "summary_json": str(summary)}
            continue
        if not isinstance(payload, dict):
            statuses[event_id] = {"state": "WORKFLOW_ATTEMPTED", "summary_json": str(summary)}
            continue
        status = payload.get("status", {})
        status = status if isinstance(status, dict) else {}
        normalized = str(status.get("normalized") or "")
        if normalized == "OK":
            state = "WORKFLOW_NORMALIZED_OK"
        elif any(str(status.get(key) or "") in failing_values for key in ["download", "obs_validation", "process", "quality", "normalized"]):
            state = "FAILED_RETRYABLE"
        else:
            state = "WORKFLOW_ATTEMPTED"
        statuses[event_id] = {"state": state, "summary_json": str(summary), "status": status}
    return statuses


def coverage_status(event: dict[str, Any], workflow_statuses: dict[str, dict[str, Any]] | set[str]) -> str:
    event_id = str(event.get("event_id", ""))
    if isinstance(workflow_statuses, set):
        workflow_state = "WORKFLOW_DONE" if event_id in workflow_statuses else ""
    else:
        workflow_state = str(workflow_statuses.get(event_id, {}).get("state") or "")
    has_collected = event.get("existing_data_status") == "HAS_NORMALIZED"
    if has_collected and workflow_state in {"WORKFLOW_DONE", "WORKFLOW_NORMALIZED_OK"}:
        return "BOTH"
    if has_collected:
        return "COLLECTED_NORMALIZED"
    if workflow_state:
        return workflow_state
    return "MISSING"


def event_priority(event: dict[str, Any], status: str) -> str:
    if status not in {"MISSING", "FAILED_RETRYABLE"}:
        return "SKIP"
    stations_200km = int(event.get("stations_200km", 0) or 0)
    if stations_200km >= 20:
        return "HIGH"
    if stations_200km >= 5:
        return "MEDIUM"
    return "LOW"


def _database_not_found(source: str, db_path: Path) -> dict[str, Any]:
    return {
        "source": source,
        "ok": False,
        "error_code": "DATABASE_NOT_FOUND",
        "error": f"Database not found: {_display_path(db_path)}",
        "counts": _empty_counts(),
        "candidates": [],
    }


def _empty_counts() -> dict[str, int]:
    return {
        "total": 0,
        "missing": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "workflow_done": 0,
        "workflow_attempted": 0,
        "workflow_normalized_ok": 0,
        "failed_retryable": 0,
        "collected_normalized": 0,
        "both": 0,
    }


def _list_earthscope_events_for_config(db_path: Path, event_table: str, subset: str) -> dict[str, Any]:
    conn = _connect_db(db_path)
    if conn is None:
        return _database_not_found("earthscope", db_path) | {"events": [], "count": 0}
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (event_table,),
        ).fetchone()
        if table_exists is None:
            return {"source": "earthscope", "ok": True, "db": _display_path(db_path), "events": [], "count": 0}
        rows = conn.execute(
            f"""
            SELECT e.event_id,
                   e.magnitude,
                   e.event_date,
                   COALESCE(e.place, '') AS place,
                   COALESCE(SUM(CASE WHEN c.radius_km = 200 THEN 1 ELSE 0 END), 0) AS stations_200km,
                   COALESCE(SUM(CASE WHEN c.radius_km = 300 THEN 1 ELSE 0 END), 0) AS stations_300km,
                   COALESCE(SUM(CASE WHEN c.radius_km = 500 THEN 1 ELSE 0 END), 0) AS stations_500km,
                   COALESCE(SUM(CASE WHEN c.radius_km = 1000 THEN 1 ELSE 0 END), 0) AS stations_1000km,
                   COALESCE(e.existing_data_status, '') AS existing_data_status,
                   COALESCE(e.existing_station_count, 0) AS existing_station_count
            FROM {event_table} e
            LEFT JOIN event_earthscope_station_candidates c
              ON c.event_id = e.event_id
             AND c.radius_km IN (200, 300, 500, 1000)
            GROUP BY e.event_id
            ORDER BY e.magnitude DESC, e.event_date DESC
            """
        ).fetchall()
    finally:
        conn.close()

    events = []
    for row in rows:
        event = _coerce_row(dict(row))
        event["source"] = "earthscope"
        event["earthscope_subset"] = subset
        event["db"] = _display_path(db_path)
        event["event_table"] = event_table
        events.append(event)
    return {"source": "earthscope", "ok": True, "db": _display_path(db_path), "events": events, "count": len(events)}


def list_earthscope_events(earthscope_db: Path, earthscope_nonconus_db: Path) -> dict[str, Any]:
    configs = [
        (earthscope_db, "usgs_m6plus_events_usa", "usa"),
        (earthscope_nonconus_db, "usgs_m6plus_events_earthscope_nonconus", "nonconus"),
    ]
    results = [_list_earthscope_events_for_config(db_path, event_table, subset) for db_path, event_table, subset in configs]
    ok_results = [result for result in results if result["ok"]]
    if not ok_results:
        return {**results[0], "source": "earthscope", "dbs": [_display_path(db_path) for db_path, _, _ in configs]}

    events = [event for result in ok_results for event in result.get("events", [])]
    events.sort(key=lambda event: (float(event.get("magnitude") or 0), str(event.get("event_date") or ""), str(event.get("event_id") or "")), reverse=True)
    errors = [result for result in results if not result["ok"]]
    return {
        "source": "earthscope",
        "ok": True,
        "dbs": [_display_path(db_path) for db_path, _, _ in configs],
        "events": events,
        "count": len(events),
        "errors": errors,
    }


def list_geonet_events(geonet_db: Path) -> dict[str, Any]:
    conn = _connect_db(geonet_db)
    if conn is None:
        return _database_not_found("geonet", geonet_db) | {"events": [], "count": 0}
    try:
        rows = conn.execute(
            """
            SELECT e.event_id,
                   e.magnitude,
                   e.event_date,
                   COALESCE(e.place, '') AS place,
                   COALESCE(a.candidate_200km_station_count, 0) AS stations_200km,
                   COALESCE(a.candidate_300km_station_count, 0) AS stations_300km,
                   COALESCE(e.existing_data_status, '') AS existing_data_status,
                   COALESCE(e.existing_station_count, 0) AS existing_station_count,
                   COALESCE(a.has_1hz, 0) AS has_1hz,
                   COALESCE(a.file_count, 0) AS file_count,
                   COALESCE(a.station_count, 0) AS available_station_count,
                   COALESCE(a.candidate_300km_with_data_count, 0) AS candidate_300km_with_data_count
            FROM geonet_m6plus_events_nz e
            LEFT JOIN event_highrate_day_availability a ON a.event_id = e.event_id
            ORDER BY e.magnitude DESC, e.event_date DESC, e.event_id
            """
        ).fetchall()
    finally:
        conn.close()

    events = [_coerce_row(dict(row)) for row in rows]
    for event in events:
        event["source"] = "geonet"
        event["db"] = _display_path(geonet_db)
    return {"source": "geonet", "ok": True, "db": _display_path(geonet_db), "events": events, "count": len(events)}


def _decorate_events(events: list[dict[str, Any]], workflow_statuses: dict[str, dict[str, Any]] | set[str]) -> list[dict[str, Any]]:
    decorated = []
    for event in events:
        current_status = coverage_status(event, workflow_statuses)
        priority = event_priority(event, current_status)
        decorated.append({**event, "coverage_status": current_status, "priority": priority})
    decorated.sort(key=lambda event: str(event.get("event_id") or ""), reverse=True)
    decorated.sort(key=lambda event: str(event.get("event_date") or ""), reverse=True)
    decorated.sort(key=lambda event: float(event.get("magnitude") or 0), reverse=True)
    decorated.sort(key=lambda event: PRIORITY_RANK.get(str(event.get("priority", "SKIP")), 99))
    return decorated


def _source_report(source_result: dict[str, Any], workflow_statuses: dict[str, dict[str, Any]] | set[str], limit: int) -> dict[str, Any]:
    if not source_result["ok"]:
        return {
            "source": source_result["source"],
            "ok": False,
            "error_code": source_result.get("error_code", "SOURCE_ERROR"),
            "error": source_result.get("error", "source unavailable"),
            "counts": _empty_counts(),
            "candidates": [],
        }

    events = _decorate_events(source_result.get("events", []), workflow_statuses)
    counts = _empty_counts()
    counts["total"] = len(events)
    for event in events:
        status_key = STATUS_KEYS.get(str(event.get("coverage_status")))
        if status_key:
            counts[status_key] += 1
        priority = str(event.get("priority", "")).lower()
        if priority in {"high", "medium", "low"}:
            counts[priority] += 1

    candidates = [event for event in events if event.get("coverage_status") in {"MISSING", "FAILED_RETRYABLE"}][:limit]
    report = {
        "source": source_result["source"],
        "ok": True,
        "counts": counts,
        "candidates": candidates,
    }
    for key in ("db", "dbs", "errors"):
        if key in source_result:
            report[key] = source_result[key]
    return report


def build_monitor_report(
    *,
    source: str = "all",
    limit: int = 20,
    earthscope_db: Path = DEFAULT_EARTHSCOPE_DB,
    earthscope_nonconus_db: Path = DEFAULT_EARTHSCOPE_NONCONUS_DB,
    geonet_db: Path = DEFAULT_GEONET_DB,
    runs_root: Path = DEFAULT_RUNS_ROOT,
) -> dict[str, Any]:
    if source not in {"all", "earthscope", "geonet"}:
        raise ValueError("source must be one of: all, earthscope, geonet")
    if limit < 1:
        raise ValueError("limit must be a positive integer")

    workflow_statuses = workflow_status_by_event(runs_root)
    source_results = []
    if source in {"all", "earthscope"}:
        source_results.append(list_earthscope_events(earthscope_db, earthscope_nonconus_db))
    if source in {"all", "geonet"}:
        source_results.append(list_geonet_events(geonet_db))

    sources = [_source_report(result, workflow_statuses, limit) for result in source_results]
    return {
        "ok": all(result["ok"] for result in sources),
        "read_only": True,
        "source": source,
        "limit": limit,
        "runs_root": _display_path(runs_root),
        "sources": sources,
    }


def _tsv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")


def _write_tsv_row(row: dict[str, Any]) -> None:
    print("\t".join(_tsv_value(row.get(field, "")) for field in MONITOR_FIELDS))


def write_monitor_tsv(report: dict[str, Any]) -> None:
    print("\t".join(MONITOR_FIELDS))
    for source_report in report.get("sources", []):
        counts = source_report.get("counts", {})
        summary = {
            "kind": "SUMMARY",
            "source": source_report.get("source"),
            "ok": source_report.get("ok"),
            "detail": source_report.get("error") or "",
        }
        summary.update(counts)
        _write_tsv_row(summary)
        if not source_report.get("ok", False):
            _write_tsv_row(
                {
                    "kind": "ERROR",
                    "source": source_report.get("source"),
                    "ok": False,
                    "detail": source_report.get("error_code") or source_report.get("error"),
                }
            )
            continue
        for error in source_report.get("errors", []):
            _write_tsv_row(
                {
                    "kind": "ERROR",
                    "source": source_report.get("source"),
                    "ok": False,
                    "detail": error.get("error_code") or error.get("error"),
                }
            )
        for candidate in source_report.get("candidates", []):
            _write_tsv_row(
                {
                    "kind": "CANDIDATE",
                    "source": candidate.get("source") or source_report.get("source"),
                    "ok": True,
                    "priority": candidate.get("priority"),
                    "coverage_status": candidate.get("coverage_status"),
                    "event_id": candidate.get("event_id"),
                    "magnitude": candidate.get("magnitude"),
                    "event_date": candidate.get("event_date"),
                    "stations_200km": candidate.get("stations_200km"),
                    "stations_300km": candidate.get("stations_300km"),
                    "place": candidate.get("place"),
                }
            )


def write_monitor_json(report: dict[str, Any]) -> None:
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
