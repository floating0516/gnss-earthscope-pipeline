#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch workflow summaries after late workflow stages.")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--summary-tsv", type=Path)
    parser.add_argument("--summary-md", type=Path)
    parser.add_argument("--plot-status")
    parser.add_argument("--plot-files", type=Path)
    parser.add_argument("--extract-plot-files-from-log", type=Path)
    parser.add_argument("--write-plot-files", type=Path)
    return parser.parse_args(argv)


def read_plot_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_plot_files_from_log(path: Path) -> list[str]:
    if not path.exists():
        return []

    result = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = raw.strip()
        if text.endswith(".png") and (text.startswith("/") or text.startswith("figure/") or "/figure/" in text):
            result.append(text)
    return result


def update_json(path: Path, plot_status: str, plot_files: list[str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("status", {})["plot"] = plot_status
    payload.setdefault("counts", {})["plot_files"] = len(plot_files)
    payload.setdefault("files", {})["plots"] = plot_files
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_tsv(path: Path, plot_status: str, plot_count: int) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))

    seen = set()
    for row in rows:
        if len(row) < 2:
            continue
        if row[0] == "plot_status":
            row[1] = plot_status
            seen.add("plot_status")
        elif row[0] == "plot_file_count":
            row[1] = str(plot_count)
            seen.add("plot_file_count")

    if "plot_status" not in seen:
        rows.append(["plot_status", plot_status])
    if "plot_file_count" not in seen:
        rows.append(["plot_file_count", str(plot_count)])

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def update_markdown(path: Path, plot_status: str, plot_count: int) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    status_line = f"- Plot status: `{plot_status}`"
    count_line = f"- Plot files: `{plot_count}`"
    status_done = False
    count_done = False

    for index, line in enumerate(lines):
        if line.startswith("- Plot status:"):
            lines[index] = status_line
            status_done = True
        elif line.startswith("- Plot files:"):
            lines[index] = count_line
            count_done = True

    if not status_done:
        lines.append(status_line)
    if not count_done:
        lines.append(count_line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plot_manifest_from_log(log_path: Path, out_path: Path) -> None:
    plots = extract_plot_files_from_log(log_path)
    out_path.write_text("\n".join(plots) + ("\n" if plots else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.extract_plot_files_from_log or args.write_plot_files:
        if not args.extract_plot_files_from_log or not args.write_plot_files:
            raise SystemExit("--extract-plot-files-from-log and --write-plot-files must be used together")
        write_plot_manifest_from_log(args.extract_plot_files_from_log, args.write_plot_files)
        return 0

    required = {
        "--summary-json": args.summary_json,
        "--summary-tsv": args.summary_tsv,
        "--summary-md": args.summary_md,
        "--plot-status": args.plot_status,
        "--plot-files": args.plot_files,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("Missing required arguments for summary update: " + ", ".join(missing))

    plot_files = read_plot_files(args.plot_files)
    update_json(args.summary_json, args.plot_status, plot_files)
    update_tsv(args.summary_tsv, args.plot_status, len(plot_files))
    update_markdown(args.summary_md, args.plot_status, len(plot_files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
