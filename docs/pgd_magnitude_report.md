# PGD Magnitude Report

The PGD report target turns normalized event packages into a reproducible peak-ground-displacement magnitude evaluation. It uses `scripts/pgd_magnitude/evaluate_pgd_magnitude.py` for the actual PGD extraction and magnitude scaling laws; `run_pgd_report.py` is the product wrapper that standardizes outputs.

## Default Benchmark Command

Use the lightweight benchmark runner as the default PGD workflow:

```bash
python3 scripts/pgd_magnitude/run_pgd_benchmark_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/benchmark/latest
```

This command keeps the core PGD benchmark workflow to four stages:

```text
1. compute PGD station/event features
2. estimate event magnitude with the three PGD formulas
3. compare each estimate to catalog magnitude
4. package the benchmark tables for downstream analysis and ML baselines
```

The benchmark package writes:

```text
reports/pgd_magnitude/benchmark/latest/
  events.csv
  stations.csv
  formula_errors.csv
  formula_summary.csv
  summary.json
  README.md
  filter_benchmark/
    scenario_formula_summary.csv
    scenario_event_errors.csv
    scenario_exclusions.csv
    summary.json
    README.md
    interpretation/
      pgd_benchmark_interpretation.md
      pgd_benchmark_interpretation.json
      figures/
```

`formula_errors.csv` is the main formula-baseline table: one row per event/formula with catalog magnitude, estimated magnitude, residual, absolute residual, usable station count, SNR, and distance context. `formula_summary.csv` gives the overall per-formula error metrics. The station aggregation method is fixed to `median`; `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas/scaling laws, not separate aggregation methods.

The default bundle also builds the filter benchmark and interpretation products from the compact station table. Those companion steps do not rescan waveform files.

By default, the benchmark runner includes every country/region discovered in complete normalized event packages under `--export-root`. Use `--countries` only when you intentionally want a subset:

```bash
python3 scripts/pgd_magnitude/run_pgd_benchmark_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/benchmark/latest \
  --countries "United States" "New Zealand" "Mexico"
```

## Filter Benchmark

The default benchmark bundle runs this step automatically. To rerun only the station-level filter comparison, use:

```bash
python3 scripts/pgd_magnitude/build_pgd_filter_benchmark.py \
  --benchmark-dir reports/pgd_magnitude/benchmark/latest \
  --out-dir reports/pgd_magnitude/benchmark/latest/filter_benchmark
```

This command consumes `reports/pgd_magnitude/benchmark/latest/stations.csv`; it does not rescan waveform files. It writes:

```text
reports/pgd_magnitude/benchmark/latest/filter_benchmark/
  scenario_formula_summary.csv
  scenario_event_errors.csv
  scenario_exclusions.csv
  summary.json
  README.md
```

The standard scenarios include no filter, PGD amplitude thresholds (`>=1 cm`, `>=2 cm`, `>=5 cm`), SNR thresholds (`>=3`, `>=5`), distance thresholds (`<=300 km`, `<=200 km`), and two station-count-gated sets:

```text
quality_snr3_time300_dist300_min3sta
strict_snr5_time300_dist300_min3sta
```

Use the filter benchmark to compare error reduction against sample loss. The strict set is a high-confidence reference set, not a replacement for the full benchmark.

The default benchmark bundle also runs this step automatically. To rerun only the compact interpretation report and figures, use:

```bash
python3 scripts/pgd_magnitude/build_pgd_benchmark_interpretation.py \
  --filter-dir reports/pgd_magnitude/benchmark/latest/filter_benchmark \
  --out-dir reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation
```

This writes:

```text
reports/pgd_magnitude/benchmark/latest/filter_benchmark/interpretation/
  pgd_benchmark_interpretation.md
  pgd_benchmark_interpretation.json
  figures/
    scenario_mae_rmse.svg
    event_count_vs_mae.svg
    estimated_vs_catalog_all.svg
    estimated_vs_catalog_quality.svg
    estimated_vs_catalog_strict.svg
    residual_diagnostics.svg
