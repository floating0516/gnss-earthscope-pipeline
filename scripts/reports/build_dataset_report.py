#!/usr/bin/env python3
"""Build a human and machine-readable report from normalized GNSS packages."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SUMMARIES_DIR = ROOT / "scripts" / "summaries"
if str(SUMMARIES_DIR) not in sys.path:
    sys.path.insert(0, str(SUMMARIES_DIR))

import build_current_normalized_inventory as inventory


EVENT_FIELDS = inventory.OUTPUT_FIELDS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--figure-root", type=Path, required=True, help="Root containing generated figures.")
    parser.add_argument("--out-md", type=Path, required=True, help="Markdown report path.")
    parser.add_argument("--out-csv", type=Path, required=True, help="Per-event CSV report path.")
    parser.add_argument("--out-json", type=Path, required=True, help="Machine-readable JSON report path.")
    return parser.parse_args(argv)


def int_value(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def float_value(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def magnitude_bin(value: object) -> str:
    magnitude = float_value(value)
    if magnitude is None:
        return "unknown"
    if magnitude < 6.0:
        return "<6.0"
    if magnitude < 7.0:
        return "6.0-6.9"
    if magnitude < 8.0:
        return "7.0-7.9"
    return "8.0+"


def station_count_bin(value: object) -> str:
    count = int_value(value)
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 3:
        return "2-3"
    if count <= 7:
        return "4-7"
    return "8+"


def waveform_row_bin(value: object) -> str:
    count = int_value(value)
    if count <= 0:
        return "0"
    if count < 1_000:
        return "1-999"
    if count < 1_000_000:
        return "1k-999k"
    return "1M+"


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def count_by(rows: list[dict[str, str]], field: str, default: str = "unknown") -> dict[str, int]:
    return sorted_counter(Counter((row.get(field) or default).strip() or default for row in rows))


def top_station_count_events(rows: list[dict[str, str]], limit: int = 10) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (-int_value(row.get("station_count")), row.get("event_time", ""), row.get("event_id", "")),
    )
    result: list[dict[str, Any]] = []
    for row in ordered[:limit]:
        result.append(
            {
                "event_id": row.get("event_id", ""),
                "source": row.get("source", ""),
                "event_time": row.get("event_time", ""),
                "magnitude": row.get("magnitude", ""),
                "region": row.get("region", ""),
                "station_count": int_value(row.get("station_count")),
                "waveform_rows": int_value(row.get("waveform_rows")),
                "event_grade": row.get("event_grade", ""),
                "has_figure": row.get("has_figure", ""),
            }
        )
    return result


def missing_figure_events(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": row.get("event_id", ""),
            "source": row.get("source", ""),
            "event_time": row.get("event_time", ""),
            "magnitude": row.get("magnitude", ""),
            "region": row.get("region", ""),
            "station_count": int_value(row.get("station_count")),
            "event_grade": row.get("event_grade", ""),
            "package_path": row.get("package_path", ""),
        }
        for row in rows
        if row.get("has_figure") != "yes"
    ]


def summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    station_distribution = Counter(station_count_bin(row.get("station_count")) for row in rows)
    waveform_distribution = Counter(waveform_row_bin(row.get("waveform_rows")) for row in rows)
    magnitude_distribution = Counter(magnitude_bin(row.get("magnitude")) for row in rows)
    figure_count = sum(1 for row in rows if row.get("has_figure") == "yes")
    return {
        "total_events": len(rows),
        "events_with_figures": figure_count,
        "events_missing_figures": len(rows) - figure_count,
        "events_by_source": count_by(rows, "source"),
        "events_by_region": count_by(rows, "region"),
        "events_by_magnitude_bin": sorted_counter(magnitude_distribution),
        "station_count_distribution": sorted_counter(station_distribution),
        "waveform_row_distribution": sorted_counter(waveform_distribution),
        "quality_status_distribution": count_by(rows, "quality_status"),
        "event_grade_distribution": count_by(rows, "event_grade"),
    }


def build_report(export_root: Path, figure_root: Path) -> dict[str, Any]:
    rows = inventory.build_inventory_rows(export_root, figure_root)
    return {
        "summary": summary(rows),
        "top_station_count_events": top_station_count_events(rows),
        "missing_figure_events": missing_figure_events(rows),
        "events": rows,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in EVENT_FIELDS})


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def markdown_counter_table(title: str, values: dict[str, int]) -> list[str]:
    lines = [f"## {title}", "", "| Value | Events |", "|---|---:|"]
    if not values:
        lines.append("| none | 0 |")
    else:
        for key, count in values.items():
            lines.append(f"| {markdown_escape(key)} | {count} |")
    lines.append("")
    return lines


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary_payload = report["summary"]
    lines = [
        "# Normalized Dataset Report",
        "",
        f"- Total events: {summary_payload['total_events']}",
        f"- Events with figures: {summary_payload['events_with_figures']}",
        f"- Events missing figures: {summary_payload['events_missing_figures']}",
        "",
    ]
    lines.extend(markdown_counter_table("Events By Source", summary_payload["events_by_source"]))
    lines.extend(markdown_counter_table("Events By Region", summary_payload["events_by_region"]))
    lines.extend(markdown_counter_table("Events By Magnitude Bin", summary_payload["events_by_magnitude_bin"]))
    lines.extend(markdown_counter_table("Station Count Distribution", summary_payload["station_count_distribution"]))
    lines.extend(markdown_counter_table("Quality Status Distribution", summary_payload["quality_status_distribution"]))
    lines.extend(markdown_counter_table("Event Grade Distribution", summary_payload["event_grade_distribution"]))

    lines.extend(
        [
            "## Top Station-count Events",
            "",
            "| event_id | source | magnitude | region | stations | grade | figure |",
            "|---|---|---:|---|---:|---|---|",
        ]
    )
    for row in report["top_station_count_events"]:
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(row.get(field, ""))
                for field in ["event_id", "source", "magnitude", "region", "station_count", "event_grade", "has_figure"]
            )
            + " |"
        )
    lines.append("")

    lines.extend(
        [
            "## Missing Figure Events",
            "",
            "| event_id | source | magnitude | region | stations | grade |",
            "|---|---|---:|---|---:|---|",
        ]
    )
    missing = report["missing_figure_events"]
    if not missing:
        lines.append("| none |  |  |  |  |  |")
    else:
        for row in missing:
            lines.append(
                "| "
                + " | ".join(
                    markdown_escape(row.get(field, ""))
                    for field in ["event_id", "source", "magnitude", "region", "station_count", "event_grade"]
                )
                + " |"
            )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(report: dict[str, Any], out_md: Path, out_csv: Path, out_json: Path) -> None:
    write_csv(out_csv, report["events"])
    write_json(out_json, report)
    write_markdown(out_md, report)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.export_root, args.figure_root)
    write_outputs(report, args.out_md, args.out_csv, args.out_json)
    print(f"wrote dataset report: events={report['summary']['total_events']} md={args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
