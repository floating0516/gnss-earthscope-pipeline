from __future__ import annotations

import csv
import os
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "static"


class DashboardConfig:
    def __init__(self) -> None:
        self.db_path = Path(os.environ.get("GNSS_EQ_WEB_DB", ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite")).resolve(strict=False)
        self.run_root = Path(os.environ.get("GNSS_EQ_WEB_RUN_ROOT", ROOT / "runs")).resolve(strict=False)
        self.obs_root = Path(os.environ.get("GNSS_EQ_WEB_OBS_ROOT", ROOT / "data" / "obs")).resolve(strict=False)
        self.batch_root = Path(os.environ.get("GNSS_EQ_WEB_BATCH_ROOT", ROOT / "data" / "batches")).resolve(strict=False)
        self.summary_path = Path(os.environ.get("GNSS_EQ_WEB_SUMMARY", ROOT / "batch-summary.tsv")).resolve(strict=False)
        self.allow_workflow_run = os.environ.get("GNSS_EQ_WEB_ALLOW_WORKFLOW_RUN") == "1"
        self.default_base_url = os.environ.get("GNSS_EQ_WEB_BASE_URL", "https://web-services.unavco.org")


CONFIG = DashboardConfig()
app = FastAPI(title="GNSS EQ Workflow Dashboard")
if STATIC_ROOT.exists():
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


class WorkflowPreviewRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=120)
    radius_km: float = Field(default=200, ge=1, le=1000)
    max_stations: int = Field(default=20, ge=1, le=200)
    include_existing: bool = False


class WorkflowRunRequest(WorkflowPreviewRequest):
    timeout: int = Field(default=3600, ge=60, le=86400)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)


class JobRecord(BaseModel):
    job_id: str
    event_id: str
    status: str
    started_at: str
    ended_at: str | None = None
    returncode: int | None = None
    summary_path: str
    log_path: str
    batch_path: str


jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def connect_db() -> sqlite3.Connection:
    if not CONFIG.db_path.exists():
        raise HTTPException(status_code=503, detail=f"Database not found: {CONFIG.db_path}")
    conn = sqlite3.connect(CONFIG.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def read_summary(path: Path | None = None) -> list[dict[str, str]]:
    source = path or CONFIG.summary_path
    if not source.exists():
        return []
    with source.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def ensure_under(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise HTTPException(status_code=400, detail=f"Path escapes configured root: {path}")
    return resolved


def get_event_or_404(event_id: str) -> dict[str, Any]:
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM usgs_m6plus_events_usa WHERE event_id = ?", (event_id,)).fetchone()
    event = row_dict(row)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found in local database")
    return event


def event_time(event: dict[str, Any]) -> str:
    value = event.get("time_utc") or event.get("event_time")
    if not value:
        raise HTTPException(status_code=409, detail="Event is missing time_utc")
    return str(value)


def existing_data_status(event: dict[str, Any]) -> str:
    return str(event.get("existing_data_status") or "").strip().upper()


def query_selected_stations(event_id: str, radius_km: float, max_stations: int, verified_only: bool = False) -> list[dict[str, Any]]:
    sql = [
        "SELECT c.station, c.station_latitude AS latitude, c.station_longitude AS longitude,",
        "c.distance_km, c.radius_km, v.verified_status, v.file_count, v.obs_file_count, v.first_obs_url",
        "FROM event_earthscope_station_candidates c",
        "LEFT JOIN event_earthscope_station_verified_files v ON v.event_id = c.event_id AND v.station = c.station",
        "WHERE c.event_id = ? AND c.radius_km <= ?",
    ]
    params: list[Any] = [event_id, radius_km]
    if verified_only:
        sql.append("AND COALESCE(v.obs_file_count, 0) > 0")
    sql.append("ORDER BY c.distance_km ASC, c.station ASC LIMIT ?")
    params.append(max_stations)
    with connect_db() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params)]


def preview_workflow(request: WorkflowPreviewRequest) -> dict[str, Any]:
    event = get_event_or_404(request.event_id)
    already_existing = existing_data_status(event) not in {"", "NONE", "NO", "MISSING", "NULL"}
    if already_existing and not request.include_existing:
        stations: list[dict[str, Any]] = []
    else:
        stations = query_selected_stations(request.event_id, request.radius_km, request.max_stations)
    station_codes = [str(station["station"]) for station in stations]
    return {
        "event_id": request.event_id,
        "event_time": event_time(event),
        "already_has_existing_data": already_existing,
        "existing_data_status": event.get("existing_data_status"),
        "existing_station_count": event.get("existing_station_count"),
        "radius_km": request.radius_km,
        "max_stations": request.max_stations,
        "station_count": len(station_codes),
        "stations": station_codes,
        "command_preview": " ".join(
            [
                sys.executable,
                "-m",
                "gnss_eq",
                "run-batch",
                "--csv",
                "<generated-web-batch.csv>",
                "--timeout",
                "<timeout>",
                "--summary",
                str(CONFIG.summary_path),
            ]
        ),
    }