```

Read `ALL` as the coverage baseline, `QUALITY` as the main formula-comparison tier, and `STRICT` as the high-confidence reference tier. The current real benchmark shows that PGD amplitude thresholds at 1 cm and 2 cm do not materially improve the error; the useful quality gate combines SNR, peak time, distance, and a minimum station count. The station aggregation method remains fixed to `median`.

## Optional Release/Review Bundle

The larger PGD science bundle remains available when the goal is release readiness, manual review, or external-review handoff:

```bash
python3 scripts/pgd_magnitude/run_pgd_science_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --release-dir reports/pgd_magnitude/release/latest
```

The optional release/review bundle runs the median-only baseline report, residual review merge, residual triage, review template, sensitivity report, interpretation report, release package, release review dashboard, release decision report, reviewed release-set view, residual review worklist, release-blocking review starter, release-readiness report, formula test matrix, blocker analysis, blocker decision guide, recommended-formula release status, baseline narrative handoff, baseline science narrative, comparison-formula review packet summary, review briefing, release README, release blocker review prompt pack, and external review handoff manifest. It writes `pgd_science_bundle_summary.json` with the command list, return codes, outputs, and failed stage if any child command fails. This path is intentionally heavier than the default benchmark workflow.

If manual residual annotations already exist, pass them explicitly:

```bash
python3 scripts/pgd_magnitude/run_pgd_science_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --release-dir reports/pgd_magnitude/release/latest \
  --annotations reports/pgd_magnitude/latest/residual_review_annotations.csv
```

If reviewers filled a focused release-blocking starter file instead, pass it through the bundle with `--starter-annotations`. This option is mutually exclusive with `--annotations`. The bundle first runs `validate_release_starter_annotations.py --require-complete --strict` against `release_blocking_review_starter.csv`; only a valid completed starter is then forwarded to `manage_residual_review.py --starter-annotations`:

```bash
python3 scripts/pgd_magnitude/run_pgd_science_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --release-dir reports/pgd_magnitude/release/latest \
  --starter-annotations <completed-starter.csv>
```

Use `--skip-release-package` and `--skip-release-review` only for report-only reruns. The individual commands remain available for targeted reruns. To rebuild only the compact release package:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_package.py \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --out-dir reports/pgd_magnitude/release/latest
```

The release package does not rescan waveform data. It packages the ready-event table, median formula comparison, sensitivity recommendations, residual triage summary, full residual-review evidence queue, per-row residual review packets, figure manifest, field dictionary, formula/aggregation note, formula coefficients/provenance, and bundle provenance into a small report directory. It rejects upstream products that do not use `station_aggregation=median`; the three-way comparison in the release package is formula-only, not a comparison of station aggregation methods.

After building the release package, generate the residual-review dashboard:

```bash
python3 scripts/pgd_magnitude/build_residual_review_dashboard.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The dashboard reads the release package's residual evidence, packet index, and annotation starter. It writes `residual_review_dashboard.csv`, `residual_review_dashboard.json`, and `residual_review_dashboard.md` without changing the evidence or starter files.

After a dashboard exists, generate the residual-review decision report:

```bash
python3 scripts/pgd_magnitude/build_residual_review_decision_report.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The decision report checks whether manual review status and `accepted_for_release` are consistent. It writes `residual_review_decision_report.csv`, `residual_review_decision_report.json`, and `residual_review_decision_report.md`; conflicting manual decisions return `INVALID` without mutating release evidence, starter, dashboard, or release-set products.

Then build the reviewed release-set view:

```bash
python3 scripts/pgd_magnitude/build_reviewed_release_set.py \
  --release-dir reports/pgd_magnitude/release/latest
```

This view starts from `release_events.csv`, removes events with pending, invalid, or excluded residual-review decisions, and adds rows explicitly accepted by review. It writes `reviewed_release_events.csv`, `reviewed_release_blockers.csv`, `reviewed_release_summary.json`, and `reviewed_release_summary.md`.

After the reviewed release set exists, generate the residual-review worklist:

```bash
python3 scripts/pgd_magnitude/build_residual_review_worklist.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The worklist combines the dashboard, decision report, and reviewed-release blockers into `residual_review_worklist.csv`, `residual_review_worklist.json`, and `residual_review_worklist.md`. It is a review aid only: it suggests status/cause/action fields and points to review packets, but it does not mutate evidence, annotation starters, dashboard rows, decision rows, or reviewed release products.

After the worklist exists, generate the focused release-blocking review starter:

```bash
python3 scripts/pgd_magnitude/build_release_blocking_review_starter.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The focused starter writes `release_blocking_review_starter.csv`, `release_blocking_review_starter.json`, and `release_blocking_review_starter.md`. By default it includes only release-blocking pending or invalid worklist rows; use `--include-nonblocking` to include every worklist row. It keeps suggested fields separate from blank manual fields so reviewers can fill a copy and import it with `run_pgd_science_bundle.py --starter-annotations` or, for a targeted merge only, `manage_residual_review.py --starter-annotations`.

