#!/usr/bin/env python3
"""Build the PGD baseline narrative handoff from release status products."""

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
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_baseline_narrative_handoff.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_baseline_narrative_handoff.md.")
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


def validate_station_aggregation(product: str, value: object, errors: list[dict[str, object]]) -> None:
    text = str(value or "").strip()
    if text != STATION_AGGREGATION:
        errors.append(
            error(
                "INVALID_STATION_AGGREGATION",
                "PGD baseline narrative handoff requires station_aggregation=median.",
                product=product,
                station_aggregation=text,
            )
        )


def baseline_narrative_status(recommended_status: str, ready_count: int, requires_caveat: bool, invalid: bool) -> str:
    if invalid:
        return "INVALID_INPUTS"
    if recommended_status == "READY_FOR_BASELINE_NARRATIVE":
        return "READY_WITH_CAVEATS" if requires_caveat else "READY"
    if ready_count <= 0:
        return "NO_READY_EVENTS"
    return "BLOCKED_ON_REVIEW"


def formula_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        formula = str(row.get("formula") or "").strip()
        if not formula:
            continue
        output.append(
            {
                "formula": formula,
                "formula_scope": str(row.get("formula_scope") or ""),
                "formula_release_status": str(row.get("formula_release_status") or ""),
                "station_aggregation": str(row.get("station_aggregation") or ""),
                "blocker_count": str(row.get("blocker_count") or "0"),
            }
        )
    return sorted(output, key=lambda row: (0 if row["formula_scope"] == "recommended_formula" else 1, row["formula"]))


def build_payload(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    errors: list[dict[str, object]] = []
    status_json_path = release_dir / "pgd_recommended_formula_release_status.json"
    status_csv_path = release_dir / "pgd_recommended_formula_release_status.csv"
    status = load_required_json(status_json_path, errors)
    rows = load_required_csv(status_csv_path, errors)

    if status.get("status") not in {"OK", None, ""}:
        errors.append(
            error(
                "INVALID_INPUT_STATUS",
                "Recommended-formula release status is not OK.",
                product="pgd_recommended_formula_release_status",
                status=status.get("status"),
            )
        )
    validate_station_aggregation("pgd_recommended_formula_release_status.json", status.get("station_aggregation"), errors)
    for index, row in enumerate(rows, start=1):
        validate_station_aggregation(f"pgd_recommended_formula_release_status.csv row {index}", row.get("station_aggregation"), errors)

    curated_formula_rows = formula_rows(rows)
    formulas = [row["formula"] for row in curated_formula_rows]
    recommended_status = str(status.get("recommended_formula_release_status") or "")
    ready_count = int_value(status.get("ready_event_count"))
    requires_caveat = bool_value(status.get("requires_sensitivity_caveat"))
    narrative_status = baseline_narrative_status(recommended_status, ready_count, requires_caveat, bool(errors))
    comparison_status = str(status.get("comparison_formula_review_status") or "")
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "baseline_formula": str(status.get("recommended_formula") or ""),
        "recommended_formula": str(status.get("recommended_formula") or ""),
        "station_aggregation": str(status.get("station_aggregation") or ""),
        "station_aggregation_method": STATION_AGGREGATION,
        "method_contract": pgd_contract.METHOD_CONTRACT,
        "formula_comparison_scope": "formula_only",
        "baseline_narrative_status": narrative_status,
        "recommended_formula_release_status": recommended_status if not errors else "INVALID_INPUTS",
        "overall_release_readiness_status": str(status.get("overall_release_readiness_status") or ("INVALID_INPUTS" if errors else "")),
        "comparison_formula_review_status": comparison_status,
        "ready_event_count": ready_count,
        "reviewed_release_count": int_value(status.get("reviewed_release_count")),
        "recommended_formula_blocker_count": int_value(status.get("recommended_formula_blocker_count")),
        "comparison_formula_blocker_count": int_value(status.get("comparison_formula_blocker_count")),
        "manual_decisions_written": int_value(status.get("manual_decisions_written")),
        "requires_sensitivity_caveat": requires_caveat,
        "formula_count": len(formulas),
        "formulas": formulas,
        "formula_rows": curated_formula_rows,
        "errors": errors,
        "next_actions": [],
    }
    payload["next_actions"] = next_actions(payload)
    return payload


def next_actions(payload: dict[str, Any]) -> list[str]:
    if payload["status"] != "OK":
        return ["Regenerate valid PGD release status products with station_aggregation=median."]
    actions = []
    if payload["baseline_narrative_status"] in {"READY", "READY_WITH_CAVEATS"}:
        actions.append("Use the baseline formula for the PGD baseline narrative under the median station aggregation method.")
    else:
        actions.append("Resolve recommended-formula blockers before using the PGD baseline narrative.")
    if payload.get("requires_sensitivity_caveat"):
        actions.append("Carry the sensitivity caveat into the narrative.")
    if payload.get("comparison_formula_review_status") == "NEEDS_COMPARISON_REVIEW":
        actions.append("Keep comparison-formula review pending until the starter rows are manually decided.")
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
    formulas = ", ".join(f"`{formula}`" for formula in payload.get("formulas", []))
    rows = payload.get("formula_rows", [])
    assert isinstance(rows, list)
    lines = [
        "# PGD Baseline Narrative Handoff",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Baseline formula: `{payload.get('baseline_formula', '')}`",
        f"- Baseline narrative status: `{payload.get('baseline_narrative_status', '')}`",
        "- PGD uses one station aggregation method: `median`.",
        f"- Formula comparison scope: `{payload.get('formula_comparison_scope', '')}`",
        f"- Formulas: {formulas}",
        f"- Overall release readiness: `{payload.get('overall_release_readiness_status', '')}`",
        f"- Comparison-formula review status: `{payload.get('comparison_formula_review_status', '')}`",
        f"- Manual decisions written: {payload.get('manual_decisions_written', 0)}",
        "",
        f"The three PGD formulas are compared under median station aggregation; they are not alternative aggregation methods. The current baseline formula is `{payload.get('baseline_formula', '')}`.",
        "",
    ]
    if payload.get("baseline_narrative_status") == "READY_WITH_CAVEATS":
        lines.extend(["The baseline narrative can proceed with the recorded sensitivity caveat.", ""])
    if payload.get("comparison_formula_review_status") == "NEEDS_COMPARISON_REVIEW":
        lines.extend(
            [
                "The comparison-formula review remains pending; this handoff does not clear comparison blockers such as `crowell_2016_gfast`.",
                "",
            ]
        )
    lines.extend(
        [
            "This handoff is generated from existing release status products and does not write manual decisions.",
            "",
            "## Formula Rows",
            "",
            *markdown_table(rows, ["formula_scope", "formula", "formula_release_status", "blocker_count"]),
            "",
            "## Next Actions",
            "",
            *[f"- {action}" for action in payload.get("next_actions", [])],
            "",
        ]
    )
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "product", "station_aggregation"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.release_dir / "pgd_baseline_narrative_handoff.json"
    out_md = args.out_md or args.release_dir / "pgd_baseline_narrative_handoff.md"
    payload = build_payload(args.release_dir)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(
        "wrote PGD baseline narrative handoff: "
        f"status={payload['status']} baseline={payload['baseline_narrative_status']} json={out_json}"
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
