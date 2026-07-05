#!/usr/bin/env python3
"""Validate and summarize PGD residual review decisions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")
TERMINAL_MANUAL_STATUSES = {"ACCEPTED", "EXCLUDED", "REVIEWED"}
PENDING_MANUAL_STATUSES = {"", "UNREVIEWED", "NEEDS_DATA_CHECK", "NEEDS_METADATA_CHECK", "NEEDS_FORMULA_REVIEW"}
TRUE_VALUES = {"1", "true", "yes", "y", "accepted"}
FALSE_VALUES = {"0", "false", "no", "n", "excluded"}
DECISION_FIELDS = [
    "triage_priority",
    "event_id",
    "formula",
    "decision_status",
    "decision_issue",
    "next_decision_action",
    "manual_review_status",
    "accepted_for_release",
    "manual_review_cause",
    "manual_review_notes",
    "reviewer",
    "reviewed_at",
    "packet_path",
    "abs_residual_mw",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "next_review_action",
    "release_status",
    "release_failure_reasons",
    "release_review_reasons",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "best_formula_for_event",
    "best_formula_abs_residual_mw",
    "formula_residuals_for_event",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--dashboard-csv", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "dashboard_csv": args.dashboard_csv or release_dir / "residual_review_dashboard.csv",
        "out_csv": args.out_csv or release_dir / "residual_review_decision_report.csv",
        "out_json": args.out_json or release_dir / "residual_review_decision_report.json",
        "out_md": args.out_md or release_dir / "residual_review_decision_report.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalized_manual_status(row: dict[str, str]) -> str:
    return str(row.get("manual_review_status") or "").strip().upper()


def normalized_accepted_flag(row: dict[str, str]) -> str:
    value = str(row.get("accepted_for_release") or "").strip().lower()
    if value in TRUE_VALUES:
        return "yes"
    if value in FALSE_VALUES:
        return "no"
    return ""


def error(code: str, message: str, row: dict[str, str] | None = None, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    if row is not None:
        payload.update({"event_id": row.get("event_id", ""), "formula": row.get("formula", "")})
    payload.update(extra)
    return payload


def decision_for_row(row: dict[str, str]) -> tuple[str, str, str, dict[str, object] | None]:
    status = normalized_manual_status(row)
    accepted = normalized_accepted_flag(row)
    if status in PENDING_MANUAL_STATUSES:
        if accepted:
            issue = "release decision is filled before a terminal manual_review_status"
            return (
                "INVALID_DECISION",
                issue,
                "FIX_CONFLICTING_DECISION",
                error("CONFLICTING_RELEASE_DECISION", issue, row),
            )
        return "PENDING_REVIEW", "", "COMPLETE_REVIEW_DECISION", None

    if status == "ACCEPTED":
        if accepted == "yes":
            return "ACCEPTED_FOR_RELEASE", "", "INCLUDE_IN_REVIEWED_RELEASE_SET", None
        issue = "manual_review_status=ACCEPTED requires accepted_for_release=yes"
        return (
            "INVALID_DECISION",
            issue,
            "FIX_CONFLICTING_DECISION",
            error("CONFLICTING_RELEASE_DECISION", issue, row),
        )

    if status == "EXCLUDED":
        if accepted == "no":
            return "EXCLUDED_BY_REVIEW", "", "KEEP_OUT_OF_REVIEWED_RELEASE_SET", None
        issue = "manual_review_status=EXCLUDED requires accepted_for_release=no"
        return (
            "INVALID_DECISION",
            issue,
            "FIX_CONFLICTING_DECISION",
            error("CONFLICTING_RELEASE_DECISION", issue, row),
        )

    if status == "REVIEWED":
        if accepted == "yes":
            return "ACCEPTED_FOR_RELEASE", "", "INCLUDE_IN_REVIEWED_RELEASE_SET", None
        if accepted == "no":
            return "EXCLUDED_BY_REVIEW", "", "KEEP_OUT_OF_REVIEWED_RELEASE_SET", None
        issue = "manual_review_status=REVIEWED requires accepted_for_release=yes or no"
        return (
            "INVALID_DECISION",
            issue,
            "FIX_MISSING_RELEASE_DECISION",
            error("MISSING_RELEASE_DECISION", issue, row),
        )

    issue = f"manual_review_status is not recognized: {status}"
    return "INVALID_DECISION", issue, "FIX_UNKNOWN_MANUAL_STATUS", error("UNKNOWN_MANUAL_STATUS", issue, row)


def build_decision_rows(dashboard_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, object]] = []
    for row in dashboard_rows:
        decision_status, issue, action, row_error = decision_for_row(row)
        if row_error:
            errors.append(row_error)
        output = {field: "" for field in DECISION_FIELDS}
        for field in DECISION_FIELDS:
            if field in row:
                output[field] = row.get(field, "")
        output["manual_review_status"] = normalized_manual_status(row)
        output["accepted_for_release"] = normalized_accepted_flag(row)
        output["decision_status"] = decision_status
        output["decision_issue"] = issue
        output["next_decision_action"] = action
        rows.append(output)
    return rows, errors


def count_field(rows: list[dict[str, str]], field: str, *, blank: str = "unfilled") -> dict[str, int]:
    counts = Counter(str(row.get(field) or "").strip() or blank for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def summary_payload(paths: dict[str, Path], rows: list[dict[str, str]], errors: list[dict[str, object]]) -> dict[str, object]:
    decision_counts = count_field(rows, "decision_status")
    invalid_count = decision_counts.get("INVALID_DECISION", 0)
    pending_count = decision_counts.get("PENDING_REVIEW", 0)
    completion_status = "COMPLETE" if pending_count == 0 and invalid_count == 0 else "INCOMPLETE"
    return {
        "status": "INVALID" if errors else "OK",
        "completion_status": completion_status,
        "release_dir": str(paths["release_dir"]),
        "dashboard_csv": str(paths["dashboard_csv"]),
        "out_csv": str(paths["out_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        "row_count": len(rows),
        "accepted_count": decision_counts.get("ACCEPTED_FOR_RELEASE", 0),
        "excluded_count": decision_counts.get("EXCLUDED_BY_REVIEW", 0),
        "pending_count": pending_count,
        "invalid_count": invalid_count,
        "decision_status_counts": decision_counts,
        "manual_status_counts": count_field(rows, "manual_review_status", blank="UNFILLED"),
        "accepted_for_release_counts": count_field(rows, "accepted_for_release"),
        "reviewer_counts": count_field(rows, "reviewer"),
        "errors": errors,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in DECISION_FIELDS} for row in rows)


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, object], rows: list[dict[str, str]]) -> None:
    lines = [
        "# Residual Review Decision Report",
        "",
        f"- Status: `{payload['status']}`",
        f"- Completion: `{payload['completion_status']}`",
        f"- Rows: {payload['row_count']}",
        f"- Accepted: {payload['accepted_count']}",
        f"- Excluded: {payload['excluded_count']}",
        f"- Pending: {payload['pending_count']}",
        f"- Invalid: {payload['invalid_count']}",
        f"- Dashboard CSV: `{payload['dashboard_csv']}`",
        "",
        "## Decision Counts",
        "",
        *markdown_table(
            [{"decision_status": key, "count": str(value)} for key, value in dict(payload["decision_status_counts"]).items()],
            ["decision_status", "count"],
        ),
        "",
        "## Decisions",
        "",
        *markdown_table(
            rows[:30],
            [
                "triage_priority",
                "event_id",
                "formula",
                "decision_status",
                "manual_review_status",
                "accepted_for_release",
                "next_decision_action",
                "packet_path",
            ],
        ),
        "",
    ]
    if payload["errors"]:
        lines.extend(
            [
                "## Errors",
                "",
                *markdown_table([dict(error_row) for error_row in payload["errors"]], ["code", "message", "event_id", "formula"]),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, object]]:
    paths = resolve_paths(args)
    errors: list[dict[str, object]] = []
    try:
        dashboard_rows = read_csv(paths["dashboard_csv"])
    except FileNotFoundError as exc:
        rows: list[dict[str, str]] = []
        errors.append(error("MISSING_INPUT", "Residual review dashboard CSV is missing.", path=str(exc.filename)))
    else:
        rows, errors = build_decision_rows(dashboard_rows)
    payload = summary_payload(paths, rows, errors)
    write_csv(paths["out_csv"], rows)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, rows)
    return rows, payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _rows, payload = run(args)
    print(json.dumps({"status": payload["status"], "completion_status": payload["completion_status"], "row_count": payload["row_count"]}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
