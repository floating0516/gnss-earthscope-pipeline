#!/usr/bin/env python3
"""Build a PGD release-set view after residual review decisions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")
BASE_RELEASE_FIELDS = [
    "event_id",
    "event_time",
    "country",
    "region",
    "place",
    "formula",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "release_status",
]
REVIEWED_RELEASE_FIELDS = [
    "reviewed_release_status",
    "review_source",
    *BASE_RELEASE_FIELDS,
    "decision_status",
    "manual_review_status",
    "accepted_for_release",
    "manual_review_cause",
    "manual_review_notes",
    "reviewer",
    "reviewed_at",
    "packet_path",
]
BLOCKER_FIELDS = [
    "event_id",
    "formula",
    "blocker_status",
    "blocker_reason",
    "review_source",
    "decision_status",
    "manual_review_status",
    "accepted_for_release",
    "manual_review_cause",
    "reviewer",
    "reviewed_at",
    "packet_path",
    "release_status",
    "release_failure_reasons",
    "release_review_reasons",
    "abs_residual_mw",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "next_decision_action",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--release-events-csv", type=Path, default=None)
    parser.add_argument("--decision-report-csv", type=Path, default=None)
    parser.add_argument("--out-events-csv", type=Path, default=None)
    parser.add_argument("--out-blockers-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "release_events_csv": args.release_events_csv or release_dir / "release_events.csv",
        "decision_report_csv": args.decision_report_csv or release_dir / "residual_review_decision_report.csv",
        "out_events_csv": args.out_events_csv or release_dir / "reviewed_release_events.csv",
        "out_blockers_csv": args.out_blockers_csv or release_dir / "reviewed_release_blockers.csv",
        "out_json": args.out_json or release_dir / "reviewed_release_summary.json",
        "out_md": args.out_md or release_dir / "reviewed_release_summary.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def event_key(row: dict[str, str]) -> str:
    return str(row.get("event_id") or "")


def decision_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    priority = str(row.get("triage_priority") or "")
    return (int(priority) if priority.isdigit() else 999999, str(row.get("event_id") or ""), str(row.get("formula") or ""))


def latest_decision_by_event(decision_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_event: dict[str, list[dict[str, str]]] = {}
    for row in sorted(decision_rows, key=decision_sort_key):
        event_id = event_key(row)
        if event_id:
            by_event.setdefault(event_id, []).append(row)
    return by_event


def decision_blocks_release(decision: dict[str, str]) -> bool:
    return str(decision.get("decision_status") or "") in {"EXCLUDED_BY_REVIEW", "PENDING_REVIEW", "INVALID_DECISION"}


def blocker_reason(decision: dict[str, str]) -> str:
    status = str(decision.get("decision_status") or "")
    if status == "EXCLUDED_BY_REVIEW":
        return "Residual review excluded this event/formula from the reviewed release set."
    if status == "PENDING_REVIEW":
        return "Residual review decision is still pending."
    if status == "INVALID_DECISION":
        return "Residual review decision is invalid and must be corrected."
    return "Residual review decision blocks release."


def reviewed_row_from_release(row: dict[str, str], status: str) -> dict[str, str]:
    output = {field: "" for field in REVIEWED_RELEASE_FIELDS}
    for field in BASE_RELEASE_FIELDS:
        output[field] = row.get(field, "")
    output["reviewed_release_status"] = status
    output["review_source"] = "baseline_release_set"
    return output


def reviewed_row_from_decision(row: dict[str, str]) -> dict[str, str]:
    output = {field: "" for field in REVIEWED_RELEASE_FIELDS}
    for field in BASE_RELEASE_FIELDS:
        output[field] = row.get(field, "")
    output["reviewed_release_status"] = "INCLUDED_BY_REVIEW"
    output["review_source"] = "residual_review_decision"
    for field in [
        "decision_status",
        "manual_review_status",
        "accepted_for_release",
        "manual_review_cause",
        "manual_review_notes",
        "reviewer",
        "reviewed_at",
        "packet_path",
    ]:
        output[field] = row.get(field, "")
    return output


def blocker_row_from_decision(row: dict[str, str]) -> dict[str, str]:
    output = {field: "" for field in BLOCKER_FIELDS}
    for field in BLOCKER_FIELDS:
        output[field] = row.get(field, "")
    output["blocker_status"] = row.get("decision_status", "")
    output["blocker_reason"] = blocker_reason(row)
    output["review_source"] = "residual_review_decision"
    return output


def build_reviewed_release(
    release_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    decisions_by_event = latest_decision_by_event(decision_rows)
    included: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    included_event_ids: set[str] = set()

    for row in sorted(release_rows, key=lambda item: str(item.get("event_id") or "")):
        event_id = event_key(row)
        event_decisions = decisions_by_event.get(event_id, [])
        blocking_decisions = [decision for decision in event_decisions if decision_blocks_release(decision)]
        if blocking_decisions:
            blockers.extend(blocker_row_from_decision(decision) for decision in blocking_decisions)
            continue
        included.append(reviewed_row_from_release(row, "INCLUDED_BASELINE_RELEASE_SET"))
        included_event_ids.add(event_id)

    for decision in sorted(decision_rows, key=decision_sort_key):
        status = str(decision.get("decision_status") or "")
        event_id = event_key(decision)
        if status == "ACCEPTED_FOR_RELEASE" and event_id not in included_event_ids:
            included.append(reviewed_row_from_decision(decision))
            included_event_ids.add(event_id)
        elif status in {"EXCLUDED_BY_REVIEW", "PENDING_REVIEW", "INVALID_DECISION"} and event_id not in {row.get("event_id", "") for row in blockers}:
            blockers.append(blocker_row_from_decision(decision))

    counts = Counter(str(row.get("decision_status") or "") for row in decision_rows)
    metrics = {
        "baseline_ready_count": len(release_rows),
        "reviewed_release_count": len(included),
        "included_from_baseline_count": sum(1 for row in included if row.get("reviewed_release_status") == "INCLUDED_BASELINE_RELEASE_SET"),
        "accepted_by_review_count": counts.get("ACCEPTED_FOR_RELEASE", 0),
        "excluded_by_review_count": counts.get("EXCLUDED_BY_REVIEW", 0),
        "pending_review_count": counts.get("PENDING_REVIEW", 0),
        "invalid_decision_count": counts.get("INVALID_DECISION", 0),
        "blocker_count": len(blockers),
    }
    included.sort(key=lambda row: (str(row.get("event_time") or ""), str(row.get("event_id") or "")))
    blockers.sort(key=lambda row: (str(row.get("triage_priority") or ""), str(row.get("event_id") or ""), str(row.get("formula") or "")))
    return included, blockers, metrics


def summary_payload(paths: dict[str, Path], metrics: dict[str, int]) -> dict[str, object]:
    invalid_count = metrics["invalid_decision_count"]
    pending_count = metrics["pending_review_count"]
    return {
        "status": "INVALID" if invalid_count else "OK",
        "completion_status": "COMPLETE" if not pending_count and not invalid_count else "INCOMPLETE",
        "release_dir": str(paths["release_dir"]),
        "release_events_csv": str(paths["release_events_csv"]),
        "decision_report_csv": str(paths["decision_report_csv"]),
        "out_events_csv": str(paths["out_events_csv"]),
        "out_blockers_csv": str(paths["out_blockers_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        **metrics,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


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


def write_markdown(path: Path, payload: dict[str, object], included: list[dict[str, str]], blockers: list[dict[str, str]]) -> None:
    lines = [
        "# Reviewed Release Set",
        "",
        f"- Status: `{payload['status']}`",
        f"- Completion: `{payload['completion_status']}`",
        f"- Baseline ready events: {payload['baseline_ready_count']}",
        f"- Reviewed release events: {payload['reviewed_release_count']}",
        f"- Blockers: {payload['blocker_count']}",
        f"- Pending review decisions: {payload['pending_review_count']}",
        f"- Invalid decisions: {payload['invalid_decision_count']}",
        "",
        "## Reviewed Release Events",
        "",
        *markdown_table(
            included,
            ["event_id", "formula", "reviewed_release_status", "review_source", "reviewer", "packet_path"],
        ),
        "",
        "## Blockers",
        "",
        *markdown_table(
            blockers,
            ["event_id", "formula", "blocker_status", "blocker_reason", "reviewer", "packet_path"],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    paths = resolve_paths(args)
    release_rows = read_csv(paths["release_events_csv"])
    decision_rows = read_csv(paths["decision_report_csv"])
    included, blockers, metrics = build_reviewed_release(release_rows, decision_rows)
    payload = summary_payload(paths, metrics)
    write_csv(paths["out_events_csv"], included, REVIEWED_RELEASE_FIELDS)
    write_csv(paths["out_blockers_csv"], blockers, BLOCKER_FIELDS)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, included, blockers)
    return included, blockers, payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _included, _blockers, payload = run(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "completion_status": payload["completion_status"],
                "reviewed_release_count": payload["reviewed_release_count"],
                "blocker_count": payload["blocker_count"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
