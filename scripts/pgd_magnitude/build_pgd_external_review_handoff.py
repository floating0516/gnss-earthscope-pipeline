#!/usr/bin/env python3
"""Build a read-only external-review handoff index for PGD release products."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract


REQUIRED_JSON_PRODUCTS = {
    "release_readme": "release_readme.json",
    "release_prompt": "pgd_release_blocker_review_prompt.json",
    "review_briefing": "pgd_review_briefing.json",
    "release_readiness": "pgd_release_readiness.json",
    "release_package": "release_package_summary.json",
    "packet_summary": "pgd_comparison_formula_review_packet_summary.json",
}
REQUIRED_HANDOFF_FILES = [
    {
        "role": "start_here",
        "path": "README.md",
        "required": True,
        "editable": "no",
        "description": "Release entrypoint and operator instructions.",
    },
    {
        "role": "review_prompt",
        "path": "pgd_release_blocker_review_prompt.md",
        "required": True,
        "editable": "no",
        "description": "Prompt pack for reviewers or external models.",
    },
    {
        "role": "review_briefing",
        "path": "pgd_review_briefing.md",
        "required": True,
        "editable": "no",
        "description": "Compact release briefing with import commands.",
    },
    {
        "role": "release_readiness",
        "path": "pgd_release_readiness.md",
        "required": True,
        "editable": "no",
        "description": "Current release readiness gate state.",
    },
    {
        "role": "decision_guide",
        "path": "pgd_release_blocker_decision_guide.md",
        "required": True,
        "editable": "no",
        "description": "Decision rules for release-blocking rows.",
    },
    {
        "role": "packet_summary",
        "path": "pgd_comparison_formula_review_packet_summary.md",
        "required": True,
        "editable": "no",
        "description": "Summary of comparison-formula blocker packets.",
    },
    {
        "role": "starter",
        "path": "release_blocking_review_starter.csv",
        "required": True,
        "editable": "copy_only",
        "description": "Blank worksheet to copy and fill with manual decisions.",
    },
    {
        "role": "packet_index",
        "path": "residual_review_packet_index.md",
        "required": True,
        "editable": "no",
        "description": "Index for row-by-row residual review packets.",
    },
]
OPTIONAL_HANDOFF_FILES = [
    {
        "role": "release_package",
        "path": "release_package.md",
        "required": False,
        "editable": "no",
        "description": "Release package summary report.",
    },
    {
        "role": "formula_matrix",
        "path": "pgd_formula_test_matrix.md",
        "required": False,
        "editable": "no",
        "description": "Three-formula test matrix under median aggregation.",
    },
    {
        "role": "formula_provenance",
        "path": "formula_provenance.md",
        "required": False,
        "editable": "no",
        "description": "Formula coefficient and citation provenance.",
    },
    {
        "role": "formula_note",
        "path": "formula_aggregation_note.md",
        "required": False,
        "editable": "no",
        "description": "Median aggregation and formula terminology note.",
    },
    {
        "role": "residual_evidence",
        "path": "residual_review_evidence.csv",
        "required": False,
        "editable": "no",
        "description": "Machine residual-review evidence rows.",
    },
    {
        "role": "decision_report",
        "path": "residual_review_decision_report.md",
        "required": False,
        "editable": "no",
        "description": "Manual decision consistency report.",
    },
    {
        "role": "reviewed_release",
        "path": "reviewed_release_summary.json",
        "required": False,
        "editable": "no",
        "description": "Reviewed-release summary state.",
    },
]
MANIFEST_FIELDS = [
    "role",
    "path",
    "exists",
    "required",
    "editable",
    "size_bytes",
    "sha256",
    "description",
]
BLOCKER_FIELDS = [
    "review_priority",
    "event_id",
    "formula",
    "recommended_formula",
    "station_aggregation",
    "packet_path",
    "packet_exists",
    "suggested_review_status",
    "manual_decision_state",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_external_review_handoff_manifest.json.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_external_review_handoff_manifest.csv.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_external_review_handoff.md.")
    return parser.parse_args(argv)


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def read_json_product(release_dir: Path, filename: str, product: str, errors: list[dict[str, object]]) -> dict[str, Any]:
    path = release_dir / filename
    if not path.exists():
        errors.append(error("MISSING_PRODUCT", "Required PGD release JSON product is missing.", product=product, path=str(path)))
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(error("INVALID_JSON", "Required PGD release JSON product is invalid.", product=product, path=str(path), detail=str(exc)))
        return {}
    if not isinstance(payload, dict):
        errors.append(error("INVALID_JSON_OBJECT", "Required PGD release JSON product must be an object.", product=product, path=str(path)))
        return {}
    return payload


def read_csv_rows(path: Path, errors: list[dict[str, object]]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error as exc:
        errors.append(error("INVALID_CSV", "PGD handoff CSV input is invalid.", path=str(path), detail=str(exc)))
        return []


def int_value(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    if value is None or value == "":
        return
    if not pgd_contract.is_median_station_aggregation(value):
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD external review handoff requires station_aggregation=median.",
                product=product,
                station_aggregation=str(value or ""),
            )
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_row(release_dir: Path, item: dict[str, object]) -> dict[str, object]:
    relative = str(item["path"])
    path = release_dir / relative
    exists = path.exists()
    size = path.stat().st_size if exists and path.is_file() else 0
    digest = sha256_file(path) if exists and path.is_file() else ""
    return {
        "role": str(item["role"]),
        "path": relative,
        "exists": exists,
        "required": bool(item["required"]),
        "editable": str(item["editable"]),
        "size_bytes": size,
        "sha256": digest,
        "description": str(item["description"]),
    }


def packet_rows(release_dir: Path, errors: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = read_csv_rows(release_dir / "pgd_comparison_formula_review_packet_summary.csv", errors)
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        packet_path = str(row.get("packet_path") or "").strip()
        if not packet_path or packet_path in seen:
            continue
        seen.add(packet_path)
        selected.append(
            {
                "role": "review_packet",
                "path": packet_path,
                "required": True,
                "editable": "no",
                "description": f"Residual review packet for {row.get('event_id', '')}/{row.get('formula', '')}.",
            }
        )
    return selected


def blocker_rows(release_dir: Path, errors: list[dict[str, object]]) -> list[dict[str, str]]:
    rows = read_csv_rows(release_dir / "pgd_comparison_formula_review_packet_summary.csv", errors)
    selected = [{field: str(row.get(field, "")) for field in BLOCKER_FIELDS} for row in rows]
    return sorted(selected, key=lambda row: (int_value(row.get("review_priority")) or 10**9, row.get("event_id", ""), row.get("formula", "")))


def build_payload(release_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, object]] = []
    payloads = {product: read_json_product(release_dir, filename, product, errors) for product, filename in REQUIRED_JSON_PRODUCTS.items()}
    for product, payload in payloads.items():
        validate_station_aggregation(f"{product}.station_aggregation", payload.get("station_aggregation"), errors)
        validate_station_aggregation(f"{product}.station_aggregation_method", payload.get("station_aggregation_method"), errors)

    optional_items = [item for item in OPTIONAL_HANDOFF_FILES if (release_dir / str(item["path"])).exists()]
    file_items = [*REQUIRED_HANDOFF_FILES, *optional_items, *packet_rows(release_dir, errors)]
    files = [manifest_row(release_dir, item) for item in file_items]
    missing_required = [row for row in files if bool(row["required"]) and not bool(row["exists"])]
    for row in missing_required:
        errors.append(error("MISSING_HANDOFF_FILE", "Required external review handoff file is missing.", path=row["path"], role=row["role"]))

    readme = payloads["release_readme"]
    prompt = payloads["release_prompt"]
    briefing = payloads["review_briefing"]
    readiness = payloads["release_readiness"]
    release_package = payloads["release_package"]
    packet_summary = payloads["packet_summary"]
    status = "INVALID" if errors else "OK"
    blocker_count = int_value(prompt.get("blocker_count") or packet_summary.get("comparison_formula_blocker_count") or readiness.get("release_blocking_count"))
    return {
        "schema_version": "pgd-external-review-handoff/v1",
        "status": status,
        "handoff_status": "INVALID_INPUTS" if errors else first_nonempty(prompt.get("prompt_status"), readme.get("entrypoint_status"), briefing.get("briefing_status"), readiness.get("readiness_status"), "BLOCKED_ON_REVIEW"),
        "release_dir": str(release_dir),
        "station_aggregation": first_nonempty(prompt.get("station_aggregation"), readme.get("station_aggregation"), briefing.get("station_aggregation"), readiness.get("station_aggregation"), release_package.get("station_aggregation"), pgd_contract.STATION_AGGREGATION_METHOD),
        "baseline_formula": first_nonempty(prompt.get("baseline_formula"), readme.get("baseline_formula"), briefing.get("baseline_formula"), release_package.get("recommended_formula"), packet_summary.get("recommended_formula")),
        "formula_comparison_scope": first_nonempty(prompt.get("formula_comparison_scope"), readme.get("formula_comparison_scope"), briefing.get("formula_comparison_scope"), pgd_contract.FORMULA_COMPARISON_SCOPE),
        "formulas": list(readme.get("formulas") or prompt.get("formulas") or pgd_contract.FORMULA_NAMES),
        "ready_event_count": int_value(readme.get("ready_event_count") or readiness.get("ready_event_count") or release_package.get("ready_event_count")),
        "blocker_count": blocker_count,
        "comparison_formula_blocker_count": int_value(readme.get("comparison_formula_blocker_count") or packet_summary.get("comparison_formula_blocker_count") or blocker_count),
        "manual_decisions_written": max(
            int_value(readme.get("manual_decisions_written")),
            int_value(prompt.get("manual_decisions_written")),
            int_value(briefing.get("manual_decisions_written")),
            int_value(packet_summary.get("manual_decisions_written")),
        ),
        "included_file_count": len(files),
        "missing_required_count": len(missing_required),
        "files": files,
        "blocker_rows": blocker_rows(release_dir, errors),
        "instructions": [
            "Start with README.md and pgd_release_blocker_review_prompt.md.",
            "Do not edit generated evidence files.",
            "Fill a copy of release_blocking_review_starter.csv with manual review decisions.",
            "Validate the completed starter before importing it into the PGD bundle.",
        ],
        "errors": errors,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    if not rows:
        return ["_None._"]
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    required_files = [row for row in payload["files"] if bool(row.get("required"))]
    optional_files = [row for row in payload["files"] if not bool(row.get("required"))]
    lines = [
        "# PGD External Review Handoff",
        "",
        f"- Status: `{payload['status']}`",
        f"- Handoff status: `{payload['handoff_status']}`",
        f"- Station aggregation: `{payload['station_aggregation']}`",
        f"- Baseline formula: `{payload['baseline_formula']}`",
        f"- Formula comparison scope: `{payload['formula_comparison_scope']}`",
        f"- Release blockers: {payload['blocker_count']}",
        f"- Manual decisions written: {payload['manual_decisions_written']}",
        "",
        "This package uses one station aggregation method: `median`. The three formulas are `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019`; they are formulas/scaling laws, not station aggregation methods.",
        "",
        "Do not edit generated evidence files. Fill a copy of `release_blocking_review_starter.csv`, validate it, then import it through the PGD science bundle.",
        "",
        "## Required Files",
        "",
        *markdown_table(required_files, ["role", "path", "exists", "editable", "sha256"]),
        "",
        "## Optional Context Files",
        "",
        *markdown_table(optional_files, ["role", "path", "exists", "editable", "sha256"]),
        "",
        "## Release Blockers",
        "",
        *markdown_table(payload["blocker_rows"], ["review_priority", "event_id", "formula", "packet_path", "suggested_review_status", "manual_decision_state"]),
        "",
    ]
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "path", "product", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.release_dir / "pgd_external_review_handoff_manifest.json"
    out_csv = args.out_csv or args.release_dir / "pgd_external_review_handoff_manifest.csv"
    out_md = args.out_md or args.release_dir / "pgd_external_review_handoff.md"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_csv(out_csv, payload["files"])
    write_markdown(out_md, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "handoff_status": payload["handoff_status"],
                "included_file_count": payload["included_file_count"],
                "missing_required_count": payload["missing_required_count"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
