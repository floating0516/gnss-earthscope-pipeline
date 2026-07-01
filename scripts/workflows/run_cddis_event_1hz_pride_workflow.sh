#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_cddis_event_1hz_pride_workflow.sh --event-id EVENT --event-time UTC_TIME --radius-km KM [options]

Required:
  --event-id EVENT          CDDIS event id already present in event_cddis_station_candidates
  --event-time UTC_TIME     Event time in UTC, e.g. 2026-06-23T23:00:00Z
  --radius-km KM            Candidate radius to download from the CDDIS candidate table

Options:
  --process-event-time UTC  PRIDE/quality event time. Default: --event-time
  --db DB                   CDDIS SQLite DB. Default: data/cddis_highrate/cddis_highrate.sqlite
  --event-dir DIR           CDDIS event directory. Default: data/cddis_highrate/events/<event-id>
  --hours N                 Hours before/after process event time. Default: 0.125
  --interval N              PRIDE processing interval in seconds. Default: 1
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --max-stations N          Process at most N obs files after sorting
  --timeout N               CDDIS curl timeout seconds. Default: 180
  --cookie-file FILE        Earthdata cookie file. Default: ~/.urs_cookies
  --merge-method METHOD     auto, gfzrnx, or python. Default: auto
  --run-root DIR            PRIDE run root. Default: <event-dir>/pride
  --skip-download           Reuse existing downloaded CDDIS files/manifests
  --skip-prepare            Reuse existing prepared obs files
  --skip-process            Do not run PRIDE
  --skip-quality            Do not run kin quality report
  --skip-normalize          Do not write isolated normalized export
  --skip-plot               Do not generate isolated normalized plots
  --normalized-root DIR     Normalized export root. Default: <event-dir>/normalized
  --figure-dir DIR          Figure output directory. Default: <event-dir>/figures
  --overwrite               Redownload/reprepare existing files
  --dry-run                 Print commands and create no outputs
  -h, --help                Show this help

Outputs stay under:
  data/cddis_highrate/events/<event-id>/
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DOWNLOADER="${PIPELINE_ROOT}/tools/cddis_downloader/download_cddis_event_window.py"
PREPARER="${PIPELINE_ROOT}/tools/cddis_downloader/prepare_cddis_event_obs.py"
PRIDE_PROCESSOR="${PIPELINE_ROOT}/tools/pride_processor/process_event_window.sh"
QUALITY_SCRIPT="${PIPELINE_ROOT}/scripts/quality/compute_kin_quality.py"
NORMALIZER="${PIPELINE_ROOT}/scripts/normalize/normalize_cddis_pride_kin_event.py"
PLOTTER="${PIPELINE_ROOT}/scripts/plotting/plot_completed_normalized_event.py"

absolute_path() {
  realpath -m -- "$1"
}

resolve_path() {
  local path="$1"
  if [[ -z "$path" ]]; then
    printf '\n'
    return
  fi
  case "$path" in
    @ROOT@)
      printf '%s\n' "$PIPELINE_ROOT"
      ;;
    @ROOT@/*)
      printf '%s/%s\n' "$PIPELINE_ROOT" "${path#@ROOT@/}"
      ;;
    /*)
      if [[ -e "$path" || -L "$path" ]]; then
        printf '%s\n' "$path"
      elif [[ "$path" == *"/gnss-earthscope-pipeline/"* ]]; then
        printf '%s/%s\n' "$PIPELINE_ROOT" "${path#*/gnss-earthscope-pipeline/}"
      else
        printf '%s\n' "$path"
      fi
      ;;
    *)
      printf '%s/%s\n' "$PIPELINE_ROOT" "$path"
      ;;
  esac
}

