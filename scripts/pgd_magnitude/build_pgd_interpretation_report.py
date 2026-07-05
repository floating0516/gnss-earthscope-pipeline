#!/usr/bin/env python3
"""Build a compact PGD interpretation report from generated PGD products."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True, help="PGD latest report directory.")
    parser.add_argument("--sensitivity-dir", type=Path, required=True, help="PGD sensitivity report directory.")
    parser.add_argument("--out-json", type=Path, required=True, help="Output interpretation JSON.")
    parser.add_argument("--out-md", type=Path, required=True, help="Output interpretation Markdown.")
    return parser.parse_args(argv)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def fmt(value: object, digits: int = 6) -> str:
    number = as_float(value)
    if number is None:
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".")


def table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def formula_switch_scenarios(recommendations: list[dict[str, Any]]) -> list[str]:
    switches: list[str] = []
    for row in recommendations:
        scenario = str(row.get("scenario_id") or "")
        if not scenario or scenario == "baseline":
            continue
        if str(row.get("matches_baseline") or "").lower() == "no":
            switches.append(scenario)
    return switches


def build_payload(report_dir: Path, sensitivity_dir: Path) -> dict[str, Any]:
    report_summary = read_json(report_dir / "summary.json")
    sensitivity_summary = read_json(sensitivity_dir / "summary.json")
    triage_summary = read_json(report_dir / "residual_review_triage_summary.json")

    recommendation = dict(report_summary.get("formula_recommendation") or {})
    release_set = dict(report_summary.get("pgd_release_set") or {})
    recommendations = list(sensitivity_summary.get("recommendations") or [])
    switches = formula_switch_scenarios(recommendations)
    status_counts = dict(triage_summary.get("suggested_status_counts") or {})
    data_check_count = as_int(status_counts.get("NEEDS_DATA_CHECK"))
    formula_review_count = as_int(status_counts.get("NEEDS_FORMULA_REVIEW"))
    triage_rows = as_int(triage_summary.get("row_count"))

    return {
        "status": "OK",
        "report_dir": str(report_dir),
        "sensitivity_dir": str(sensitivity_dir),
        "baseline": {
            "recommended_formula": recommendation.get("recommended_formula", ""),
            "station_aggregation": recommendation.get("station_aggregation", ""),
            "criterion": recommendation.get("criterion", ""),
            "event_count": recommendation.get("event_count", report_summary.get("counts", {}).get("unique_events", "")),
            "mae_mw": recommendation.get("mae_mw", ""),
            "rmse_mw": recommendation.get("rmse_mw", ""),
            "median_abs_error_mw": recommendation.get("median_abs_error_mw", ""),
        },
        "sensitivity": {
            "recommendation_stable": sensitivity_summary.get("recommendation_stable", ""),
            "formula_switch_scenarios": switches,
            "recommendations": recommendations,
        },
        "release_set": {
            "total_events": release_set.get("total_events", ""),
            "candidate_events": release_set.get("candidate_events", ""),
            "ready_events": release_set.get("ready_events", ""),
            "review_required_events": release_set.get("review_required_events", ""),
            "excluded_events": release_set.get("excluded_events", ""),
            "by_failure_reason": release_set.get("by_failure_reason", {}),
        },
        "residual_triage": {
            "row_count": triage_rows,
            "suggested_status_counts": status_counts,
            "suggested_cause_counts": triage_summary.get("suggested_cause_counts", {}),
            "top_priority_rows": triage_summary.get("top_priority_rows", []),
        },
        "interpretation_flags": {
            "requires_sensitivity_caveat": str(sensitivity_summary.get("recommendation_stable") or "").lower() != "yes",
            "residuals_data_quality_dominated": data_check_count > formula_review_count and data_check_count > 0,
            "has_release_ready_events": as_int(release_set.get("ready_events")) > 0,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    sensitivity = payload["sensitivity"]
    release_set = payload["release_set"]
    residual_triage = payload["residual_triage"]
    flags = payload["interpretation_flags"]
    switch_scenarios = sensitivity["formula_switch_scenarios"]
    data_quality_text = (
        "Residual triage is dominated by data-quality checks."
        if flags["residuals_data_quality_dominated"]
        else "Residual triage is not dominated by data-quality checks."
    )
    lines = [
        "# PGD Interpretation Report",
        "",
        "## Baseline",
        "",
        f"- Recommended formula: `{baseline['recommended_formula']}`",
        f"- Station aggregation: `{baseline['station_aggregation']}`",
        f"- Criterion: `{baseline['criterion']}`",
        f"- Event count: {baseline['event_count']}",
        f"- MAE/RMSE Mw: {fmt(baseline['mae_mw'])} / {fmt(baseline['rmse_mw'])}",
        "",
        "## Sensitivity",
        "",
        f"- Recommendation stability: `{sensitivity['recommendation_stable']}`",
        f"- Formula-switch scenarios: {', '.join(f'`{item}`' for item in switch_scenarios) if switch_scenarios else 'none'}",
        "",
        *table(
            [
                {
                    "scenario_id": row.get("scenario_id", ""),
                    "recommended_formula": row.get("recommended_formula", ""),
                    "matches_baseline": row.get("matches_baseline", ""),
                    "mae_mw": fmt(row.get("mae_mw")),
                }
                for row in sensitivity["recommendations"]
            ],
            ["scenario_id", "recommended_formula", "matches_baseline", "mae_mw"],
        ),
        "",
        "## Release Set",
        "",
        f"- Ready events: {release_set['ready_events']} / {release_set['total_events']}",
        f"- Excluded events: {release_set['excluded_events']}",
        f"- Review-required events: {release_set['review_required_events']}",
        "",
        "## Residual Triage",
        "",
        f"- Review rows: {residual_triage['row_count']}",
        f"- Suggested statuses: {json.dumps(residual_triage['suggested_status_counts'], sort_keys=True)}",
        f"- {data_quality_text}",
        "",
        *table(
            [
                {
                    "event_id": row.get("event_id", ""),
                    "formula": row.get("formula", ""),
                    "abs_residual_mw": row.get("abs_residual_mw", ""),
                    "triage_status_suggestion": row.get("triage_status_suggestion", ""),
                    "triage_cause_suggestion": row.get("triage_cause_suggestion", ""),
                }
                for row in residual_triage["top_priority_rows"][:10]
            ],
            ["event_id", "formula", "abs_residual_mw", "triage_status_suggestion", "triage_cause_suggestion"],
        ),
        "",
        "## Interpretation Flags",
        "",
        f"- Requires sensitivity caveat: `{str(flags['requires_sensitivity_caveat']).lower()}`",
        f"- Residuals data-quality dominated: `{str(flags['residuals_data_quality_dominated']).lower()}`",
        f"- Has release-ready events: `{str(flags['has_release_ready_events']).lower()}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args.report_dir, args.sensitivity_dir)
    write_json(args.out_json, payload)
    write_markdown(args.out_md, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(args)
    print(json.dumps({"status": payload["status"], "out_json": str(args.out_json), "out_md": str(args.out_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
