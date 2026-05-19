#!/usr/bin/env python3
"""Estimate a symmetric event processing window from RINEX observation coverage."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--max-hours", type=float, default=3.0)
    parser.add_argument("--safety-seconds", type=float, default=1.0)
    parser.add_argument("--out-json")
    parser.add_argument("obs_files", nargs="+")
    return parser.parse_args()


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def rinex_version(path: Path) -> int:
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    try:
        return int(float(first[:20].strip()))
    except (ValueError, IndexError):
        return 2


def parse_rinex3_epoch(line: str) -> dt.datetime | None:
    if not line.startswith(">"):
        return None
    parts = line[1:].split()
    if len(parts) < 6:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = float(parts[5])
    except ValueError:
        return None
    return build_datetime(year, month, day, hour, minute, second)


def parse_rinex2_epoch(line: str) -> dt.datetime | None:
    parts = line.split()
    if len(parts) < 6:
        return None
    try:
        year2 = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = float(parts[5])
    except ValueError:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    year = 1900 + year2 if year2 >= 80 else 2000 + year2
    return build_datetime(year, month, day, hour, minute, second)


def build_datetime(year: int, month: int, day: int, hour: int, minute: int, second: float) -> dt.datetime | None:
    whole = math.floor(second)
    microsecond = int(round((second - whole) * 1_000_000))
    if microsecond >= 1_000_000:
        whole += 1
        microsecond -= 1_000_000
    try:
        base = dt.datetime(year, month, day, hour, minute, 0, tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return base + dt.timedelta(seconds=whole, microseconds=microsecond)


def read_coverage(path: Path) -> tuple[dt.datetime, dt.datetime, int]:
    version = rinex_version(path)
    in_body = False
    first: dt.datetime | None = None
    last: dt.datetime | None = None
    count = 0
    parser = parse_rinex3_epoch if version >= 3 else parse_rinex2_epoch

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not in_body:
            if "END OF HEADER" in raw:
                in_body = True
            continue
        epoch = parser(raw)
        if epoch is None:
            continue
        if first is None:
            first = epoch
        last = epoch
        count += 1

    if first is None or last is None:
        raise ValueError(f"no RINEX epochs found: {path}")
    return first, last, count


def main() -> int:
    args = parse_args()
    event_time = parse_utc(args.event_time)
    files: list[dict[str, object]] = []
    starts: list[dt.datetime] = []
    ends: list[dt.datetime] = []

    for value in args.obs_files:
        path = Path(value)
        start, end, epoch_count = read_coverage(path)
        contains_event = start <= event_time <= end
        files.append(
            {
                "path": str(path),
                "start_utc": start.isoformat().replace("+00:00", "Z"),
                "end_utc": end.isoformat().replace("+00:00", "Z"),
                "epoch_count": epoch_count,
                "contains_event": contains_event,
            }
        )
        if not contains_event:
            payload = {
                "status": "FAIL",
                "reason": "event_time_outside_observation_coverage",
                "event_time_utc": event_time.isoformat().replace("+00:00", "Z"),
                "files": files,
            }
            write_payload(args, payload)
            return 2
        starts.append(start)
        ends.append(end)

    common_start = max(starts)
    common_end = min(ends)
    before_seconds = (event_time - common_start).total_seconds()
    after_seconds = (common_end - event_time).total_seconds()
    max_seconds = args.max_hours * 3600.0
    window_seconds = min(before_seconds, after_seconds, max_seconds) - args.safety_seconds
    if window_seconds <= 0:
        payload = {
            "status": "FAIL",
            "reason": "no_symmetric_window_around_event",
            "event_time_utc": event_time.isoformat().replace("+00:00", "Z"),
            "common_start_utc": common_start.isoformat().replace("+00:00", "Z"),
            "common_end_utc": common_end.isoformat().replace("+00:00", "Z"),
            "files": files,
        }
        write_payload(args, payload)
        return 2

    suggested_hours = window_seconds / 3600.0
    payload = {
        "status": "OK",
        "event_time_utc": event_time.isoformat().replace("+00:00", "Z"),
        "requested_max_hours_each_side": args.max_hours,
        "suggested_hours_each_side": round(suggested_hours, 6),
        "common_start_utc": common_start.isoformat().replace("+00:00", "Z"),
        "common_end_utc": common_end.isoformat().replace("+00:00", "Z"),
        "before_event_seconds": round(before_seconds, 3),
        "after_event_seconds": round(after_seconds, 3),
        "safety_seconds": args.safety_seconds,
        "files": files,
    }
    write_payload(args, payload)
    print(f"{suggested_hours:.6f}")
    return 0


def write_payload(args: argparse.Namespace, payload: dict[str, object]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out_json:
        Path(args.out_json).write_text(text, encoding="utf-8")
    else:
        print(text, end="", file=sys.stderr if payload.get("status") != "OK" else sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
