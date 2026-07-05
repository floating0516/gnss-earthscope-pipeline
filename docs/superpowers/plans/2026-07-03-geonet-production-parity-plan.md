# GeoNet Production Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote GeoNet from a validated schema fixture to a real production path that writes, validates, plots, and accounts for normalized event packages using the same export contract as EarthScope.

**Architecture:** Keep EarthScope and GeoNet as separate workflow/downloader paths, but make their final product identical: `event.json`, `stations.csv`, `waveforms.csv.gz`, and `provenance.json` under the normalized export root. Implement a GeoNet-specific normalizer that reuses the existing PRIDE kin/quality semantics and GeoNet SQLite metadata, then wire it into `run_geonet_event_1hz_pride_workflow.sh` before final plotting and status derivation.

**Tech Stack:** Python 3.10+ standard library, SQLite, shell workflow wrappers, unittest, existing PRIDE kin quality helpers, normalized export validator.

---

## Current State

- `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh` downloads GeoNet data, runs PRIDE, computes kin quality, writes workflow summaries, and has a conditional normalized validator hook.
- The same workflow still initializes `normalized_status=SKIPPED_UNSUPPORTED_SOURCE` and never calls a normalizer.
- `tests/test_geonet_normalized_export_contract.py` proves a fake GeoNet package can satisfy the shared schema, but it does not prove the workflow can produce one.
- `scripts/database/build_geonet_nz_database.py` defines the metadata tables needed for normalization:
  - `geonet_m6plus_events_nz`
  - `event_geonet_station_candidates`
  - `geonet_gnss_stations`
- Existing status tools already understand `normalized_status`, `normalized_export_valid`, `failure_code`, and `next_action`; they mostly need tests to verify GeoNet DONE/FAIL/RETRY behavior once normalization exists.

## Non-Goals

- Do not merge the EarthScope and GeoNet workflows.
- Do not introduce network-dependent tests.
- Do not mutate real `data/`, `runs/`, `exports/`, or `figure/` during tests.
- Do not promote CDDIS/GA/RING/RENAG/EPOS into production.
- Do not change PGD formulas in this phase; PGD should consume the new GeoNet packages after the export contract passes.

## Task 36: Audit and Freeze the GeoNet Normalization Gap

**Files:**
- Modify: `.planning/2026-07-03-mainline-roadmap/findings.md`
- Modify: `.planning/2026-07-03-mainline-roadmap/progress.md`
- Test: `tests/test_regional_workflow_status.py`

- [ ] **Step 1: Record the current gap**

Add a short finding:

```text
GeoNet workflow currently has production download/PRIDE/quality/summary plumbing, but normalization is still hard-coded as SKIPPED_UNSUPPORTED_SOURCE. GeoNet production parity requires a real source-specific normalizer and workflow integration.
```

- [ ] **Step 2: Keep the existing unsupported path covered until replacement**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests/test_regional_workflow_status.py
```

Expected before implementation: pass, proving the current unsupported-normalization behavior is still intentionally documented.

- [ ] **Step 3: Decide the replacement gate**

Document this decision:

```text
Once GeoNet normalizer integration lands, update the regional workflow status test so GeoNet is no longer expected to block final plotting for unsupported normalization. Keep the RING assertion unchanged.
```

## Task 37: Implement GeoNet Normalizer

**Files:**
- Create: `scripts/normalize/normalize_geonet_pride_kin_event.py`
- Create: `tests/test_normalize_geonet_pride_kin_event.py`
- Reuse by import where practical: `scripts/quality/compute_kin_quality.py`
- Reference implementation: `scripts/normalize/normalize_pride_kin_event.py`

- [ ] **Step 1: Write the failing GeoNet normalizer test**

Create a fake SQLite DB with:

```sql
CREATE TABLE geonet_m6plus_events_nz (
  event_id TEXT PRIMARY KEY,
  title TEXT,
  time_utc TEXT NOT NULL,
  event_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  doy INTEGER NOT NULL,
  magnitude REAL NOT NULL,
  mag_type TEXT,
  longitude REAL NOT NULL,
  latitude REAL NOT NULL,
  depth_km REAL,
  place TEXT,
  geonet_url TEXT
);

