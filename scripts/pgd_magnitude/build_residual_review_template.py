#!/usr/bin/env python3
"""Build a PGD residual review annotation template with science context."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


REVIEW_FIELDS = [
    "review_status",
    "suspected_cause",
    "waveform_issue",
    "station_geometry_issue",
    "magnitude_metadata_issue",
    "formula_limitation",
    "reviewer_note",
]

TERMINAL_REVIEW_STATUSES = {"REVIEWED", "ACCEPTED", "EXCLUDED"}
ALLOWED_REVIEW_STATUSES = [
    "UNREVIEWED",
    "REVIEWED",
    "ACCEPTED",
    "EXCLUDED",
    "NEEDS_DATA_CHECK",
    "NEEDS_METADATA_CHECK",
    "NEEDS_FORMULA_REVIEW",
]

TEMPLATE_FIELDS = [
    "review_priority",
    "event_id",
    "formula",
    *REVIEW_FIELDS,
    "event_time",
    "country",
    "place",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "release_status",
    "release_failure_reasons",
    "release_review_reasons",
    "best_formula_for_event",
    "best_formula_abs_residual_mw",
    "formula_residuals_for_event",
    "suggested_checks",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, required=True, help="Annotated residual review CSV.")
    parser.add_argument("--events-csv", type=Path, required=True, help="PGD report events.csv with all formula rows.")
    parser.add_argument("--release-set-csv", type=Path, required=True, help="PGD release_set.csv.")
    parser.add_argument("--out-csv", type=Path, required=True, help="Output annotation template CSV.")
    parser.add_argument("--out-md", type=Path, required=True, help="Output Markdown review guide.")
    parser.add_argument("--include-reviewed", action="store_true", help="Include rows whose review_status is terminal.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def normalized_status(value: object) -> str:
    status = str(value or "").strip().upper()
    return status or "UNREVIEWED"


def is_pending(row: dict[str, str]) -> bool:
    return normalized_status(row.get("review_status")) not in TERMINAL_REVIEW_STATUSES


def event_formula_context(events: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in events:
        event_id = str(row.get("event_id") or "")
        if event_id:
            by_event[event_id].append(row)

    context: dict[str, dict[str, object]] = {}
    for event_id, rows in by_event.items():
        finite_rows = [row for row in rows if math.isfinite(finite_float(row.get("abs_residual_mw")))]
        best = min(finite_rows, key=lambda row: (finite_float(row.get("abs_residual_mw")), str(row.get("formula") or ""))) if finite_rows else {}
        residual_parts = []
        for row in sorted(finite_rows, key=lambda item: str(item.get("formula") or "")):
            residual_parts.append(f"{row.get('formula', '')}={fmt(row.get('abs_residual_mw'))}")
        context[event_id] = {
            "best_formula_for_event": best.get("formula", ""),
            "best_formula_abs_residual_mw": fmt(best.get("abs_residual_mw", "")),
            "formula_residuals_for_event": ";".join(residual_parts),
        }
    return context


def release_context(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("event_id") or ""): row for row in rows if str(row.get("event_id") or "")}


def suggested_checks(row: dict[str, str], formula_context: dict[str, object], release: dict[str, str]) -> str:
    checks: list[str] = []
    usable_count = finite_float(row.get("usable_station_count"))
    median_snr = finite_float(row.get("median_pgd_snr"))
    abs_residual = finite_float(row.get("abs_residual_mw"))
    formula = str(row.get("formula") or "")
    best_formula = str(formula_context.get("best_formula_for_event") or "")
    if math.isfinite(usable_count) and usable_count <= 0:
        checks.append("check usable station filtering and waveform PGD extraction")
    if not math.isfinite(median_snr):
        checks.append("check missing median PGD SNR and pre-event noise window")
    elif median_snr < 3.0:
        checks.append("check low PGD SNR and waveform noise")
    if math.isfinite(abs_residual) and abs_residual >= 1.0:
        checks.append("verify waveform amplitude and event magnitude metadata")
    if best_formula and formula and best_formula != formula:
        checks.append("compare formula limitation against best formula for this event")
    release_status = str(release.get("release_status") or "")
    if release_status and release_status != "INCLUDED_RELEASE_SET":
        checks.append("review release gate failure reasons")
    return "; ".join(dict.fromkeys(checks))


def build_template_rows(
    review_rows: list[dict[str, str]],
    events: list[dict[str, str]],
    release_rows: list[dict[str, str]],
    include_reviewed: bool,
) -> list[dict[str, str]]:
    formula_by_event = event_formula_context(events)
    release_by_event = release_context(release_rows)
    source_rows = review_rows if include_reviewed else [row for row in review_rows if is_pending(row)]

    def sort_key(row: dict[str, str]) -> tuple[float, str, str]:
        abs_residual = finite_float(row.get("abs_residual_mw"))
        sort_residual = abs_residual if math.isfinite(abs_residual) else -1.0
        return (-sort_residual, str(row.get("event_id") or ""), str(row.get("formula") or ""))

    rows: list[dict[str, str]] = []
    for index, row in enumerate(sorted(source_rows, key=sort_key), start=1):
        event_id = str(row.get("event_id") or "")
        formula_context = formula_by_event.get(event_id, {})
        release = release_by_event.get(event_id, {})
        output = {field: "" for field in TEMPLATE_FIELDS}
        output.update({field: row.get(field, "") for field in row if field in output})
        output["review_priority"] = str(index)
        output["review_status"] = normalized_status(row.get("review_status"))
        output["release_status"] = release.get("release_status", "")
        output["release_failure_reasons"] = release.get("release_failure_reasons", "")
        output["release_review_reasons"] = release.get("release_review_reasons", "")
        output["best_formula_for_event"] = str(formula_context.get("best_formula_for_event") or "")
        output["best_formula_abs_residual_mw"] = str(formula_context.get("best_formula_abs_residual_mw") or "")
        output["formula_residuals_for_event"] = str(formula_context.get("formula_residuals_for_event") or "")
        output["suggested_checks"] = suggested_checks(row, formula_context, release)
        rows.append(output)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_markdown(path: Path, rows: list[dict[str, str]], args: argparse.Namespace) -> None:
    lines = [
        "# Residual Review Guide",
        "",
        f"- Template rows: {len(rows)}",
        f"- Review CSV: `{args.review_csv}`",
        f"- Events CSV: `{args.events_csv}`",
        f"- Release set CSV: `{args.release_set_csv}`",
        "",
        "## Allowed Review Statuses",
        "",
        ", ".join(f"`{status}`" for status in ALLOWED_REVIEW_STATUSES),
        "",
        "## Suggested Cause Labels",
        "",
        "`waveform`, `station_geometry`, `magnitude_metadata`, `formula_limitation`, `data_quality`, `other`",
        "",
        "## Review Queue",
        "",
        *markdown_table(
            rows,
            [
                "review_priority",
                "event_id",
                "formula",
                "review_status",
                "abs_residual_mw",
                "pgd_reliability",
                "usable_station_count",
                "release_status",
                "best_formula_for_event",
                "suggested_checks",
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> list[dict[str, str]]:
    review_rows = read_csv(args.review_csv)
    event_rows = read_csv(args.events_csv)
    release_rows = read_csv(args.release_set_csv)
    rows = build_template_rows(review_rows, event_rows, release_rows, args.include_reviewed)
    write_csv(args.out_csv, rows)
    write_markdown(args.out_md, rows, args)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = run(args)
    print(json.dumps({"status": "OK", "template_rows": len(rows), "out_csv": str(args.out_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
