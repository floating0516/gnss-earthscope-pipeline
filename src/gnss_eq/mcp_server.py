from __future__ import annotations

import csv
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install MCP support with: pip install -e .[mcp]") from exc

ROOT = Path(__file__).resolve().parents[2]
CURRENT_PIPELINE = ROOT / "scripts" / "workflows" / "current_pipeline.sh"
BATCH_ROOT = ROOT / "data" / "batches"
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
GEONET_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"
BATCH_SUMMARY = ROOT / "runs" / "batch-summary.tsv"
RUNS_ROOT = ROOT / "runs"
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ALLOWED_RADII_KM = {200, 300}
MAX_LIMIT = 1000
MAX_RUN_BATCH_TIMEOUT = 14400
TAIL_LINES = 200

mcp = FastMCP("gnss-earthscope")


def _tail(text: str, lines: int = TAIL_LINES) -> tuple[str, bool]:
    parts = text.splitlines()
    if len(parts) <= lines:
        return text, False
    return "\n".join(parts[-lines:]) + ("\n" if text.endswith("\n") else ""), True


def _run_command(command: list[str], timeout: int | None = None) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout_tail, stdout_truncated = _tail(result.stdout)
    stderr_tail, stderr_truncated = _tail(result.stderr)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def _run_current_pipeline(args: list[str], timeout: int | None = None) -> dict[str, Any]:
    return _run_command([str(CURRENT_PIPELINE), *args], timeout=timeout)


def _validate_event_id(event_id: str) -> str:
    event_id = event_id.strip()
    if not event_id:
        raise ValueError("event_id is required")
    if not EVENT_ID_RE.fullmatch(event_id):
        raise ValueError("event_id may only contain letters, numbers, underscore, dot, and dash")
    return event_id


def _validate_radius(radius_km: int) -> int:
    if radius_km not in ALLOWED_RADII_KM:
        allowed = ", ".join(str(radius) for radius in sorted(ALLOWED_RADII_KM))
        raise ValueError(f"radius_km must be one of: {allowed}")
    return radius_km


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit


def _validate_timeout(timeout: int) -> int:
    if not 1 <= timeout <= MAX_RUN_BATCH_TIMEOUT:
        raise ValueError(f"timeout must be between 1 and {MAX_RUN_BATCH_TIMEOUT}")
    return timeout


def _validate_overview_view(view: str) -> str:
    allowed = {"events", "summary", "coverage", "stations"}
    if view not in allowed:
        raise ValueError(f"view must be one of: {', '.join(sorted(allowed))}")
    return view


def _validate_batch_mode(mode: str) -> str:
    allowed = {"preview", "export"}
    if mode not in allowed:
        raise ValueError(f"mode must be one of: {', '.join(sorted(allowed))}")
    return mode


def _validate_source(source: str) -> str:
    allowed = {"earthscope", "geonet"}
    if source not in allowed:
        raise ValueError(f"source must be one of: {', '.join(sorted(allowed))}")
    return source


