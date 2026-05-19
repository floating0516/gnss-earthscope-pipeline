#!/usr/bin/env python3
"""Plot PRIDE kinematic XYZ files as ENU SVG figures."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
from pathlib import Path


MJD_UNIX_EPOCH = 40587
SECONDS_PER_DAY = 86400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-time", required=True, help="UTC event time, e.g. 2021-10-11T09:10:25Z")
    parser.add_argument("--out-dir", required=True, help="Directory for SVG outputs")
    parser.add_argument("--post-seconds", type=int, default=200, help="Post-event detail window in seconds")
    parser.add_argument("kin_files", nargs="+", help="PRIDE kin_* files")
    return parser.parse_args()


def parse_utc(value: str) -> dt.datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def mjd_sod_to_utc(mjd: int, sod: float) -> dt.datetime:
    seconds = (mjd - MJD_UNIX_EPOCH) * SECONDS_PER_DAY + sod
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)


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
            mjd = int(parts[0])
            sod = float(parts[1])
            x = float(parts[2])
            y = float(parts[3])
            z = float(parts[4])
        except ValueError:
            continue
        rows.append((mjd_sod_to_utc(mjd, sod), x, y, z))
    return rows


def median(values: list[float]) -> float:
    return statistics.median(values)


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


def kin_to_enu(path: Path, event_time: dt.datetime) -> tuple[str, list[tuple[float, float, float, float]]]:
    rows = read_kin(path)
    if not rows:
        raise ValueError(f"no data rows found: {path}")
    pre = [row for row in rows if row[0] < event_time]
    ref_rows = pre if pre else rows[: min(len(rows), 300)]
    ref_x = median([row[1] for row in ref_rows])
    ref_y = median([row[2] for row in ref_rows])
    ref_z = median([row[3] for row in ref_rows])
    series: list[tuple[float, float, float, float]] = []
    for timestamp, x, y, z in rows:
        east, north, up = ecef_to_enu(x - ref_x, y - ref_y, z - ref_z, ref_x, ref_y, ref_z)
        seconds = (timestamp - event_time).total_seconds()
        series.append((seconds, east * 100.0, north * 100.0, up * 100.0))
    return station_from_path(path), series


def downsample(points: list[tuple[float, float]], max_points: int = 3000) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return points
    step = math.ceil(len(points) / max_points)
    return points[::step]


def nice_range(values: list[float]) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        pad = 1.0
    else:
        pad = (high - low) * 0.08
    return low - pad, high + pad


def polyline(points: list[tuple[float, float]], x0: float, y0: float, width: float, height: float,
             xmin: float, xmax: float, ymin: float, ymax: float) -> str:
    coords = []
    for x, y in downsample(points):
        sx = x0 + (x - xmin) / (xmax - xmin) * width
        sy = y0 + height - (y - ymin) / (ymax - ymin) * height
        coords.append(f"{sx:.1f},{sy:.1f}")
    return " ".join(coords)


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_station_svg(station: str, series: list[tuple[float, float, float, float]], out_path: Path,
                       title: str, window: tuple[float, float] | None = None) -> None:
    if window is not None:
        start, end = window
        series = [row for row in series if start <= row[0] <= end]
    if not series:
        raise ValueError(f"no points in requested window for {station}")

    components = [("East", "#1264a3", 1), ("North", "#2f7d32", 2), ("Up", "#b42318", 3)]
    xmin = min(row[0] for row in series)
    xmax = max(row[0] for row in series)
    if math.isclose(xmin, xmax):
        xmax = xmin + 1
    all_values = [row[index] for _, _, index in components for row in series]
    ymin, ymax = nice_range(all_values)

    width = 1100
    panel_h = 215
    left = 78
    right = 28
    top = 62
    gap = 42
    plot_w = width - left - right
    height = top + len(components) * panel_h + (len(components) - 1) * gap + 55

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="34" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{svg_escape(title)}</text>',
        f'<text x="{left}" y="55" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">Reference: pre-event median, unit: cm, x-axis: seconds from event</text>',
    ]

    for panel_index, (label, color, value_index) in enumerate(components):
        y0 = top + panel_index * (panel_h + gap)
        zero_y = y0 + panel_h - (0 - ymin) / (ymax - ymin) * panel_h
        if y0 <= zero_y <= y0 + panel_h:
            parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{zero_y:.1f}" y2="{zero_y:.1f}" stroke="#d1d5db" stroke-width="1"/>')
        if xmin <= 0 <= xmax:
            event_x = left + (0 - xmin) / (xmax - xmin) * plot_w
            parts.append(f'<line x1="{event_x:.1f}" x2="{event_x:.1f}" y1="{y0}" y2="{y0 + panel_h}" stroke="#111827" stroke-width="1.2" stroke-dasharray="5 5"/>')
        parts.append(f'<rect x="{left}" y="{y0}" width="{plot_w}" height="{panel_h}" fill="none" stroke="#9ca3af" stroke-width="1"/>')
        points = [(row[0], row[value_index]) for row in series]
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.4" points="{polyline(points, left, y0, plot_w, panel_h, xmin, xmax, ymin, ymax)}"/>')
        parts.append(f'<text x="18" y="{y0 + 24}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="{color}">{label}</text>')
        parts.append(f'<text x="18" y="{y0 + 44}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">cm</text>')
        parts.append(f'<text x="{left - 8}" y="{y0 + 13}" text-anchor="end" font-family="Arial, sans-serif" font-size="11" fill="#4b5563">{ymax:.1f}</text>')
        parts.append(f'<text x="{left - 8}" y="{y0 + panel_h}" text-anchor="end" font-family="Arial, sans-serif" font-size="11" fill="#4b5563">{ymin:.1f}</text>')

    parts.append(f'<text x="{left}" y="{height - 22}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">x range: {xmin:.0f}s to {xmax:.0f}s</text>')
    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n")


def main() -> None:
    args = parse_args()
    event_time = parse_utc(args.event_time)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    for kin_file in args.kin_files:
        path = Path(kin_file)
        try:
            station, series = kin_to_enu(path, event_time)
        except ValueError as exc:
            skipped.append((path, str(exc)))
            continue
        full_path = out_dir / f"{station.lower()}_enu_full.svg"
        post_path = out_dir / f"{station.lower()}_enu_post{args.post_seconds}s.svg"
        try:
            render_station_svg(station, series, full_path, f"{station} ENU, full PRIDE window")
            render_station_svg(
                station,
                series,
                post_path,
                f"{station} ENU, first {args.post_seconds}s after event",
                window=(0, float(args.post_seconds)),
            )
        except ValueError as exc:
            skipped.append((path, str(exc)))
            continue
        else:
            generated.extend([full_path, post_path])

    manifest = out_dir / "plots-manifest.txt"
    manifest.write_text("".join(f"{path}\n" for path in generated))
    skipped_manifest = out_dir / "plots-skipped.tsv"
    skipped_manifest.write_text(
        "kin_file\treason\n" + "".join(f"{path}\t{reason}\n" for path, reason in skipped)
    )
    for path in generated:
        print(path)
    print(manifest)
    if skipped:
        print(skipped_manifest)
    if not generated and skipped:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
