#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_event_batch_workflow.sh --csv events.csv [options]

CSV format:
  event_id,event_time,stations,status
  ak021d1u1nos,2021-10-11T09:10:25Z,AB07 AC02 AC12,
  us7000fcn1,2022-06-15T08:30:00Z,AV01 AV02,

Required:
  --csv FILE                Batch CSV. A status column is added if missing.

Batch options:
  --timeout SECONDS         Per-event timeout. Default: 3600
  --summary FILE            Batch summary TSV. Default: <csv-dir>/batch-summary.tsv
  --rerun-ok                Also run rows whose status is already OK
  --existing-db FILE        SQLite DB with usgs_m6plus_events_usa existing_data_status labels
  --include-existing        Run events marked with existing normalized data
  --dry-run                 Print event workflow commands and update no statuses

Forwarded workflow options:
  --hours N                 Hours before/after event for PRIDE. Default: 3
  --interval N              PRIDE processing interval in seconds. Default: 1
  --max-stations N          Limit station count for PRIDE processing
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --run-root DIR            Workflow run root. Default: ./runs
  --obs-root DIR            Canonical obs root. Default: ./data/obs
  --normalize-db FILE       SQLite DB for normalization station coordinates. Default: data/earthscope_availability/earthscope_1hz.sqlite
  --verified-files-db FILE  SQLite DB with verified first_obs_url records for direct highrate downloads
  --skip-download           Use existing obs files only
  --force-download          Download again even if valid obs files already exist
  --no-allow-partial        Do not pass --allow-partial. Batch default is partial allowed.
  --skip-process            Download only, do not run PRIDE
  --skip-plot               Do not generate final normalized map/waveform figures
  --cleanup-downloads       Remove raw downloader intermediates after successful event workflow (default: on)
  --cleanup-pride-workdir   Remove bulky reproducible PRIDE workdir files after each event workflow (default: on)
  --cleanup-obs             Remove data/obs/<event-id> files after successful kin generation (default: on)
  --no-cleanup-downloads    Preserve raw downloader intermediates
  --no-cleanup-pride-workdir Preserve bulky reproducible PRIDE workdir files
  --no-cleanup-obs          Preserve data/obs/<event-id> files
  -h, --help                Show this help

Status behavior:
  Rows with status OK, CLASSIFIED_*, or ABANDONED_* are skipped by default.
  Blank, FAIL, TIMEOUT, and other statuses are runnable, so the same CSV can be resumed after interruption.
  Rows whose event_id is marked with existing_data_status in --existing-db are marked
  SKIPPED_EXISTING and skipped unless --include-existing is set.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW="${SCRIPT_DIR}/run_event_1hz_pride_workflow.sh"
PROXY_ENV_VARS=(http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY)

for proxy_var in "${PROXY_ENV_VARS[@]}"; do
  unset "${proxy_var}"
done

absolute_path() {
  realpath -m -- "$1"
}

