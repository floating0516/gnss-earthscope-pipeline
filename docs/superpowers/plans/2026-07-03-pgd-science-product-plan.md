# PGD Science Product Plan

## Goal

Make PGD magnitude analysis the next project deliverable. The normalized export, validator, quality contract, run ledger, reports, and GeoNet parity work are treated as input controls for this science layer, not as the final objective.

## Current PGD Baseline

Already implemented:

- `scripts/pgd_magnitude/run_pgd_report.py` packages PGD evaluator output into a reproducible report directory.
- `scripts/pgd_magnitude/evaluate_pgd_magnitude.py` contains the PGD extraction, station/event aggregation, reliability flags, scaling-law evaluation, and calibration helpers.
- PGD report outputs include event rows, station rows, residual rows, formula comparisons, formula breakdowns, magnitude-bin summaries, quality-filtered magnitude-bin summaries, residual outliers, JSON/Markdown summaries, and SVG figures.
- PGD tests cover waveform PGD extraction, normalized-event metadata fallback, station reliability flags, event aggregation, calibration behavior, and report generation.

Current evaluator formula set:

```text
melgar_2015
crowell_2016_gfast
ruhl_2019
```

Primary event-level PGD aggregation method:

```text
median
```

The primary PGD experiment fixes station aggregation to the median and compares the three PGD magnitude formulas. `mean` and `trimmed-mean` are no longer separate PGD methods in the mainline. Secondary sensitivity runs can vary PGD component (`3d` vs `horizontal`), distance mode (`hypocentral` vs `epicentral`), or calibration (`none` vs `leave-one-out-country-linear`), but the station aggregation method remains median.

Latest real-export smoke from the validated normalized dataset:

```text
normalized events: 142
PGD usable unique events: 94
event/formula rows: 282
station/formula rows: 1947
magnitude-bin summary rows: 9
quality-filtered magnitude-bin summary rows: 6
formula comparison rows: 3
formula breakdown rows: 45
method comparison rows: 45 (backward-compatible alias)
release-set rows: 94
release-set ready events: 13
release-set review-required events: 0
release-set excluded events: 81
science release events: 13
science figures: 3
default residual outlier rows: 20
current median baseline recommendation: ruhl_2019
inclusion/exclusion: 142 normalized -> 94 PGD-evaluable -> 48 excluded
current exclusion reason: FILTERED_BY_COUNTRY=48
metadata override: nz-* packages are treated as New Zealand for PGD reporting
```

## Interpretation

The PGD layer is not just another report. It is the science product that should answer:

- Which normalized GNSS earthquake events are actually usable for PGD magnitude analysis?
- Which PGD formula is defensible for this dataset under the single median aggregation method?
- How does performance vary by region, source, magnitude bin, station count, distance, and reliability?
- Which residual outliers are caused by waveform/metadata problems versus expected limitations of the method?
- What event subset can be published as the PGD release set?

## Execution Tasks

### PGD-001: Freeze A Stable PGD Report Run

Run the real normalized export into:

```text
reports/pgd_magnitude/latest/
```

Record:

- exact command
- evaluator parameters
- input export root
- output row counts
- generated figures
- test command used after generation

Acceptance:

```text
reports/pgd_magnitude/latest/science_narrative.md
reports/pgd_magnitude/latest/science_release_events.csv
reports/pgd_magnitude/latest/science_formula_summary.csv
reports/pgd_magnitude/latest/science_figure_manifest.csv
```

The narrative must cover dataset description, PGD method, formula comparison, release set, residual behavior, outlier review status, limitations, and next experiments. The final release-event table contains only `INCLUDED_RELEASE_SET` rows.

Current status: implemented in `run_pgd_report.py`. The current real report writes all four science outputs. `science_release_events.csv` has 13 ready events, `science_formula_summary.csv` has the three median formula rows, `science_figure_manifest.csv` has the three generated SVG figures, and `science_narrative.md` contains all required narrative sections.

```bash
python3 scripts/pgd_magnitude/run_pgd_report.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/latest
```

The output directory contains all expected PGD products and `summary.json` reports `status=OK`.

### PGD-002: Explain PGD Inclusion And Exclusion

Create a PGD-specific inclusion/exclusion report that explains the transition:

```text
validated normalized export -> PGD candidate event -> PGD usable event -> PGD release set
```

Required categories:

