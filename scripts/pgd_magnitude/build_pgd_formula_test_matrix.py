#!/usr/bin/env python3
"""Build a median-only PGD formula testing matrix from release products."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract

STATION_AGGREGATION = pgd_contract.STATION_AGGREGATION_METHOD

MATRIX_FIELDS = [
    "formula",
    "station_aggregation",
    "baseline_event_count",
    "baseline_mae_mw",
    "baseline_rmse_mw",
    "baseline_median_abs_error_mw",
    "baseline_residual_outlier_count",
    "baseline_rank_by_mae",
    "baseline_recommended",
    "sensitivity_win_count",
    "sensitivity_scenario_count",
    "sensitivity_winning_scenarios",
    "sensitivity_switch_caveat",
    "release_role",
    "release_ready_event_count",
    "release_readiness_status",
    "review_work_items",
    "release_blocking_work_items",
    "pending_review_work_items",
    "test_status",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_formula_test_matrix.csv.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_formula_test_matrix.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_formula_test_matrix.md.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def truthy_yes(value: object) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def pending_status(value: object) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return False
    return text.startswith("PENDING") or text in {"NEEDS_REVIEW", "INVALID_DECISION"}


def validate_station_aggregation(
    *,
    rows: list[dict[str, str]],
    source_path: Path,
    row_label: str,
    errors: list[dict[str, object]],
) -> None:
    for index, row in enumerate(rows, start=1):
        value = str(row.get("station_aggregation") or "").strip()
        if value != STATION_AGGREGATION:
            errors.append(
                error(
                    "INVALID_STATION_AGGREGATION",
                    "PGD formula test matrix requires station_aggregation=median.",
                    path=str(source_path),
                    row=f"{row_label}_{index}",
                    formula=row.get("formula") or row.get("recommended_formula") or "",
                    station_aggregation=value,
                )
            )


def validate_json_station_aggregation(path: Path, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    value = str(payload.get("station_aggregation") or "").strip()
    if value and value != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD formula test matrix requires station_aggregation=median.",
                path=str(path),
                station_aggregation=value,
            )
        )


def load_required_csv(path: Path, errors: list[dict[str, object]]) -> list[dict[str, str]]:
    if not path.exists():
        errors.append(error("MISSING_INPUT", "Required PGD release CSV is missing.", path=str(path)))
        return []
    try:
        return read_csv(path)
    except (OSError, csv.Error) as exc:
        errors.append(error("READ_ERROR", "Could not read PGD release CSV.", path=str(path), detail=str(exc)))
        return []


def load_required_json(path: Path, errors: list[dict[str, object]]) -> dict[str, Any]:
    if not path.exists():
        errors.append(error("MISSING_INPUT", "Required PGD release JSON is missing.", path=str(path)))
        return {}
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(error("READ_ERROR", "Could not read PGD release JSON.", path=str(path), detail=str(exc)))
        return {}


def baseline_formula_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if str(row.get("comparison_group") or "").strip().lower() == "all"
        and str(row.get("comparison_value") or "").strip().upper() == "ALL"
    ]
    return selected or rows


def ranked_formula_rows(rows: list[dict[str, str]]) -> list[tuple[int, dict[str, str]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            finite_float(row.get("mae_mw")) if math.isfinite(finite_float(row.get("mae_mw"))) else float("inf"),
            finite_float(row.get("rmse_mw")) if math.isfinite(finite_float(row.get("rmse_mw"))) else float("inf"),
            str(row.get("formula") or ""),
        ),
    )
    return [(index, row) for index, row in enumerate(ordered, start=1)]


def sensitivity_wins(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    wins: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        formula = str(row.get("recommended_formula") or "").strip()
        scenario = str(row.get("scenario_id") or "").strip()
        if formula:
            wins[formula].append(scenario or "unnamed")
    return {formula: sorted(scenarios) for formula, scenarios in wins.items()}


def worklist_counts(rows: list[dict[str, str]]) -> tuple[Counter[str], Counter[str], Counter[str]]:
    review_items: Counter[str] = Counter()
    release_blocking: Counter[str] = Counter()
    pending_items: Counter[str] = Counter()
    for row in rows:
        formula = str(row.get("formula") or "").strip()
        if not formula:
            continue
        review_items[formula] += 1
        if truthy_yes(row.get("release_blocking")):
            release_blocking[formula] += 1
        if pending_status(row.get("worklist_status")) or truthy_yes(row.get("release_blocking")):
            pending_items[formula] += 1
    return review_items, release_blocking, pending_items


def formula_status(
    *,
    formula: str,
    recommended_formula: str,
    release_readiness_status: str,
    release_blocking_count: int,
    pending_count: int,
    sensitivity_win_count: int,
) -> str:
    if formula == recommended_formula and release_readiness_status and release_readiness_status != "READY":
        return "BASELINE_RECOMMENDED_REVIEW_BLOCKED"
    if formula == recommended_formula:
        return "BASELINE_RECOMMENDED"
    if release_blocking_count > 0 or pending_count > 0:
        return "COMPARISON_NEEDS_REVIEW"
    if sensitivity_win_count > 0:
        return "SENSITIVITY_WINNER"
    return "COMPARISON_TESTED"


def build_matrix(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    paths = {
        "formula_comparison": release_dir / "formula_comparison.csv",
        "sensitivity_recommendations": release_dir / "sensitivity_recommendations.csv",
        "residual_review_worklist": release_dir / "residual_review_worklist.csv",
        "release_package_summary": release_dir / "release_package_summary.json",
        "pgd_release_readiness": release_dir / "pgd_release_readiness.json",
    }
    errors: list[dict[str, object]] = []
    formula_rows = load_required_csv(paths["formula_comparison"], errors)
    sensitivity_rows = load_required_csv(paths["sensitivity_recommendations"], errors)
    worklist_rows = load_required_csv(paths["residual_review_worklist"], errors)
    release_summary = load_required_json(paths["release_package_summary"], errors)
    readiness = load_required_json(paths["pgd_release_readiness"], errors)

    validate_station_aggregation(rows=formula_rows, source_path=paths["formula_comparison"], row_label="formula", errors=errors)
    validate_station_aggregation(rows=sensitivity_rows, source_path=paths["sensitivity_recommendations"], row_label="sensitivity", errors=errors)
    validate_json_station_aggregation(paths["release_package_summary"], release_summary, errors)
    validate_json_station_aggregation(paths["pgd_release_readiness"], readiness, errors)

    baseline_rows = baseline_formula_rows(formula_rows)
    if formula_rows and not baseline_rows:
        errors.append(error("NO_BASELINE_FORMULA_ROWS", "No baseline formula comparison rows were found.", path=str(paths["formula_comparison"])))

    recommended_formula = str(release_summary.get("recommended_formula") or readiness.get("recommended_formula") or "").strip()
    station_aggregation = str(release_summary.get("station_aggregation") or readiness.get("station_aggregation") or STATION_AGGREGATION).strip()
    release_readiness_status = str(readiness.get("readiness_status") or "").strip()
    release_ready_event_count = str(release_summary.get("ready_event_count") or readiness.get("ready_event_count") or "")
    sensitivity_scenario_count = len(sensitivity_rows)
    sensitivity_switch_caveat = truthy_yes(release_summary.get("requires_sensitivity_caveat")) or any(
        str(row.get("recommended_formula") or "").strip() not in {"", recommended_formula} for row in sensitivity_rows
    )

    wins = sensitivity_wins(sensitivity_rows)
    review_items, release_blocking, pending_items = worklist_counts(worklist_rows)

    rows: list[dict[str, str]] = []
    for rank, row in ranked_formula_rows(baseline_rows):
        formula = str(row.get("formula") or "").strip()
        if not formula:
            continue
        win_scenarios = wins.get(formula, [])
        release_blocking_count = release_blocking.get(formula, 0)
        pending_count = pending_items.get(formula, 0)
        rows.append(
            {
                "formula": formula,
                "station_aggregation": str(row.get("station_aggregation") or station_aggregation),
                "baseline_event_count": str(row.get("event_count") or ""),
                "baseline_mae_mw": str(row.get("mae_mw") or ""),
                "baseline_rmse_mw": str(row.get("rmse_mw") or ""),
                "baseline_median_abs_error_mw": str(row.get("median_abs_error_mw") or ""),
                "baseline_residual_outlier_count": str(row.get("residual_outlier_count") or ""),
                "baseline_rank_by_mae": str(rank),
                "baseline_recommended": "yes" if formula == recommended_formula else "no",
                "sensitivity_win_count": str(len(win_scenarios)),
                "sensitivity_scenario_count": str(sensitivity_scenario_count),
                "sensitivity_winning_scenarios": ";".join(win_scenarios),
                "sensitivity_switch_caveat": "yes" if sensitivity_switch_caveat else "no",
                "release_role": "recommended_baseline_formula" if formula == recommended_formula else "comparison_formula",
                "release_ready_event_count": release_ready_event_count if formula == recommended_formula else "",
                "release_readiness_status": release_readiness_status,
                "review_work_items": str(review_items.get(formula, 0)),
                "release_blocking_work_items": str(release_blocking_count),
                "pending_review_work_items": str(pending_count),
                "test_status": formula_status(
                    formula=formula,
                    recommended_formula=recommended_formula,
                    release_readiness_status=release_readiness_status,
                    release_blocking_count=release_blocking_count,
                    pending_count=pending_count,
                    sensitivity_win_count=len(win_scenarios),
                ),
            }
        )

    if not rows and not errors:
        errors.append(error("NO_FORMULA_ROWS", "No formula rows were available for the PGD formula test matrix."))

    return {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "station_aggregation": station_aggregation,
        "recommended_formula": recommended_formula,
        "formula_count": len(rows),
        "sensitivity_scenario_count": sensitivity_scenario_count,
        "release_readiness_status": release_readiness_status,
        "requires_sensitivity_caveat": bool(sensitivity_switch_caveat),
        "errors": errors,
        "matrix": rows,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATRIX_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MATRIX_FIELDS})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(markdown_escape(row.get(field, "")) for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload.get("matrix", [])
    errors = payload.get("errors", [])
    assert isinstance(rows, list)
    assert isinstance(errors, list)
    lines = [
        "# PGD Formula Test Matrix",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Recommended formula: `{payload.get('recommended_formula', '')}`",
        f"- Release readiness: `{payload.get('release_readiness_status', '')}`",
        f"- Sensitivity caveat required: `{str(payload.get('requires_sensitivity_caveat', False)).lower()}`",
        "",
        "The station aggregation method is fixed to `median`; the rows compare PGD scaling formulas, not aggregation methods.",
        "",
        "## Matrix",
        "",
        *markdown_table(
            rows,
            [
                "formula",
                "baseline_rank_by_mae",
                "baseline_mae_mw",
                "sensitivity_win_count",
                "release_blocking_work_items",
                "test_status",
            ],
        ),
        "",
    ]
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "message", "path", "row", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_csv = args.out_csv or args.release_dir / "pgd_formula_test_matrix.csv"
    out_json = args.out_json or args.release_dir / "pgd_formula_test_matrix.json"
    out_md = args.out_md or args.release_dir / "pgd_formula_test_matrix.md"
    payload = build_matrix(args.release_dir)
    rows = payload.get("matrix", [])
    assert isinstance(rows, list)
    write_csv(out_csv, rows)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(f"wrote PGD formula test matrix: status={payload['status']} formulas={len(rows)} csv={out_csv}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
