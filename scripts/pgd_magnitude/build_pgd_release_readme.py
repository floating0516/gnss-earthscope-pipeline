#!/usr/bin/env python3
"""Build the top-level README for a PGD release directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract


REQUIRED_JSON_PRODUCTS = {
    "release_package": "release_package_summary.json",
    "review_briefing": "pgd_review_briefing.json",
    "release_readiness": "pgd_release_readiness.json",
    "recommended_formula_status": "pgd_recommended_formula_release_status.json",
    "reviewed_release": "reviewed_release_summary.json",
    "release_blocking_starter": "release_blocking_review_starter.json",
}

KEY_FILES = [
    ("Start here", "README.md"),
    ("Review briefing", "pgd_review_briefing.md"),
    ("Release package summary", "release_package_summary.json"),
    ("Release package report", "release_package.md"),
    ("Baseline science narrative", "pgd_baseline_science_narrative.md"),
    ("Formula test matrix", "pgd_formula_test_matrix.md"),
    ("Release readiness", "pgd_release_readiness.md"),
    ("Release-blocking starter", "release_blocking_review_starter.csv"),
    ("Residual packet index", "residual_review_packet_index.md"),
    ("Residual packet directory", "residual_review_packets/"),
    ("Decision report", "residual_review_decision_report.md"),
    ("Reviewed release summary", "reviewed_release_summary.json"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/README.md.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/release_readme.json.")
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


def validate_station_aggregation(product: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    for key in ("station_aggregation", "station_aggregation_method"):
        if key in payload and not pgd_contract.is_median_station_aggregation(payload.get(key)):
            errors.append(
                error(
                    "INVALID_STATION_AGGREGATION",
                    "PGD release README requires station_aggregation=median.",
                    product=f"{product}.{key}",
                    station_aggregation=str(payload.get(key) or ""),
                )
            )


def int_value(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def release_files(release_dir: Path) -> list[dict[str, object]]:
    rows = []
    for label, relative_path in KEY_FILES:
        path = release_dir / relative_path
        rows.append({"label": label, "path": relative_path, "exists": True if relative_path == "README.md" else path.exists()})
    return rows


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


def build_payload(release_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, object]] = []
    payloads = {product: read_json_product(release_dir, filename, product, errors) for product, filename in REQUIRED_JSON_PRODUCTS.items()}
    for product, payload in payloads.items():
        validate_station_aggregation(product, payload, errors)

    package = payloads["release_package"]
    briefing = payloads["review_briefing"]
    readiness = payloads["release_readiness"]
    recommended = payloads["recommended_formula_status"]
    reviewed = payloads["reviewed_release"]
    starter = payloads["release_blocking_starter"]

    status = "INVALID" if errors else "OK"
    entrypoint_status = "INVALID_INPUTS" if errors else str(briefing.get("briefing_status") or readiness.get("readiness_status") or "UNKNOWN")
    baseline_formula = str(briefing.get("baseline_formula") or recommended.get("recommended_formula") or package.get("recommended_formula") or "")
    station_aggregation = str(briefing.get("station_aggregation") or readiness.get("station_aggregation") or package.get("station_aggregation") or "")
    manual_decisions_written = max(
        int_value(briefing.get("manual_decisions_written")),
        int_value(recommended.get("manual_decisions_written")),
    )
    payload: dict[str, Any] = {
        "schema_version": "pgd-release-readme/v1",
        "status": status,
        "entrypoint_status": entrypoint_status,
        "release_dir": str(release_dir),
        "baseline_formula": baseline_formula,
        "station_aggregation": station_aggregation,
        "formula_comparison_scope": str(briefing.get("formula_comparison_scope") or pgd_contract.FORMULA_COMPARISON_SCOPE),
        "formulas": list(pgd_contract.FORMULA_NAMES),
        "pgd_event_count": int_value(briefing.get("pgd_event_count")),
        "ready_event_count": int_value(readiness.get("ready_event_count") or package.get("ready_event_count") or briefing.get("ready_event_count")),
        "reviewed_release_count": int_value(readiness.get("reviewed_release_count") or reviewed.get("reviewed_release_count")),
        "release_blocking_count": int_value(readiness.get("release_blocking_count") or reviewed.get("blocker_count")),
        "work_item_count": int_value(readiness.get("work_item_count")),
        "comparison_formula_blocker_count": int_value(briefing.get("comparison_formula_blocker_count") or recommended.get("comparison_formula_blocker_count")),
        "review_packet_count": int_value(briefing.get("review_packet_count")),
        "starter_row_count": int_value(starter.get("starter_row_count")),
        "manual_decisions_written": manual_decisions_written,
        "requires_sensitivity_caveat": bool(package.get("requires_sensitivity_caveat") or briefing.get("requires_sensitivity_caveat")),
        "review_completion_status": str(reviewed.get("completion_status") or ""),
        "key_files": release_files(release_dir),
        "import_commands": import_commands(release_dir),
        "next_actions": list(briefing.get("next_actions") or []),
        "errors": errors,
    }
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
    key_files = payload.get("key_files", [])
    assert isinstance(key_files, list)
    errors = payload.get("errors", [])
    assert isinstance(errors, list)
    lines = [
        "# PGD Magnitude Release",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Release entrypoint status: `{payload.get('entrypoint_status', '')}`",
        f"- Baseline formula: `{payload.get('baseline_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Formula comparison scope: `{payload.get('formula_comparison_scope', '')}`",
        f"- PGD evaluable events: {payload.get('pgd_event_count', 0)}",
        f"- Ready baseline release events: {payload.get('ready_event_count', 0)}",
        f"- Reviewed release events: {payload.get('reviewed_release_count', 0)}",
        f"- Release blockers: {payload.get('release_blocking_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Review packet count: {payload.get('review_packet_count', 0)}",
        f"- Manual decisions written by this README: {payload.get('manual_decisions_written', 0)}",
        "",
        "This README is a read-only release entrypoint. It does not write manual decisions, clear blockers, or rescan waveform data.",
        "",
        "## Median Aggregation And Formulas",
        "",
        "The PGD release uses one station aggregation method: `median`. The compared PGD scaling formulas are:",
        "",
        *[f"- `{formula}`" for formula in payload.get("formulas", [])],
        "",
        "The formula labels are not alternative station aggregation methods.",
        "",
        "## Key Files",
        "",
        *markdown_table(key_files, ["label", "path", "exists"]),
        "",
        "## Review Commands",
        "",
        *[f"```bash\n{command}\n```" for command in payload.get("import_commands", [])],
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
    out_md = args.out_md or args.release_dir / "README.md"
    out_json = args.out_json or args.release_dir / "release_readme.json"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(json.dumps({"status": payload["status"], "entrypoint_status": payload["entrypoint_status"], "readme": str(out_md)}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
