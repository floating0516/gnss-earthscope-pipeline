#!/usr/bin/env python3
"""Build a release-level PGD baseline science narrative."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract

STATION_AGGREGATION = pgd_contract.STATION_AGGREGATION_METHOD


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_baseline_science_narrative.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_baseline_science_narrative.md.")
    return parser.parse_args(argv)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def load_required_json(path: Path, errors: list[dict[str, object]]) -> dict[str, Any]:
    if not path.exists():
        errors.append(error("MISSING_INPUT", "Required PGD release JSON is missing.", path=str(path)))
        return {}
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(error("READ_ERROR", "Could not read PGD release JSON.", path=str(path), detail=str(exc)))
        return {}


def load_required_csv(path: Path, errors: list[dict[str, object]]) -> list[dict[str, str]]:
    if not path.exists():
        errors.append(error("MISSING_INPUT", "Required PGD release CSV is missing.", path=str(path)))
        return []
    try:
        return read_csv(path)
    except (OSError, csv.Error) as exc:
        errors.append(error("READ_ERROR", "Could not read PGD release CSV.", path=str(path), detail=str(exc)))
        return []


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return default


def bool_value(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def validate_status(name: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    status = str(payload.get("status") or "").strip()
    if status and status not in {"OK", "NO_READY_EVENTS"}:
        errors.append(error("INVALID_INPUT_STATUS", "Required PGD release product is not OK.", product=name, status=status))


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    text = str(value or "").strip()
    if text != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD baseline science narrative requires station_aggregation=median.",
                product=product,
                station_aggregation=text,
            )
        )


def baseline_formula_row(rows: list[dict[str, str]], formula: str) -> dict[str, str]:
    all_rows = [
        row
        for row in rows
        if row.get("formula") == formula
        and str(row.get("comparison_group") or "").strip().lower() == "all"
        and str(row.get("comparison_value") or "").strip().upper() == "ALL"
    ]
    if all_rows:
        return all_rows[0]
    for row in rows:
        if row.get("formula") == formula:
            return row
    return {}


def switch_scenarios(rows: list[dict[str, str]], baseline_formula: str) -> list[str]:
    scenarios = []
    for row in rows:
        scenario = str(row.get("scenario_id") or "").strip()
        formula = str(row.get("recommended_formula") or "").strip()
        matches = str(row.get("matches_baseline") or "").strip().lower()
        if scenario and formula and formula != baseline_formula and matches != "yes":
            scenarios.append(scenario)
    return sorted(set(scenarios))


def formula_names(rows: list[dict[str, str]], handoff: dict[str, Any]) -> list[str]:
    names = [str(item) for item in handoff.get("formulas", []) if str(item)]
    names.extend(str(row.get("formula") or "") for row in rows if row.get("formula"))
    return sorted(set(names))


def validate_csv_station_aggregation(rows: list[dict[str, str]], path: Path, errors: list[dict[str, object]]) -> None:
    for index, row in enumerate(rows, start=1):
        validate_station_aggregation(f"{path.name} row {index}", row.get("station_aggregation"), errors)


def narrative_status(handoff: dict[str, Any], invalid: bool) -> str:
    if invalid:
        return "INVALID_INPUTS"
    return str(handoff.get("baseline_narrative_status") or "")


def build_payload(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    errors: list[dict[str, object]] = []
    release_summary = load_required_json(release_dir / "release_package_summary.json", errors)
    handoff = load_required_json(release_dir / "pgd_baseline_narrative_handoff.json", errors)
    readiness = load_required_json(release_dir / "pgd_release_readiness.json", errors)
    reviewed = load_required_json(release_dir / "reviewed_release_summary.json", errors)
    formula_rows = load_required_csv(release_dir / "formula_comparison.csv", errors)
    sensitivity_rows = load_required_csv(release_dir / "sensitivity_recommendations.csv", errors)

    for name, payload in [
        ("release_package_summary", release_summary),
        ("pgd_baseline_narrative_handoff", handoff),
        ("pgd_release_readiness", readiness),
        ("reviewed_release_summary", reviewed),
    ]:
        validate_status(name, payload, errors)
    for product, payload in [
        ("release_package_summary", release_summary),
        ("pgd_baseline_narrative_handoff", handoff),
        ("pgd_release_readiness", readiness),
    ]:
        validate_station_aggregation(product, payload.get("station_aggregation"), errors)
    validate_station_aggregation("pgd_baseline_narrative_handoff.station_aggregation_method", handoff.get("station_aggregation_method"), errors)
    validate_csv_station_aggregation(formula_rows, release_dir / "formula_comparison.csv", errors)
    validate_csv_station_aggregation(sensitivity_rows, release_dir / "sensitivity_recommendations.csv", errors)

    baseline_formula = str(handoff.get("baseline_formula") or release_summary.get("recommended_formula") or readiness.get("recommended_formula") or "")
    baseline_metrics = baseline_formula_row(formula_rows, baseline_formula)
    sensitivity_switches = switch_scenarios(sensitivity_rows, baseline_formula)
    requires_caveat = bool_value(handoff.get("requires_sensitivity_caveat")) or bool_value(release_summary.get("requires_sensitivity_caveat")) or bool(sensitivity_switches)
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "baseline_formula": baseline_formula,
        "station_aggregation": str(handoff.get("station_aggregation") or release_summary.get("station_aggregation") or ""),
        "station_aggregation_method": STATION_AGGREGATION,
        "formula_comparison_scope": str(handoff.get("formula_comparison_scope") or "formula_only"),
        "narrative_status": narrative_status(handoff, bool(errors)),
        "overall_release_readiness_status": str(handoff.get("overall_release_readiness_status") or readiness.get("readiness_status") or ""),
        "comparison_formula_review_status": str(handoff.get("comparison_formula_review_status") or ""),
        "pgd_event_count": int_value(release_summary.get("pgd_event_count")),
        "ready_event_count": int_value(handoff.get("ready_event_count") or release_summary.get("ready_event_count") or readiness.get("ready_event_count")),
        "reviewed_release_count": int_value(handoff.get("reviewed_release_count") or reviewed.get("reviewed_release_count")),
        "recommended_formula_blocker_count": int_value(handoff.get("recommended_formula_blocker_count")),
        "comparison_formula_blocker_count": int_value(handoff.get("comparison_formula_blocker_count") or readiness.get("blocker_count")),
        "manual_decisions_written": int_value(handoff.get("manual_decisions_written")),
        "requires_sensitivity_caveat": requires_caveat,
        "sensitivity_switch_scenarios": list(release_summary.get("sensitivity_switch_scenarios") or sensitivity_switches),
        "formula_count": len(formula_names(formula_rows, handoff)),
        "formulas": formula_names(formula_rows, handoff),
        "baseline_metrics": {
            "mae_mw": str(baseline_metrics.get("mae_mw") or ""),
            "rmse_mw": str(baseline_metrics.get("rmse_mw") or ""),
            "median_abs_error_mw": str(baseline_metrics.get("median_abs_error_mw") or ""),
            "residual_outlier_count": str(baseline_metrics.get("residual_outlier_count") or ""),
            "event_count": str(baseline_metrics.get("event_count") or ""),
        },
        "errors": errors,
        "next_actions": [],
    }
    payload["next_actions"] = next_actions(payload)
    return payload


def next_actions(payload: dict[str, Any]) -> list[str]:
    if payload["status"] != "OK":
        return ["Regenerate valid PGD release products with station_aggregation=median."]
    actions = ["Use this as a baseline narrative draft, not as a completed manual review record."]
    if payload.get("requires_sensitivity_caveat"):
        actions.append("Keep the sensitivity caveat in any scientific text.")
    if payload.get("comparison_formula_review_status") == "NEEDS_COMPARISON_REVIEW":
        actions.append("Complete comparison-formula review before declaring full formula-review readiness.")
    return actions


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(markdown_escape(row.get(field, "")) for field in fields) + " |")
    return lines


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    metrics = dict(payload.get("baseline_metrics") or {})
    switch_scenarios = list(payload.get("sensitivity_switch_scenarios") or [])
    formulas = ", ".join(f"`{formula}`" for formula in payload.get("formulas", []))
    lines = [
        "# PGD Baseline Science Narrative",
        "",
        "## Baseline Conclusion",
        "",
        f"The baseline PGD formula is `{payload.get('baseline_formula', '')}` under one station aggregation method: `median`. "
        "The comparison is a formula-only comparison; the formula labels are not alternative aggregation methods.",
        "",
        f"- Narrative status: `{payload.get('narrative_status', '')}`",
        f"- PGD-evaluable events: {payload.get('pgd_event_count', 0)}",
        f"- Ready baseline release events: {payload.get('ready_event_count', 0)}",
        f"- Reviewed release events: {payload.get('reviewed_release_count', 0)}",
        f"- Baseline MAE/RMSE: {metrics.get('mae_mw', '')} / {metrics.get('rmse_mw', '')} Mw",
        "",
        "## Formula Scope",
        "",
        f"Formulas compared under median aggregation: {formulas}.",
        "",
        "## Caveats",
        "",
    ]
    if payload.get("requires_sensitivity_caveat"):
        lines.append(
            "A sensitivity caveat is required because nearby PGD component, distance, or calibration choices can change the recommended formula."
        )
    else:
        lines.append("No sensitivity caveat is currently required by the release products.")
    lines.extend(
        [
            f"Sensitivity switch scenarios: {', '.join(f'`{scenario}`' for scenario in switch_scenarios) or 'none'}.",
            "",
            "## Review Boundary",
            "",
        ]
    )
    if payload.get("comparison_formula_review_status") == "NEEDS_COMPARISON_REVIEW":
        lines.append(
            "The comparison-formula review remains pending; blockers such as `crowell_2016_gfast` are not cleared by this narrative."
        )
    else:
        lines.append(f"Comparison-formula review status: `{payload.get('comparison_formula_review_status', '')}`.")
    lines.extend(
        [
            "This generated narrative does not write manual decisions and does not replace residual-review starter decisions.",
            "",
            "## Machine Summary",
            "",
            *markdown_table(
                [
                    {
                        "baseline_formula": payload.get("baseline_formula", ""),
                        "station_aggregation": payload.get("station_aggregation", ""),
                        "ready_event_count": payload.get("ready_event_count", 0),
                        "comparison_formula_blocker_count": payload.get("comparison_formula_blocker_count", 0),
                        "manual_decisions_written": payload.get("manual_decisions_written", 0),
                    }
                ],
                [
                    "baseline_formula",
                    "station_aggregation",
                    "ready_event_count",
                    "comparison_formula_blocker_count",
                    "manual_decisions_written",
                ],
            ),
            "",
            "## Next Actions",
            "",
            *[f"- {action}" for action in payload.get("next_actions", [])],
            "",
        ]
    )
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "product", "path", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.release_dir / "pgd_baseline_science_narrative.json"
    out_md = args.out_md or args.release_dir / "pgd_baseline_science_narrative.md"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(
        "wrote PGD baseline science narrative: "
        f"status={payload['status']} narrative={payload['narrative_status']} json={out_json}"
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
