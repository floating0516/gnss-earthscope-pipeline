#!/usr/bin/env python3
"""Build a release-readiness report for the PGD science package."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")

REQUIRED_JSON_PRODUCTS = {
    "release_package_summary": "release_package_summary.json",
    "residual_review_decision_report": "residual_review_decision_report.json",
    "reviewed_release_summary": "reviewed_release_summary.json",
    "residual_review_worklist": "residual_review_worklist.json",
    "release_blocking_review_starter": "release_blocking_review_starter.json",
}

BLOCKER_FIELDS = [
    "event_id",
    "formula",
    "abs_residual_mw",
    "blocker_reason",
    "suggested_manual_status",
    "suggested_manual_cause",
    "next_action",
    "packet_path",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR, help="PGD release package directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Readiness JSON path. Defaults to <release-dir>/pgd_release_readiness.json.")
    parser.add_argument("--out-md", type=Path, default=None, help="Readiness Markdown path. Defaults to <release-dir>/pgd_release_readiness.md.")
    parser.add_argument("--blocker-limit", type=int, default=20, help="Maximum release-blocking rows to include in the report.")
    return parser.parse_args(argv)


def read_json(path: Path) -> tuple[dict[str, Any] | None, dict[str, object] | None]:
    if not path.exists():
        return None, {"code": "MISSING_INPUT", "message": "Required PGD release product is missing.", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, {"code": "INVALID_JSON", "message": str(exc), "path": str(path)}
    if not isinstance(payload, dict):
        return None, {"code": "INVALID_JSON_SHAPE", "message": "Expected a JSON object.", "path": str(path)}
    return payload, None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def int_value(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def is_yes(value: object) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def first_value(row: dict[str, str], *fields: str) -> str:
    for field in fields:
        value = str(row.get(field) or "")
        if value.strip():
            return value
    return ""


def json_status(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return "MISSING"
    return str(payload.get("status") or "")


def top_blockers(release_dir: Path, limit: int) -> list[dict[str, str]]:
    rows = read_csv_rows(release_dir / "residual_review_worklist.csv")
    blockers = [row for row in rows if is_yes(row.get("release_blocking"))]
    if not blockers:
        blockers = read_csv_rows(release_dir / "reviewed_release_blockers.csv")
    selected = blockers[: max(limit, 0)]
    rows: list[dict[str, str]] = []
    for row in selected:
        rows.append(
            {
                "event_id": row.get("event_id", ""),
                "formula": row.get("formula", ""),
                "abs_residual_mw": row.get("abs_residual_mw", ""),
                "blocker_reason": row.get("blocker_reason", ""),
                "suggested_manual_status": first_value(row, "suggested_manual_status", "suggested_review_status", "triage_status_suggestion"),
                "suggested_manual_cause": first_value(row, "suggested_manual_cause", "suggested_review_cause", "triage_cause_suggestion"),
                "next_action": first_value(row, "next_action", "next_review_action", "next_decision_action"),
                "packet_path": row.get("packet_path", ""),
            }
        )
    return rows


def determine_readiness(
    *,
    errors: list[dict[str, object]],
    input_statuses: dict[str, str],
    decision_completion_status: str,
    reviewed_completion_status: str,
    release_blocking_count: int,
    blocker_count: int,
) -> tuple[str, str]:
    if errors or any(status != "OK" for status in input_statuses.values()):
        return "INVALID", "INVALID_INPUTS"
    if (
        release_blocking_count == 0
        and blocker_count == 0
        and decision_completion_status == "COMPLETE"
        and reviewed_completion_status == "COMPLETE"
    ):
        return "OK", "READY"
    return "OK", "BLOCKED_ON_REVIEW"


def next_actions(readiness_status: str, release_dir: Path) -> list[str]:
    starter = release_dir / "release_blocking_review_starter.csv"
    if readiness_status == "READY":
        return ["PGD release review is complete; package can be used for downstream science reporting."]
    if readiness_status == "INVALID_INPUTS":
        return [
            "Regenerate the standard PGD bundle before reviewing release readiness.",
            "Check missing or invalid release products listed in pgd_release_readiness.json.",
        ]
    return [
        f"Fill a copy of {starter} for release-blocking rows.",
        "Inspect packet paths listed in residual_review_worklist.csv before assigning manual review status.",
        "Re-run run_pgd_science_bundle.py with --starter-annotations <completed-starter.csv>.",
    ]


def build_payload(release_dir: Path, blocker_limit: int) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any] | None] = {}
    errors: list[dict[str, object]] = []
    for name, filename in REQUIRED_JSON_PRODUCTS.items():
        payload, error = read_json(release_dir / filename)
        payloads[name] = payload
        if error:
            errors.append(error)

    release_package = payloads["release_package_summary"] or {}
    decision = payloads["residual_review_decision_report"] or {}
    reviewed = payloads["reviewed_release_summary"] or {}
    worklist = payloads["residual_review_worklist"] or {}
    starter = payloads["release_blocking_review_starter"] or {}
    input_statuses = {name: json_status(payload) for name, payload in payloads.items()}
    decision_completion_status = str(decision.get("completion_status") or "")
    reviewed_completion_status = str(reviewed.get("completion_status") or "")
    release_blocking_count = int_value(worklist.get("release_blocking_count"))
    blocker_count = int_value(reviewed.get("blocker_count"))
    status, readiness_status = determine_readiness(
        errors=errors,
        input_statuses=input_statuses,
        decision_completion_status=decision_completion_status,
        reviewed_completion_status=reviewed_completion_status,
        release_blocking_count=release_blocking_count,
        blocker_count=blocker_count,
    )

    return {
        "status": status,
        "readiness_status": readiness_status,
        "release_dir": str(release_dir),
        "recommended_formula": str(release_package.get("recommended_formula") or ""),
        "station_aggregation": str(release_package.get("station_aggregation") or ""),
        "ready_event_count": int_value(release_package.get("ready_event_count")),
        "reviewed_release_count": int_value(reviewed.get("reviewed_release_count")),
        "blocker_count": blocker_count,
        "work_item_count": int_value(worklist.get("work_item_count")),
        "release_blocking_count": release_blocking_count,
        "starter_row_count": int_value(starter.get("starter_row_count")),
        "decision_completion_status": decision_completion_status,
        "reviewed_completion_status": reviewed_completion_status,
        "requires_sensitivity_caveat": bool(release_package.get("requires_sensitivity_caveat")),
        "release_blocking_review_starter": str(release_dir / "release_blocking_review_starter.csv"),
        "top_blockers": top_blockers(release_dir, blocker_limit),
        "next_actions": next_actions(readiness_status, release_dir),
        "input_statuses": input_statuses,
        "errors": errors,
    }


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
    lines = [
        "# PGD Release Readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Readiness: `{payload['readiness_status']}`",
        f"- Recommended formula: `{payload['recommended_formula']}`",
        f"- Station aggregation: `{payload['station_aggregation']}`",
        f"- Ready events: {payload['ready_event_count']}",
        f"- Reviewed release events: {payload['reviewed_release_count']}",
        f"- Release blockers: {payload['blocker_count']}",
        f"- Worklist rows: {payload['work_item_count']}",
        f"- Release-blocking rows: {payload['release_blocking_count']}",
        f"- Sensitivity caveat required: `{str(payload['requires_sensitivity_caveat']).lower()}`",
        f"- Release-blocking starter: `{payload['release_blocking_review_starter']}`",
        "",
        "## Next Actions",
        "",
    ]
    for action in payload["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Top Release Blockers", "", *markdown_table(payload["top_blockers"], BLOCKER_FIELDS), ""])
    if payload["errors"]:
        lines.extend(["## Errors", "", *markdown_table(payload["errors"], ["code", "message", "path"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    release_dir = args.release_dir
    out_json = args.out_json or release_dir / "pgd_release_readiness.json"
    out_md = args.out_md or release_dir / "pgd_release_readiness.md"
    payload = build_payload(release_dir, args.blocker_limit)
    write_json(out_json, payload)
    write_markdown(out_md, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "readiness_status": payload["readiness_status"],
                "release_blocking_count": payload["release_blocking_count"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