Before importing a completed starter, validate the filled copy:

```bash
python3 scripts/pgd_magnitude/validate_release_starter_annotations.py \
  --release-dir reports/pgd_magnitude/release/latest \
  --completed-starter <completed-starter.csv> \
  --require-complete \
  --strict
```

The validation step writes `release_starter_validation.csv`, `release_starter_validation.json`, and `release_starter_validation.md`. It checks that release-blocking rows have terminal manual decisions, that `manual_review_status` agrees with `accepted_for_release`, and that completed rows match the focused starter keys when `--strict` is used. It does not mutate evidence, starter, review, decision, or release-set products.

After the focused starter exists, generate the release-readiness report:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_readiness_report.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The readiness report writes `pgd_release_readiness.json` and `pgd_release_readiness.md`. It reports `READY`, `BLOCKED_ON_REVIEW`, or `INVALID_INPUTS` from existing release products and lists next actions; it does not make or overwrite manual scientific review decisions.

After readiness is available, build the formula test matrix:

```bash
python3 scripts/pgd_magnitude/build_pgd_formula_test_matrix.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The formula test matrix writes `pgd_formula_test_matrix.csv`, `pgd_formula_test_matrix.json`, and `pgd_formula_test_matrix.md`. It reads existing release-package products and summarizes each PGD formula's median-aggregation baseline rank, residual metrics, sensitivity wins, release-review blockers, release role, and test status. It rejects missing or non-`median` station aggregation in formula/sensitivity inputs.

Then build the release blocker analysis:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_blocker_analysis.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The blocker analysis writes `pgd_release_blocker_analysis.csv`, `pgd_release_blocker_analysis.json`, and `pgd_release_blocker_analysis.md`. It focuses on release-blocking worklist rows, separates recommended-formula blockers from comparison-formula blockers, preserves packet paths and review focus, and does not write manual review decisions.

To prepare reviewer-filled starter rows, build the decision guide:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_blocker_decision_guide.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The decision guide writes `pgd_release_blocker_decision_guide.csv`, `pgd_release_blocker_decision_guide.json`, and `pgd_release_blocker_decision_guide.md`. It lists allowed terminal manual statuses, `accepted_for_release` consistency rules, packet paths, and pre-decision checks for each blocker, while keeping all manual review fields blank.

After the blocker decision guide exists, build the recommended-formula release status:

```bash
python3 scripts/pgd_magnitude/build_pgd_recommended_formula_release_status.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The recommended-formula status report writes `pgd_recommended_formula_release_status.csv`, `pgd_recommended_formula_release_status.json`, and `pgd_recommended_formula_release_status.md`. It separates the recommended baseline formula's readiness from comparison-formula review blockers. This report is read-only: it does not write manual review decisions, does not clear comparison-formula blockers, and keeps station aggregation fixed to `median`.

Finally, build the baseline narrative handoff:

```bash
python3 scripts/pgd_magnitude/build_pgd_baseline_narrative_handoff.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The baseline handoff writes `pgd_baseline_narrative_handoff.json` and `pgd_baseline_narrative_handoff.md`. It states that PGD has one station aggregation method (`median`), that `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas under that method, and that baseline narrative use of the recommended formula is separate from pending comparison-formula review. It does not write manual decisions.

Then build the baseline science narrative:

```bash
python3 scripts/pgd_magnitude/build_pgd_baseline_science_narrative.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The baseline science narrative writes `pgd_baseline_science_narrative.json` and `pgd_baseline_science_narrative.md`. It turns the handoff, formula comparison, sensitivity recommendations, readiness report, and reviewed-release summary into a release-level narrative draft for the baseline formula. It keeps the station aggregation method fixed to `median`, treats the three labels as formulas only, preserves the sensitivity caveat and pending comparison-formula review, and does not write manual decisions.

Then build the comparison-formula review packet summary:

```bash
python3 scripts/pgd_magnitude/build_pgd_comparison_formula_review_packet_summary.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The comparison-formula review packet summary writes `pgd_comparison_formula_review_packet_summary.csv`, `pgd_comparison_formula_review_packet_summary.json`, and `pgd_comparison_formula_review_packet_summary.md`. It gives one compact row per release-blocking comparison-formula packet, joins formula-test-matrix context, checks packet existence, keeps manual review fields read-only, and rejects non-`median` release context.

Then build the review briefing:

```bash
python3 scripts/pgd_magnitude/build_pgd_review_briefing.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The review briefing writes `pgd_review_briefing.json` and `pgd_review_briefing.md`. It gives reviewers or other models one read-only entry point for the current PGD release state: baseline formula, median aggregation contract, release readiness, comparison-formula blocker counts, exact starter and packet files to review, allowed manual review statuses, and the validation/import commands. It does not write manual decisions.

Then build the top-level release README:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_readme.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The release README writes `README.md` and `release_readme.json` in the release directory. It is the first file to hand to reviewers or other models: it summarizes the current release state, median-only aggregation contract, baseline formula, blockers, key files, and completed-starter validation/import commands. It reads existing release products only and does not write manual decisions.

Then build the release blocker review prompt pack:

```bash
python3 scripts/pgd_magnitude/build_pgd_release_blocker_review_prompt.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The prompt pack writes `pgd_release_blocker_review_prompt.md` and `pgd_release_blocker_review_prompt.json`. It is a read-only handoff artifact for another model or reviewer: it includes the median-only aggregation contract, the three formula labels, release-blocking rows, packet paths, blank starter rows, allowed terminal statuses, manual fields, and completed-starter validation/import commands. It does not write manual decisions or clear blockers.

Then build the external review handoff index:

```bash
python3 scripts/pgd_magnitude/build_pgd_external_review_handoff.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The external review handoff writes `pgd_external_review_handoff.md`, `pgd_external_review_handoff_manifest.json`, and `pgd_external_review_handoff_manifest.csv`. It is a read-only manifest for handing the release directory to another model or reviewer: it lists the start-here files, prompt pack, focused starter, packet index, per-row packets, file sizes, SHA256 hashes, and the remaining blocker rows. It rejects non-`median` release context and missing required handoff files, but it does not copy large data, rescan waveforms, write manual decisions, or clear blockers.

The individual commands remain available for targeted reruns. The baseline report command is:

```bash
python3 scripts/pgd_magnitude/run_pgd_report.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --out-dir reports/pgd_magnitude/latest
```

Residual review annotations are managed as a separate step so the generated base review queue is not edited in place:

```bash
python3 scripts/pgd_magnitude/manage_residual_review.py \
  --review-csv reports/pgd_magnitude/latest/residual_review.csv \
  --out-csv reports/pgd_magnitude/latest/residual_review_annotated.csv \
  --out-json reports/pgd_magnitude/latest/residual_review_summary.json \
  --out-md reports/pgd_magnitude/latest/residual_review_summary.md \
  --strict
```

Automatic triage can then be generated before manual review. It appends suggested status/cause/action fields, but it does not overwrite `review_status` or other manual annotation fields:

```bash
python3 scripts/pgd_magnitude/triage_residual_review.py \
  --review-csv reports/pgd_magnitude/latest/residual_review_annotated.csv \
  --events-csv reports/pgd_magnitude/latest/events.csv \
  --release-set-csv reports/pgd_magnitude/latest/release_set.csv \
  --out-csv reports/pgd_magnitude/latest/residual_review_triage.csv \
  --out-json reports/pgd_magnitude/latest/residual_review_triage_summary.json \
  --out-md reports/pgd_magnitude/latest/residual_review_triage.md
```

```bash
python3 scripts/pgd_magnitude/build_residual_review_template.py \
  --review-csv reports/pgd_magnitude/latest/residual_review_annotated.csv \
  --events-csv reports/pgd_magnitude/latest/events.csv \
  --release-set-csv reports/pgd_magnitude/latest/release_set.csv \
  --out-csv reports/pgd_magnitude/latest/residual_review_annotations_template.csv \
  --out-md reports/pgd_magnitude/latest/residual_review_guide.md
```

After manual annotations are filled, merge them back with strict key checking:

```bash
python3 scripts/pgd_magnitude/manage_residual_review.py \
  --review-csv reports/pgd_magnitude/latest/residual_review.csv \
  --annotations reports/pgd_magnitude/latest/residual_review_annotations.csv \
  --out-csv reports/pgd_magnitude/latest/residual_review_annotated.csv \
  --out-json reports/pgd_magnitude/latest/residual_review_summary.json \
  --out-md reports/pgd_magnitude/latest/residual_review_summary.md \
  --strict
```

The report-level interpretation layer combines baseline formula comparison, sensitivity, release-set, and residual-triage outputs:

```bash
python3 scripts/pgd_magnitude/build_pgd_interpretation_report.py \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --out-json reports/pgd_magnitude/latest/pgd_interpretation.json \
  --out-md reports/pgd_magnitude/latest/pgd_interpretation.md