EVENT_ID=""
EVENT_TIME=""
PROCESS_EVENT_TIME=""
RADIUS_KM=""
DB="${PIPELINE_ROOT}/data/cddis_highrate/cddis_highrate.sqlite"
EVENT_DIR=""
HOURS="0.125"
INTERVAL="1"
PROCESS_JOBS="1"
MAX_STATIONS="0"
TIMEOUT="180"
COOKIE_FILE="${HOME}/.urs_cookies"
MERGE_METHOD="auto"
RUN_ROOT=""
SKIP_DOWNLOAD="0"
SKIP_PREPARE="0"
SKIP_PROCESS="0"
SKIP_QUALITY="0"
SKIP_NORMALIZE="0"
SKIP_PLOT="0"
NORMALIZED_ROOT=""
FIGURE_DIR=""
OVERWRITE="0"
DRY_RUN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-id) EVENT_ID="$2"; shift 2 ;;
    --event-time) EVENT_TIME="$2"; shift 2 ;;
    --process-event-time) PROCESS_EVENT_TIME="$2"; shift 2 ;;
    --radius-km) RADIUS_KM="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --event-dir) EVENT_DIR="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --process-jobs|--jobs) PROCESS_JOBS="$2"; shift 2 ;;
    --max-stations) MAX_STATIONS="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --cookie-file) COOKIE_FILE="$2"; shift 2 ;;
    --merge-method) MERGE_METHOD="$2"; shift 2 ;;
    --run-root) RUN_ROOT="$2"; shift 2 ;;
    --skip-download) SKIP_DOWNLOAD="1"; shift ;;
    --skip-prepare) SKIP_PREPARE="1"; shift ;;
    --skip-process) SKIP_PROCESS="1"; shift ;;
    --skip-quality) SKIP_QUALITY="1"; shift ;;
    --skip-normalize) SKIP_NORMALIZE="1"; shift ;;
    --skip-plot) SKIP_PLOT="1"; shift ;;
    --normalized-root) NORMALIZED_ROOT="$2"; shift 2 ;;
    --figure-dir) FIGURE_DIR="$2"; shift 2 ;;
    --overwrite) OVERWRITE="1"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ -z "$EVENT_ID" || -z "$EVENT_TIME" ]]; then
  usage >&2
  exit 1
fi
if [[ "$SKIP_DOWNLOAD" == "0" && -z "$RADIUS_KM" ]]; then
  echo "--radius-km is required unless --skip-download is set" >&2
  exit 1
fi
if ! [[ "$PROCESS_JOBS" =~ ^[0-9]+$ ]] || (( PROCESS_JOBS < 1 )); then
  echo "--process-jobs must be a positive integer" >&2
  exit 1
fi

PROCESS_EVENT_TIME="${PROCESS_EVENT_TIME:-$EVENT_TIME}"
EVENT_DIR="$(absolute_path "${EVENT_DIR:-${PIPELINE_ROOT}/data/cddis_highrate/events/${EVENT_ID}}")"
DB="$(absolute_path "$DB")"
RUN_ROOT="$(absolute_path "${RUN_ROOT:-${EVENT_DIR}/pride}")"
NORMALIZED_ROOT="$(absolute_path "${NORMALIZED_ROOT:-${EVENT_DIR}/normalized}")"
FIGURE_DIR="$(absolute_path "${FIGURE_DIR:-${EVENT_DIR}/figures}")"
OBS_DIR="${EVENT_DIR}/obs"
WORKFLOW_DIR="${EVENT_DIR}/workflow-$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="${WORKFLOW_DIR}/logs"
MANIFEST_DIR="${WORKFLOW_DIR}/manifests"
REPORT_DIR="${WORKFLOW_DIR}/reports"
KIN_QUALITY_TSV="${REPORT_DIR}/kin-quality.tsv"
KIN_QUALITY_JSON="${REPORT_DIR}/kin-quality.json"
NORMALIZE_RESULT_JSON="${REPORT_DIR}/normalize-result.json"
SUMMARY_TSV="${REPORT_DIR}/workflow-summary.tsv"
SUMMARY_JSON="${REPORT_DIR}/workflow-summary.json"

