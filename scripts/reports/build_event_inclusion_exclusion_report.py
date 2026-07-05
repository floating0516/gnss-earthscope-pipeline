#!/usr/bin/env python3
"""Build an event inclusion/exclusion report from batches, runs, and normalized exports."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SUMMARY_DIR = REPO_ROOT / "scripts" / "summaries"
if str(SUMMARY_DIR) not in sys.path:
    sys.path.insert(0, str(SUMMARY_DIR))

import build_run_ledger


FIELDS = [
    "event_id",
    "event_time",
    "source",
    "batch_present",
    "run_present",
    "workflow_count",
    "latest_workflow",
    "latest_status",
    "export_status",
    "quality_status",
    "kin_count",
    "station_count",
    "plot_status",
    "failure_class",
    "inclusion_stage",
    "final_status",
    "exclusion_reason",
    "next_action",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, action="append", default=[], help="Candidate/batch CSV or TSV. May be repeated.")
    parser.add_argument("--runs", type=Path, required=True, help="Workflow runs root.")
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    return parser.parse_args(argv)


def read_table(path: Path) -> list[dict[str, str]]:
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle, delimiter=delimiter))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def first_text(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def batch_event_id(row: dict[str, str]) -> str:
    return first_text(row.get("event_id"), row.get("Event_ID"), row.get("id"))


def load_batch_index(batch_paths: list[Path]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for path in batch_paths:
        for row in read_table(path):
            event_id = batch_event_id(row)
            if not event_id:
                continue
            indexed.setdefault(
                event_id,
                {
                    "event_id": event_id,
                    "event_time": first_text(row.get("event_time"), row.get("time_utc"), row.get("date"), row.get("Event_Time")),
                    "source": first_text(row.get("source"), row.get("network"), row.get("Source")),
                    "batch_status": first_text(row.get("status"), row.get("batch_status")),
                },
            )
    return indexed


def derive_final_status(batch_present: bool, run_present: bool, ledger: dict[str, str]) -> tuple[str, str, str, str]:
    export_status = ledger.get("export_status", "")
    latest_status = ledger.get("latest_status", "")
    failure_class = ledger.get("failure_class", "")
    next_action = ledger.get("next_action", "")

    if export_status == "OK":
        return "normalized_export", "INCLUDED_NORMALIZED", "", "DONE"
    if not run_present and batch_present:
        return "batch_candidate", "NOT_STARTED", "", "SCHEDULE_WORKFLOW"
    if failure_class == "NO_OBS":
        return "obs_validation", "EXCLUDED_NO_OBS", "NO_OBS", next_action or "CLASSIFY_NO_OBS"
    if failure_class == "NO_KIN":
        return "pride_processing", "EXCLUDED_NO_KIN", "NO_KIN", next_action or "CLASSIFY_NO_KIN"
    if failure_class == "QUALITY_FAIL":
        return "quality", "EXCLUDED_QUALITY_FAIL", "QUALITY_FAIL", next_action or "REVIEW_QUALITY"
    if latest_status.startswith("ABANDONED") or failure_class == "TIMEOUT" and latest_status.startswith("ABANDONED"):
        return "workflow_timeout", "EXCLUDED_ABANDONED", failure_class or latest_status, next_action or "REVIEW_OR_ABANDON"
    if latest_status.startswith("RETRY"):
        return "workflow_retry", "RETRY_PENDING", failure_class, next_action or "RERUN"
    if run_present:
        return "workflow_review", "NEEDS_REVIEW", failure_class or latest_status or "UNKNOWN", next_action or "REVIEW"
    return "untracked", "NEEDS_REVIEW", "NO_BATCH_OR_RUN", "REVIEW"


def build_rows(batch_paths: list[Path], runs_root: Path, export_root: Path) -> list[dict[str, str]]:
    batch_index = load_batch_index(batch_paths)
    ledger_rows = {row["event_id"]: row for row in build_run_ledger.build_rows(runs_root, export_root)}
    event_ids = sorted(set(batch_index) | set(ledger_rows))
    rows: list[dict[str, str]] = []
    for event_id in event_ids:
        batch = batch_index.get(event_id, {})
        ledger = ledger_rows.get(event_id, {})
        workflow_count = first_text(ledger.get("workflow_count"), "0")
        run_present = workflow_count not in {"", "0"}
        batch_present = event_id in batch_index
        inclusion_stage, final_status, exclusion_reason, next_action = derive_final_status(batch_present, run_present, ledger)
        rows.append(
            {
                "event_id": event_id,
                "event_time": first_text(batch.get("event_time")),
                "source": first_text(batch.get("source")),
                "batch_present": "yes" if batch_present else "no",
                "run_present": "yes" if run_present else "no",
                "workflow_count": workflow_count,
                "latest_workflow": first_text(ledger.get("latest_workflow")),
                "latest_status": first_text(ledger.get("latest_status")),
                "export_status": first_text(ledger.get("export_status"), "MISSING"),
                "quality_status": first_text(ledger.get("quality_status")),
                "kin_count": first_text(ledger.get("kin_count")),
                "station_count": first_text(ledger.get("station_count")),
                "plot_status": first_text(ledger.get("plot_status")),
                "failure_class": first_text(ledger.get("failure_class")),
                "inclusion_stage": inclusion_stage,
                "final_status": final_status,
                "exclusion_reason": exclusion_reason,
                "next_action": next_action,
            }
        )
    return rows


def summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_status = Counter(row["final_status"] for row in rows)
    by_stage = Counter(row["inclusion_stage"] for row in rows)
    return {
        "total_events": len(rows),
        "included_normalized": by_status.get("INCLUDED_NORMALIZED", 0),
        "excluded_events": sum(count for status, count in by_status.items() if status.startswith("EXCLUDED")),
        "retry_pending": by_status.get("RETRY_PENDING", 0),
        "not_started": by_status.get("NOT_STARTED", 0),
        "needs_review": by_status.get("NEEDS_REVIEW", 0),
        "by_final_status": dict(sorted(by_status.items())),
        "by_inclusion_stage": dict(sorted(by_stage.items())),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary(rows), "events": rows}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    payload = summary(rows)
    lines = [
        "# Event Inclusion/Exclusion Report",
        "",
        f"- Total events: {payload['total_events']}",
        f"- Included normalized: {payload['included_normalized']}",
        f"- Excluded events: {payload['excluded_events']}",
        f"- Retry pending: {payload['retry_pending']}",
        f"- Not started: {payload['not_started']}",
        f"- Needs review: {payload['needs_review']}",
        "",
        "| event_id | final_status | stage | reason | next_action | export | workflows |",
        "|---|---|---|---|---|---|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(row.get(field, ""))
                for field in [
                    "event_id",
                    "final_status",
                    "inclusion_stage",
                    "exclusion_reason",
                    "next_action",
                    "export_status",
                    "workflow_count",
                ]
            )
            + " |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_rows(args.batch, args.runs, args.export_root)
    write_csv(args.out_csv, rows)
    write_json(args.out_json, rows)
    write_markdown(args.out_md, rows)
    print(f"wrote event inclusion/exclusion report: events={len(rows)} md={args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
