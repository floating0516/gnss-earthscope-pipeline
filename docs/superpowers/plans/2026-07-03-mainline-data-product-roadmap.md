# GNSS Mainline Data Product Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the repository from a collection of working scripts and local runs into a reproducible GNSS earthquake normalized data-product pipeline with validation, reporting, and resumable task accounting.

**Architecture:** Treat EarthScope/GAGE and GeoNet as the only production sources. Treat `exports/normalized-ok-stations-us-nz/` as the final product boundary, `runs/` as history, `data/` as local state, and CDDIS/GA/RING/RENAG/EPOS as non-production unless explicitly promoted. Build contract-first tooling: validate packages before rebuilding manifests, reporting, or classifying work.

**Tech Stack:** Python 3.10+, standard library CLI scripts, shell workflow wrappers, SQLite state databases, unittest, PRIDE PPP-AR external tooling.

---

## 1. Battle Assessment

### What Is Correct

- The mainline should stop being "find more sources and run more events" and become "produce a validated normalized data product".
- EarthScope/GAGE and GeoNet are the right production sources; CDDIS should remain research; GA/RING/RENAG/EPOS should remain parked.
- `exports/normalized-ok-stations-us-nz/` is the final-data layer. `runs/` is attempt history and should not be used as the final event count.
- A validator is the right first green light. Without it, manifest rebuilders, reports, run ledgers, and PGD analysis can encode inconsistent assumptions.
- A run ledger and batch classifier are the right way to replace manual directory inspection.

### What Needs Adjustment

- The quality-layer claim is too broad. Local code does not blindly change every `OK` station to `WARN`; it only downgrades `OK` when `gap_count` is nonzero. The confirmed issues are narrower: station-level synthetic tests are missing, `--allow-partial-failures` is currently defined but unused, and quality JSON lacks `schema_version` and thresholds.
- Manifest rebuilding should not be first. The validator and package contract must land before a rebuild script writes canonical indexes.
- Atomic normalizer writes are important but should come after the package contract is explicit. Atomicity protects whatever contract exists; if the contract is fuzzy, atomic writes will just preserve fuzzy output more reliably.
- Workflow failure semantics should be improved, but full fake end-to-end workflow tests may be expensive. Start with unit-level summary/status tests and small shell syntax checks, then add offline smoke tests.
- A GitHub Actions workflow is useful for public source code, but it must not depend on local `data/`, `runs/`, `exports/`, `figure/`, EarthScope auth, or PRIDE binaries.

### What I Would Defer

- New source promotion work.
- PGD magnitude as a "formal product" until export validation and inventory are stable.
- Large refactors of workflow shell scripts.
- Schema unification across all sources in one pass. Start with validator tolerance for current schema, then version future schema.

---

## 2. Target Operating Model

### Final Product

A production event is a normalized event package:

```text
exports/normalized-ok-stations-us-nz/<event-dir>/
  event.json
  stations.csv
  waveforms.csv.gz
  provenance.json
```

The dataset is production-valid only when:

```text
manifest.tsv event IDs
== event_summary.csv event IDs
== complete event package event IDs
```

and every package has readable JSON, readable CSV/GZIP CSV, station rows, waveform rows, and provenance.

### Layer Boundaries

```text
Discovery:      watch-usgs, review-usgs, monitor, source routing
Planning state: data/*_availability, data/*_batches, data/summaries
Run history:    runs/<event-id>/workflow-*/
Final product:  exports/normalized-ok-stations-us-nz/
Figures:        figure/
Reports:        reports/
```

### Source Policy

```text
Production: EarthScope/GAGE, GeoNet
Research:   CDDIS
Parked:     GA, RING, RENAG, EPOS
Reference:  historical/paper normalized data
```

---

## 3. Execution Gates

### Gate 0: Plan Approval

This document is the current deliverable. No business-code execution starts until the user approves or edits it.

