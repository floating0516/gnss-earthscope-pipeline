#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_ring_event_1hz_pride_workflow.sh --event-id EVENT --event-time UTC_TIME [options] station1 [station2 ...]

Required:
  --event-id EVENT          Event id used for obs and run naming
  --event-time UTC_TIME     Event time in UTC, e.g. 2016-10-30T06:40:18Z

Station input:
  --stations "A B C"        Station codes separated by comma/space/newline
  --stations-file FILE      File containing station codes separated by comma/space/newline
  station1 ...              RING station codes, e.g. ARQT MRLC UNTR

Options:
  --year YYYY               Observation year. Default: derived from --event-time
  --doy DDD                 Observation day of year. Default: derived from --event-time
  --hours N                 Hours before/after event for download and PRIDE. Default: 3
  --interval N              PRIDE processing interval in seconds. Default: 1
  --max-stations N          Limit station count for PRIDE processing
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --run-root DIR            Workflow run root. Default: ./runs
  --obs-root DIR            Canonical obs root. Default: ./data/obs
  --skip-download           Use existing obs files only
  --force-download          Download again even if valid obs files already exist
  --allow-partial           Continue PRIDE with available stations when some stations fail
  --merge-method METHOD     auto, gfzrnx, or python. Default: auto
  --skip-process            Download only, do not run PRIDE
  --skip-plot               Do not generate ENU SVG plots
  --post-seconds N          Post-event detail plot window. Default: 200
  --cleanup-downloads       After a successful workflow, remove compressed/raw downloader intermediates (default: on)
  --cleanup-pride-workdir   After plots/quality, remove bulky reproducible PRIDE workdir files (default: on)
  --cleanup-obs             After successful kin generation, remove data/obs/<event-id> files (default: on)
  --dry-run                 Print commands and create no outputs
  -h, --help                Show this help

Directory layout:
  runs/<event-id>/workflow-<timestamp>/
    download/raw-ring-1hz/         INGV RING downloaded hourly RINEX files and manifests
    pride/                         PRIDE run directories
    logs/                          stdout/stderr logs for each stage
    manifests/                     station and observation file inventories
    plots/enu/                     ENU SVG plots from PRIDE kin_* files
    reports/                       workflow-summary.json/.tsv/.md

Canonical combined observation files are written to:
  data/obs/<event-id>/
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DOWNLOADER="${PIPELINE_ROOT}/tools/ring_downloader/fetch_ring_highrate.py"
PRIDE_PROCESSOR="${PIPELINE_ROOT}/tools/pride_processor/process_event_window.sh"
PRIDE_CLEANER="${PIPELINE_ROOT}/tools/pride_processor/cleanup_pride_workdir.sh"
PLOTTER="${PIPELINE_ROOT}/tools/pride_processor/plot_enu_svg.py"
QUALITY_SCRIPT="${PIPELINE_ROOT}/scripts/quality/compute_kin_quality.py"

absolute_path() {
  realpath -m -- "$1"
}

EVENT_ID=""
EVENT_TIME=""
YEAR=""
DOY=""
HOURS="3"
INTERVAL="1"
MAX_STATIONS="0"
PROCESS_JOBS="1"
RUN_ROOT="${PIPELINE_ROOT}/runs"
OBS_ROOT="${PIPELINE_ROOT}/data/obs"
STATIONS_FILE=""
SKIP_DOWNLOAD="0"
FORCE_DOWNLOAD="0"
ALLOW_PARTIAL="0"
SKIP_PROCESS="0"
SKIP_PLOT="0"
POST_SECONDS="200"
CLEANUP_DOWNLOADS="1"
CLEANUP_PRIDE_WORKDIR="1"
CLEANUP_OBS="1"
DRY_RUN="0"
MIN_OBS_BYTES="10240"
MERGE_METHOD="auto"
declare -a STATIONS=()
declare -A SEEN_STATIONS=()

