# EarthScope Workflow Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the EarthScope local workflow report and control its real end-to-end state: download, PRIDE, quality, normalization, export package, final plotting, retry eligibility, and cleanup behavior.

**Architecture:** Keep the current shell workflow shape, but move fragile inline summary logic into small testable Python helpers. The single-event workflow will update summaries after final plotting, the batch workflow will build richer summaries from workflow JSON plus export package checks, and monitor/MCP/CLI will share clearer state semantics without treating any workflow directory as a successful collection.

**Tech Stack:** Bash workflow scripts, Python 3.10+ standard library, `unittest`, existing `gnss_eq` CLI/MCP modules, existing `@ROOT@` portable path convention.

---

## Global Constraints

- Scope is the maintained EarthScope/GAGE line only.
- Do not reprocess or rewrite existing `runs/`, `exports/`, or `data/` products during implementation.
- Do not refactor GeoNet, CDDIS, GA, RING, EPOS, or RENAG workflows in this pass.
- Preserve default cleanup behavior: cleanup stays on unless explicitly disabled.
- Add disable flags rather than changing defaults: `--no-cleanup-downloads`, `--no-cleanup-pride-workdir`, `--no-cleanup-obs`.
- Use `@ROOT@` portable paths in generated summaries.
- Use TDD for each behavior change: write failing tests, verify the expected failure, then implement.
- Use `PYTHONPATH=src` for Python tests.

---

## File Structure

- Create `scripts/workflows/update_workflow_summary_status.py`
  - Responsibility: update an existing single-event `workflow-summary.tsv`, `workflow-summary.json`, and `workflow-summary.md` after late stages such as final plotting.
  - Inputs: summary file paths, `plot_status`, plot manifest path, optional `plot_count`.
  - Outputs: patched summary files only.

- Create `scripts/workflows/build_event_batch_summary.py`
  - Responsibility: build `batch-summary.tsv` from a batch CSV and latest workflow summary JSON files.
  - Inputs: batch CSV, summary path, run root, pipeline root.
  - Outputs: richer batch summary with normalized and export package fields.

- Modify `scripts/workflows/run_event_1hz_pride_workflow.sh`
  - Responsibility: call final plotting before final status is considered complete, capture plot files, and patch summaries.
  - Add cleanup disable flags.

- Modify `scripts/workflows/run_event_batch_workflow.sh`
  - Responsibility: delegate batch summary generation to `build_event_batch_summary.py`.
  - Add cleanup disable flags and forward them to the event workflow.

- Modify `src/gnss_eq/cli.py`
  - Responsibility: expose boolean cleanup flags with true default and explicit false forwarding.

- Modify `src/gnss_eq/mcp_server.py`
  - Responsibility: align cleanup defaults with shell workflow and expose disable forwarding. Update coverage status logic used by MCP overview.

- Modify `src/gnss_eq/monitor.py`
  - Responsibility: classify workflow attempts from latest summary content rather than directory presence.

- Modify `src/gnss_eq/preflight.py`
  - Responsibility: verify all scripts needed by the full EarthScope workflow, not just early stages.

- Modify tests:
  - `tests/test_cli.py`
  - `tests/test_mcp_server.py`
  - `tests/test_preflight.py`
  - `tests/test_process_event_window_paths.py`
  - Create `tests/test_workflow_summary_status.py`
  - Create `tests/test_event_batch_summary.py`
  - Create or extend monitor tests in `tests/test_cli.py` or `tests/test_monitor.py`

---

### Task 1: Add a testable workflow summary updater

**Files:**
- Create: `scripts/workflows/update_workflow_summary_status.py`
- Create: `tests/test_workflow_summary_status.py`

- [x] **Step 1: Write failing tests for post-plot summary update**

Create `tests/test_workflow_summary_status.py` with tests equivalent to:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.workflows import update_workflow_summary_status as updater