```

## Outputs

```text
reports/pgd_magnitude/latest/
  events.csv
  stations.csv
  residuals.csv
  residual_outliers.csv
  residual_review.csv
  residual_review_annotated.csv
  residual_review_summary.json
  residual_review_summary.md
  residual_review_triage.csv
  residual_review_triage_summary.json
  residual_review_triage.md
  residual_review_annotations_template.csv
  residual_review_guide.md
  release_set.csv
  release_set_summary.json
  science_narrative.md
  science_release_events.csv
  science_formula_summary.csv
  science_figure_manifest.csv
  pgd_interpretation.json
  pgd_interpretation.md
  pgd_science_bundle_summary.json
  formula_comparison.csv
  formula_breakdown.csv
  formula_breakdown.md
  formula_summary.csv
  formula_summary_raw.csv
  formula_summary_by_magnitude_bin.csv
  formula_summary_quality_filtered_by_magnitude_bin.csv
  inclusion_exclusion.csv
  inclusion_exclusion.md
  summary.json
  summary.md
  figures/
    estimated_vs_usgs_by_region.svg
    formula_mae_by_region.svg
    residual_vs_usgs_magnitude.svg

reports/pgd_magnitude/release/latest/
  release_package_summary.json
  release_package.md
  release_events.csv
  formula_comparison.csv
  sensitivity_recommendations.csv
  residual_triage_top.csv
  residual_review_evidence.csv
  residual_review_evidence.json
  residual_review_evidence.md
  residual_review_annotations_starter.csv
  residual_review_annotations_starter.md
  residual_review_checklist.md
  residual_review_packet_index.csv
  residual_review_packet_index.md
  residual_review_packets/
  residual_review_dashboard.csv
  residual_review_dashboard.json
  residual_review_dashboard.md
  residual_review_decision_report.csv
  residual_review_decision_report.json
  residual_review_decision_report.md
  reviewed_release_events.csv
  reviewed_release_blockers.csv
  reviewed_release_summary.json
  reviewed_release_summary.md
  residual_review_worklist.csv
  residual_review_worklist.json
  residual_review_worklist.md
  release_blocking_review_starter.csv
  release_starter_validation.csv
  release_starter_validation.json
  release_starter_validation.md
  pgd_release_readiness.json
  pgd_release_readiness.md
  pgd_formula_test_matrix.csv
  pgd_formula_test_matrix.json
  pgd_formula_test_matrix.md
  pgd_release_blocker_analysis.csv
  pgd_release_blocker_analysis.json
  pgd_release_blocker_analysis.md
  pgd_release_blocker_decision_guide.csv
  pgd_release_blocker_decision_guide.json
  pgd_release_blocker_decision_guide.md
  pgd_comparison_formula_review_packet_summary.csv
  pgd_comparison_formula_review_packet_summary.json
  pgd_comparison_formula_review_packet_summary.md
  release_blocking_review_starter.json
  release_blocking_review_starter.md
  pgd_release_blocker_review_prompt.md
  pgd_release_blocker_review_prompt.json
  pgd_external_review_handoff.md
  pgd_external_review_handoff_manifest.csv
  pgd_external_review_handoff_manifest.json
  figure_manifest.csv
  package_manifest.csv
  data_dictionary.csv
  data_dictionary.md
  formula_aggregation_note.md
  formula_coefficients.csv
  formula_coefficients.json
  formula_provenance.md
