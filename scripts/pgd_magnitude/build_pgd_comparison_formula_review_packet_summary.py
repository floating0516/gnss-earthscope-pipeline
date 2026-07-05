#!/usr/bin/env python3
"""Build a compact review summary for PGD comparison-formula blockers."""

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

SUMMARY_FIELDS = [
    "review_priority",
    "event_id",
    "formula",
    "recommended_formula",
    "station_aggregation",
    "formula_scope",
    "baseline_rank_by_mae",
    "baseline_mae_mw",
    "baseline_rmse_mw",
    "sensitivity_winning_scenarios",
    "formula_test_status",
    "release_readiness_status",
    "packet_path",
    "packet_exists",
    "abs_residual_mw",
    "suggested_review_status",
    "suggested_review_cause",
    "pre_decision_checks",
    "next_review_action",
    "review_focus",
    "release_status",
    "release_failure_reasons",
    "formula_residuals_for_event",
    "manual_decision_state",
    "manual_review_status",
    "accepted_for_release",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_comparison_formula_review_packet_summary.csv.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_comparison_formula_review_packet_summary.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_comparison_formula_review_packet_summary.md.")
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
    if status and status not in {"OK", "NO_READY_EVENTS"}:
        errors.append(error("INVALID_INPUT_STATUS", "Required PGD release product is not OK.", product=product, status=status))


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    station_aggregation = str(value or "").strip()
    if station_aggregation != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD comparison-formula review packet summary requires station_aggregation=median.",
                product=product,
                station_aggregation=station_aggregation,
            )
        )


def validate_csv_station_aggregation(path: Path, rows: list[dict[str, str]], errors: list[dict[str, object]]) -> None:
    for index, row in enumerate(rows, start=1):
        if "station_aggregation" in row:
            validate_station_aggregation(f"{path.name} row {index}", row.get("station_aggregation"), errors)


def key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("formula") or ""))


def formula_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("formula") or ""): row for row in rows if row.get("formula")}


def packet_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {key(row): row for row in rows if all(key(row))}


def manual_decision_state(row: dict[str, str]) -> str:
    manual_fields = ["manual_review_status", "manual_review_cause", "manual_review_notes", "accepted_for_release", "reviewer", "reviewed_at"]
    return "filled" if any(str(row.get(field) or "").strip() for field in manual_fields) else "blank"


