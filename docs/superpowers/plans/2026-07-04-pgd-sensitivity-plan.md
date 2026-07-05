# PGD Sensitivity Plan

## Goal
Test whether the current median-based PGD formula recommendation is stable under nearby scientific choices without reopening station aggregation as a method dimension.

The fixed baseline remains:

```text
station_aggregation = median
formulas = melgar_2015, crowell_2016_gfast, ruhl_2019
```

Sensitivity scenarios vary only:

```text
pgd_component = 3d | horizontal
distance = hypocentral | epicentral
calibration = none | leave-one-out-country-linear
```

## Deliverable
Add a reproducible command:

```bash
python3 scripts/pgd_magnitude/run_pgd_sensitivity.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/sensitivity/latest
```

The command writes:

```text
sensitivity_summary.csv
sensitivity_recommendations.csv
sensitivity_formula_deltas.csv
sensitivity_interpretation.md
summary.json
summary.md
```

## Required Contract
- Station aggregation is always `median`.
- Each scenario produces one summary row per PGD formula.
- Each summary row includes scenario id, component, distance mode, calibration, formula, event count, bias, MAE, RMSE, median absolute error, high/medium reliability count, low reliability count, and residual outlier count.
- Recommendations are selected per scenario by lowest MAE, then RMSE, then median absolute error.
- The Markdown report explicitly states whether the baseline recommended formula remains stable across scenarios.
- The script must use the existing PGD evaluator and formula logic instead of duplicating scaling laws.
- Raw event evaluation is cached by component, distance mode, station aggregation, country set, and PGD/quality thresholds. Calibration is applied after cache retrieval, so `baseline` and `calibrated` share the same raw waveform pass.
- `sensitivity_formula_deltas.csv` compares every scenario/formula row against the baseline scenario for the same formula, including rank changes and MAE/RMSE/median-absolute-error/outlier deltas.
- `sensitivity_interpretation.md` summarizes formula switches and reports how much the switched-to formula improves MAE relative to the baseline formula inside that scenario.

## Scenario Set
Default scenarios:

```text
baseline:        3d,         hypocentral, none
horizontal:      horizontal, hypocentral, none
epicentral:      3d,         epicentral,   none
calibrated:      3d,         hypocentral, leave-one-out-country-linear
```

This is intentionally smaller than a full 2x2x2 grid. It tests one scientific degree of freedom at a time and keeps the report interpretable.

## Verification
Focused tests:

```bash
PYTHONPATH=src python3 -m unittest tests/test_run_pgd_sensitivity.py
```

PGD regression tests:

```bash
PYTHONPATH=src python3 -m unittest \
  tests/test_pgd_magnitude_evaluator.py \
  tests/test_run_pgd_report.py \
  tests/test_run_pgd_sensitivity.py
```

Full suite:

```bash
PYTHONPATH=src python3 -m unittest discover tests
```

Real report:

```bash
python3 scripts/pgd_magnitude/run_pgd_sensitivity.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/sensitivity/latest
```