```

## Interpretation

- `events.csv` has one row per event and PGD scaling formula.
- `stations.csv` has station-level PGD and reliability rows.
- `residuals.csv` is the compact event/formula residual table for review.
- `residual_outliers.csv` is the same residual row shape sorted by largest absolute residual first. Use `--outlier-limit` to control its length.
- `residual_review.csv` adds stable manual-review columns to the largest residual rows. Regeneration preserves existing annotations keyed by `(event_id, formula)`.
- `residual_review_annotated.csv` is the merged review table produced by `manage_residual_review.py`; it keeps the generated queue order and overlays manual annotations keyed by `(event_id, formula)`.
- `residual_review_summary.json` and `residual_review_summary.md` summarize review status counts, suspected-cause counts, rows still pending review, and any validation errors.
- `residual_review_triage.csv`, `residual_review_triage_summary.json`, and `residual_review_triage.md` add automatic priority/status/cause/action suggestions. They are review aids only and do not mutate manual review fields.
- `residual_review_annotations_template.csv` is a pending-row annotation worksheet generated from `residual_review_annotated.csv`; it adds formula residual comparisons, release-gate context, SNR/distance/station-count context, and suggested checks.
- `residual_review_guide.md` is the companion human-readable review queue and status/cause glossary.
- `release_set.csv` applies the PGD release gate to the recommended formula, one event per row.
- `release_set_summary.json` records the release gate thresholds, candidate counts, ready counts, review-required counts, and exclusion reasons.
- `science_narrative.md` is the human-facing PGD science narrative with dataset, median aggregation, formula, release-set, residual, limitation, and next-experiment sections.
- `science_release_events.csv` is the final ready-event table for the release set.
- `science_formula_summary.csv` is the report-facing copy of the overall median formula comparison.
- `science_figure_manifest.csv` lists generated science figures and their role in the narrative.
- `pgd_interpretation.json` and `pgd_interpretation.md` combine baseline formula recommendation, sensitivity stability, release-set counts, and residual triage into a release-facing interpretation summary.
- `formula_comparison.csv` is the primary median-aggregation comparison across the three PGD formulas.
- `formula_breakdown.csv` and `formula_breakdown.md` add formula comparisons by country, region, magnitude bin, reliability, and source where available. These are formula breakdowns under the single median station aggregation method, not separate aggregation methods.
- `formula_summary.csv` and `formula_summary_raw.csv` summarize residual metrics by country/formula, using median station aggregation.
- `formula_summary_by_magnitude_bin.csv` groups residual metrics by magnitude bin and formula.
- `formula_summary_quality_filtered_by_magnitude_bin.csv` repeats that table after keeping only HIGH/MEDIUM PGD reliability events.
- The direct evaluator `evaluate_pgd_magnitude.py` follows the same naming contract for TSV outputs: `formula_summary*.tsv` are the only formula-summary products.
- `inclusion_exclusion.csv` and `inclusion_exclusion.md` explain how normalized events become PGD-evaluable events, including country filters, missing metadata, empty waveforms, and PGD threshold failures.
- `summary.json` and `summary.md` record row counts, parameters, formula summary, low-reliability events, and generated figures.
- `reports/pgd_magnitude/release/latest/` is the compact handoff package for the current PGD release set. It includes the ready events, formula comparison, sensitivity caveat source rows, top residual triage rows, figure manifest, and a package manifest that points back to source products.
- `reports/pgd_magnitude/release/latest/residual_review_evidence.csv`, `residual_review_evidence.json`, and `residual_review_evidence.md` carry the complete residual-review evidence queue from `residual_review_triage.csv`. These are review inputs, not manual scientific decisions.
- `reports/pgd_magnitude/release/latest/residual_review_annotations_starter.csv` and `residual_review_annotations_starter.md` copy the residual-review evidence rows and add blank manual fields: `manual_review_status`, `manual_review_cause`, `manual_review_notes`, `accepted_for_release`, `reviewer`, and `reviewed_at`.
- `reports/pgd_magnitude/release/latest/residual_review_checklist.md` gives the row-by-row review checklist for filling the annotation starter without mutating the evidence products.
- `reports/pgd_magnitude/release/latest/residual_review_packet_index.csv` and `residual_review_packet_index.md` index one packet per residual evidence row.
- `reports/pgd_magnitude/release/latest/residual_review_packets/` contains one Markdown packet per residual evidence row with event/formula identity, residual context, triage suggestion, best-formula comparison, release-gate context, and blank manual-review placeholders.
- `reports/pgd_magnitude/release/latest/residual_review_dashboard.csv`, `residual_review_dashboard.json`, and `residual_review_dashboard.md` summarize packet review progress by manual status, triage suggestion, release status, accepted flag, and reviewer.
- `reports/pgd_magnitude/release/latest/residual_review_decision_report.csv`, `residual_review_decision_report.json`, and `residual_review_decision_report.md` validate completed review decisions and summarize accepted, excluded, pending, and invalid rows.
- `reports/pgd_magnitude/release/latest/reviewed_release_events.csv`, `reviewed_release_blockers.csv`, `reviewed_release_summary.json`, and `reviewed_release_summary.md` combine baseline release-gate events with residual-review decisions into a reviewed release-set view.
- `reports/pgd_magnitude/release/latest/residual_review_worklist.csv`, `residual_review_worklist.json`, and `residual_review_worklist.md` combine pending/invalid decisions with release blockers and packet paths into a reviewer queue. Suggested status/cause/action fields are review aids, not final scientific decisions.
- `reports/pgd_magnitude/release/latest/release_blocking_review_starter.csv`, `release_blocking_review_starter.json`, and `release_blocking_review_starter.md` provide a focused starter for release-blocking worklist rows. Suggested fields remain machine guidance; the manual review fields are blank until a reviewer fills a copy.
- `reports/pgd_magnitude/release/latest/release_starter_validation.csv`, `release_starter_validation.json`, and `release_starter_validation.md` validate a completed starter before it is imported into the PGD bundle or residual-review merge.
- `reports/pgd_magnitude/release/latest/pgd_release_readiness.json` and `pgd_release_readiness.md` summarize the release gate across the package summary, decision report, reviewed release set, worklist, and focused starter. Readiness can be `READY`, `BLOCKED_ON_REVIEW`, or `INVALID_INPUTS`.
- `reports/pgd_magnitude/release/latest/pgd_formula_test_matrix.csv`, `pgd_formula_test_matrix.json`, and `pgd_formula_test_matrix.md` summarize the three PGD formulas under the single median aggregation method, including baseline rank, sensitivity wins, release blockers, and formula test status.
- `reports/pgd_magnitude/release/latest/pgd_release_blocker_analysis.csv`, `pgd_release_blocker_analysis.json`, and `pgd_release_blocker_analysis.md` explain the remaining release-blocking review rows by formula scope, suggested status/cause, release status, packet path, and next action without filling any manual decision fields.
- `reports/pgd_magnitude/release/latest/pgd_release_blocker_decision_guide.csv`, `pgd_release_blocker_decision_guide.json`, and `pgd_release_blocker_decision_guide.md` provide reviewer-facing allowed statuses, `accepted_for_release` consistency rules, and pre-decision checks for filling a completed starter copy.
- `reports/pgd_magnitude/release/latest/pgd_recommended_formula_release_status.csv`, `pgd_recommended_formula_release_status.json`, and `pgd_recommended_formula_release_status.md` separate recommended-formula baseline readiness from comparison-formula review blockers without writing manual decisions.
- `reports/pgd_magnitude/release/latest/pgd_baseline_narrative_handoff.json` and `pgd_baseline_narrative_handoff.md` state the median-only aggregation method, the formula-only comparison scope, and the baseline narrative handoff status without writing manual decisions.
- `reports/pgd_magnitude/release/latest/pgd_baseline_science_narrative.json` and `pgd_baseline_science_narrative.md` provide a release-level baseline narrative draft with ready-event counts, baseline formula metrics, sensitivity caveat, and pending comparison-review boundary.
- `reports/pgd_magnitude/release/latest/pgd_comparison_formula_review_packet_summary.csv`, `pgd_comparison_formula_review_packet_summary.json`, and `pgd_comparison_formula_review_packet_summary.md` provide a compact handoff table for the remaining comparison-formula blocker packets. They verify packet existence, attach formula-rank context, and keep manual decision fields blank/read-only.
- `reports/pgd_magnitude/release/latest/pgd_review_briefing.json` and `pgd_review_briefing.md` provide the compact reviewer/model briefing for the PGD release state, starter files, packet paths, allowed manual statuses, and completed-starter import commands.
- `reports/pgd_magnitude/release/latest/README.md` and `release_readme.json` provide the release directory entrypoint for reviewers and other models. They point to the briefing, starter, packet index, packet directory, validation command, and bundle import command without writing manual decisions.
- `reports/pgd_magnitude/release/latest/pgd_release_blocker_review_prompt.md` and `pgd_release_blocker_review_prompt.json` provide a direct prompt pack for reviewers or other models to fill a copy of the release-blocking starter. They include blocker rows, packet paths, blank manual fields, allowed terminal statuses, and import commands without editing generated evidence or writing decisions.
- `reports/pgd_magnitude/release/latest/pgd_external_review_handoff.md`, `pgd_external_review_handoff_manifest.json`, and `pgd_external_review_handoff_manifest.csv` are the external reviewer/model handoff index. They list every required handoff file, packet path, file size, SHA256 hash, editable policy, and current blocker rows while preserving the median-only PGD contract and avoiding manual decisions.
- `reports/pgd_magnitude/release/latest/data_dictionary.csv` and `data_dictionary.md` define release-package fields.
- `reports/pgd_magnitude/release/latest/formula_aggregation_note.md` records the single station aggregation method (`median`) and the three PGD formulas (`melgar_2015`, `crowell_2016_gfast`, `ruhl_2019`).
- `reports/pgd_magnitude/release/latest/formula_coefficients.csv`, `formula_coefficients.json`, and `formula_provenance.md` record formula coefficients, units, equations, DOI/source URLs, and citation labels. Coefficients are read from `scripts/pgd_magnitude/evaluate_pgd_magnitude.py` when the release package is built.

The report depends on normalized packages with `event.json`, `stations.csv`, and `waveforms.csv.gz`. Stations need `Distance_Km` for PGD magnitude estimates.

The event-level station aggregation method is `median`. The mainline PGD report does not expose `mean` or `trimmed-mean` as separate methods; the comparison is the three scaling formulas under median aggregation. `scripts/pgd_magnitude/pgd_contract.py` is the shared vocabulary contract for this rule: one station aggregation method, `median`, and three formula labels (`melgar_2015`, `crowell_2016_gfast`, `ruhl_2019`).

Allowed residual review statuses are `UNREVIEWED`, `REVIEWED`, `ACCEPTED`, `EXCLUDED`, `NEEDS_DATA_CHECK`, `NEEDS_METADATA_CHECK`, and `NEEDS_FORMULA_REVIEW`. Use `--strict` when merging annotations to reject rows whose `(event_id, formula)` key is not present in the generated review queue.

The intended residual-review loop is:

```text
residual_review.csv
  -> manage_residual_review.py
  -> residual_review_annotated.csv + residual_review_summary.*
  -> triage_residual_review.py
  -> residual_review_triage.csv + residual_review_triage_summary.json + residual_review_triage.md
  -> build_residual_review_template.py
  -> residual_review_annotations_template.csv + residual_review_guide.md
  -> manual annotation CSV
  -> manage_residual_review.py --annotations <manual CSV> --strict
