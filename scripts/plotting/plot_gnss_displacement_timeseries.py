#!/usr/bin/env python3
"""Plot academic-style GNSS displacement time series for a normalized event."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple

_src = str(Path(__file__).resolve().parents[2] / "src")
if _src in sys.path:
    sys.path.remove(_src)
sys.path.insert(0, _src)

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

from gnss_eq.pgd import read_pgd_by_station
from gnss_eq.pgd import station_quality_flags


COMPONENTS = ("E", "N", "U")
COMPONENT_TITLES = {
    "E": "East (cm)",
    "N": "North (cm)",
    "U": "Vertical (cm)",
}
REQUIRED_STATION_COLUMNS = {"Station", "Distance_Km"}
REQUIRED_WAVEFORM_COLUMNS = {"Station", "Time_Offset_s", "Component", "Value_m"}


class StationPlotInfo(NamedTuple):
    station: str
    distance_km: float


class PlotData(NamedTuple):
    stations: list[StationPlotInfo]
    traces: dict[tuple[str, str], pd.DataFrame]
    time_start: float
    time_end: float


class StationPGD(NamedTuple):
    station: str
    pgd_cm: float
    east_cm_at_peak: float
    north_cm_at_peak: float
    vertical_cm_at_peak: float
    time_offset_s: float
    snr: float
    quality_flags: str
    usable: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_dir", type=Path, help="Normalized event directory with event.json/stations.csv/waveforms.csv.gz")
    parser.add_argument("--out", type=Path, help="Output PNG path; defaults to figure/<event>_displacement_timeseries.png")
    parser.add_argument("--outdir", type=Path, default=Path("figure"), help="Output directory when --out is not set")
    parser.add_argument("--dpi", type=int, default=300, help="PNG save resolution")
    parser.add_argument("--time-start", type=float, default=0.0, help="Start time after origin, seconds")
    parser.add_argument("--time-end", type=float, default=600.0, help="End time after origin, seconds")
    parser.add_argument(
        "--baseline-seconds",
        type=float,
        default=10.0,
        help="Subtract median over the first N seconds of the plotted window; use 0 to disable",
    )
    parser.add_argument("--max-stations", type=int, help="Plot only the farthest N stations after sorting")
    parser.add_argument("--vertical-spacing-cm", type=float, help="Fixed vertical trace spacing in centimeters")
    parser.add_argument("--scale-bar-cm", type=float, default=5.0, help="Vertical amplitude scale bar in centimeters")
    parser.add_argument("--line-width", type=float, default=0.55, help="Waveform line width")
    parser.add_argument("--highlight-max-pgd", action="store_true", help="Highlight the largest usable PGD station in red")
    parser.add_argument("--noise-window-start", type=float, default=-300.0, help="Start of pre-event noise window for PGD SNR")
    parser.add_argument("--noise-window-end", type=float, default=0.0, help="End of pre-event noise window for PGD SNR")
    parser.add_argument("--min-pgd-snr", type=float, default=3.0, help="Minimum PGD/pre-event-RMS SNR for a highlighted station")
    parser.add_argument("--quality-max-pgd-time-offset", type=float, default=300.0, help="Latest accepted PGD peak time; use 0 to disable")
    parser.add_argument("--quality-max-distance-km", type=float, default=0.0, help="Maximum accepted station distance for highlight; use 0 to disable")
    parser.add_argument("--min-pgd-m", type=float, default=1e-6, help="Minimum PGD in meters")
    parser.add_argument("--show", action="store_true", help="Show the figure interactively after saving")
    return parser.parse_args()


def load_event(event_dir: Path) -> dict:
    path = event_dir / "event.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_stations(event_dir: Path) -> pd.DataFrame:
    return pd.read_csv(event_dir / "stations.csv")


def load_waveforms(event_dir: Path) -> pd.DataFrame:
    return pd.read_csv(
        event_dir / "waveforms.csv.gz",
        usecols=["Station", "Time_Offset_s", "Component", "Value_m"],
        low_memory=False,
    )


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(missing)}")


def _normalise_station_column(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["Station"] = out["Station"].astype(str).str.strip().str.upper()
    return out


def prepare_plot_data(
    stations: pd.DataFrame,
    waveforms: pd.DataFrame,
    *,
    time_start: float,
    time_end: float,
    baseline_seconds: float = 10.0,
    max_stations: int | None = None,
) -> PlotData:
    """Return far-to-near station order and centimeter traces within the time window."""
    _require_columns(stations, REQUIRED_STATION_COLUMNS, "stations.csv")
    _require_columns(waveforms, REQUIRED_WAVEFORM_COLUMNS, "waveforms.csv.gz")
    if time_end <= time_start:
        raise ValueError("--time-end must be greater than --time-start")

    station_table = _normalise_station_column(stations)
    station_table = station_table[["Station", "Distance_Km"]].copy()
    station_table["Distance_Km"] = pd.to_numeric(station_table["Distance_Km"], errors="coerce")
    station_table = station_table.dropna(subset=["Station", "Distance_Km"])
    station_table = station_table.drop_duplicates(subset=["Station"], keep="first")
    station_table = station_table.sort_values(["Distance_Km", "Station"], ascending=[False, True])
    if max_stations is not None:
        if max_stations <= 0:
            raise ValueError("--max-stations must be positive")
        station_table = station_table.head(max_stations)

    station_order = [
        StationPlotInfo(station=str(row.Station), distance_km=float(row.Distance_Km))
        for row in station_table.itertuples(index=False)
    ]
    station_names = {row.station for row in station_order}
    if not station_order:
        raise ValueError("No stations with valid Distance_Km values")

    traces: dict[tuple[str, str], pd.DataFrame] = {}
    waveform_table = _normalise_station_column(waveforms)
    waveform_table["Time_Offset_s"] = pd.to_numeric(waveform_table["Time_Offset_s"], errors="coerce")
    waveform_table["Value_m"] = pd.to_numeric(waveform_table["Value_m"], errors="coerce")
    waveform_table["Component"] = waveform_table["Component"].astype(str).str.strip().str.upper()
    waveform_table = waveform_table[
        waveform_table["Station"].isin(station_names)
        & waveform_table["Component"].isin(COMPONENTS)
        & waveform_table["Time_Offset_s"].between(time_start, time_end, inclusive="both")
    ].dropna(subset=["Time_Offset_s", "Value_m"])

    for (station, component), group in waveform_table.groupby(["Station", "Component"], sort=False):
        trace = group.sort_values("Time_Offset_s")[["Time_Offset_s", "Value_m"]].copy()
        trace["value_cm"] = trace["Value_m"] * 100.0
        if baseline_seconds > 0:
            baseline_mask = trace["Time_Offset_s"] <= (time_start + baseline_seconds)
            baseline = trace.loc[baseline_mask, "value_cm"]
            if not baseline.empty:
                trace["value_cm"] = trace["value_cm"] - float(baseline.median())
        trace = trace.rename(columns={"Time_Offset_s": "time_s"})[["time_s", "value_cm"]]
        traces[(str(station), str(component))] = trace.reset_index(drop=True)

    if not traces:
        raise ValueError(f"No waveform samples in {time_start:g}-{time_end:g} s for selected stations")

    return PlotData(stations=station_order, traces=traces, time_start=time_start, time_end=time_end)


def origin_time_text(event: dict) -> str:
    raw = str(event.get("date", "")).strip()
    if not raw:
        return "起始时间 (s)"
    text = raw
    if text.endswith("Z"):
        text = text[:-1]
    text = text.replace("T", " ")
    if "." in text:
        text = text.split(".", 1)[0]
    return f"起始时间{text} (s)"


def event_title(event: dict) -> str:
    raw_date = str(event.get("date", "")).replace("T", " ")
    date = raw_date[:19] if raw_date else ""
    magnitude = event.get("magnitude")
    place = event.get("place") or event.get("event") or ""
    parts = []
    if date:
        parts.append(f"{date} UTC")
    if magnitude is not None:
        parts.append(f"Mw {float(magnitude):.1f}")
    if place:
        parts.append(str(place))
    return "  ".join(parts)


def choose_vertical_spacing_cm(plot_data: PlotData, requested_spacing_cm: float | None) -> float:
    if requested_spacing_cm is not None:
        if requested_spacing_cm <= 0:
            raise ValueError("--vertical-spacing-cm must be positive")
        return requested_spacing_cm

    values = np.concatenate(
        [trace["value_cm"].to_numpy(dtype=float) for trace in plot_data.traces.values()]
    )
    finite_abs = np.abs(values[np.isfinite(values)])
    if finite_abs.size == 0:
        return 2.0
    robust_amplitude = float(np.percentile(finite_abs, 98.0))
    return max(2.0, robust_amplitude * 3.2)


def _station_pgd_from_record(
    station: str,
    raw_pgd: dict[str, float],
    *,
    distance_km: float,
    min_pgd_snr: float,
    quality_max_pgd_time_offset: float,
    quality_max_distance_km: float,
) -> StationPGD:
    usable, quality_flags = station_quality_flags(
        raw_pgd,
        distance_km,
        min_pgd_snr=min_pgd_snr,
        quality_max_pgd_time_offset=quality_max_pgd_time_offset,
        quality_max_distance_km=quality_max_distance_km,
    )
    return StationPGD(
        station=station,
        pgd_cm=float(raw_pgd["pgd_cm"]),
        east_cm_at_peak=float(raw_pgd["pgd_e_m"]) * 100.0,
        north_cm_at_peak=float(raw_pgd["pgd_n_m"]) * 100.0,
        vertical_cm_at_peak=float(raw_pgd["pgd_u_m"]) * 100.0,
        time_offset_s=float(raw_pgd["pgd_time_offset_s"]),
        snr=float(raw_pgd["pgd_snr"]),
        quality_flags=quality_flags,
        usable=usable,
    )


def find_max_usable_station_pgd(
    stations: list[StationPlotInfo],
    pgd_by_station: dict[str, dict[str, float]],
    *,
    min_pgd_snr: float,
    quality_max_pgd_time_offset: float,
    quality_max_distance_km: float,
) -> StationPGD | None:
    best: StationPGD | None = None
    for row in stations:
        raw_pgd = pgd_by_station.get(row.station)
        if raw_pgd is None:
            continue
        pgd = _station_pgd_from_record(
            row.station,
            raw_pgd,
            distance_km=row.distance_km,
            min_pgd_snr=min_pgd_snr,
            quality_max_pgd_time_offset=quality_max_pgd_time_offset,
            quality_max_distance_km=quality_max_distance_km,
        )
        if not pgd.usable:
            continue
        if best is None or pgd.pgd_cm > best.pgd_cm:
            best = pgd
    return best


def pgd_label(pgd: StationPGD) -> str:
    return f"PGD = {pgd.pgd_cm:.2f} cm"


def _station_label_size(count: int) -> float:
    return max(5.8, min(8.2, 10.0 - 0.08 * count))


def _nice_scale_cm(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = np.floor(np.log10(value))
    base = value / (10**exponent)
    if base <= 1:
        nice = 1.0
    elif base <= 2:
        nice = 2.0
    elif base <= 5:
        nice = 5.0
    else:
        nice = 10.0
    return float(nice * (10**exponent))


def _format_cm(value: float) -> str:
    if value >= 1:
        return f"{value:g} cm"
    return f"{value * 10:g} mm"


def set_paper_style() -> None:
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_fonts = ["Times New Roman", "Noto Serif CJK SC", "SimSun", "DejaVu Serif"]
    font_family = [name for name in preferred_fonts if name in available_fonts] or ["DejaVu Serif"]
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": font_family,
            "axes.edgecolor": "black",
            "axes.linewidth": 0.9,
            "xtick.color": "black",
            "ytick.color": "black",
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "savefig.facecolor": "white",
        }
    )


def plot_displacement_timeseries(
    plot_data: PlotData,
    event: dict,
    out_path: Path,
    *,
    max_station_pgd: StationPGD | None = None,
    dpi: int = 300,
    vertical_spacing_cm: float | None = None,
    scale_bar_cm: float | None = 5.0,
    line_width: float = 0.55,
    show: bool = False,
) -> Path:
    set_paper_style()
    spacing_cm = choose_vertical_spacing_cm(plot_data, vertical_spacing_cm)
    scale_cm = _nice_scale_cm(spacing_cm / 8.0) if scale_bar_cm is None else scale_bar_cm
    if scale_cm <= 0:
        raise ValueError("--scale-bar-cm must be positive")
    peak_station = max_station_pgd.station if max_station_pgd is not None else None
    station_count = len(plot_data.stations)
    height = min(11.0, max(6.2, 2.5 + 0.24 * station_count))
    fig, axes = plt.subplots(1, 3, figsize=(14.0, height), sharex=True, sharey=True)
    y_slots = {
        row.station: (station_count - 1 - index) * spacing_cm
        for index, row in enumerate(plot_data.stations)
    }
    y_values = list(y_slots.values())
    y_pad = max(spacing_cm, scale_cm * 1.6, 1.0)
    x_range = plot_data.time_end - plot_data.time_start
    text_pad = max(8.0, x_range * 0.025)
    label_size = _station_label_size(station_count)

    for ax, component in zip(axes, COMPONENTS, strict=True):
        for row in plot_data.stations:
            trace = plot_data.traces.get((row.station, component))
            if trace is None or trace.empty:
                continue
            slot = y_slots[row.station]
            is_peak_station = row.station == peak_station
            ax.plot(
                trace["time_s"],
                trace["value_cm"] + slot,
                color="#c00000" if is_peak_station else "black",
                linewidth=line_width * 1.7 if is_peak_station else line_width,
                solid_capstyle="round",
                rasterized=True,
            )

        ax.set_title(COMPONENT_TITLES[component], fontsize=13, fontweight="bold", pad=8)
        ax.set_xlabel(origin_time_text(event), fontsize=9.5, fontweight="bold")
        ax.set_xlim(plot_data.time_start, plot_data.time_end)
        ax.set_ylim(min(y_values) - y_pad, max(y_values) + y_pad)
        ax.set_xticks(np.arange(plot_data.time_start, plot_data.time_end + 0.1, 100.0))
        ax.set_yticks([y_slots[row.station] for row in plot_data.stations])
        ax.grid(axis="x", color="#d6d6d6", linewidth=0.6)
        ax.grid(axis="y", visible=False)
        ax.tick_params(labelsize=8.5, length=3.8)
        ax.tick_params(axis="y", labelleft=False)
        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(0.9)

    scale_x = plot_data.time_start + x_range * 0.045
    scale_y = min(y_values) - y_pad * 0.72
    axes[0].plot([scale_x, scale_x], [scale_y, scale_y + scale_cm], color="black", linewidth=1.4)
    axes[0].text(
        scale_x + x_range * 0.015,
        scale_y + scale_cm / 2.0,
        _format_cm(scale_cm),
        ha="left",
        va="center",
        fontsize=8.0,
        fontweight="bold",
        color="black",
    )

    left_ax = axes[0]
    right_ax = axes[-1]
    for row in plot_data.stations:
        slot = y_slots[row.station]
        is_peak_station = row.station == peak_station
        left_ax.text(
            plot_data.time_start - text_pad,
            slot,
            row.station,
            ha="right",
            va="center",
            fontsize=label_size + 0.7 if is_peak_station else label_size,
            fontweight="bold",
            color="#c00000" if is_peak_station else "black",
            clip_on=False,
        )
        right_ax.text(
            plot_data.time_end + text_pad,
            slot,
            f"{row.distance_km:.0f} km",
            ha="left",
            va="center",
            fontsize=label_size,
            fontweight="bold",
            color="#c00000" if is_peak_station else "black",
            clip_on=False,
        )
        if max_station_pgd is not None and is_peak_station:
            left_ax.text(
                plot_data.time_start + x_range * 0.025,
                slot + spacing_cm * 0.25,
                pgd_label(max_station_pgd),
                ha="left",
                va="center",
                fontsize=label_size + 0.5,
                fontweight="bold",
                color="#c00000",
                clip_on=False,
            )

    title = event_title(event)
    if title:
        fig.suptitle(title, fontsize=11.5, fontweight="bold", y=0.985)
    fig.subplots_adjust(left=0.105, right=0.905, bottom=0.105, top=0.92, wspace=0.11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)
    print(f"saved: {out_path}")
    return out_path


def default_output_path(event_dir: Path, outdir: Path) -> Path:
    return outdir / f"{event_dir.name}_displacement_timeseries.png"


def main() -> None:
    args = parse_args()
    event_dir = args.event_dir
    event = load_event(event_dir)
    stations = load_stations(event_dir)
    waveforms = load_waveforms(event_dir)
    plot_data = prepare_plot_data(
        stations,
        waveforms,
        time_start=args.time_start,
        time_end=args.time_end,
        baseline_seconds=args.baseline_seconds,
        max_stations=args.max_stations,
    )
    max_station_pgd = None
    if args.highlight_max_pgd:
        pgd_by_station = read_pgd_by_station(
            event_dir / "waveforms.csv.gz",
            args.time_start,
            args.time_end,
            args.min_pgd_m,
            "3d",
            args.noise_window_start,
            args.noise_window_end,
        )
        max_station_pgd = find_max_usable_station_pgd(
            plot_data.stations,
            pgd_by_station,
            min_pgd_snr=args.min_pgd_snr,
            quality_max_pgd_time_offset=args.quality_max_pgd_time_offset,
            quality_max_distance_km=args.quality_max_distance_km,
        )
        if max_station_pgd is None:
            print("warning: no usable PGD station passed quality filters; no red PGD highlight will be drawn")
    out_path = args.out if args.out else default_output_path(event_dir, args.outdir)
    plot_displacement_timeseries(
        plot_data,
        event,
        out_path,
        max_station_pgd=max_station_pgd,
        dpi=args.dpi,
        vertical_spacing_cm=args.vertical_spacing_cm,
        scale_bar_cm=args.scale_bar_cm,
        line_width=args.line_width,
        show=args.show,
    )


if __name__ == "__main__":
    main()