def validate_base_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="base_url must be an http(s) URL")
    return value.strip()


def safe_job_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"process", "log_handle"}}


def create_batch_csv(job_id: str, event: dict[str, Any], stations: list[str]) -> Path:
    if not stations:
        raise HTTPException(status_code=409, detail="No stations selected for this workflow")
    CONFIG.batch_root.mkdir(parents=True, exist_ok=True)
    batch_path = ensure_under(CONFIG.batch_root / f"web-{job_id}.csv", CONFIG.batch_root)
    with batch_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "event_time", "stations", "status"], lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "event_id": event["event_id"],
                "event_time": event_time(event),
                "stations": " ".join(stations),
                "status": "",
            }
        )
    return batch_path


def monitor_job(job_id: str) -> None:
    with jobs_lock:
        record = jobs[job_id]
        process: subprocess.Popen[str] = record["process"]
        log_handle = record.get("log_handle")
    returncode = process.wait()
    if log_handle is not None:
        log_handle.close()
    with jobs_lock:
        record = jobs[job_id]
        record["returncode"] = returncode
        record["ended_at"] = utc_now()
        record["status"] = "completed" if returncode == 0 else "failed"


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_ROOT / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=503, detail="Static frontend is not installed")
    return FileResponse(index_path)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": CONFIG.db_path.exists(),
        "db_exists": CONFIG.db_path.exists(),
        "db_path": str(CONFIG.db_path),
        "summary_exists": CONFIG.summary_path.exists(),
        "summary_path": str(CONFIG.summary_path),
        "workflow_enabled": CONFIG.allow_workflow_run,
        "run_root": str(CONFIG.run_root),
        "batch_root": str(CONFIG.batch_root),
    }


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "default_base_url": CONFIG.default_base_url,
        "workflow_enabled": CONFIG.allow_workflow_run,
        "map_tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "map_tile_attribution": "© OpenStreetMap contributors",
    }