append_station() {
  local station="$1"
  local key=""
  station="${station//$'\r'/}"
  station="$(printf '%s' "$station" | xargs)"
  key="$(printf '%s' "$station" | tr '[:lower:]' '[:upper:]')"
  key="${key:0:4}"
  if [[ -z "$key" || "$key" == \#* ]]; then
    return
  fi
  if [[ -z "${SEEN_STATIONS[$key]+x}" ]]; then
    SEEN_STATIONS["$key"]=1
    STATIONS+=("$key")
  fi
}

append_station_list() {
  local value="$1"
  local station=""
  while IFS= read -r station; do
    append_station "$station"
  done < <(printf '%s\n' "$value" | tr ',[:space:]' '\n')
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-id) EVENT_ID="$2"; shift 2 ;;
    --event-time) EVENT_TIME="$2"; shift 2 ;;
    --year) YEAR="$2"; shift 2 ;;
    --doy) DOY="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-stations) MAX_STATIONS="$2"; shift 2 ;;
    --process-jobs|--jobs) PROCESS_JOBS="$2"; shift 2 ;;
    --run-root) RUN_ROOT="$2"; shift 2 ;;
    --obs-root) OBS_ROOT="$2"; shift 2 ;;
    --stations-file) STATIONS_FILE="$2"; shift 2 ;;
    --stations) append_station_list "$2"; shift 2 ;;
    --skip-download) SKIP_DOWNLOAD="1"; shift ;;
    --force-download) FORCE_DOWNLOAD="1"; shift ;;
    --allow-partial) ALLOW_PARTIAL="1"; shift ;;
    --merge-method) MERGE_METHOD="$2"; shift 2 ;;
    --skip-process) SKIP_PROCESS="1"; shift ;;
    --skip-plot) SKIP_PLOT="1"; shift ;;
    --post-seconds) POST_SECONDS="$2"; shift 2 ;;
    --cleanup-downloads) CLEANUP_DOWNLOADS="1"; shift ;;
    --cleanup-pride-workdir) CLEANUP_PRIDE_WORKDIR="1"; shift ;;
    --cleanup-obs) CLEANUP_OBS="1"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *) append_station "$1"; shift ;;
  esac
done

for station in "$@"; do
  append_station "$station"
done

if [[ -n "$STATIONS_FILE" ]]; then
  if [[ ! -f "$STATIONS_FILE" ]]; then
    echo "Stations file not found: $STATIONS_FILE" >&2
    exit 1
  fi
  while IFS= read -r station; do
    append_station "$station"
  done < <(tr ',[:space:]' '\n' < "$STATIONS_FILE")
fi

if [[ -z "$EVENT_ID" || -z "$EVENT_TIME" ]]; then
  usage >&2
  exit 1
fi

RUN_ROOT="$(absolute_path "$RUN_ROOT")"
OBS_ROOT="$(absolute_path "$OBS_ROOT")"
if [[ -n "$STATIONS_FILE" ]]; then
  STATIONS_FILE="$(absolute_path "$STATIONS_FILE")"
fi

if ! [[ "$PROCESS_JOBS" =~ ^[0-9]+$ ]] || (( PROCESS_JOBS < 1 )); then
  echo "--process-jobs must be a positive integer" >&2
  exit 1
fi

case "$MERGE_METHOD" in
  auto|gfzrnx|python) ;;
  *) echo "--merge-method must be auto, gfzrnx, or python" >&2; exit 1 ;;
esac

if [[ ! -f "$DOWNLOADER" ]]; then
  echo "RING downloader not found: $DOWNLOADER" >&2
  exit 1
fi
if [[ ! -x "$PRIDE_PROCESSOR" ]]; then
  echo "PRIDE processor not found or not executable: $PRIDE_PROCESSOR" >&2
  exit 1
fi
if [[ ! -x "$PRIDE_CLEANER" ]]; then
  echo "PRIDE cleaner not found or not executable: $PRIDE_CLEANER" >&2
  exit 1
fi
if [[ ! -x "$PLOTTER" ]]; then
  echo "ENU plot script not found or not executable: $PLOTTER" >&2
  exit 1
fi

