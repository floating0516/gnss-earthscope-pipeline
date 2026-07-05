#!/usr/bin/env python3
"""Build a focused PGD residual-review annotation starter from the worklist."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


CONTEXT_FIELDS = [
    "starter_priority",
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
]

MANUAL_FIELDS = [
    "manual_review_status",
    "manual_review_cause",
    "manual_review_notes",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]

STARTER_FIELDS = CONTEXT_FIELDS + MANUAL_FIELDS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=Path("reports/pgd_magnitude/release/latest"))
    parser.add_argument("--worklist-csv", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument(
        "--include-nonblocking",
        action="store_true",
        help="Include all worklist rows instead of only release-blocking rows.",
    )
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "worklist_csv": args.worklist_csv or release_dir / "residual_review_worklist.csv",
        "out_csv": args.out_csv or release_dir / "release_blocking_review_starter.csv",
        "out_json": args.out_json or release_dir / "release_blocking_review_starter.json",
        "out_md": args.out_md or release_dir / "release_blocking_review_starter.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unfilled") for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def build_starter_rows(worklist_rows: list[dict[str, str]], include_nonblocking: bool = False) -> list[dict[str, str]]:
    selected = [
        row
        for row in worklist_rows
        if include_nonblocking or str(row.get("release_blocking") or "").strip().lower() == "yes"
    ]
    rows: list[dict[str, str]] = []
    for index, row in enumerate(selected, start=1):
        output = {field: str(row.get(field, "")) for field in STARTER_FIELDS}
        output["starter_priority"] = str(index)
        for field in MANUAL_FIELDS:
            output[field] = ""
        rows.append(output)
    return rows


def summary_payload(
    paths: dict[str, Path],
    worklist_rows: list[dict[str, str]],
    starter_rows: list[dict[str, str]],
    include_nonblocking: bool,
) -> dict[str, Any]:
    release_blocking_count = sum(1 for row in starter_rows if row.get("release_blocking") == "yes")
    return {
        "status": "OK",
        "mode": "all_worklist_rows" if include_nonblocking else "release_blocking",
        "release_dir": str(paths["release_dir"]),
        "worklist_csv": str(paths["worklist_csv"]),
        "out_csv": str(paths["out_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        "worklist_input_count": len(worklist_rows),
        "starter_row_count": len(starter_rows),
        "release_blocking_count": release_blocking_count,
        "nonblocking_count": len(starter_rows) - release_blocking_count,
        "suggested_review_status_counts": count_by(starter_rows, "suggested_review_status"),
        "suggested_review_cause_counts": count_by(starter_rows, "suggested_review_cause"),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STARTER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in STARTER_FIELDS} for row in rows)


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
        "# Release-Blocking Review Starter",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Mode: `{payload.get('mode', '')}`",
        f"- Worklist input rows: {payload.get('worklist_input_count', 0)}",
        f"- Starter rows: {payload.get('starter_row_count', 0)}",
        f"- Release-blocking rows: {payload.get('release_blocking_count', 0)}",
        "",
        "This starter is a focused manual review worksheet. Suggested fields are copied from the worklist; manual fields are blank until a reviewer fills a copy.",
        "",
        "Rows can be merged back with `manage_residual_review.py --starter-annotations` after manual fields are filled.",
        "",
        "## Starter Rows",
        "",
        *markdown_table(
            rows,
            [
                "starter_priority",
                "event_id",
                "formula",
                "worklist_status",
                "release_blocking",
                "suggested_review_status",
                "suggested_review_cause",
                "packet_path",
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    paths = resolve_paths(args)
    worklist_rows = read_csv(paths["worklist_csv"])
    starter_rows = build_starter_rows(worklist_rows, include_nonblocking=args.include_nonblocking)
    payload = summary_payload(paths, worklist_rows, starter_rows, include_nonblocking=args.include_nonblocking)
    write_csv(paths["out_csv"], starter_rows)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, starter_rows)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "mode": payload["mode"],
                "starter_row_count": payload["starter_row_count"],
                "release_blocking_count": payload["release_blocking_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
