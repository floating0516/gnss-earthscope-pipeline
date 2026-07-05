#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


OUTPUT_FIELDS = [
    "event_id",
    "source",
    "event_time",
    "magnitude",
    "region",
    "station_count",
    "waveform_rows",
    "quality_status",
    "event_grade",
    "azimuth_bins",
    "has_figure",
    "figure_paths",
    "package_path",
]

COMMON_PLACE_WORDS = {
    "and",
    "earthquake",
    "from",
    "near",
    "the",
    "with",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an inventory for normalized GNSS event packages.")
    parser.add_argument("--root", type=Path, required=True, help="Normalized export root")
    parser.add_argument("--figure-root", type=Path, required=True, help="Root containing generated figures")
    parser.add_argument("--out-prefix", type=Path, required=True, help="Output prefix for .tsv, .json, and .md")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def count_gzip_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def count_string(value: Any, fallback: int) -> str:
    text = stringify(value).strip()
    return text if text else str(fallback)


def first_text(*values: Any) -> str:
    for value in values:
        text = stringify(value).strip()
        if text:
            return text
    return ""


def quality_status(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    quality_summary = provenance.get("quality_summary")
    if isinstance(quality_summary, dict):
        status = first_text(quality_summary.get("status"))
        if status:
            return status
    return first_text(event.get("quality_status"), provenance.get("quality_status"))


def event_grade(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    for payload in [event.get("event_grade"), provenance.get("event_grade")]:
        if isinstance(payload, dict):
            value = first_text(payload.get("grade"))
        else:
            value = first_text(payload)
        if value:
            return value
    return ""


def azimuth_bins(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    provenance_grade = provenance.get("event_grade")
    provenance_bins = provenance_grade.get("azimuth_bins_covered") if isinstance(provenance_grade, dict) else None
    return first_text(event.get("azimuth_bins_covered"), provenance_bins)


def source_label(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    candidates = [
        event.get("network"),
        event.get("source"),
        provenance.get("source_label"),
        provenance.get("source"),
    ]
    for value in candidates:
        text = stringify(value).strip()
        lower = text.lower()
        if "geonet" in lower:
            return "GeoNet"
        if "earthscope" in lower or "gage" in lower:
            return "EarthScope"
        if "cddis" in lower:
            return "CDDIS"
        if text:
            return text
    return ""


def slug_words(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return [word for word in words if len(word) >= 4 and word not in COMMON_PLACE_WORDS]


def figure_matches(figure_name: str, event: dict[str, Any], package_dir: Path, event_id: str) -> bool:
    name = figure_name.lower()
    direct_tokens = [event_id.lower(), package_dir.name.lower()]
    if any(token and token in name for token in direct_tokens):
        return True

    event_time = first_text(event.get("date"), event.get("event_time"), event.get("origin_time"))
    date_token = re.sub(r"[^0-9]", "", event_time[:10])
    place_tokens = slug_words(first_text(event.get("place"), event.get("event"), package_dir.name))
    if date_token and date_token in name and any(token in name for token in place_tokens):
        return True
    return False


def find_figures(
    event: dict[str, Any],
    package_dir: Path,
    event_id: str,
    figure_root: Path,
    figure_files: list[Path],
) -> list[str]:
    if not figure_root.exists():
        return []
    matches = [
        str(path.relative_to(figure_root))
        for path in figure_files
        if figure_matches(path.name, event, package_dir, event_id)
    ]
    return sorted(matches)


def event_package_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and not path.name.startswith(".")
        and ((path / "event.json").exists() or (path / "provenance.json").exists())
    ]


def build_inventory_rows(root: Path, figure_root: Path) -> list[dict[str, str]]:
    root = root.expanduser()
    figure_root = figure_root.expanduser()
    figure_files = sorted(path for path in figure_root.rglob("*") if path.is_file()) if figure_root.exists() else []
    rows: list[dict[str, str]] = []

    for package_dir in event_package_dirs(root):
        event = load_json(package_dir / "event.json")
        provenance = load_json(package_dir / "provenance.json")
        stations_counted = count_csv_rows(package_dir / "stations.csv")
        waveform_counted = 0

        event_id = first_text(
            event.get("event_id"),
            event.get("usgs_event_id"),
            provenance.get("event_id"),
            package_dir.name,
        )
        waveform_metadata = first_text(provenance.get("waveform_rows"), event.get("waveform_rows"))
        if not waveform_metadata:
            waveform_counted = count_gzip_csv_rows(package_dir / "waveforms.csv.gz")

        figures = find_figures(event, package_dir, event_id, figure_root, figure_files)
        rows.append(
            {
                "event_id": event_id,
                "source": source_label(event, provenance),
                "event_time": first_text(event.get("date"), event.get("event_time"), event.get("origin_time")),
                "magnitude": first_text(event.get("magnitude"), provenance.get("magnitude")),
                "region": first_text(event.get("region"), provenance.get("region")),
                "station_count": count_string(
                    first_text(provenance.get("station_count"), event.get("station_count"), event.get("stations")),
                    stations_counted,
                ),
                "waveform_rows": count_string(waveform_metadata, waveform_counted),
                "quality_status": quality_status(event, provenance),
                "event_grade": event_grade(event, provenance),
                "azimuth_bins": azimuth_bins(event, provenance),
                "has_figure": "yes" if figures else "no",
                "figure_paths": ";".join(figures),
                "package_path": str(package_dir),
            }
        )

    return sorted(rows, key=lambda row: (row.get("event_time", ""), row.get("event_id", "")))


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def summary_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_source = Counter(row.get("source", "") or "unknown" for row in rows)
    by_quality = Counter(row.get("quality_status", "") or "unknown" for row in rows)
    by_grade = Counter(row.get("event_grade", "") or "unknown" for row in rows)
    with_figures = sum(1 for row in rows if row.get("has_figure") == "yes")
    return {
        "summary": {
            "total_events": len(rows),
            "events_with_figures": with_figures,
            "events_missing_figures": len(rows) - with_figures,
            "events_by_source": dict(sorted(by_source.items())),
            "events_by_quality_status": dict(sorted(by_quality.items())),
            "events_by_grade": dict(sorted(by_grade.items())),
        },
        "events": rows,
    }


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary_payload(rows), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|")


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    payload = summary_payload(rows)
    summary = payload["summary"]
    lines = [
        "# Current Normalized Export Inventory",
        "",
        f"- Total events: {summary['total_events']}",
        f"- Events with figures: {summary['events_with_figures']}",
        f"- Events missing figures: {summary['events_missing_figures']}",
        "",
        "| event_id | source | event_time | magnitude | stations | quality | grade | figure |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(row.get(field, ""))
                for field in [
                    "event_id",
                    "source",
                    "event_time",
                    "magnitude",
                    "station_count",
                    "quality_status",
                    "event_grade",
                    "has_figure",
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = build_inventory_rows(args.root, args.figure_root)
    write_tsv(args.out_prefix.with_suffix(".tsv"), rows)
    write_json(args.out_prefix.with_suffix(".json"), rows)
    write_markdown(args.out_prefix.with_suffix(".md"), rows)
    print(f"wrote inventory: events={len(rows)} prefix={args.out_prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
