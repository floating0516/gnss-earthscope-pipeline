# PGD Benchmark-First Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default PGD workflow a four-stage benchmark package: compute PGD, evaluate the three formulas, summarize catalog-magnitude errors, and package the benchmark for later ML work.

**Architecture:** Add a small wrapper, `run_pgd_benchmark_bundle.py`, that delegates PGD extraction and formula math to the existing `run_pgd_report.py`. The wrapper copies/renames only benchmark-relevant products into `reports/pgd_magnitude/benchmark/latest`, writes a compact `summary.json` and `README.md`, and leaves the existing 24-stage release/review bundle available as an optional path.

**Tech Stack:** Python standard library, existing PGD report script, `unittest`, CSV/JSON/Markdown outputs.

---

### Task 1: Benchmark Bundle CLI

**Files:**
- Create: `scripts/pgd_magnitude/run_pgd_benchmark_bundle.py`
- Test: `tests/test_run_pgd_benchmark_bundle.py`

- [x] Write a failing test that expects the benchmark bundle to run only `run_pgd_report.py`, create benchmark outputs, and avoid release/review stages.
- [x] Run the focused test and confirm it fails because `run_pgd_benchmark_bundle.py` is missing.
- [x] Implement the wrapper with `--export-root`, `--out-dir`, `--work-dir`, `--out-json`, and pass-through PGD options.
- [x] Copy benchmark files from the report work directory into the benchmark directory: `events.csv`, `stations.csv`, `formula_errors.csv`, `formula_summary.csv`, and `summary.json`.
- [x] Write a compact `README.md` describing the four-stage benchmark and the median-only formula contract.
- [x] Run focused tests and compile the new script.

### Task 2: Documentation And Planning

**Files:**
- Modify: `docs/pgd_magnitude_report.md`
- Modify: `.planning/2026-07-03-mainline-roadmap/task_plan.md`
- Modify: `.planning/2026-07-03-mainline-roadmap/progress.md`
- Modify: `.planning/2026-07-03-mainline-roadmap/findings.md`
- Modify: `tests/test_repo_allowlist.py`

- [x] Update PGD documentation so the benchmark bundle is the default command.
- [x] Keep the 24-stage PGD science/release bundle documented as optional release-review tooling.
- [x] Add repository allowlist coverage for the new benchmark script.
- [x] Add Phase 55 to the persistent planning files.
- [x] Run focused tests, full unittest, and `git diff --check`.

### Task 3: Real Benchmark Product

**Files:**
- Generate: `reports/pgd_magnitude/benchmark/latest/`

- [x] Run the benchmark bundle on the real normalized export.
- [x] Verify the real benchmark package contains the compact output set.
- [x] Verify `station_aggregation=median` in benchmark products and no current benchmark product exposes `method_*` names.
