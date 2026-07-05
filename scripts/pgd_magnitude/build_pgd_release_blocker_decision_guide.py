#!/usr/bin/env python3
"""Build a reviewer decision guide for PGD release-blocking rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_TERMINAL_STATUSES = ["REVIEWED", "ACCEPTED", "EXCLUDED"]
ACCEPTED_RULE = "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes"

GUIDE_FIELDS = [
    "guide_priority",
    "event_id",
    "formula",
    "recommended_formula",
    "formula_scope",
    "packet_path",
    "allowed_terminal_statuses",
    "accepted_for_release_rule",
    "suggested_review_status",
    "suggested_review_cause",
    "pre_decision_checks",
    "review_focus",
    "release_status",
    "release_failure_reasons",
    "formula_residuals_for_event",
    "manual_decision_written",
    "manual_review_status",
    "manual_review_cause",
    "manual_review_notes",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True, help="PGD release package directory.")
    parser.add_argument("--out-csv", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_decision_guide.csv.")
    parser.add_argument("--out-json", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_decision_guide.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Defaults to <release-dir>/pgd_release_blocker_decision_guide.md.")
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


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unfilled") for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def starter_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (str(row.get("event_id") or ""), str(row.get("formula") or "")): row
        for row in rows
        if str(row.get("event_id") or "") and str(row.get("formula") or "")
    }


def check_tokens(row: dict[str, str]) -> list[str]:
    raw_actions = str(row.get("next_review_action") or "")
    actions = {item for item in raw_actions.split(";") if item}
    checks: list[str] = []
    if "CHECK_WAVEFORM_AND_STATION_FILTERING" in actions:
        checks.append("CHECK_WAVEFORM_AND_STATION_FILTERING")
    if "CHECK_NOISE_WINDOW_AND_SNR" in actions:
        checks.append("CHECK_NOISE_WINDOW_AND_SNR")
    if "CHECK_RELEASE_GATE" in actions or row.get("release_failure_reasons"):
        checks.append("CHECK_RELEASE_GATE")
    if "COMPARE_FORMULA_RESIDUALS" in actions or row.get("formula_residuals_for_event"):
        checks.append("CHECK_FORMULA_CONTEXT")
    if row.get("formula_scope") == "recommended_formula":
        checks.append("CHECK_RECOMMENDED_FORMULA_IMPACT")
    if not checks:
        checks.append("CHECK_PACKET_CONTEXT")
    return checks


def build_guide_rows(analysis_rows: list[dict[str, str]], starter_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    starters = starter_lookup(starter_rows)
    rows: list[dict[str, str]] = []
    for index, analysis in enumerate(analysis_rows, start=1):
        key = (str(analysis.get("event_id") or ""), str(analysis.get("formula") or ""))
        starter = starters.get(key, {})
        rows.append(
            {
                "guide_priority": str(index),
                "event_id": key[0],
                "formula": key[1],
                "recommended_formula": str(analysis.get("recommended_formula") or ""),
                "formula_scope": str(analysis.get("formula_scope") or ""),
                "packet_path": str(analysis.get("packet_path") or starter.get("packet_path") or ""),
                "allowed_terminal_statuses": ";".join(ALLOWED_TERMINAL_STATUSES),
                "accepted_for_release_rule": ACCEPTED_RULE,
                "suggested_review_status": str(analysis.get("suggested_review_status") or starter.get("suggested_review_status") or ""),
                "suggested_review_cause": str(analysis.get("suggested_review_cause") or starter.get("suggested_review_cause") or ""),
                "pre_decision_checks": ";".join(check_tokens(analysis)),
                "review_focus": str(analysis.get("review_focus") or starter.get("review_focus") or ""),
                "release_status": str(analysis.get("release_status") or ""),
                "release_failure_reasons": str(analysis.get("release_failure_reasons") or ""),
                "formula_residuals_for_event": str(analysis.get("formula_residuals_for_event") or ""),
                "manual_decision_written": "no",
                "manual_review_status": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    return rows


def build_payload(release_dir: Path) -> dict[str, Any]:
    release_dir = release_dir.expanduser()
    errors: list[dict[str, object]] = []
    analysis_rows = load_required_csv(release_dir / "pgd_release_blocker_analysis.csv", errors)
    analysis_summary = load_required_json(release_dir / "pgd_release_blocker_analysis.json", errors)
    starter_rows = load_required_csv(release_dir / "release_blocking_review_starter.csv", errors)
    if analysis_summary and str(analysis_summary.get("status") or "") != "OK":
        errors.append(
            error(
                "INVALID_INPUT_STATUS",
                "PGD blocker decision guide requires pgd_release_blocker_analysis.json status=OK.",
                path=str(release_dir / "pgd_release_blocker_analysis.json"),
                status=str(analysis_summary.get("status") or ""),
            )
        )
    rows = build_guide_rows(analysis_rows, starter_rows)
    payload: dict[str, Any] = {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(release_dir),
        "recommended_formula": str(analysis_summary.get("recommended_formula") or ""),
        "station_aggregation": str(analysis_summary.get("station_aggregation") or ""),
        "row_count": len(rows),
        "recommended_formula_blocker_count": sum(1 for row in rows if row.get("formula_scope") == "recommended_formula"),
        "comparison_formula_blocker_count": sum(1 for row in rows if row.get("formula_scope") == "comparison_formula"),
        "manual_decisions_written": 0,
        "allowed_terminal_statuses": ALLOWED_TERMINAL_STATUSES,
        "accepted_for_release_rule": ACCEPTED_RULE,
        "required_completed_starter": str(release_dir / "release_blocking_review_starter.csv"),
        "guide_by_formula_scope": count_by(rows, "formula_scope"),
        "guide_by_suggested_review_status": count_by(rows, "suggested_review_status"),
        "errors": errors,
        "guide_rows": rows,
    }
    return payload


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=GUIDE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in GUIDE_FIELDS})


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
    guide_rows = payload.get("guide_rows", [])
    assert isinstance(guide_rows, list)
    lines = [
        "# PGD Release Blocker Decision Guide",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Recommended formula: `{payload.get('recommended_formula', '')}`",
        f"- Station aggregation: `{payload.get('station_aggregation', '')}`",
        f"- Guide rows: {payload.get('row_count', 0)}",
        f"- Recommended-formula blockers: {payload.get('recommended_formula_blocker_count', 0)}",
        f"- Comparison-formula blockers: {payload.get('comparison_formula_blocker_count', 0)}",
        f"- Allowed terminal statuses: `{';'.join(ALLOWED_TERMINAL_STATUSES)}`",
        f"- Accepted-for-release rule: `{ACCEPTED_RULE}`",
        "",
        "This guide does not fill manual review fields. Fill a copy of the release-blocking starter after inspecting the packet and checks listed here.",
        "",
        "## Guide Rows",
        "",
        *markdown_table(
            guide_rows,
            [
                "guide_priority",
                "event_id",
                "formula",
                "formula_scope",
                "pre_decision_checks",
                "packet_path",
            ],
        ),
        "",
    ]
    if payload.get("errors"):
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "path", "status"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_csv = args.out_csv or args.release_dir / "pgd_release_blocker_decision_guide.csv"
    out_json = args.out_json or args.release_dir / "pgd_release_blocker_decision_guide.json"
    out_md = args.out_md or args.release_dir / "pgd_release_blocker_decision_guide.md"
    payload = build_payload(args.release_dir)
    rows = payload.get("guide_rows", [])
    assert isinstance(rows, list)
    write_csv(out_csv, rows)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(f"wrote PGD release blocker decision guide: status={payload['status']} rows={len(rows)} csv={out_csv}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
