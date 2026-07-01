#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_cddis_event_batch_workflow.sh --csv events.csv [options]

CSV format:
  event_id,event_time,radius_km,status
  cddis-smoke-daej,2026-06-23T23:00:00Z,1000,

Optional CSV columns:
  process_event_time  PRIDE/quality event time for a row. Defaults to event_time.

Required:
  --csv FILE          Batch CSV. A status column is added if missing.

Batch options:
  --event-timeout N   Per-event workflow timeout seconds. Default: 3600
  --summary FILE      Batch summary TSV. Default: <csv-dir>/cddis-batch-summary.tsv
  --rerun-ok          Also run rows whose status is already OK
  --dry-run           Print event workflow commands and update no statuses

Forwarded workflow options:
  --radius-km KM      Default candidate radius when a CSV row has no radius_km
  --db DB             CDDIS SQLite DB. Default: data/cddis_highrate/cddis_highrate.sqlite
  --event-root DIR    CDDIS event root. Default: data/cddis_highrate/events
  --hours N           Hours before/after process event time. Default: 0.125
  --interval N        PRIDE processing interval in seconds. Default: 1
  --process-jobs N    Number of station PRIDE jobs to run concurrently. Default: 1
  --max-stations N    Process at most N obs files after sorting
  --download-timeout N CDDIS curl timeout seconds. Default: 180
  --cookie-file FILE  Earthdata cookie file. Default: ~/.urs_cookies
  --merge-method M    auto, gfzrnx, or python. Default: auto
  --skip-download     Reuse existing downloaded CDDIS files/manifests
  --skip-prepare      Reuse existing prepared obs files
  --skip-process      Do not run PRIDE
  --skip-quality      Do not run kin quality report
  --skip-normalize    Do not write isolated normalized export
  --skip-plot         Do not generate isolated normalized plots
  --overwrite         Redownload/reprepare existing files
  -h, --help          Show this help

Status behavior:
  Rows with status OK, CLASSIFIED_*, or ABANDONED_* are skipped by default.
  Blank, FAIL, TIMEOUT, and other statuses are runnable, so the same CSV can be resumed after interruption.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW="${SCRIPT_DIR}/run_cddis_event_1hz_pride_workflow.sh"

absolute_path() {
  realpath -m -- "$1"
}

CSV_FILE=""
SUMMARY_FILE=""
EVENT_TIMEOUT="3600"
DEFAULT_RADIUS_KM=""
DB="${PIPELINE_ROOT}/data/cddis_highrate/cddis_highrate.sqlite"
EVENT_ROOT="${PIPELINE_ROOT}/data/cddis_highrate/events"
HOURS="0.125"
INTERVAL="1"
PROCESS_JOBS="1"
MAX_STATIONS="0"
DOWNLOAD_TIMEOUT="180"
COOKIE_FILE="${HOME}/.urs_cookies"
MERGE_METHOD="auto"
RERUN_OK="0"
SKIP_DOWNLOAD="0"
SKIP_PREPARE="0"
SKIP_PROCESS="0"
SKIP_QUALITY="0"
SKIP_NORMALIZE="0"
SKIP_PLOT="0"
OVERWRITE="0"
DRY_RUN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv) CSV_FILE="$2"; shift 2 ;;
    --summary) SUMMARY_FILE="$2"; shift 2 ;;
    --event-timeout) EVENT_TIMEOUT="$2"; shift 2 ;;
    --timeout) EVENT_TIMEOUT="$2"; shift 2 ;;
    --radius-km) DEFAULT_RADIUS_KM="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --event-root) EVENT_ROOT="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --process-jobs|--jobs) PROCESS_JOBS="$2"; shift 2 ;;
    --max-stations) MAX_STATIONS="$2"; shift 2 ;;
    --download-timeout) DOWNLOAD_TIMEOUT="$2"; shift 2 ;;
    --cookie-file) COOKIE_FILE="$2"; shift 2 ;;
    --merge-method) MERGE_METHOD="$2"; shift 2 ;;
    --skip-download) SKIP_DOWNLOAD="1"; shift ;;
    --skip-prepare) SKIP_PREPARE="1"; shift ;;
    --skip-process) SKIP_PROCESS="1"; shift ;;
    --skip-quality) SKIP_QUALITY="1"; shift ;;
    --skip-normalize) SKIP_NORMALIZE="1"; shift ;;
    --skip-plot) SKIP_PLOT="1"; shift ;;
    --overwrite) OVERWRITE="1"; shift ;;
    --rerun-ok) RERUN_OK="1"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ -z "$CSV_FILE" ]]; then
  usage >&2
  exit 1
fi
if [[ ! -f "$CSV_FILE" ]]; then
  echo "Batch CSV not found: $CSV_FILE" >&2
  exit 1
