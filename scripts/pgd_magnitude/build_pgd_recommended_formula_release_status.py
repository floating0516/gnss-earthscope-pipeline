#!/usr/bin/env python3
"""Summarize recommended-formula PGD release status without writing decisions."""

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

STATUS_FIELDS = [
    "formula_scope",
    "formula",
    "formula_release_status",
    "recommended_formula",
    "station_aggregation",
    "baseline_rank_by_mae",
    "baseline_recommended",
    "sensitivity_win_count",
    "test_status",
    "blocker_count",
    "ready_event_count",
    "reviewed_release_count",
    "overall_release_readiness_status",
    "manual_decision_written",
    "action",
    "note",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_recommended_formula_release_status.csv.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_recommended_formula_release_status.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_recommended_formula_release_status.md.")
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


def validate_status(product: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    status = str(payload.get("status") or "").strip()
    if status and status != "OK":
        errors.append(error("INVALID_INPUT_STATUS", "Required PGD release product is not OK.", product=product, status=status))


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    text = str(value or "").strip()
    if text and text != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD recommended-formula release status requires station_aggregation=median.",
                product=product,
                station_aggregation=text,
            )
        )


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return default


def bool_value(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def blockers_by_formula(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("blockers_by_formula")
    if not isinstance(raw, dict):
        return {}
    return {str(key): int_value(value) for key, value in raw.items()}


def formula_scope(formula: str, recommended_formula: str) -> str:
    return "recommended_formula" if formula == recommended_formula else "comparison_formula"


def recommended_formula_status(ready_event_count: int, recommended_blockers: int, invalid: bool) -> str:
    if invalid:
        return "INVALID_INPUTS"
    if ready_event_count <= 0:
        return "NO_READY_EVENTS"
    if recommended_blockers:
        return "BLOCKED_ON_RECOMMENDED_FORMULA_REVIEW"
    return "READY_FOR_BASELINE_NARRATIVE"


def comparison_status(blockers: int) -> str:
    return "NEEDS_COMPARISON_REVIEW" if blockers else "COMPARISON_CLEAR"


def action_for_row(scope: str, status: str, formula: str) -> str:
    if status == "READY_FOR_BASELINE_NARRATIVE":
        return "USE_RECOMMENDED_FORMULA_FOR_BASELINE_NARRATIVE_WITH_RECORDED_CAVEATS"
    if status == "BLOCKED_ON_RECOMMENDED_FORMULA_REVIEW":
        return "REVIEW_RECOMMENDED_FORMULA_BLOCKERS_BEFORE_BASELINE_NARRATIVE"
    if status == "NO_READY_EVENTS":
        return "REVIEW_RELEASE_SET_GATES_BEFORE_BASELINE_NARRATIVE"
    if status == "NEEDS_COMPARISON_REVIEW":
        return "COMPLETE_COMPARISON_FORMULA_REVIEW_STARTER_ROWS"
    if scope == "comparison_formula":
        return "KEEP_AS_COMPARISON_FORMULA_CONTEXT"
    return f"REVIEW_{formula}"


def note_for_row(scope: str, status: str, formula: str) -> str:
    if status == "READY_FOR_BASELINE_NARRATIVE":
        return "Recommended formula has no release-blocking rows; this does not clear comparison-formula blockers or write manual decisions."
    if status == "BLOCKED_ON_RECOMMENDED_FORMULA_REVIEW":
        return "Recommended formula still has release-blocking rows; manual review is required before baseline narrative use."
    if status == "NEEDS_COMPARISON_REVIEW":
        return "Comparison formula has pending release-blocking review rows; decide through the starter workflow."
    if scope == "comparison_formula":
        return "Comparison formula has no current release-blocking rows."
    return f"{formula} status derived from existing release products only."


def build_rows(
    matrix_rows: list[dict[str, str]],
    recommended_formula: str,
    station_aggregation: str,
    ready_event_count: int,
    reviewed_release_count: int,
    overall_readiness: str,
    blocker_counts: dict[str, int],
    recommended_status: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for matrix in matrix_rows:
        formula = str(matrix.get("formula") or "")
        if not formula:
            continue
        scope = formula_scope(formula, recommended_formula)
        blockers = blocker_counts.get(formula, int_value(matrix.get("release_blocking_work_items")))
        status = recommended_status if scope == "recommended_formula" else comparison_status(blockers)
        rows.append(
            {
                "formula_scope": scope,
                "formula": formula,
                "formula_release_status": status,
                "recommended_formula": recommended_formula,
                "station_aggregation": station_aggregation,
                "baseline_rank_by_mae": str(matrix.get("baseline_rank_by_mae") or ""),
                "baseline_recommended": str(matrix.get("baseline_recommended") or ""),
                "sensitivity_win_count": str(matrix.get("sensitivity_win_count") or ""),
                "test_status": str(matrix.get("test_status") or ""),
                "blocker_count": str(blockers),
                "ready_event_count": str(ready_event_count),
                "reviewed_release_count": str(reviewed_release_count),
                "overall_release_readiness_status": overall_readiness,
                "manual_decision_written": "no",
                "action": action_for_row(scope, status, formula),
                "note": note_for_row(scope, status, formula),
            }
        )
    rows.sort(key=lambda row: (0 if row["formula_scope"] == "recommended_formula" else 1, int_value(row["baseline_rank_by_mae"], 999), row["formula"]))
    return rows


def next_actions(payload: dict[str, Any]) -> list[str]:
    if payload["status"] != "OK":
        return ["Regenerate the standard PGD release products, then rebuild recommended-formula status."]
    if payload["recommended_formula_release_status"] == "BLOCKED_ON_RECOMMENDED_FORMULA_REVIEW":
        return ["Review recommended formula blockers before using the baseline PGD release narrative."]
    if payload["recommended_formula_release_status"] == "NO_READY_EVENTS":
        return ["Review release-set quality gates; no ready PGD release events are available for the recommended formula."]
    actions = ["Use the recommended formula for the baseline PGD narrative with the recorded sensitivity caveat."]
    if payload["comparison_formula_blocker_count"]:
        actions.append("Complete comparison-formula blocker review through release_blocking_review_starter.csv before declaring the full formula review complete.")
    else:
        actions.append("Recommended and comparison formula review blockers are clear; check pgd_release_readiness.json for final readiness.")
    return actions


def build_payload(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    errors: list[dict[str, object]] = []
    release_summary = load_required_json(release_dir / "release_package_summary.json", errors)
    readiness = load_required_json(release_dir / "pgd_release_readiness.json", errors)
    formula_matrix = load_required_json(release_dir / "pgd_formula_test_matrix.json", errors)
    blocker_analysis = load_required_json(release_dir / "pgd_release_blocker_analysis.json", errors)
    reviewed_summary = load_required_json(release_dir / "reviewed_release_summary.json", errors)
    matrix_rows = load_required_csv(release_dir / "pgd_formula_test_matrix.csv", errors)

    for name, payload in [
        ("release_package_summary", release_summary),
        ("pgd_release_readiness", readiness),
        ("pgd_formula_test_matrix", formula_matrix),
        ("pgd_release_blocker_analysis", blocker_analysis),
        ("reviewed_release_summary", reviewed_summary),
    ]:
        validate_status(name, payload, errors)
        validate_station_aggregation(name, payload.get("station_aggregation"), errors)
    for index, row in enumerate(matrix_rows, start=1):
        validate_station_aggregation(f"pgd_formula_test_matrix.csv row {index}", row.get("station_aggregation"), errors)

    recommended_formula = str(
        release_summary.get("recommended_formula")
        or formula_matrix.get("recommended_formula")
        or blocker_analysis.get("recommended_formula")
        or readiness.get("recommended_formula")
        or ""
    )
    station_aggregation = str(
        release_summary.get("station_aggregation")
        or formula_matrix.get("station_aggregation")
        or blocker_analysis.get("station_aggregation")
        or readiness.get("station_aggregation")
        or STATION_AGGREGATION
    )
    ready_event_count = int_value(release_summary.get("ready_event_count") or readiness.get("ready_event_count"))
    reviewed_release_count = int_value(reviewed_summary.get("reviewed_release_count"))
    recommended_blockers = int_value(blocker_analysis.get("recommended_formula_blocker_count"))
    comparison_blockers = int_value(blocker_analysis.get("comparison_formula_blocker_count"))
    blocker_counts = blockers_by_formula(blocker_analysis)
    overall_readiness = str(readiness.get("readiness_status") or "")
    rec_status = recommended_formula_status(ready_event_count, recommended_blockers, bool(errors))
    rows = build_rows(
        matrix_rows,
        recommended_formula,
        station_aggregation,
        ready_event_count,
        reviewed_release_count,
        overall_readiness,
        blocker_counts,
        rec_status,
    )
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "recommended_formula": recommended_formula,
        "station_aggregation": station_aggregation,
        "recommended_formula_release_status": rec_status,
        "overall_release_readiness_status": overall_readiness if not errors else "INVALID_INPUTS",
        "comparison_formula_review_status": "NEEDS_COMPARISON_REVIEW" if comparison_blockers else "CLEAR",
        "ready_event_count": ready_event_count,
        "reviewed_release_count": reviewed_release_count,
        "recommended_formula_blocker_count": recommended_blockers,
        "comparison_formula_blocker_count": comparison_blockers,
        "manual_decisions_written": 0,
        "requires_sensitivity_caveat": bool_value(release_summary.get("requires_sensitivity_caveat")),
        "row_count": len(rows),
        "errors": errors,
        "next_actions": [],
        "formula_rows": rows,
    }
    payload["next_actions"] = next_actions(payload)
    return payload


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload.get("formula_rows", [])
    assert isinstance(rows, list)
    lines = [
        "# PGD Recommended Formula Release Status",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Recommended formula: `{payload.get('recommended_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Recommended-formula release status: `{payload.get('recommended_formula_release_status', '')}`",
        f"- Overall release readiness: `{payload.get('overall_release_readiness_status', '')}`",
        f"- Recommended-formula blockers: {payload.get('recommended_formula_blocker_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Sensitivity caveat required: `{payload.get('requires_sensitivity_caveat', False)}`",
        "",
        "This report separates recommended-formula readiness from comparison-formula blockers. It does not write manual decisions or clear comparison-formula review items.",
        "",
        "## Formula Status",
        "",
        *markdown_table(
            rows,
            [
                "formula_scope",
                "formula",
                "formula_release_status",
                "blocker_count",
                "action",
            ],
        ),
        "",
        "## Next Actions",
        "",
        *[f"- {action}" for action in payload.get("next_actions", [])],
        "",
    ]
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "product", "path", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_csv = args.out_csv or args.release_dir / "pgd_recommended_formula_release_status.csv"
    out_json = args.out_json or args.release_dir / "pgd_recommended_formula_release_status.json"
    out_md = args.out_md or args.release_dir / "pgd_recommended_formula_release_status.md"
    payload = build_payload(args.release_dir)
    rows = payload.get("formula_rows", [])
    assert isinstance(rows, list)
    write_csv(out_csv, rows)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(
        "wrote PGD recommended formula release status: "
        f"status={payload['status']} recommended={payload['recommended_formula_release_status']} csv={out_csv}"
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
