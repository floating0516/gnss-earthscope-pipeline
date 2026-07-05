#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_event_1hz_pride_workflow.sh --event-id EVENT --event-time UTC_TIME [options] station1 [station2 ...]

Required:
  --event-id EVENT          Event id used for obs and run naming
  --event-time UTC_TIME     Event time in UTC, e.g. 2021-10-11T09:10:25Z

Station input:
  --stations "A B C"       Station codes separated by comma/space/newline
  --stations-file FILE      File containing station codes separated by comma/space/newline
  station1 ...              Station codes, e.g. AB07 AC02 AC12

Options:
  --year YYYY               Observation year. Default: derived from --event-time
  --doy DDD                 Observation day of year. Default: derived from --event-time
  --hours N                 Hours before/after event for PRIDE processing window. Default: 3
  --interval N              PRIDE processing interval in seconds. Default: 1
  --max-stations N          Limit station count for PRIDE processing
  --process-jobs N          Number of station PRIDE jobs to run concurrently. Default: 1
  --run-root DIR            Workflow run root. Default: ./runs
  --obs-root DIR            Canonical obs root. Default: ./data/obs
  --normalize-db FILE       SQLite DB for normalization station coordinates. Default: data/earthscope_availability/earthscope_1hz.sqlite
  --verified-files-db FILE  SQLite DB with verified first_obs_url records for direct highrate downloads
  --skip-download           Use existing obs files only
  --force-download          Download again even if valid obs files already exist
  --allow-partial           Continue PRIDE with available stations when some obs files fail validation
  --skip-process            Download only, do not run PRIDE
  --skip-plot               Do not generate final normalized map/waveform figures
  --cleanup-downloads       After kin generation, remove compressed/raw downloader intermediates (default: on)
  --cleanup-pride-workdir   After kin generation, remove bulky reproducible PRIDE workdir files (default: on)
  --cleanup-obs             After kin generation, remove data/obs/<event-id> files (default: on)
  --no-cleanup-downloads    Preserve compressed/raw downloader intermediates
  --no-cleanup-pride-workdir Preserve bulky reproducible PRIDE workdir files
  --no-cleanup-obs          Preserve data/obs/<event-id> files
  --dry-run                 Print commands and create no outputs
  -h, --help                Show this help

Directory layout:
  runs/<event-id>/workflow-<timestamp>/
    download/raw-earthscope-1hz/   EarthScope downloaded products and manifests
    pride/                         PRIDE run directories
    logs/                          stdout/stderr logs for each stage
    manifests/                     station and observation file inventories
    reports/                       workflow-summary.json/.tsv/.md

Canonical observation files are copied by the downloader to:
  data/obs/<event-id>/
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DOWNLOADER="${PIPELINE_ROOT}/tools/earthscope_downloader/download_earthscope_default.sh"
PRIDE_PROCESSOR="${PIPELINE_ROOT}/tools/pride_processor/process_event_window.sh"
PRIDE_CLEANER="${PIPELINE_ROOT}/tools/pride_processor/cleanup_pride_workdir.sh"
QUALITY_SCRIPT="${PIPELINE_ROOT}/scripts/quality/compute_kin_quality.py"
NORMALIZER="${PIPELINE_ROOT}/scripts/normalize/normalize_pride_kin_event.py"
VALIDATOR="${PIPELINE_ROOT}/scripts/summaries/validate_normalized_export.py"
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

portable_manifest() {
  local in_file="$1"
  local out_file="$2"
  : > "$out_file"
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    portable_path "$path" >> "$out_file"
  done < "$in_file"
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
NORMALIZE_DB="${PIPELINE_ROOT}/data/earthscope_availability/earthscope_1hz.sqlite"
VERIFIED_FILES_DB=""
STATIONS_FILE=""
SKIP_DOWNLOAD="0"
FORCE_DOWNLOAD="0"
ALLOW_PARTIAL="0"
SKIP_PROCESS="0"
SKIP_PLOT="0"
CLEANUP_DOWNLOADS="1"
CLEANUP_PRIDE_WORKDIR="1"
CLEANUP_OBS="1"
DRY_RUN="0"
MIN_OBS_BYTES="10240"
declare -a STATIONS=()
declare -A SEEN_STATIONS=()

append_station() {
  local station="$1"
  local key=""
  station="${station//$'\r'/}"
  station="$(printf '%s' "$station" | xargs)"
  key="$(printf '%s' "$station" | tr '[:lower:]' '[:upper:]')"

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
    --event-id)
      EVENT_ID="$2"
      shift 2
      ;;
    --event-time)
      EVENT_TIME="$2"
      shift 2
      ;;
    --year)
      YEAR="$2"
      shift 2
      ;;
    --doy)
      DOY="$2"
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
    --stations-file)
      STATIONS_FILE="$2"
      shift 2
      ;;
    --stations)
      append_station_list "$2"
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
    --allow-partial)
      ALLOW_PARTIAL="1"
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
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      append_station "$1"
      shift
      ;;
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