class WorkflowSummaryStatusTest(unittest.TestCase):
    def test_updates_plot_status_and_plot_count_in_all_summary_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            manifest_dir = report_dir.parent / "manifests"
            report_dir.mkdir(parents=True)
            manifest_dir.mkdir(parents=True)

            summary_json = report_dir / "workflow-summary.json"
            summary_tsv = report_dir / "workflow-summary.tsv"
            summary_md = report_dir / "workflow-summary.md"
            plot_manifest = manifest_dir / "plot-files.txt"

            summary_json.write_text(
                json.dumps(
                    {
                        "status": {"plot": "SKIPPED_DISABLED", "normalized": "OK"},
                        "counts": {"plot_files": 0},
                        "files": {"plots": []},
                    },
                    indent=2,
                )
                + "\n"
            )
            summary_tsv.write_text("key\tvalue\nplot_status\tSKIPPED_DISABLED\nplot_file_count\t0\n")
            summary_md.write_text("- Plot status: `SKIPPED_DISABLED`\n- Plot files: `0`\n")
            plot_manifest.write_text("@ROOT@/figure/event-a-map.png\n@ROOT@/figure/event-a-record.png\n")

            rc = updater.main(
                [
                    "--summary-json",
                    str(summary_json),
                    "--summary-tsv",
                    str(summary_tsv),
                    "--summary-md",
                    str(summary_md),
                    "--plot-status",
                    "OK",
                    "--plot-files",
                    str(plot_manifest),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(summary_json.read_text())
            self.assertEqual(payload["status"]["plot"], "OK")
            self.assertEqual(payload["counts"]["plot_files"], 2)
            self.assertEqual(payload["files"]["plots"], ["@ROOT@/figure/event-a-map.png", "@ROOT@/figure/event-a-record.png"])
            self.assertIn("plot_status\tOK\n", summary_tsv.read_text())
            self.assertIn("plot_file_count\t2\n", summary_tsv.read_text())
            self.assertIn("- Plot status: `OK`", summary_md.read_text())
            self.assertIn("- Plot files: `2`", summary_md.read_text())
```

- [x] **Step 2: Run the new test to verify it fails**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_workflow_summary_status -v
```

Expected: FAIL or ERROR because `scripts.workflows.update_workflow_summary_status` does not exist.

- [x] **Step 3: Implement the summary updater**

Create `scripts/workflows/update_workflow_summary_status.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch workflow summaries after late workflow stages.")
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--summary-tsv", type=Path, required=True)
    parser.add_argument("--summary-md", type=Path, required=True)
    parser.add_argument("--plot-status", required=True)
    parser.add_argument("--plot-files", type=Path, required=True)
    return parser.parse_args(argv)


def read_plot_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_json(path: Path, plot_status: str, plot_files: list[str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("status", {})["plot"] = plot_status
    payload.setdefault("counts", {})["plot_files"] = len(plot_files)
    payload.setdefault("files", {})["plots"] = plot_files
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_tsv(path: Path, plot_status: str, plot_count: int) -> None:
    rows: list[list[str]] = []
    with path.open(newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        rows = list(reader)

    seen = set()
    for row in rows:
        if len(row) < 2:
            continue
        if row[0] == "plot_status":
            row[1] = plot_status
            seen.add("plot_status")
        elif row[0] == "plot_file_count":
            row[1] = str(plot_count)
            seen.add("plot_file_count")

    if "plot_status" not in seen:
        rows.append(["plot_status", plot_status])
    if "plot_file_count" not in seen:
        rows.append(["plot_file_count", str(plot_count)])

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def update_markdown(path: Path, plot_status: str, plot_count: int) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    status_line = f"- Plot status: `{plot_status}`"
    count_line = f"- Plot files: `{plot_count}`"
    status_done = False
    count_done = False
    for index, line in enumerate(lines):
        if line.startswith("- Plot status:"):
            lines[index] = status_line
            status_done = True
        elif line.startswith("- Plot files:"):
            lines[index] = count_line
            count_done = True
    if not status_done:
        lines.append(status_line)
    if not count_done:
        lines.append(count_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plot_files = read_plot_files(args.plot_files)
    update_json(args.summary_json, args.plot_status, plot_files)
    update_tsv(args.summary_tsv, args.plot_status, len(plot_files))
    update_markdown(args.summary_md, args.plot_status, len(plot_files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run the new test to verify it passes**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_workflow_summary_status -v
```

Expected: PASS.

---

### Task 2: Patch final plotting into EarthScope event summaries

**Files:**
- Modify: `scripts/workflows/run_event_1hz_pride_workflow.sh`
- Test: `tests/test_workflow_summary_status.py`

- [x] **Step 1: Add a failing test for extracting final plot files from a log**

Extend `tests/test_workflow_summary_status.py` with:

```python
    def test_extracts_png_paths_from_final_plot_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "plot-final-normalized.log"
            log.write_text(
                "rendering\n"
                "/mnt/data/gnss-earthscope-pipeline/figure/event-map.png\n"
                "figure/event-record.png\n"
                "not-a-plot.txt\n"
            )
            self.assertEqual(
                updater.extract_plot_files_from_log(log),
                [
                    "/mnt/data/gnss-earthscope-pipeline/figure/event-map.png",
                    "figure/event-record.png",
                ],
            )
```

- [x] **Step 2: Verify the test fails**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_workflow_summary_status.WorkflowSummaryStatusTest.test_extracts_png_paths_from_final_plot_log -v
```

Expected: FAIL because `extract_plot_files_from_log` does not exist.

- [x] **Step 3: Add `extract_plot_files_from_log` to the updater**

Add this function to `scripts/workflows/update_workflow_summary_status.py`:

```python
def extract_plot_files_from_log(path: Path) -> list[str]:
    if not path.exists():
        return []
    result = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = raw.strip()
        if text.endswith(".png") and (text.startswith("/") or text.startswith("figure/") or "/figure/" in text):
            result.append(text)
    return result
```

- [x] **Step 4: Wire event workflow post-plot update**

Modify `scripts/workflows/run_event_1hz_pride_workflow.sh` after the final plot command:

```bash
  if "$FINAL_PLOT_PYTHON" "${PIPELINE_ROOT}/scripts/plotting/plot_completed_normalized_event.py" --workflow-summary "$WORKFLOW_JSON" --normalized-root "$FINAL_NORMALIZED_ROOT" --outdir "$FINAL_FIGURE_DIR" > "${LOG_DIR}/plot-final-normalized.log" 2>&1; then
    final_plot_status="OK"
  else
    final_plot_status="FAIL"
    echo "Final normalized plotting failed. See ${LOG_DIR}/plot-final-normalized.log" >&2
  fi
  python3 - "${LOG_DIR}/plot-final-normalized.log" "${MANIFEST_DIR}/plot-files.txt" <<'PY'
import sys
from pathlib import Path
from scripts.workflows.update_workflow_summary_status import extract_plot_files_from_log

log_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
out_path.write_text("\n".join(extract_plot_files_from_log(log_path)) + ("\n" if extract_plot_files_from_log(log_path) else ""), encoding="utf-8")
PY
  plot_count="$(wc -l < "${MANIFEST_DIR}/plot-files.txt" | tr -d ' ')"
  python3 "${PIPELINE_ROOT}/scripts/workflows/update_workflow_summary_status.py" \
    --summary-json "$WORKFLOW_JSON" \
    --summary-tsv "${REPORT_DIR}/workflow-summary.tsv" \
    --summary-md "${REPORT_DIR}/workflow-summary.md" \
    --plot-status "$final_plot_status" \
    --plot-files "${MANIFEST_DIR}/plot-files.txt"
```

Then simplify the inline Python to avoid calling `extract_plot_files_from_log` twice if desired:

```python
plots = extract_plot_files_from_log(log_path)
out_path.write_text("\n".join(plots) + ("\n" if plots else ""), encoding="utf-8")
```

- [x] **Step 5: Run syntax and focused tests**

Run:

```bash
bash -n scripts/workflows/run_event_1hz_pride_workflow.sh
PYTHONPATH=src:. python3 -m unittest tests.test_workflow_summary_status -v
```

Expected: both pass.

---

### Task 3: Add cleanup disable flags through Bash, CLI, and MCP

**Files:**
- Modify: `scripts/workflows/run_event_1hz_pride_workflow.sh`
- Modify: `scripts/workflows/run_event_batch_workflow.sh`
- Modify: `src/gnss_eq/cli.py`
- Modify: `src/gnss_eq/mcp_server.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_mcp_server.py`

- [x] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
    def test_run_batch_forwards_cleanup_disable_flags(self):
        args = argparse.Namespace(
            csv="data/batches/example.csv",
            state_csv=None,
            timeout="120",
            hours="3",
            interval="1",
            run_root="runs",
            obs_root="data/obs",
            normalize_db="data/earthscope_availability/earthscope_1hz.sqlite",
            verified_files_db="",
            post_seconds="200",
            process_jobs=1,
            summary=None,
            max_stations="0",
            skip_download=False,
            force_download=False,
            no_allow_partial=False,
            skip_process=False,
            skip_plot=False,
            cleanup_downloads=False,
            cleanup_pride_workdir=False,
            cleanup_obs=False,
            rerun_ok=False,
            dry_run=False,
        )
        with patch.object(cli, "run_command", return_value=0) as run_command:
            self.assertEqual(cli.cmd_run_batch(args), 0)
        command = run_command.call_args.args[0]
        self.assertIn("--no-cleanup-downloads", command)
        self.assertIn("--no-cleanup-pride-workdir", command)
        self.assertIn("--no-cleanup-obs", command)
```

- [x] **Step 2: Verify CLI test fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliWorkflowCommandTest.test_run_batch_forwards_cleanup_disable_flags -v
```

Expected: FAIL because the CLI does not forward `--no-cleanup-*`.

- [x] **Step 3: Update `src/gnss_eq/cli.py` cleanup arguments**

Replace cleanup argument definitions in `add_common_workflow_flags` with:

```python
    parser.add_argument("--cleanup-downloads", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup-pride-workdir", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup-obs", action=argparse.BooleanOptionalAction, default=True)
```

Update `cmd_run_event` forwarding:

```python
    if not args.cleanup_downloads:
        cmd.append("--no-cleanup-downloads")
    if not args.cleanup_pride_workdir:
        cmd.append("--no-cleanup-pride-workdir")
    if not args.cleanup_obs:
        cmd.append("--no-cleanup-obs")
```

Update `cmd_run_batch` forwarding the same way.

Keep other boolean flags unchanged.

- [x] **Step 4: Add Bash parser support**

In both `scripts/workflows/run_event_1hz_pride_workflow.sh` and `scripts/workflows/run_event_batch_workflow.sh`, add cases:

```bash
    --no-cleanup-downloads)
      CLEANUP_DOWNLOADS="0"
      shift
      ;;
    --no-cleanup-pride-workdir)
      CLEANUP_PRIDE_WORKDIR="0"
      shift
      ;;
    --no-cleanup-obs)
      CLEANUP_OBS="0"
      shift
      ;;
