#!/usr/bin/env python3
"""Build a read-only PGD review briefing from release products."""

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
    "baseline_science_narrative": "pgd_baseline_science_narrative.json",
    "comparison_packet_summary": "pgd_comparison_formula_review_packet_summary.json",
    "release_readiness": "pgd_release_readiness.json",
    "recommended_formula_release_status": "pgd_recommended_formula_release_status.json",
    "release_blocking_review_starter": "release_blocking_review_starter.json",
}
REQUIRED_CSV_PRODUCTS = {
    "comparison_packet_rows": "pgd_comparison_formula_review_packet_summary.csv",
}

ALLOWED_MANUAL_REVIEW_STATUSES = [
    "UNREVIEWED",
    "REVIEWED",
    "ACCEPTED",
    "EXCLUDED",
    "NEEDS_DATA_CHECK",
    "NEEDS_METADATA_CHECK",
    "NEEDS_FORMULA_REVIEW",
]
ALLOWED_ACCEPTED_FOR_RELEASE = ["yes", "no"]
REVIEW_PACKET_FIELDS = [
    "review_priority",
    "event_id",
    "formula",
    "packet_path",
    "packet_exists",
    "abs_residual_mw",
    "suggested_review_status",
    "suggested_review_cause",
    "next_review_action",
    "manual_decision_state",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_review_briefing.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_review_briefing.md.")
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


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    if not pgd_contract.is_median_station_aggregation(value):
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD review briefing requires station_aggregation=median.",
                product=product,
                station_aggregation=str(value or ""),
            )
        )


def validate_inputs(payloads: dict[str, dict[str, Any]], packet_rows: list[dict[str, str]], errors: list[dict[str, object]]) -> None:
    for product, payload in payloads.items():
        if "station_aggregation" in payload:
            validate_station_aggregation(f"{product}.station_aggregation", payload.get("station_aggregation"), errors)
        if "station_aggregation_method" in payload:
            validate_station_aggregation(f"{product}.station_aggregation_method", payload.get("station_aggregation_method"), errors)
    for index, row in enumerate(packet_rows, start=1):
        if "station_aggregation" in row:
            validate_station_aggregation(f"pgd_comparison_formula_review_packet_summary.csv row {index}", row.get("station_aggregation"), errors)


def review_files(release_dir: Path, payloads: dict[str, dict[str, Any]]) -> dict[str, str]:
    starter = payloads["release_blocking_review_starter"].get("out_csv") or release_dir / "release_blocking_review_starter.csv"
    return {
        "starter_csv": str(starter),
        "starter_md": str(release_dir / "release_blocking_review_starter.md"),
        "starter_json": str(release_dir / "release_blocking_review_starter.json"),
        "packet_summary_csv": str(release_dir / "pgd_comparison_formula_review_packet_summary.csv"),
        "packet_summary_md": str(release_dir / "pgd_comparison_formula_review_packet_summary.md"),
        "packet_index_csv": str(release_dir / "residual_review_packet_index.csv"),
        "packet_dir": str(release_dir / "residual_review_packets"),
        "readiness_md": str(release_dir / "pgd_release_readiness.md"),
        "baseline_science_narrative_md": str(release_dir / "pgd_baseline_science_narrative.md"),
    }


def import_commands(release_dir: Path) -> list[str]:
    return [
        "python scripts/pgd_magnitude/validate_release_starter_annotations.py "
        f"--release-dir {release_dir} --completed-starter <completed-starter.csv> --require-complete --strict",
        "python scripts/pgd_magnitude/run_pgd_science_bundle.py "
        "--export-root exports/normalized-ok-stations-us-nz "
        "--report-dir reports/pgd_magnitude/latest "
        "--sensitivity-dir reports/pgd_magnitude/sensitivity/latest "
        f"--release-dir {release_dir} --starter-annotations <completed-starter.csv>",
    ]