```

The release-package dashboard can be regenerated at any point while a starter worksheet is being filled:

```bash
python scripts/pgd_magnitude/build_residual_review_dashboard.py \
  --release-dir reports/pgd_magnitude/release/latest
```

Then generate the decision report to check whether filled rows are internally consistent:

```bash
python scripts/pgd_magnitude/build_residual_review_decision_report.py \
  --release-dir reports/pgd_magnitude/release/latest
```

The reviewed release-set view can be regenerated after the decision report:

```bash
python scripts/pgd_magnitude/build_reviewed_release_set.py \
  --release-dir reports/pgd_magnitude/release/latest
```

For bundle-level release review, fill a copy of the focused `reports/pgd_magnitude/release/latest/release_blocking_review_starter.csv`, validate the completed file first, then merge it back with:

```bash
python scripts/pgd_magnitude/validate_release_starter_annotations.py \
  --release-dir reports/pgd_magnitude/release/latest \
  --completed-starter <completed-starter.csv> \
  --require-complete \
  --strict
```

```bash
python scripts/pgd_magnitude/manage_residual_review.py \
  --review-csv reports/pgd_magnitude/latest/residual_review.csv \
  --starter-annotations <completed-starter.csv> \
  --out-csv reports/pgd_magnitude/latest/residual_review_annotated.csv \
  --out-json reports/pgd_magnitude/latest/residual_review_summary.json \
  --out-md reports/pgd_magnitude/latest/residual_review_summary.md \
  --strict