def _safe_batch_csv(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(BATCH_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Batch CSV must be under {BATCH_ROOT.relative_to(ROOT)}") from exc
    if resolved.suffix.lower() != ".csv":
        raise ValueError("Batch path must end with .csv")
    return resolved


def _parse_tsv(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    return [dict(row) for row in csv.DictReader(lines, delimiter="\t")]


def _coerce_number(value: str) -> str | int | float:
    if value == "":
        return value
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def _coerce_row(row: dict[str, str]) -> dict[str, Any]:
    return {key: _coerce_number(value) for key, value in row.items()}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _workflow_event_ids() -> set[str]:
    if not RUNS_ROOT.exists():
        return set()
    return {
        path.name
        for path in RUNS_ROOT.iterdir()
        if path.is_dir() and any(child.is_dir() and child.name.startswith("workflow-") for child in path.iterdir())
    }


def _coverage_status(event: dict[str, Any], workflow_event_ids: set[str]) -> str:
    has_workflow = str(event.get("event_id", "")) in workflow_event_ids
    has_collected = event.get("existing_data_status") == "HAS_NORMALIZED"
    if has_workflow and has_collected:
        return "BOTH"
    if has_workflow:
        return "WORKFLOW_DONE"
    if has_collected:
        return "COLLECTED_NORMALIZED"
    return "MISSING"


def _event_priority(event: dict[str, Any], coverage_status: str) -> str:
    if coverage_status != "MISSING":
        return "SKIP"
    stations_200km = int(event.get("stations_200km", 0) or 0)
    if stations_200km >= 20:
        return "HIGH"
    if stations_200km >= 5:
        return "MEDIUM"
    return "LOW"


def _check_env() -> dict[str, Any]:
    return _run_command(["gnss-eq", "check-env"])


def _list_events() -> dict[str, Any]:
    result = _run_current_pipeline(["list-events"])
    result["format"] = "tsv"
    result["events"] = [_coerce_row(row) for row in _parse_tsv(result["stdout"])] if result["ok"] else []
    result["count"] = len(result["events"])
    return result


def _connect_db(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _list_geonet_events() -> dict[str, Any]:
    conn = _connect_db(GEONET_DB)
    if conn is None:
        return {"ok": False, "error_code": "DATABASE_NOT_FOUND", "error": f"Database not found: {_display_path(GEONET_DB)}", "events": [], "count": 0}
    try:
        rows = conn.execute(
            """
            SELECT e.event_id,
                   e.magnitude,
                   e.event_date,
                   e.place,
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
    return {"ok": True, "format": "sqlite", "events": events, "count": len(events)}


def check_env() -> dict[str, Any]:
    """Compatibility wrapper for checking local pipeline runtime dependencies."""
    return _check_env()


def list_events() -> dict[str, Any]:
    """Compatibility wrapper for listing current EarthScope event candidates."""
    return _list_events()


def _find_event(event_id: str) -> dict[str, Any] | None:
    result = _list_events()
    if not result["ok"]:
        return None
    return next((event for event in result["events"] if event.get("event_id") == event_id), None)


def _preview_batch(event_id: str, radius_km: int = 200, include_existing: bool = False) -> dict[str, Any]:
    event_id = _validate_event_id(event_id)
    radius_km = _validate_radius(radius_km)
    event = _find_event(event_id)
    if event is None:
        return {
            "ok": False,
            "error_code": "EVENT_NOT_FOUND",
            "message": f"event not found: {event_id}",
            "event_id": event_id,
        }

    stations_field = f"stations_{radius_km}km"
    station_count = int(event.get(stations_field, 0) or 0)
    has_existing = event.get("existing_data_status") == "HAS_NORMALIZED"
    would_fail_without_include_existing = has_existing and not include_existing
    return {
        "ok": True,
        "event_id": event_id,
        "radius_km": radius_km,
        "csv_path": str((BATCH_ROOT / f"{event_id}-{radius_km}km.csv").relative_to(ROOT)),
        "station_count": station_count,
        "stations_field": stations_field,
        "has_existing_normalized": has_existing,
        "existing_station_count": int(event.get("existing_station_count", 0) or 0),
        "would_fail_without_include_existing": would_fail_without_include_existing,
        "would_export": not would_fail_without_include_existing,
        "event": event,
    }


def _export_batch(event_id: str, radius_km: int = 200, include_existing: bool = False) -> dict[str, Any]:
    event_id = _validate_event_id(event_id)
    radius_km = _validate_radius(radius_km)

    args = ["export-batch", "--event-id", event_id, "--radius-km", str(radius_km)]
    if include_existing:
        args.append("--include-existing")
    result = _run_current_pipeline(args)
    result["csv_path"] = str((BATCH_ROOT / f"{event_id}-{radius_km}km.csv").relative_to(ROOT))
    if "event already has normalized data" in result["stderr"]:
        result["error_code"] = "EVENT_ALREADY_HAS_NORMALIZED"
        result["suggested_action"] = "retry_with_include_existing"
    return result


def preview_batch(event_id: str, radius_km: int = 200, include_existing: bool = False) -> dict[str, Any]:
    """Compatibility wrapper for previewing a batch export."""
    return _preview_batch(event_id, radius_km, include_existing)


def export_batch(event_id: str, radius_km: int = 200, include_existing: bool = False) -> dict[str, Any]:
    """Compatibility wrapper for exporting a batch CSV."""
    return _export_batch(event_id, radius_km, include_existing)


def _get_batch_summary(limit: int = 50, event_id: str | None = None) -> dict[str, Any]:
    limit = _validate_limit(limit)
    event_id = _validate_event_id(event_id) if event_id else None
    if not BATCH_SUMMARY.exists():
        return {"ok": True, "path": _display_path(BATCH_SUMMARY), "rows": [], "count": 0}

    rows = [_coerce_row(row) for row in _parse_tsv(BATCH_SUMMARY.read_text(encoding="utf-8"))]
    if event_id:
        rows = [row for row in rows if str(row.get("event_id", "")) == event_id]
    return {"ok": True, "path": _display_path(BATCH_SUMMARY), "rows": rows[:limit], "count": len(rows)}


def _query_station_candidates(event_id: str, limit: int = 100) -> dict[str, Any]:
    event_id = _validate_event_id(event_id)
    limit = _validate_limit(limit)
    conn = _connect_db(DEFAULT_DB)
    if conn is None:
        return {
            "ok": False,
            "error_code": "DATABASE_NOT_FOUND",
            "error": f"Database not found: {_display_path(DEFAULT_DB)}",
            "stations": [],
            "count": 0,
        }
    try:
        rows = conn.execute(
            """
            SELECT station,
                   station_latitude,
                   station_longitude,
                   MIN(distance_km) AS distance_km
            FROM event_earthscope_station_candidates
            WHERE event_id = ?
            GROUP BY station, station_latitude, station_longitude
            ORDER BY distance_km IS NULL, distance_km, station
            LIMIT ?
            """,
            (event_id, limit),
        ).fetchall()
    finally:
        conn.close()
    stations = [dict(row) for row in rows]
    return {"ok": True, "event_id": event_id, "stations": stations, "count": len(stations)}


def _query_geonet_station_candidates(event_id: str, limit: int = 100) -> dict[str, Any]:
    event_id = _validate_event_id(event_id)
    limit = _validate_limit(limit)
    conn = _connect_db(GEONET_DB)
    if conn is None:
        return {
            "ok": False,
            "error_code": "DATABASE_NOT_FOUND",
            "error": f"Database not found: {_display_path(GEONET_DB)}",
            "stations": [],
            "count": 0,
        }
    try:
        rows = conn.execute(
            """
            SELECT station,
                   station_latitude,
                   station_longitude,
                   MIN(distance_km) AS distance_km,
                   station9,
                   network,
                   MAX(station_active_at_event) AS station_active_at_event
            FROM event_geonet_station_candidates
            WHERE event_id = ?
            GROUP BY station, station_latitude, station_longitude, station9, network
            ORDER BY distance_km IS NULL, distance_km, station
            LIMIT ?
            """,
            (event_id, limit),
        ).fetchall()
    finally:
        conn.close()
    stations = [_coerce_row(dict(row)) for row in rows]
    return {"ok": True, "event_id": event_id, "stations": stations, "count": len(stations)}


def get_batch_summary(limit: int = 50, event_id: str | None = None) -> dict[str, Any]:
    """Compatibility wrapper for reading the current batch summary TSV."""
    return _get_batch_summary(limit, event_id)


def query_station_candidates(event_id: str, limit: int = 100) -> dict[str, Any]:
    """Compatibility wrapper for querying EarthScope station candidates."""
    return _query_station_candidates(event_id, limit)


@mcp.tool()
def overview(
    view: str = "coverage",
    event_id: str | None = None,
    limit: int = 50,
    include_env: bool = False,
    source: str = "earthscope",
) -> dict[str, Any]:
    """Unified read-only status, event coverage, summary, and station views."""
    view = _validate_overview_view(view)
    limit = _validate_limit(limit)
    event_id = _validate_event_id(event_id) if event_id else None
    source = _validate_source(source)

    result: dict[str, Any] = {"ok": True, "view": view, "source": source}
    if include_env:
        result["env"] = _check_env()

    if view == "summary":
        result["batch_summary"] = _get_batch_summary(limit=limit, event_id=event_id)
        return result

    if view == "stations":
        if not event_id:
            raise ValueError("event_id is required for stations view")
        if source == "geonet":
            result["stations"] = _query_geonet_station_candidates(event_id=event_id, limit=limit)
        else:
            result["stations"] = _query_station_candidates(event_id=event_id, limit=limit)
        return result

    events_result = _list_geonet_events() if source == "geonet" else _list_events()
    if not events_result["ok"]:
        return {**result, "ok": False, "events": [], "count": 0, "source": events_result}

    events = events_result["events"]
    if event_id:
        events = [event for event in events if str(event.get("event_id", "")) == event_id]

    if view == "coverage":
        workflow_event_ids = _workflow_event_ids()
        events = [
            {
                **event,
                "coverage_status": (status := _coverage_status(event, workflow_event_ids)),
                "priority": _event_priority(event, status),
            }
            for event in events
        ]

    result["events"] = events[:limit]
    result["count"] = len(events)
    result["format"] = events_result["format"]
    return result


@mcp.tool()
def batch(event_id: str, mode: str = "preview", radius_km: int = 200, include_existing: bool = False) -> dict[str, Any]:
    """Preview or export an EarthScope batch CSV for one event."""
    mode = _validate_batch_mode(mode)
    if mode == "preview":
        return _preview_batch(event_id, radius_km, include_existing)
    return _export_batch(event_id, radius_km, include_existing)


@mcp.tool()
def run_batch(
    csv: str,
    timeout: int = 3600,
    cleanup_pride_workdir: bool = False,
    cleanup_obs: bool = False,
    rerun_ok: bool = False,
) -> dict[str, Any]:
    """Run a batch CSV through the current EarthScope workflow."""
    timeout = _validate_timeout(timeout)
    csv_path = _safe_batch_csv(csv)
    args = ["run-batch", "--csv", str(csv_path.relative_to(ROOT)), "--timeout", str(timeout)]
    if cleanup_pride_workdir:
        args.append("--cleanup-pride-workdir")
    if cleanup_obs:
        args.append("--cleanup-obs")
    if rerun_ok:
        args.append("--rerun-ok")

    result = _run_current_pipeline(args, timeout=timeout + 30)
    result["summary_hint"] = "runs/batch-summary.tsv"
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