```

In `run_event_batch_workflow.sh`, forward disable flags:

```bash
  [[ "$CLEANUP_DOWNLOADS" == "0" ]] && cmd+=(--no-cleanup-downloads)
  [[ "$CLEANUP_PRIDE_WORKDIR" == "0" ]] && cmd+=(--no-cleanup-pride-workdir)
  [[ "$CLEANUP_OBS" == "0" ]] && cmd+=(--no-cleanup-obs)
```

Remove or keep positive cleanup forwarding only if it remains harmless. The preferred final shape is to forward only non-default disable flags.

- [x] **Step 5: Write failing MCP cleanup test**

In `tests/test_mcp_server.py`, add or update a `run_batch` test so that `cleanup_obs=False` and `cleanup_pride_workdir=False` produce `--no-cleanup-*` in the current pipeline command.

Expected assertion shape:

```python
self.assertIn("--no-cleanup-pride-workdir", command)
self.assertIn("--no-cleanup-obs", command)
```

- [x] **Step 6: Update `src/gnss_eq/mcp_server.py`**

Change `run_batch` signature:

```python
def run_batch(
    csv: str,
    timeout: int = 3600,
    process_jobs: int = 1,
    cleanup_downloads: bool = True,
    cleanup_pride_workdir: bool = True,
    cleanup_obs: bool = True,
    rerun_ok: bool = False,
    source: str = "earthscope",
    use_verified_files: bool = False,
) -> dict[str, Any]:
```

Forward disables:

```python
    if not cleanup_downloads:
        args.append("--no-cleanup-downloads")
    if not cleanup_pride_workdir:
        args.append("--no-cleanup-pride-workdir")
    if not cleanup_obs:
        args.append("--no-cleanup-obs")
