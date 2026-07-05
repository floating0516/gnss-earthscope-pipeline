#!/usr/bin/env python3
"""Analyze PGD release-blocking review rows without making manual decisions."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract

STATION_AGGREGATION = pgd_contract.STATION_AGGREGATION_METHOD

ANALYSIS_FIELDS = [
    "blocker_priority",
    "worklist_priority",
    "event_id",
    "formula",
    "recommended_formula",
    "formula_scope",
    "manual_decision_written",
    "worklist_status",
    "blocker_status",
    "blocker_reason",
    "abs_residual_mw",
    "suggested_review_status",
    "suggested_review_cause",
    "next_review_action",
    "review_focus",
    "release_status",
    "release_failure_reasons",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "best_formula_for_event",
    "best_formula_abs_residual_mw",
    "formula_residuals_for_event",
    "packet_path",
    "analysis_note",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_analysis.csv.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_analysis.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_analysis.md.")
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


def truthy_yes(value: object) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unfilled") for row in rows)
    return {key: counts[key] for key in sorted(counts)}


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


def validate_status(name: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    status = str(payload.get("status") or "").strip()
    if status and status != "OK":
        errors.append(error("INVALID_INPUT_STATUS", "Required PGD release product is not OK.", product=name, status=status))


def validate_station_aggregation(name: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    value = str(payload.get("station_aggregation") or "").strip()
    if value and value != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD release blocker analysis requires station_aggregation=median.",
                product=name,
                station_aggregation=value,
            )
        )


def formula_scope(formula: str, recommended_formula: str) -> str:
    return "recommended_formula" if formula == recommended_formula else "comparison_formula"


def analysis_note(row: dict[str, str], recommended_formula: str) -> str:
    formula = str(row.get("formula") or "")
    if formula == recommended_formula:
        return "This blocker is on the recommended baseline formula and must be reviewed before interpreting the release set."
    return "This blocker is on a comparison formula; it blocks review readiness but does not write a manual decision or change the recommended formula."


def build_analysis_rows(worklist_rows: list[dict[str, str]], recommended_formula: str) -> list[dict[str, str]]:
    blockers = [row for row in worklist_rows if truthy_yes(row.get("release_blocking"))]
    rows: list[dict[str, str]] = []
    for index, row in enumerate(blockers, start=1):
        formula = str(row.get("formula") or "")
        rows.append(
            {
                "blocker_priority": str(index),
                "worklist_priority": str(row.get("worklist_priority") or ""),
                "event_id": str(row.get("event_id") or ""),
                "formula": formula,
                "recommended_formula": recommended_formula,
                "formula_scope": formula_scope(formula, recommended_formula),
                "manual_decision_written": "no",
                "worklist_status": str(row.get("worklist_status") or ""),
                "blocker_status": str(row.get("blocker_status") or ""),
                "blocker_reason": str(row.get("blocker_reason") or ""),
                "abs_residual_mw": str(row.get("abs_residual_mw") or ""),
                "suggested_review_status": str(row.get("suggested_review_status") or row.get("triage_status_suggestion") or ""),
                "suggested_review_cause": str(row.get("suggested_review_cause") or row.get("triage_cause_suggestion") or ""),
                "next_review_action": str(row.get("next_review_action") or row.get("next_decision_action") or ""),
                "review_focus": str(row.get("review_focus") or ""),
                "release_status": str(row.get("release_status") or ""),
                "release_failure_reasons": str(row.get("release_failure_reasons") or ""),
                "pgd_reliability": str(row.get("pgd_reliability") or ""),
                "usable_station_count": str(row.get("usable_station_count") or ""),
                "median_pgd_snr": str(row.get("median_pgd_snr") or ""),
                "median_distance_km": str(row.get("median_distance_km") or ""),
                "best_formula_for_event": str(row.get("best_formula_for_event") or ""),
                "best_formula_abs_residual_mw": str(row.get("best_formula_abs_residual_mw") or ""),
                "formula_residuals_for_event": str(row.get("formula_residuals_for_event") or ""),
                "packet_path": str(row.get("packet_path") or ""),
                "analysis_note": analysis_note(row, recommended_formula),
            }
        )
    return rows


def next_actions(payload: dict[str, Any]) -> list[str]:
    if payload["status"] != "OK":
        return ["Regenerate the standard PGD release products, then rebuild blocker analysis."]
    if payload["blocker_count"] == 0:
        return ["No release-blocking rows remain; check pgd_release_readiness.json for final readiness."]
    actions = [
        "Open pgd_release_blocker_analysis.csv alongside release_blocking_review_starter.csv.",
        "Inspect packet paths for each blocker before filling manual review fields in a starter copy.",
    ]
    if payload["comparison_formula_blocker_count"] and not payload["recommended_formula_blocker_count"]:
        actions.append("All current release blockers are comparison formula blockers; decide whether those comparison formula residuals should remain release-blocking.")
    if payload["recommended_formula_blocker_count"]:
        actions.append("At least one blocker is on the recommended formula; prioritize those packets before release interpretation.")
    actions.append("Re-run run_pgd_science_bundle.py with --starter-annotations <completed-starter.csv> after review.")
    return actions


def build_payload(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    paths = {
        "worklist": release_dir / "residual_review_worklist.csv",
        "formula_matrix_csv": release_dir / "pgd_formula_test_matrix.csv",
        "formula_matrix_json": release_dir / "pgd_formula_test_matrix.json",
        "release_summary": release_dir / "release_package_summary.json",
        "readiness": release_dir / "pgd_release_readiness.json",
    }
    errors: list[dict[str, object]] = []
    worklist_rows = load_required_csv(paths["worklist"], errors)
    _matrix_rows = load_required_csv(paths["formula_matrix_csv"], errors)
    matrix = load_required_json(paths["formula_matrix_json"], errors)
    release_summary = load_required_json(paths["release_summary"], errors)
    readiness = load_required_json(paths["readiness"], errors)
    for name, payload in [("pgd_formula_test_matrix", matrix), ("release_package_summary", release_summary), ("pgd_release_readiness", readiness)]:
        validate_status(name, payload, errors)
        validate_station_aggregation(name, payload, errors)

    recommended_formula = str(
        release_summary.get("recommended_formula")
        or matrix.get("recommended_formula")
        or readiness.get("recommended_formula")
        or ""
    )
    station_aggregation = str(
        release_summary.get("station_aggregation")
        or matrix.get("station_aggregation")
        or readiness.get("station_aggregation")
        or STATION_AGGREGATION
    )
    rows = build_analysis_rows(worklist_rows, recommended_formula)
    recommended_formula_blocker_count = sum(1 for row in rows if row["formula_scope"] == "recommended_formula")
    comparison_formula_blocker_count = sum(1 for row in rows if row["formula_scope"] == "comparison_formula")
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "recommended_formula": recommended_formula,
        "station_aggregation": station_aggregation,
        "release_readiness_status": str(readiness.get("readiness_status") or ""),
        "blocker_count": len(rows),
        "recommended_formula_blocker_count": recommended_formula_blocker_count,
        "comparison_formula_blocker_count": comparison_formula_blocker_count,
        "blockers_by_formula": count_by(rows, "formula"),
        "blockers_by_formula_scope": count_by(rows, "formula_scope"),
        "blockers_by_suggested_review_status": count_by(rows, "suggested_review_status"),
        "blockers_by_suggested_review_cause": count_by(rows, "suggested_review_cause"),
        "blockers_by_release_status": count_by(rows, "release_status"),
        "blockers_by_next_review_action": count_by(rows, "next_review_action"),
        "manual_decisions_written": 0,
        "errors": errors,
        "next_actions": [],
        "blockers": rows,
    }
    payload["next_actions"] = next_actions(payload)
    return payload


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANALYSIS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in ANALYSIS_FIELDS})


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


def counter_rows(counter: dict[str, int], key_field: str) -> list[dict[str, object]]:
    return [{key_field: key, "count": value} for key, value in counter.items()]


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    blockers = payload.get("blockers", [])
    assert isinstance(blockers, list)
    lines = [
        "# PGD Release Blocker Analysis",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Recommended formula: `{payload.get('recommended_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Release readiness: `{payload.get('release_readiness_status', '')}`",
        f"- Release blockers: {payload.get('blocker_count', 0)}",
        f"- Recommended-formula blockers: {payload.get('recommended_formula_blocker_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        "",
        "This report does not write manual review decisions. It explains the release-blocking rows that still need a reviewer-filled starter copy.",
        "",
        "## Next Actions",
        "",
    ]
    for action in payload.get("next_actions", []):
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Blockers By Formula",
            "",
            *markdown_table(counter_rows(payload.get("blockers_by_formula", {}), "formula"), ["formula", "count"]),
            "",
            "## Release Blockers",
            "",
            *markdown_table(
                blockers,
                [
                    "blocker_priority",
                    "event_id",
                    "formula",
                    "formula_scope",
                    "abs_residual_mw",
                    "suggested_review_status",
                    "packet_path",
                ],
            ),
            "",
        ]
    )
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "path", "product", "status"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_csv = args.out_csv or args.release_dir / "pgd_release_blocker_analysis.csv"
    out_json = args.out_json or args.release_dir / "pgd_release_blocker_analysis.json"
    out_md = args.out_md or args.release_dir / "pgd_release_blocker_analysis.md"
    payload = build_payload(args.release_dir)
    blockers = payload.get("blockers", [])
    assert isinstance(blockers, list)
    write_csv(out_csv, blockers)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(f"wrote PGD release blocker analysis: status={payload['status']} blockers={len(blockers)} csv={out_csv}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