fi
if [[ ! -x "$WORKFLOW" ]]; then
  echo "CDDIS event workflow not found or not executable: $WORKFLOW" >&2
  exit 1
fi
if ! [[ "$PROCESS_JOBS" =~ ^[0-9]+$ ]] || (( PROCESS_JOBS < 1 )); then
  echo "--process-jobs must be a positive integer" >&2
  exit 1
fi

if [[ -z "$SUMMARY_FILE" ]]; then
  SUMMARY_FILE="$(cd "$(dirname "$CSV_FILE")" && pwd)/cddis-batch-summary.tsv"
fi

CSV_FILE="$(absolute_path "$CSV_FILE")"
SUMMARY_FILE="$(absolute_path "$SUMMARY_FILE")"
DB="$(absolute_path "$DB")"
EVENT_ROOT="$(absolute_path "$EVENT_ROOT")"

export CSV_FILE SUMMARY_FILE EVENT_ROOT RERUN_OK DRY_RUN SKIP_DOWNLOAD DEFAULT_RADIUS_KM

python3 - <<'PY'
import csv
import os
from pathlib import Path

path = Path(os.environ["CSV_FILE"])
with path.open(newline="") as handle:
    rows = list(csv.DictReader(handle))

if not rows:
    raise SystemExit("Batch CSV has no data rows.")

fieldnames = list(rows[0].keys())
required = ["event_id", "event_time"]
missing = [name for name in required if name not in fieldnames]
if missing:
    raise SystemExit(f"Batch CSV missing required column(s): {', '.join(missing)}")

if "status" not in fieldnames:
    fieldnames.append("status")
    for row in rows:
        row["status"] = ""

skip_download = os.environ.get("SKIP_DOWNLOAD") == "1"
default_radius = os.environ.get("DEFAULT_RADIUS_KM", "").strip()
if not skip_download:
    bad_rows = []
    for index, row in enumerate(rows, start=2):
        radius = (row.get("radius_km") or default_radius).strip()
        if not radius:
            bad_rows.append(str(index))
    if bad_rows:
        raise SystemExit("radius_km is required for CSV row(s) " + ", ".join(bad_rows) + " unless --skip-download or --radius-km is set")

tmp = path.with_suffix(path.suffix + ".tmp")
with tmp.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
tmp.replace(path)
PY

list_runnable_rows() {
  python3 - <<'PY'
import csv
import os
from pathlib import Path

rerun_ok = os.environ.get("RERUN_OK") == "1"
default_radius = os.environ.get("DEFAULT_RADIUS_KM", "").strip()
with Path(os.environ["CSV_FILE"]).open(newline="") as handle:
    reader = csv.DictReader(handle)
    for index, row in enumerate(reader):
        status = (row.get("status") or "").strip().upper()
        if not rerun_ok and (status == "OK" or status.startswith("CLASSIFIED_") or status.startswith("ABANDONED_")):
            continue
        event_id = (row.get("event_id") or "").strip()
        event_time = (row.get("event_time") or "").strip()
        process_event_time = (row.get("process_event_time") or event_time).strip()
        radius_km = (row.get("radius_km") or default_radius).strip()
        if not event_id or not event_time:
            print(f"Skipping row {index}: event_id and event_time are required", flush=True)
            continue
        print(f"{index}\t{event_id}\t{event_time}\t{process_event_time}\t{radius_km}")
PY
}

update_status() {
  local row_index="$1"
  local status="$2"
  python3 - "$row_index" "$status" <<'PY'
import csv
import os
import sys
from pathlib import Path

path = Path(os.environ["CSV_FILE"])
row_index = int(sys.argv[1])
status = sys.argv[2]
with path.open(newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)

if "status" not in fieldnames:
    fieldnames.append("status")

if row_index >= len(rows):
    raise SystemExit(f"Row index out of range: {row_index}")

rows[row_index]["status"] = status
tmp = path.with_suffix(path.suffix + ".tmp")
with tmp.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
tmp.replace(path)
PY
}

