#!/usr/bin/env python3
"""Run median-based PGD sensitivity experiments."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_pgd_magnitude as pgd


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    label: str
    pgd_component: str
    distance: str
    calibration: str


DEFAULT_SCENARIOS = [
    Scenario("baseline", "3D PGD, hypocentral distance, no calibration", "3d", "hypocentral", "none"),
    Scenario("horizontal", "Horizontal PGD, hypocentral distance, no calibration", "horizontal", "hypocentral", "none"),
    Scenario("epicentral", "3D PGD, epicentral distance, no calibration", "3d", "epicentral", "none"),
    Scenario("calibrated", "3D PGD, hypocentral distance, leave-one-out country calibration", "3d", "hypocentral", "leave-one-out-country-linear"),
]

SUMMARY_FIELDS = [
    "scenario_id",
    "scenario_label",
    "pgd_component",
    "distance_mode",
    "calibration",
    "station_aggregation",
    "formula",
    "event_count",
    "high_medium_reliability_events",
    "low_reliability_events",
    "residual_outlier_count",
    "bias_mw",
    "mae_mw",
    "rmse_mw",
    "median_abs_error_mw",
]

RECOMMENDATION_FIELDS = [
    "scenario_id",
    "scenario_label",
    "pgd_component",
    "distance_mode",
    "calibration",
    "station_aggregation",
    "recommended_formula",
    "criterion",
    "event_count",
    "mae_mw",
    "rmse_mw",
    "median_abs_error_mw",
    "residual_outlier_count",
    "matches_baseline",
]

DELTA_FIELDS = [
    "scenario_id",
    "scenario_label",
    "pgd_component",
    "distance_mode",
    "calibration",
    "station_aggregation",
    "formula",
    "baseline_formula",
    "scenario_recommended_formula",
    "scenario_rank",
    "baseline_rank",
    "rank_delta_vs_baseline_scenario",
    "event_count",
    "baseline_event_count",
    "mae_mw",
    "baseline_mae_mw",
    "delta_mae_vs_baseline_scenario",
    "rmse_mw",
    "baseline_rmse_mw",
    "delta_rmse_vs_baseline_scenario",
    "median_abs_error_mw",
    "baseline_median_abs_error_mw",
    "delta_median_abs_error_vs_baseline_scenario",
    "residual_outlier_count",
    "baseline_residual_outlier_count",
    "delta_residual_outliers_vs_baseline_scenario",
    "matches_baseline_recommendation",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for sensitivity products.")
    parser.add_argument("--countries", nargs="*", default=sorted(pgd.TARGET_COUNTRIES))
    parser.add_argument("--pgd-window-start", type=float, default=0.0)
    parser.add_argument("--pgd-window-end", type=float, default=600.0)
    parser.add_argument("--max-pgd-time-offset", type=float, default=0.0)
    parser.add_argument("--noise-window-start", type=float, default=-300.0)
    parser.add_argument("--noise-window-end", type=float, default=0.0)
    parser.add_argument("--min-pgd-snr", type=float, default=3.0)
    parser.add_argument("--near-distance-km", type=float, default=300.0)
    parser.add_argument("--min-distance-km", type=float, default=1.0)
    parser.add_argument("--max-distance-km", type=float, default=0.0)
    parser.add_argument("--quality-max-distance-km", type=float, default=500.0)
    parser.add_argument("--quality-max-pgd-time-offset", type=float, default=300.0)
    parser.add_argument("--min-pgd-m", type=float, default=1e-6)
    parser.add_argument("--min-stations", type=int, default=1)
    parser.add_argument("--residual-review-threshold", type=float, default=1.0)
    return parser.parse_args(argv)


def scenario_eval_args(args: argparse.Namespace, scenario: Scenario) -> SimpleNamespace:
    return SimpleNamespace(
        pgd_window_start=args.pgd_window_start,
        pgd_window_end=args.pgd_window_end,
        pgd_component=scenario.pgd_component,
        distance=scenario.distance,
        station_aggregation=pgd.STATION_AGGREGATION,
        max_pgd_time_offset=args.max_pgd_time_offset,
        noise_window_start=args.noise_window_start,
        noise_window_end=args.noise_window_end,
        min_pgd_snr=args.min_pgd_snr,
        near_distance_km=args.near_distance_km,
        min_distance_km=args.min_distance_km,
        max_distance_km=args.max_distance_km,
        quality_max_distance_km=args.quality_max_distance_km,
        quality_max_pgd_time_offset=args.quality_max_pgd_time_offset,
        min_pgd_m=args.min_pgd_m,
        min_stations=args.min_stations,
        calibration=scenario.calibration,
    )


def finite_float(value: object) -> float:
    return pgd.finite_float(value)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    return value


def fmt(value: object, digits: int = 6) -> str:
    return pgd.fmt(value, digits)


def csv_value(value: object) -> str:
    if isinstance(value, (int, float)):
        return fmt(value)
    return str(value if value is not None else "")


RawEvaluationKey = tuple[object, ...]


def raw_evaluation_key(args: argparse.Namespace, scenario: Scenario) -> RawEvaluationKey:
    return (
        str(args.export_root),
        tuple(sorted(args.countries)),
        scenario.pgd_component,
        scenario.distance,
        pgd.STATION_AGGREGATION,
        args.pgd_window_start,
        args.pgd_window_end,
        args.max_pgd_time_offset,
        args.noise_window_start,
        args.noise_window_end,
        args.min_pgd_snr,
        args.near_distance_km,
        args.min_distance_km,
        args.max_distance_km,
        args.quality_max_distance_km,
        args.quality_max_pgd_time_offset,
        args.min_pgd_m,
        args.min_stations,
    )


def copy_event_rows(event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [dict(row) for row in event_rows]


def evaluate_raw_scenario(args: argparse.Namespace, scenario: Scenario) -> list[dict[str, object]]:
    raw_scenario = Scenario(scenario.scenario_id, scenario.label, scenario.pgd_component, scenario.distance, "none")
    eval_args = scenario_eval_args(args, raw_scenario)
    event_rows: list[dict[str, object]] = []
    for event_dir in pgd.iter_event_dirs(args.export_root, set(args.countries)):
        _station_rows, scenario_event_rows = pgd.evaluate_event(event_dir, eval_args)
        event_rows.extend(scenario_event_rows)
    return event_rows


def evaluate_scenario(
    args: argparse.Namespace,
    scenario: Scenario,
    raw_event_cache: dict[RawEvaluationKey, list[dict[str, object]]] | None = None,
) -> list[dict[str, object]]:
    key = raw_evaluation_key(args, scenario)
    if raw_event_cache is None:
        raw_event_rows = evaluate_raw_scenario(args, scenario)
    else:
        if key not in raw_event_cache:
            raw_event_cache[key] = evaluate_raw_scenario(args, scenario)
        raw_event_rows = raw_event_cache[key]
    event_rows = copy_event_rows(raw_event_rows)
    if scenario.calibration == "leave-one-out-country-linear":
        event_rows = pgd.apply_leave_one_out_calibration(event_rows)
    return event_rows


def summary_rows_for_scenario(args: argparse.Namespace, scenario: Scenario, event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for law in pgd.SCALING_LAWS:
        formula_rows = [row for row in event_rows if row.get("formula") == law.name]
        if not formula_rows:
            continue
        payload = pgd.summary_payload(formula_rows)
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_label": scenario.label,
                "pgd_component": scenario.pgd_component,
                "distance_mode": scenario.distance,
                "calibration": scenario.calibration,
                "station_aggregation": pgd.STATION_AGGREGATION,
                "formula": law.name,
                "event_count": payload["event_count"],
                "high_medium_reliability_events": sum(1 for row in formula_rows if row.get("pgd_reliability") in {"HIGH", "MEDIUM"}),
                "low_reliability_events": sum(1 for row in formula_rows if row.get("pgd_reliability") == "LOW"),
                "residual_outlier_count": sum(
                    1
                    for row in formula_rows
                    if math.isfinite(finite_float(row.get("abs_residual_mw")))
                    and finite_float(row.get("abs_residual_mw")) >= args.residual_review_threshold
                ),
                "bias_mw": payload["bias_mw"],
                "mae_mw": payload["mae_mw"],
                "rmse_mw": payload["rmse_mw"],
                "median_abs_error_mw": payload["median_abs_error_mw"],
            }
        )
    return rows


def recommend_formula(summary_rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [row for row in summary_rows if math.isfinite(finite_float(row.get("mae_mw")))]
    if not candidates:
        return {
            "recommended_formula": "",
            "criterion": "lowest_mae_mw",
            "event_count": 0,
            "mae_mw": "",
            "rmse_mw": "",
            "median_abs_error_mw": "",
            "residual_outlier_count": "",
        }
    best = min(
        candidates,
        key=lambda row: (
            finite_float(row.get("mae_mw")),
            finite_float(row.get("rmse_mw")),
            finite_float(row.get("median_abs_error_mw")),
            str(row.get("formula") or ""),
        ),
    )
    return {
        "recommended_formula": best.get("formula", ""),
        "criterion": "lowest_mae_mw",
        "event_count": best.get("event_count", ""),
        "mae_mw": best.get("mae_mw", ""),
        "rmse_mw": best.get("rmse_mw", ""),
        "median_abs_error_mw": best.get("median_abs_error_mw", ""),
        "residual_outlier_count": best.get("residual_outlier_count", ""),
    }


def recommendation_row(scenario: Scenario, recommendation: dict[str, object], baseline_formula: str) -> dict[str, object]:
    recommended_formula = str(recommendation.get("recommended_formula") or "")
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_label": scenario.label,
        "pgd_component": scenario.pgd_component,
        "distance_mode": scenario.distance,
        "calibration": scenario.calibration,
        "station_aggregation": pgd.STATION_AGGREGATION,
        **recommendation,
        "matches_baseline": "yes" if recommended_formula and recommended_formula == baseline_formula else "no",
    }


def ranked_summary_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            finite_float(row.get("mae_mw")),
            finite_float(row.get("rmse_mw")),
            finite_float(row.get("median_abs_error_mw")),
            str(row.get("formula") or ""),
        ),
    )


def metric_delta(value: object, baseline_value: object) -> float:
    current = finite_float(value)
    baseline = finite_float(baseline_value)
    return current - baseline if math.isfinite(current) and math.isfinite(baseline) else math.nan


def formula_delta_rows(
    summary_rows: list[dict[str, object]],
    recommendations: list[dict[str, object]],
    baseline_formula: str,
) -> list[dict[str, object]]:
    rows_by_scenario: dict[str, list[dict[str, object]]] = {}
    for row in summary_rows:
        rows_by_scenario.setdefault(str(row.get("scenario_id") or ""), []).append(row)

    baseline_rows = {str(row.get("formula") or ""): row for row in rows_by_scenario.get("baseline", [])}
    ranks: dict[tuple[str, str], int] = {}
    for scenario_id, rows in rows_by_scenario.items():
        for index, row in enumerate(ranked_summary_rows(rows), start=1):
            ranks[(scenario_id, str(row.get("formula") or ""))] = index

    recommended_by_scenario = {
        str(row.get("scenario_id") or ""): str(row.get("recommended_formula") or "")
        for row in recommendations
    }

    delta_rows: list[dict[str, object]] = []
    scenario_order = [scenario.scenario_id for scenario in DEFAULT_SCENARIOS]
    for scenario_id in scenario_order:
        for row in sorted(rows_by_scenario.get(scenario_id, []), key=lambda item: str(item.get("formula") or "")):
            formula = str(row.get("formula") or "")
            baseline_row = baseline_rows.get(formula, {})
            scenario_rank = ranks.get((scenario_id, formula), 0)
            baseline_rank = ranks.get(("baseline", formula), 0)
            delta_rows.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_label": row.get("scenario_label", ""),
                    "pgd_component": row.get("pgd_component", ""),
                    "distance_mode": row.get("distance_mode", ""),
                    "calibration": row.get("calibration", ""),
                    "station_aggregation": pgd.STATION_AGGREGATION,
                    "formula": formula,
                    "baseline_formula": baseline_formula,
                    "scenario_recommended_formula": recommended_by_scenario.get(scenario_id, ""),
                    "scenario_rank": scenario_rank,
                    "baseline_rank": baseline_rank,
                    "rank_delta_vs_baseline_scenario": scenario_rank - baseline_rank if scenario_rank and baseline_rank else "",
                    "event_count": row.get("event_count", ""),
                    "baseline_event_count": baseline_row.get("event_count", ""),
                    "mae_mw": row.get("mae_mw", ""),
                    "baseline_mae_mw": baseline_row.get("mae_mw", ""),
                    "delta_mae_vs_baseline_scenario": metric_delta(row.get("mae_mw"), baseline_row.get("mae_mw")),
                    "rmse_mw": row.get("rmse_mw", ""),
                    "baseline_rmse_mw": baseline_row.get("rmse_mw", ""),
                    "delta_rmse_vs_baseline_scenario": metric_delta(row.get("rmse_mw"), baseline_row.get("rmse_mw")),
                    "median_abs_error_mw": row.get("median_abs_error_mw", ""),
                    "baseline_median_abs_error_mw": baseline_row.get("median_abs_error_mw", ""),
                    "delta_median_abs_error_vs_baseline_scenario": metric_delta(
                        row.get("median_abs_error_mw"),
                        baseline_row.get("median_abs_error_mw"),
                    ),
                    "residual_outlier_count": row.get("residual_outlier_count", ""),
                    "baseline_residual_outlier_count": baseline_row.get("residual_outlier_count", ""),
                    "delta_residual_outliers_vs_baseline_scenario": metric_delta(
                        row.get("residual_outlier_count"),
                        baseline_row.get("residual_outlier_count"),
                    ),
                    "matches_baseline_recommendation": "yes" if recommended_by_scenario.get(scenario_id, "") == baseline_formula else "no",
                }
            )
    return delta_rows


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _field in fields) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "") if row.get(field, "") is not None else "") for field in fields) + " |")
    return lines


def write_summary_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_summary_md(path: Path, payload: dict[str, object]) -> None:
    baseline = payload.get("baseline_recommendation", {})
    recommendations = payload.get("recommendations", [])
    assert isinstance(baseline, dict)
    assert isinstance(recommendations, list)
    lines = [
        "# PGD Sensitivity",
        "",
        f"- Status: {payload.get('status', '')}",
        f"- Station aggregation: `{pgd.STATION_AGGREGATION}`",
        f"- Baseline formula: `{baseline.get('recommended_formula', '')}`",
        f"- Recommendation stable: `{payload.get('recommendation_stable', '')}`",
        "",
        "## Scenario Recommendations",
        "",
        *markdown_table(recommendations, RECOMMENDATION_FIELDS),
        "",
        "## Interpretation",
        "",
    ]
    if payload.get("recommendation_stable") == "yes":
        lines.append("The baseline formula remains the recommendation across all default sensitivity scenarios.")
    else:
        lines.append("At least one sensitivity scenario changes the recommended formula; inspect `sensitivity_recommendations.csv` before treating the baseline as robust.")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "These experiments vary PGD component, distance mode, and calibration one at a time. They do not reintroduce non-median station aggregation.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_interpretation_md(path: Path, payload: dict[str, object]) -> None:
    baseline = payload.get("baseline_recommendation", {})
    recommendations = payload.get("recommendations", [])
    formula_deltas = payload.get("formula_deltas", [])
    assert isinstance(baseline, dict)
    assert isinstance(recommendations, list)
    assert isinstance(formula_deltas, list)
    baseline_formula = str(baseline.get("recommended_formula") or "")
    switched = [row for row in recommendations if row.get("matches_baseline") == "no"]
    lines = [
        "# PGD Sensitivity Interpretation",
        "",
        f"- Station aggregation: `{pgd.STATION_AGGREGATION}`",
        f"- Baseline formula: `{baseline_formula}`",
        f"- Recommendation stable: `{payload.get('recommendation_stable', '')}`",
        "",
        "## Formula Switches",
        "",
    ]
    if not switched:
        lines.append("No default sensitivity scenario changed the recommended formula.")
    else:
        for recommendation in switched:
            scenario_id = str(recommendation.get("scenario_id") or "")
            scenario_formula = str(recommendation.get("recommended_formula") or "")
            scenario_rows = [row for row in formula_deltas if row.get("scenario_id") == scenario_id]
            scenario_best = next((row for row in scenario_rows if row.get("formula") == scenario_formula), {})
            baseline_formula_row = next((row for row in scenario_rows if row.get("formula") == baseline_formula), {})
            scenario_mae = finite_float(scenario_best.get("mae_mw"))
            baseline_formula_mae = finite_float(baseline_formula_row.get("mae_mw"))
            advantage = baseline_formula_mae - scenario_mae if math.isfinite(scenario_mae) and math.isfinite(baseline_formula_mae) else math.nan
            lines.append(
                f"- `{scenario_id}` recommends `{scenario_formula}` instead of `{baseline_formula}`. "
                f"In this scenario, `{scenario_formula}` MAE is {fmt(scenario_mae)} Mw and `{baseline_formula}` MAE is {fmt(baseline_formula_mae)} Mw "
                f"(advantage {fmt(advantage)} Mw)."
            )
    lines.extend(
        [
            "",
            "## Formula Delta Table",
            "",
            *markdown_table(formula_deltas, DELTA_FIELDS),
            "",
            "## Reading Notes",
            "",
            "Positive delta values mean the scenario metric is larger than the baseline scenario for the same formula; negative values mean the scenario metric is smaller.",
            "These rows compare formulas under the fixed median station aggregation method.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_sensitivity(args: argparse.Namespace) -> dict[str, object]:
    summary_rows: list[dict[str, object]] = []
    scenario_recommendations: list[dict[str, object]] = []
    raw_recommendations: dict[str, dict[str, object]] = {}
    raw_event_cache: dict[RawEvaluationKey, list[dict[str, object]]] = {}

    for scenario in DEFAULT_SCENARIOS:
        event_rows = evaluate_scenario(args, scenario, raw_event_cache)
        scenario_summary = summary_rows_for_scenario(args, scenario, event_rows)
        summary_rows.extend(scenario_summary)
        raw_recommendations[scenario.scenario_id] = recommend_formula(scenario_summary)

    baseline_formula = str(raw_recommendations.get("baseline", {}).get("recommended_formula") or "")
    for scenario in DEFAULT_SCENARIOS:
        scenario_recommendations.append(recommendation_row(scenario, raw_recommendations[scenario.scenario_id], baseline_formula))

    delta_rows = formula_delta_rows(summary_rows, scenario_recommendations, baseline_formula)
    recommendation_stable = "yes" if baseline_formula and all(row["matches_baseline"] == "yes" for row in scenario_recommendations) else "no"
    status = "OK" if summary_rows else "NO_PGD_EVENTS"
    payload = {
        "status": status,
        "message": "PGD sensitivity report generated." if summary_rows else "No PGD event rows generated for sensitivity scenarios.",
        "counts": {
            "scenario_count": len(DEFAULT_SCENARIOS),
            "summary_rows": len(summary_rows),
            "recommendation_rows": len(scenario_recommendations),
            "formula_delta_rows": len(delta_rows),
        },
        "parameters": {
            "export_root": str(args.export_root),
            "countries": sorted(args.countries),
            "station_aggregation": pgd.STATION_AGGREGATION,
            "residual_review_threshold": args.residual_review_threshold,
        },
        "scenarios": [scenario.__dict__ for scenario in DEFAULT_SCENARIOS],
        "summary_rows": summary_rows,
        "recommendations": scenario_recommendations,
        "formula_deltas": delta_rows,
        "baseline_recommendation": raw_recommendations.get("baseline", {}),
        "recommendation_stable": recommendation_stable,
    }

    write_csv(args.out_dir / "sensitivity_summary.csv", summary_rows, SUMMARY_FIELDS)
    write_csv(args.out_dir / "sensitivity_recommendations.csv", scenario_recommendations, RECOMMENDATION_FIELDS)
    write_csv(args.out_dir / "sensitivity_formula_deltas.csv", delta_rows, DELTA_FIELDS)
    write_summary_json(args.out_dir / "summary.json", payload)
    write_summary_md(args.out_dir / "summary.md", payload)
    write_interpretation_md(args.out_dir / "sensitivity_interpretation.md", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_sensitivity(args)
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "out_dir": str(args.out_dir)}, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