```

Include these values in the returned dict:

```python
    result["cleanup_downloads"] = cleanup_downloads
    result["cleanup_pride_workdir"] = cleanup_pride_workdir
    result["cleanup_obs"] = cleanup_obs
```

- [x] **Step 7: Run focused checks**

Run:

```bash
bash -n scripts/workflows/run_event_1hz_pride_workflow.sh scripts/workflows/run_event_batch_workflow.sh
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_mcp_server -v
```

Expected: PASS.

---

### Task 4: Extract richer batch summary generation

**Files:**
- Create: `scripts/workflows/build_event_batch_summary.py`
- Create: `tests/test_event_batch_summary.py`
- Modify: `scripts/workflows/run_event_batch_workflow.sh`

- [x] **Step 1: Write failing tests for richer batch summary**

Create `tests/test_event_batch_summary.py`:

```python
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.workflows import build_event_batch_summary


class EventBatchSummaryTest(unittest.TestCase):
    def test_summary_includes_normalized_and_export_package_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            workflow_reports = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            export_dir = root / "exports" / "normalized-ok-stations-us-nz" / "us-event-a"
            batch_csv.parent.mkdir(parents=True)
            workflow_reports.mkdir(parents=True)
            export_dir.mkdir(parents=True)

            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,OK\n")
            for name in ["event.json", "stations.csv", "waveforms.csv.gz"]:
                (export_dir / name).write_text("x")
            (workflow_reports / "workflow-summary.json").write_text(
                json.dumps(
                    {
                        "status": {
                            "download": "OK",
                            "obs_validation": "OK",
                            "process": "OK",
                            "plot": "OK",
                            "quality": "WARN",
                            "cleanup": "OK",
                            "pride_cleanup": "OK",
                            "obs_cleanup": "OK",
                            "normalized": "OK",
                        },
                        "counts": {
                            "requested_stations": 1,
                            "obs_files": 1,
                            "kin_files": 1,
                            "plot_files": 2,
                            "normalized_stations": 1,
                            "normalized_waveform_rows": 120,
                        },
                        "paths": {
                            "workflow_dir": "@ROOT@/runs/event-a/workflow-20200101T000000Z",
                            "normalized_event_dir": str(export_dir),
                            "normalized_event_grade": "C",
                        },
                        "duration_seconds": 10,
                        "quality": {"summary": {"ok_station_count": 1, "warn_station_count": 0, "fail_station_count": 0}},
                    }
                )
                + "\n"
            )

            rc = build_event_batch_summary.main(
                [
                    "--csv",
                    str(batch_csv),
                    "--summary",
                    str(summary_tsv),
                    "--run-root",
                    str(root / "runs"),
                    "--pipeline-root",
                    str(root),
                ]
            )

            self.assertEqual(rc, 0)
            with summary_tsv.open(newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["normalized_status"], "OK")
            self.assertEqual(rows[0]["normalized_station_count"], "1")
            self.assertEqual(rows[0]["normalized_waveform_rows"], "120")
            self.assertEqual(rows[0]["normalized_event_grade"], "C")
            self.assertEqual(rows[0]["export_package_status"], "COMPLETE")