@app.get("/api/events")
def events(
    q: str | None = None,
    min_magnitude: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    bbox: str | None = None,
    has_existing_data: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if q:
        where.append("(LOWER(place) LIKE ? OR LOWER(region_filter) LIKE ? OR LOWER(event_id) LIKE ?)")
        needle = f"%{q.lower()}%"
        params.extend([needle, needle, needle])
    if min_magnitude is not None:
        where.append("magnitude >= ?")
        params.append(min_magnitude)
    if start_date:
        where.append("event_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("event_date <= ?")
        params.append(end_date)
    if bbox:
        raw_parts = bbox.split(",")
        if len(raw_parts) != 4:
            raise HTTPException(status_code=422, detail="bbox must be minLon,minLat,maxLon,maxLat")
        try:
            min_lon, min_lat, max_lon, max_lat = [float(part.strip()) for part in raw_parts]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="bbox values must be numeric") from exc
        where.append("longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?")
        params.extend([min_lon, max_lon, min_lat, max_lat])
    if has_existing_data is not None:
        if has_existing_data:
            where.append("COALESCE(existing_data_status, '') NOT IN ('', 'NONE', 'NO', 'MISSING')")
        else:
            where.append("COALESCE(existing_data_status, '') IN ('', 'NONE', 'NO', 'MISSING')")
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    select_sql = (
        "SELECT event_id, time_utc, event_date, magnitude, longitude, latitude, depth_km, place, region_filter, "
        "existing_data_status, existing_station_count FROM usgs_m6plus_events_usa"
    )
    with connect_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM usgs_m6plus_events_usa{where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"{select_sql}{where_sql} ORDER BY time_utc DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@app.get("/api/events/{event_id}")
def event_detail(event_id: str) -> dict[str, Any]:
    event = get_event_or_404(event_id)
    with connect_db() as conn:
        candidate_counts = {
            str(row["radius_km"]): row["station_count"]
            for row in conn.execute(
                "SELECT radius_km, COUNT(DISTINCT station) AS station_count "
                "FROM event_earthscope_station_candidates WHERE event_id = ? GROUP BY radius_km ORDER BY radius_km",
                (event_id,),
            )
        }
        verified = conn.execute(
            "SELECT COUNT(DISTINCT station) AS station_count, COALESCE(SUM(obs_file_count), 0) AS obs_file_count "
            "FROM event_earthscope_station_verified_files WHERE event_id = ? AND COALESCE(obs_file_count, 0) > 0",
            (event_id,),
        ).fetchone()
    return {
        "event": event,
        "candidate_counts": candidate_counts,
        "verified_file_count": verified["obs_file_count"] if verified else 0,
        "verified_station_count": verified["station_count"] if verified else 0,
        "existing_data": {
            "status": event.get("existing_data_status"),
            "station_count": event.get("existing_station_count"),
            "source": event.get("existing_data_source"),
            "dataset_dir": event.get("existing_dataset_dir"),
        },
    }


@app.get("/api/events/{event_id}/stations")
def event_stations(
    event_id: str,
    radius_km: float = Query(200, ge=1, le=1000),
    verified_only: bool = False,
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    get_event_or_404(event_id)
    return {"items": query_selected_stations(event_id, radius_km, limit, verified_only)}


@app.get("/api/batch-summary")
def batch_summary() -> dict[str, Any]:
    return {"items": read_summary()}


@app.post("/api/workflows/preview")
def workflow_preview(request: WorkflowPreviewRequest) -> dict[str, Any]:
    return preview_workflow(request)


@app.post("/api/workflows/run")
def workflow_run(request: WorkflowRunRequest) -> dict[str, Any]:
    if not CONFIG.allow_workflow_run:
        raise HTTPException(status_code=403, detail="Workflow execution is disabled. Start dashboard with --allow-workflow-run.")
    base_url = validate_base_url(request.base_url)
    preview = preview_workflow(request)
    event = get_event_or_404(request.event_id)
    stations = list(preview["stations"])
    with jobs_lock:
        if any(record["status"] == "running" for record in jobs.values()):
            raise HTTPException(status_code=409, detail="Another workflow job is already running")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_id = f"{timestamp}-{request.event_id}-{uuid.uuid4().hex[:8]}"
    batch_path = create_batch_csv(job_id, event, stations)
    job_root = ensure_under(CONFIG.run_root / "web-jobs", CONFIG.run_root)
    job_root.mkdir(parents=True, exist_ok=True)
    log_path = ensure_under(job_root / f"{job_id}.log", job_root)
    summary_path = ensure_under(CONFIG.summary_path, CONFIG.summary_path.parent)
    command = [
        sys.executable,
        "-m",
        "gnss_eq",
        "run-batch",
        "--csv",
        str(batch_path),
        "--timeout",
        str(request.timeout),
        "--summary",
        str(summary_path),
        "--run-root",
        str(CONFIG.run_root),
        "--obs-root",
        str(CONFIG.obs_root),
    ]
    env = os.environ.copy()
    if base_url:
        env["EARTHSCOPE_BASE_URL"] = base_url
    if request.api_key:
        env["EARTHSCOPE_ACCESS_TOKEN"] = request.api_key
    log_handle = log_path.open("w")
    log_handle.write("Command: " + " ".join(command) + "\n")
    log_handle.flush()
    process = subprocess.Popen(command, cwd=str(ROOT), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
    record: dict[str, Any] = {
        "job_id": job_id,
        "event_id": request.event_id,
        "status": "running",
        "started_at": utc_now(),
        "ended_at": None,
        "returncode": None,
        "summary_path": str(summary_path),
        "log_path": str(log_path),
        "batch_path": str(batch_path),
        "process": process,
        "log_handle": log_handle,
    }
    with jobs_lock:
        jobs[job_id] = record
    threading.Thread(target=monitor_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    with jobs_lock:
        items = [safe_job_payload(record) for record in jobs.values()]
    return {"items": sorted(items, key=lambda row: row["started_at"], reverse=True)}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return safe_job_payload(record)


@app.get("/api/jobs/{job_id}/logs", response_class=PlainTextResponse)
def get_job_logs(job_id: str, tail: int = Query(200, ge=1, le=2000)) -> str:
    with jobs_lock:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        log_path = Path(record["log_path"])
    if not log_path.exists():
        return ""
    lines = log_path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-tail:]) + ("\n" if lines else "")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        process: subprocess.Popen[str] = record["process"]
        if record["status"] != "running" or process.poll() is not None:
            return safe_job_payload(record)
        process.terminate()
        record["status"] = "canceling"
    return {"job_id": job_id, "status": "canceling"}
