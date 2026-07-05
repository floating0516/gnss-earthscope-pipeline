#!/usr/bin/env python3
"""Merge and summarize PGD residual review annotations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


REVIEW_FIELDS = [
    "review_status",
    "suspected_cause",
    "waveform_issue",
    "station_geometry_issue",
    "magnitude_metadata_issue",
    "formula_limitation",
    "reviewer_note",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]

KEY_FIELDS = ["event_id", "formula"]
STARTER_MANUAL_FIELDS = [
    "manual_review_status",
    "manual_review_cause",
    "manual_review_notes",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]

ALLOWED_REVIEW_STATUSES = {
    "UNREVIEWED",
    "REVIEWED",
    "ACCEPTED",
    "EXCLUDED",
    "NEEDS_DATA_CHECK",
    "NEEDS_METADATA_CHECK",
    "NEEDS_FORMULA_REVIEW",
}

TERMINAL_REVIEW_STATUSES = {"REVIEWED", "ACCEPTED", "EXCLUDED"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, required=True, help="Base residual_review.csv from the PGD report.")
    annotation_group = parser.add_mutually_exclusive_group()
    annotation_group.add_argument("--annotations", type=Path, default=None, help="Optional manual annotation CSV keyed by event_id and formula.")
    annotation_group.add_argument(
        "--starter-annotations",
        type=Path,
        default=None,
        help="Optional completed residual_review_annotations_starter.csv from the PGD release package.",
    )
    parser.add_argument("--out-csv", type=Path, required=True, help="Merged annotated residual review CSV.")
    parser.add_argument("--out-json", type=Path, required=True, help="Machine-readable review summary JSON.")
    parser.add_argument("--out-md", type=Path, required=True, help="Human-readable review summary Markdown.")
    parser.add_argument("--strict", action="store_true", help="Fail on annotation rows that do not match a base review row.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def review_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("formula") or ""))


def normalized_review_status(value: str | None) -> str:
    status = str(value or "").strip().upper()
    return status or "UNREVIEWED"


def output_fields(base_fields: list[str]) -> list[str]:
    fields = list(base_fields)
    for field in KEY_FIELDS + REVIEW_FIELDS:
        if field not in fields:
            fields.append(field)
    return fields


def error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def load_annotations(path: Path | None) -> tuple[list[dict[str, str]], list[str]]:
    if path is None:
        return [], []
    return read_csv(path)


def starter_row_has_manual_values(row: dict[str, str]) -> bool:
    return any(str(row.get(field) or "").strip() for field in STARTER_MANUAL_FIELDS)


def starter_annotations_to_review_annotations(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    annotations: list[dict[str, str]] = []
    for row in rows:
        if not starter_row_has_manual_values(row):
            continue
        annotations.append(
            {
                "event_id": str(row.get("event_id") or ""),
                "formula": str(row.get("formula") or ""),
                "review_status": str(row.get("manual_review_status") or ""),
                "suspected_cause": str(row.get("manual_review_cause") or ""),
                "reviewer_note": str(row.get("manual_review_notes") or ""),
                "accepted_for_release": str(row.get("accepted_for_release") or ""),
                "reviewer": str(row.get("reviewer") or ""),
                "reviewed_at": str(row.get("reviewed_at") or ""),
            }
        )
    return annotations, [*KEY_FIELDS, *REVIEW_FIELDS]


def load_starter_annotations(path: Path | None) -> tuple[list[dict[str, str]], list[str], int]:
    if path is None:
        return [], [], 0
    rows, _fields = read_csv(path)
    annotations, fields = starter_annotations_to_review_annotations(rows)
    return annotations, fields, len(rows)


def merge_annotations(
    base_rows: list[dict[str, str]],
    base_fields: list[str],
    annotation_rows: list[dict[str, str]],
    annotation_fields: list[str],
    strict: bool,
) -> tuple[list[dict[str, str]], list[str], list[dict[str, object]]]:
    fields = output_fields(base_fields)
    by_key = {review_key(row): row for row in base_rows if all(review_key(row))}
    errors: list[dict[str, object]] = []
    unknown_annotation_fields = [
        field for field in annotation_fields if field not in set(KEY_FIELDS + REVIEW_FIELDS) and field is not None
    ]
    if strict and unknown_annotation_fields:
        errors.append(
            error(
                "UNKNOWN_ANNOTATION_FIELD",
                "Annotation CSV contains fields that are not part of the residual review contract.",
                fields=",".join(sorted(unknown_annotation_fields)),
            )
        )

    merged_by_key = {key: dict(row) for key, row in by_key.items()}
    for row in annotation_rows:
        key = review_key(row)
        if not all(key):
            errors.append(error("MISSING_ANNOTATION_KEY", "Annotation row is missing event_id or formula."))
            continue
        if key not in merged_by_key:
            if strict:
                errors.append(
                    error(
                        "UNKNOWN_ANNOTATION_KEY",
                        "Annotation row does not match any base residual review row.",
                        event_id=key[0],
                        formula=key[1],
                    )
                )
            continue
        for field in REVIEW_FIELDS:
            if field in row and row[field] is not None:
                merged_by_key[key][field] = row[field]

    merged_rows: list[dict[str, str]] = []
    for row in base_rows:
        key = review_key(row)
        merged = dict(merged_by_key.get(key, row))
        for field in fields:
            merged.setdefault(field, "")
        merged["review_status"] = normalized_review_status(merged.get("review_status"))
        if merged["review_status"] not in ALLOWED_REVIEW_STATUSES:
            errors.append(
                error(
                    "INVALID_REVIEW_STATUS",
                    "Residual review status is not allowed.",
                    event_id=key[0],
                    formula=key[1],
                    review_status=merged["review_status"],
                )
            )
        merged_rows.append(merged)

    return merged_rows, fields, errors


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(normalized_review_status(row.get("review_status")) for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def cause_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(str(row.get("suspected_cause") or "").strip() for row in rows if str(row.get("suspected_cause") or "").strip())
    return {key: counts[key] for key in sorted(counts)}


def pending_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    pending: list[dict[str, str]] = []
    for row in rows:
        status = normalized_review_status(row.get("review_status"))
        if status in TERMINAL_REVIEW_STATUSES:
            continue
        pending.append(
            {
                "event_id": row.get("event_id", ""),
                "formula": row.get("formula", ""),
                "review_status": status,
                "abs_residual_mw": row.get("abs_residual_mw", ""),
                "suspected_cause": row.get("suspected_cause", ""),
                "reviewer_note": row.get("reviewer_note", ""),
            }
        )
    return pending


def summary_payload(
    *,
    args: argparse.Namespace,
    rows: list[dict[str, str]],
    annotation_rows: list[dict[str, str]],
    starter_row_count: int,
    errors: list[dict[str, object]],
) -> dict[str, object]:
    statuses = status_counts(rows)
    unreviewed_count = statuses.get("UNREVIEWED", 0)
    return {
        "status": "INVALID" if errors else "OK",
        "review_csv": str(args.review_csv),
        "annotations": str(args.annotations) if args.annotations else "",
        "starter_annotations": str(args.starter_annotations) if args.starter_annotations else "",
        "out_csv": str(args.out_csv),
        "row_count": len(rows),
        "annotation_count": len(annotation_rows),
        "starter_row_count": starter_row_count,
        "reviewed_count": len(rows) - unreviewed_count,
        "unreviewed_count": unreviewed_count,
        "status_counts": statuses,
        "suspected_cause_counts": cause_counts(rows),
        "pending_review_rows": pending_rows(rows),
        "errors": errors,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    status_counts_payload = payload.get("status_counts", {})
    cause_counts_payload = payload.get("suspected_cause_counts", {})
    pending = payload.get("pending_review_rows", [])
    errors = payload.get("errors", [])
    assert isinstance(status_counts_payload, dict)
    assert isinstance(cause_counts_payload, dict)
    assert isinstance(pending, list)
    assert isinstance(errors, list)
    lines = [
        "# Residual Review Summary",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Rows: {payload.get('row_count', 0)}",
        f"- Reviewed rows: {payload.get('reviewed_count', 0)}",
        f"- Unreviewed rows: {payload.get('unreviewed_count', 0)}",
        "",
        "## Status Counts",
        "",
        *markdown_table([{"review_status": key, "count": value} for key, value in status_counts_payload.items()], ["review_status", "count"]),
        "",
        "## Suspected Causes",
        "",
        *markdown_table([{"suspected_cause": key, "count": value} for key, value in cause_counts_payload.items()], ["suspected_cause", "count"]),
        "",
        "## Pending Review",
        "",
        *markdown_table(pending, ["event_id", "formula", "review_status", "abs_residual_mw", "suspected_cause", "reviewer_note"]),
        "",
    ]
    if errors:
        lines.extend(
            [
                "## Errors",
                "",
                *markdown_table(errors, ["code", "message", "event_id", "formula", "review_status"]),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, object]:
    base_rows, base_fields = read_csv(args.review_csv)
    if args.starter_annotations:
        annotation_rows, annotation_fields, starter_row_count = load_starter_annotations(args.starter_annotations)
    else:
        annotation_rows, annotation_fields = load_annotations(args.annotations)
        starter_row_count = 0
    merged_rows, fields, errors = merge_annotations(base_rows, base_fields, annotation_rows, annotation_fields, args.strict)
    payload = summary_payload(args=args, rows=merged_rows, annotation_rows=annotation_rows, starter_row_count=starter_row_count, errors=errors)
    write_csv(args.out_csv, merged_rows, fields)
    write_json(args.out_json, payload)
    write_markdown(args.out_md, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(args)
    print(json.dumps({"status": payload["status"], "row_count": payload["row_count"], "errors": len(payload["errors"])}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