if ! [[ "$PROCESS_JOBS" =~ ^[0-9]+$ ]] || (( PROCESS_JOBS < 1 )); then
  echo "--process-jobs must be a positive integer" >&2
  exit 1
fi

RUN_ROOT="$(absolute_path "$RUN_ROOT")"
OBS_ROOT="$(absolute_path "$OBS_ROOT")"
NORMALIZE_DB="$(absolute_path "$NORMALIZE_DB")"
if [[ -n "$VERIFIED_FILES_DB" ]]; then
  VERIFIED_FILES_DB="$(absolute_path "$VERIFIED_FILES_DB")"
fi
if [[ -n "$STATIONS_FILE" ]]; then
  STATIONS_FILE="$(absolute_path "$STATIONS_FILE")"
fi

if [[ ! -x "$DOWNLOADER" ]]; then
  echo "Downloader script not found or not executable: $DOWNLOADER" >&2
  exit 1
fi

if [[ ! -x "$PRIDE_PROCESSOR" ]]; then
  echo "PRIDE processor script not found or not executable: $PRIDE_PROCESSOR" >&2
  exit 1
fi

if [[ ! -x "$PRIDE_CLEANER" ]]; then
  echo "PRIDE cleaner script not found or not executable: $PRIDE_CLEANER" >&2
  exit 1
fi

if [[ ! -x "$NORMALIZER" ]]; then
  echo "Normalizer script not found or not executable: $NORMALIZER" >&2
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
DOWNLOAD_DIR="${WORKFLOW_DIR}/download/raw-earthscope-1hz"
PRIDE_RUN_ROOT="${WORKFLOW_DIR}/pride"
LOG_DIR="${WORKFLOW_DIR}/logs"
MANIFEST_DIR="${WORKFLOW_DIR}/manifests"
REPORT_DIR="${WORKFLOW_DIR}/reports"
WORKFLOW_JSON="${REPORT_DIR}/workflow-summary.json"
OBS_DIR="${OBS_ROOT}/${EVENT_ID}"

if [[ "$SKIP_DOWNLOAD" == "0" && "${#STATIONS[@]}" -eq 0 ]]; then
  echo "At least one station or --stations-file is required unless --skip-download is set." >&2
  exit 1
fi

if [[ -n "${EARTHSCOPE_ENV_BIN:-}" ]]; then
  export PATH="${EARTHSCOPE_ENV_BIN}:${PATH}"
fi
if [[ -n "${PRIDE_BIN_DIR:-}" ]]; then
  export PATH="${PRIDE_BIN_DIR}:${PATH}"
fi
if [[ -n "${LOCAL_BIN_DIR:-}" ]]; then
  export PATH="${LOCAL_BIN_DIR}:${PATH}"
fi

echo "Event: ${EVENT_ID}"
echo "Event time UTC: ${EVENT_TIME_UTC}"
echo "Observation day: ${YEAR}/${DOY}"
echo "Workflow dir: ${WORKFLOW_DIR}"
echo "Canonical obs dir: ${OBS_DIR}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry run commands:"
  if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
    printf '  %q --year %q --doy %q --event-id %q --sample-interval 01S --out-dir %q --obs-root %q' \
      "$DOWNLOADER" "$YEAR" "$DOY" "$EVENT_ID" "$DOWNLOAD_DIR" "$OBS_ROOT"
    if [[ -n "$STATIONS_FILE" ]]; then
      printf ' --stations-file %q' "$STATIONS_FILE"
    fi
    if [[ -n "$VERIFIED_FILES_DB" ]]; then
      printf ' --verified-files-db %q' "$VERIFIED_FILES_DB"
    fi
    for station in "${STATIONS[@]}"; do
      printf ' %q' "$station"
    done
    printf '\n'
  fi
  if [[ "$SKIP_PROCESS" == "0" ]]; then
    printf '  %q --event-id %q --event-time %q --hours %q --interval %q --obs-dir %q --run-root %q' \
      "$PRIDE_PROCESSOR" "$EVENT_ID" "$EVENT_TIME_UTC" "$HOURS" "$INTERVAL" "$OBS_DIR" "$PRIDE_RUN_ROOT"
    if (( MAX_STATIONS > 0 )); then
      printf ' --max-stations %q' "$MAX_STATIONS"
    fi
    printf ' --process-jobs %q' "$PROCESS_JOBS"
    printf '\n'
  fi
  if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
    printf '  %q --pride-summary %q\n' "$PRIDE_CLEANER" '<latest-pride-summary>'
  fi
  if [[ "$CLEANUP_OBS" == "1" ]]; then
    printf '  find %q -maxdepth 1 -type f <rinex-observation-patterns> -print -delete\n' "$OBS_DIR"
  fi
  printf '  python3 %q --event-time %q --expected-hours-each-side %q --out-tsv %q --out-json %q %s\n' \
    "$QUALITY_SCRIPT" "$EVENT_TIME_UTC" "$HOURS" "${REPORT_DIR}/kin-quality.tsv" "${REPORT_DIR}/kin-quality.json" '<kin-files-from-manifest>'
  printf '  python3 %q --workflow-summary %q --quality-json %q --db %q --normalized-root %q --include-warn\n' \
    "$NORMALIZER" "${REPORT_DIR}/workflow-summary.json" "${REPORT_DIR}/kin-quality.json" "$NORMALIZE_DB" "${PIPELINE_ROOT}/exports/normalized-ok-stations-us-nz"
  printf '  python3 %q --root %q --event-id %q --json-out %q\n' \
    "$VALIDATOR" "${PIPELINE_ROOT}/exports/normalized-ok-stations-us-nz" "$EVENT_ID" "${REPORT_DIR}/normalized-export-validation.json"
  if [[ "$SKIP_PLOT" == "0" ]]; then
    printf '  final normalized figures from %q after normalization\n' "${PIPELINE_ROOT}/scripts/plotting/plot_completed_normalized_event.py"
  fi
  exit 0
