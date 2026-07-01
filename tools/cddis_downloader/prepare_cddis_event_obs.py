#!/usr/bin/env python3
"""Prepare downloaded CDDIS event RINEX files for PRIDE processing."""

from __future__ import annotations

import argparse
import csv
import gzip
import re
import shutil
import subprocess
import sys
from pathlib import Path

from cddis_common import station_ids_from_filename, write_json, write_tsv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENT_ROOT = ROOT / "data" / "cddis_highrate" / "events"

PREPARE_FIELDS = [
    "event_id",
    "station4",
    "filename",
    "source_file",
    "prepared_file",
    "status",
    "interval_seconds",
    "size_bytes",
    "reason",
]

OBS_FIELDS = [
    "event_id",
    "station4",
    "input_count",
    "prepared_files",
    "obs_file",
    "status",
    "reason",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--event-dir", help="CDDIS event directory; default data/cddis_highrate/events/<event-id>")
    parser.add_argument("--downloaded-tsv", help="Downloaded manifest; default <event-dir>/manifests/cddis-event-downloaded.tsv")
    parser.add_argument("--prepared-dir", help="Prepared working directory; default <event-dir>/prepared")
    parser.add_argument("--obs-dir", help="Prepared observation directory; default <event-dir>/obs")
    parser.add_argument(
        "--merge-method",
        choices=["auto", "gfzrnx", "python"],
        default="auto",
        help="Merge multiple prepared RINEX files with gfzrnx when available, or Python fallback.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def read_downloaded_rows(path: Path, event_id: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return [row for row in rows if not row.get("event_id") or row.get("event_id") == event_id]


def split_rinex_header(path: Path) -> tuple[list[str], list[str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines):
        if "END OF HEADER" in line:
            return lines[: index + 1], lines[index + 1 :]
    raise ValueError(f"RINEX file has no END OF HEADER: {path}")


def rinex_interval_seconds(path: Path) -> float | None:
    header, _ = split_rinex_header(path)
    for line in header:
        if "INTERVAL" not in line:
            continue
        try:
            return float(line[:20].strip())
        except ValueError:
            return None
    return None


def rinex_one_second_status(path: Path) -> bool | None:
    interval = rinex_interval_seconds(path)
    if interval is not None:
        return abs(interval - 1.0) < 0.001
    if "_01S_" in path.name.upper():
        return True
    return None


def decompress_archive(path: Path, *, overwrite: bool = False) -> Path:
    suffix = path.suffix.lower()
    if suffix not in {".gz", ".z"}:
        return path

    target = path.with_suffix("")
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return target

    if suffix == ".gz":
        with gzip.open(path, "rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return target

    gunzip = shutil.which("gunzip")
    if gunzip is None:
        raise FileNotFoundError("gunzip not found in PATH for .Z decompression")
    with target.open("wb") as handle:
        try:
            subprocess.run([gunzip, "-c", str(path)], stdout=handle, stderr=subprocess.PIPE, text=False, check=True)
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return target


def hatanaka_target(path: Path) -> Path:
    lower = path.name.lower()
    if lower.endswith(".crx"):
        return path.with_suffix(".rnx")
    return path.with_name(path.name[:-1] + "o")


def convert_hatanaka(path: Path, *, overwrite: bool = False) -> Path:
    lower = path.name.lower()
    if not (lower.endswith(".crx") or re.search(r"\.\d{2}d$", lower)):
        return path

    target = hatanaka_target(path)
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return target

    converter = shutil.which("CRX2RNX") or shutil.which("crx2rnx")
    if converter is None:
        raise FileNotFoundError("CRX2RNX/crx2rnx not found in PATH")
    subprocess.run([converter, str(path)], check=True, cwd=str(path.parent))
    if not target.exists():
        candidates = sorted(path.parent.glob(path.stem + "*.rnx")) + sorted(path.parent.glob(path.stem[:-1] + "*.o"))
        if not candidates:
            raise FileNotFoundError(f"Converted RINEX not found for {path}")
        target = candidates[0]
    return target


def prepare_rinex_file(path: Path, prepared_dir: Path, *, overwrite: bool = False) -> Path:
    prepared_dir.mkdir(parents=True, exist_ok=True)
    work = prepared_dir / path.name
    if overwrite or not work.exists() or work.stat().st_size == 0:
        shutil.copy2(path, work)
    work = decompress_archive(work, overwrite=overwrite)
    work = convert_hatanaka(work, overwrite=overwrite)
    split_rinex_header(work)
    return work


def combine_rinex_files(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("No RINEX inputs to combine.")
    output.parent.mkdir(parents=True, exist_ok=True)
    first_header, first_body = split_rinex_header(inputs[0])
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for line in first_header:
            handle.write(line.rstrip("\n") + "\n")
        for line in first_body:
            handle.write(line.rstrip("\n") + "\n")
        for path in inputs[1:]:
            _, body = split_rinex_header(path)
            for line in body:
                handle.write(line.rstrip("\n") + "\n")


def splice_rinex_with_gfzrnx(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("No RINEX inputs to splice.")
    gfzrnx = shutil.which("gfzrnx")
    if gfzrnx is None:
        raise FileNotFoundError("gfzrnx not found in PATH")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([gfzrnx, "-finp", *[str(path) for path in inputs], "-fout", str(output), "-kv", "-try_append", "900"], check=True)


def merge_rinex_files(inputs: list[Path], output: Path, method: str = "auto") -> str:
    if method not in {"auto", "gfzrnx", "python"}:
        raise ValueError(f"Unknown merge method: {method}")
    if method in {"auto", "gfzrnx"} and shutil.which("gfzrnx"):
        splice_rinex_with_gfzrnx(inputs, output)
        return "gfzrnx"
    if method == "gfzrnx":
        raise FileNotFoundError("gfzrnx requested but not found in PATH")
    combine_rinex_files(inputs, output)
    return "python"


def safe_event_token(event_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", event_id).strip("_") or "event"


def station_from_row(row: dict[str, str]) -> str:
    station = str(row.get("station4") or "").strip().upper()[:4]
    if station:
        return station
    station4, _ = station_ids_from_filename(str(row.get("filename") or ""))
    return station4


def prepare_row(
    row: dict[str, str],
    *,
    event_id: str,
    prepared_dir: Path,
    dry_run: bool,
    overwrite: bool,
) -> tuple[dict[str, str], Path | None]:
    station = station_from_row(row)
    source = Path(str(row.get("local_file") or "")).expanduser()
    filename = str(row.get("filename") or source.name)
    output: Path | None = None
    interval = ""
    status = "DRY_RUN" if dry_run else "OK"
    reason = ""

    if not source.exists() or source.stat().st_size == 0:
        status = "MISSING"
        download_status = str(row.get("status") or "")
        reason = f"download status={download_status}" if download_status and download_status != "OK" else "local file missing"
    elif not dry_run:
        try:
            output = prepare_rinex_file(source, prepared_dir / station.lower(), overwrite=overwrite)
            parsed_interval = rinex_interval_seconds(output)
            interval = "" if parsed_interval is None else f"{parsed_interval:g}"
            one_second = rinex_one_second_status(output)
            if one_second is False:
                status = "INVALID"
                reason = f"RINEX INTERVAL is {interval} seconds"
                output = None
            elif one_second is None:
                reason = "RINEX INTERVAL not declared"
        except Exception as exc:  # noqa: BLE001
            status = "FAIL"
            reason = str(exc)
            output = None

    return (
        {
            "event_id": event_id,
            "station4": station,
            "filename": filename,
            "source_file": str(source),
            "prepared_file": "" if output is None else str(output),
            "status": status,
            "interval_seconds": interval,
            "size_bytes": "" if output is None or not output.exists() else str(output.stat().st_size),
            "reason": reason,
        },
        output,
    )


def write_obs_row(
    event_id: str,
    station: str,
    paths: list[Path],
    *,
    obs_dir: Path,
    merge_method: str,
    dry_run: bool,
    overwrite: bool,
) -> dict[str, str]:
    paths = sorted(paths)
    obs_file = obs_dir / f"{station.lower()}_{safe_event_token(event_id)}_cddis.rnx"
    status = "DRY_RUN" if dry_run else "OK"
    reason = ""
    if dry_run:
        pass
    elif not paths:
        status = "MISSING"
        reason = "no prepared 1Hz RINEX files"
    else:
        try:
            obs_dir.mkdir(parents=True, exist_ok=True)
            if len(paths) == 1:
                if overwrite or not obs_file.exists() or obs_file.stat().st_size == 0:
                    shutil.copy2(paths[0], obs_file)
                reason = "copy"
            else:
                if overwrite or not obs_file.exists() or obs_file.stat().st_size == 0:
                    method = merge_rinex_files(paths, obs_file, method=merge_method)
                else:
                    method = "existing"
                reason = f"merge_method={method}"
        except Exception as exc:  # noqa: BLE001
            status = "FAIL"
            reason = str(exc)
            obs_file = Path("")

    return {
        "event_id": event_id,
        "station4": station,
        "input_count": str(len(paths)),
        "prepared_files": " ".join(str(path) for path in paths),
        "obs_file": "" if status in {"MISSING", "FAIL"} else str(obs_file),
        "status": status,
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    event_dir = Path(args.event_dir).expanduser() if args.event_dir else DEFAULT_EVENT_ROOT / args.event_id
    downloaded_tsv = Path(args.downloaded_tsv).expanduser() if args.downloaded_tsv else event_dir / "manifests" / "cddis-event-downloaded.tsv"
    prepared_dir = Path(args.prepared_dir).expanduser() if args.prepared_dir else event_dir / "prepared"
    obs_dir = Path(args.obs_dir).expanduser() if args.obs_dir else event_dir / "obs"
    manifests_dir = event_dir / "manifests"
    prepared_tsv = manifests_dir / "cddis-event-prepared.tsv"
    obs_tsv = manifests_dir / "cddis-event-obs.tsv"
    summary_json = manifests_dir / "cddis-prepare-summary.json"

    downloaded_rows = read_downloaded_rows(downloaded_tsv, args.event_id)
    prepared_rows: list[dict[str, str]] = []
    station_inputs: dict[str, list[Path]] = {}
    for row in downloaded_rows:
        manifest_row, prepared = prepare_row(
            row,
            event_id=args.event_id,
            prepared_dir=prepared_dir,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        prepared_rows.append(manifest_row)
        if prepared is not None and manifest_row["status"] == "OK":
            station_inputs.setdefault(manifest_row["station4"], []).append(prepared)

    stations = sorted({station_from_row(row) for row in downloaded_rows if station_from_row(row)} | set(station_inputs))
    obs_rows = [
        write_obs_row(
            args.event_id,
            station,
            station_inputs.get(station, []),
            obs_dir=obs_dir,
            merge_method=args.merge_method,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        for station in stations
    ]

    write_tsv(prepared_tsv, prepared_rows, PREPARE_FIELDS)
    write_tsv(obs_tsv, obs_rows, OBS_FIELDS)

    status_counts: dict[str, int] = {}
    for row in prepared_rows + obs_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    prepared_ok = sum(1 for row in prepared_rows if row["status"] == "OK")
    obs_ok = sum(1 for row in obs_rows if row["status"] == "OK")
    failed = sum(1 for row in prepared_rows + obs_rows if row["status"] in {"FAIL", "MISSING", "INVALID"})
    summary = {
        "provider": "CDDIS",
        "event_id": args.event_id,
        "downloaded_file_count": len(downloaded_rows),
        "prepared_count": prepared_ok,
        "obs_count": obs_ok,
        "failed_count": failed,
        "dry_run": args.dry_run,
        "event_dir": str(event_dir),
        "downloaded_tsv": str(downloaded_tsv),
        "prepared_dir": str(prepared_dir),
        "obs_dir": str(obs_dir),
        "prepared_tsv": str(prepared_tsv),
        "obs_tsv": str(obs_tsv),
        "summary_json": str(summary_json),
        "status_counts": status_counts,
    }
    write_json(summary_json, summary)

    print(f"CDDIS prepare: {args.event_id}", file=sys.stderr)
    print(f"Downloaded rows: {len(downloaded_rows)}; prepared: {prepared_ok}; obs: {obs_ok}; failed: {failed}", file=sys.stderr)
    if args.dry_run:
        return 0 if downloaded_rows else 1
    return 1 if failed or obs_ok == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
