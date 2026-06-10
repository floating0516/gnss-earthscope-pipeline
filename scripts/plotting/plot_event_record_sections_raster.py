#!/usr/bin/env python3
"""Create raster GNSS displacement record-section figures for solved events.

This is the production version of the event-level record-section plotter.  It
reads PRIDE ``kin_*`` files from workflow directories, converts ECEF positions
to ENU displacement in centimeters, sorts stations by EarthScope/database
epicentral distance, and saves one three-panel figure per event as high
resolution PNG plus rasterized PDF.

The figure uses Matplotlib image rendering, not dense SVG rectangles.  This is
important for record sections because the plotted object is a high-density
time-distance matrix similar to ``imshow``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sqlite3
import statistics
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = ROOT / "runs"
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
DEFAULT_FIGURE_ROOT = ROOT / "figure" / "record_section"

MJD_UNIX_EPOCH = 40587
SECONDS_PER_DAY = 86400
COMPONENTS = ("East", "North", "Vertical")


@dataclass
class StationRecord:
    station: str
    distance_km: float
    east: list[float | None]
    north: list[float | None]
    vertical: list[float | None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT), help="Root containing event workflow runs")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB with event/station distances")
    parser.add_argument("--workflow", action="append", default=[], help="Specific workflow directory; can repeat")
    parser.add_argument("--time-min", type=int, default=0, help="Record-section start time after OT, seconds")
    parser.add_argument("--time-max", type=int, default=200, help="Record-section end time after OT, seconds")
    parser.add_argument("--distance-max", type=float, default=600.0, help="Maximum plotted distance, km")
    parser.add_argument("--radius-km", type=float, default=300.0, help="Candidate station radius used for distances")
    parser.add_argument("--out-root", default=str(DEFAULT_FIGURE_ROOT), help="Directory for event-level figures")
    parser.add_argument("--out-prefix", default="record_section", help="Output filename prefix")
    parser.add_argument("--dpi", type=int, default=300, help="PNG/PDF save resolution")
    parser.add_argument("--percentile", type=float, default=99.5, help="Symmetric amplitude clipping percentile")
    parser.add_argument("--distance-pixels", type=int, default=900, help="Raster rows used after distance interpolation")
    parser.add_argument(
        "--baseline-seconds",
        type=int,
        default=10,
        help="Remove each trace median over the first N seconds after OT; use 0 to disable",
    )
    parser.add_argument(
        "--highpass-seconds",
        type=int,
        default=0,
        help="Subtract each trace's centered running mean over this window to suppress static offsets and slow drift; use 0 to disable",
    )
    parser.add_argument(
        "--trace-normalize-percentile",
        type=float,
        default=98.0,
        help="Normalize each station trace by this absolute percentile after filtering; use 0 to keep centimeter amplitudes",
    )
    parser.add_argument(
        "--no-trace-median",
        action="store_true",
        help="Do not subtract each trace's full-window median after baseline removal",
    )
    parser.add_argument("--no-pdf", action="store_true", help="Only write PNG output")
    parser.add_argument("--show", action="store_true", help="Show each figure interactively after saving")
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


def read_key_value_tsv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        if not raw.strip() or raw.startswith("key\t"):
            continue
        parts = raw.split("\t", 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1]
    return values


def find_workflows(runs_root: Path) -> list[Path]:
    return sorted(path.parent.parent for path in runs_root.glob("*/workflow-*/reports/workflow-summary.tsv"))


def load_distances(db_path: Path, event_id: str, radius_km: float) -> dict[str, float]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT station, MIN(distance_km)
            FROM event_earthscope_station_candidates
            WHERE event_id = ? AND radius_km = ?
            GROUP BY station
            """,
            (event_id, radius_km),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT station, MIN(distance_km)
                FROM event_earthscope_station_candidates
                WHERE event_id = ?
                GROUP BY station
                """,
                (event_id,),
            ).fetchall()
    finally:
        conn.close()
    return {str(station).upper(): float(distance) for station, distance in rows}


def station_from_kin_path(path: Path) -> str:
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


def kin_to_enu_series(path: Path, event_time: dt.datetime) -> list[tuple[float, float, float, float]]:
    rows = read_kin(path)
    if not rows:
        return []
    pre = [row for row in rows if row[0] < event_time]
    ref_rows = pre if pre else rows[: min(len(rows), 300)]
    ref_x = statistics.median(row[1] for row in ref_rows)
    ref_y = statistics.median(row[2] for row in ref_rows)
    ref_z = statistics.median(row[3] for row in ref_rows)

    series: list[tuple[float, float, float, float]] = []
    for timestamp, x, y, z in rows:
        east, north, up = ecef_to_enu(x - ref_x, y - ref_y, z - ref_z, ref_x, ref_y, ref_z)
        seconds = (timestamp - event_time).total_seconds()
        series.append((seconds, east * 100.0, north * 100.0, up * 100.0))
    return series


def interpolate_series(
    series: list[tuple[float, float, float, float]],
    target_times: list[int],
    max_gap_seconds: float = 3.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    if len(series) < 2:
        return [None] * len(target_times), [None] * len(target_times), [None] * len(target_times)

    series = sorted(series, key=lambda row: row[0])
    out = [[None for _ in target_times] for _ in COMPONENTS]
    j = 0
    for i, target in enumerate(target_times):
        while j + 1 < len(series) and series[j + 1][0] < target:
            j += 1
        if j + 1 >= len(series):
            continue
        t0, e0, n0, u0 = series[j]
        t1, e1, n1, u1 = series[j + 1]
        if t0 <= target <= t1 and (t1 - t0) <= max_gap_seconds:
            frac = 0.0 if math.isclose(t0, t1) else (target - t0) / (t1 - t0)
            out[0][i] = e0 + frac * (e1 - e0)
            out[1][i] = n0 + frac * (n1 - n0)
            out[2][i] = u0 + frac * (u1 - u0)
    return out[0], out[1], out[2]


def load_event_records(
    workflow_dir: Path,
    db_path: Path,
    target_times: list[int],
    radius_km: float,
    distance_max: float,
) -> tuple[dict[str, str], list[StationRecord], list[str]]:
    summary = read_key_value_tsv(workflow_dir / "reports" / "workflow-summary.tsv")
    event_id = summary.get("event_id", workflow_dir.parent.name)
    event_time = parse_utc(summary["event_time_utc"])
    distances = load_distances(db_path, event_id, radius_km)
    kin_list = workflow_dir / "manifests" / "kin-files.txt"
    skipped: list[str] = []
    records: list[StationRecord] = []

    if not kin_list.exists():
        return summary, records, ["missing kin-files.txt"]

    for raw in kin_list.read_text().splitlines():
        if not raw.strip():
            continue
        kin_path = Path(raw.strip())
        station = station_from_kin_path(kin_path)
        distance = distances.get(station)
        if distance is None:
            skipped.append(f"{station}: no distance in DB")
            continue
        if distance > distance_max:
            skipped.append(f"{station}: distance {distance:.1f} km > {distance_max:.1f} km")
            continue
        series = kin_to_enu_series(kin_path, event_time)
        if not series:
            skipped.append(f"{station}: no kin data rows")
            continue
        east, north, vertical = interpolate_series(series, target_times)
        if not any(value is not None for values in (east, north, vertical) for value in values):
            skipped.append(f"{station}: no samples in {target_times[0]}-{target_times[-1]} s")
            continue
        records.append(StationRecord(station, distance, east, north, vertical))

    records.sort(key=lambda row: (row.distance_km, row.station))
    return summary, records, skipped


def build_record_section_colormap() -> LinearSegmentedColormap:
    colors = [
        (0.035, 0.040, 0.045),
        (0.18, 0.21, 0.24),
        (0.40, 0.48, 0.54),
        (0.68, 0.74, 0.77),
        (0.94, 0.95, 0.93),
    ]
    cmap = LinearSegmentedColormap.from_list("jgr_gray_blue", colors, N=256)
    cmap.set_bad("#a8b3b9")
    return cmap


def running_nanmean(row: np.ndarray, window_samples: int) -> np.ndarray:
    """Centered running mean that ignores NaNs."""
    if window_samples <= 1:
        return np.zeros_like(row)
    if window_samples % 2 == 0:
        window_samples += 1
    good = np.isfinite(row)
    if not good.any():
        return np.full_like(row, np.nan)
    kernel = np.ones(window_samples, dtype=float)
    values = np.where(good, row, 0.0)
    counts = np.convolve(good.astype(float), kernel, mode="same")
    sums = np.convolve(values, kernel, mode="same")
    trend = np.full_like(row, np.nan)
    usable = counts >= max(3.0, 0.25 * window_samples)
    trend[usable] = sums[usable] / counts[usable]
    return trend


def component_matrix(
    records: list[StationRecord],
    component: str,
    target_times: list[int],
    baseline_seconds: int,
    highpass_seconds: int,
    remove_trace_median: bool,
    trace_normalize_percentile: float,
) -> np.ndarray:
    if component == "East":
        rows = [record.east for record in records]
    elif component == "North":
        rows = [record.north for record in records]
    elif component == "Vertical":
        rows = [record.vertical for record in records]
    else:
        raise ValueError(component)
    matrix = np.array([[np.nan if value is None else value for value in row] for row in rows], dtype=float)

    if baseline_seconds > 0:
        time = np.array(target_times, dtype=float)
        baseline_mask = time <= (time.min() + baseline_seconds)
        for row_index in range(matrix.shape[0]):
            baseline = matrix[row_index, baseline_mask]
            if np.isfinite(baseline).any():
                matrix[row_index, :] -= np.nanmedian(baseline)

    if remove_trace_median:
        for row_index in range(matrix.shape[0]):
            row = matrix[row_index, :]
            if np.isfinite(row).any():
                matrix[row_index, :] -= np.nanmedian(row)

    if highpass_seconds > 0 and len(target_times) > 1:
        dt_seconds = float(np.median(np.diff(np.array(target_times, dtype=float))))
        window_samples = max(3, int(round(highpass_seconds / max(dt_seconds, 1e-6))))
        for row_index in range(matrix.shape[0]):
            row = matrix[row_index, :]
            trend = running_nanmean(row, window_samples)
            good = np.isfinite(row) & np.isfinite(trend)
            matrix[row_index, good] = row[good] - trend[good]

    if trace_normalize_percentile > 0:
        for row_index in range(matrix.shape[0]):
            row = matrix[row_index, :]
            finite_abs = np.abs(row[np.isfinite(row)])
            if not finite_abs.size:
                continue
            scale = np.percentile(finite_abs, trace_normalize_percentile)
            if scale > 0:
                matrix[row_index, :] = row / scale

    return matrix


def interpolate_to_regular_distance(
    station_distances: np.ndarray,
    matrix: np.ndarray,
    distance_grid: np.ndarray,
) -> np.ndarray:
    """Interpolate station rows onto a regular distance grid for imshow."""
    out = np.full((distance_grid.size, matrix.shape[1]), np.nan, dtype=float)
    for col in range(matrix.shape[1]):
        values = matrix[:, col]
        good = np.isfinite(values)
        if good.sum() == 0:
            continue
        if good.sum() == 1:
            nearest = np.argmin(np.abs(distance_grid - station_distances[good][0]))
            out[nearest, col] = values[good][0]
            continue
        out[:, col] = np.interp(distance_grid, station_distances[good], values[good], left=np.nan, right=np.nan)
    return out


def light_smooth(matrix: np.ndarray) -> np.ndarray:
    """Apply a minimal 3-point smoothing to avoid hard station-row artifacts."""
    filled = np.array(matrix, copy=True)
    finite = np.isfinite(filled)
    if not finite.any():
        return matrix
    median = np.nanmedian(filled)
    filled[~finite] = median

    # Weak smoothing only; preserve wave arrivals while reducing hard raster rows.
    time_smoothed = 0.18 * np.roll(filled, 1, axis=1) + 0.64 * filled + 0.18 * np.roll(filled, -1, axis=1)
    dist_smoothed = 0.12 * np.roll(time_smoothed, 1, axis=0) + 0.76 * time_smoothed + 0.12 * np.roll(time_smoothed, -1, axis=0)
    dist_smoothed[~finite] = np.nan
    return dist_smoothed


def plot_event_record_section(
    summary: dict[str, str],
    records: list[StationRecord],
    skipped: list[str],
    target_times: list[int],
    distance_max: float,
    out_png: Path,
    out_pdf: Path | None,
    dpi: int,
    clip_percentile: float,
    distance_pixels: int,
    baseline_seconds: int,
    highpass_seconds: int,
    remove_trace_median: bool,
    trace_normalize_percentile: float,
    show: bool,
) -> None:
    if not records:
        raise ValueError("no station records to plot")

    station_distances = np.array([record.distance_km for record in records], dtype=float)
    distance_grid = np.linspace(0.0, distance_max, distance_pixels)
    time = np.array(target_times, dtype=float)

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "savefig.dpi": dpi,
        }
    )

    cmap = build_record_section_colormap()
    fig, axes = plt.subplots(1, 3, figsize=(13, 7), sharex=True, sharey=True)
    fig.patch.set_facecolor("#e6eaec")

    event_id = summary.get("event_id", "event")
    event_time = summary.get("event_time_utc", "")
    fig.suptitle(
        f"{event_id} GNSS displacement record section",
        fontsize=16,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.075,
        0.925,
        (
            f"OT {event_time}; stations plotted {len(records)}; skipped {len(skipped)}; "
            f"baseline {baseline_seconds}s; highpass {highpass_seconds}s"
        ),
        fontsize=10,
        color="#374151",
    )

    for ax, component in zip(axes, COMPONENTS, strict=True):
        raw = component_matrix(
            records,
            component,
            target_times,
            baseline_seconds,
            highpass_seconds,
            remove_trace_median,
            trace_normalize_percentile,
        )
        regular = interpolate_to_regular_distance(station_distances, raw, distance_grid)
        image = light_smooth(regular)
        finite = np.abs(image[np.isfinite(image)])
        clip = np.percentile(finite, clip_percentile) if finite.size else 1.0
        if clip <= 0:
            clip = np.nanmax(finite) if finite.size else 1.0

        norm = TwoSlopeNorm(vmin=-clip, vcenter=0.0, vmax=clip)
        ax.imshow(
            image,
            extent=[time.min(), time.max(), 0.0, distance_max],
            origin="lower",
            aspect="auto",
            cmap=cmap,
            norm=norm,
            interpolation="bilinear",
            rasterized=True,
        )
        ax.set_title(component, fontsize=15, pad=10)
        ax.set_xlabel("Time past OT (s)", fontsize=13)
        ax.set_xlim(time.min(), time.max())
        ax.set_ylim(0, distance_max)
        ax.set_xticks([0, 50, 100, 150, 200])
        ax.set_yticks([0, 100, 200, 300, 400, 500, 600])
        ax.tick_params(labelsize=11, length=4)
        ax.grid(False)
        ax.set_facecolor("#a8b3b9")
        for spine in ax.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("black")
        ax.text(
            0.98,
            0.98,
            f"{clip_percentile:g}% = {clip:.2f} {'rel.' if trace_normalize_percentile > 0 else 'cm'}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#1f2937",
        )

    axes[0].set_ylabel("Distance (km)", fontsize=13)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.105, top=0.88, wspace=0.16)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    if out_pdf is not None:
        fig.savefig(out_pdf, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    else:
        plt.close(fig)

    skipped_path = out_png.with_suffix(".skipped.txt")
    skipped_path.write_text("\n".join(skipped) + ("\n" if skipped else ""))


def main() -> None:
    args = parse_args()
    target_times = list(range(args.time_min, args.time_max + 1))
    workflows = [Path(path).resolve() for path in args.workflow] if args.workflow else find_workflows(Path(args.runs_root))
    out_root = Path(args.out_root)

    for workflow_dir in workflows:
        summary_path = workflow_dir / "reports" / "workflow-summary.tsv"
        if not summary_path.exists():
            print(f"SKIP missing summary: {workflow_dir}")
            continue
        summary = read_key_value_tsv(summary_path)
        if int(summary.get("kin_file_count") or 0) <= 0:
            print(f"SKIP no kin: {workflow_dir}")
            continue

        summary, records, skipped = load_event_records(
            workflow_dir=workflow_dir,
            db_path=Path(args.db),
            target_times=target_times,
            radius_km=args.radius_km,
            distance_max=args.distance_max,
        )
        if not records:
            print(f"SKIP no plottable records: {workflow_dir}")
            continue

        event_id = summary.get("event_id", workflow_dir.parent.name)
        out_png = out_root / f"{args.out_prefix}_{event_id}.png"
        out_pdf = None if args.no_pdf else out_root / f"{args.out_prefix}_{event_id}.pdf"
        plot_event_record_section(
            summary=summary,
            records=records,
            skipped=skipped,
            target_times=target_times,
            distance_max=args.distance_max,
            out_png=out_png,
            out_pdf=out_pdf,
            dpi=args.dpi,
            clip_percentile=args.percentile,
            distance_pixels=args.distance_pixels,
            baseline_seconds=args.baseline_seconds,
            highpass_seconds=args.highpass_seconds,
            remove_trace_median=not args.no_trace_median,
            trace_normalize_percentile=args.trace_normalize_percentile,
            show=args.show,
        )
        print(f"{event_id}\tstations={len(records)}\tskipped={len(skipped)}\t{out_png}")


if __name__ == "__main__":
    main()
