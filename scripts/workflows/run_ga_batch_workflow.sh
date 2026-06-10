#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_ga_batch_workflow.sh --csv events.csv [options]

CSV format:
  event_id,event_time,latitude,longitude,magnitude,radius_km,stations,status

Required:
  --csv FILE                Batch CSV. A status column is added if missing.

Batch options:
  --timeout SECONDS         Per-event timeout. Default: 3600
  --summary FILE            Batch summary TSV. Default: <csv-dir>/ga-batch-summary.tsv
  --rerun-ok                Also run rows whose status is already OK
  --dry-run                 Print event workflow commands and update no statuses

Forwarded workflow options:
  --hours N                 Hours before/after event for download and PRIDE. Default: 3
  --interval N              PRIDE processing interval in seconds. Default: 1
  --max-stations N          Limit station count for PRIDE processing
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --run-root DIR            Workflow run root. Default: ./runs
  --obs-root DIR            Canonical obs root. Default: ./data/obs
  --skip-download           Use existing obs files only
  --force-download          Download again even if valid obs files already exist
  --no-allow-partial        Do not pass --allow-partial. Batch default is partial allowed.
  --merge-method METHOD     auto, gfzrnx, or python. Default: auto
  --ga-api-url URL          GA RINEX API URL override
  --skip-process            Download only, do not run PRIDE
  --skip-plot               Do not generate final normalized figures
  --post-seconds N          Post-event detail plot window. Default: 200
  --cleanup-downloads       Remove raw downloader intermediates after successful kin generation (default: on)
  --cleanup-pride-workdir   Remove bulky reproducible PRIDE workdir files after each event workflow (default: on)
  --cleanup-obs             Remove data/obs/<event-id> files after successful kin generation (default: on)
  -h, --help                Show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW="${SCRIPT_DIR}/run_ga_event_1hz_pride_workflow.sh"

absolute_path() {
  realpath -m -- "$1"
}

CSV_FILE=""
SUMMARY_FILE=""
EVENT_TIMEOUT="3600"
HOURS="3"
INTERVAL="1"
MAX_STATIONS="0"
PROCESS_JOBS="1"
RUN_ROOT="${PIPELINE_ROOT}/runs"
OBS_ROOT="${PIPELINE_ROOT}/data/obs"
ALLOW_PARTIAL="1"
RERUN_OK="0"
SKIP_DOWNLOAD="0"
FORCE_DOWNLOAD="0"
SKIP_PROCESS="0"
SKIP_PLOT="0"
POST_SECONDS="200"
CLEANUP_DOWNLOADS="1"
CLEANUP_PRIDE_WORKDIR="1"
CLEANUP_OBS="1"
DRY_RUN="0"
MERGE_METHOD="auto"
GA_API_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv) CSV_FILE="$2"; shift 2 ;;
    --summary) SUMMARY_FILE="$2"; shift 2 ;;
    --timeout) EVENT_TIMEOUT="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-stations) MAX_STATIONS="$2"; shift 2 ;;
    --process-jobs|--jobs) PROCESS_JOBS="$2"; shift 2 ;;
    --run-root) RUN_ROOT="$2"; shift 2 ;;
    --obs-root) OBS_ROOT="$2"; shift 2 ;;
    --skip-download) SKIP_DOWNLOAD="1"; shift ;;
    --force-download) FORCE_DOWNLOAD="1"; shift ;;
    --no-allow-partial) ALLOW_PARTIAL="0"; shift ;;
    --merge-method) MERGE_METHOD="$2"; shift 2 ;;
    --ga-api-url) GA_API_URL="$2"; shift 2 ;;
    --skip-process) SKIP_PROCESS="1"; shift ;;
    --skip-plot) SKIP_PLOT="1"; shift ;;
    --post-seconds) POST_SECONDS="$2"; shift 2 ;;
    --cleanup-downloads) CLEANUP_DOWNLOADS="1"; shift ;;
    --cleanup-pride-workdir) CLEANUP_PRIDE_WORKDIR="1"; shift ;;
    --cleanup-obs) CLEANUP_OBS="1"; shift ;;
    --rerun-ok) RERUN_OK="1"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *) echo "Unexpected argument: $1" >&2; usage >&2; exit 1 ;;
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
  echo "GA workflow script not found or not executable: $WORKFLOW" >&2
  exit 1
