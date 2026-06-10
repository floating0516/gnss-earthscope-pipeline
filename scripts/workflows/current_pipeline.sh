#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DB="${PIPELINE_ROOT}/data/earthscope_availability/earthscope_1hz.sqlite"
METADATA_ROOT="${PIPELINE_ROOT}/data/earthscope_metadata"
BATCH_ROOT="${PIPELINE_ROOT}/data/batches"
OBS_ROOT="${PIPELINE_ROOT}/data/obs"
RUN_ROOT="${PIPELINE_ROOT}/runs"

usage() {
  cat <<EOF
Usage:
  current_pipeline.sh paths
  current_pipeline.sh list-events
  current_pipeline.sh sync-existing-labels [--reset] [--dry-run]
  current_pipeline.sh export-batch --event-id ID [--radius-km KM] [--output FILE] [--include-existing]
  current_pipeline.sh run-batch --csv FILE [workflow options]
  current_pipeline.sh update-availability [update options]
  current_pipeline.sh rebuild-candidates [--event-id ID] [--dry-run]
  current_pipeline.sh refresh-verified-files [--missing-only] [--event-id ID] [--dry-run]

This wrapper is the isolated EarthScope pipeline entry point.
It always uses:
  DB:            ${DB}
  metadata root: ${METADATA_ROOT}
  obs root:      ${OBS_ROOT}
  run root:      ${RUN_ROOT}

It must not use legacy local inventories under the collector repo data/gnss_data
or data/velocity_data directories for station selection.
EOF
}

require_db() {
  if [[ ! -f "${DB}" ]]; then
    echo "Missing availability DB: ${DB}" >&2
    exit 1
  fi
}

cmd_paths() {
  cat <<EOF
PIPELINE_ROOT=${PIPELINE_ROOT}
DB=${DB}
METADATA_ROOT=${METADATA_ROOT}
BATCH_ROOT=${BATCH_ROOT}
OBS_ROOT=${OBS_ROOT}
RUN_ROOT=${RUN_ROOT}
EOF
}

cmd_list_events() {
  require_db
  python3 - "${DB}" <<'PY'
import sqlite3
import sys

db = sys.argv[1]
conn = sqlite3.connect(db)
rows = conn.execute(
    """
    SELECT
      e.event_id,
      e.magnitude,
      e.event_date,
      COALESCE(e.place, ''),
      COALESCE(SUM(CASE WHEN c.radius_km = 200 THEN 1 ELSE 0 END), 0) AS stations_200km,
      COALESCE(SUM(CASE WHEN c.radius_km = 300 THEN 1 ELSE 0 END), 0) AS stations_300km,
      COALESCE(e.existing_data_status, '') AS existing_data_status,
      COALESCE(e.existing_station_count, 0) AS existing_station_count
    FROM usgs_m6plus_events_usa e
    LEFT JOIN event_earthscope_station_candidates c
      ON c.event_id = e.event_id
     AND c.radius_km IN (200, 300)
    GROUP BY e.event_id
    ORDER BY e.magnitude DESC, e.event_date DESC
    """
).fetchall()

print("event_id\tmagnitude\tevent_date\tplace\tstations_200km\tstations_300km\texisting_data_status\texisting_station_count")
for row in rows:
    print("\t".join(str(value) for value in row))
PY
}

cmd_export_batch() {
  require_db
  local event_id=""
  local radius_km="200"
  local output=""
  local include_existing="0"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --event-id)
        event_id="$2"
        shift 2
        ;;
      --radius-km)
        radius_km="$2"
        shift 2
        ;;
      --output)
        output="$2"
        shift 2
        ;;
      --include-existing)
        include_existing="1"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown export-batch option: $1" >&2
        exit 1
        ;;
    esac
  done

  if [[ -z "${event_id}" ]]; then
    echo "export-batch requires --event-id" >&2
    exit 1
  fi
  if [[ -z "${output}" ]]; then
    output="${BATCH_ROOT}/${event_id}-${radius_km}km.csv"
  fi

  mkdir -p "$(dirname "${output}")"
  python3 - "${DB}" "${event_id}" "${radius_km}" "${output}" "${include_existing}" <<'PY'
import csv
import sqlite3
import sys

db, event_id, radius_km, output, include_existing = sys.argv[1:6]
conn = sqlite3.connect(db)
event = conn.execute(
    """
    SELECT event_id, time_utc, COALESCE(existing_data_status, '')
    FROM usgs_m6plus_events_usa
    WHERE event_id = ?
    """,
    (event_id,),
).fetchone()
if event is None:
    raise SystemExit(f"event not found in usgs_m6plus_events_usa: {event_id}")
if event[2] and include_existing != "1":
    raise SystemExit(
        f"event already has normalized data ({event[2]}): {event_id}; "
        "use --include-existing to export it anyway"
    )

stations = [
    row[0]
    for row in conn.execute(
        """
        SELECT station
        FROM event_earthscope_station_candidates
        WHERE event_id = ? AND radius_km = ?
        ORDER BY distance_km, station
        """,
        (event_id, float(radius_km)),
    )
]
if not stations:
    raise SystemExit(f"no EarthScope same-day candidates for {event_id} within {radius_km} km")

with open(output, "w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["event_id", "event_time", "stations", "status"], lineterminator="\n")
    writer.writeheader()
    writer.writerow(
        {
            "event_id": event[0],
            "event_time": event[1],
            "stations": " ".join(stations),
            "status": "",
        }
    )

print(output)
print(f"stations={len(stations)}")
PY
}

cmd_run_batch() {
  mkdir -p "${OBS_ROOT}" "${RUN_ROOT}" "${BATCH_ROOT}"
  "${PIPELINE_ROOT}/scripts/workflows/run_event_batch_workflow.sh" \
    --run-root "${RUN_ROOT}" \
    --obs-root "${OBS_ROOT}" \
    --existing-db "${DB}" \
    "$@"
}

cmd_update_availability() {
  mkdir -p "$(dirname "${DB}")"
  python3 "${PIPELINE_ROOT}/scripts/availability/update_earthscope_availability.py" \
    --db "${DB}" \
    "$@"
}

cmd_rebuild_candidates() {
  require_db
  python3 "${PIPELINE_ROOT}/scripts/availability/rebuild_event_station_candidates.py" \
    --db "${DB}" \
    --metadata-root "${METADATA_ROOT}" \
    "$@"
}

cmd_refresh_verified_files() {
  require_db
  python3 "${PIPELINE_ROOT}/scripts/availability/refresh_event_station_verified_files.py" \
    --db "${DB}" \
    "$@"
}

cmd_sync_existing_labels() {
  require_db
  python3 "${PIPELINE_ROOT}/scripts/normalize/sync_normalized_existing_labels.py" \
    --db "${DB}" \
    "$@"
}

main() {
  local command="${1:-}"
  if [[ -z "${command}" ]]; then
    usage
    exit 1
  fi
  shift

  case "${command}" in
    paths)
      cmd_paths "$@"
      ;;
    list-events)
      cmd_list_events "$@"
      ;;
    sync-existing-labels)
      cmd_sync_existing_labels "$@"
      ;;
    export-batch)
      cmd_export_batch "$@"
      ;;
    run-batch)
      cmd_run_batch "$@"
      ;;
    update-availability)
      cmd_update_availability "$@"
      ;;
    rebuild-candidates)
      cmd_rebuild_candidates "$@"
      ;;
    refresh-verified-files)
      cmd_refresh_verified_files "$@"
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown command: ${command}" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