### Gate 1: Export Contract

Must produce:

```text
scripts/summaries/validate_normalized_export.py
tests/test_validate_normalized_export.py
docs/mainline_operating_model.md
docs/runbook_earthscope_geonet.md
AGENTS.md
```

Gate passes when:

```bash
python -m unittest tests/test_validate_normalized_export.py
python -m unittest discover tests
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz
```

### Gate 2: Quality Contract

Must produce:

```text
tests/test_compute_kin_quality.py updates
scripts/quality/compute_kin_quality.py updates
```

Gate passes when:

```bash
python -m unittest tests/test_compute_kin_quality.py
python -m unittest discover tests
```

The quality JSON must include:

```json
{
  "schema_version": "kin-quality/v1",
  "thresholds": {
    "min_epochs": 60,
    "min_coverage_ratio": 0.8,
    "min_station_health_ratio": 0.8,
    "max_pre_rms_cm": 10.0,
    "max_epoch_jump_cm": 50.0
  },
  "summary": {},
  "stations": []
}
```

### Gate 3: Index and Inventory

Must produce:

```text
scripts/normalize/rebuild_normalized_manifest.py
tests/test_rebuild_normalized_manifest.py
scripts/summaries/build_current_normalized_inventory.py
tests/test_build_current_normalized_inventory.py
```

Gate passes when rebuilt fake indexes validate and real export can be inventoried read-only.

### Gate 4: Task Accounting

Must produce:

```text
scripts/workflows/classify_batch_status.py
tests/test_classify_batch_status.py
scripts/summaries/build_run_ledger.py
tests/test_build_run_ledger.py
```

Gate passes when fake runs are classified into deterministic `final_status`, `failure_class`, and `next_action`.

### Gate 5: Workflow Hardening

Must produce:

```text
scripts/workflows/run_event_1hz_pride_workflow.sh updates
scripts/workflows/run_geonet_event_1hz_pride_workflow.sh updates
tests/test_workflow_summary_status.py updates or new focused tests
scripts/ops/check_shell_syntax.sh
scripts/ops/smoke_test_offline.sh
```

Gate passes when:

```bash
bash scripts/ops/check_shell_syntax.sh
bash scripts/ops/smoke_test_offline.sh
python -m unittest discover tests
```

---

## 4. Implementation Plan

### Task 1: Mainline Docs and Contributor Guardrails

**Files:**
- Create: `docs/mainline_operating_model.md`
- Create: `docs/runbook_earthscope_geonet.md`
- Create: `AGENTS.md`

- [ ] **Step 1: Write `docs/mainline_operating_model.md`**

Include these exact sections:

```text
1. Project goal
2. Production sources
3. Research and parked sources
4. Final product definition
5. Event DONE
6. Batch DONE
7. Dataset DONE
8. Source promotion rules
9. What not to optimize yet
10. Standard command sequence
```

- [ ] **Step 2: Write `docs/runbook_earthscope_geonet.md`**

Include this command sequence:

```bash
gnss-eq check-env
scripts/workflows/current_pipeline.sh paths
scripts/workflows/current_pipeline.sh update-availability
scripts/workflows/current_pipeline.sh rebuild-candidates
scripts/workflows/current_pipeline.sh list-events
scripts/workflows/current_pipeline.sh export-batch --event-id EVENT_ID --radius-km 200
scripts/workflows/current_pipeline.sh run-batch --csv data/batches/EVENT_ID-200km.csv
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz
```

- [ ] **Step 3: Write `AGENTS.md`**

Include these rules:

```text
Do not move source-specific scripts without wrappers.
Do not commit data/runs/exports/figure bulk products.
Use tempfile for tests.
Run unittest for Python changes.
Run bash -n for shell workflow changes.
Treat CDDIS as research.
Treat GA/RING/RENAG/EPOS as parked.
Treat EarthScope/GeoNet normalized export as production.
```