def count_values(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unfilled").strip() or "unfilled" for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return default


def summary_rows(
    *,
    release_dir: Path,
    guide_rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    packet_rows: list[dict[str, str]],
    readiness: dict[str, Any],
    errors: list[dict[str, object]],
) -> list[dict[str, str]]:
    formulas = formula_lookup(matrix_rows)
    packets = packet_lookup(packet_rows)
    rows: list[dict[str, str]] = []
    for guide in guide_rows:
        if str(guide.get("formula_scope") or "").strip() != "comparison_formula":
            continue
        formula = str(guide.get("formula") or "")
        matrix = formulas.get(formula, {})
        packet = packets.get(key(guide), {})
        packet_path = str(guide.get("packet_path") or packet.get("packet_path") or "")
        packet_exists = "yes" if packet_path and (release_dir / packet_path).exists() else "no"
        if packet_exists == "no":
            errors.append(error("MISSING_PACKET", "Comparison-formula review packet is missing.", event_id=guide.get("event_id", ""), formula=formula, packet_path=packet_path))
        row = {
            "review_priority": str(guide.get("guide_priority") or guide.get("blocker_priority") or ""),
            "event_id": str(guide.get("event_id") or ""),
            "formula": formula,
            "recommended_formula": str(guide.get("recommended_formula") or readiness.get("recommended_formula") or ""),
            "station_aggregation": STATION_AGGREGATION,
            "formula_scope": "comparison_formula",
            "baseline_rank_by_mae": str(matrix.get("baseline_rank_by_mae") or ""),
            "baseline_mae_mw": str(matrix.get("baseline_mae_mw") or ""),
            "baseline_rmse_mw": str(matrix.get("baseline_rmse_mw") or ""),
            "sensitivity_winning_scenarios": str(matrix.get("sensitivity_winning_scenarios") or ""),
            "formula_test_status": str(matrix.get("test_status") or ""),
            "release_readiness_status": str(readiness.get("readiness_status") or ""),
            "packet_path": packet_path,
            "packet_exists": packet_exists,
            "abs_residual_mw": str(packet.get("abs_residual_mw") or guide.get("abs_residual_mw") or ""),
            "suggested_review_status": str(guide.get("suggested_review_status") or packet.get("triage_status_suggestion") or ""),
            "suggested_review_cause": str(guide.get("suggested_review_cause") or packet.get("triage_cause_suggestion") or ""),
            "pre_decision_checks": str(guide.get("pre_decision_checks") or ""),
            "next_review_action": str(packet.get("next_review_action") or ""),
            "review_focus": str(guide.get("review_focus") or ""),
            "release_status": str(guide.get("release_status") or packet.get("release_status") or ""),
            "release_failure_reasons": str(guide.get("release_failure_reasons") or ""),
            "formula_residuals_for_event": str(guide.get("formula_residuals_for_event") or ""),
            "manual_decision_state": manual_decision_state(guide),
            "manual_review_status": str(guide.get("manual_review_status") or ""),
            "accepted_for_release": str(guide.get("accepted_for_release") or ""),
        }
        rows.append(row)
    rows.sort(key=lambda row: (int_value(row.get("review_priority")), row.get("event_id", ""), row.get("formula", "")))
    return rows


def build_payload(release_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    release_dir = release_dir.expanduser()
    errors: list[dict[str, object]] = []
    guide_csv = release_dir / "pgd_release_blocker_decision_guide.csv"
    guide_json_path = release_dir / "pgd_release_blocker_decision_guide.json"
    analysis_json_path = release_dir / "pgd_release_blocker_analysis.json"
    readiness_json_path = release_dir / "pgd_release_readiness.json"
    matrix_csv_path = release_dir / "pgd_formula_test_matrix.csv"
    matrix_json_path = release_dir / "pgd_formula_test_matrix.json"
    packet_index_path = release_dir / "residual_review_packet_index.csv"

    guide_rows = load_required_csv(guide_csv, errors)
    matrix_rows = load_required_csv(matrix_csv_path, errors)
    packet_rows = load_required_csv(packet_index_path, errors)
    guide_json = load_required_json(guide_json_path, errors)
    analysis = load_required_json(analysis_json_path, errors)
    readiness = load_required_json(readiness_json_path, errors)
    matrix_json = load_required_json(matrix_json_path, errors)

    for name, payload in [
        ("pgd_release_blocker_decision_guide", guide_json),
        ("pgd_release_blocker_analysis", analysis),
        ("pgd_release_readiness", readiness),
        ("pgd_formula_test_matrix", matrix_json),
    ]:
        validate_status(name, payload, errors)
        validate_station_aggregation(name, payload.get("station_aggregation"), errors)
    validate_csv_station_aggregation(matrix_csv_path, matrix_rows, errors)

    rows = summary_rows(
        release_dir=release_dir,
        guide_rows=guide_rows,
        matrix_rows=matrix_rows,
        packet_rows=packet_rows,
        readiness=readiness,
        errors=errors,
    )
    packet_exists_count = sum(1 for row in rows if row.get("packet_exists") == "yes")
    manual_decisions_written = sum(1 for row in rows if row.get("manual_decision_state") == "filled")
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "recommended_formula": str(readiness.get("recommended_formula") or analysis.get("recommended_formula") or guide_json.get("recommended_formula") or ""),
        "station_aggregation": STATION_AGGREGATION,
        "formula_comparison_scope": "comparison_formula_review_packets",
        "release_readiness_status": str(readiness.get("readiness_status") or ""),
        "row_count": len(rows),
        "comparison_formula_blocker_count": len(rows),
        "source_comparison_formula_blocker_count": int_value(analysis.get("comparison_formula_blocker_count") or guide_json.get("comparison_formula_blocker_count")),
        "packet_exists_count": packet_exists_count,
        "missing_packet_count": len(rows) - packet_exists_count,
        "manual_decisions_written": manual_decisions_written,
        "blockers_by_formula": count_values(rows, "formula"),
        "suggested_review_status_counts": count_values(rows, "suggested_review_status"),
        "suggested_review_cause_counts": count_values(rows, "suggested_review_cause"),
        "manual_decision_state_counts": count_values(rows, "manual_decision_state"),
        "errors": errors,
    }
    return payload, rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any], rows: list[dict[str, str]]) -> None:
    errors = payload.get("errors", [])
    assert isinstance(errors, list)
    lines = [
        "# PGD Comparison-Formula Review Packet Summary",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Recommended baseline formula: `{payload.get('recommended_formula', '')}`",
        f"- Comparison-formula blocker packets: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Missing packets: {payload.get('missing_packet_count', 0)}",
        f"- Manual decisions written: {payload.get('manual_decisions_written', 0)}",
        "",
        "This product uses one station aggregation method: `median`. The rows are comparison-formula review packets; the formulas are not station aggregation methods. It does not write manual decisions or clear blockers.",
        "",
        "## Suggested Review Status Counts",
        "",
        *markdown_table([{"suggested_review_status": key, "count": value} for key, value in dict(payload.get("suggested_review_status_counts", {})).items()], ["suggested_review_status", "count"]),
        "",
        "## Review Packets",
        "",
        *markdown_table(rows, ["review_priority", "event_id", "formula", "baseline_rank_by_mae", "packet_exists", "suggested_review_status", "packet_path"]),
        "",
    ]
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "message", "event_id", "formula", "packet_path", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    release_dir = args.release_dir
    out_csv = args.out_csv or release_dir / "pgd_comparison_formula_review_packet_summary.csv"
    out_json = args.out_json or release_dir / "pgd_comparison_formula_review_packet_summary.json"
    out_md = args.out_md or release_dir / "pgd_comparison_formula_review_packet_summary.md"
    payload, rows = build_payload(release_dir)
    write_csv(out_csv, rows)
    write_json(out_json, payload)
    write_markdown(out_md, payload, rows)
    print(json.dumps({"status": payload["status"], "row_count": payload["row_count"], "missing_packet_count": payload["missing_packet_count"]}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