fi

mkdir -p "$DOWNLOAD_DIR" "$PRIDE_RUN_ROOT" "$LOG_DIR" "$MANIFEST_DIR" "$REPORT_DIR" "$OBS_DIR"
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
    | sort > "${MANIFEST_DIR}/obs-files.abs.txt"
  portable_manifest "${MANIFEST_DIR}/obs-files.abs.txt" "${MANIFEST_DIR}/obs-files.txt"
}

validate_obs_files() {
  local station=""
  local station_lc=""
  local match=""
  local size_bytes=""
  local status=""
  local reason=""
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
        status="INVALID"
        reason="file smaller than ${MIN_OBS_BYTES} bytes"
        invalid_count=$((invalid_count + 1))
      else
        status="OK"
        reason="ready"
        valid_count=$((valid_count + 1))
        portable_path "$match" >> "$valid_obs_file"
      fi
      printf '%s\t%s\t%s\t%s\t%s\n' "$station" "$(portable_path "$match")" "$size_bytes" "$status" "$reason"
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
    echo "Valid obs files already exist; reusing them. Use --force-download to download again."
    SKIP_DOWNLOAD="1"
    download_status="REUSED"
  fi
fi

if [[ "$SKIP_DOWNLOAD" == "0" ]]; then
  download_cmd=(
    "$DOWNLOADER"
    --year "$YEAR"
    --doy "$DOY"
    --event-id "$EVENT_ID"
    --sample-interval "01S"
    --out-dir "$DOWNLOAD_DIR"
    --obs-root "$OBS_ROOT"
  )
  if [[ -n "$STATIONS_FILE" ]]; then
    download_cmd+=(--stations-file "$STATIONS_FILE")
  fi
  if [[ -n "$VERIFIED_FILES_DB" ]]; then
    download_cmd+=(--verified-files-db "$VERIFIED_FILES_DB")
  fi
  download_cmd+=("${STATIONS[@]}")

  echo
  echo "Running download stage..."
  if "${download_cmd[@]}" > "${LOG_DIR}/download.log" 2>&1; then
    download_status="OK"
  else
    download_status="FAIL"
  fi
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
    while IFS= read -r obs_file; do
      [[ -z "$obs_file" ]] && continue
      resolve_path "$obs_file"
    done < "${MANIFEST_DIR}/valid-requested-obs-files.txt" > "$PROCESS_OBS_FILES"
  else
    cp -f "${MANIFEST_DIR}/obs-files.abs.txt" "$PROCESS_OBS_FILES"
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

latest_pride_summary="$(find "$PRIDE_RUN_ROOT" -type f -name 'event-window-summary.tsv' | sort | tail -n 1 || true)"
if [[ -n "$latest_pride_summary" && -f "$latest_pride_summary" ]]; then
  awk -F '\t' '
    $1 == "station" { seen_header = 1; next }
    seen_header && NF >= 4 && $3 == "OK" { print $4 }
  ' "$latest_pride_summary" \
    | while IFS= read -r station_run_dir; do
        resolved_station_run_dir="$(resolve_path "$station_run_dir")"
        [[ -d "$resolved_station_run_dir" ]] && find "$resolved_station_run_dir" -type f -name 'kin_*'
      done \
    | sort > "${MANIFEST_DIR}/kin-files.abs.txt"
else
  find "$PRIDE_RUN_ROOT" -type f -name 'kin_*' | sort > "${MANIFEST_DIR}/kin-files.abs.txt"
fi
portable_manifest "${MANIFEST_DIR}/kin-files.abs.txt" "${MANIFEST_DIR}/kin-files.txt"
kin_count="$(wc -l < "${MANIFEST_DIR}/kin-files.txt" | tr -d ' ')"
plot_count="0"

if [[ "$SKIP_PROCESS" == "1" && "$process_status" == "SKIPPED" && "$kin_count" != "0" ]]; then
  process_status="REUSED"
fi

plot_status="SKIPPED_DISABLED"
: > "${MANIFEST_DIR}/plot-files.txt"
plot_count="0"

cleanup_status="SKIPPED"
pride_cleanup_status="SKIPPED"
obs_cleanup_status="SKIPPED"
if [[ "$CLEANUP_DOWNLOADS" == "1" ]]; then
  if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ]]; then
    cleanup_status="SKIPPED_WORKFLOW_FAILED"
  elif (( kin_count < 1 )); then
    cleanup_status="SKIPPED_NO_KIN"
  else
    echo
    echo "Cleaning raw download intermediates after kin generation..."
    {
      find "$DOWNLOAD_DIR" -type f \( \
        -name '*.crx' -o -name '*.crx.gz' -o -name '*.d.Z' -o -name '*.d.gz' -o \
        -name '*.[0-9][0-9]d' -o -name '*.[0-9][0-9]o' -o -name '*.rnx' -o \
        -name '*.rnx.gz' -o -name '*.rnx.Z' -o -name '*.zip' -o -name '*.tar' -o \
        -name '*.tar.gz' -o -name '*.tmp' -o -name '*.part' \
      \) -print -delete
      find "$DOWNLOAD_DIR" -type d -empty -print -delete
    } > "${LOG_DIR}/cleanup-downloads.log" 2>&1 || true
    cleanup_status="OK"
  fi