fi

CSV_FILE="$(absolute_path "$CSV_FILE")"
RUN_ROOT="$(absolute_path "$RUN_ROOT")"
OBS_ROOT="$(absolute_path "$OBS_ROOT")"
if [[ -z "$SUMMARY_FILE" ]]; then
  SUMMARY_FILE="$(cd "$(dirname "$CSV_FILE")" && pwd)/ga-batch-summary.tsv"
fi
SUMMARY_FILE="$(absolute_path "$SUMMARY_FILE")"
QUEUE_FILE="$(mktemp "${TMPDIR:-/tmp}/ga-batch.XXXXXX.tsv")"
trap 'rm -f "$QUEUE_FILE"' EXIT

export CSV_FILE QUEUE_FILE RERUN_OK DRY_RUN
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
missing = [name for name in ["event_id", "event_time"] if name not in fieldnames]
if missing:
    raise SystemExit(f"Batch CSV missing required column(s): {', '.join(missing)}")
if "status" not in fieldnames:
    fieldnames.append("status")
    for row in rows:
        row["status"] = ""
if os.environ.get("DRY_RUN") != "1":
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)
with Path(os.environ["QUEUE_FILE"]).open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        status = (row.get("status") or "").strip().upper()
        if status == "OK" and os.environ.get("RERUN_OK") != "1":
            continue
        writer.writerow(row)
PY

mkdir -p "$(dirname "$SUMMARY_FILE")"
printf 'event_id\tevent_time\tbatch_status\tdownload_status\tobs_validation_status\tprocess_status\tplot_status\tquality_status\tquality_ok_stations\tquality_warn_stations\tquality_fail_stations\tcleanup_status\tpride_cleanup_status\tobs_cleanup_status\tnormalized_status\tnormalized_station_count\tnormalized_event_grade\trequested_stations\tobs_files\tkin_files\tplot_files\tduration_seconds\tworkflow_dir\tsummary_json\n' > "$SUMMARY_FILE"

update_status() {
  local event_id="$1"
  local status="$2"
  if [[ "$DRY_RUN" == "1" ]]; then
    return
  fi
  EVENT_ID_TO_UPDATE="$event_id" STATUS_TO_UPDATE="$status" python3 - <<'PY'
import csv
import os
from pathlib import Path

path = Path(os.environ["CSV_FILE"])
with path.open(newline="") as handle:
    rows = list(csv.DictReader(handle))
fieldnames = list(rows[0].keys())
for row in rows:
    if row.get("event_id") == os.environ["EVENT_ID_TO_UPDATE"]:
        row["status"] = os.environ["STATUS_TO_UPDATE"]
tmp = path.with_suffix(path.suffix + ".tmp")
with tmp.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
tmp.replace(path)
PY
}