- [ ] **Step 4: Verify docs**

Run:

```bash
grep -i "EarthScope" docs/mainline_operating_model.md
grep -i "GeoNet" docs/mainline_operating_model.md
grep -i "normalized" docs/mainline_operating_model.md
grep -i "current_pipeline.sh" docs/runbook_earthscope_geonet.md
grep -i "CDDIS" AGENTS.md
python -m unittest discover tests
```

Expected: all grep commands find text; unittest passes.

### Task 2: Normalized Export Validator

**Files:**
- Create: `scripts/summaries/validate_normalized_export.py`
- Create: `tests/test_validate_normalized_export.py`

- [ ] **Step 1: Write failing tests for a valid fake export**

Test fixture contents:

```text
manifest.tsv with event_id
event_summary.csv with event_id
file_inventory.tsv with package files
event-dir/event.json
event-dir/stations.csv
event-dir/waveforms.csv.gz
event-dir/provenance.json
```

Expected test assertions:

```python
self.assertEqual(report["status"], "OK")
self.assertEqual(report["event_count"], 1)
self.assertEqual(report["error_count"], 0)
```

- [ ] **Step 2: Write failing tests for missing files and set mismatches**

Cases:

```text
missing provenance.json -> invalid
manifest event_id missing package -> invalid
event_summary event_id differs from package event_id -> invalid
file_inventory path missing -> invalid
stations.csv empty -> invalid
waveforms.csv.gz empty -> invalid
```

- [ ] **Step 3: Implement CLI**

Required arguments:

```bash
--root PATH
--event-id EVENT_ID
--json-out PATH
--strict
```

Exit behavior:

```text
0 when valid
1 when invalid
```

- [ ] **Step 4: Verify**

Run:

```bash
python -m unittest tests/test_validate_normalized_export.py
python -m unittest discover tests
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz
```

Expected: tests pass; real export prints a human-readable summary. If real export fails, preserve the failure report and do not "fix" data until the user approves data edits.

### Task 3: Quality Contract Audit and Fix

**Files:**
- Modify: `scripts/quality/compute_kin_quality.py`
- Modify: `tests/test_compute_kin_quality.py`

- [ ] **Step 1: Add synthetic `kin_*` fixture helper in tests**

The helper must generate GPST/MJD rows using existing test helpers and create:

```text
clean continuous station
low coverage station
high pre-event RMS station
station with intentional gap
```

- [ ] **Step 2: Add station-level assertions**

Expected behavior:

```text
clean continuous station -> station OK, summary OK
low coverage station -> station FAIL
high pre-event RMS station -> station WARN
gap station -> station WARN
```

- [ ] **Step 3: Add JSON schema and thresholds**

Output must include:

```json
{
  "schema_version": "kin-quality/v1",
  "thresholds": {},
  "summary": {},
  "stations": []
}
```

- [ ] **Step 4: Resolve `--allow-partial-failures` semantics**

Implement one explicit behavior:

```text
without --allow-partial-failures: any FAIL station can make event summary FAIL when station health is below threshold
with --allow-partial-failures: at least one OK/WARN station may produce summary WARN instead of FAIL
```

Record the active policy in JSON:

```json
{"policy": {"allow_partial_failures": true}}
```

- [ ] **Step 5: Verify**

Run:

```bash
python -m unittest tests/test_compute_kin_quality.py
python -m unittest discover tests
```

Expected: tests pass and quality exit code remains `0` for summary `OK` or `WARN`, nonzero for summary `FAIL`.

### Task 4: Current Normalized Inventory

**Files:**
- Create: `scripts/summaries/build_current_normalized_inventory.py`
- Create: `tests/test_build_current_normalized_inventory.py`

- [ ] **Step 1: Build tests with fake export and fake figures**

Expected output rows:

```text
event_id
source
event_time
magnitude
region
station_count
waveform_rows
quality_status
event_grade
azimuth_bins
has_figure
figure_paths
package_path
```

