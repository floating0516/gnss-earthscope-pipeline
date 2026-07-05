# PGD Benchmark Interpretation

This report interprets the PGD formula benchmark across ALL, QUALITY, and STRICT data tiers.

The station aggregation method is fixed to `median`; `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas/scaling laws.

## Tier Summary

| Tier | Scenario | Events | Recommended formula | Best MAE | Best RMSE |
|---|---|---:|---|---:|---:|
| ALL | `all` | 142 | `ruhl_2019` | 0.496 | 0.601 |
| QUALITY | `quality_snr3_time300_dist300_min3sta` | 14 | `melgar_2015` | 0.383 | 0.510 |
| STRICT | `strict_snr5_time300_dist300_min3sta` | 6 | `melgar_2015` | 0.099 | 0.118 |

## Main Interpretation

- ALL is the coverage baseline and should remain in the benchmark package.
- QUALITY is the main formula-comparison tier because it balances error reduction with enough events to inspect.
- STRICT is a high-confidence reference tier. It should not replace ALL or QUALITY because the sample is small.
- PGD amplitude thresholds at 1 cm and 2 cm do not materially change the current sample, so they are weak primary filters.

## Formula Metrics By Scenario

| Scenario | Formula | Events | Bias | MAE | RMSE | Median Abs Err | >1 Mw | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `all` | `melgar_2015` | 142 | 0.542 | 0.606 | 0.724 | 0.572 | 26 | 2 |
| `all` | `crowell_2016_gfast` | 142 | 0.806 | 0.820 | 0.939 | 0.872 | 57 | 3 |
| `all` | `ruhl_2019` | 142 | 0.338 | 0.496 | 0.601 | 0.432 | 13 | 1 |
| `pgd_ge_1cm` | `melgar_2015` | 142 | 0.542 | 0.606 | 0.724 | 0.572 | 26 | 2 |
| `pgd_ge_1cm` | `crowell_2016_gfast` | 142 | 0.806 | 0.820 | 0.939 | 0.872 | 57 | 3 |
| `pgd_ge_1cm` | `ruhl_2019` | 142 | 0.338 | 0.496 | 0.601 | 0.432 | 13 | 1 |
| `pgd_ge_2cm` | `melgar_2015` | 141 | 0.549 | 0.608 | 0.726 | 0.577 | 26 | 2 |
| `pgd_ge_2cm` | `crowell_2016_gfast` | 141 | 0.811 | 0.825 | 0.943 | 0.876 | 57 | 3 |
| `pgd_ge_2cm` | `ruhl_2019` | 141 | 0.346 | 0.495 | 0.601 | 0.425 | 13 | 1 |
| `pgd_ge_5cm` | `melgar_2015` | 107 | 0.709 | 0.748 | 0.873 | 0.832 | 33 | 2 |
| `pgd_ge_5cm` | `crowell_2016_gfast` | 107 | 0.921 | 0.936 | 1.062 | 1.055 | 56 | 3 |
| `pgd_ge_5cm` | `ruhl_2019` | 107 | 0.521 | 0.631 | 0.740 | 0.660 | 20 | 1 |
| `snr_ge_3` | `melgar_2015` | 80 | 0.505 | 0.584 | 0.697 | 0.576 | 11 | 2 |
| `snr_ge_3` | `crowell_2016_gfast` | 80 | 0.755 | 0.773 | 0.902 | 0.824 | 27 | 3 |
| `snr_ge_3` | `ruhl_2019` | 80 | 0.304 | 0.494 | 0.586 | 0.427 | 7 | 1 |
| `snr_ge_5` | `melgar_2015` | 20 | 0.380 | 0.549 | 0.793 | 0.242 | 5 | 1 |
| `snr_ge_5` | `crowell_2016_gfast` | 20 | 0.506 | 0.592 | 0.866 | 0.222 | 6 | 3 |
| `snr_ge_5` | `ruhl_2019` | 20 | 0.191 | 0.582 | 0.747 | 0.418 | 4 | 2 |
| `dist_le_300km` | `melgar_2015` | 138 | 0.513 | 0.582 | 0.704 | 0.555 | 23 | 2 |
| `dist_le_300km` | `crowell_2016_gfast` | 138 | 0.774 | 0.788 | 0.911 | 0.836 | 52 | 3 |
| `dist_le_300km` | `ruhl_2019` | 138 | 0.306 | 0.476 | 0.583 | 0.418 | 11 | 1 |
| `dist_le_200km` | `melgar_2015` | 104 | 0.424 | 0.512 | 0.624 | 0.474 | 11 | 2 |
| `dist_le_200km` | `crowell_2016_gfast` | 104 | 0.658 | 0.685 | 0.796 | 0.714 | 23 | 3 |
| `dist_le_200km` | `ruhl_2019` | 104 | 0.204 | 0.418 | 0.513 | 0.380 | 6 | 1 |
| `quality_snr3_time300_dist300_min3sta` | `melgar_2015` | 14 | 0.260 | 0.383 | 0.510 | 0.251 | 1 | 1 |
| `quality_snr3_time300_dist300_min3sta` | `crowell_2016_gfast` | 14 | 0.476 | 0.531 | 0.690 | 0.298 | 2 | 3 |
| `quality_snr3_time300_dist300_min3sta` | `ruhl_2019` | 14 | 0.056 | 0.386 | 0.450 | 0.339 | 0 | 2 |
| `strict_snr5_time300_dist300_min3sta` | `melgar_2015` | 6 | -0.048 | 0.099 | 0.118 | 0.083 | 0 | 1 |
| `strict_snr5_time300_dist300_min3sta` | `crowell_2016_gfast` | 6 | 0.055 | 0.115 | 0.128 | 0.126 | 0 | 2 |
| `strict_snr5_time300_dist300_min3sta` | `ruhl_2019` | 6 | -0.255 | 0.255 | 0.275 | 0.294 | 0 | 3 |

## Figures

- `scenario_mae_rmse`: `figures/scenario_mae_rmse.svg`
- `event_count_vs_mae`: `figures/event_count_vs_mae.svg`
- `estimated_vs_catalog_all`: `figures/estimated_vs_catalog_all.svg`
- `estimated_vs_catalog_quality`: `figures/estimated_vs_catalog_quality.svg`
- `estimated_vs_catalog_strict`: `figures/estimated_vs_catalog_strict.svg`
- `residual_diagnostics`: `figures/residual_diagnostics.svg`