event_epoch="$(date -u -d "$EVENT_TIME" +%s)"
EVENT_TIME_UTC="$(date -u -d "@${event_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
if [[ -z "$YEAR" ]]; then
  YEAR="$(date -u -d "@${event_epoch}" +%Y)"
fi
if [[ -z "$DOY" ]]; then
  DOY="$(date -u -d "@${event_epoch}" +%j)"
else
  DOY="$(printf '%03d' "$((10#$DOY))")"
fi

run_tag="$(date -u -d "@${event_epoch}" +%Y%m%dT%H%M%SZ)"
WORKFLOW_DIR="${RUN_ROOT}/${EVENT_ID}/workflow-${run_tag}"
DOWNLOAD_DIR="${WORKFLOW_DIR}/download/raw-ring-1hz"
PRIDE_RUN_ROOT="${WORKFLOW_DIR}/pride"
LOG_DIR="${WORKFLOW_DIR}/logs"
MANIFEST_DIR="${WORKFLOW_DIR}/manifests"
REPORT_DIR="${WORKFLOW_DIR}/reports"
PLOTS_DIR="${WORKFLOW_DIR}/plots/enu"
OBS_DIR="${OBS_ROOT}/${EVENT_ID}"

if [[ "$SKIP_DOWNLOAD" == "0" && "${#STATIONS[@]}" -eq 0 ]]; then
  echo "At least one station or --stations-file is required unless --skip-download is set." >&2
  exit 1
fi

PRIDE_BIN_DIR="${PRIDE_BIN_DIR:-/home/lihe/.PRIDE_PPPAR_BIN}"
LOCAL_BIN_DIR="${LOCAL_BIN_DIR:-/home/lihe/.local/bin}"
export PATH="${PRIDE_BIN_DIR}:${LOCAL_BIN_DIR}:${PATH}"

echo "Event: ${EVENT_ID}"
echo "Event time UTC: ${EVENT_TIME_UTC}"
echo "Observation day: ${YEAR}/${DOY}"
echo "Workflow dir: ${WORKFLOW_DIR}"
echo "Canonical obs dir: ${OBS_DIR}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry run commands:"
  if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
    printf '  python3 %q --event-id %q --event-time %q --year %q --doy %q --hours %q --out-dir %q --obs-root %q --merge-method %q' \
      "$DOWNLOADER" "$EVENT_ID" "$EVENT_TIME_UTC" "$YEAR" "$DOY" "$HOURS" "$DOWNLOAD_DIR" "$OBS_ROOT" "$MERGE_METHOD"
    if [[ "$ALLOW_PARTIAL" == "1" ]]; then
      printf ' --allow-missing --keep-partial'
    fi
    if [[ -n "$STATIONS_FILE" ]]; then
      printf ' --stations-file %q' "$STATIONS_FILE"
    fi
    for station in "${STATIONS[@]}"; do
      printf ' %q' "$station"
    done
    printf '\n'
  fi
  if [[ "$SKIP_PROCESS" == "0" ]]; then
    printf '  %q --event-id %q --event-time %q --hours %q --interval %q --process-jobs %q --obs-dir %q --run-root %q\n' \
      "$PRIDE_PROCESSOR" "$EVENT_ID" "$EVENT_TIME_UTC" "$HOURS" "$INTERVAL" "$PROCESS_JOBS" "$OBS_DIR" "$PRIDE_RUN_ROOT"
  fi
  if [[ "$CLEANUP_DOWNLOADS" == "1" ]]; then
    printf '  find %q -type f <ring-raw-download-patterns> -print -delete\n' "$DOWNLOAD_DIR"
  fi
  if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
    printf '  %q --pride-summary <latest-pride-summary>\n' "$PRIDE_CLEANER"
  fi
  if [[ "$CLEANUP_OBS" == "1" ]]; then
    printf '  find %q -maxdepth 1 -type f <rinex-observation-patterns> -print -delete\n' "$OBS_DIR"
  fi
  exit 0
fi

mkdir -p "$DOWNLOAD_DIR" "$PRIDE_RUN_ROOT" "$LOG_DIR" "$MANIFEST_DIR" "$REPORT_DIR" "$PLOTS_DIR" "$OBS_DIR"
workflow_start_epoch="$(date -u +%s)"

{
  printf 'station\n'
  for station in "${STATIONS[@]}"; do
    printf '%s\n' "$station"
  done
} > "${MANIFEST_DIR}/requested-stations.tsv"

download_status="SKIPPED"
process_status="SKIPPED"
plot_status="SKIPPED"
quality_status="SKIPPED"
obs_validation_status="SKIPPED"

write_obs_inventory() {
  find "$OBS_DIR" -maxdepth 1 -type f \( -name "*.rnx" -o -name "*.[0-9][0-9]o" -o -name "*.obs" \) \
    | sort > "${MANIFEST_DIR}/obs-files.txt"
}

validate_obs_files() {
  local station=""
  local station_lc=""
  local match=""
  local size_bytes=""
  local valid_count=0
  local invalid_count=0
  local valid_obs_file="${MANIFEST_DIR}/valid-requested-obs-files.txt"

  write_obs_inventory
  : > "$valid_obs_file"
  {
    printf 'station\tobs_file\tsize_bytes\tstatus\treason\n'
    for station in "${STATIONS[@]}"; do
      station_lc="${station,,}"
      match="$(find "$OBS_DIR" -maxdepth 1 -type f \( -name "${station_lc}*" -o -name "${station}*" \) \( -name "*.rnx" -o -name "*.[0-9][0-9]o" -o -name "*.obs" \) | sort | head -n 1 || true)"
      if [[ -z "$match" ]]; then
        printf '%s\t\t0\tMISSING\tno obs file for station\n' "$station"
        invalid_count=$((invalid_count + 1))
        continue
      fi
      size_bytes="$(stat -c '%s' "$match")"
      if (( size_bytes < MIN_OBS_BYTES )); then
        printf '%s\t%s\t%s\tINVALID\tfile smaller than %s bytes\n' "$station" "$match" "$size_bytes" "$MIN_OBS_BYTES"
        invalid_count=$((invalid_count + 1))
      else
        printf '%s\t%s\t%s\tOK\tready\n' "$station" "$match" "$size_bytes"
        printf '%s\n' "$match" >> "$valid_obs_file"
        valid_count=$((valid_count + 1))
      fi
    done
  } > "${MANIFEST_DIR}/obs-validation.tsv"

  if (( ${#STATIONS[@]} == 0 )); then
    obs_validation_status="SKIPPED_NO_REQUESTED_STATIONS"
  elif (( invalid_count == 0 && valid_count == ${#STATIONS[@]} )); then
    obs_validation_status="OK"
  elif (( valid_count > 0 && ALLOW_PARTIAL == 1 )); then
    obs_validation_status="PARTIAL"
  else
    obs_validation_status="FAIL"
  fi
}

write_obs_inventory
obs_count="$(wc -l < "${MANIFEST_DIR}/obs-files.txt" | tr -d ' ')"

if [[ "$SKIP_DOWNLOAD" == "0" && "$FORCE_DOWNLOAD" == "0" && "${#STATIONS[@]}" -gt 0 ]]; then
  validate_obs_files
  if [[ "$obs_validation_status" == "OK" ]]; then
    echo
    echo "Valid RING obs files already exist; reusing them. Use --force-download to download again."
    SKIP_DOWNLOAD="1"
    download_status="REUSED"
  fi
fi

if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
  download_cmd=(
    python3 "$DOWNLOADER"
    --event-id "$EVENT_ID"
    --event-time "$EVENT_TIME_UTC"
    --year "$YEAR"
    --doy "$DOY"
    --hours "$HOURS"
    --out-dir "$DOWNLOAD_DIR"
    --obs-root "$OBS_ROOT"
    --merge-method "$MERGE_METHOD"
  )
  if [[ "$ALLOW_PARTIAL" == "1" ]]; then
    download_cmd+=(--allow-missing --keep-partial)
  fi
  if [[ -n "$STATIONS_FILE" ]]; then
    download_cmd+=(--stations-file "$STATIONS_FILE")
  fi
  download_cmd+=("${STATIONS[@]}")

  echo
  echo "Running RING download stage..."
  if "${download_cmd[@]}" > "${LOG_DIR}/download.log" 2>&1; then
    download_status="OK"
  else
    download_status="FAIL"
    if [[ "$ALLOW_PARTIAL" == "1" ]]; then
      download_status="PARTIAL_OR_FAIL"
    fi
  fi

  for manifest in ring-requested-files.tsv ring-downloaded-files.tsv ring-combined-files.tsv ring-download-summary.json; do
    if [[ -f "${DOWNLOAD_DIR}/${manifest}" ]]; then
      cp -f "${DOWNLOAD_DIR}/${manifest}" "${MANIFEST_DIR}/${manifest}"
    fi
  done
fi

write_obs_inventory
obs_count="$(wc -l < "${MANIFEST_DIR}/obs-files.txt" | tr -d ' ')"
if [[ "$SKIP_DOWNLOAD" == "1" && "$download_status" == "SKIPPED" && "$obs_count" != "0" ]]; then
  download_status="REUSED"
fi

if (( ${#STATIONS[@]} > 0 )); then
  validate_obs_files
  if [[ "$obs_validation_status" == "FAIL" ]]; then
    echo "Observation validation failed. See ${MANIFEST_DIR}/obs-validation.tsv" >&2
    process_status="BLOCKED_OBS_VALIDATION"
    SKIP_PROCESS="1"
    SKIP_PLOT="1"
  elif [[ "$obs_validation_status" == "PARTIAL" ]]; then
    echo "Observation validation is partial; continuing because --allow-partial was set."
  fi
fi

if [[ "$SKIP_PROCESS" == "0" ]]; then
  PROCESS_OBS_FILES="${MANIFEST_DIR}/process-obs-files.txt"
  if (( ${#STATIONS[@]} > 0 )) && [[ -s "${MANIFEST_DIR}/valid-requested-obs-files.txt" ]]; then
    cp -f "${MANIFEST_DIR}/valid-requested-obs-files.txt" "$PROCESS_OBS_FILES"
  else
    cp -f "${MANIFEST_DIR}/obs-files.txt" "$PROCESS_OBS_FILES"
  fi
  process_obs_count="$(wc -l < "$PROCESS_OBS_FILES" | tr -d ' ')"
  if (( process_obs_count == 0 )); then
    echo "No obs files found for PRIDE stage: $OBS_DIR" >&2
    process_status="FAIL"
  else
    mapfile -t process_obs_files < "$PROCESS_OBS_FILES"
    process_cmd=(
      "$PRIDE_PROCESSOR"
      --event-id "$EVENT_ID"
      --event-time "$EVENT_TIME_UTC"
      --hours "$HOURS"
      --interval "$INTERVAL"
      --process-jobs "$PROCESS_JOBS"
      --obs-dir "$OBS_DIR"
      --run-root "$PRIDE_RUN_ROOT"
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

latest_pride_summary="$(find "$PRIDE_RUN_ROOT" -type f -name 'event-window-summary.tsv' -printf '%T@\t%p\n' 2>/dev/null | sort -n | tail -n 1 | cut -f2- || true)"
if [[ -n "$latest_pride_summary" && -f "$latest_pride_summary" ]]; then
  awk -F '\t' '
    $1 == "station" { seen_header = 1; next }
    seen_header && NF >= 4 && $3 == "OK" { print $4 }
  ' "$latest_pride_summary" \
    | while IFS= read -r station_run_dir; do
        find "$station_run_dir" -type f -name 'kin_*'
      done \
    | sort > "${MANIFEST_DIR}/kin-files.txt"
else
  find "$PRIDE_RUN_ROOT" -type f -name 'kin_*' | sort > "${MANIFEST_DIR}/kin-files.txt"
fi
kin_count="$(wc -l < "${MANIFEST_DIR}/kin-files.txt" | tr -d ' ')"
plot_count="0"

if [[ "$SKIP_PROCESS" == "1" && "$process_status" == "SKIPPED" && "$kin_count" != "0" ]]; then
  process_status="REUSED"
fi

if [[ "$SKIP_PLOT" == "0" ]]; then
  if (( kin_count == 0 )); then
    plot_status="SKIPPED_NO_KIN"
  else
    echo
    echo "Running ENU plot stage..."
    mapfile -t kin_files < "${MANIFEST_DIR}/kin-files.txt"
    if "$PLOTTER" --event-time "$EVENT_TIME_UTC" --post-seconds "$POST_SECONDS" --out-dir "$PLOTS_DIR" "${kin_files[@]}" > "${LOG_DIR}/plot-enu.log" 2>&1; then
      plot_status="OK"
    else
      plot_status="FAIL"
    fi
  fi
fi

: > "${MANIFEST_DIR}/plot-files.txt"
if [[ -s "${MANIFEST_DIR}/kin-files.txt" ]]; then
  while IFS= read -r kin_file; do
    kin_name="$(basename "$kin_file")"
    station="${kin_name##*_}"
    find "$PLOTS_DIR" -maxdepth 1 -type f \( -name "${station}_enu_full.svg" -o -name "${station}_enu_post${POST_SECONDS}s.svg" \) >> "${MANIFEST_DIR}/plot-files.txt"
  done < "${MANIFEST_DIR}/kin-files.txt"
  sort -u -o "${MANIFEST_DIR}/plot-files.txt" "${MANIFEST_DIR}/plot-files.txt"
fi
plot_count="$(wc -l < "${MANIFEST_DIR}/plot-files.txt" | tr -d ' ')"

KIN_QUALITY_TSV="${REPORT_DIR}/kin-quality.tsv"
KIN_QUALITY_JSON="${REPORT_DIR}/kin-quality.json"
if (( kin_count == 0 )); then
  quality_status="SKIPPED_NO_KIN"
  printf 'station\tkin_file\tquality_status\tquality_flags\n' > "$KIN_QUALITY_TSV"
  printf '{"summary":{"status":"SKIPPED_NO_KIN","station_count":0},"stations":[]}\n' > "$KIN_QUALITY_JSON"
else
  echo
  echo "Computing kin quality metrics..."
  mapfile -t kin_files < "${MANIFEST_DIR}/kin-files.txt"
  if python3 "$QUALITY_SCRIPT" --event-time "$EVENT_TIME_UTC" --expected-hours-each-side "$HOURS" --allow-partial-failures --out-tsv "$KIN_QUALITY_TSV" --out-json "$KIN_QUALITY_JSON" "${kin_files[@]}" > "${LOG_DIR}/kin-quality.log" 2>&1; then
    quality_status="$(python3 -c "import json; print(json.load(open('$KIN_QUALITY_JSON')).get('summary',{}).get('status','OK'))")"
  else
    quality_status="FAIL"
  fi
fi

cleanup_status="SKIPPED"
pride_cleanup_status="SKIPPED"
obs_cleanup_status="SKIPPED"
if [[ "$CLEANUP_DOWNLOADS" == "1" ]]; then
  if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ]]; then
    cleanup_status="SKIPPED_WORKFLOW_FAILED"
  else
    echo
    echo "Cleaning raw RING download intermediates..."
    {
      find "$DOWNLOAD_DIR" -type f \( \
        -name '*.crx' -o -name '*.crx.gz' -o -name '*.d.Z' -o -name '*.d.gz' -o \
        -name '*.[0-9][0-9]d' -o -name '*.[0-9][0-9]d.Z' -o \
        -name '*.[0-9][0-9]o' -o -name '*.[0-9][0-9]o.gz' -o \
        -name '*.rnx' -o -name '*.rnx.gz' -o -name '*.rnx.Z' -o \
        -name '*.tmp' -o -name '*.part' \
      \) -print -delete
      find "$DOWNLOAD_DIR" -type d -empty -print -delete
    } > "${LOG_DIR}/cleanup-downloads.log" 2>&1 || true
    cleanup_status="OK"
  fi
fi

if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
  if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ]]; then
    pride_cleanup_status="SKIPPED_WORKFLOW_FAILED"
  elif [[ -z "$latest_pride_summary" || ! -f "$latest_pride_summary" ]]; then
    pride_cleanup_status="SKIPPED_NO_PRIDE_SUMMARY"
  else
    echo
    echo "Cleaning PRIDE workdir intermediates..."
    if "$PRIDE_CLEANER" --pride-summary "$latest_pride_summary" > "${LOG_DIR}/cleanup-pride-workdir.log" 2>&1; then
      pride_cleanup_status="OK"
    else
      pride_cleanup_status="FAIL"
    fi
  fi
fi

if [[ "$CLEANUP_OBS" == "1" ]]; then
  if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ]]; then
    obs_cleanup_status="SKIPPED_WORKFLOW_FAILED"
  elif (( kin_count < 1 )); then
    obs_cleanup_status="SKIPPED_NO_KIN"
  elif [[ ! -d "$OBS_DIR" ]]; then
    obs_cleanup_status="SKIPPED_NO_OBS_DIR"
  else
    echo
    echo "Cleaning canonical RING observation cache..."
    if {
      find "$OBS_DIR" -maxdepth 1 -type f \( \
        -name '*.rnx' -o -name '*.obs' -o -name '*.[0-9][0-9]o' -o \
        -name '*.[0-9][0-9]o.gz' -o \
        -name '*.rnx.gz' -o -name '*.rnx.Z' -o -name '*.crx' -o -name '*.crx.gz' -o \
        -name '*.d.Z' -o -name '*.d.gz' -o -name '*.[0-9][0-9]d' -o -name '*.[0-9][0-9]d.Z' \
      \) -print -delete
      find "$OBS_DIR" -maxdepth 1 -type d -empty -print -delete
    } > "${LOG_DIR}/cleanup-obs.log" 2>&1; then
      obs_cleanup_status="OK"
    else
      obs_cleanup_status="FAIL"
    fi
  fi
fi

workflow_end_epoch="$(date -u +%s)"
duration_seconds=$((workflow_end_epoch - workflow_start_epoch))

{
  printf 'key\tvalue\n'
  printf 'source\tRING\n'
  printf 'event_id\t%s\n' "$EVENT_ID"
  printf 'event_time_utc\t%s\n' "$EVENT_TIME_UTC"
  printf 'year\t%s\n' "$YEAR"
  printf 'doy\t%s\n' "$DOY"
  printf 'hours_each_side\t%s\n' "$HOURS"
  printf 'interval_seconds\t%s\n' "$INTERVAL"
  printf 'process_jobs\t%s\n' "$PROCESS_JOBS"
  printf 'merge_method\t%s\n' "$MERGE_METHOD"
  printf 'download_status\t%s\n' "$download_status"
  printf 'process_status\t%s\n' "$process_status"
  printf 'plot_status\t%s\n' "$plot_status"
  printf 'quality_status\t%s\n' "$quality_status"
  printf 'obs_validation_status\t%s\n' "$obs_validation_status"
  printf 'cleanup_status\t%s\n' "$cleanup_status"
  printf 'pride_cleanup_status\t%s\n' "$pride_cleanup_status"
  printf 'obs_cleanup_status\t%s\n' "$obs_cleanup_status"
  printf 'duration_seconds\t%s\n' "$duration_seconds"
  printf 'requested_station_count\t%s\n' "${#STATIONS[@]}"
  printf 'obs_file_count\t%s\n' "$obs_count"
  printf 'kin_file_count\t%s\n' "$kin_count"
  printf 'plot_file_count\t%s\n' "$plot_count"
  printf 'workflow_dir\t%s\n' "$WORKFLOW_DIR"
  printf 'download_dir\t%s\n' "$DOWNLOAD_DIR"
  printf 'obs_dir\t%s\n' "$OBS_DIR"
  printf 'pride_run_root\t%s\n' "$PRIDE_RUN_ROOT"
  printf 'plots_dir\t%s\n' "$PLOTS_DIR"
  printf 'kin_quality_tsv\t%s\n' "$KIN_QUALITY_TSV"
  printf 'kin_quality_json\t%s\n' "$KIN_QUALITY_JSON"
  printf 'pride_summary\t%s\n' "$latest_pride_summary"
} > "${REPORT_DIR}/workflow-summary.tsv"

WORKFLOW_JSON="${REPORT_DIR}/workflow-summary.json"
export EVENT_ID EVENT_TIME_UTC YEAR DOY HOURS INTERVAL MERGE_METHOD download_status process_status plot_status quality_status obs_validation_status cleanup_status pride_cleanup_status obs_cleanup_status duration_seconds
export WORKFLOW_DIR DOWNLOAD_DIR OBS_DIR PRIDE_RUN_ROOT PLOTS_DIR LOG_DIR MANIFEST_DIR REPORT_DIR latest_pride_summary
export REQUESTED_STATION_COUNT="${#STATIONS[@]}" OBS_COUNT="$obs_count" KIN_COUNT="$kin_count" PLOT_COUNT="$plot_count"
export KIN_QUALITY_TSV KIN_QUALITY_JSON

python3 - "$WORKFLOW_JSON" <<'PY'
import csv
import json
import os
import sys
from pathlib import Path


def read_lines(path):
    if not path or not Path(path).exists():
        return []
    return [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]


def read_tsv(path):
    if not path or not Path(path).exists():
        return []
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_json(path):
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text())
    except json.JSONDecodeError:
        return {}


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


summary = {
    "source": "RING",
    "event": {
        "id": os.environ["EVENT_ID"],
        "time_utc": os.environ["EVENT_TIME_UTC"],
        "year": os.environ["YEAR"],
        "doy": os.environ["DOY"],
    },
    "parameters": {
        "process_window_hours_each_side": float(os.environ["HOURS"]),
        "interval_seconds": as_int(os.environ["INTERVAL"]),
        "merge_method": os.environ["MERGE_METHOD"],
    },
    "status": {
        "download": os.environ["download_status"],
        "obs_validation": os.environ["obs_validation_status"],
        "process": os.environ["process_status"],
        "plot": os.environ["plot_status"],
        "quality": os.environ["quality_status"],
        "cleanup": os.environ["cleanup_status"],
        "pride_cleanup": os.environ["pride_cleanup_status"],
        "obs_cleanup": os.environ["obs_cleanup_status"],
    },
    "counts": {
        "requested_stations": as_int(os.environ["REQUESTED_STATION_COUNT"]),
        "obs_files": as_int(os.environ["OBS_COUNT"]),
        "kin_files": as_int(os.environ["KIN_COUNT"]),
        "plot_files": as_int(os.environ["PLOT_COUNT"]),
    },
    "duration_seconds": as_int(os.environ["duration_seconds"]),
    "paths": {
        "workflow_dir": os.environ["WORKFLOW_DIR"],
        "download_dir": os.environ["DOWNLOAD_DIR"],
        "obs_dir": os.environ["OBS_DIR"],
        "pride_run_root": os.environ["PRIDE_RUN_ROOT"],
        "plots_dir": os.environ["PLOTS_DIR"],
        "logs_dir": os.environ["LOG_DIR"],
        "manifests_dir": os.environ["MANIFEST_DIR"],
        "reports_dir": os.environ["REPORT_DIR"],
        "kin_quality_tsv": os.environ["KIN_QUALITY_TSV"],
        "kin_quality_json": os.environ["KIN_QUALITY_JSON"],
        "pride_summary": os.environ.get("latest_pride_summary", ""),
    },
    "ring_download": read_json(Path(os.environ["MANIFEST_DIR"]) / "ring-download-summary.json"),
    "obs_validation": read_tsv(Path(os.environ["MANIFEST_DIR"]) / "obs-validation.tsv"),
    "quality": read_json(os.environ.get("KIN_QUALITY_JSON")),
    "files": {
        "obs": read_lines(Path(os.environ["MANIFEST_DIR"]) / "obs-files.txt"),
        "kin": read_lines(Path(os.environ["MANIFEST_DIR"]) / "kin-files.txt"),
        "plots": read_lines(Path(os.environ["MANIFEST_DIR"]) / "plot-files.txt"),
    },
}
Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
PY

{
  printf '# RING 1Hz GNSS + PRIDE Workflow Summary\n\n'
  printf '%s\n' "- Event: \`${EVENT_ID}\`"
  printf '%s\n' "- Event time UTC: \`${EVENT_TIME_UTC}\`"
  printf '%s\n' "- Observation day: \`${YEAR}/${DOY}\`"
  printf '%s\n' "- Download status: \`${download_status}\`"
  printf '%s\n' "- PRIDE status: \`${process_status}\`"
  printf '%s\n' "- Plot status: \`${plot_status}\`"
  printf '%s\n' "- Quality status: \`${quality_status}\`"
  printf '%s\n' "- Obs validation: \`${obs_validation_status}\`"
  printf '%s\n' "- Cleanup status: \`${cleanup_status}\`"
  printf '%s\n' "- PRIDE cleanup status: \`${pride_cleanup_status}\`"
  printf '%s\n' "- Obs cleanup status: \`${obs_cleanup_status}\`"
  printf '%s\n' "- Duration seconds: \`${duration_seconds}\`"
  printf '%s\n' "- Requested stations: \`${#STATIONS[@]}\`"
  printf '%s\n' "- Observation files: \`${obs_count}\`"
  printf '%s\n' "- Kinematic files: \`${kin_count}\`"
  printf '%s\n\n' "- Plot files: \`${plot_count}\`"
  printf '## Paths\n\n'
  printf '%s\n' "- Workflow directory: \`${WORKFLOW_DIR}\`"
  printf '%s\n' "- RING downloads: \`${DOWNLOAD_DIR}\`"
  printf '%s\n' "- Canonical obs files: \`${OBS_DIR}\`"
  printf '%s\n' "- PRIDE runs: \`${PRIDE_RUN_ROOT}\`"
  printf '%s\n' "- Logs: \`${LOG_DIR}\`"
  printf '%s\n' "- Manifests: \`${MANIFEST_DIR}\`"
  printf '%s\n' "- ENU plots: \`${PLOTS_DIR}\`"
  printf '%s\n' "- Reports: \`${REPORT_DIR}\`"
  printf '%s\n' "- JSON summary: \`${WORKFLOW_JSON}\`"
} > "${REPORT_DIR}/workflow-summary.md"

echo
echo "Workflow summary: ${REPORT_DIR}/workflow-summary.md"
echo "JSON summary: ${WORKFLOW_JSON}"
echo "Machine-readable summary: ${REPORT_DIR}/workflow-summary.tsv"

final_plot_status="SKIPPED"
if [[ "$SKIP_PLOT" == "0" && "$download_status" != "FAIL" && "$process_status" != "FAIL" && "$process_status" != "BLOCKED_OBS_VALIDATION" && "$quality_status" != "FAIL" ]]; then
  echo
  echo "Running final normalized plot stage..."
  FINAL_NORMALIZED_ROOT="${FINAL_NORMALIZED_ROOT:-${PIPELINE_ROOT}/exports/normalized-ok-stations-us-nz}"
  FINAL_FIGURE_DIR="${FINAL_FIGURE_DIR:-${PIPELINE_ROOT}/figure}"
  FINAL_PLOT_PYTHON="${FINAL_PLOT_PYTHON:-${PIPELINE_ROOT}/.venv/bin/python}"
  if [[ ! -x "$FINAL_PLOT_PYTHON" ]]; then
    FINAL_PLOT_PYTHON="python3"
  fi
  if "$FINAL_PLOT_PYTHON" "${PIPELINE_ROOT}/scripts/plotting/plot_completed_normalized_event.py" --workflow-summary "$WORKFLOW_JSON" --normalized-root "$FINAL_NORMALIZED_ROOT" --outdir "$FINAL_FIGURE_DIR" > "${LOG_DIR}/plot-final-normalized.log" 2>&1; then
    final_plot_status="OK"
  else
    final_plot_status="FAIL"
    echo "Final normalized plotting failed. See ${LOG_DIR}/plot-final-normalized.log" >&2
  fi
fi

if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" || "$plot_status" == "FAIL" || "$quality_status" == "FAIL" || "$pride_cleanup_status" == "FAIL" || "$obs_cleanup_status" == "FAIL" || "$final_plot_status" == "FAIL" ]]; then
  exit 1
fi