CREATE TABLE event_geonet_station_candidates (
  event_id TEXT NOT NULL,
  station TEXT NOT NULL,
  event_date TEXT NOT NULL,
  radius_km REAL NOT NULL,
  distance_km REAL NOT NULL,
  station_latitude REAL NOT NULL,
  station_longitude REAL NOT NULL,
  station9 TEXT,
  network TEXT,
  station_active_at_event INTEGER NOT NULL,
  availability_source TEXT NOT NULL,
  metadata_file TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

The test should create one synthetic `kin_*`, one quality JSON with station `OK`, and one workflow summary with `source=GeoNet`, then assert:

```python
event["schema_version"] == "normalized-event/v1"
event["source"] == "geonet"
event["event_authority"] == "GeoNet"
event["station_authority"] == "GeoNet"
provenance["schema_version"] == "provenance/v1"
provenance["source"]["name"] == "geonet"
provenance["source"]["downloader"] in {
    "tools/geonet_downloader/fetch_geonet_1hz.py",
    "tools/geonet_downloader/fetch_geonet_event_highrate.py",
    "tools/geonet_downloader/",
}
```

Run:

```bash
PYTHONPATH=src python3 -m unittest tests/test_normalize_geonet_pride_kin_event.py
```

Expected: fail because the script does not exist.

- [ ] **Step 2: Implement the CLI**

The CLI must support:

```bash
python3 scripts/normalize/normalize_geonet_pride_kin_event.py \
  --workflow-summary <workflow-summary.json> \
  --quality-json <kin-quality.json> \
  --db <geonet_1hz.sqlite> \
  --normalized-root <export-root> \
  --include-warn \
  --overwrite
```

Use the same overwrite semantics as the EarthScope normalizer:

```text
default / --no-overwrite: fail if package exists
--overwrite: stage package first, then atomically replace existing package
```

- [ ] **Step 3: Implement GeoNet event and station metadata readers**

Read events from `geonet_m6plus_events_nz`:

```text
event_id, title, time_utc, event_date, magnitude, mag_type,
longitude, latitude, depth_km, place, geonet_url
```

Read station metadata from `event_geonet_station_candidates` grouped by station:

```text
station, station_latitude, station_longitude, MIN(distance_km) AS distance_km
```

Fallback behavior:

```text
If the event is missing from DB, use workflow summary event id/time and blank spatial fields.
If a quality-passing kin station lacks coordinates, skip it and record skipped_stations reason=missing_coordinates.
If all stations are skipped, exit nonzero.
```

- [ ] **Step 4: Write the normalized package**

Output files must be:

```text
event.json
stations.csv
waveforms.csv.gz
provenance.json
```

GeoNet event fields:

```json
{
  "schema_version": "normalized-event/v1",
  "event_id": "<event_id>",
  "source": "geonet",
  "source_label": "GeoNet PRIDE PPP-AR kin quality-passing stations",
  "event_authority": "GeoNet",
  "station_authority": "GeoNet",
  "event_time": "<time_utc>",
  "region": "New Zealand",
  "network": "GeoNet"
}
```

GeoNet provenance fields:

```json
{
  "schema_version": "provenance/v1",
  "workflow": {
    "name": "geonet-event-1hz-pride",
    "script": "scripts/workflows/run_geonet_event_1hz_pride_workflow.sh"
  },
  "source": {
    "name": "geonet",
    "event_authority": "GeoNet",
    "station_authority": "GeoNet",
    "downloader": "tools/geonet_downloader/"
  },
  "quality": {
    "quality_json": "<path>",
    "thresholds": {},
    "summary_status": "OK"
  }
}
```

- [ ] **Step 5: Validate output through the shared validator**

The unit test must run:

```python
report = validate_export.validate_export(root, event_id=event_id)
self.assertEqual(report["status"], "OK")
```

Then run:

```bash
PYTHONPATH=src python3 -m unittest tests/test_normalize_geonet_pride_kin_event.py
```

Expected: pass.

## Task 38: Wire GeoNet Normalizer Into the Event Workflow

**Files:**
- Modify: `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`
- Modify: `tests/test_workflow_validator_integration.py`
- Modify: `tests/test_regional_workflow_status.py`

- [ ] **Step 1: Add a failing workflow integration test**

Assert `run_geonet_event_1hz_pride_workflow.sh` contains all of:

```text
normalize_geonet_pride_kin_event.py
--workflow-summary
--quality-json
--normalized-root
validate_normalized_export.py
--event-id
```

Run:

```bash
PYTHONPATH=src python3 -m unittest tests/test_workflow_validator_integration.py
```

Expected before implementation: fail because the normalizer is not referenced.

- [ ] **Step 2: Add workflow options**

Add options:

```text
--normalized-root DIR       Final normalized export root
--include-warn-normalize    Include WARN stations in normalized package
--overwrite-normalized      Replace existing normalized event package
--skip-normalize            Do not normalize even when kin quality exists
```

Defaults:

```text
normalized root: $FINAL_NORMALIZED_ROOT or exports/normalized-ok-stations-us-nz
include WARN: on, matching current EarthScope production behavior
overwrite: off
skip normalize: off
```

- [ ] **Step 3: Run GeoNet normalization after quality**

If:

```text
kin_count > 0
quality_status is OK or WARN
SKIP_PROCESS did not prevent reused kin discovery
SKIP_NORMALIZE is false
```

then call:

```bash
python3 "$GEONET_NORMALIZER" \
  --workflow-summary "$WORKFLOW_JSON" \
  --quality-json "$KIN_QUALITY_JSON" \
  --db "$GEONET_DB" \
  --normalized-root "$FINAL_NORMALIZED_ROOT" \
  --include-warn
```

Capture the JSON stdout and update:

```text
normalized_status
normalized_event_dir
normalized_station_count
normalized_waveform_rows
normalized_event_grade
```

If the normalizer exits nonzero, set:

```text
normalized_status=FAIL
normalized_validation_status=SKIPPED_NORMALIZE_FAILED
```

- [ ] **Step 4: Validate before final plotting**

Keep the existing validator call, but make it reachable for GeoNet packages:

```bash
python3 "$VALIDATOR" \
  --root "$FINAL_NORMALIZED_ROOT" \
  --event-id "$EVENT_ID" \
  --json-out "$NORMALIZED_VALIDATION_JSON"
```

Final plot should run only when:

```text
normalized_status == OK
normalized_validation_status == OK
```

- [ ] **Step 5: Update unsupported regional workflow test**

Change `tests/test_regional_workflow_status.py`:

```text
GeoNet: use --skip-normalize and expect plot_status=BLOCKED_NORMALIZE_UNSUPPORTED or SKIPPED_NORMALIZE as explicitly requested.
RING: keep expecting SKIPPED_UNSUPPORTED_SOURCE.
```

Run:

```bash
bash -n scripts/workflows/run_geonet_event_1hz_pride_workflow.sh
PYTHONPATH=src python3 -m unittest tests/test_workflow_validator_integration.py tests/test_regional_workflow_status.py
```

Expected: pass.

## Task 39: Add GeoNet Workflow Smoke With Fake Normalizer Inputs

**Files:**
- Create or modify: `tests/test_geonet_workflow_normalization_integration.py`
- Modify if needed: `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`

- [ ] **Step 1: Write a shell-level integration test with fake components**

Use `tempfile.TemporaryDirectory(dir=ROOT)` and fake executables/scripts so the test does not use network or PRIDE:

```text
fake GeoNet downloader: writes one valid obs placeholder large enough for validation
fake PRIDE processor: writes event-window-summary.tsv and one synthetic kin_* file
real quality script: compute quality from synthetic kin
real GeoNet normalizer: write normalized package
real validator: validate package
fake final plot python: records that plotting was called
```

If directly faking PRIDE output is too brittle, keep this as a smaller integration test that supplies pre-existing `kin-files.txt` and invokes the normalizer branch through controlled workflow state.

- [ ] **Step 2: Assert workflow summary fields**

Expected TSV/JSON fields:

```text
normalized_status=OK
normalized_export_valid=true
normalized_validation_status=OK
normalized_station_count=1
normalized_waveform_rows>0
plot_status=OK or SKIPPED_NO_NORMALIZED_EVENT depending on fake plotter contract
workflow_result=DONE
```

- [ ] **Step 3: Run focused tests**

```bash
PYTHONPATH=src python3 -m unittest tests/test_geonet_workflow_normalization_integration.py
```

Expected: pass without network access.

## Task 40: Update GeoNet Batch, Ledger, and Worklist Accounting

**Files:**
- Modify: `tests/test_classify_batch_status.py`
- Modify: `tests/test_build_run_ledger.py`
- Modify: `tests/test_cli_worklist.py`
- Modify only if tests expose a gap: `scripts/workflows/classify_batch_status.py`
- Modify only if tests expose a gap: `scripts/summaries/build_run_ledger.py`
- Modify only if tests expose a gap: `src/gnss_eq/cli.py`

- [ ] **Step 1: Add GeoNet DONE fixture**

Build fake run/export rows where:

```text
source=GeoNet
normalized_status=OK
normalized_export_valid=true
workflow_result=DONE
```

Assert:

```text
classifier final_status=OK
run ledger export_status=OK
worklist_status=DONE
```

- [ ] **Step 2: Add GeoNet retry fixtures**

Cover:

```text
normalized_status=FAIL -> RETRY_NORMALIZE
normalized_status=OK but normalized_validation_status=FAIL -> RETRY_NORMALIZE or UNKNOWN_REVIEW with failure_code=NORMALIZED_VALIDATION_FAIL
plot_status=FAIL with valid export -> RETRY_PLOT
quality_status=FAIL -> CLASSIFIED_QUALITY_FAIL
```

- [ ] **Step 3: Keep source-neutral status semantics**

Prefer fixing shared classifier/ledger logic instead of adding GeoNet-only branches unless a GeoNet field truly differs.

- [ ] **Step 4: Run focused and full tests**

```bash
PYTHONPATH=src python3 -m unittest tests/test_classify_batch_status.py tests/test_build_run_ledger.py tests/test_cli_worklist.py
PYTHONPATH=src python3 -m unittest discover tests
```

Expected: all pass.

## Final Verification

Run:

```bash
PYTHONPATH=src python3 -m unittest tests/test_normalize_geonet_pride_kin_event.py
PYTHONPATH=src python3 -m unittest tests/test_workflow_validator_integration.py tests/test_regional_workflow_status.py
PYTHONPATH=src python3 -m unittest tests/test_classify_batch_status.py tests/test_build_run_ledger.py tests/test_cli_worklist.py
bash scripts/ops/check_shell_syntax.sh
bash scripts/ops/smoke_test_offline.sh
PYTHONPATH=src python3 -m unittest discover tests
```

Expected:

```text
all focused tests pass
shell_syntax_ok
offline_smoke_ok
full unittest OK
```

## Acceptance Criteria

- GeoNet workflow can produce a strict-schema normalized package from PRIDE `kin_*` plus GeoNet DB metadata.
- GeoNet `event.json` uses `source=geonet`, `event_authority=GeoNet`, and `station_authority=GeoNet`.
- GeoNet `provenance.json` uses `schema_version=provenance/v1` and records workflow/source/processing/quality metadata.
- `validate_normalized_export.py --event-id <geonet_event_id>` passes immediately after normalization.
- GeoNet final plotting is blocked by validation failures, not by hard-coded unsupported-normalization.
- Batch classifier, run ledger, and `gnss-eq worklist` classify GeoNet DONE/RETRY/REVIEW rows without source-specific hacks.
