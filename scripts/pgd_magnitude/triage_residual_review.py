#!/usr/bin/env python3
"""Add automatic triage suggestions to PGD residual review rows."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


TERMINAL_REVIEW_STATUSES = {"REVIEWED", "ACCEPTED", "EXCLUDED"}

TRIAGE_FIELDS = [
    "triage_priority",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "triage_reason",
    "next_review_action",
    "best_formula_for_event",
    "best_formula_abs_residual_mw",
    "formula_residuals_for_event",
    "formula_limitation_suggested",
    "release_status",
    "release_failure_reasons",
    "release_review_reasons",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, required=True, help="Annotated residual review CSV.")
    parser.add_argument("--events-csv", type=Path, required=True, help="PGD report events.csv with all formula rows.")
    parser.add_argument("--release-set-csv", type=Path, required=True, help="PGD release_set.csv.")
    parser.add_argument("--out-csv", type=Path, required=True, help="Output triage CSV.")
    parser.add_argument("--out-json", type=Path, required=True, help="Output triage summary JSON.")
    parser.add_argument("--out-md", type=Path, required=True, help="Output triage Markdown report.")
    parser.add_argument("--residual-threshold", type=float, default=1.0, help="Absolute residual threshold that triggers review suggestions.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def fmt(value: object, digits: int = 6) -> str:
    number = finite_float(value)
    if not math.isfinite(number):
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".")


def normalized_review_status(value: object) -> str:
    status = str(value or "").strip().upper()
    return status or "UNREVIEWED"


def event_formula_context(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_event: dict[str, list[dict[str, str]]] = {}
    for row in events:
        event_id = str(row.get("event_id") or "")
        if event_id:
            by_event.setdefault(event_id, []).append(row)

    context: dict[str, dict[str, str]] = {}
    for event_id, rows in by_event.items():
        finite_rows = [row for row in rows if math.isfinite(finite_float(row.get("abs_residual_mw")))]
        best = min(finite_rows, key=lambda row: (finite_float(row.get("abs_residual_mw")), str(row.get("formula") or ""))) if finite_rows else {}
        residual_parts = [
            f"{row.get('formula', '')}={fmt(row.get('abs_residual_mw'))}"
            for row in sorted(finite_rows, key=lambda item: str(item.get("formula") or ""))
        ]
        context[event_id] = {
            "best_formula_for_event": str(best.get("formula") or ""),
            "best_formula_abs_residual_mw": fmt(best.get("abs_residual_mw", "")),
            "formula_residuals_for_event": ";".join(residual_parts),
        }
    return context


def release_context(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("event_id") or ""): row for row in rows if str(row.get("event_id") or "")}


def sort_key(row: dict[str, str]) -> tuple[int, float, str, str]:
    status = normalized_review_status(row.get("review_status"))
    terminal_rank = 1 if status in TERMINAL_REVIEW_STATUSES else 0
    residual = finite_float(row.get("abs_residual_mw"))
    residual_sort = residual if math.isfinite(residual) else -1.0
    return (terminal_rank, -residual_sort, str(row.get("event_id") or ""), str(row.get("formula") or ""))


def append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def triage_suggestion(
    row: dict[str, str],
    formula_context: dict[str, str],
    release: dict[str, str],
    residual_threshold: float,
) -> dict[str, str]:
    status = normalized_review_status(row.get("review_status"))
    formula = str(row.get("formula") or "")
    best_formula = str(formula_context.get("best_formula_for_event") or "")
    abs_residual = finite_float(row.get("abs_residual_mw"))
    usable_count = finite_float(row.get("usable_station_count"))
    median_snr = finite_float(row.get("median_pgd_snr"))
    release_status = str(release.get("release_status") or "")
    release_failure = str(release.get("release_failure_reasons") or "")
    release_review = str(release.get("release_review_reasons") or "")

    reasons: list[str] = []
    data_check_reasons: list[str] = []
    actions: list[str] = []
    formula_limitation = "yes" if best_formula and formula and best_formula != formula else "no"

    if status in TERMINAL_REVIEW_STATUSES:
        return {
            "triage_status_suggestion": status,
            "triage_cause_suggestion": "already_reviewed",
            "triage_reason": "manual review status is terminal",
            "next_review_action": "NO_ACTION",
            "formula_limitation_suggested": formula_limitation,
        }

    if math.isfinite(usable_count) and usable_count <= 0:
        append_unique(reasons, "zero usable stations")
        append_unique(data_check_reasons, "zero usable stations")
        append_unique(actions, "CHECK_WAVEFORM_AND_STATION_FILTERING")
    if not math.isfinite(median_snr):
        append_unique(reasons, "missing median PGD SNR")
        append_unique(data_check_reasons, "missing median PGD SNR")
        append_unique(actions, "CHECK_NOISE_WINDOW_AND_SNR")
    elif median_snr < 3.0:
        append_unique(reasons, "low median PGD SNR")
        append_unique(data_check_reasons, "low median PGD SNR")
        append_unique(actions, "CHECK_WAVEFORM_NOISE")
    if release_status and release_status != "INCLUDED_RELEASE_SET":
        append_unique(reasons, f"release gate: {release_status}")
        append_unique(actions, "CHECK_RELEASE_GATE")
        if release_status == "EXCLUDED_RELEASE_SET":
            append_unique(data_check_reasons, f"release gate: {release_status}")
    if release_failure:
        append_unique(reasons, f"release failures: {release_failure}")
        append_unique(data_check_reasons, f"release failures: {release_failure}")
    if release_review:
        append_unique(reasons, f"release review: {release_review}")

    if data_check_reasons:
        status_suggestion = "NEEDS_DATA_CHECK"
        cause_suggestion = "data_quality"
    elif formula_limitation == "yes" and math.isfinite(abs_residual) and abs_residual >= residual_threshold:
        status_suggestion = "NEEDS_FORMULA_REVIEW"
        cause_suggestion = "formula_limitation"
    elif math.isfinite(abs_residual) and abs_residual >= residual_threshold:
        status_suggestion = "NEEDS_DATA_CHECK"
        cause_suggestion = "residual_outlier"
    else:
        status_suggestion = "ACCEPTED"
        cause_suggestion = "low_priority"

    if formula_limitation == "yes":
        append_unique(reasons, f"formula differs from best formula {best_formula}")
        append_unique(actions, "COMPARE_FORMULA_RESIDUALS")
    if math.isfinite(abs_residual) and abs_residual >= residual_threshold:
        append_unique(reasons, f"abs residual {fmt(abs_residual)} >= {fmt(residual_threshold)}")
    if not actions:
        append_unique(actions, "NO_ACTION")

    return {
        "triage_status_suggestion": status_suggestion,
        "triage_cause_suggestion": cause_suggestion,
        "triage_reason": "; ".join(reasons),
        "next_review_action": ";".join(actions),
        "formula_limitation_suggested": formula_limitation,
    }


def build_triage_rows(
    review_rows: list[dict[str, str]],
    events: list[dict[str, str]],
    release_rows: list[dict[str, str]],
    residual_threshold: float,
) -> list[dict[str, str]]:
    formula_by_event = event_formula_context(events)
    release_by_event = release_context(release_rows)
    rows: list[dict[str, str]] = []
    for index, row in enumerate(sorted(review_rows, key=sort_key), start=1):
        event_id = str(row.get("event_id") or "")
        formula_context = formula_by_event.get(event_id, {})
        release = release_by_event.get(event_id, {})
        output = dict(row)
        output["review_status"] = normalized_review_status(row.get("review_status"))
        output["triage_priority"] = str(index)
        output["best_formula_for_event"] = formula_context.get("best_formula_for_event", "")
        output["best_formula_abs_residual_mw"] = formula_context.get("best_formula_abs_residual_mw", "")
        output["formula_residuals_for_event"] = formula_context.get("formula_residuals_for_event", "")
        output["release_status"] = release.get("release_status", "")
        output["release_failure_reasons"] = release.get("release_failure_reasons", "")
        output["release_review_reasons"] = release.get("release_review_reasons", "")
        output.update(triage_suggestion(row, formula_context, release, residual_threshold))
        rows.append(output)
    return rows


def output_fields(base_fields: list[str]) -> list[str]:
    fields = list(base_fields)
    for field in TRIAGE_FIELDS:
        if field not in fields:
            fields.append(field)
    return fields


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def summary_payload(args: argparse.Namespace, rows: list[dict[str, str]]) -> dict[str, object]:
    status_counts = Counter(row.get("triage_status_suggestion", "") for row in rows)
    cause_counts = Counter(row.get("triage_cause_suggestion", "") for row in rows)
    return {
        "status": "OK",
        "review_csv": str(args.review_csv),
        "events_csv": str(args.events_csv),
        "release_set_csv": str(args.release_set_csv),
        "out_csv": str(args.out_csv),
        "row_count": len(rows),
        "residual_threshold": args.residual_threshold,
        "suggested_status_counts": {key: status_counts[key] for key in sorted(status_counts) if key},
        "suggested_cause_counts": {key: cause_counts[key] for key in sorted(cause_counts) if key},
        "top_priority_rows": [
            {
                "triage_priority": row.get("triage_priority", ""),
                "event_id": row.get("event_id", ""),
                "formula": row.get("formula", ""),
                "abs_residual_mw": row.get("abs_residual_mw", ""),
                "triage_status_suggestion": row.get("triage_status_suggestion", ""),
                "triage_cause_suggestion": row.get("triage_cause_suggestion", ""),
                "next_review_action": row.get("next_review_action", ""),
            }
            for row in rows[:10]
        ],
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, object], rows: list[dict[str, str]]) -> None:
    lines = [
        "# Residual Review Triage",
        "",
        f"- Rows: {payload['row_count']}",
        f"- Residual threshold: {payload['residual_threshold']}",
        "",
        "## Suggested Status Counts",
        "",
        *markdown_table(
            [{"status": key, "count": str(value)} for key, value in dict(payload["suggested_status_counts"]).items()],
            ["status", "count"],
        ),
        "",
        "## Review Queue",
        "",
        *markdown_table(
            rows[:20],
            [
                "triage_priority",
                "event_id",
                "formula",
                "review_status",
                "abs_residual_mw",
                "triage_status_suggestion",
                "triage_cause_suggestion",
                "best_formula_for_event",
                "release_status",
                "next_review_action",
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> list[dict[str, str]]:
    review_rows, review_fields = read_csv(args.review_csv)
    event_rows, _event_fields = read_csv(args.events_csv)
    release_rows, _release_fields = read_csv(args.release_set_csv)
    rows = build_triage_rows(review_rows, event_rows, release_rows, args.residual_threshold)
    fields = output_fields(review_fields)
    payload = summary_payload(args, rows)
    write_csv(args.out_csv, rows, fields)
    write_json(args.out_json, payload)
    write_markdown(args.out_md, payload, rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = run(args)
    print(json.dumps({"status": "OK", "row_count": len(rows), "out_csv": str(args.out_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
