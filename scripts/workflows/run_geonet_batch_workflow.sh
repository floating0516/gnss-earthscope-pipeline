#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_geonet_batch_workflow.sh --csv events.csv [options]

CSV format:
  event_id,event_time,latitude,longitude,magnitude,radius_km,stations,status
  nz_demo,2026-04-29T00:30:00Z,-41.5,174.0,6.5,,WGTN KAIK,

Required:
  --csv FILE                Batch CSV. A status column is added if missing.

Batch options:
  --timeout SECONDS         Per-event timeout. Default: 3600
  --summary FILE            Batch summary TSV. Default: <csv-dir>/geonet-batch-summary.tsv
  --rerun-ok                Also run rows whose status is already OK
  --inventory FILE          GeoNet inventory CSV for automatic station selection
  --require-availability    When selecting stations, require 1 Hz files on event day
  --dry-run                 Print event workflow commands and update no statuses

Forwarded workflow options:
  --hours N                 Hours before/after event for download and PRIDE.
                            Default is delegated to the event workflow.
  --interval N              PRIDE processing interval in seconds. Default: 1
  --max-stations N          Limit station count for selection and PRIDE processing
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --run-root DIR            Workflow run root. Default: ./runs
  --obs-root DIR            Canonical obs root. Default: ./data/obs
  --skip-download           Use existing obs files only
  --force-download          Download again even if valid obs files already exist
  --no-allow-partial        Do not pass --allow-partial. Batch default is partial allowed.
  --download-source SOURCE  rolling or event-highrate. Default: rolling
  --no-auto-hours           For event-highrate, keep the default/requested --hours instead of adapting to obs coverage
  --merge-method METHOD     auto, gfzrnx, or python. Default: auto
  --skip-process            Download only, do not run PRIDE
  --skip-plot               Do not generate ENU SVG plots
  --post-seconds N          Post-event detail plot window. Default: 200
  --cleanup-downloads       Remove raw downloader intermediates after successful event workflow (default: on)
  --cleanup-pride-workdir   Remove bulky reproducible PRIDE workdir files after each event workflow (default: on)
  --cleanup-obs             Remove data/obs/<event-id> files after successful kin generation (default: on)
  -h, --help                Show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW="${SCRIPT_DIR}/run_geonet_event_1hz_pride_workflow.sh"
SELECTOR="${PIPELINE_ROOT}/tools/geonet_downloader/select_geonet_stations.py"

absolute_path() {
  realpath -m -- "$1"
}

CSV_FILE=""
SUMMARY_FILE=""
EVENT_TIMEOUT="3600"
HOURS="3"
HOURS_USER_SET="0"
INTERVAL="1"
MAX_STATIONS="0"
PROCESS_JOBS="1"
RUN_ROOT="${PIPELINE_ROOT}/runs"
OBS_ROOT="${PIPELINE_ROOT}/data/obs"
ALLOW_PARTIAL="1"
RERUN_OK="0"
INVENTORY="${PIPELINE_ROOT}/data/geonet_inventory/geonet_gnss_stations.csv"
REQUIRE_AVAILABILITY="0"
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
DOWNLOAD_SOURCE="rolling"
AUTO_HOURS_FROM_OBS="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv) CSV_FILE="$2"; shift 2 ;;
    --summary) SUMMARY_FILE="$2"; shift 2 ;;
    --timeout) EVENT_TIMEOUT="$2"; shift 2 ;;
    --hours) HOURS="$2"; HOURS_USER_SET="1"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-stations) MAX_STATIONS="$2"; shift 2 ;;
    --process-jobs|--jobs) PROCESS_JOBS="$2"; shift 2 ;;
    --run-root) RUN_ROOT="$2"; shift 2 ;;
    --obs-root) OBS_ROOT="$2"; shift 2 ;;
    --inventory) INVENTORY="$2"; shift 2 ;;
    --require-availability) REQUIRE_AVAILABILITY="1"; shift ;;
    --skip-download) SKIP_DOWNLOAD="1"; shift ;;
    --force-download) FORCE_DOWNLOAD="1"; shift ;;
    --no-allow-partial) ALLOW_PARTIAL="0"; shift ;;
    --download-source) DOWNLOAD_SOURCE="$2"; shift 2 ;;
    --no-auto-hours) AUTO_HOURS_FROM_OBS="0"; shift ;;
    --merge-method) MERGE_METHOD="$2"; shift 2 ;;
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
  echo "GeoNet workflow script not found or not executable: $WORKFLOW" >&2
  exit 1