if [[ ! -f "$DOWNLOADER" ]]; then
  echo "CDDIS event downloader not found: $DOWNLOADER" >&2
  exit 1
fi
if [[ ! -f "$PREPARER" ]]; then
  echo "CDDIS preparation script not found: $PREPARER" >&2
  exit 1
fi
if [[ ! -x "$PRIDE_PROCESSOR" && "$SKIP_PROCESS" == "0" ]]; then
  echo "PRIDE processor not found or not executable: $PRIDE_PROCESSOR" >&2
  exit 1
fi
if [[ ! -f "$NORMALIZER" && "$SKIP_NORMALIZE" == "0" ]]; then
  echo "CDDIS normalizer not found: $NORMALIZER" >&2
  exit 1
fi
if [[ ! -f "$PLOTTER" && "$SKIP_PLOT" == "0" ]]; then
  echo "Normalized plotter not found: $PLOTTER" >&2
  exit 1
fi

print_command() {
  printf '  '
  printf '%q ' "$@"
  printf '\n'
}

build_download_cmd() {
  download_cmd=(
    python3 "$DOWNLOADER"
    --db "$DB"
    --event-id "$EVENT_ID"
    --radius-km "$RADIUS_KM"
    --out-dir "$EVENT_DIR"
    --timeout "$TIMEOUT"
    --cookie-file "$COOKIE_FILE"
  )
  if [[ "$OVERWRITE" == "1" ]]; then
    download_cmd+=(--overwrite)
  fi
}

build_prepare_cmd() {
  prepare_cmd=(
    python3 "$PREPARER"
    --event-id "$EVENT_ID"
    --event-dir "$EVENT_DIR"
    --merge-method "$MERGE_METHOD"
  )
  if [[ "$OVERWRITE" == "1" ]]; then
    prepare_cmd+=(--overwrite)
  fi
}

copy_cddis_manifests() {
  local manifest=""
  mkdir -p "$MANIFEST_DIR"
  for manifest in \
    cddis-event-requested.tsv \
    cddis-event-downloaded.tsv \
    cddis-event-prepared.tsv \
    cddis-event-obs.tsv \
    cddis-event-summary.json \
    cddis-prepare-summary.json; do
    if [[ -f "${EVENT_DIR}/manifests/${manifest}" ]]; then
      cp -f "${EVENT_DIR}/manifests/${manifest}" "${MANIFEST_DIR}/${manifest}"
    fi
  done
}

write_obs_inventory() {
  mkdir -p "$MANIFEST_DIR"
  if [[ -d "$OBS_DIR" ]]; then
    find "$OBS_DIR" -maxdepth 1 -type f \( -name "*.rnx" -o -name "*.[0-9][0-9]o" -o -name "*.obs" \) | sort > "${MANIFEST_DIR}/obs-files.txt"
  else
    : > "${MANIFEST_DIR}/obs-files.txt"
  fi
}

