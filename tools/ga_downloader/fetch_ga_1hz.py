#!/usr/bin/env python3
"""Download and combine Geoscience Australia 15-minute 1 Hz RINEX files for an event window."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import shutil
import sys
from pathlib import Path

from ga_common import (
    GA_RINEX_API_URL,
    event_current_slot_window,
    event_day_window,
    event_three_slot_window,
    fetch_bytes,
    iso_utc,
    iter_required_slots,
    list_ga_files,
    merge_rinex_files,
    normalize_doy,
    prepare_rinex_file,
    read_station_file,
    rinex_interval_is_one_second,
    unique_stations,
    write_json,
    parse_utc,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--year", type=int, help="Observation year, default from event time")
    parser.add_argument("--doy", help="Observation day-of-year, default from event time")
    parser.add_argument("--hours", type=float, default=3.0)
    parser.add_argument(
        "--slot-window",
        choices=["event-15min", "event-45min", "hours"],
        default="event-15min",
        help="Select GA 15-minute slots: current event slot, previous/current/next around event time, or legacy --hours window.",
    )
    parser.add_argument("--stations", default="", help="Station codes separated by comma/space")
    parser.add_argument("--stations-file")
    parser.add_argument("--out-dir", required=True, help="Raw GA download directory")
    parser.add_argument("--obs-root", default="data/obs")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--keep-partial", action="store_true")
    parser.add_argument("--ga-api-url", default=GA_RINEX_API_URL)
    parser.add_argument(
        "--merge-method",
        choices=["auto", "gfzrnx", "python"],
        default="auto",
        help="Combine 15-minute RINEX files with gfzrnx when available, or Python fallback. Default: auto.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("station_args", nargs="*")
    return parser.parse_args()


def parse_station_args(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.stations:
        values.extend(args.stations.replace(",", " ").split())
    if args.stations_file:
        values.extend(read_station_file(Path(args.stations_file)))
    values.extend(args.station_args)
    return unique_stations(values)


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(fetch_bytes(url, timeout=180, retries=3))
    tmp.replace(target)


def main() -> int:
    args = parse_args()
    stations = parse_station_args(args)
    if not stations:
        raise SystemExit("At least one GA station is required.")

    event_time = parse_utc(args.event_time)
    year = args.year or event_time.year
    doy = normalize_doy(args.doy or event_time.strftime("%j"))
    if args.slot_window == "event-15min":
        start, end, slots = event_current_slot_window(event_time)
    elif args.slot_window == "event-45min":
        start, end, slots = event_three_slot_window(event_time)
    else:
        start, end = event_day_window(event_time, args.hours)
        slots = iter_required_slots(start, end)
    if year != event_time.year or doy != int(event_time.strftime("%j")):
        day_start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1)
        start = day_start
        end = day_start.replace(hour=23, minute=59, second=59)
        slots = iter_required_slots(start, end)

    if args.slot_window == "event-15min":
        slot_roles = {slots[0]: (0, "current")} if slots else {}
    elif args.slot_window == "event-45min":
        slot_roles = {slot: (index - 1, role) for index, (slot, role) in enumerate(zip(slots, ["previous", "current", "next"]))}
    else:
        slot_roles = {slot: (index, "window") for index, slot in enumerate(slots)}
    out_dir = Path(args.out_dir)
    files_dir = out_dir / "files"
    prepared_dir = out_dir / "prepared"
    combined_dir = out_dir / "combined"
    obs_dir = Path(args.obs_root) / args.event_id

    print(f"GA event: {args.event_id}", file=sys.stderr)
    print(f"Event time UTC: {iso_utc(event_time)}", file=sys.stderr)
    print(f"Observation day: {year}/{doy:03d}", file=sys.stderr)
    print(f"Window UTC: {iso_utc(start)} -> {iso_utc(end)}", file=sys.stderr)
    print(f"Stations: {len(stations)}", file=sys.stderr)
    print(f"15-minute slots: {len(slots)}", file=sys.stderr)

    available_files = list_ga_files(stations, start, end, api_url=args.ga_api_url)
    available = {(item.station, item.start_time): item for item in available_files}

    requested_rows: list[dict[str, str]] = []
    downloaded_rows: list[dict[str, str]] = []
    combined_rows: list[dict[str, str]] = []
    station_inputs: dict[str, list[Path]] = {station: [] for station in sorted(stations)}

    for station in sorted(stations):
        for slot in slots:
            item = available.get((station, slot))
            slot_index, slot_role = slot_roles.get((slot), (slots.index(slot), "window"))
            requested_rows.append(
                {
                    "station": station,
                    "slot_index": str(slot_index),
                    "slot_role": slot_role,
                    "slot_start_utc": iso_utc(slot),
                    "slot_end_utc": iso_utc(slot + dt.timedelta(minutes=15)),
                    "status": "FOUND" if item else "MISSING",
                    "filename": "" if item is None else item.filename,
                    "url": "" if item is None else item.url,
                }
            )
            if item is None:
                continue
            target = files_dir / item.filename
            status = "DRY_RUN"
            reason = ""
            if not args.dry_run:
                try:
                    if not target.exists() or target.stat().st_size == 0:
                        download_file(item.url, target)
                    prepared = prepare_rinex_file(target, prepared_dir / station.lower())
                    if rinex_interval_is_one_second(prepared):
                        station_inputs[station].append(prepared)
                        status = "OK"
                    else:
                        status = "INVALID"
                        reason = "RINEX INTERVAL is not 1 second"
                except Exception as exc:  # noqa: BLE001
                    status = "FAIL"
                    reason = str(exc)
            downloaded_rows.append(
                {
                    "station": station,
                    "filename": item.filename,
                    "url": item.url,
                    "local_file": str(target),
                    "size_bytes": "" if args.dry_run or not target.exists() else str(target.stat().st_size),
                    "status": status,
                    "reason": reason,
                }
            )

    if not args.dry_run:
        obs_dir.mkdir(parents=True, exist_ok=True)
        for station, paths in sorted(station_inputs.items()):
            paths = sorted(paths)
            if not paths:
                combined_rows.append(
                    {
                        "station": station,
                        "input_count": "0",
                        "combined_file": "",
                        "obs_file": "",
                        "status": "MISSING",
                        "reason": "no downloaded 1Hz RINEX files",
                    }
                )
                continue
            if len(paths) < len(slots) and not args.keep_partial:
                combined_rows.append(
                    {
                        "station": station,
                        "input_count": str(len(paths)),
                        "combined_file": "",
                        "obs_file": "",
                        "status": "PARTIAL",
                        "reason": f"only {len(paths)} of {len(slots)} requested slots",
                    }
                )
                continue
            combined_file = combined_dir / f"{station.lower()}_{year}{doy:03d}_1hz.rnx"
            obs_file = obs_dir / combined_file.name
            try:
                merge_method_used = merge_rinex_files(paths, combined_file, method=args.merge_method)
                shutil.copy2(combined_file, obs_file)
                status = "OK"
                reason = f"merge_method={merge_method_used}"
            except Exception as exc:  # noqa: BLE001
                status = "FAIL"
                reason = str(exc)
                obs_file = Path("")
            combined_rows.append(
                {
                    "station": station,
                    "input_count": str(len(paths)),
                    "combined_file": str(combined_file),
                    "obs_file": "" if not str(obs_file) else str(obs_file),
                    "status": status,
                    "reason": reason,
                }
            )

    write_tsv(
        out_dir / "ga-requested-files.tsv",
        requested_rows,
        ["station", "slot_index", "slot_role", "slot_start_utc", "slot_end_utc", "status", "filename", "url"],
    )
    write_tsv(
        out_dir / "ga-downloaded-files.tsv",
        downloaded_rows,
        ["station", "filename", "url", "local_file", "size_bytes", "status", "reason"],
    )
    write_tsv(
        out_dir / "ga-combined-files.tsv",
        combined_rows,
        ["station", "input_count", "combined_file", "obs_file", "status", "reason"],
    )
    write_json(
        out_dir / "ga-download-summary.json",
        {
            "source": "Geoscience Australia",
            "event_id": args.event_id,
            "event_time_utc": iso_utc(event_time),
            "year": year,
            "doy": doy,
            "window_start_utc": iso_utc(start),
            "window_end_utc": iso_utc(end),
            "download_window_mode": {"event-15min": "event_15min_current", "event-45min": "event_45min_previous_current_next"}.get(args.slot_window, "hours"),
            "slot_anchor_utc": iso_utc(slots[1] if args.slot_window == "event-45min" and len(slots) == 3 else slots[0]) if slots else "",
            "requested_slot_start_utc": iso_utc(start),
            "requested_slot_end_utc": iso_utc(end),
            "slot_duration_minutes": 15,
            "required_slot_count": len(slots),
            "required_slots_utc": [iso_utc(slot) for slot in slots],
            "pride_event_time_utc": iso_utc(event_time),
            "requested_station_count": len(stations),
            "slot_count": len(slots),
            "requested_file_count": len(requested_rows),
            "found_file_count": sum(1 for row in requested_rows if row["status"] == "FOUND"),
            "downloaded_file_count": sum(1 for row in downloaded_rows if row["status"] == "OK"),
            "combined_file_count": sum(1 for row in combined_rows if row["status"] == "OK"),
            "obs_file_count": sum(1 for row in combined_rows if row["status"] == "OK"),
            "missing_station_count": sum(1 for row in combined_rows if row["status"] in {"MISSING", "PARTIAL"}),
            "failed_station_count": sum(1 for row in combined_rows if row["status"] == "FAIL"),
            "obs_dir": str(obs_dir),
            "out_dir": str(out_dir),
        },
    )

    ok_count = sum(1 for row in combined_rows if row["status"] == "OK")
    if args.dry_run:
        print("Dry run complete.")
        return 0
    if ok_count == len(stations):
        print(f"GA download OK: {ok_count}/{len(stations)} stations")
        return 0
    if ok_count > 0 and args.allow_missing:
        print(f"GA download partial: {ok_count}/{len(stations)} stations", file=sys.stderr)
        return 0
    print(f"GA download failed: {ok_count}/{len(stations)} stations", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
