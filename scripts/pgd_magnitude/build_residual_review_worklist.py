#!/usr/bin/env python3
"""Build a reviewer worklist for pending PGD residual review decisions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


WORKLIST_FIELDS = [
    "worklist_priority",
    "event_id",
    "formula",
    "worklist_status",
    "decision_issue",
    "release_blocking",
    "blocker_status",
    "blocker_reason",
    "packet_path",
    "abs_residual_mw",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "suggested_review_status",
    "suggested_review_cause",
    "suggested_accepted_for_release",
    "next_review_action",
    "next_decision_action",
    "review_focus",
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
    "manual_review_status",
    "accepted_for_release",
    "manual_review_cause",
    "reviewer",
    "reviewed_at",
]

WORKLIST_STATUSES = {"PENDING_REVIEW", "INVALID_DECISION"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=Path("reports/pgd_magnitude/release/latest"))
    parser.add_argument("--dashboard-csv", type=Path, default=None)
    parser.add_argument("--decision-report-csv", type=Path, default=None)
    parser.add_argument("--blockers-csv", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "dashboard_csv": args.dashboard_csv or release_dir / "residual_review_dashboard.csv",
        "decision_report_csv": args.decision_report_csv or release_dir / "residual_review_decision_report.csv",
        "blockers_csv": args.blockers_csv or release_dir / "reviewed_release_blockers.csv",
        "out_csv": args.out_csv or release_dir / "residual_review_worklist.csv",
        "out_json": args.out_json or release_dir / "residual_review_worklist.json",
        "out_md": args.out_md or release_dir / "residual_review_worklist.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("formula") or ""))


def int_value(value: object, default: int = 999999) -> int:
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else default


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unfilled") for row in rows)
    return {item: counts[item] for item in sorted(counts)}


def review_focus(row: dict[str, str]) -> str:
    decision_action = str(row.get("next_decision_action") or "")
    review_action = str(row.get("next_review_action") or "")
    action = " ".join([decision_action, review_action]).upper()
    if "FIX" in decision_action.upper() or row.get("decision_status") == "INVALID_DECISION":
        return "Fix inconsistent manual decision fields before scientific release review."
    if "WAVEFORM" in action or "STATION" in action:
        return "Inspect waveform and station filtering before release decision."
    if "FORMULA" in action:
        return "Compare formula residuals and decide whether formula limitation is acceptable."
    return "Complete manual review decision using the packet evidence."


def suggested_review_status(row: dict[str, str]) -> str:
    if row.get("decision_status") == "INVALID_DECISION":
        return "FIX_INVALID_DECISION"
    return str(row.get("triage_status_suggestion") or "NEEDS_REVIEW")


def worklist_sort_key(row: dict[str, str]) -> tuple[int, int, int, str, str]:
    status_rank = 0 if row.get("worklist_status") == "INVALID_DECISION" else 1
    blocking_rank = 0 if row.get("release_blocking") == "yes" else 1
    return (
        status_rank,
        blocking_rank,
        int_value(row.get("triage_priority")),
        str(row.get("event_id") or ""),
        str(row.get("formula") or ""),
    )


def build_worklist(
    dashboard_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    blocker_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    dashboard_by_key = {key(row): row for row in dashboard_rows}
    blockers_by_key = {key(row): row for row in blocker_rows}
    work_rows: list[dict[str, str]] = []
    for decision in decision_rows:
        status = str(decision.get("decision_status") or "")
        if status not in WORKLIST_STATUSES:
            continue
        row_key = key(decision)
        dashboard = dashboard_by_key.get(row_key, {})
        blocker = blockers_by_key.get(row_key, {})
        source = {**dashboard, **decision}
        output = {field: "" for field in WORKLIST_FIELDS}
        for field in WORKLIST_FIELDS:
            output[field] = str(source.get(field, ""))
        output["worklist_status"] = status
        output["release_blocking"] = "yes" if blocker else "no"
        output["blocker_status"] = str(blocker.get("blocker_status") or "")
        output["blocker_reason"] = str(blocker.get("blocker_reason") or "")
        output["suggested_review_status"] = suggested_review_status(source)
        output["suggested_review_cause"] = str(source.get("triage_cause_suggestion") or "")
        output["suggested_accepted_for_release"] = ""
        output["review_focus"] = review_focus(source)
        work_rows.append(output)

    work_rows.sort(key=worklist_sort_key)
    for index, row in enumerate(work_rows, start=1):
        row["worklist_priority"] = str(index)
    return work_rows


def summary_payload(paths: dict[str, Path], rows: list[dict[str, str]]) -> dict[str, Any]:
    invalid_count = sum(1 for row in rows if row.get("worklist_status") == "INVALID_DECISION")
    pending_count = sum(1 for row in rows if row.get("worklist_status") == "PENDING_REVIEW")
    release_blocking_count = sum(1 for row in rows if row.get("release_blocking") == "yes")
    return {
        "status": "INVALID" if invalid_count else "OK",
        "completion_status": "COMPLETE" if not rows else "INCOMPLETE",
        "release_dir": str(paths["release_dir"]),
        "dashboard_csv": str(paths["dashboard_csv"]),
        "decision_report_csv": str(paths["decision_report_csv"]),
        "blockers_csv": str(paths["blockers_csv"]),
        "out_csv": str(paths["out_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        "work_item_count": len(rows),
        "pending_count": pending_count,
        "invalid_count": invalid_count,
        "release_blocking_count": release_blocking_count,
        "suggested_review_status_counts": count_by(rows, "suggested_review_status"),
        "suggested_review_cause_counts": count_by(rows, "suggested_review_cause"),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WORKLIST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in WORKLIST_FIELDS} for row in rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(markdown_escape(row.get(field, "")) for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any], rows: list[dict[str, str]]) -> None:
    lines = [
        "# Residual Review Worklist",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Completion: `{payload.get('completion_status', '')}`",
        f"- Work items: {payload.get('work_item_count', 0)}",
        f"- Pending review: {payload.get('pending_count', 0)}",
        f"- Invalid decisions: {payload.get('invalid_count', 0)}",
        f"- release-blocking items: {payload.get('release_blocking_count', 0)}",
        "",
        "This worklist is a review aid. It does not mutate residual evidence, annotation starters, dashboards, decision reports, or reviewed release-set products.",
        "",
        "## Queue",
        "",
        *markdown_table(
            rows,
            [
                "worklist_priority",
                "event_id",
                "formula",
                "worklist_status",
                "release_blocking",
                "suggested_review_status",
                "suggested_review_cause",
                "packet_path",
                "review_focus",
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    paths = resolve_paths(args)
    dashboard_rows = read_csv(paths["dashboard_csv"])
    decision_rows = read_csv(paths["decision_report_csv"])
    blocker_rows = read_csv(paths["blockers_csv"]) if paths["blockers_csv"].exists() else []
    rows = build_worklist(dashboard_rows, decision_rows, blocker_rows)
    payload = summary_payload(paths, rows)
    write_csv(paths["out_csv"], rows)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, rows)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "completion_status": payload["completion_status"],
                "work_item_count": payload["work_item_count"],
                "release_blocking_count": payload["release_blocking_count"],
            },
            indent=2,
        )
    )
    return 1 if payload["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