write_workflow_summary() {
  {
    printf 'event_id\t%s\n' "$EVENT_ID"
    printf 'event_time_utc\t%s\n' "$EVENT_TIME"
    printf 'process_event_time_utc\t%s\n' "$PROCESS_EVENT_TIME"
    printf 'radius_km\t%s\n' "${RADIUS_KM:-}"
    printf 'download_status\t%s\n' "$download_status"
    printf 'prepare_status\t%s\n' "$prepare_status"
    printf 'process_status\t%s\n' "$process_status"
    printf 'quality_status\t%s\n' "$quality_status"
    printf 'normalize_status\t%s\n' "$normalize_status"
    printf 'plot_status\t%s\n' "$plot_status"
    printf 'obs_file_count\t%s\n' "$obs_count"
    printf 'kin_file_count\t%s\n' "$kin_count"
    printf 'event_dir\t%s\n' "$EVENT_DIR"
    printf 'workflow_dir\t%s\n' "$WORKFLOW_DIR"
    printf 'run_root\t%s\n' "$RUN_ROOT"
    printf 'normalized_root\t%s\n' "$NORMALIZED_ROOT"
    printf 'normalized_event_dir\t%s\n' "$normalized_event_dir"
    printf 'figure_dir\t%s\n' "$FIGURE_DIR"
    printf 'kin_quality_tsv\t%s\n' "$KIN_QUALITY_TSV"
    printf 'kin_quality_json\t%s\n' "$KIN_QUALITY_JSON"
    printf 'normalize_result_json\t%s\n' "$NORMALIZE_RESULT_JSON"
  } > "$SUMMARY_TSV"

  export EVENT_ID EVENT_TIME PROCESS_EVENT_TIME RADIUS_KM download_status prepare_status process_status quality_status normalize_status plot_status obs_count kin_count EVENT_DIR WORKFLOW_DIR RUN_ROOT NORMALIZED_ROOT normalized_event_dir FIGURE_DIR KIN_QUALITY_TSV KIN_QUALITY_JSON NORMALIZE_RESULT_JSON SUMMARY_TSV SUMMARY_JSON
  python3 - <<'PY'
import json
import os
from pathlib import Path

def as_int(name: str) -> int:
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0

payload = {
    "provider": "CDDIS",
    "event_id": os.environ["EVENT_ID"],
    "event_time_utc": os.environ["EVENT_TIME"],
    "process_event_time_utc": os.environ["PROCESS_EVENT_TIME"],
    "radius_km": os.environ.get("RADIUS_KM", ""),
    "status": {
        "download": os.environ["download_status"],
        "prepare": os.environ["prepare_status"],
        "process": os.environ["process_status"],
        "quality": os.environ["quality_status"],
        "normalize": os.environ["normalize_status"],
        "plot": os.environ["plot_status"],
    },
    "counts": {
        "obs_files": as_int("obs_count"),
        "kin_files": as_int("kin_count"),
    },
    "paths": {
        "event_dir": os.environ["EVENT_DIR"],
        "workflow_dir": os.environ["WORKFLOW_DIR"],
        "run_root": os.environ["RUN_ROOT"],
        "normalized_root": os.environ["NORMALIZED_ROOT"],
        "normalized_event_dir": os.environ.get("normalized_event_dir", ""),
        "figure_dir": os.environ["FIGURE_DIR"],
        "summary_tsv": os.environ["SUMMARY_TSV"],
        "summary_json": os.environ["SUMMARY_JSON"],
        "kin_quality_tsv": os.environ["KIN_QUALITY_TSV"],
        "kin_quality_json": os.environ["KIN_QUALITY_JSON"],
        "normalize_result_json": os.environ["NORMALIZE_RESULT_JSON"],
    },
}
Path(os.environ["SUMMARY_JSON"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

if [[ "$DRY_RUN" == "1" ]]; then
  echo "CDDIS workflow dry run: ${EVENT_ID}"
  echo "Event dir: ${EVENT_DIR}"
  echo "Workflow dir: ${WORKFLOW_DIR}"
  if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
    build_download_cmd
    print_command "${download_cmd[@]}"
  fi
  if [[ "$SKIP_PREPARE" == "0" ]]; then
    build_prepare_cmd
    print_command "${prepare_cmd[@]}"
  fi
  if [[ "$SKIP_PROCESS" == "0" ]]; then
    print_command "$PRIDE_PROCESSOR" --event-id "$EVENT_ID" --event-time "$PROCESS_EVENT_TIME" --hours "$HOURS" --interval "$INTERVAL" --process-jobs "$PROCESS_JOBS" --obs-dir "$OBS_DIR" --run-root "$RUN_ROOT" '<obs-files>'
  fi
  if [[ "$SKIP_QUALITY" == "0" ]]; then
    print_command python3 "$QUALITY_SCRIPT" --event-time "$PROCESS_EVENT_TIME" --expected-hours-each-side "$HOURS" --allow-partial-failures --out-tsv "$KIN_QUALITY_TSV" --out-json "$KIN_QUALITY_JSON" '<kin-files>'
  fi
  if [[ "$SKIP_NORMALIZE" == "0" ]]; then
    print_command python3 "$NORMALIZER" --workflow-summary "$SUMMARY_JSON" --quality-json "$KIN_QUALITY_JSON" --db "$DB" --normalized-root "$NORMALIZED_ROOT"
  fi
  if [[ "$SKIP_PLOT" == "0" ]]; then
    print_command python3 "$PLOTTER" --workflow-summary "$SUMMARY_JSON" --normalized-root "$NORMALIZED_ROOT" --outdir "$FIGURE_DIR"
  fi
  exit 0
fi

mkdir -p "$EVENT_DIR" "$LOG_DIR" "$MANIFEST_DIR" "$REPORT_DIR" "$RUN_ROOT"

echo "CDDIS event workflow: ${EVENT_ID}"
echo "Event time UTC: ${EVENT_TIME}"
echo "PRIDE event time UTC: ${PROCESS_EVENT_TIME}"
echo "Radius: ${RADIUS_KM:-SKIPPED} km"
echo "Event dir: ${EVENT_DIR}"
echo "Workflow dir: ${WORKFLOW_DIR}"

download_status="SKIPPED"
prepare_status="SKIPPED"
process_status="SKIPPED"
quality_status="SKIPPED"
normalize_status="SKIPPED"
plot_status="SKIPPED"
normalized_event_dir=""

if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
  build_download_cmd
  echo
  echo "Running CDDIS download stage..."
  if "${download_cmd[@]}" > "${LOG_DIR}/download.log" 2>&1; then
    download_status="OK"
  else
    download_status="FAIL"
  fi
fi
copy_cddis_manifests

if [[ "$SKIP_PREPARE" == "0" ]]; then
  build_prepare_cmd
  echo
  echo "Running CDDIS preparation stage..."
  if "${prepare_cmd[@]}" > "${LOG_DIR}/prepare.log" 2>&1; then
    prepare_status="OK"
  else
    prepare_status="FAIL"
  fi
fi
copy_cddis_manifests
write_obs_inventory
obs_count="$(wc -l < "${MANIFEST_DIR}/obs-files.txt" | tr -d ' ')"

if [[ "$SKIP_PROCESS" == "0" ]]; then
  if [[ "$prepare_status" == "FAIL" || "$download_status" == "FAIL" ]]; then
    process_status="BLOCKED_INPUT_STAGE"
  elif (( obs_count == 0 )); then
    echo "No obs files found for PRIDE stage: ${OBS_DIR}" >&2
    process_status="FAIL"
  else
    mapfile -t process_obs_files < "${MANIFEST_DIR}/obs-files.txt"
    process_cmd=(
      "$PRIDE_PROCESSOR"
      --event-id "$EVENT_ID"
      --event-time "$PROCESS_EVENT_TIME"
      --hours "$HOURS"
      --interval "$INTERVAL"
      --process-jobs "$PROCESS_JOBS"
      --obs-dir "$OBS_DIR"
      --run-root "$RUN_ROOT"
    )
    if (( MAX_STATIONS > 0 )); then
      process_cmd+=(--max-stations "$MAX_STATIONS")
    fi
    process_cmd+=("${process_obs_files[@]}")

    echo
    echo "Running PRIDE stage..."
    if "${process_cmd[@]}" > "${LOG_DIR}/pride.log" 2>&1; then
      process_status="OK"
    else
      process_status="FAIL"
    fi
  fi
fi

latest_pride_summary="$(find "$RUN_ROOT" -type f -name 'event-window-summary.tsv' -printf '%T@\t%p\n' 2>/dev/null | sort -n | tail -n 1 | cut -f2- || true)"
if [[ -n "$latest_pride_summary" && -f "$latest_pride_summary" ]]; then
  awk -F '\t' '
    $1 == "station" { seen_header = 1; next }
    seen_header && NF >= 4 && $3 == "OK" { print $4 }
	  ' "$latest_pride_summary" \
	    | while IFS= read -r station_run_dir; do
	        find "$(resolve_path "$station_run_dir")" -type f -name 'kin_*'
	      done \
	    | sort > "${MANIFEST_DIR}/kin-files.txt"
else
  find "$RUN_ROOT" -type f -name 'kin_*' | sort > "${MANIFEST_DIR}/kin-files.txt"
fi
kin_count="$(wc -l < "${MANIFEST_DIR}/kin-files.txt" | tr -d ' ')"

if [[ "$SKIP_QUALITY" == "0" ]]; then
  if [[ "$process_status" == "FAIL" || "$process_status" == "BLOCKED_INPUT_STAGE" ]]; then
    quality_status="BLOCKED_PROCESS_STAGE"
  elif (( kin_count == 0 )); then
    quality_status="FAIL"
  else
    mapfile -t kin_files < "${MANIFEST_DIR}/kin-files.txt"
    echo
    echo "Running quality stage..."
    if python3 "$QUALITY_SCRIPT" \
      --event-time "$PROCESS_EVENT_TIME" \
      --expected-hours-each-side "$HOURS" \
      --allow-partial-failures \
      --out-tsv "$KIN_QUALITY_TSV" \
      --out-json "$KIN_QUALITY_JSON" \
      "${kin_files[@]}" > "${LOG_DIR}/kin-quality.log" 2>&1; then
      quality_status="OK"
    else
      quality_status="FAIL"
    fi
  fi
fi

write_workflow_summary

if [[ "$SKIP_NORMALIZE" == "0" ]]; then
  if [[ "$quality_status" != "OK" ]]; then
    normalize_status="BLOCKED_QUALITY_STAGE"
  else
    echo
    echo "Running normalization stage..."
    if python3 "$NORMALIZER" \
      --workflow-summary "$SUMMARY_JSON" \
      --quality-json "$KIN_QUALITY_JSON" \
      --db "$DB" \
      --normalized-root "$NORMALIZED_ROOT" > "$NORMALIZE_RESULT_JSON" 2> "${LOG_DIR}/normalize.log"; then
      normalize_status="OK"
      normalized_event_dir="$(python3 - "$NORMALIZE_RESULT_JSON" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload.get("normalized_event_dir", ""))
PY
)"
    else
      normalize_status="FAIL"
    fi
  fi
fi

if [[ "$SKIP_PLOT" == "0" ]]; then
  if [[ "$normalize_status" != "OK" ]]; then
    plot_status="BLOCKED_NORMALIZE_STAGE"
  else
    echo
    echo "Running plotting stage..."
    if PYTHONPATH="${PIPELINE_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" python3 "$PLOTTER" \
      --workflow-summary "$SUMMARY_JSON" \
      --normalized-root "$NORMALIZED_ROOT" \
      --outdir "$FIGURE_DIR" > "${LOG_DIR}/plot.log" 2>&1; then
      plot_status="OK"
    else
      plot_status="FAIL"
    fi
  fi
fi

write_workflow_summary

echo
cat "$SUMMARY_TSV"

if [[ "$download_status" == "FAIL" || "$prepare_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_INPUT_STAGE" || "$quality_status" == "FAIL" || "$quality_status" == "BLOCKED_PROCESS_STAGE" || "$normalize_status" == "FAIL" || "$normalize_status" == "BLOCKED_QUALITY_STAGE" || "$plot_status" == "FAIL" || "$plot_status" == "BLOCKED_NORMALIZE_STAGE" ]]; then
  exit 1
fi
