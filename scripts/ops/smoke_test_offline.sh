#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

EVENT_ID="offline-smoke"
EVENT_TIME="2020-01-01T00:01:00Z"
KIN_FILE="${WORKDIR}/kin_2020001_smok"
DB="${WORKDIR}/events.sqlite"
WORKFLOW_ROOT="${WORKDIR}/workflow"
REPORT_DIR="${WORKFLOW_ROOT}/reports"
EXPORT_ROOT="${WORKDIR}/normalized"
QUALITY_JSON="${REPORT_DIR}/kin-quality.json"
SUMMARY_JSON="${REPORT_DIR}/workflow-summary.json"

mkdir -p "$REPORT_DIR"

python3 - "$KIN_FILE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("w", encoding="utf-8") as handle:
    handle.write("END OF HEADER\n")
    for sod in range(18, 138):
        handle.write(f"58849 {sod} 1000.0 2000.0 3000.0\n")
PY

python3 - "$DB" <<'PY'
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1])
conn = sqlite3.connect(db)
conn.execute(
    """
    CREATE TABLE usgs_m6plus_events_usa (
        event_id TEXT PRIMARY KEY,
        title TEXT,
        time_utc TEXT,
        event_date TEXT,
        magnitude REAL,
        longitude REAL,
        latitude REAL,
        depth_km REAL,
        place TEXT,
        usgs_url TEXT
    )
    """
)
conn.execute(
    """
    CREATE TABLE event_earthscope_station_verified_files (
        event_id TEXT,
        station TEXT,
        station_latitude REAL,
        station_longitude REAL,
        distance_km REAL
    )
    """
)
conn.execute(
    """
    CREATE TABLE event_earthscope_station_candidates (
        event_id TEXT,
        station TEXT,
        station_latitude REAL,
        station_longitude REAL,
        distance_km REAL
    )
    """
)
conn.execute(
    """
    INSERT INTO usgs_m6plus_events_usa
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        "offline-smoke",
        "Offline smoke event",
        "2020-01-01T00:01:00Z",
        "2020-01-01",
        6.0,
        -120.0,
        35.0,
        10.0,
        "Offline test",
        "",
    ),
)
conn.execute(
    """
    INSERT INTO event_earthscope_station_candidates
    VALUES (?, ?, ?, ?, ?)
    """,
    ("offline-smoke", "SMOK", 35.1, -120.1, 15.0),
)
conn.commit()
conn.close()
PY

python3 - "$SUMMARY_JSON" "$KIN_FILE" <<'PY'
import json
import sys
from pathlib import Path

summary = Path(sys.argv[1])
kin = Path(sys.argv[2])
summary.write_text(
    json.dumps(
        {
            "event": {"id": "offline-smoke", "time_utc": "2020-01-01T00:01:00Z"},
            "files": {"kin": [str(kin)]},
        }
    )
    + "\n",
    encoding="utf-8",
)
PY

python3 "$ROOT/scripts/quality/compute_kin_quality.py" \
  --event-time "$EVENT_TIME" \
  --expected-seconds 119 \
  --out-json "$QUALITY_JSON" \
  "$KIN_FILE"

python3 "$ROOT/scripts/normalize/normalize_pride_kin_event.py" \
  --workflow-summary "$SUMMARY_JSON" \
  --quality-json "$QUALITY_JSON" \
  --db "$DB" \
  --normalized-root "$EXPORT_ROOT" \
  --include-warn

python3 "$ROOT/scripts/summaries/validate_normalized_export.py" \
  --root "$EXPORT_ROOT" \
  --event-id "$EVENT_ID"

python3 "$ROOT/scripts/normalize/rebuild_normalized_manifest.py" \
  --root "$EXPORT_ROOT" \
  --write

python3 "$ROOT/scripts/summaries/validate_normalized_export.py" \
  --root "$EXPORT_ROOT" \
  --strict

echo "offline_smoke_ok"