```

- [x] **Step 2: Verify the test fails**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_event_batch_summary -v
```

Expected: ERROR because `build_event_batch_summary.py` does not exist.

- [x] **Step 3: Implement `build_event_batch_summary.py`**

Create a Python script that:

```python
FIELDS = [
    "event_id",
    "event_time",
    "batch_status",
    "download_status",
    "obs_validation_status",
    "process_status",
    "plot_status",
    "quality_status",
    "quality_ok_stations",
    "quality_warn_stations",
    "quality_fail_stations",
    "cleanup_status",
    "pride_cleanup_status",
    "obs_cleanup_status",
    "normalized_status",
    "normalized_station_count",
    "normalized_waveform_rows",
    "normalized_event_grade",
    "normalized_event_dir",
    "export_package_status",
    "requested_stations",
    "obs_files",
    "kin_files",
    "plot_files",
    "duration_seconds",
    "workflow_dir",
    "summary_json",
]
```

The script must:

```python
def resolve_portable(path_text: str, pipeline_root: Path) -> Path:
    if not path_text:
        return Path()
    if path_text == "@ROOT@":
        return pipeline_root
    if path_text.startswith("@ROOT@/"):
        return pipeline_root / path_text[len("@ROOT@/") :]
    path = Path(path_text)
    return path if path.is_absolute() else pipeline_root / path


def export_package_status(path_text: str, pipeline_root: Path) -> str:
    path = resolve_portable(path_text, pipeline_root)
    if not path:
        return ""
    missing = [name for name in ["event.json", "stations.csv", "waveforms.csv.gz"] if not (path / name).exists()]
    return "COMPLETE" if not missing else "MISSING_" + ",".join(missing)
```

It should select the latest JSON by sorted path:

```python
matches = sorted(run_root.glob(f"{event_id}/workflow-*/reports/workflow-summary.json"))
latest_json = matches[-1] if matches else None
```

- [x] **Step 4: Replace inline batch summary code in Bash**

In `scripts/workflows/run_event_batch_workflow.sh`, replace the large inline Python body in `write_batch_summary` with:

```bash
write_batch_summary() {
  python3 "${PIPELINE_ROOT}/scripts/workflows/build_event_batch_summary.py" \
    --csv "$CSV_FILE" \
    --summary "$SUMMARY_FILE" \
    --run-root "$RUN_ROOT" \
    --pipeline-root "$PIPELINE_ROOT"
}
```

- [x] **Step 5: Run focused checks**

Run:

```bash
bash -n scripts/workflows/run_event_batch_workflow.sh
PYTHONPATH=src:. python3 -m unittest tests.test_event_batch_summary -v
```

Expected: PASS.

---

### Task 5: Make monitor classify attempts by latest summary status

**Files:**
- Modify: `src/gnss_eq/monitor.py`
- Modify: `src/gnss_eq/cli.py` if CLI parser needs new normalized root option
- Test: `tests/test_cli.py` or create `tests/test_monitor_workflow_status.py`

- [x] **Step 1: Write failing monitor test for failed retryable workflow**

Add a test in `tests/test_cli.py` or a new `tests/test_monitor_workflow_status.py`:

```python
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gnss_eq import monitor


class MonitorWorkflowStatusTest(unittest.TestCase):
    def test_failed_workflow_is_retryable_candidate_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "earthscope.sqlite"
            runs_root = root / "runs"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE usgs_m6plus_events_usa ("
                "event_id TEXT, magnitude REAL, event_date TEXT, time_utc TEXT, place TEXT, "
                "existing_data_status TEXT, existing_station_count INTEGER)"
            )
            conn.execute(
                "CREATE TABLE event_earthscope_station_candidates ("
                "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL, radius_km REAL)"
            )
            conn.execute(
                "INSERT INTO usgs_m6plus_events_usa VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("event-a", 6.5, "2020-01-01", "2020-01-01T00:00:00Z", "Test", "", 0),
            )
            for index in range(6):
                conn.execute(
                    "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?, ?)",
                    ("event-a", f"S{index:03d}", 1.0, 2.0, 3.0, 200.0),
                )
            conn.commit()
            conn.close()

            report_dir = runs_root / "event-a" / "workflow-20200101T000000Z" / "reports"
            report_dir.mkdir(parents=True)
            (report_dir / "workflow-summary.json").write_text(
                json.dumps({"status": {"download": "FAIL", "process": "SKIPPED", "normalized": "SKIPPED_WORKFLOW_FAILED"}})
            )

            report = monitor.build_monitor_report(
                source="earthscope",
                limit=20,
                earthscope_db=db,
                earthscope_nonconus_db=root / "missing.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=runs_root,
            )
            source = report["sources"][0]
            self.assertEqual(source["counts"]["failed_retryable"], 1)
            self.assertEqual(source["candidates"][0]["coverage_status"], "FAILED_RETRYABLE")
            self.assertEqual(source["candidates"][0]["priority"], "MEDIUM")
```