fi

CSV_FILE="$(absolute_path "$CSV_FILE")"
RUN_ROOT="$(absolute_path "$RUN_ROOT")"
OBS_ROOT="$(absolute_path "$OBS_ROOT")"
INVENTORY="$(absolute_path "$INVENTORY")"
if [[ -z "$SUMMARY_FILE" ]]; then
  SUMMARY_FILE="$(cd "$(dirname "$CSV_FILE")" && pwd)/geonet-batch-summary.tsv"
fi
SUMMARY_FILE="$(absolute_path "$SUMMARY_FILE")"
QUEUE_FILE="$(mktemp "${TMPDIR:-/tmp}/geonet-batch.XXXXXX.tsv")"
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
required = ["event_id", "event_time"]
missing = [name for name in required if name not in fieldnames]
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
printf 'event_id\tevent_time\tstatus\tduration_seconds\tcleanup_status\tpride_cleanup_status\tobs_cleanup_status\tworkflow_command\n' > "$SUMMARY_FILE"

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
event_id = os.environ["EVENT_ID_TO_UPDATE"]
status = os.environ["STATUS_TO_UPDATE"]
with path.open(newline="") as handle:
    rows = list(csv.DictReader(handle))
fieldnames = list(rows[0].keys())
for row in rows:
    if row.get("event_id") == event_id:
        row["status"] = status
tmp = path.with_suffix(path.suffix + ".tmp")
with tmp.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
tmp.replace(path)
PY
}

latest_workflow_status_value() {
  local event_id="$1"
  local status_key="$2"
  EVENT_ID_FOR_SUMMARY="$event_id" RUN_ROOT_FOR_SUMMARY="$RUN_ROOT" STATUS_KEY_FOR_SUMMARY="$status_key" python3 - <<'PY'
import glob
import json
import os
from pathlib import Path

event_id = os.environ["EVENT_ID_FOR_SUMMARY"]
run_root = Path(os.environ["RUN_ROOT_FOR_SUMMARY"])
status_key = os.environ["STATUS_KEY_FOR_SUMMARY"]
matches = sorted(glob.glob(str(run_root / event_id / "workflow-*" / "reports" / "workflow-summary.json")))
if not matches:
    print("")
    raise SystemExit(0)
try:
    summary = json.loads(Path(matches[-1]).read_text())
except json.JSONDecodeError:
    print("")
    raise SystemExit(0)
print(summary.get("status", {}).get(status_key, ""))
PY
}

