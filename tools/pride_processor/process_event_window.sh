#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  process_event_window.sh --event-id EVENT --event-time UTC_TIME [options] [obs-file ...]

Options:
  --event-time UTC_TIME   Event time in UTC, e.g. 2021-10-11T09:10:25Z
  --event-id EVENT        Event id used for output naming
  --obs-dir DIR           Directory containing RINEX obs files
                           default: <pipeline-root>/data/obs/<event-id>
  --run-root DIR          Root for PRIDE run directories
                           default: ./runs
  --hours N               Hours before/after event time, default: 3
  --interval N            PRIDE processing interval in seconds, default: 1
  --max-stations N        Process at most N obs files after sorting
  --process-jobs N        Number of station PRIDE jobs to run concurrently, default: 1
  --dry-run               Print planned commands without running pdp3
  -h, --help              Show this help

Window rule:
  Use event_time +/- hours. If the window crosses the observation day boundary,
  truncate to that day's 00:00:00 or 23:59:59 UTC.
EOF
}

EVENT_ID=""
EVENT_TIME=""
OBS_DIR=""
RUN_ROOT=""
HOURS="3"
INTERVAL="1"
MAX_STATIONS="0"
PROCESS_JOBS="1"
DRY_RUN="0"
declare -a OBS_FILES=()

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
    --obs-dir)
      OBS_DIR="$2"
      shift 2
      ;;
    --run-root)
      RUN_ROOT="$2"
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
      OBS_FILES+=("$1")
      shift
      ;;
  esac
done

for obs in "$@"; do
  OBS_FILES+=("$obs")
done

if [[ -z "$EVENT_ID" || -z "$EVENT_TIME" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "$OBS_DIR" ]]; then
  PIPELINE_ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  OBS_DIR="${GNSS_EQ_OBS_ROOT:-${PIPELINE_ROOT_DEFAULT}/data/obs}/${EVENT_ID}"
fi

if [[ -z "$RUN_ROOT" ]]; then
  RUN_ROOT="$(pwd)/runs"
fi

if ! command -v pdp3 >/dev/null 2>&1 && [[ -n "${PRIDE_BIN_DIR:-}" ]]; then
  export PATH="${PRIDE_BIN_DIR}:${PATH}"
fi

if ! command -v pdp3 >/dev/null 2>&1; then
  echo "Missing required command: pdp3" >&2
  exit 1
fi

event_epoch="$(date -u -d "$EVENT_TIME" +%s)"
event_day="$(date -u -d "@${event_epoch}" +%F)"
event_day_start="$(date -u -d "${event_day} 00:00:00Z" +%s)"
event_day_end="$(date -u -d "${event_day} 23:59:59Z" +%s)"
window_seconds="$(python3 - "$HOURS" <<'PY'
import math
import sys

try:
    hours = float(sys.argv[1])
except ValueError:
    raise SystemExit("--hours must be numeric")
if not math.isfinite(hours) or hours < 0:
    raise SystemExit("--hours must be a non-negative number")
print(int(round(hours * 3600.0)))
PY
)"
start_epoch=$((event_epoch - window_seconds))
end_epoch=$((event_epoch + window_seconds))

if (( start_epoch < event_day_start )); then
  start_epoch="$event_day_start"
fi

if (( end_epoch > event_day_end )); then
  end_epoch="$event_day_end"
fi

start_date="$(date -u -d "@${start_epoch}" +%Y/%m/%d)"
start_time="$(date -u -d "@${start_epoch}" +%H:%M:%S)"
end_date="$(date -u -d "@${end_epoch}" +%Y/%m/%d)"
end_time="$(date -u -d "@${end_epoch}" +%H:%M:%S)"
window_tag="$(date -u -d "@${start_epoch}" +%Y%m%dT%H%M%S)-$(date -u -d "@${end_epoch}" +%H%M%S)"