- [x] **Step 2: Verify the test fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_monitor_workflow_status -v
```

Expected: FAIL because current code treats any workflow directory as `WORKFLOW_DONE`.

- [x] **Step 3: Implement workflow status reading in `monitor.py`**

Add:

```python
def workflow_status_by_event(runs_root: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    if not runs_root.exists():
        return statuses
    for summary in sorted(runs_root.glob("*/workflow-*/reports/workflow-summary.json")):
        event_id = summary.parts[-4]
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            statuses[event_id] = {"state": "WORKFLOW_ATTEMPTED", "summary_json": str(summary)}
            continue
        status = payload.get("status", {})
        normalized = str(status.get("normalized") or "")
        failing_values = {
            "FAIL",
            "BLOCKED_OBS_VALIDATION",
            "SKIPPED_NO_KIN",
            "SKIPPED_WORKFLOW_FAILED",
            "SKIPPED_QUALITY_FAIL",
        }
        if normalized == "OK":
            state = "WORKFLOW_NORMALIZED_OK"
        elif any(str(status.get(key) or "") in failing_values for key in ["download", "obs_validation", "process", "quality", "normalized"]):
            state = "FAILED_RETRYABLE"
        else:
            state = "WORKFLOW_ATTEMPTED"
        statuses[event_id] = {"state": state, "summary_json": str(summary), "status": status}
    return statuses
```

Update counts:

```python
STATUS_KEYS = {
    "MISSING": "missing",
    "WORKFLOW_ATTEMPTED": "workflow_attempted",
    "WORKFLOW_NORMALIZED_OK": "workflow_normalized_ok",
    "FAILED_RETRYABLE": "failed_retryable",
    "COLLECTED_NORMALIZED": "collected_normalized",
    "BOTH": "both",
}
```

Update `_empty_counts` with new keys:

```python
"workflow_attempted": 0,
"workflow_normalized_ok": 0,
"failed_retryable": 0,
```

Keep `"workflow_done": 0` only if tests or docs still require it as a compatibility alias.

Update `coverage_status` to accept workflow status dict:

```python
def coverage_status(event: dict[str, Any], workflow_statuses: dict[str, dict[str, Any]]) -> str:
    event_id = str(event.get("event_id", ""))
    workflow_state = workflow_statuses.get(event_id, {}).get("state")
    has_collected = event.get("existing_data_status") == "HAS_NORMALIZED"
    if has_collected and workflow_state == "WORKFLOW_NORMALIZED_OK":
        return "BOTH"
    if has_collected:
        return "COLLECTED_NORMALIZED"
    if workflow_state:
        return str(workflow_state)
    return "MISSING"
```

Update `event_priority`:

```python
def event_priority(event: dict[str, Any], status: str) -> str:
    if status not in {"MISSING", "FAILED_RETRYABLE"}:
        return "SKIP"
    stations_200km = int(event.get("stations_200km", 0) or 0)
    if stations_200km >= 20:
        return "HIGH"
    if stations_200km >= 5:
        return "MEDIUM"
    return "LOW"
```

Update candidates:

```python
candidates = [event for event in events if event.get("coverage_status") in {"MISSING", "FAILED_RETRYABLE"}][:limit]
```

- [x] **Step 4: Run focused monitor tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_monitor_workflow_status -v
```

Expected: PASS after updating existing assertions that expected `WORKFLOW_DONE`.

---

### Task 6: Align MCP overview coverage status with monitor semantics

**Files:**
- Modify: `src/gnss_eq/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [x] **Step 1: Write failing MCP coverage test**

Add a test that creates a temp run with `workflow-summary.json` containing `download=FAIL` and checks `earthscope.overview(view="coverage")` returns `coverage_status="FAILED_RETRYABLE"` and non-SKIP priority.

Expected assertion shape:

```python
self.assertEqual(event["coverage_status"], "FAILED_RETRYABLE")
self.assertEqual(event["priority"], "MEDIUM")
```

- [x] **Step 2: Verify the MCP test fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_mcp_server -v
```

Expected: FAIL because MCP currently only checks workflow directory presence.

- [x] **Step 3: Update MCP status helpers**

In `src/gnss_eq/mcp_server.py`, replace `_workflow_event_ids` with `_workflow_status_by_event` using the same logic as `monitor.workflow_status_by_event`.

Update `_coverage_status` and `_event_priority` to match `monitor.py`.

Preferred minimal import option:

```python
from gnss_eq import monitor
```

Then use:

```python
workflow_statuses = monitor.workflow_status_by_event(RUNS_ROOT)
status = monitor.coverage_status(event, workflow_statuses)
priority = monitor.event_priority(event, status)
```

This avoids duplicating status logic.

- [x] **Step 4: Run focused MCP tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_mcp_server -v
```

Expected: PASS.

---

### Task 7: Expand EarthScope preflight to full workflow dependencies

**Files:**
- Modify: `src/gnss_eq/preflight.py`
- Test: `tests/test_preflight.py`

- [x] **Step 1: Write failing preflight test**

In `tests/test_preflight.py`, add assertions that `script_checks()` includes:

```python
"quality script"
"normalizer script"
"summary updater script"
"batch summary builder script"
"final plotter script"
"PRIDE cleaner script"
```

- [x] **Step 2: Verify the test fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_preflight -v
```

Expected: FAIL because `REQUIRED_SCRIPTS` is incomplete.

- [x] **Step 3: Update `REQUIRED_SCRIPTS`**

In `src/gnss_eq/preflight.py`, extend `REQUIRED_SCRIPTS`:

```python
REQUIRED_SCRIPTS = (
    ("run-batch script", SCRIPTS / "workflows" / "run_event_batch_workflow.sh"),
    ("run-event script", SCRIPTS / "workflows" / "run_event_1hz_pride_workflow.sh"),
    ("summary updater script", SCRIPTS / "workflows" / "update_workflow_summary_status.py"),
    ("batch summary builder script", SCRIPTS / "workflows" / "build_event_batch_summary.py"),
    ("downloader script", DOWNLOADER_TOOLS / "download_earthscope_default.sh"),
    ("rinex3 downloader script", DOWNLOADER_TOOLS / "download_earthscope_rinex3.sh"),
    ("PRIDE processor script", PRIDE_TOOLS / "process_event_window.sh"),
    ("PRIDE cleaner script", PRIDE_TOOLS / "cleanup_pride_workdir.sh"),
    ("quality script", SCRIPTS / "quality" / "compute_kin_quality.py"),
    ("normalizer script", SCRIPTS / "normalize" / "normalize_pride_kin_event.py"),
    ("final plotter script", SCRIPTS / "plotting" / "plot_completed_normalized_event.py"),
)
```

If Python scripts are not executable, either mark them executable or adjust `script_checks` so `.py` files require `is_file()` but not executable because workflows call them through `python3`.

Preferred check:

```python
if path.suffix == ".py":
    ok = path.is_file()
else:
    ok = path.is_file() and os.access(path, os.X_OK)
```

- [x] **Step 4: Run focused preflight tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_preflight -v
```

Expected: PASS.

---

### Task 8: Make PRIDE path test independent of external `pdp3`

**Files:**
- Modify: `tests/test_process_event_window_paths.py`

- [x] **Step 1: Inspect the failing test**

Open `tests/test_process_event_window_paths.py` and locate `test_reused_ok_station_status_is_refreshed_to_portable_paths`.

- [x] **Step 2: Add a fake `pdp3` binary to the test temp directory**

Patch the test setup:

```python
fake_bin = root / "bin"
fake_bin.mkdir()
pdp3 = fake_bin / "pdp3"
pdp3.write_text("#!/usr/bin/env bash\nexit 0\n")
pdp3.chmod(0o755)
env = os.environ.copy()
env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
```

Pass `env=env` to `subprocess.run(...)`.

- [x] **Step 3: Run the focused test**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_process_event_window_paths -v
```

Expected: PASS without real `pdp3`.

---

### Task 9: End-to-end verification

**Files:**
- No new files unless tests expose needed fixes.

- [x] **Step 1: Shell syntax validation**

Run:

```bash
bash -n scripts/workflows/current_pipeline.sh \
  scripts/workflows/run_event_batch_workflow.sh \
  scripts/workflows/run_event_1hz_pride_workflow.sh \
  tools/earthscope_downloader/download_earthscope_default.sh \
  tools/earthscope_downloader/download_earthscope_rinex3.sh \
  tools/pride_processor/process_event_window.sh \
  tools/pride_processor/cleanup_pride_workdir.sh
```

Expected: no output and exit code 0.

- [x] **Step 2: Python compile check for touched modules**

Run:

```bash
PYTHONPATH=src:. python3 -m py_compile \
  src/gnss_eq/cli.py \
  src/gnss_eq/mcp_server.py \
  src/gnss_eq/monitor.py \
  src/gnss_eq/preflight.py \
  scripts/workflows/update_workflow_summary_status.py \
  scripts/workflows/build_event_batch_summary.py
```

Expected: no output and exit code 0.

- [x] **Step 3: Focused unit tests**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.test_workflow_summary_status \
  tests.test_event_batch_summary \
  tests.test_cli \
  tests.test_mcp_server \
  tests.test_preflight \
  tests.test_process_event_window_paths \
  -v
```

Expected: PASS.

- [x] **Step 4: Full test suite**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest discover tests
```

Expected: PASS.

- [x] **Step 5: Dry-run smoke test**

Run:

```bash
scripts/workflows/run_event_1hz_pride_workflow.sh \
  --event-id test-event \
  --event-time 2020-01-01T00:00:00Z \
  --stations "ABCD" \
  --dry-run
```

Expected: prints planned download, PRIDE, quality, normalization, and final plot commands. No files are created for the dry run.

- [x] **Step 6: Batch dry-run smoke test with cleanup disabled**

Create a temp CSV outside repository outputs:

```bash
tmpdir="$(mktemp -d)"
printf 'event_id,event_time,stations,status\nsmoke-event,2020-01-01T00:00:00Z,ABCD,\n' > "$tmpdir/batch.csv"
scripts/workflows/run_event_batch_workflow.sh \
  --csv "$tmpdir/batch.csv" \
  --run-root "$tmpdir/runs" \
  --obs-root "$tmpdir/obs" \
  --normalize-db data/earthscope_availability/earthscope_1hz.sqlite \
  --no-cleanup-downloads \
  --no-cleanup-pride-workdir \
  --no-cleanup-obs \
  --dry-run
```

Expected: printed event command includes all three `--no-cleanup-*` flags.

---

### Task 10: Documentation and final review

**Files:**
- Modify: `README.md` or `docs/earthscope-mcp.md` only if implementation changes user-facing commands.

- [x] **Step 1: Update user-facing command docs if cleanup flags changed**

If help text now includes `--no-cleanup-*`, update the EarthScope workflow section in `README.md` or `docs/earthscope-mcp.md` with a short note:

```markdown
Cleanup remains enabled by default. Use `--no-cleanup-obs`, `--no-cleanup-pride-workdir`, or `--no-cleanup-downloads` when preserving intermediates for debugging.
```

- [x] **Step 2: Review changed files**

Run:

```bash
git diff -- scripts/workflows/run_event_1hz_pride_workflow.sh \
  scripts/workflows/run_event_batch_workflow.sh \
  scripts/workflows/update_workflow_summary_status.py \
  scripts/workflows/build_event_batch_summary.py \
  src/gnss_eq/cli.py \
  src/gnss_eq/mcp_server.py \
  src/gnss_eq/monitor.py \
  src/gnss_eq/preflight.py \
  tests
```

Expected: diff only contains planned EarthScope workflow completeness changes.

- [x] **Step 3: Report final outcome**

Final report must include:

- Summary of changed behavior.
- Tests run and results.
- Any tests not run and why.
- Note that existing generated data under `runs/`, `exports/`, and `data/` was not reprocessed.

---

## Self-Review

- Spec coverage: The plan covers status summary correctness, richer batch output, monitor retry semantics, cleanup flag consistency, preflight completeness, and test reliability around external `pdp3`.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: New status names are consistent across monitor and MCP: `MISSING`, `FAILED_RETRYABLE`, `WORKFLOW_ATTEMPTED`, `WORKFLOW_NORMALIZED_OK`, `COLLECTED_NORMALIZED`, `BOTH`.
- Scope check: The plan intentionally excludes GeoNet/CDDIS/GA/RING parked or separate source workflows. Some of the same status-update pattern may later be copied to GeoNet/GA, but not in this pass.
- Risk check: The highest-risk change is monitor semantics because it affects candidate selection. The plan keeps retryable failures visible rather than hiding them as done.