tail -n +2 "$QUEUE_FILE" | while IFS=$'\t' read -r event_id event_time latitude longitude magnitude radius_km stations status rest; do
  if [[ -z "$event_id" ]]; then
    continue
  fi

  station_file=""
  if [[ -z "${stations:-}" ]]; then
    if [[ ! -f "$INVENTORY" ]]; then
      echo "No stations in CSV and inventory not found: $INVENTORY" >&2
      update_status "$event_id" "SKIPPED_NO_INVENTORY"
      printf '%s\t%s\t%s\t0\t\t\t\t\n' "$event_id" "$event_time" "SKIPPED_NO_INVENTORY" >> "$SUMMARY_FILE"
      continue
    fi
    if [[ -z "${latitude:-}" || -z "${longitude:-}" || -z "${magnitude:-}" ]]; then
      update_status "$event_id" "SKIPPED_NO_STATIONS"
      printf '%s\t%s\t%s\t0\t\t\t\t\n' "$event_id" "$event_time" "SKIPPED_NO_STATIONS" >> "$SUMMARY_FILE"
      continue
    fi
    year="$(date -u -d "$event_time" +%Y)"
    doy="$(date -u -d "$event_time" +%j)"
    station_file="${PIPELINE_ROOT}/data/geonet_batches/${event_id}-stations.txt"
    selector_cmd=(python3 "$SELECTOR" --event-id "$event_id" --latitude "$latitude" --longitude "$longitude" --magnitude "$magnitude" --inventory "$INVENTORY" --year "$year" --doy "$doy" --out-stations "$station_file" --out-csv "${PIPELINE_ROOT}/data/geonet_batches/${event_id}-stations.csv" --out-json "${PIPELINE_ROOT}/data/geonet_batches/${event_id}-stations.json")
    if [[ -n "${radius_km:-}" ]]; then
      selector_cmd+=(--radius-km "$radius_km")
    fi
    if (( MAX_STATIONS > 0 )); then
      selector_cmd+=(--max-stations "$MAX_STATIONS")
    fi
    if [[ "$REQUIRE_AVAILABILITY" == "1" ]]; then
      selector_cmd+=(--require-availability)
    fi
    if ! "${selector_cmd[@]}" >/dev/null; then
      update_status "$event_id" "SKIPPED_SELECT_FAIL"
      printf '%s\t%s\t%s\t0\t\t\t\t%s\n' "$event_id" "$event_time" "SKIPPED_SELECT_FAIL" "${selector_cmd[*]}" >> "$SUMMARY_FILE"
      continue
    fi
    if [[ ! -s "$station_file" ]]; then
      update_status "$event_id" "SKIPPED_NO_STATIONS"
      printf '%s\t%s\t%s\t0\t\t\t\t%s\n' "$event_id" "$event_time" "SKIPPED_NO_STATIONS" "${selector_cmd[*]}" >> "$SUMMARY_FILE"
      continue
    fi
  fi

  workflow_cmd=("$WORKFLOW" --event-id "$event_id" --event-time "$event_time" --interval "$INTERVAL" --process-jobs "$PROCESS_JOBS" --download-source "$DOWNLOAD_SOURCE" --run-root "$RUN_ROOT" --obs-root "$OBS_ROOT" --post-seconds "$POST_SECONDS")
  if [[ "$HOURS_USER_SET" == "1" ]]; then
    workflow_cmd+=(--hours "$HOURS")
  fi
  if [[ "$AUTO_HOURS_FROM_OBS" == "0" ]]; then
    workflow_cmd+=(--no-auto-hours)
  fi
  workflow_cmd+=(--merge-method "$MERGE_METHOD")
  if (( MAX_STATIONS > 0 )); then
    workflow_cmd+=(--max-stations "$MAX_STATIONS")
  fi
  if [[ "$ALLOW_PARTIAL" == "1" ]]; then
    workflow_cmd+=(--allow-partial)
  fi
  if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
    workflow_cmd+=(--skip-download)
  fi
  if [[ "$FORCE_DOWNLOAD" == "1" ]]; then
    workflow_cmd+=(--force-download)
  fi
  if [[ "$SKIP_PROCESS" == "1" ]]; then
    workflow_cmd+=(--skip-process)
  fi
  if [[ "$SKIP_PLOT" == "1" ]]; then
    workflow_cmd+=(--skip-plot)
  fi
  if [[ "$CLEANUP_DOWNLOADS" == "1" ]]; then
    workflow_cmd+=(--cleanup-downloads)
  fi
  if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
    workflow_cmd+=(--cleanup-pride-workdir)
  fi
  if [[ "$CLEANUP_OBS" == "1" ]]; then
    workflow_cmd+=(--cleanup-obs)
  fi
  if [[ -n "$station_file" ]]; then
    workflow_cmd+=(--stations-file "$station_file")
  else
    workflow_cmd+=(--stations "$stations")
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    workflow_cmd+=(--dry-run)
  fi

  start_epoch="$(date -u +%s)"
  run_status="OK"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY RUN:'
    printf ' %q' "${workflow_cmd[@]}"
    printf '\n'
  elif timeout "$EVENT_TIMEOUT" "${workflow_cmd[@]}"; then
    run_status="OK"
  else
    code="$?"
    if [[ "$code" == "124" ]]; then
      run_status="TIMEOUT"
    else
      run_status="FAIL"
    fi
  fi
  end_epoch="$(date -u +%s)"
  duration="$((end_epoch - start_epoch))"
  cleanup_status="$(latest_workflow_status_value "$event_id" cleanup)"
  pride_cleanup_status="$(latest_workflow_status_value "$event_id" pride_cleanup)"
  obs_cleanup_status="$(latest_workflow_status_value "$event_id" obs_cleanup)"
  update_status "$event_id" "$run_status"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t' "$event_id" "$event_time" "$run_status" "$duration" "$cleanup_status" "$pride_cleanup_status" "$obs_cleanup_status" >> "$SUMMARY_FILE"
  printf '%q ' "${workflow_cmd[@]}" >> "$SUMMARY_FILE"
  printf '\n' >> "$SUMMARY_FILE"
done

echo "GeoNet batch summary: $SUMMARY_FILE"