def packet_records(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    records = [{field: str(row.get(field, "")) for field in REVIEW_PACKET_FIELDS} for row in rows]
    return sorted(records, key=lambda row: (int(row["review_priority"] or "999999"), row["event_id"], row["formula"]))


def next_actions(payload: dict[str, Any]) -> list[str]:
    if payload["status"] != "OK":
        return ["Regenerate valid PGD release products before briefing reviewers."]
    if payload["briefing_status"] == "READY":
        return ["PGD release review is complete; use the release package for downstream science review."]
    return [
        "Fill a copy of release_blocking_review_starter.csv; do not edit generated evidence files in place.",
        "Use residual review packet paths to inspect each release-blocking row before assigning manual fields.",
        "Validate the completed starter with validate_release_starter_annotations.py --require-complete --strict.",
        "Re-run run_pgd_science_bundle.py with --starter-annotations <completed-starter.csv> to import reviewed decisions.",
    ]


def build_payload(release_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, object]] = []
    payloads = {product: read_json_product(release_dir, filename, product, errors) for product, filename in REQUIRED_JSON_PRODUCTS.items()}
    packet_rows = read_csv_product(release_dir, REQUIRED_CSV_PRODUCTS["comparison_packet_rows"], "comparison_packet_rows", errors)
    validate_inputs(payloads, packet_rows, errors)

    baseline = payloads["baseline_science_narrative"]
    packet_summary = payloads["comparison_packet_summary"]
    readiness = payloads["release_readiness"]
    recommended_status = payloads["recommended_formula_release_status"]
    starter = payloads["release_blocking_review_starter"]
    status = "INVALID" if errors else "OK"
    briefing_status = "INVALID_INPUTS" if errors else str(readiness.get("readiness_status") or "UNKNOWN")
    manual_decisions_written = max(
        int(baseline.get("manual_decisions_written") or 0),
        int(packet_summary.get("manual_decisions_written") or 0),
        int(recommended_status.get("manual_decisions_written") or 0),
    )
    payload: dict[str, Any] = {
        "schema_version": "pgd-review-briefing/v1",
        "status": status,
        "briefing_status": briefing_status,
        "release_dir": str(release_dir),
        "baseline_formula": str(baseline.get("baseline_formula") or recommended_status.get("recommended_formula") or readiness.get("recommended_formula") or ""),
        "station_aggregation": str(baseline.get("station_aggregation") or readiness.get("station_aggregation") or ""),
        "formula_comparison_scope": str(baseline.get("formula_comparison_scope") or pgd_contract.FORMULA_COMPARISON_SCOPE),
        "formulas": list(baseline.get("formulas") or pgd_contract.FORMULA_NAMES),
        "narrative_status": str(baseline.get("narrative_status") or ""),
        "recommended_formula_release_status": str(recommended_status.get("recommended_formula_release_status") or ""),
        "release_readiness_status": str(readiness.get("readiness_status") or ""),
        "pgd_event_count": int(baseline.get("pgd_event_count") or 0),
        "ready_event_count": int(readiness.get("ready_event_count") or baseline.get("ready_event_count") or 0),
        "reviewed_release_count": int(readiness.get("reviewed_release_count") or baseline.get("reviewed_release_count") or 0),
        "work_item_count": int(readiness.get("work_item_count") or 0),
        "release_blocking_count": int(readiness.get("release_blocking_count") or 0),
        "comparison_formula_blocker_count": int(packet_summary.get("comparison_formula_blocker_count") or recommended_status.get("comparison_formula_blocker_count") or 0),
        "recommended_formula_blocker_count": int(recommended_status.get("recommended_formula_blocker_count") or baseline.get("recommended_formula_blocker_count") or 0),
        "review_packet_count": len(packet_rows),
        "packet_exists_count": int(packet_summary.get("packet_exists_count") or 0),
        "missing_packet_count": int(packet_summary.get("missing_packet_count") or 0),
        "manual_decisions_written": manual_decisions_written,
        "requires_sensitivity_caveat": bool(baseline.get("requires_sensitivity_caveat") or readiness.get("requires_sensitivity_caveat")),
        "sensitivity_switch_scenarios": list(baseline.get("sensitivity_switch_scenarios") or []),
        "suggested_review_status_counts": dict(packet_summary.get("suggested_review_status_counts") or {}),
        "suggested_review_cause_counts": dict(packet_summary.get("suggested_review_cause_counts") or {}),
        "manual_decision_state_counts": dict(packet_summary.get("manual_decision_state_counts") or {}),
        "review_files": review_files(release_dir, payloads),
        "allowed_manual_review_statuses": ALLOWED_MANUAL_REVIEW_STATUSES,
        "allowed_accepted_for_release_values": ALLOWED_ACCEPTED_FOR_RELEASE,
        "import_commands": import_commands(release_dir),
        "review_packets": packet_records(packet_rows),
        "starter_row_count": int(starter.get("starter_row_count") or 0),
        "errors": errors,
    }
    payload["next_actions"] = next_actions(payload)
    return payload


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
    review_files_payload = payload.get("review_files", {})
    assert isinstance(review_files_payload, dict)
    packets = payload.get("review_packets", [])
    assert isinstance(packets, list)
    errors = payload.get("errors", [])
    assert isinstance(errors, list)
    lines = [
        "# PGD Review Briefing",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Briefing status: `{payload.get('briefing_status', '')}`",
        f"- Baseline formula: `{payload.get('baseline_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Formula comparison scope: `{payload.get('formula_comparison_scope', '')}`",
        f"- PGD evaluable events: {payload.get('pgd_event_count', 0)}",
        f"- Ready baseline release events: {payload.get('ready_event_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Manual decisions written by this briefing: {payload.get('manual_decisions_written', 0)}",
        "",
        "This briefing does not write manual decisions or clear release blockers.",
        "",
        "## Review Files",
        "",
        *markdown_table([{"file": key, "path": value} for key, value in review_files_payload.items()], ["file", "path"]),
        "",
        "## Allowed Manual Fields",
        "",
        f"- Manual review statuses: `{', '.join(ALLOWED_MANUAL_REVIEW_STATUSES)}`",
        f"- Accepted for release values: `{', '.join(ALLOWED_ACCEPTED_FOR_RELEASE)}`",
        "",
        "## Import Commands",
        "",
        *[f"```bash\n{command}\n```" for command in payload.get("import_commands", [])],
        "",
        "## Review Packets",
        "",
        *markdown_table(packets, REVIEW_PACKET_FIELDS),
        "",
        "## Next Actions",
        "",
        *[f"- {action}" for action in payload.get("next_actions", [])],
        "",
    ]
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "message", "product", "path", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.release_dir / "pgd_review_briefing.json"
    out_md = args.out_md or args.release_dir / "pgd_review_briefing.md"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(json.dumps({"status": payload["status"], "briefing_status": payload["briefing_status"], "review_packet_count": payload["review_packet_count"]}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