append_summary() {
  local event_id="$1"
  local event_time="$2"
  local batch_status="$3"
  EVENT_ID_FOR_SUMMARY="$event_id" EVENT_TIME_FOR_SUMMARY="$event_time" BATCH_STATUS_FOR_SUMMARY="$batch_status" RUN_ROOT_FOR_SUMMARY="$RUN_ROOT" SUMMARY_FILE_FOR_SUMMARY="$SUMMARY_FILE" python3 - <<'PY'
import json
import os
from pathlib import Path

summary_file = Path(os.environ["SUMMARY_FILE_FOR_SUMMARY"])
event_id = os.environ["EVENT_ID_FOR_SUMMARY"]
event_time = os.environ["EVENT_TIME_FOR_SUMMARY"]
batch_status = os.environ["BATCH_STATUS_FOR_SUMMARY"]
run_root = Path(os.environ["RUN_ROOT_FOR_SUMMARY"])
candidates = sorted((run_root / event_id).glob("workflow-*/reports/workflow-summary.json"))
payload = {}
summary_json = ""
if candidates:
    summary_json = str(candidates[-1])
    try:
        payload = json.loads(candidates[-1].read_text())
    except json.JSONDecodeError:
        payload = {}
status = payload.get("status", {})
counts = payload.get("counts", {})
paths = payload.get("paths", {})
quality_summary = payload.get("quality", {}).get("summary", {})
values = [
    event_id,
    event_time,
    batch_status,
    status.get("download", ""),
    status.get("obs_validation", ""),
    status.get("process", ""),
    status.get("plot", ""),
    status.get("quality", ""),
    str(quality_summary.get("ok_station_count", "")),
    str(quality_summary.get("warn_station_count", "")),
    str(quality_summary.get("fail_station_count", "")),
    status.get("cleanup", ""),
    status.get("pride_cleanup", ""),
    status.get("obs_cleanup", ""),
    status.get("normalized", ""),
    str(counts.get("normalized_stations", "")),
    paths.get("normalized_event_grade", ""),
    str(counts.get("requested_stations", "")),
    str(counts.get("obs_files", "")),
    str(counts.get("kin_files", "")),
    str(counts.get("plot_files", "")),
    str(payload.get("duration_seconds", "")),
    paths.get("workflow_dir", ""),
    summary_json,
]
with summary_file.open("a", encoding="utf-8") as handle:
    handle.write("\t".join(str(value).replace("\t", " ") for value in values) + "\n")
PY
}

row_count=0
while IFS=$'\t' read -r event_id event_time latitude longitude magnitude radius_km stations rest; do
  if [[ "$event_id" == "event_id" ]]; then
    continue
  fi
  row_count=$((row_count + 1))
  if [[ -z "$stations" ]]; then
    echo "[$row_count] $event_id has no stations; marking NO_STATIONS" >&2
    update_status "$event_id" "NO_STATIONS"
    append_summary "$event_id" "$event_time" "NO_STATIONS"
    continue
  fi

  cmd=(
    "$WORKFLOW"
    --event-id "$event_id"
    --event-time "$event_time"
    --hours "$HOURS"
    --interval "$INTERVAL"
    --process-jobs "$PROCESS_JOBS"
    --run-root "$RUN_ROOT"
    --obs-root "$OBS_ROOT"
    --merge-method "$MERGE_METHOD"
    --post-seconds "$POST_SECONDS"
    --stations "$stations"
  )
  if (( MAX_STATIONS > 0 )); then
    cmd+=(--max-stations "$MAX_STATIONS")
  fi
  if [[ -n "$GA_API_URL" ]]; then
    cmd+=(--ga-api-url "$GA_API_URL")
  fi
  if [[ "$ALLOW_PARTIAL" == "1" ]]; then
    cmd+=(--allow-partial)
  fi
  if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
    cmd+=(--skip-download)
  fi
  if [[ "$FORCE_DOWNLOAD" == "1" ]]; then
    cmd+=(--force-download)
  fi
  if [[ "$SKIP_PROCESS" == "1" ]]; then
    cmd+=(--skip-process)
  fi
  if [[ "$SKIP_PLOT" == "1" ]]; then
    cmd+=(--skip-plot)
  fi
  if [[ "$CLEANUP_DOWNLOADS" == "1" ]]; then
    cmd+=(--cleanup-downloads)
  fi
  if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
    cmd+=(--cleanup-pride-workdir)
  fi
  if [[ "$CLEANUP_OBS" == "1" ]]; then
    cmd+=(--cleanup-obs)
  fi

  echo "[$row_count] Running GA event $event_id"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '  %q' "${cmd[@]}"
    printf '\n'
    append_summary "$event_id" "$event_time" "DRY_RUN"
    continue
  fi

  if timeout "$EVENT_TIMEOUT" "${cmd[@]}"; then
    update_status "$event_id" "OK"
    append_summary "$event_id" "$event_time" "OK"
  else
    rc=$?
    if [[ "$rc" == "124" ]]; then
      update_status "$event_id" "TIMEOUT"
      append_summary "$event_id" "$event_time" "TIMEOUT"
    else
      update_status "$event_id" "FAIL"
      append_summary "$event_id" "$event_time" "FAIL"
    fi
  fi
done < "$QUEUE_FILE"

echo "GA batch summary: $SUMMARY_FILE"