fi

if [[ "$CLEANUP_PRIDE_WORKDIR" == "1" ]]; then
  if [[ "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ]]; then
    pride_cleanup_status="SKIPPED_WORKFLOW_FAILED"
  elif (( kin_count < 1 )); then
    pride_cleanup_status="SKIPPED_NO_KIN"
  elif [[ -z "$latest_pride_summary" || ! -f "$latest_pride_summary" ]]; then
    pride_cleanup_status="SKIPPED_NO_PRIDE_SUMMARY"
  else
    echo
    echo "Cleaning PRIDE workdir intermediates after kin generation..."
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
    echo "Cleaning canonical observation cache after kin generation..."
    if {
      find "$OBS_DIR" -maxdepth 1 -type f \( \
        -name '*.rnx' -o -name '*.obs' -o -name '*.[0-9][0-9]o' -o \
        -name '*.rnx.gz' -o -name '*.rnx.Z' -o -name '*.crx' -o -name '*.crx.gz' -o \
        -name '*.d.Z' -o -name '*.d.gz' -o -name '*.[0-9][0-9]d' \
      \) -print -delete
      find "$OBS_DIR" -maxdepth 1 -type d -empty -print -delete
    } > "${LOG_DIR}/cleanup-obs.log" 2>&1; then
      obs_cleanup_status="OK"
    else
      obs_cleanup_status="FAIL"
    fi
  fi
fi

KIN_QUALITY_TSV="${REPORT_DIR}/kin-quality.tsv"
KIN_QUALITY_JSON="${REPORT_DIR}/kin-quality.json"
python3 - "$WORKFLOW_JSON" "$EVENT_ID" "$EVENT_TIME_UTC" "$YEAR" "$DOY" "$WORKFLOW_DIR" "$DOWNLOAD_DIR" "$OBS_DIR" "$PRIDE_RUN_ROOT" "$LOG_DIR" "$MANIFEST_DIR" "$REPORT_DIR" "$latest_pride_summary" "${MANIFEST_DIR}/kin-files.txt" "$PIPELINE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

out, event_id, event_time, year, doy, workflow_dir, download_dir, obs_dir, pride_run_root, log_dir, manifest_dir, report_dir, pride_summary, kin_files, root = sys.argv[1:16]

def portable(path):
    if not path:
        return ""
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return str(path)
    return "@ROOT@" if str(rel) == "." else f"@ROOT@/{rel.as_posix()}"

def read_lines(path):
    return [line.strip() for line in Path(path).read_text().splitlines() if line.strip()] if Path(path).exists() else []
summary = {
    "event": {"id": event_id, "time_utc": event_time, "year": year, "doy": doy},
    "paths": {
        "root": "@ROOT@",
        "workflow_dir": portable(workflow_dir),
        "download_dir": portable(download_dir),
        "obs_dir": portable(obs_dir),
        "pride_run_root": portable(pride_run_root),
        "logs_dir": portable(log_dir),
        "manifests_dir": portable(manifest_dir),
        "reports_dir": portable(report_dir),
        "pride_summary": portable(pride_summary),
    },
    "files": {"kin": read_lines(kin_files)},
}
Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
PY
quality_expected_seconds=""
if (( kin_count == 0 )); then
  quality_status="SKIPPED_NO_KIN"
  printf 'station\tkin_file\tquality_status\tquality_flags\n' > "$KIN_QUALITY_TSV"
  python3 - "$KIN_QUALITY_JSON" <<'PY'
import json
import sys
from pathlib import Path

payload = {
    "summary": {
        "status": "SKIPPED_NO_KIN",
        "station_count": 0,
        "ok_station_count": 0,
        "warn_station_count": 0,
        "fail_station_count": 0,
    },
    "stations": [],
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
PY
else
  echo
  echo "Computing kin quality metrics..."
  mapfile -t kin_files < "${MANIFEST_DIR}/kin-files.abs.txt"
  if [[ -n "$latest_pride_summary" && -f "$latest_pride_summary" ]]; then
    quality_expected_seconds="$(python3 - "$latest_pride_summary" <<'PY'
import datetime as dt
import sys
from pathlib import Path

values = {}
for raw in Path(sys.argv[1]).read_text(errors="replace").splitlines():
    key, sep, value = raw.partition("\t")
    if sep and key in {"window_start_utc", "window_end_utc"}:
        values[key] = value.strip()

def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return dt.datetime.fromisoformat(text).astimezone(dt.timezone.utc)

try:
    start = parse_utc(values["window_start_utc"])
    end = parse_utc(values["window_end_utc"])
except (KeyError, ValueError):
    raise SystemExit(0)

seconds = (end - start).total_seconds()
if seconds > 0:
    print(f"{seconds:.3f}")
PY
)"
  fi
  quality_cmd=(
    python3 "$QUALITY_SCRIPT"
    --event-time "$EVENT_TIME_UTC"
    --expected-hours-each-side "$HOURS"
    --out-tsv "$KIN_QUALITY_TSV"
    --out-json "$KIN_QUALITY_JSON"
  )
  if [[ -n "$quality_expected_seconds" ]]; then
    quality_cmd+=(--expected-seconds "$quality_expected_seconds")
  fi
  if [[ "$ALLOW_PARTIAL" == "1" ]]; then
    quality_cmd+=(--allow-partial-failures)
  fi
  if "${quality_cmd[@]}" \
      "${kin_files[@]}" > "${LOG_DIR}/kin-quality.log" 2>&1; then
    :
  else
    :
  fi
  quality_status="$(python3 - "$KIN_QUALITY_JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("FAIL")
else:
    try:
        print(json.loads(path.read_text()).get("summary", {}).get("status") or "FAIL")
    except json.JSONDecodeError:
        print("FAIL")
PY
)"
fi

normalized_status="SKIPPED"
normalized_event_dir=""
normalized_station_count="0"
normalized_waveform_rows="0"
normalized_event_grade=""
normalized_azimuth_bins_covered="0"
FINAL_NORMALIZED_ROOT="${FINAL_NORMALIZED_ROOT:-${PIPELINE_ROOT}/exports/normalized-ok-stations-us-nz}"
NORMALIZED_VALIDATION_JSON="${REPORT_DIR}/normalized-export-validation.json"
normalized_validation_status="SKIPPED"
normalized_export_valid="false"
normalized_validation_errors=""
usable_kin="0"
if (( kin_count > 0 )) && [[ "$quality_status" != "FAIL" && "$quality_status" != "SKIPPED_NO_KIN" ]]; then
  usable_kin="1"
fi

if (( kin_count == 0 )); then
  normalized_status="SKIPPED_NO_KIN"
elif [[ "$quality_status" == "FAIL" ]]; then
  normalized_status="SKIPPED_QUALITY_FAIL"
elif [[ "$usable_kin" != "1" && ( "$download_status" == "FAIL" || "$process_status" == "FAIL" || "$process_status" == "BLOCKED_OBS_VALIDATION" ) ]]; then
  normalized_status="SKIPPED_WORKFLOW_FAILED"
else
  echo
  echo "Normalizing PRIDE kin results..."
  NORMALIZE_RESULT="${REPORT_DIR}/normalize-pride-kin.json"
  if python3 "$NORMALIZER" \
      --workflow-summary "$WORKFLOW_JSON" \
      --quality-json "$KIN_QUALITY_JSON" \
      --db "$NORMALIZE_DB" \
      --normalized-root "$FINAL_NORMALIZED_ROOT" \
      --include-warn \
      > "$NORMALIZE_RESULT" 2> "${LOG_DIR}/normalize-pride-kin.log"; then
    normalized_status="OK"
    normalized_event_dir="$(python3 - "$NORMALIZE_RESULT" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get("normalized_event_dir", ""))
PY
)"
    normalized_station_count="$(python3 - "$NORMALIZE_RESULT" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get("normalized_station_count", 0))
