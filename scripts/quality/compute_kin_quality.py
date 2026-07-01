#!/usr/bin/env python3
"""Compute quality metrics from PRIDE kin_* files."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
from pathlib import Path


MJD_UNIX_EPOCH = 40587
SECONDS_PER_DAY = 86400
GPS_UTC_OFFSETS = (
    (dt.datetime(1981, 7, 1, tzinfo=dt.timezone.utc), 1),
    (dt.datetime(1982, 7, 1, tzinfo=dt.timezone.utc), 2),
    (dt.datetime(1983, 7, 1, tzinfo=dt.timezone.utc), 3),
    (dt.datetime(1985, 7, 1, tzinfo=dt.timezone.utc), 4),
    (dt.datetime(1988, 1, 1, tzinfo=dt.timezone.utc), 5),
    (dt.datetime(1990, 1, 1, tzinfo=dt.timezone.utc), 6),
    (dt.datetime(1991, 1, 1, tzinfo=dt.timezone.utc), 7),
    (dt.datetime(1992, 7, 1, tzinfo=dt.timezone.utc), 8),
    (dt.datetime(1993, 7, 1, tzinfo=dt.timezone.utc), 9),
    (dt.datetime(1994, 7, 1, tzinfo=dt.timezone.utc), 10),
    (dt.datetime(1996, 1, 1, tzinfo=dt.timezone.utc), 11),
    (dt.datetime(1997, 7, 1, tzinfo=dt.timezone.utc), 12),
    (dt.datetime(1999, 1, 1, tzinfo=dt.timezone.utc), 13),
    (dt.datetime(2006, 1, 1, tzinfo=dt.timezone.utc), 14),
    (dt.datetime(2009, 1, 1, tzinfo=dt.timezone.utc), 15),
    (dt.datetime(2012, 7, 1, tzinfo=dt.timezone.utc), 16),
    (dt.datetime(2015, 7, 1, tzinfo=dt.timezone.utc), 17),
    (dt.datetime(2017, 1, 1, tzinfo=dt.timezone.utc), 18),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-time", required=True, help="UTC event time, e.g. 2021-10-11T09:10:25Z")
    parser.add_argument("--expected-hours-each-side", type=float, default=0.0)
    parser.add_argument(
        "--expected-seconds",
        type=float,
        default=0.0,
        help="Expected processed window length in seconds. Overrides --expected-hours-each-side when positive.",
    )
    parser.add_argument("--out-tsv", help="Write per-station quality table.")
    parser.add_argument("--out-json", help="Write JSON quality summary.")
    parser.add_argument("--min-epochs", type=int, default=60)
    parser.add_argument("--min-coverage-ratio", type=float, default=0.80)
    parser.add_argument(
        "--min-station-health-ratio",
        type=float,
        default=0.80,
        help="Event-level WARN threshold: warn only when OK stations / processed stations is below this ratio.",
    )
    parser.add_argument("--max-pre-rms-cm", type=float, default=10.0)
    parser.add_argument("--max-epoch-jump-cm", type=float, default=50.0)
    parser.add_argument("--event-step-window", type=float, default=30.0, help="Seconds before/after event for step median.")
    parser.add_argument(
        "--allow-partial-failures",
        action="store_true",
        help="Report WARN instead of FAIL when at least one station is usable and only some stations fail.",
    )
    parser.add_argument("kin_files", nargs="*", help="PRIDE kin_* files")
    return parser.parse_args()


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def mjd_sod_to_gpst(mjd: int, sod: float) -> dt.datetime:
    seconds = (mjd - MJD_UNIX_EPOCH) * SECONDS_PER_DAY + sod
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)


def gps_utc_offset_seconds(gpst: dt.datetime) -> int:
    gpst = gpst.astimezone(dt.timezone.utc)
    offset = 0
    for effective_utc, value in GPS_UTC_OFFSETS:
        if gpst >= effective_utc + dt.timedelta(seconds=value):
            offset = value
        else:
            break
    return offset


def mjd_sod_to_utc(mjd: int, sod: float) -> dt.datetime:
    gpst = mjd_sod_to_gpst(mjd, sod)
    offset = gps_utc_offset_seconds(gpst)
    return gpst - dt.timedelta(seconds=offset)


def station_from_path(path: Path) -> str:
    name = path.name
    if name.startswith("kin_") and "_" in name:
        return name.rsplit("_", 1)[-1].upper()
    return path.parent.parent.parent.name.upper()


def read_kin(path: Path) -> list[tuple[dt.datetime, float, float, float]]:
    rows: list[tuple[dt.datetime, float, float, float]] = []
    in_data = False
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "END OF HEADER":
            in_data = True
            continue
        if not in_data or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            rows.append((mjd_sod_to_utc(int(parts[0]), float(parts[1])), float(parts[2]), float(parts[3]), float(parts[4])))
        except ValueError:
            continue
    return rows


def median(values: list[float]) -> float:
    return statistics.median(values)


def rms(values: list[float]) -> float:
    if not values:
        return math.nan
    return math.sqrt(sum(value * value for value in values) / len(values))


def round_or_blank(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def ecef_to_enu(dx: float, dy: float, dz: float, ref_x: float, ref_y: float, ref_z: float) -> tuple[float, float, float]:
    lon = math.atan2(ref_y, ref_x)
    hyp = math.hypot(ref_x, ref_y)
    lat = math.atan2(ref_z, hyp)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return east, north, up


def kin_to_enu(path: Path, event_time: dt.datetime) -> list[tuple[dt.datetime, float, float, float, float]]:
    rows = read_kin(path)
    if not rows:
        return []
    pre = [row for row in rows if row[0] < event_time]
    ref_rows = pre if pre else rows[: min(len(rows), 300)]
    ref_x = median([row[1] for row in ref_rows])
    ref_y = median([row[2] for row in ref_rows])
    ref_z = median([row[3] for row in ref_rows])
    series: list[tuple[dt.datetime, float, float, float, float]] = []
    for timestamp, x, y, z in rows:
        east, north, up = ecef_to_enu(x - ref_x, y - ref_y, z - ref_z, ref_x, ref_y, ref_z)
        seconds = (timestamp - event_time).total_seconds()
        series.append((timestamp, seconds, east * 100.0, north * 100.0, up * 100.0))
    return series


def component_rms(rows: list[tuple[dt.datetime, float, float, float, float]]) -> tuple[float, float, float, float]:
    if not rows:
        return math.nan, math.nan, math.nan, math.nan
    east = [row[2] for row in rows]
    north = [row[3] for row in rows]
    up = [row[4] for row in rows]
    horizontal = [math.hypot(row[2], row[3]) for row in rows]
    return rms(east), rms(north), rms(up), rms(horizontal)


def max_epoch_jumps(rows: list[tuple[dt.datetime, float, float, float, float]]) -> tuple[float, float, float, float]:
    if len(rows) < 2:
        return math.nan, math.nan, math.nan, math.nan
    de: list[float] = []
    dn: list[float] = []
    du: list[float] = []
    d3: list[float] = []
    for prev, curr in zip(rows, rows[1:]):
        east = curr[2] - prev[2]
        north = curr[3] - prev[3]
        up = curr[4] - prev[4]
        de.append(abs(east))
        dn.append(abs(north))
        du.append(abs(up))
        d3.append(math.sqrt(east * east + north * north + up * up))
    return max(de), max(dn), max(du), max(d3)


def median_step(before: list[float], after: list[float]) -> float:
    if not before or not after:
        return math.nan
    return median(after) - median(before)


def quality_status(
    epoch_count: int,
    coverage_ratio: float,
    pre_rms_3d_cm: float,
    max_jump_3d_cm: float,
    args: argparse.Namespace,
) -> tuple[str, str]:
    issues: list[str] = []
    hard_fail = False
    if epoch_count == 0:
        return "FAIL", "no_data"
    if epoch_count < args.min_epochs:
        hard_fail = True
        issues.append("too_few_epochs")
    if math.isfinite(coverage_ratio) and coverage_ratio < args.min_coverage_ratio:
        hard_fail = True
        issues.append("short_coverage")
    if math.isfinite(pre_rms_3d_cm) and pre_rms_3d_cm > args.max_pre_rms_cm:
        issues.append("high_pre_event_rms")
    if math.isfinite(max_jump_3d_cm) and max_jump_3d_cm > args.max_epoch_jump_cm:
        issues.append("large_epoch_jump")
    if hard_fail:
        return "FAIL", ",".join(issues)
    if issues:
        return "WARN", ",".join(issues)
    return "OK", ""


def summarize_file(path: Path, event_time: dt.datetime, args: argparse.Namespace) -> dict[str, str]:
    series = kin_to_enu(path, event_time)
    station = station_from_path(path)
    if not series:
        return {
            "station": station,
            "kin_file": str(path),
            "quality_status": "FAIL",
            "quality_flags": "no_data",
        }

    times = [row[0] for row in series]
    seconds = [row[1] for row in series]
    intervals = [(curr - prev).total_seconds() for prev, curr in zip(times, times[1:])]
    median_interval = median(intervals) if intervals else math.nan
    gap_threshold = median_interval * 1.5 if math.isfinite(median_interval) and median_interval > 0 else math.inf
    gap_count = sum(1 for value in intervals if value > gap_threshold)
    coverage_seconds = (times[-1] - times[0]).total_seconds()
    expected_seconds = (
        args.expected_seconds
        if args.expected_seconds > 0
        else args.expected_hours_each_side * 2.0 * SECONDS_PER_DAY / 24.0
    )
    coverage_ratio = coverage_seconds / expected_seconds if expected_seconds > 0 else math.nan

    pre_rows = [row for row in series if row[1] < 0]
    noise_rows = pre_rows if pre_rows else series
    pre_e_rms, pre_n_rms, pre_u_rms, pre_h_rms = component_rms(noise_rows)
    pre_3d_rms = rms([math.sqrt(row[2] ** 2 + row[3] ** 2 + row[4] ** 2) for row in noise_rows])
    max_de, max_dn, max_du, max_d3 = max_epoch_jumps(series)

    before = [row for row in series if -args.event_step_window <= row[1] < 0]
    after = [row for row in series if 0 <= row[1] <= args.event_step_window]
    step_e = median_step([row[2] for row in before], [row[2] for row in after])
    step_n = median_step([row[3] for row in before], [row[3] for row in after])
    step_u = median_step([row[4] for row in before], [row[4] for row in after])
    step_h = math.hypot(step_e, step_n) if math.isfinite(step_e) and math.isfinite(step_n) else math.nan
    step_3d = math.sqrt(step_e * step_e + step_n * step_n + step_u * step_u) if all(math.isfinite(v) for v in [step_e, step_n, step_u]) else math.nan

    status, flags = quality_status(len(series), coverage_ratio, pre_3d_rms, max_d3, args)
    if gap_count:
        flags = ",".join([part for part in [flags, f"gaps:{gap_count}"] if part])
        if status == "OK":
            status = "WARN"

    return {
        "station": station,
        "kin_file": str(path),
        "quality_status": status,
        "quality_flags": flags,
        "epoch_count": str(len(series)),
        "start_utc": times[0].isoformat().replace("+00:00", "Z"),
        "end_utc": times[-1].isoformat().replace("+00:00", "Z"),
        "coverage_seconds": round_or_blank(coverage_seconds, 1),
        "coverage_ratio": round_or_blank(coverage_ratio, 3),
        "median_interval_seconds": round_or_blank(median_interval, 3),
        "gap_count": str(gap_count),
        "pre_event_epoch_count": str(len(pre_rows)),
        "pre_event_e_rms_cm": round_or_blank(pre_e_rms),
        "pre_event_n_rms_cm": round_or_blank(pre_n_rms),
        "pre_event_u_rms_cm": round_or_blank(pre_u_rms),
        "pre_event_horizontal_rms_cm": round_or_blank(pre_h_rms),
        "pre_event_3d_rms_cm": round_or_blank(pre_3d_rms),
        "max_epoch_jump_e_cm": round_or_blank(max_de),
        "max_epoch_jump_n_cm": round_or_blank(max_dn),
        "max_epoch_jump_u_cm": round_or_blank(max_du),
        "max_epoch_jump_3d_cm": round_or_blank(max_d3),
        "event_step_window_seconds": round_or_blank(args.event_step_window, 1),
        "event_step_e_cm": round_or_blank(step_e),
        "event_step_n_cm": round_or_blank(step_n),
        "event_step_u_cm": round_or_blank(step_u),
        "event_step_horizontal_cm": round_or_blank(step_h),
        "event_step_3d_cm": round_or_blank(step_3d),
    }


def aggregate(rows: list[dict[str, str]], min_station_health_ratio: float = 0.80) -> dict[str, object]:
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for row in rows:
        status = row.get("quality_status", "")
        if status in counts:
            counts[status] += 1

    station_count = len(rows)
    station_health_ratio = counts["OK"] / station_count if station_count else 0.0
    if not rows:
        status = "FAIL"
    elif station_health_ratio < min_station_health_ratio:
        status = "WARN"
    else:
        status = "OK"

    return {
        "status": status,
        "station_count": station_count,
        "ok_station_count": counts["OK"],
        "warn_station_count": counts["WARN"],
        "fail_station_count": counts["FAIL"],
        "station_health_ratio": round(station_health_ratio, 3),
        "min_station_health_ratio": min_station_health_ratio,
    }


def main() -> int:
    args = parse_args()
    event_time = parse_utc(args.event_time)
    rows = [summarize_file(Path(path), event_time, args) for path in args.kin_files]
    summary = aggregate(rows, min_station_health_ratio=args.min_station_health_ratio)
    payload = {"summary": summary, "stations": rows}

    if args.out_tsv:
        out_tsv = Path(args.out_tsv)
        out_tsv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys())) if rows else ["station", "kin_file", "quality_status", "quality_flags"]
        with out_tsv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(text)
    elif not args.out_tsv:
        sys.stdout.write(text)

    return 1 if summary["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
