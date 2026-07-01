#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  cleanup_pride_workdir.sh --pride-summary FILE [--dry-run]

Removes bulky PRIDE station workdir files that are reproducible after a
completed workflow:
  - copied RINEX observation files in each station run directory
  - broadcast ephemeris files copied into station directories
  - downloaded PRIDE product directories
  - large intermediate files such as res_*, amb_*, ztd_*, and SP3 files

Keeps event summaries, station status files, pdp3.log, and kin_* results.
EOF
}

PRIDE_SUMMARY=""
DRY_RUN="0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pride-summary)
      PRIDE_SUMMARY="$2"
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

if [[ -z "$PRIDE_SUMMARY" || ! -f "$PRIDE_SUMMARY" ]]; then
  echo "PRIDE summary not found: ${PRIDE_SUMMARY}" >&2
  exit 1
fi

delete_path() {
  local path="$1"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY_RUN\t%s\n' "$path"
    return
  fi
  if [[ -e "$path" || -L "$path" ]]; then
    printf 'DELETE\t%s\n' "$path"
    rm -rf -- "$path"
  fi
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

cleanup_station_dir() {
  local station_dir="$1"
  local obs_file="$2"
  local obs_name=""

  if [[ -z "$station_dir" || ! -d "$station_dir" ]]; then
    return
  fi

  obs_name="$(basename "$obs_file")"
  if [[ -n "$obs_name" && -f "${station_dir}/${obs_name}" ]]; then
    delete_path "${station_dir}/${obs_name}"
  fi

  find "$station_dir" -maxdepth 1 -type f \( \
      -name 'brdm*.??p' -o -name 'BRDM*.??P' \
    \) -print0 \
    | while IFS= read -r -d '' file; do
        delete_path "$file"
      done

  find "$station_dir" -mindepth 2 -type f \( \
      -name 'res_*' -o -name 'amb_*' -o -name 'att_*' -o -name 'cst_*' -o \
      -name 'fcb_*' -o -name 'log_*' -o -name 'neq_*' -o -name 'orb_*' -o \
      -name 'otl_*' -o -name 'rck_*' -o -name 'sck_*' -o -name 'stt_*' -o \
      -name 'ztd_*' -o -name 'igserp' -o -name 'sat_parameters' -o \
      -name 'leap.sec' -o -name 'abs_igs.atx' -o -name '*.SP3' -o \
      -name '*.CLK' -o -name '*.ERP' -o -name '*.BIA' -o -name '*.OBX' -o \
      -name '*.gz' -o -name 'config.*' \
    \) -print0 \
    | while IFS= read -r -d '' file; do
        case "$(basename "$file")" in
          kin_*) continue ;;
        esac
        delete_path "$file"
      done

  find "$station_dir" -mindepth 2 -type d -name product -print0 \
    | while IFS= read -r -d '' dir; do
        delete_path "$dir"
      done

  if [[ "$DRY_RUN" == "0" ]]; then
    find "$station_dir" -depth -type d -empty -print -delete
  fi
}

awk -F '\t' '
  $1 == "station" { seen_header = 1; next }
  seen_header && NF >= 4 && $3 == "OK" { print $2 "\t" $4 }
' "$PRIDE_SUMMARY" \
  | while IFS=$'\t' read -r obs_file station_run_dir; do
      cleanup_station_dir "$(resolve_path "$station_run_dir")" "$(resolve_path "$obs_file")"
    done