if (( ${#OBS_FILES[@]} == 0 )); then
  if [[ ! -d "$OBS_DIR" ]]; then
    echo "Observation directory not found: $OBS_DIR" >&2
    exit 1
  fi
  while IFS= read -r file; do
    OBS_FILES+=("$file")
  done < <(find "$OBS_DIR" -maxdepth 1 -type f \( -name "*.rnx" -o -name "*.[0-9][0-9]o" -o -name "*.obs" \) | sort)
fi

if (( ${#OBS_FILES[@]} == 0 )); then
  echo "No observation files found." >&2
  exit 1
fi

if (( MAX_STATIONS > 0 && ${#OBS_FILES[@]} > MAX_STATIONS )); then
  OBS_FILES=("${OBS_FILES[@]:0:MAX_STATIONS}")
fi

if ! [[ "$PROCESS_JOBS" =~ ^[0-9]+$ ]] || (( PROCESS_JOBS < 1 )); then
  echo "--process-jobs must be a positive integer" >&2
  exit 1
fi

run_dir="${RUN_ROOT}/${EVENT_ID}-pdp3-${HOURS}h-${window_tag}"
summary_file="${run_dir}/event-window-summary.tsv"
status_dir="${run_dir}/.station-status"

if [[ "$DRY_RUN" == "0" ]]; then
  mkdir -p "$run_dir" "$status_dir"
  {
    printf 'event_id\t%s\n' "$EVENT_ID"
    printf 'event_time_utc\t%s\n' "$(date -u -d "@${event_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
    printf 'window_start_utc\t%s\n' "$(date -u -d "@${start_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
    printf 'window_end_utc\t%s\n' "$(date -u -d "@${end_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
    printf 'hours_each_side\t%s\n' "$HOURS"
    printf 'interval_seconds\t%s\n' "$INTERVAL"
    printf 'run_dir\t%s\n' "$run_dir"
    printf 'station\tobs_file\tstatus\tstation_run_dir\n'
  } > "$summary_file"
fi

echo "Event: ${EVENT_ID}"
echo "Event time UTC: $(date -u -d "@${event_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
echo "Processing window UTC: $(date -u -d "@${start_epoch}" +%Y-%m-%dT%H:%M:%SZ) -> $(date -u -d "@${end_epoch}" +%Y-%m-%dT%H:%M:%SZ)"
echo "Run dir: ${run_dir}"
echo "Station process jobs: ${PROCESS_JOBS}"

process_one_obs() {
  local obs="$1"
  local obs_path=""
  local obs_name=""
  local station=""
  local station_dir=""
  local status_file=""

  obs_path="$(readlink -f "$obs")"
  obs_name="$(basename "$obs_path")"
  station="${obs_name:0:4}"
  station="${station,,}"
  station_dir="${run_dir}/${station}"
  status_file="${status_dir}/${station}.tsv"

  echo "== ${station} =="
  echo "pdp3 -s ${start_date} ${start_time} -e ${end_date} ${end_time} -i ${INTERVAL} ${obs_name}"

  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi

  mkdir -p "$station_dir"

  if [[ -f "$status_file" ]] && awk -F '\t' 'NF >= 3 && $3 == "OK" { found = 1 } END { exit found ? 0 : 1 }' "$status_file" \
      && find "$station_dir" -type f -name 'kin_*' -print -quit | grep -q .; then
    echo "Existing OK kin found for ${station}; skipping pdp3."
    return 0
  fi

  cp -f "$obs_path" "$station_dir/"

  if (
    cd "$station_dir"
    pdp3 -s "$start_date" "$start_time" -e "$end_date" "$end_time" -i "$INTERVAL" "$obs_name"
  ) >"${station_dir}/pdp3.log" 2>&1 && find "$station_dir" -type f -name 'kin_*' -print -quit | grep -q .; then
    printf '%s\t%s\t%s\t%s\n' "$station" "$obs_path" "OK" "$station_dir" > "$status_file"
  else
    printf '%s\t%s\t%s\t%s\n' "$station" "$obs_path" "FAIL" "$station_dir" > "$status_file"
  fi
}

for obs in "${OBS_FILES[@]}"; do
  if [[ "$DRY_RUN" == "1" ]]; then
    process_one_obs "$obs"
    continue
  fi

  while (( "$(jobs -pr | wc -l)" >= PROCESS_JOBS )); do
    wait -n || true
  done
  process_one_obs "$obs" &
done

if [[ "$DRY_RUN" == "0" ]]; then
  wait || true
  find "$status_dir" -maxdepth 1 -type f -name '*.tsv' -print0 \
    | sort -z \
    | xargs -0 --no-run-if-empty cat >> "$summary_file"
  echo "Summary: ${summary_file}"
  if find "$status_dir" -maxdepth 1 -type f -name '*.tsv' -print0 \
      | xargs -0 --no-run-if-empty awk -F '\t' 'NF >= 3 && $3 != "OK" { found = 1 } END { exit found ? 0 : 1 }'; then
    exit 1
  fi
fi