PY
)"
    normalized_waveform_rows="$(python3 - "$NORMALIZE_RESULT" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get("normalized_waveform_rows", 0))
PY
)"
    normalized_event_grade="$(python3 - "$NORMALIZE_RESULT" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get("event_grade", ""))
PY
)"
    normalized_azimuth_bins_covered="$(python3 - "$NORMALIZE_RESULT" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
print(payload.get("azimuth_bins_covered", 0))
PY
)"
    echo "Validating normalized export package..."
    if python3 "$VALIDATOR" \
        --root "$FINAL_NORMALIZED_ROOT" \
        --event-id "$EVENT_ID" \
        --json-out "$NORMALIZED_VALIDATION_JSON" \
        > "${LOG_DIR}/normalized-export-validation.log" 2>&1; then
      normalized_validation_status="OK"
      normalized_export_valid="true"
    else
      normalized_validation_status="FAIL"
      normalized_export_valid="false"
      echo "Normalized export validation failed. See ${LOG_DIR}/normalized-export-validation.log" >&2
    fi
    normalized_validation_errors="$(python3 - "$NORMALIZED_VALIDATION_JSON" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    print("")
else:
    try:
        print(json.loads(path.read_text()).get("error_count", ""))
    except json.JSONDecodeError:
        print("")
