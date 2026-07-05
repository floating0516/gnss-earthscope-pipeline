# PGD Benchmark Package

This is the compact, four-stage PGD benchmark package for formula-baseline and later ML comparison work.

## Four-Stage Workflow

1. Compute PGD station/event features from normalized waveforms.
2. Estimate event magnitude with the three PGD formulas.
3. Compare each formula estimate to the catalog magnitude and record residuals.
4. Package the benchmark tables for downstream analysis.

The package uses one station aggregation method: `median`. The labels `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas/scaling laws, not station aggregation methods.

## Files

- `events.csv`: event/formula rows from the PGD report.
- `stations.csv`: station/formula PGD feature rows.
- `formula_errors.csv`: formula-level event residual rows copied from `events.csv` for explicit benchmark use.
- `formula_summary.csv`: overall per-formula error metrics.
- `summary.json`: machine-readable benchmark summary.
- `filter_benchmark/`: station-level filter scenarios for amplitude, SNR, distance, QUALITY, and STRICT gates.
- `filter_benchmark/interpretation/`: PGD Benchmark Interpretation Markdown, JSON, and SVG figures.

## Current Counts

- Status: `OK`
- Unique events: 142
- Formula error rows: 426
- Station rows: 2535
- Recommended baseline formula: `ruhl_2019`
- Country scope: all normalized export countries
- Countries: Americas, Antigua and Barbuda, Costa Rica, Cuba, El Salvador, Guadeloupe, Guatemala, Haiti, Jamaica, Mexico, New Zealand, Nicaragua, Panama, Puerto Rico, United States, Venezuela

## Output Paths

- `events`: `reports/pgd_magnitude/benchmark/latest/events.csv`
- `stations`: `reports/pgd_magnitude/benchmark/latest/stations.csv`
- `formula_errors`: `reports/pgd_magnitude/benchmark/latest/formula_errors.csv`
- `formula_summary`: `reports/pgd_magnitude/benchmark/latest/formula_summary.csv`

## Filter Benchmark Paths

- `root`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark`
- `scenario_formula_summary`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/scenario_formula_summary.csv`
- `scenario_event_errors`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/scenario_event_errors.csv`
- `scenario_exclusions`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/scenario_exclusions.csv`
- `summary`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/summary.json`
- `readme`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/README.md`

## PGD Benchmark Interpretation Paths

- `root`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation`
- `markdown`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation/pgd_benchmark_interpretation.md`
- `json`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation/pgd_benchmark_interpretation.json`
- `figures_dir`: `reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation/figures`