write_batch_summary() {
  python3 - <<'PY'
import csv
import glob
import json
import os
from pathlib import Path

csv_path = Path(os.environ["CSV_FILE"])
summary_path = Path(os.environ["SUMMARY_FILE"])
event_root = Path(os.environ["EVENT_ROOT"])

fields = [
    "event_id",
    "event_time",
    "process_event_time",
    "radius_km",
    "batch_status",
    "download_status",
    "prepare_status",
    "process_status",
    "quality_status",
    "normalize_status",
    "plot_status",
    "obs_files",
    "kin_files",
    "workflow_dir",
    "normalized_event_dir",
    "figure_dir",
    "summary_json",
]

rows_out = []
with csv_path.open(newline="") as handle:
    for row in csv.DictReader(handle):
        event_id = (row.get("event_id") or "").strip()
        latest_json = ""
        summary = {}
        if event_id:
            matches = sorted(glob.glob(str(event_root / event_id / "workflow-*" / "reports" / "workflow-summary.json")))
            if matches:
                latest_json = matches[-1]
                try:
                    summary = json.loads(Path(latest_json).read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    summary = {}

        status = summary.get("status", {})
        counts = summary.get("counts", {})
        paths = summary.get("paths", {})
        rows_out.append({
            "event_id": event_id,
            "event_time": (row.get("event_time") or "").strip(),
            "process_event_time": (row.get("process_event_time") or "").strip(),
            "radius_km": (row.get("radius_km") or "").strip(),
            "batch_status": (row.get("status") or "").strip(),
            "download_status": status.get("download", ""),
            "prepare_status": status.get("prepare", ""),
            "process_status": status.get("process", ""),
            "quality_status": status.get("quality", ""),
            "normalize_status": status.get("normalize", ""),
            "plot_status": status.get("plot", ""),
            "obs_files": counts.get("obs_files", ""),
            "kin_files": counts.get("kin_files", ""),
            "workflow_dir": paths.get("workflow_dir", ""),
            "normalized_event_dir": paths.get("normalized_event_dir", ""),
            "figure_dir": paths.get("figure_dir", ""),
            "summary_json": latest_json,
        })

summary_path.parent.mkdir(parents=True, exist_ok=True)
with summary_path.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows_out)
PY
}

total=0
ok_count=0
fail_count=0
timeout_count=0

while IFS=$'\t' read -r row_index event_id event_time process_event_time radius_km; do
  [[ -z "${row_index:-}" ]] && continue
  if [[ "$row_index" == Skipping* ]]; then
    echo "$row_index" >&2
    continue
  fi

  total=$((total + 1))
  event_dir="${EVENT_ROOT}/${event_id}"
  cmd=(
    "$WORKFLOW"
    --event-id "$event_id"
    --event-time "$event_time"
    --event-dir "$event_dir"
    --db "$DB"
    --hours "$HOURS"
    --interval "$INTERVAL"
    --process-jobs "$PROCESS_JOBS"
    --timeout "$DOWNLOAD_TIMEOUT"
    --cookie-file "$COOKIE_FILE"
    --merge-method "$MERGE_METHOD"
  )
  [[ -n "$process_event_time" ]] && cmd+=(--process-event-time "$process_event_time")
  if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
    cmd+=(--skip-download)
  else
    cmd+=(--radius-km "$radius_km")
  fi
  if (( MAX_STATIONS > 0 )); then
    cmd+=(--max-stations "$MAX_STATIONS")
  fi
  [[ "$SKIP_PREPARE" == "1" ]] && cmd+=(--skip-prepare)
  [[ "$SKIP_PROCESS" == "1" ]] && cmd+=(--skip-process)
  [[ "$SKIP_QUALITY" == "1" ]] && cmd+=(--skip-quality)
  [[ "$SKIP_NORMALIZE" == "1" ]] && cmd+=(--skip-normalize)
  [[ "$SKIP_PLOT" == "1" ]] && cmd+=(--skip-plot)
  [[ "$OVERWRITE" == "1" ]] && cmd+=(--overwrite)
  [[ "$DRY_RUN" == "1" ]] && cmd+=(--dry-run)

  echo
  echo "CDDIS batch event: ${event_id}"
  printf 'Command:'
  printf ' %q' "${cmd[@]}"
  printf '\n'

  if [[ "$DRY_RUN" == "1" ]]; then
    "${cmd[@]}"
    continue
  fi

  set +e
  timeout "$EVENT_TIMEOUT" "${cmd[@]}"
  rc=$?
  set -e

  if [[ "$rc" -eq 0 ]]; then
    update_status "$row_index" "OK"
    ok_count=$((ok_count + 1))
  elif [[ "$rc" -eq 124 || "$rc" -eq 137 ]]; then
    update_status "$row_index" "TIMEOUT"
    timeout_count=$((timeout_count + 1))
    echo "CDDIS event timed out after ${EVENT_TIMEOUT}s: ${event_id}" >&2
  else
    update_status "$row_index" "FAIL"
    fail_count=$((fail_count + 1))
    echo "CDDIS event failed with exit code ${rc}: ${event_id}" >&2
  fi

  write_batch_summary
done < <(list_runnable_rows)

write_batch_summary

echo
echo "CDDIS batch summary: ${SUMMARY_FILE}"
echo "Runnable events processed: ${total}"
echo "OK: ${ok_count}"
echo "FAIL: ${fail_count}"
echo "TIMEOUT: ${timeout_count}"

if (( fail_count > 0 || timeout_count > 0 )); then
  exit 1
fi
