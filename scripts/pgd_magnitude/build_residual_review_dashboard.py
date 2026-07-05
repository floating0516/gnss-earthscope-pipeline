#!/usr/bin/env python3
"""Build a dashboard for PGD residual review packet status."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")
KEY_FIELDS = ["event_id", "formula"]
TERMINAL_MANUAL_STATUSES = {"REVIEWED", "ACCEPTED", "EXCLUDED"}
DASHBOARD_FIELDS = [
    "triage_priority",
    "event_id",
    "formula",
    "review_dashboard_status",
    "manual_review_status",
    "manual_review_cause",
    "accepted_for_release",
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
    "manual_review_notes",
    "triage_reason",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--evidence-csv", type=Path, default=None)
    parser.add_argument("--packet-index-csv", type=Path, default=None)
    parser.add_argument("--starter-csv", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "evidence_csv": args.evidence_csv or release_dir / "residual_review_evidence.csv",
        "packet_index_csv": args.packet_index_csv or release_dir / "residual_review_packet_index.csv",
        "starter_csv": args.starter_csv or release_dir / "residual_review_annotations_starter.csv",
        "out_csv": args.out_csv or release_dir / "residual_review_dashboard.csv",
        "out_json": args.out_json or release_dir / "residual_review_dashboard.json",
        "out_md": args.out_md or release_dir / "residual_review_dashboard.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def review_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("formula") or ""))


def rows_by_key(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {review_key(row): row for row in rows if all(review_key(row))}


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def manual_status(row: dict[str, str]) -> str:
    return str(row.get("manual_review_status") or "").strip().upper()


def manual_status_for_counts(row: dict[str, str]) -> str:
    return manual_status(row) or "UNFILLED"


def review_dashboard_status(row: dict[str, str]) -> str:
    status = manual_status(row)
    if not status:
        return "PENDING_REVIEW"
    if status in TERMINAL_MANUAL_STATUSES:
        return "REVIEWED"
    return "IN_REVIEW"


def build_dashboard_rows(
    evidence_rows: list[dict[str, str]],
    packet_rows: list[dict[str, str]],
    starter_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    packet_by_key = rows_by_key(packet_rows)
    starter_by_key = rows_by_key(starter_rows)
    errors: list[dict[str, object]] = []
    dashboard_rows: list[dict[str, str]] = []

    for evidence in sorted(
        evidence_rows,
        key=lambda row: (
            int(str(row.get("triage_priority") or "999999")) if str(row.get("triage_priority") or "").isdigit() else 999999,
            str(row.get("event_id") or ""),
            str(row.get("formula") or ""),
        ),
    ):
        key = review_key(evidence)
        if not all(key):
            errors.append(error("MISSING_EVIDENCE_KEY", "Residual evidence row is missing event_id or formula."))
            continue
        packet = packet_by_key.get(key)
        starter = starter_by_key.get(key)
        if packet is None:
            errors.append(
                error(
                    "MISSING_PACKET_INDEX_ROW",
                    "Residual evidence row has no matching packet index row.",
                    event_id=key[0],
                    formula=key[1],
                )
            )
            packet = {}
        if starter is None:
            errors.append(
                error(
                    "MISSING_STARTER_ROW",
                    "Residual evidence row has no matching annotation starter row.",
                    event_id=key[0],
                    formula=key[1],
                )
            )
            starter = {}

        output = {field: "" for field in DASHBOARD_FIELDS}
        for source in (evidence, packet, starter):
            for field in DASHBOARD_FIELDS:
                if field in source and source[field] not in {None, ""}:
                    output[field] = source[field]
        output["event_id"] = key[0]
        output["formula"] = key[1]
        output["manual_review_status"] = manual_status(starter)
        output["review_dashboard_status"] = review_dashboard_status(starter)
        dashboard_rows.append(output)

    return dashboard_rows, errors


def count_field(rows: list[dict[str, str]], field: str, *, blank: str = "unfilled") -> dict[str, int]:
    counts = Counter(str(row.get(field) or "").strip() or blank for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def summary_payload(paths: dict[str, Path], rows: list[dict[str, str]], errors: list[dict[str, object]]) -> dict[str, object]:
    status_counts = count_field(rows, "review_dashboard_status")
    pending_count = status_counts.get("PENDING_REVIEW", 0) + status_counts.get("IN_REVIEW", 0)
    return {
        "status": "INVALID" if errors else "OK",
        "release_dir": str(paths["release_dir"]),
        "evidence_csv": str(paths["evidence_csv"]),
        "packet_index_csv": str(paths["packet_index_csv"]),
        "starter_csv": str(paths["starter_csv"]),
        "out_csv": str(paths["out_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        "row_count": len(rows),
        "reviewed_count": status_counts.get("REVIEWED", 0),
        "pending_count": pending_count,
        "dashboard_status_counts": status_counts,
        "manual_status_counts": count_field(rows, "manual_review_status", blank="UNFILLED"),
        "triage_status_counts": count_field(rows, "triage_status_suggestion"),
        "triage_cause_counts": count_field(rows, "triage_cause_suggestion"),
        "release_status_counts": count_field(rows, "release_status"),
        "accepted_for_release_counts": count_field(rows, "accepted_for_release"),
        "reviewer_counts": count_field(rows, "reviewer"),
        "errors": errors,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DASHBOARD_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in DASHBOARD_FIELDS} for row in rows)


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
    preview = rows[:20]
    lines = [
        "# Residual Review Dashboard",
        "",
        f"- Status: `{payload['status']}`",
        f"- Rows: {payload['row_count']}",
        f"- Reviewed: {payload['reviewed_count']}",
        f"- Pending: {payload['pending_count']}",
        f"- Evidence CSV: `{payload['evidence_csv']}`",
        f"- Packet index CSV: `{payload['packet_index_csv']}`",
        f"- Starter CSV: `{payload['starter_csv']}`",
        "",
        "## Counts",
        "",
        "### Manual Status",
        "",
        *markdown_table(
            [{"status": key, "count": str(value)} for key, value in dict(payload["manual_status_counts"]).items()],
            ["status", "count"],
        ),
        "",
        "### Triage Suggestion",
        "",
        *markdown_table(
            [{"status": key, "count": str(value)} for key, value in dict(payload["triage_status_counts"]).items()],
            ["status", "count"],
        ),
        "",
        "## Review Queue",
        "",
        *markdown_table(
            preview,
            [
                "triage_priority",
                "event_id",
                "formula",
                "review_dashboard_status",
                "manual_review_status",
                "triage_status_suggestion",
                "release_status",
                "accepted_for_release",
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
        evidence_rows = read_csv(paths["evidence_csv"])
        packet_rows = read_csv(paths["packet_index_csv"])
        starter_rows = read_csv(paths["starter_csv"])
    except FileNotFoundError as exc:
        rows: list[dict[str, str]] = []
        errors.append(error("MISSING_INPUT", "Required residual review input is missing.", path=str(exc.filename)))
    else:
        rows, row_errors = build_dashboard_rows(evidence_rows, packet_rows, starter_rows)
        errors.extend(row_errors)

    payload = summary_payload(paths, rows, errors)
    write_csv(paths["out_csv"], rows)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, rows)
    return rows, payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _rows, payload = run(args)
    print(json.dumps({"status": payload["status"], "row_count": payload["row_count"], "out_csv": payload["out_csv"]}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