- missing distance metadata
- missing/empty waveform rows
- below PGD threshold
- below station-count threshold
- low SNR
- excessive PGD time offset
- filtered by country/source/region selection
- missing magnitude metadata
- usable for PGD

Acceptance:

```text
reports/pgd_magnitude/latest/inclusion_exclusion.csv
reports/pgd_magnitude/latest/inclusion_exclusion.md
```

The report explains why 142 normalized events currently become 94 PGD-usable events.

### PGD-003: Residual Review Table

Convert `residual_outliers.csv` from a raw sorted list into a review product.

Required additional fields:

- review_status
- suspected_cause
- waveform_issue
- station_geometry_issue
- magnitude_metadata_issue
- formula_limitation
- reviewer_note

Initial values can be blank or `UNREVIEWED`, but the table structure must be stable and reproducible.

Acceptance:

```text
reports/pgd_magnitude/latest/residual_review.csv
```

It is sorted by `abs_residual_mw` descending and can be regenerated without destroying existing manually reviewed columns unless explicitly requested.

Current status: implemented in `reports/pgd_magnitude/latest/residual_review.csv`; the real report has 20 rows, default `UNREVIEWED` status, stable review fields, and preserved manual annotations keyed by `(event_id, formula)`.

### PGD-004: Median-Based Formula Comparison

Run and summarize the primary median-based PGD formula comparison:

```text
event aggregation:
  median

formulas:
  melgar_2015
  crowell_2016_gfast
  ruhl_2019
```

Each formula must report:

- event count
- bias Mw
- MAE Mw
- RMSE Mw
- median absolute error Mw
- high/medium reliability event count
- low reliability event count
- residual outlier count above the review threshold

Break the same formula comparison down by:

- formula
- country/region
- source
- magnitude bin
- quality filter
- station-count bin
- distance mode
- PGD component

Acceptance:

```text
reports/pgd_magnitude/latest/formula_breakdown.md
reports/pgd_magnitude/latest/formula_breakdown.csv
reports/pgd_magnitude/latest/formula_comparison.csv
```

`formula_breakdown.*` is the canonical product name. `method_comparison.*` aliases are no longer part of the PGD report contract because the station aggregation method has been unified to median.

The report recommends a default PGD formula under the median aggregation method or states why the dataset is not ready for one. The recommendation must call out whether the formula choice changes by region or magnitude bin.

### PGD-005: PGD Release-Set Gate

Define a machine-readable PGD release-set filter.

Candidate criteria:

- minimum usable station count
- HIGH/MEDIUM reliability only
- maximum median distance
- minimum median PGD SNR
- maximum PGD time offset
- residual sanity threshold for review, not automatic exclusion

Acceptance:

```text
reports/pgd_magnitude/latest/release_set.csv
reports/pgd_magnitude/latest/release_set_summary.json
```

The release-set logic is documented and can be re-run from normalized exports.

Current status: implemented in `run_pgd_report.py`. The default hard gate uses at least 3 usable stations, HIGH/MEDIUM PGD reliability, median PGD SNR >= 3.0, and median distance <= 300 km. The residual threshold is a review trigger, not an automatic exclusion. On the current real report, `ruhl_2019` has 94 release-set rows: 13 ready events, 0 review-required candidates, and 81 hard-gate exclusions.

### PGD-006: Final PGD Narrative

Produce the human-facing science narrative:

- dataset description
- PGD method
- formula comparison
- residual behavior
- outlier review status
- release-set definition
- limitations and next experiments

Acceptance:

```text
reports/pgd_magnitude/latest/pgd_science_report.md
```

The report references generated CSV/JSON/figure outputs rather than relying on manual counting.

## What Not To Do In This Phase

- Do not make GeoNet the headline deliverable; use it only where it increases PGD-ready event coverage.
- Do not add new data sources before the PGD inclusion/exclusion and residual review are understood.
- Do not tune PGD formulas only to improve headline metrics without documenting the validation split or reliability filters.
- Do not treat all 142 normalized events as PGD-ready; the PGD evaluator has stricter requirements.

## Verification

Run focused PGD tests:

```bash
PYTHONPATH=src python3 -m unittest \
  tests/test_pgd_magnitude_evaluator.py \
  tests/test_run_pgd_report.py
```

Run full local verification after PGD product changes:

```bash
PYTHONPATH=src python3 -m unittest discover tests
bash scripts/ops/check_shell_syntax.sh
bash scripts/ops/smoke_test_offline.sh
```