PY
)"
  else
    normalized_status="FAIL"
    echo "Normalizing PRIDE kin results failed. See ${LOG_DIR}/normalize-pride-kin.log" >&2
  fi
fi

workflow_end_epoch="$(date -u +%s)"
duration_seconds=$((workflow_end_epoch - workflow_start_epoch))

{
  printf 'key\tvalue\n'
  printf 'event_id\t%s\n' "$EVENT_ID"
  printf 'event_time_utc\t%s\n' "$EVENT_TIME_UTC"
  printf 'year\t%s\n' "$YEAR"
  printf 'doy\t%s\n' "$DOY"
  printf 'hours_each_side\t%s\n' "$HOURS"
  printf 'interval_seconds\t%s\n' "$INTERVAL"
  printf 'process_jobs\t%s\n' "$PROCESS_JOBS"
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
  printf 'normalized_status\t%s\n' "$normalized_status"
  printf 'normalized_event_dir\t%s\n' "$(portable_path "$normalized_event_dir")"
  printf 'normalized_station_count\t%s\n' "$normalized_station_count"
  printf 'normalized_waveform_rows\t%s\n' "$normalized_waveform_rows"
  printf 'normalized_event_grade\t%s\n' "$normalized_event_grade"
  printf 'normalized_azimuth_bins_covered\t%s\n' "$normalized_azimuth_bins_covered"
  printf 'normalized_validation_status\t%s\n' "$normalized_validation_status"
  printf 'normalized_export_valid\t%s\n' "$normalized_export_valid"
  printf 'normalized_validation_errors\t%s\n' "$normalized_validation_errors"
  printf 'normalized_validation_json\t%s\n' "$(portable_path "$NORMALIZED_VALIDATION_JSON")"
  printf 'workflow_dir\t%s\n' "$(portable_path "$WORKFLOW_DIR")"
  printf 'download_dir\t%s\n' "$(portable_path "$DOWNLOAD_DIR")"
  printf 'obs_dir\t%s\n' "$(portable_path "$OBS_DIR")"
  printf 'pride_run_root\t%s\n' "$(portable_path "$PRIDE_RUN_ROOT")"
  printf 'kin_quality_tsv\t%s\n' "$(portable_path "$KIN_QUALITY_TSV")"
  printf 'kin_quality_json\t%s\n' "$(portable_path "$KIN_QUALITY_JSON")"
  printf 'pride_summary\t%s\n' "$(portable_path "$latest_pride_summary")"
} > "${REPORT_DIR}/workflow-summary.tsv"

WORKFLOW_JSON="${REPORT_DIR}/workflow-summary.json"
export EVENT_ID EVENT_TIME_UTC YEAR DOY HOURS INTERVAL PROCESS_JOBS download_status process_status plot_status quality_status obs_validation_status cleanup_status pride_cleanup_status obs_cleanup_status normalized_status normalized_event_dir normalized_station_count normalized_waveform_rows normalized_event_grade normalized_azimuth_bins_covered normalized_validation_status normalized_export_valid normalized_validation_errors duration_seconds
export WORKFLOW_DIR DOWNLOAD_DIR OBS_DIR PRIDE_RUN_ROOT LOG_DIR MANIFEST_DIR REPORT_DIR latest_pride_summary
export PIPELINE_ROOT
export OBS_VALIDATION_FILE="${MANIFEST_DIR}/obs-validation.tsv"
export OBS_FILES_FILE="${MANIFEST_DIR}/obs-files.txt"
export KIN_FILES_FILE="${MANIFEST_DIR}/kin-files.txt"
export PLOT_FILES_FILE="${MANIFEST_DIR}/plot-files.txt"
export PRIDE_SUMMARY_FILE="$latest_pride_summary"
export KIN_QUALITY_TSV KIN_QUALITY_JSON
export NORMALIZED_VALIDATION_JSON
export REQUESTED_STATION_COUNT="${#STATIONS[@]}"
export OBS_COUNT="$obs_count"
export KIN_COUNT="$kin_count"
export PLOT_COUNT="$plot_count"

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