```

Only starter rows with at least one manual field filled are imported; blank starter rows do not overwrite the base review queue.

The broader `reports/pgd_magnitude/release/latest/residual_review_annotations_starter.csv` remains available for full residual-evidence review. Import a completed full starter through the targeted `manage_residual_review.py --starter-annotations` path after checking that its keys match the generated residual review queue; the standard bundle validation gate is intentionally focused on release-blocking rows.

The same completed starter can be imported while regenerating the full PGD bundle:

```bash
python scripts/pgd_magnitude/run_pgd_science_bundle.py \
  --export-root exports/normalized-ok-stations-us-nz \
  --report-dir reports/pgd_magnitude/latest \
  --sensitivity-dir reports/pgd_magnitude/sensitivity/latest \
  --release-dir reports/pgd_magnitude/release/latest \
  --starter-annotations <completed-starter.csv>
```

With `--starter-annotations`, the bundle records a `release_starter_validation` stage before `residual_review_merge`. If validation returns nonzero, the bundle stops before importing manual decisions.

The release-set gate uses hard criteria for usable station count, PGD reliability, median PGD SNR, and median distance. The residual threshold is a review trigger, not an automatic exclusion: a candidate above the residual threshold is marked `NEEDS_RESIDUAL_REVIEW` rather than dropped from the candidate set.

For current legacy normalized exports, `nz-*` event package directories are treated as `country=New Zealand` and `region=New Zealand` inside the PGD report even if the package `event.json` contains a broader legacy country label. This keeps the PGD science sample aligned with the intended US/NZ/Mexico default country selection without rewriting the normalized export packages.