- [ ] **Step 2: Implement CLI**

CLI:

```bash
python scripts/summaries/build_current_normalized_inventory.py \
  --root exports/normalized-ok-stations-us-nz \
  --figure-root figure \
  --out-prefix data/summaries/current-normalized-export
```

Outputs:

```text
<out-prefix>.tsv
<out-prefix>.json
<out-prefix>.md
```

- [ ] **Step 3: Verify**

Run:

```bash
python -m unittest tests/test_build_current_normalized_inventory.py
python scripts/summaries/build_current_normalized_inventory.py \
  --root exports/normalized-ok-stations-us-nz \
  --figure-root figure \
  --out-prefix data/summaries/current-normalized-export
```

Expected: test passes; real command writes summary files only after user confirms writing to `data/summaries`.

### Task 5: Manifest Rebuild

**Files:**
- Create: `scripts/normalize/rebuild_normalized_manifest.py`
- Create: `tests/test_rebuild_normalized_manifest.py`

- [ ] **Step 1: Write fake export tests**

Build two fake packages and assert generated:

```text
manifest.tsv
event_summary.csv
file_inventory.tsv
```

- [ ] **Step 2: Implement dry-run default**

CLI:

```bash
python scripts/normalize/rebuild_normalized_manifest.py --root exports/normalized-ok-stations-us-nz
```

Default behavior:

```text
Print planned row counts and diff summary.
Do not write files.
```

- [ ] **Step 3: Implement `--write` with atomic replace**

Write temporary files in the export root and replace:

```text
manifest.tsv
event_summary.csv
file_inventory.tsv
```

- [ ] **Step 4: Verify**

Run:

```bash
python -m unittest tests/test_rebuild_normalized_manifest.py
python -m unittest discover tests
```

Expected: tests pass; dry-run on real export does not modify files.

### Task 6: Batch Classifier and Run Ledger

**Files:**
- Create: `scripts/workflows/classify_batch_status.py`
- Create: `tests/test_classify_batch_status.py`
- Create: `scripts/summaries/build_run_ledger.py`
- Create: `tests/test_build_run_ledger.py`

- [ ] **Step 1: Define status vocabulary**

Allowed values:

```text
OK
SKIPPED_EXISTING
RETRY_DOWNLOAD
RETRY_PROCESS
RETRY_NORMALIZE
RETRY_PLOT
CLASSIFIED_NO_OBS
CLASSIFIED_NO_KIN
CLASSIFIED_QUALITY_FAIL
CLASSIFIED_NO_STATIONS
CLASSIFIED_SOURCE_UNSUPPORTED
ABANDONED_AUTH
ABANDONED_REPEATED_TIMEOUT
UNKNOWN_REVIEW
```

- [ ] **Step 2: Test fake workflows**

Use fake `workflow-summary.json` files to test:

```text
export valid -> OK
obs_validation FAIL -> CLASSIFIED_NO_OBS
kin_count 0 -> CLASSIFIED_NO_KIN
quality FAIL -> CLASSIFIED_QUALITY_FAIL
normalized OK + plot FAIL -> RETRY_PLOT
three TIMEOUT batch statuses -> ABANDONED_REPEATED_TIMEOUT
```

- [ ] **Step 3: Implement classifier CLI**

```bash
python scripts/workflows/classify_batch_status.py \
  --batch data/batches/example.csv \
  --runs runs \
  --export-root exports/normalized-ok-stations-us-nz \
  --out data/batches/example.classified.csv
```

- [ ] **Step 4: Implement run ledger CLI**

```bash
python scripts/summaries/build_run_ledger.py \
  --runs runs \
  --export-root exports/normalized-ok-stations-us-nz \
  --out data/summaries/run-ledger.tsv
```

- [ ] **Step 5: Verify**

Run:

```bash
python -m unittest tests/test_classify_batch_status.py
python -m unittest tests/test_build_run_ledger.py
python -m unittest discover tests
```

Expected: tests pass; real writes to `data/batches` or `data/summaries` happen only when user confirms output paths.

### Task 7: Workflow Validator Hook and Failure Reasons

**Files:**
- Modify: `scripts/workflows/run_event_1hz_pride_workflow.sh`
- Modify: `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`
- Modify: `scripts/workflows/update_workflow_summary_status.py`
- Modify/Create tests under `tests/`

- [ ] **Step 1: Add summary fields**

Add machine-readable fields:

```json
{
  "failure": {
    "stage": "",
    "failure_code": "",
    "failure_message": "",
    "next_action": ""
  },
  "export_validation": {
    "status": "",
    "error_count": 0
  }
}
```

- [ ] **Step 2: Call validator after successful normalization**

Command shape:

```bash
python3 scripts/summaries/validate_normalized_export.py \
  --root exports/normalized-ok-stations-us-nz \
  --event-id "$EVENT_ID" \
  --json-out "$REPORT_DIR/export-validation.json"
```

- [ ] **Step 3: Verify shell syntax**

Run:

```bash
bash -n scripts/workflows/run_event_1hz_pride_workflow.sh
bash -n scripts/workflows/run_geonet_event_1hz_pride_workflow.sh
python -m unittest discover tests
```

Expected: syntax checks and tests pass.

### Task 8: Offline Smoke and CI

**Files:**
- Create: `scripts/ops/check_shell_syntax.sh`
- Create: `scripts/ops/smoke_test_offline.sh`
- Create: `.github/workflows/tests.yml`

- [ ] **Step 1: Add shell syntax checker**

Expected script body:

```bash
#!/usr/bin/env bash
set -euo pipefail

find scripts tools -name "*.sh" -print0 | while IFS= read -r -d '' file; do
  bash -n "$file"
done
```

- [ ] **Step 2: Add offline smoke test**

The smoke test must:

```text
create temp dir
generate fake kin files
run compute_kin_quality.py
create fake metadata DB and workflow summary
run normalize_pride_kin_event.py
run validate_normalized_export.py
```

It must not access network or real `data/`, `runs/`, `exports/`, or `figure`.

- [ ] **Step 3: Add CI**

Workflow command:

```yaml
- run: python -m pip install -e .
- run: python -m unittest discover tests
```

- [ ] **Step 4: Verify locally**

Run:

```bash
bash scripts/ops/check_shell_syntax.sh
bash scripts/ops/smoke_test_offline.sh
python -m unittest discover tests
```

Expected: all pass without network.

---

## 5. Recommended Approval Scope

Approve the first execution batch as:

```text
Task 1: Mainline docs and AGENTS.md
Task 2: Normalized export validator
Task 3: Quality contract audit and fix
Task 4: Current normalized inventory
```

Hold these until the first batch passes:

```text
Manifest rebuild
Batch classifier
Run ledger
Workflow hook changes
Atomic normalizer writes
Dataset report
PGD report
Source promotion docs
```

This keeps the first pass focused on contract, observability, and the biggest confirmed quality risk.

---

## 6. Success Criteria

After the approved plan is implemented, the project should be able to answer these with commands, not manual inspection:

```bash
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz --strict
python scripts/summaries/build_current_normalized_inventory.py --root exports/normalized-ok-stations-us-nz --figure-root figure --out-prefix data/summaries/current-normalized-export
python scripts/summaries/build_run_ledger.py --runs runs --export-root exports/normalized-ok-stations-us-nz --out data/summaries/run-ledger.tsv
```

The desired operating statement becomes:

```text
We have a validated normalized GNSS earthquake dataset.
Every event package has a contract.
Every run has an accounting status.
Every failure has a next action.
Production sources are EarthScope/GAGE and GeoNet.
Research and parked sources are fenced.
```