ROOT = Path(os.environ["PIPELINE_ROOT"]).resolve()


def portable(path):
    if not path:
        return ""
    try:
        rel = Path(path).resolve().relative_to(ROOT)
    except ValueError:
        return str(path)
    return "@ROOT@" if str(rel) == "." else f"@ROOT@/{rel.as_posix()}"


def read_tsv_dicts(path):
    if not path or not Path(path).exists():
        return []
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_pride_summary(path):
    rows = []
    if not path or not Path(path).exists():
        return rows
    station_header_seen = False
    with Path(path).open(newline="") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("station\t"):
                station_header_seen = True
                continue
            if not station_header_seen:
                continue
            parts = line.split("\t")
            if len(parts) >= 4:
                rows.append({
                    "station": parts[0],
                    "obs_file": parts[1],
                    "status": parts[2],
                    "station_run_dir": parts[3],
                })
    return rows


def read_json(path):
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text())
    except json.JSONDecodeError:
        return {}


def portable_value(value):
    if isinstance(value, dict):
        return {key: portable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_value(item) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return portable(value)
    return value


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


summary = {
    "event": {
        "id": os.environ["EVENT_ID"],
        "time_utc": os.environ["EVENT_TIME_UTC"],
        "year": os.environ["YEAR"],
        "doy": os.environ["DOY"],
    },
    "parameters": {
        "process_window_hours_each_side": as_int(os.environ["HOURS"]),
        "interval_seconds": as_int(os.environ["INTERVAL"]),
        "process_jobs": as_int(os.environ["PROCESS_JOBS"]),
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
        "normalized": os.environ["normalized_status"],
        "normalized_validation": os.environ["normalized_validation_status"],
        "normalized_export_valid": os.environ["normalized_export_valid"] == "true",
    },
    "counts": {
        "requested_stations": as_int(os.environ["REQUESTED_STATION_COUNT"]),
        "obs_files": as_int(os.environ["OBS_COUNT"]),
        "kin_files": as_int(os.environ["KIN_COUNT"]),
        "plot_files": as_int(os.environ["PLOT_COUNT"]),
        "normalized_stations": as_int(os.environ["normalized_station_count"]),
        "normalized_waveform_rows": as_int(os.environ["normalized_waveform_rows"]),
        "normalized_azimuth_bins_covered": as_int(os.environ["normalized_azimuth_bins_covered"]),
        "normalized_validation_errors": as_int(os.environ["normalized_validation_errors"]),
    },
    "duration_seconds": as_int(os.environ["duration_seconds"]),
    "paths": {
        "root": "@ROOT@",
        "workflow_dir": portable(os.environ["WORKFLOW_DIR"]),
        "download_dir": portable(os.environ["DOWNLOAD_DIR"]),
        "obs_dir": portable(os.environ["OBS_DIR"]),
        "pride_run_root": portable(os.environ["PRIDE_RUN_ROOT"]),
        "logs_dir": portable(os.environ["LOG_DIR"]),
        "manifests_dir": portable(os.environ["MANIFEST_DIR"]),
        "reports_dir": portable(os.environ["REPORT_DIR"]),
        "kin_quality_tsv": portable(os.environ["KIN_QUALITY_TSV"]),
        "kin_quality_json": portable(os.environ["KIN_QUALITY_JSON"]),
        "pride_summary": portable(os.environ.get("latest_pride_summary", "")),
        "normalized_event_dir": portable(os.environ["normalized_event_dir"]),
        "normalized_event_grade": os.environ["normalized_event_grade"],
        "normalized_validation_json": portable(os.environ.get("NORMALIZED_VALIDATION_JSON", "")),
    },
    "obs_validation": read_tsv_dicts(os.environ.get("OBS_VALIDATION_FILE")),
    "pride_stations": read_pride_summary(os.environ.get("PRIDE_SUMMARY_FILE")),
    "quality": portable_value(read_json(os.environ.get("KIN_QUALITY_JSON"))),
    "files": {
        "obs": read_lines(os.environ.get("OBS_FILES_FILE")),
        "kin": read_lines(os.environ.get("KIN_FILES_FILE")),
        "plots": read_lines(os.environ.get("PLOT_FILES_FILE")),
    },
}

Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
PY

{
  printf '# 1Hz GNSS + PRIDE Workflow Summary\n\n'
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
  printf '%s\n' "- Normalized status: \`${normalized_status}\`"
  printf '%s\n' "- Normalized stations: \`${normalized_station_count}\`"
  printf '%s\n' "- Normalized waveform rows: \`${normalized_waveform_rows}\`"
  printf '%s\n' "- Normalized event grade: \`${normalized_event_grade}\`"
  printf '%s\n' "- Normalized azimuth bins covered: \`${normalized_azimuth_bins_covered}\`"
  printf '%s\n' "- Normalized validation: \`${normalized_validation_status}\`"
  printf '%s\n' "- Normalized export valid: \`${normalized_export_valid}\`"
  printf '%s\n' "- Normalized validation errors: \`${normalized_validation_errors}\`"
  printf '%s\n' "- Obs cleanup status: \`${obs_cleanup_status}\`"
  printf '%s\n' "- Duration seconds: \`${duration_seconds}\`"
  printf '%s\n' "- Requested stations: \`${#STATIONS[@]}\`"
  printf '%s\n' "- Observation files: \`${obs_count}\`"
  printf '%s\n\n' "- Kinematic files: \`${kin_count}\`"
  printf '%s\n\n' "- Plot files: \`${plot_count}\`"
  printf '## Paths\n\n'
  printf '%s\n' "- Workflow directory: \`$(portable_path "$WORKFLOW_DIR")\`"
  printf '%s\n' "- Download products: \`$(portable_path "$DOWNLOAD_DIR")\`"
  printf '%s\n' "- Canonical obs files: \`$(portable_path "$OBS_DIR")\`"
  printf '%s\n' "- PRIDE runs: \`$(portable_path "$PRIDE_RUN_ROOT")\`"
  printf '%s\n' "- Logs: \`$(portable_path "$LOG_DIR")\`"
  printf '%s\n' "- Manifests: \`$(portable_path "$MANIFEST_DIR")\`"
  printf '%s\n' "- Normalized event: \`$(portable_path "$normalized_event_dir")\`"
  printf '%s\n' "- Normalized validation JSON: \`$(portable_path "$NORMALIZED_VALIDATION_JSON")\`"
  printf '%s\n' "- Kin quality TSV: \`$(portable_path "$KIN_QUALITY_TSV")\`"
  printf '%s\n' "- Kin quality JSON: \`$(portable_path "$KIN_QUALITY_JSON")\`"
  printf '%s\n' "- Reports: \`$(portable_path "$REPORT_DIR")\`"
  printf '%s\n' "- JSON summary: \`$(portable_path "$WORKFLOW_JSON")\`"
  if [[ -n "$latest_pride_summary" ]]; then
    printf '%s\n' "- PRIDE event summary: \`$(portable_path "$latest_pride_summary")\`"
  fi
} > "${REPORT_DIR}/workflow-summary.md"

echo
echo "Workflow summary: ${REPORT_DIR}/workflow-summary.md"
echo "JSON summary: ${WORKFLOW_JSON}"
echo "Machine-readable summary: ${REPORT_DIR}/workflow-summary.tsv"

final_plot_status="SKIPPED"
if [[ "$SKIP_PLOT" == "0" && "$usable_kin" == "1" && "$normalized_status" == "OK" && "$normalized_validation_status" == "OK" ]]; then
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
  python3 "${PIPELINE_ROOT}/scripts/workflows/update_workflow_summary_status.py" \
    --extract-plot-files-from-log "${LOG_DIR}/plot-final-normalized.log" \
    --write-plot-files "${MANIFEST_DIR}/plot-files.txt"
  python3 "${PIPELINE_ROOT}/scripts/workflows/update_workflow_summary_status.py" \
    --summary-json "$WORKFLOW_JSON" \
    --summary-tsv "${REPORT_DIR}/workflow-summary.tsv" \
    --summary-md "${REPORT_DIR}/workflow-summary.md" \
    --plot-status "$final_plot_status" \
    --plot-files "${MANIFEST_DIR}/plot-files.txt"
fi

python3 "${PIPELINE_ROOT}/scripts/workflows/update_workflow_summary_status.py" \
  --summary-json "$WORKFLOW_JSON" \
  --summary-tsv "${REPORT_DIR}/workflow-summary.tsv" \
  --summary-md "${REPORT_DIR}/workflow-summary.md" \
  --derive-failure

if [[ "$usable_kin" != "1" || "$pride_cleanup_status" == "FAIL" || "$obs_cleanup_status" == "FAIL" || "$normalized_status" == "FAIL" || "$normalized_validation_status" == "FAIL" || "$final_plot_status" == "FAIL" ]]; then
  exit 1
fi
