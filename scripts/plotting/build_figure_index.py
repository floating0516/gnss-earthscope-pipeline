#!/usr/bin/env python3
"""Build an index of generated figure files and their normalized events."""

from __future__ import annotations

import argparse
import datetime as dt
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

import build_current_normalized_inventory as inventory


INDEX_FILENAMES = {"index.json", "index.md"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--figure-root", type=Path, required=True, help="Figure root to scan.")
    parser.add_argument("--out-json", type=Path, default=Path("figure/index.json"))
    parser.add_argument("--out-md", type=Path, default=Path("figure/index.md"))
    return parser.parse_args(argv)


def figure_files(figure_root: Path) -> list[Path]:
    if not figure_root.exists():
        return []
    return sorted(
        path
        for path in figure_root.rglob("*")
        if path.is_file() and not path.name.startswith(".") and path.name not in INDEX_FILENAMES
    )


def figure_type(path: Path) -> str:
    text = " ".join([*path.parts, path.stem]).lower().replace("-", "_")
    if "record_section" in text or ("record" in text and "section" in text):
        return "record_section"
    if "station_map" in text or ("station" in text and "map" in text):
        return "station_map"
    if "world_map" in text or ("world" in text and "map" in text):
        return "world_map"
    if "pgd" in text or "residual" in text or "magnitude" in text:
        return "pgd"
    return "unknown"


def created_at(path: Path) -> str:
    timestamp = path.stat().st_mtime
    return dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def event_lookup(export_root: Path, figure_root: Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in inventory.build_inventory_rows(export_root, figure_root):
        for figure_path in [item for item in row.get("figure_paths", "").split(";") if item]:
            lookup.setdefault(figure_path, row)
    return lookup


def build_index(export_root: Path, figure_root: Path) -> list[dict[str, str]]:
    export_root = export_root.expanduser()
    figure_root = figure_root.expanduser()
    lookup = event_lookup(export_root, figure_root)
    rows: list[dict[str, str]] = []
    for path in figure_files(figure_root):
        relative = str(path.relative_to(figure_root))
        event = lookup.get(relative, {})
        rows.append(
            {
                "event_id": event.get("event_id", ""),
                "figure_type": figure_type(path.relative_to(figure_root)),
                "path": relative,
                "created_at": created_at(path),
                "source": event.get("source", ""),
                "station_count": event.get("station_count", ""),
            }
        )
    return sorted(rows, key=lambda row: (row["event_id"] or "~", row["figure_type"], row["path"]))


def summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    matched = [row for row in rows if row.get("event_id")]
    by_type = Counter(row.get("figure_type") or "unknown" for row in rows)
    by_source = Counter(row.get("source") or "unknown" for row in matched)
    return {
        "total_figures": len(rows),
        "matched_figures": len(matched),
        "unmatched_figures": len(rows) - len(matched),
        "events_with_figures": len({row["event_id"] for row in matched if row.get("event_id")}),
        "figures_by_type": dict(sorted(by_type.items())),
        "matched_figures_by_source": dict(sorted(by_source.items())),
    }


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary(rows), "figures": rows}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    payload = summary(rows)
    lines = [
        "# Figure Index",
        "",
        f"- Total figures: {payload['total_figures']}",
        f"- Matched figures: {payload['matched_figures']}",
        f"- Unmatched figures: {payload['unmatched_figures']}",
        f"- Events with figures: {payload['events_with_figures']}",
        "",
        "| event_id | figure_type | source | stations | path | created_at |",
        "|---|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(row.get(field, ""))
                for field in ["event_id", "figure_type", "source", "station_count", "path", "created_at"]
            )
            + " |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_index(args.export_root, args.figure_root)
    write_json(args.out_json, rows)
    write_markdown(args.out_md, rows)
    print(f"wrote figure index: figures={len(rows)} json={args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