portable_path() {
  local path="$1"
  local abs=""
  if [[ -z "$path" ]]; then
    printf '\n'
    return
  fi
  abs="$(realpath -m -- "$path")"
  case "$abs" in
    "$PIPELINE_ROOT")
      printf '@ROOT@\n'
      ;;
    "$PIPELINE_ROOT"/*)
      printf '@ROOT@/%s\n' "${abs#"$PIPELINE_ROOT"/}"
      ;;
    *)
      printf '%s\n' "$abs"
      ;;
  esac
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
NORMALIZE_DB="${PIPELINE_ROOT}/data/earthscope_availability/earthscope_1hz.sqlite"
VERIFIED_FILES_DB=""
ALLOW_PARTIAL="1"
RERUN_OK="0"
EXISTING_DB=""
INCLUDE_EXISTING="0"
SKIP_DOWNLOAD="0"
FORCE_DOWNLOAD="0"
SKIP_PROCESS="0"
SKIP_PLOT="0"
CLEANUP_DOWNLOADS="1"
CLEANUP_PRIDE_WORKDIR="1"
CLEANUP_OBS="1"
DRY_RUN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv)
      CSV_FILE="$2"
      shift 2
      ;;
    --summary)
      SUMMARY_FILE="$2"
      shift 2
      ;;
    --timeout)
      EVENT_TIMEOUT="$2"
      shift 2
      ;;
    --hours)
      HOURS="$2"
      shift 2
      ;;
    --interval)
      INTERVAL="$2"
      shift 2
      ;;
    --max-stations)
      MAX_STATIONS="$2"
      shift 2
      ;;
    --process-jobs|--jobs)
      PROCESS_JOBS="$2"
      shift 2
      ;;
    --run-root)
      RUN_ROOT="$2"
      shift 2
      ;;
    --obs-root)
      OBS_ROOT="$2"
      shift 2
      ;;
    --normalize-db)
      NORMALIZE_DB="$2"
      shift 2
      ;;
    --verified-files-db)
      VERIFIED_FILES_DB="$2"
      shift 2
      ;;
    --skip-download)
      SKIP_DOWNLOAD="1"
      shift
      ;;
    --force-download)
      FORCE_DOWNLOAD="1"
      shift
      ;;
    --no-allow-partial)
      ALLOW_PARTIAL="0"
      shift
      ;;
    --skip-process)
      SKIP_PROCESS="1"
      shift
      ;;
    --skip-plot)
      SKIP_PLOT="1"
      shift
      ;;
    --post-seconds)
      shift 2 # Deprecated compatibility option.
      ;;
    --cleanup-downloads)
      CLEANUP_DOWNLOADS="1"
      shift
      ;;
    --no-cleanup-downloads)
      CLEANUP_DOWNLOADS="0"
      shift
      ;;
    --cleanup-pride-workdir)
      CLEANUP_PRIDE_WORKDIR="1"
      shift
      ;;
    --no-cleanup-pride-workdir)
      CLEANUP_PRIDE_WORKDIR="0"
      shift
      ;;
    --cleanup-obs)
      CLEANUP_OBS="1"
      shift
      ;;
    --no-cleanup-obs)
      CLEANUP_OBS="0"
      shift
      ;;
    --rerun-ok)
      RERUN_OK="1"
      shift
      ;;
    --existing-db)
      EXISTING_DB="$2"
      shift 2
      ;;
    --include-existing)
      INCLUDE_EXISTING="1"
      shift
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      echo "Unexpected argument: $1" >&2
      usage >&2
      exit 1
      ;;
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
  echo "Workflow script not found or not executable: $WORKFLOW" >&2
  exit 1
fi

if [[ -z "$SUMMARY_FILE" ]]; then
  SUMMARY_FILE="$(cd "$(dirname "$CSV_FILE")" && pwd)/batch-summary.tsv"
fi

RUN_ROOT="$(absolute_path "$RUN_ROOT")"
OBS_ROOT="$(absolute_path "$OBS_ROOT")"
NORMALIZE_DB="$(absolute_path "$NORMALIZE_DB")"
if [[ -n "$VERIFIED_FILES_DB" ]]; then
  VERIFIED_FILES_DB="$(absolute_path "$VERIFIED_FILES_DB")"
fi
SUMMARY_FILE="$(absolute_path "$SUMMARY_FILE")"

export CSV_FILE SUMMARY_FILE RUN_ROOT RERUN_OK DRY_RUN EXISTING_DB INCLUDE_EXISTING PIPELINE_ROOT

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
required = ["event_id", "event_time", "stations"]
missing = [name for name in required if name not in fieldnames]
if missing:
    raise SystemExit(f"Batch CSV missing required column(s): {', '.join(missing)}")

if "status" not in fieldnames:
    fieldnames.append("status")
    for row in rows:
        row["status"] = ""

tmp = path.with_suffix(path.suffix + ".tmp")
with tmp.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
tmp.replace(path)
PY

mark_existing_rows() {
  python3 - <<'PY'
import csv
import os
import sqlite3
from pathlib import Path

if os.environ.get("INCLUDE_EXISTING") == "1":
    raise SystemExit(0)
if os.environ.get("DRY_RUN") == "1":
    raise SystemExit(0)

db_path = os.environ.get("EXISTING_DB", "")
if not db_path or not Path(db_path).exists():
    raise SystemExit(0)

conn = sqlite3.connect(db_path)
try:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(usgs_m6plus_events_usa)")}
    if "existing_data_status" not in columns:
        raise SystemExit(0)
    existing = {
        row[0]: row[1]
        for row in conn.execute(
            """
            SELECT event_id, existing_data_status
            FROM usgs_m6plus_events_usa
            WHERE COALESCE(existing_data_status, '') <> ''
            """
        )
    }
finally:
    conn.close()

if not existing:
    raise SystemExit(0)

path = Path(os.environ["CSV_FILE"])
with path.open(newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)

changed = False
if "status" not in fieldnames:
    fieldnames.append("status")

for row in rows:
    event_id = (row.get("event_id") or "").strip()
    if not event_id or event_id not in existing:
        continue
    status = (row.get("status") or "").strip().upper()
    if status == "OK":
        continue
    row["status"] = "SKIPPED_EXISTING"
    changed = True

if changed:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)
PY
}

mark_existing_rows

list_runnable_rows() {
  python3 - <<'PY'
import csv
import os
import sqlite3
from pathlib import Path

rerun_ok = os.environ.get("RERUN_OK") == "1"
include_existing = os.environ.get("INCLUDE_EXISTING") == "1"
existing_events = set()
db_path = os.environ.get("EXISTING_DB", "")
if not include_existing and db_path and Path(db_path).exists():
    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(usgs_m6plus_events_usa)")}
        if "existing_data_status" in columns:
            existing_events = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT event_id
                    FROM usgs_m6plus_events_usa
                    WHERE COALESCE(existing_data_status, '') <> ''
                    """
                )
            }
    finally:
        conn.close()
with Path(os.environ["CSV_FILE"]).open(newline="") as handle:
    reader = csv.DictReader(handle)
    for index, row in enumerate(reader):
        status = (row.get("status") or "").strip().upper()
        if not rerun_ok and (status == "OK" or status.startswith("CLASSIFIED_") or status.startswith("ABANDONED_")):
            continue
        if status == "SKIPPED_EXISTING" and not include_existing:
            continue
        event_id = (row.get("event_id") or "").strip()
        if event_id in existing_events:
            continue
        event_time = (row.get("event_time") or "").strip()
        stations = (row.get("stations") or "").strip()
        if not event_id or not event_time:
            print(f"Skipping row {index}: event_id and event_time are required", flush=True)
            continue
        print(f"{index}\t{event_id}\t{event_time}\t{stations}")
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
  python3 "${PIPELINE_ROOT}/scripts/workflows/build_event_batch_summary.py" \
    --csv "$CSV_FILE" \
    --summary "$SUMMARY_FILE" \
    --run-root "$RUN_ROOT" \
    --pipeline-root "$PIPELINE_ROOT"
}

total=0
ok_count=0
fail_count=0
timeout_count=0

while IFS=$'\t' read -r row_index event_id event_time stations; do
  [[ -z "${row_index:-}" ]] && continue
  if [[ "$row_index" == Skipping* ]]; then
    echo "$row_index" >&2
    continue
  fi

  total=$((total + 1))
  cmd=(
    "$WORKFLOW"
    --event-id "$event_id"
    --event-time "$event_time"
    --stations "$stations"
    --hours "$HOURS"
    --interval "$INTERVAL"
    --process-jobs "$PROCESS_JOBS"
    --run-root "$RUN_ROOT"
    --obs-root "$OBS_ROOT"
    --normalize-db "$NORMALIZE_DB"
  )
  if (( MAX_STATIONS > 0 )); then
    cmd+=(--max-stations "$MAX_STATIONS")
  fi
  [[ -n "$VERIFIED_FILES_DB" ]] && cmd+=(--verified-files-db "$VERIFIED_FILES_DB")
  [[ "$SKIP_DOWNLOAD" == "1" ]] && cmd+=(--skip-download)
  [[ "$FORCE_DOWNLOAD" == "1" ]] && cmd+=(--force-download)
  [[ "$ALLOW_PARTIAL" == "1" ]] && cmd+=(--allow-partial)
  [[ "$SKIP_PROCESS" == "1" ]] && cmd+=(--skip-process)
  [[ "$SKIP_PLOT" == "1" ]] && cmd+=(--skip-plot)
  [[ "$CLEANUP_DOWNLOADS" == "0" ]] && cmd+=(--no-cleanup-downloads)
  [[ "$CLEANUP_PRIDE_WORKDIR" == "0" ]] && cmd+=(--no-cleanup-pride-workdir)
  [[ "$CLEANUP_OBS" == "0" ]] && cmd+=(--no-cleanup-obs)
  [[ "$DRY_RUN" == "1" ]] && cmd+=(--dry-run)

  echo
  echo "Batch event: ${event_id}"
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
    echo "Event timed out after ${EVENT_TIMEOUT}s: ${event_id}" >&2
  else
    update_status "$row_index" "FAIL"
    fail_count=$((fail_count + 1))
    echo "Event failed with exit code ${rc}: ${event_id}" >&2
  fi

  write_batch_summary
done < <(list_runnable_rows)

write_batch_summary

echo
echo "Batch summary: ${SUMMARY_FILE}"
echo "Runnable events processed: ${total}"
echo "OK: ${ok_count}"
echo "FAIL: ${fail_count}"
echo "TIMEOUT: ${timeout_count}"

if (( fail_count > 0 || timeout_count > 0 )); then
  exit 1
fi
