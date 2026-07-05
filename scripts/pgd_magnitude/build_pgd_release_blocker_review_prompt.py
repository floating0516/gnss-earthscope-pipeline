#!/usr/bin/env python3
"""Build a read-only prompt pack for PGD release-blocking review rows."""

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


REQUIRED_JSON_PRODUCTS = {
    "decision_guide": "pgd_release_blocker_decision_guide.json",
    "release_blocking_starter": "release_blocking_review_starter.json",
    "packet_summary": "pgd_comparison_formula_review_packet_summary.json",
    "release_readme": "release_readme.json",
    "review_briefing": "pgd_review_briefing.json",
}
REQUIRED_CSV_PRODUCTS = {
    "decision_guide_rows": "pgd_release_blocker_decision_guide.csv",
    "release_blocking_starter_rows": "release_blocking_review_starter.csv",
    "packet_summary_rows": "pgd_comparison_formula_review_packet_summary.csv",
}
MANUAL_FIELDS = [
    "manual_review_status",
    "manual_review_cause",
    "manual_review_notes",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]
BLOCKER_FIELDS = [
    "guide_priority",
    "event_id",
    "formula",
    "recommended_formula",
    "formula_scope",
    "packet_path",
    "suggested_review_status",
    "suggested_review_cause",
    "pre_decision_checks",
    "review_focus",
    "release_status",
    "release_failure_reasons",
    "formula_residuals_for_event",
    *MANUAL_FIELDS,
]
STARTER_FIELDS = [
    "starter_priority",
    "event_id",
    "formula",
    "packet_path",
    "suggested_review_status",
    "suggested_review_cause",
    "suggested_accepted_for_release",
    "next_review_action",
    "review_focus",
    "release_status",
    "release_failure_reasons",
    "best_formula_for_event",
    "formula_residuals_for_event",
    *MANUAL_FIELDS,
]
DEFAULT_ALLOWED_TERMINAL_STATUSES = ["REVIEWED", "ACCEPTED", "EXCLUDED"]
DEFAULT_ACCEPTED_FOR_RELEASE_RULE = "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes"
DEFAULT_IMPORT_COMMANDS = [
    "python scripts/pgd_magnitude/validate_release_starter_annotations.py "
    "--release-dir reports/pgd_magnitude/release/latest --completed-starter <completed-starter.csv> --require-complete --strict",
    "python scripts/pgd_magnitude/run_pgd_science_bundle.py "
    "--export-root exports/normalized-ok-stations-us-nz "
    "--report-dir reports/pgd_magnitude/latest "
    "--sensitivity-dir reports/pgd_magnitude/sensitivity/latest "
    "--release-dir reports/pgd_magnitude/release/latest --starter-annotations <completed-starter.csv>",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_review_prompt.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_review_prompt.md.")
    return parser.parse_args(argv)


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def read_json_product(release_dir: Path, filename: str, product: str, errors: list[dict[str, object]]) -> dict[str, Any]:
    path = release_dir / filename
    if not path.exists():
        errors.append(error("MISSING_PRODUCT", "Required PGD release product is missing.", product=product, path=str(path)))
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(error("INVALID_JSON", "Required PGD release product is not valid JSON.", product=product, path=str(path), detail=str(exc)))
        return {}
    if not isinstance(payload, dict):
        errors.append(error("INVALID_JSON_OBJECT", "Required PGD release product must contain a JSON object.", product=product, path=str(path)))
        return {}
    return payload


def read_csv_product(release_dir: Path, filename: str, product: str, errors: list[dict[str, object]]) -> list[dict[str, str]]:
    path = release_dir / filename
    if not path.exists():
        errors.append(error("MISSING_PRODUCT", "Required PGD release product is missing.", product=product, path=str(path)))
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error as exc:
        errors.append(error("INVALID_CSV", "Required PGD release product is not valid CSV.", product=product, path=str(path), detail=str(exc)))
        return []


def int_value(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def priority_value(row: dict[str, str], *fields: str) -> int:
    for field in fields:
        value = int_value(row.get(field))
        if value:
            return value
    return 10**9


def split_semicolon(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    if value is None or value == "":
        return
    if not pgd_contract.is_median_station_aggregation(value):
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD release blocker review prompt requires station_aggregation=median.",
                product=product,
                station_aggregation=str(value or ""),
            )
        )


def validate_inputs(
    payloads: dict[str, dict[str, Any]],
    csv_products: dict[str, list[dict[str, str]]],
    errors: list[dict[str, object]],
) -> None:
    for product, payload in payloads.items():
        validate_station_aggregation(f"{product}.station_aggregation", payload.get("station_aggregation"), errors)
        validate_station_aggregation(f"{product}.station_aggregation_method", payload.get("station_aggregation_method"), errors)
    for product, rows in csv_products.items():
        for index, row in enumerate(rows, start=1):
            if "station_aggregation" in row:
                validate_station_aggregation(f"{product} row {index}", row.get("station_aggregation"), errors)


def select_fields(row: dict[str, str], fields: list[str]) -> dict[str, str]:
    return {field: str(row.get(field, "")) for field in fields}


def blocker_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [select_fields(row, BLOCKER_FIELDS) for row in rows]
    return sorted(selected, key=lambda row: (priority_value(row, "guide_priority"), row.get("event_id", ""), row.get("formula", "")))


def starter_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [select_fields(row, STARTER_FIELDS) for row in rows]
    return sorted(selected, key=lambda row: (priority_value(row, "starter_priority"), row.get("event_id", ""), row.get("formula", "")))


def import_commands(payloads: dict[str, dict[str, Any]]) -> list[str]:
    for key in ("release_readme", "review_briefing"):
        commands = payloads.get(key, {}).get("import_commands")
        if isinstance(commands, list) and commands:
            normalized = [str(command) for command in commands]
            joined = "\n".join(normalized)
            if "validate_release_starter_annotations.py" in joined and "run_pgd_science_bundle.py" in joined:
                return normalized
    return list(DEFAULT_IMPORT_COMMANDS)


def first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def terminal_statuses(rows: list[dict[str, str]]) -> list[str]:
    for row in rows:
        statuses = split_semicolon(row.get("allowed_terminal_statuses"))
        if statuses:
            return statuses
    return list(DEFAULT_ALLOWED_TERMINAL_STATUSES)


def accepted_for_release_rule(rows: list[dict[str, str]]) -> str:
    for row in rows:
        value = str(row.get("accepted_for_release_rule") or "").strip()
        if value:
            return value
    return DEFAULT_ACCEPTED_FOR_RELEASE_RULE


def build_payload(release_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, object]] = []
    payloads = {product: read_json_product(release_dir, filename, product, errors) for product, filename in REQUIRED_JSON_PRODUCTS.items()}
    csv_products = {product: read_csv_product(release_dir, filename, product, errors) for product, filename in REQUIRED_CSV_PRODUCTS.items()}
    validate_inputs(payloads, csv_products, errors)

    guide = payloads["decision_guide"]
    starter = payloads["release_blocking_starter"]
    packet_summary = payloads["packet_summary"]
    readme = payloads["release_readme"]
    briefing = payloads["review_briefing"]
    guide_rows = blocker_rows(csv_products["decision_guide_rows"])
    worksheet_rows = starter_rows(csv_products["release_blocking_starter_rows"])
    status = "INVALID" if errors else "OK"
    blocker_count = len(guide_rows)
    manual_decisions_written = max(
        int_value(guide.get("manual_decisions_written")),
        int_value(packet_summary.get("manual_decisions_written")),
        int_value(readme.get("manual_decisions_written")),
        int_value(briefing.get("manual_decisions_written")),
    )
    return {
        "schema_version": "pgd-release-blocker-review-prompt/v1",
        "status": status,
        "prompt_status": "INVALID_INPUTS" if errors else first_nonempty(readme.get("entrypoint_status"), briefing.get("briefing_status"), "BLOCKED_ON_REVIEW"),
        "release_dir": str(release_dir),
        "baseline_formula": first_nonempty(readme.get("baseline_formula"), briefing.get("baseline_formula"), guide.get("recommended_formula"), packet_summary.get("recommended_formula")),
        "station_aggregation": first_nonempty(readme.get("station_aggregation"), briefing.get("station_aggregation"), guide.get("station_aggregation"), packet_summary.get("station_aggregation"), pgd_contract.STATION_AGGREGATION_METHOD),
        "formula_comparison_scope": first_nonempty(readme.get("formula_comparison_scope"), briefing.get("formula_comparison_scope"), pgd_contract.FORMULA_COMPARISON_SCOPE),
        "formulas": list(readme.get("formulas") or briefing.get("formulas") or pgd_contract.FORMULA_NAMES),
        "blocker_count": blocker_count,
        "comparison_formula_blocker_count": int_value(guide.get("comparison_formula_blocker_count") or packet_summary.get("comparison_formula_blocker_count") or blocker_count),
        "starter_row_count": int_value(starter.get("starter_row_count") or len(worksheet_rows)),
        "manual_decisions_written": manual_decisions_written,
        "manual_fields": list(MANUAL_FIELDS),
        "allowed_terminal_statuses": terminal_statuses(guide_rows),
        "accepted_for_release_rule": accepted_for_release_rule(guide_rows),
        "suggested_review_status_counts": dict(starter.get("suggested_review_status_counts") or guide.get("guide_by_suggested_review_status") or {}),
        "suggested_review_cause_counts": dict(starter.get("suggested_review_cause_counts") or {}),
        "blockers_by_formula": dict(packet_summary.get("blockers_by_formula") or {}),
        "input_files": {
            "decision_guide_csv": str(release_dir / "pgd_release_blocker_decision_guide.csv"),
            "starter_csv": str(release_dir / "release_blocking_review_starter.csv"),
            "packet_summary_csv": str(release_dir / "pgd_comparison_formula_review_packet_summary.csv"),
            "packet_dir": str(release_dir / "residual_review_packets"),
        },
        "import_commands": import_commands(payloads),
        "blocker_rows": guide_rows,
        "starter_rows": worksheet_rows,
        "reviewer_instructions": [
            "Do not edit generated evidence files.",
            "Fill a copy of release_blocking_review_starter.csv.",
            "Use packet_path for each row before assigning manual fields.",
            "Use only allowed terminal statuses for completed release-blocking decisions.",
            "Validate the completed starter before importing it into the PGD bundle.",
        ],
        "errors": errors,
    }


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
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    blocker_rows_payload = payload.get("blocker_rows", [])
    starter_rows_payload = payload.get("starter_rows", [])
    errors = payload.get("errors", [])
    assert isinstance(blocker_rows_payload, list)
    assert isinstance(starter_rows_payload, list)
    assert isinstance(errors, list)
    lines = [
        "# PGD Release Blocker Review Prompt",
        "",
        "Use this prompt pack to review the current PGD release-blocking rows with another model or reviewer.",
        "",
        "## Context",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Prompt status: `{payload.get('prompt_status', '')}`",
        f"- Baseline formula: `{payload.get('baseline_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Formula comparison scope: `{payload.get('formula_comparison_scope', '')}`",
        f"- Blocker rows: {payload.get('blocker_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Manual decisions written by this prompt: {payload.get('manual_decisions_written', 0)}",
        "",
        "The PGD release uses one station aggregation method: `median`. The formula labels are scaling formulas, not alternative station aggregation paths.",
        "",
        "Formulas under review context:",
        "",
        *[f"- `{formula}`" for formula in payload.get("formulas", [])],
        "",
        "## Reviewer Instructions",
        "",
        "- Do not edit generated evidence files.",
        "- Fill a copy of `release_blocking_review_starter.csv`; keep generated CSV/JSON/Markdown evidence read-only.",
        "- Use each row's `packet_path` before filling manual fields.",
        f"- Allowed terminal statuses: `{';'.join(payload.get('allowed_terminal_statuses', []))}`.",
        f"- Accepted-for-release rule: `{payload.get('accepted_for_release_rule', '')}`.",
        f"- Manual fields to fill: `{';'.join(payload.get('manual_fields', []))}`.",
        "",
        "## Validation And Import",
        "",
        *[f"```bash\n{command}\n```" for command in payload.get("import_commands", [])],
        "",
        "## Blocker Rows",
        "",
        *markdown_table(
            blocker_rows_payload,
            [
                "guide_priority",
                "event_id",
                "formula",
                "packet_path",
                "suggested_review_status",
                "suggested_review_cause",
                "release_status",
                "release_failure_reasons",
                "formula_residuals_for_event",
            ],
        ),
        "",
        "## Blank Starter Rows",
        "",
        *markdown_table(
            starter_rows_payload,
            [
                "starter_priority",
                "event_id",
                "formula",
                "packet_path",
                "suggested_review_status",
                "manual_review_status",
                "accepted_for_release",
                "reviewer",
            ],
        ),
        "",
    ]
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "message", "product", "path", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.release_dir / "pgd_release_blocker_review_prompt.json"
    out_md = args.out_md or args.release_dir / "pgd_release_blocker_review_prompt.md"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(json.dumps({"status": payload["status"], "prompt_status": payload["prompt_status"], "blocker_count": payload["blocker_count"]}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
