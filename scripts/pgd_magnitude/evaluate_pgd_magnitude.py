#!/usr/bin/env python3
"""Evaluate GNSS PGD magnitude scaling against catalog magnitudes."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ScalingLaw:
    name: str
    a: float
    b: float
    c: float
    pgd_unit: str


SCALING_LAWS = [
    ScalingLaw("melgar_2015", -4.434, 1.047, -0.138, "cm"),
    ScalingLaw("crowell_2016_gfast", -6.687, 1.500, -0.214, "cm"),
    ScalingLaw("ruhl_2019", -5.919, 1.009, -0.145, "m"),
]

TARGET_COUNTRIES = {"United States", "New Zealand", "Mexico"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-root", type=Path, default=Path("exports/normalized-ok-stations-us-nz"))
    parser.add_argument("--out-root", type=Path, default=Path("reports/pgd_magnitude"))
    parser.add_argument("--figure-root", type=Path, default=Path("figure/pgd_magnitude"))
    parser.add_argument("--countries", nargs="*", default=sorted(TARGET_COUNTRIES))
    parser.add_argument("--pgd-window-start", type=float, default=0.0)
    parser.add_argument("--pgd-window-end", type=float, default=600.0)
    parser.add_argument("--pgd-component", choices=["3d", "horizontal"], default="3d")
    parser.add_argument("--distance", choices=["hypocentral", "epicentral"], default="hypocentral")
    parser.add_argument("--station-aggregation", choices=["median", "mean", "trimmed-mean"], default="median")
    parser.add_argument("--trim-fraction", type=float, default=0.20)
    parser.add_argument("--max-pgd-time-offset", type=float, default=0.0)
    parser.add_argument("--min-distance-km", type=float, default=1.0)
    parser.add_argument("--max-distance-km", type=float, default=0.0)
    parser.add_argument("--min-pgd-m", type=float, default=1e-6)
    parser.add_argument("--min-stations", type=int, default=1)
    parser.add_argument("--calibration", choices=["none", "leave-one-out-country-linear"], default="none")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_stations(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        return {row["Station"].upper(): row for row in csv.DictReader(handle)}


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def iter_event_dirs(root: Path, countries: set[str]) -> Iterable[Path]:
    for event_json in sorted(root.glob("*/event.json")):
        event = load_json(event_json)
        if event.get("country") in countries:
            station_path = event_json.parent / "stations.csv"
            waveform_path = event_json.parent / "waveforms.csv.gz"
            if station_path.exists() and waveform_path.exists():
                yield event_json.parent


def read_pgd_by_station(
    waveform_path: Path,
    window_start: float,
    window_end: float,
    min_pgd_m: float,
    pgd_component: str,
) -> dict[str, dict[str, float]]:
    components: dict[str, dict[float, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    with gzip.open(waveform_path, "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            offset = finite_float(row.get("Time_Offset_s"))
            if not math.isfinite(offset) or offset < window_start or offset > window_end:
                continue
            component = str(row.get("Component") or "").upper()
            if component not in {"E", "N", "U"}:
                continue
            value = finite_float(row.get("Value_m"))
            if not math.isfinite(value):
                continue
            station = str(row.get("Station") or "").upper()
            components[station][offset][component] = value

    result: dict[str, dict[str, float]] = {}
    for station, by_time in components.items():
        pgd_m = math.nan
        pgd_time = math.nan
        pgd_e = math.nan
        pgd_n = math.nan
        pgd_u = math.nan
        sample_count = 0
        for offset, values in by_time.items():
            if not {"E", "N", "U"}.issubset(values):
                continue
            sample_count += 1
            e = values["E"]
            n = values["N"]
            u = values["U"]
            amplitude = math.hypot(e, n) if pgd_component == "horizontal" else math.sqrt(e * e + n * n + u * u)
            if not math.isfinite(pgd_m) or amplitude > pgd_m:
                pgd_m = amplitude
                pgd_time = offset
                pgd_e = e
                pgd_n = n
                pgd_u = u
        if math.isfinite(pgd_m) and pgd_m >= min_pgd_m:
            result[station] = {
                "pgd_m": pgd_m,
                "pgd_cm": pgd_m * 100.0,
                "pgd_time_offset_s": pgd_time,
                "pgd_e_m": pgd_e,
                "pgd_n_m": pgd_n,
                "pgd_u_m": pgd_u,
                "pgd_sample_count": float(sample_count),
            }
    return result


def estimate_magnitude(law: ScalingLaw, pgd_m: float, distance_km: float) -> float:
    pgd = pgd_m if law.pgd_unit == "m" else pgd_m * 100.0
    if pgd <= 0 or distance_km <= 0:
        return math.nan
    denominator = law.b + law.c * math.log10(distance_km)
    if denominator == 0:
        return math.nan
    return (math.log10(pgd) - law.a) / denominator


def median(values: list[float]) -> float:
    return statistics.median(values) if values else math.nan


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def trimmed_mean(values: list[float], trim_fraction: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    trim_count = int(len(ordered) * max(0.0, min(trim_fraction, 0.45)))
    trimmed = ordered[trim_count : len(ordered) - trim_count] if trim_count else ordered
    return mean(trimmed or ordered)


def aggregate_station_estimates(values: list[float], method: str, trim_fraction: float) -> float:
    if method == "mean":
        return mean(values)
    if method == "trimmed-mean":
        return trimmed_mean(values, trim_fraction)
    return median(values)


def rmse(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else math.nan


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(xs) < 2:
        return 0.0, 1.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    variance = sum((x - x_mean) ** 2 for x in xs)
    if variance == 0:
        return y_mean, 0.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / variance
    return y_mean - slope * x_mean, slope


def apply_leave_one_out_calibration(event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in event_rows:
        groups[(str(row["country"]), str(row["formula"]))].append(row)

    calibrated: list[dict[str, object]] = []
    for (_country, _formula), rows in groups.items():
        all_x = [float(row["estimated_mw_median"]) for row in rows]
        all_y = [float(row["usgs_magnitude"]) for row in rows]
        full_intercept, full_slope = linear_fit(all_x, all_y)
        for i, row in enumerate(rows):
            train_x = all_x[:i] + all_x[i + 1 :]
            train_y = all_y[:i] + all_y[i + 1 :]
            intercept, slope = linear_fit(train_x, train_y)
            estimated = intercept + slope * float(row["estimated_mw_median"])
            updated = dict(row)
            updated["raw_estimated_mw_median"] = row["estimated_mw_median"]
            updated["raw_residual_mw"] = row["residual_mw"]
            updated["estimated_mw_median"] = estimated
            updated["estimated_mw_p16"] = ""
            updated["estimated_mw_p84"] = ""
            updated["residual_mw"] = estimated - float(row["usgs_magnitude"])
            updated["abs_residual_mw"] = abs(float(updated["residual_mw"]))
            updated["calibration"] = "leave_one_out_country_linear"
            updated["calibration_intercept"] = intercept
            updated["calibration_slope"] = slope
            updated["full_sample_calibration_intercept"] = full_intercept
            updated["full_sample_calibration_slope"] = full_slope
            calibrated.append(updated)
    return calibrated


def fmt(value: object, digits: int = 6) -> str:
    if isinstance(value, int):
        return str(value)
    number = finite_float(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}"


def evaluate_event(event_dir: Path, args: argparse.Namespace) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    event = load_json(event_dir / "event.json")
    magnitude = finite_float(event.get("magnitude"))
    depth_km = finite_float(event.get("depth_km"))
    if not math.isfinite(magnitude):
        return [], []

    stations = read_stations(event_dir / "stations.csv")
    pgd_by_station = read_pgd_by_station(
        event_dir / "waveforms.csv.gz",
        args.pgd_window_start,
        args.pgd_window_end,
        args.min_pgd_m,
        args.pgd_component,
    )
    station_rows: list[dict[str, object]] = []
    by_law: dict[str, list[float]] = defaultdict(list)

    for station, pgd in pgd_by_station.items():
        station_meta = stations.get(station)
        if not station_meta:
            continue
        epicentral_distance_km = finite_float(station_meta.get("Distance_Km"))
        if not math.isfinite(epicentral_distance_km):
            continue
        hypocentral_distance_km = math.sqrt(epicentral_distance_km**2 + depth_km**2) if math.isfinite(depth_km) else epicentral_distance_km
        distance_km = hypocentral_distance_km if args.distance == "hypocentral" else epicentral_distance_km
        distance_km = max(distance_km, args.min_distance_km)
        if args.max_distance_km > 0 and distance_km > args.max_distance_km:
            continue
        if args.max_pgd_time_offset > 0 and float(pgd["pgd_time_offset_s"]) > args.max_pgd_time_offset:
            continue
        for law in SCALING_LAWS:
            mw_estimate = estimate_magnitude(law, float(pgd["pgd_m"]), distance_km)
            if not math.isfinite(mw_estimate):
                continue
            residual = mw_estimate - magnitude
            by_law[law.name].append(mw_estimate)
            station_rows.append(
                {
                    "event_dir": event_dir.name,
                    "event_id": event.get("event_id") or event.get("usgs_event_id") or "",
                    "event_time": event.get("date") or "",
                    "country": event.get("country") or "",
                    "place": event.get("place") or event.get("event") or "",
                    "usgs_magnitude": magnitude,
                    "depth_km": depth_km,
                    "station": station,
                    "station_quality_status": station_meta.get("Quality_Status", ""),
                    "epicentral_distance_km": epicentral_distance_km,
                    "hypocentral_distance_km": distance_km,
                    "pgd_m": pgd["pgd_m"],
                    "pgd_cm": pgd["pgd_cm"],
                    "pgd_time_offset_s": pgd["pgd_time_offset_s"],
                    "pgd_e_m": pgd["pgd_e_m"],
                    "pgd_n_m": pgd["pgd_n_m"],
                    "pgd_u_m": pgd["pgd_u_m"],
                    "pgd_sample_count": int(pgd["pgd_sample_count"]),
                    "formula": law.name,
                    "formula_pgd_unit": law.pgd_unit,
                    "pgd_component": args.pgd_component,
                    "distance_mode": args.distance,
                    "station_aggregation": args.station_aggregation,
                    "estimated_mw": mw_estimate,
                    "residual_mw": residual,
                    "abs_residual_mw": abs(residual),
                }
            )

    event_rows: list[dict[str, object]] = []
    for law_name, estimates in by_law.items():
        if len(estimates) < args.min_stations:
            continue
        event_estimate = aggregate_station_estimates(estimates, args.station_aggregation, args.trim_fraction)
        residuals = [value - magnitude for value in estimates]
        event_rows.append(
            {
                "event_dir": event_dir.name,
                "event_id": event.get("event_id") or event.get("usgs_event_id") or "",
                "event_time": event.get("date") or "",
                "country": event.get("country") or "",
                "place": event.get("place") or event.get("event") or "",
                "usgs_magnitude": magnitude,
                "depth_km": depth_km,
                "formula": law_name,
                "pgd_component": args.pgd_component,
                "distance_mode": args.distance,
                "station_aggregation": args.station_aggregation,
                "station_count": len(estimates),
                "estimated_mw_median": event_estimate,
                "estimated_mw_p16": percentile(estimates, 0.16),
                "estimated_mw_p84": percentile(estimates, 0.84),
                "residual_mw": event_estimate - magnitude,
                "abs_residual_mw": abs(event_estimate - magnitude),
                "station_residual_mean": mean(residuals),
                "station_residual_rmse": rmse(residuals),
            }
        )
    return station_rows, event_rows


def write_table(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field), 6) if isinstance(row.get(field), float) else row.get(field, "") for field in fieldnames})


def summarize(event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in event_rows:
        groups[(str(row["country"]), str(row["formula"]))].append(row)
    groups[("ALL", "")]
    summary_rows: list[dict[str, object]] = []
    for (country, formula), rows in sorted(groups.items()):
        if not rows:
            continue
        residuals = [float(row["residual_mw"]) for row in rows]
        abs_residuals = [abs(value) for value in residuals]
        summary_rows.append(
            {
                "country": country,
                "formula": formula,
                "event_count": len(rows),
                "bias_mw": mean(residuals),
                "mae_mw": mean(abs_residuals),
                "rmse_mw": rmse(residuals),
                "median_abs_error_mw": median(abs_residuals),
            }
        )
    formulas = sorted({str(row["formula"]) for row in event_rows})
    for formula in formulas:
        rows = [row for row in event_rows if row["formula"] == formula]
        residuals = [float(row["residual_mw"]) for row in rows]
        abs_residuals = [abs(value) for value in residuals]
        summary_rows.append(
            {
                "country": "ALL",
                "formula": formula,
                "event_count": len(rows),
                "bias_mw": mean(residuals),
                "mae_mw": mean(abs_residuals),
                "rmse_mw": rmse(residuals),
                "median_abs_error_mw": median(abs_residuals),
            }
        )
    return summary_rows


def svg_escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2.0
    return dst_min + (value - src_min) * (dst_max - dst_min) / (src_max - src_min)


def write_svg(path: Path, width: int, height: int, body: list[str]) -> None:
    text = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def write_plots(event_rows: list[dict[str, object]], summary_rows: list[dict[str, object]], figure_root: Path) -> None:
    figure_root.mkdir(parents=True, exist_ok=True)
    formulas = [law.name for law in SCALING_LAWS]
    countries = sorted({str(row["country"]) for row in event_rows})
    colors = {"melgar_2015": "#4c78a8", "crowell_2016_gfast": "#f58518", "ruhl_2019": "#54a24b"}
    labels = {law.name: law.name.replace("_", " ") for law in SCALING_LAWS}

    panel_w = 320
    width = 80 + panel_w * len(countries)
    height = 360
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">GNSS PGD Mw vs USGS Mw</text>']
    for i, country in enumerate(countries):
        left = 55 + i * panel_w
        top = 55
        plot_w = 240
        plot_h = 240
        body.append(f'<text x="{left + plot_w / 2:.1f}" y="48" text-anchor="middle" font-size="14" font-family="sans-serif">{svg_escape(country)}</text>')
        body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
        for tick in [6.0, 7.0, 8.0, 9.0]:
            x = scale(tick, 5.5, 9.2, left, left + plot_w)
            y = scale(tick, 5.5, 9.2, top + plot_h, top)
            body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#ddd"/>')
            body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#ddd"/>')
            body.append(f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" font-size="10" font-family="sans-serif">{tick:.0f}</text>')
            if i == 0:
                body.append(f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" font-family="sans-serif">{tick:.0f}</text>')
        body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top}" stroke="#444" stroke-dasharray="4 4"/>')
        for formula in formulas:
            rows = [row for row in event_rows if row["country"] == country and row["formula"] == formula]
            for row in rows:
                x = scale(float(row["usgs_magnitude"]), 5.5, 9.2, left, left + plot_w)
                y = scale(float(row["estimated_mw_median"]), 5.5, 9.2, top + plot_h, top)
                body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colors[formula]}" fill-opacity="0.75"><title>{svg_escape(row["event_id"])} {labels[formula]}</title></circle>')
    for j, formula in enumerate(formulas):
        y = 320 + j * 16
        body.append(f'<circle cx="{width - 190}" cy="{y - 4}" r="4" fill="{colors[formula]}"/>')
        body.append(f'<text x="{width - 178}" y="{y}" font-size="11" font-family="sans-serif">{labels[formula]}</text>')
    write_svg(figure_root / "estimated_vs_usgs_by_region.svg", width, height, body)

    entries = []
    for country in countries + ["ALL"]:
        for formula in formulas:
            row = next((item for item in summary_rows if item["country"] == country and item["formula"] == formula), None)
            if row:
                entries.append((country, formula, float(row["mae_mw"])))
    width = max(760, 70 * len(entries) + 100)
    height = 420
    left = 60
    top = 45
    plot_w = width - 90
    plot_h = 260
    max_value = max([value for _, _, value in entries] + [1.0])
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">PGD method MAE by region</text>']
    body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
    for tick in [0.0, max_value / 2.0, max_value]:
        y = scale(tick, 0.0, max_value, top + plot_h, top)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#ddd"/>')
        body.append(f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" font-family="sans-serif">{tick:.2f}</text>')
    bar_w = plot_w / max(len(entries), 1) * 0.72
    for i, (country, formula, value) in enumerate(entries):
        center = left + (i + 0.5) * plot_w / len(entries)
        bar_h = scale(value, 0.0, max_value, 0.0, plot_h)
        body.append(f'<rect x="{center - bar_w / 2:.1f}" y="{top + plot_h - bar_h:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{colors[formula]}"><title>{svg_escape(country)} {labels[formula]} MAE={value:.3f}</title></rect>')
        body.append(f'<text x="{center:.1f}" y="{top + plot_h + 15}" text-anchor="middle" font-size="9" font-family="sans-serif" transform="rotate(55 {center:.1f} {top + plot_h + 15})">{svg_escape(country)} {labels[formula]}</text>')
    write_svg(figure_root / "method_mae_by_region.svg", width, height, body)

    width = 760
    height = 420
    left = 70
    top = 45
    plot_w = 610
    plot_h = 290
    residuals = [float(row["residual_mw"]) for row in event_rows]
    y_min = min([-2.0] + residuals)
    y_max = max([2.0] + residuals)
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">PGD Mw residual vs USGS Mw</text>']
    body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
    zero_y = scale(0.0, y_min, y_max, top + plot_h, top)
    body.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left + plot_w}" y2="{zero_y:.1f}" stroke="#444" stroke-dasharray="4 4"/>')
    for formula in formulas:
        rows = [row for row in event_rows if row["formula"] == formula]
        for row in rows:
            x = scale(float(row["usgs_magnitude"]), 5.5, 9.2, left, left + plot_w)
            y = scale(float(row["residual_mw"]), y_min, y_max, top + plot_h, top)
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colors[formula]}" fill-opacity="0.75"><title>{svg_escape(row["event_id"])} residual={float(row["residual_mw"]):.3f}</title></circle>')
    for j, formula in enumerate(formulas):
        y = 360 + j * 16
        body.append(f'<circle cx="560" cy="{y - 4}" r="4" fill="{colors[formula]}"/>')
        body.append(f'<text x="572" y="{y}" font-size="11" font-family="sans-serif">{labels[formula]}</text>')
    write_svg(figure_root / "residual_vs_usgs_magnitude.svg", width, height, body)


def main() -> int:
    args = parse_args()
    countries = set(args.countries)
    station_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for event_dir in iter_event_dirs(args.normalized_root, countries):
        event_station_rows, event_event_rows = evaluate_event(event_dir, args)
        station_rows.extend(event_station_rows)
        event_rows.extend(event_event_rows)

    station_fields = [
        "event_dir",
        "event_id",
        "event_time",
        "country",
        "place",
        "usgs_magnitude",
        "depth_km",
        "station",
        "station_quality_status",
        "epicentral_distance_km",
        "hypocentral_distance_km",
        "pgd_m",
        "pgd_cm",
        "pgd_time_offset_s",
        "pgd_e_m",
        "pgd_n_m",
        "pgd_u_m",
        "pgd_sample_count",
        "formula",
        "formula_pgd_unit",
        "pgd_component",
        "distance_mode",
        "station_aggregation",
        "estimated_mw",
        "residual_mw",
        "abs_residual_mw",
    ]
    event_fields = [
        "event_dir",
        "event_id",
        "event_time",
        "country",
        "place",
        "usgs_magnitude",
        "depth_km",
        "formula",
        "pgd_component",
        "distance_mode",
        "station_aggregation",
        "station_count",
        "estimated_mw_median",
        "estimated_mw_p16",
        "estimated_mw_p84",
        "residual_mw",
        "abs_residual_mw",
        "station_residual_mean",
        "station_residual_rmse",
        "raw_estimated_mw_median",
        "raw_residual_mw",
        "calibration",
        "calibration_intercept",
        "calibration_slope",
        "full_sample_calibration_intercept",
        "full_sample_calibration_slope",
    ]
    summary_fields = ["country", "formula", "event_count", "bias_mw", "mae_mw", "rmse_mw", "median_abs_error_mw"]

    raw_event_rows = event_rows
    raw_summary_rows = summarize(raw_event_rows)
    if args.calibration == "leave-one-out-country-linear":
        event_rows = apply_leave_one_out_calibration(raw_event_rows)
    summary_rows = summarize(event_rows)

    write_table(args.out_root / "station_pgd_magnitude.tsv", station_rows, station_fields)
    write_table(args.out_root / "event_pgd_magnitude_raw.tsv", raw_event_rows, event_fields)
    write_table(args.out_root / "method_summary_raw.tsv", raw_summary_rows, summary_fields)
    write_table(args.out_root / "event_pgd_magnitude.tsv", event_rows, event_fields)
    write_table(args.out_root / "method_summary.tsv", summary_rows, summary_fields)
    if event_rows:
        write_plots(event_rows, summary_rows, args.figure_root)

    payload = {
        "event_rows": len(event_rows),
        "station_rows": len(station_rows),
        "summary_rows": len(summary_rows),
        "raw_summary_rows": len(raw_summary_rows),
        "calibration": args.calibration,
        "out_root": str(args.out_root),
        "figure_root": str(args.figure_root),
        "pgd_window_seconds": [args.pgd_window_start, args.pgd_window_end],
        "pgd_component": args.pgd_component,
        "distance_mode": args.distance,
        "station_aggregation": args.station_aggregation,
        "max_distance_km": args.max_distance_km,
        "max_pgd_time_offset": args.max_pgd_time_offset,
        "countries": sorted(countries),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if event_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
