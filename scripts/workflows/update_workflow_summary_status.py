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
    parser.add_argument("--derive-failure", action="store_true")
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


def status_value(payload: dict, key: str) -> str:
    status = payload.get("status")
    if not isinstance(status, dict):
        return ""
    return str(status.get(key) or "").strip()


def count_value(payload: dict, key: str) -> int:
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        return 0
    try:
        return int(counts.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def failure_payload(stage: str, code: str, message: str, next_action: str) -> dict[str, str]:
    return {
        "stage": stage,
        "code": code,
        "message": message,
        "next_action": next_action,
    }


def derive_failure(payload: dict) -> dict[str, str]:
    download = status_value(payload, "download")
    obs_validation = status_value(payload, "obs_validation")
    process = status_value(payload, "process")
    quality = status_value(payload, "quality")
    normalized = status_value(payload, "normalized") or status_value(payload, "normalize")
    normalized_validation = status_value(payload, "normalized_validation")
    plot = status_value(payload, "plot")
    pride_cleanup = status_value(payload, "pride_cleanup")
    obs_cleanup = status_value(payload, "obs_cleanup")
    obs_files = count_value(payload, "obs_files")
    kin_files = count_value(payload, "kin_files")

    if download == "FAIL":
        return failure_payload("download", "DOWNLOAD_FAIL", "Download failed.", "RERUN_DOWNLOAD")
    if obs_validation == "FAIL" or process == "BLOCKED_OBS_VALIDATION" or (download in {"OK", "REUSED"} and obs_files == 0):
        return failure_payload("obs_validation", "NO_OBS", "No usable observation files were validated.", "CLASSIFY_NO_OBS")
    if normalized == "SKIPPED_NO_KIN" or (process in {"OK", "FAIL"} and kin_files == 0):
        return failure_payload("process", "NO_USABLE_KIN", "No usable kin files were produced.", "CLASSIFY_NO_KIN")
    if process == "FAIL":
        return failure_payload("process", "PROCESS_FAIL", "PRIDE processing failed.", "RERUN_PROCESS")
    if quality == "FAIL" or normalized == "SKIPPED_QUALITY_FAIL":
        return failure_payload("quality", "QUALITY_FAIL", "Kin quality failed policy.", "REVIEW_QUALITY")
    if normalized == "FAIL":
        return failure_payload("normalize", "NORMALIZE_FAIL", "Normalization failed.", "RERUN_NORMALIZE")
    if normalized_validation == "FAIL":
        return failure_payload("normalize", "NORMALIZED_VALIDATION_FAIL", "Normalized package validation failed.", "RERUN_NORMALIZE")
    if pride_cleanup == "FAIL":
        return failure_payload("cleanup", "PRIDE_CLEANUP_FAIL", "PRIDE cleanup failed.", "REVIEW_CLEANUP")
    if obs_cleanup == "FAIL":
        return failure_payload("cleanup", "OBS_CLEANUP_FAIL", "Observation cleanup failed.", "REVIEW_CLEANUP")
    if plot == "FAIL":
        return failure_payload("plot", "PLOT_FAIL", "Final plotting failed.", "RERUN_PLOT")
    return failure_payload("", "", "", "DONE")


def update_failure_json(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failure = derive_failure(payload)
    result = "OK" if not failure["code"] else "FAIL"
    payload["workflow_result"] = result
    payload["stage"] = failure["stage"]
    payload["failure_code"] = failure["code"]
    payload["failure_message"] = failure["message"]
    payload["next_action"] = failure["next_action"]
    payload["failure"] = failure
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return failure | {"workflow_result": result}


def upsert_tsv(path: Path, updates: dict[str, str]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))

    seen = set()
    for row in rows:
        if len(row) < 2:
            continue
        if row[0] in updates:
            row[1] = updates[row[0]]
            seen.add(row[0])

    for key, value in updates.items():
        if key not in seen:
            rows.append([key, value])

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def update_failure_tsv(path: Path, failure: dict[str, str]) -> None:
    upsert_tsv(
        path,
        {
            "workflow_result": failure["workflow_result"],
            "failure_stage": failure["stage"],
            "failure_code": failure["code"],
            "failure_message": failure["message"],
            "next_action": failure["next_action"],
        },
    )


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


def update_failure_markdown(path: Path, failure: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    updates = {
        "- Workflow result:": f"- Workflow result: `{failure['workflow_result']}`",
        "- Failure stage:": f"- Failure stage: `{failure['stage']}`",
        "- Failure code:": f"- Failure code: `{failure['code']}`",
        "- Failure message:": f"- Failure message: `{failure['message']}`",
        "- Next action:": f"- Next action: `{failure['next_action']}`",
    }
    seen = set()
    for index, line in enumerate(lines):
        for prefix, replacement in updates.items():
            if line.startswith(prefix):
                lines[index] = replacement
                seen.add(prefix)
                break
    for prefix, replacement in updates.items():
        if prefix not in seen:
            lines.append(replacement)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_failure_summaries(summary_json: Path, summary_tsv: Path, summary_md: Path) -> None:
    failure = update_failure_json(summary_json)
    update_failure_tsv(summary_tsv, failure)
    update_failure_markdown(summary_md, failure)


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
    }
    if not args.derive_failure:
        required["--plot-status"] = args.plot_status
        required["--plot-files"] = args.plot_files
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("Missing required arguments for summary update: " + ", ".join(missing))

    if args.plot_status is not None or args.plot_files is not None:
        if args.plot_status is None or args.plot_files is None:
            raise SystemExit("--plot-status and --plot-files must be used together")
        plot_files = read_plot_files(args.plot_files)
        update_json(args.summary_json, args.plot_status, plot_files)
        update_tsv(args.summary_tsv, args.plot_status, len(plot_files))
        update_markdown(args.summary_md, args.plot_status, len(plot_files))
    if args.derive_failure:
        update_failure_summaries(args.summary_json, args.summary_tsv, args.summary_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
