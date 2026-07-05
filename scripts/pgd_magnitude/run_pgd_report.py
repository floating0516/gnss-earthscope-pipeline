#!/usr/bin/env python3
"""Run the normalized-export PGD magnitude report target."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_pgd_magnitude as pgd


STALE_PRE_MEDIAN_CONTRACT_OUTPUTS = [
    "method_comparison.csv",
    "method_comparison.md",
    "method_summary.csv",
    "method_summary_raw.csv",
    "method_summary_by_magnitude_bin.csv",
    "method_summary_quality_filtered_by_magnitude_bin.csv",
]
STALE_PRE_MEDIAN_CONTRACT_FIGURES = ["method_mae_by_region.svg"]

STATION_FIELDS = [
    "event_dir",
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
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
    "pre_event_rms_m",
    "pre_event_rms_cm",
    "noise_sample_count",
    "pgd_snr",
    "usable_for_pgd",
    "station_reliability_flags",
    "near_station",
    "formula",
    "formula_pgd_unit",
    "pgd_component",
    "distance_mode",
    "station_aggregation",
    "estimated_mw",
    "residual_mw",
    "abs_residual_mw",
]

EVENT_FIELDS = [
    "event_dir",
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
    "place",
    "usgs_magnitude",
    "depth_km",
    "formula",
    "pgd_component",
    "distance_mode",
    "station_aggregation",
    "station_count",
    "usable_station_count",
    "near_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "pgd_reliability",
    "reliability_flags",
    "estimated_mw_median",
    "estimated_mw_p16",
    "estimated_mw_p84",
    "residual_mw",
    "abs_residual_mw",
    "usable_estimated_mw_median",
    "usable_residual_mw",
    "usable_abs_residual_mw",
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

RESIDUAL_FIELDS = [
    "event_id",
    "event_time",
    "country",
    "place",
    "formula",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
]

REVIEW_FIELDS = [
    "review_status",
    "suspected_cause",
    "waveform_issue",
    "station_geometry_issue",
    "magnitude_metadata_issue",
    "formula_limitation",
    "reviewer_note",
]

SUMMARY_FIELDS = ["country", "formula", "event_count", "bias_mw", "mae_mw", "rmse_mw", "median_abs_error_mw"]

BIN_SUMMARY_FIELDS = ["magnitude_bin", "formula", "quality_filter", "event_count", "bias_mw", "mae_mw", "rmse_mw", "median_abs_error_mw"]

INCLUSION_FIELDS = [
    "event_dir",
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
    "magnitude",
    "pgd_status",
    "exclusion_reason",
    "detail",
    "waveform_rows",
    "station_count",
    "distance_station_count",
    "pgd_candidate_station_count",
    "formula_count",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "reliability_flags",
]

COMPARISON_FIELDS = [
    "comparison_group",
    "comparison_value",
    "formula",
    "station_aggregation",
    "event_count",
    "high_medium_reliability_events",
    "low_reliability_events",
    "residual_outlier_count",
    "bias_mw",
    "mae_mw",
    "rmse_mw",
    "median_abs_error_mw",
]

RESIDUAL_REVIEW_FIELDS = [*RESIDUAL_FIELDS, *REVIEW_FIELDS]

RELEASE_SET_FIELDS = [
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
    "place",
    "formula",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "release_status",
    "release_candidate",
    "release_ready",
    "review_required",
    "release_failure_reasons",
    "release_review_reasons",
    "release_notes",
]

SCIENCE_RELEASE_FIELDS = [
    "event_id",
    "event_time",
    "country",
    "region",
    "place",
    "formula",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "release_status",
]

SCIENCE_FIGURE_FIELDS = ["figure_type", "path", "role"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for PGD report products.")
    parser.add_argument("--countries", nargs="*", default=sorted(pgd.TARGET_COUNTRIES))
    parser.add_argument("--pgd-window-start", type=float, default=0.0)
    parser.add_argument("--pgd-window-end", type=float, default=600.0)
    parser.add_argument("--pgd-component", choices=["3d", "horizontal"], default="3d")
    parser.add_argument("--distance", choices=["hypocentral", "epicentral"], default="hypocentral")
    parser.add_argument("--station-aggregation", choices=[pgd.STATION_AGGREGATION], default=pgd.STATION_AGGREGATION)
    parser.add_argument("--max-pgd-time-offset", type=float, default=0.0)
    parser.add_argument("--noise-window-start", type=float, default=-300.0)
    parser.add_argument("--noise-window-end", type=float, default=0.0)
    parser.add_argument("--min-pgd-snr", type=float, default=3.0)
    parser.add_argument("--near-distance-km", type=float, default=300.0)
    parser.add_argument("--min-distance-km", type=float, default=1.0)
    parser.add_argument("--max-distance-km", type=float, default=0.0)
    parser.add_argument("--quality-max-distance-km", type=float, default=500.0)
    parser.add_argument("--quality-max-pgd-time-offset", type=float, default=300.0)
    parser.add_argument("--min-pgd-m", type=float, default=1e-6)
    parser.add_argument("--min-stations", type=int, default=1)
    parser.add_argument("--calibration", choices=["none", "leave-one-out-country-linear"], default="none")
    parser.add_argument("--outlier-limit", type=int, default=20, help="Maximum largest-residual rows to include in residual_outliers.csv and summary.md.")
    parser.add_argument("--residual-review-threshold", type=float, default=1.0, help="Absolute Mw residual threshold counted in formula comparison review metrics.")
    parser.add_argument("--release-min-usable-stations", type=int, default=3, help="Minimum usable station count for the PGD release candidate gate.")
    parser.add_argument("--release-allowed-reliability", nargs="*", choices=["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM"])
    parser.add_argument("--release-min-median-snr", type=float, default=3.0, help="Minimum median PGD SNR for the PGD release candidate gate.")
    parser.add_argument("--release-max-median-distance-km", type=float, default=300.0, help="Maximum median event-station distance for the PGD release candidate gate; use 0 to disable.")
    parser.add_argument("--release-residual-review-threshold", type=float, default=None, help="Absolute Mw residual threshold that marks a candidate for review without excluding it.")
    return parser.parse_args(argv)


def evaluator_args(args: argparse.Namespace, figure_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        normalized_root=args.export_root,
        out_root=args.out_dir,
        figure_root=figure_root,
        countries=args.countries,
        pgd_window_start=args.pgd_window_start,
        pgd_window_end=args.pgd_window_end,
        pgd_component=args.pgd_component,
        distance=args.distance,
        station_aggregation=pgd.STATION_AGGREGATION,
        max_pgd_time_offset=args.max_pgd_time_offset,
        noise_window_start=args.noise_window_start,
        noise_window_end=args.noise_window_end,
        min_pgd_snr=args.min_pgd_snr,
        near_distance_km=args.near_distance_km,
        min_distance_km=args.min_distance_km,
        max_distance_km=args.max_distance_km,
        quality_max_distance_km=args.quality_max_distance_km,
        quality_max_pgd_time_offset=args.quality_max_pgd_time_offset,
        min_pgd_m=args.min_pgd_m,
        min_stations=args.min_stations,
        calibration=args.calibration,
    )


def fmt_csv(value: object) -> object:
    if isinstance(value, float):
        return pgd.fmt(value, 6)
    return "" if value is None else value


def json_safe(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt_csv(row.get(field, "")) for field in fieldnames})


def remove_stale_pre_median_contract_outputs(out_dir: Path, figure_dir: Path) -> None:
    for name in STALE_PRE_MEDIAN_CONTRACT_OUTPUTS:
        path = out_dir / name
        if path.is_file():
            path.unlink()
    for name in STALE_PRE_MEDIAN_CONTRACT_FIGURES:
        path = figure_dir / name
        if path.is_file():
            path.unlink()


def residual_rows(event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{field: row.get(field, "") for field in RESIDUAL_FIELDS} for row in event_rows]


def residual_outliers(event_rows: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    rows = residual_rows(event_rows)

    def sort_key(row: dict[str, object]) -> tuple[float, str, str]:
        abs_residual = pgd.finite_float(row.get("abs_residual_mw"))
        sort_residual = abs_residual if math.isfinite(abs_residual) else -1.0
        return (-sort_residual, str(row.get("event_id") or ""), str(row.get("formula") or ""))

    return sorted(rows, key=sort_key)[: max(0, limit)]


def residual_review_key(row: dict[str, object]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("formula") or ""))


def load_existing_residual_reviews(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {residual_review_key(row): row for row in rows if all(residual_review_key(row))}


def residual_review_rows(outlier_rows: list[dict[str, object]], existing_path: Path) -> list[dict[str, object]]:
    existing = load_existing_residual_reviews(existing_path)
    rows: list[dict[str, object]] = []
    for outlier in outlier_rows:
        row = {field: outlier.get(field, "") for field in RESIDUAL_FIELDS}
        previous = existing.get(residual_review_key(outlier), {})
        for field in REVIEW_FIELDS:
            if field == "review_status":
                row[field] = previous.get(field) or "UNREVIEWED"
            else:
                row[field] = previous.get(field, "")
        rows.append(row)
    return rows


def event_time_value(event: dict[str, object]) -> str:
    return str(event.get("event_time") or event.get("date") or event.get("time_utc") or "")


def event_id_value(event: dict[str, object], event_dir: Path) -> str:
    return str(event.get("event_id") or event.get("usgs_event_id") or event_dir.name)


def iter_normalized_event_dirs(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob("*/event.json"))


def count_waveform_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with gzip.open(path, "rt", newline="") as handle:
            return sum(1 for _row in csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError):
        return 0


def finite_distance_station_count(stations: dict[str, dict[str, str]]) -> int:
    return sum(1 for row in stations.values() if math.isfinite(pgd.finite_float(row.get("Distance_Km"))))


def included_event_metrics(event_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in event_rows:
        event_id = str(row.get("event_id") or "")
        if event_id:
            grouped.setdefault(event_id, []).append(row)
    metrics: dict[str, dict[str, object]] = {}
    for event_id, rows in grouped.items():
        first = rows[0]
        metrics[event_id] = {
            "formula_count": len({str(row.get("formula") or "") for row in rows if row.get("formula")}),
            "station_count": first.get("station_count", ""),
            "usable_station_count": first.get("usable_station_count", ""),
            "pgd_reliability": first.get("pgd_reliability", ""),
            "median_pgd_snr": first.get("median_pgd_snr", ""),
            "median_distance_km": first.get("median_distance_km", ""),
            "reliability_flags": first.get("reliability_flags", ""),
        }
    return metrics


def base_inclusion_row(event_dir: Path, event: dict[str, object]) -> dict[str, object]:
    return {
        "event_dir": event_dir.name,
        "event_id": event_id_value(event, event_dir),
        "event_time": event_time_value(event),
        "country": pgd.event_country_value(event, event_dir),
        "region": pgd.event_region_value(event, event_dir),
        "source": event.get("source") or event.get("source_label") or "",
        "magnitude": event.get("magnitude") or "",
        "pgd_status": "",
        "exclusion_reason": "",
        "detail": "",
        "waveform_rows": "",
        "station_count": "",
        "distance_station_count": "",
        "pgd_candidate_station_count": "",
        "formula_count": "",
        "pgd_reliability": "",
        "usable_station_count": "",
        "median_pgd_snr": "",
        "median_distance_km": "",
        "reliability_flags": "",
    }


def classify_pgd_exclusion(
    event_dir: Path,
    event: dict[str, object],
    args: argparse.Namespace,
    eval_args: SimpleNamespace,
) -> dict[str, object]:
    row = base_inclusion_row(event_dir, event)
    country = str(pgd.event_country_value(event, event_dir) or "")
    if country not in set(args.countries):
        row.update(
            {
                "pgd_status": "EXCLUDED_PGD",
                "exclusion_reason": "FILTERED_BY_COUNTRY",
                "detail": f"country={country or 'unknown'} not in selected countries",
            }
        )
        return row

    if not math.isfinite(pgd.finite_float(event.get("magnitude"))):
        row.update({"pgd_status": "EXCLUDED_PGD", "exclusion_reason": "MISSING_MAGNITUDE", "detail": "event magnitude is missing or non-finite"})
        return row

    station_path = event_dir / "stations.csv"
    waveform_path = event_dir / "waveforms.csv.gz"
    missing = [path.name for path in [station_path, waveform_path] if not path.exists()]
    if missing:
        row.update({"pgd_status": "EXCLUDED_PGD", "exclusion_reason": "MISSING_PACKAGE_FILE", "detail": ",".join(missing)})
        return row

    stations = pgd.read_stations(station_path)
    row["station_count"] = len(stations)
    distance_count = finite_distance_station_count(stations)
    row["distance_station_count"] = distance_count
    if not stations:
        row.update({"pgd_status": "EXCLUDED_PGD", "exclusion_reason": "NO_STATIONS", "detail": "stations.csv has no station rows"})
        return row
    if distance_count == 0:
        row.update(
            {
                "pgd_status": "EXCLUDED_PGD",
                "exclusion_reason": "MISSING_DISTANCE_METADATA",
                "detail": "no station has finite Distance_Km",
            }
        )
        return row

    waveform_rows = count_waveform_rows(waveform_path)
    row["waveform_rows"] = waveform_rows
    if waveform_rows == 0:
        row.update({"pgd_status": "EXCLUDED_PGD", "exclusion_reason": "EMPTY_WAVEFORMS", "detail": "waveforms.csv.gz has no data rows"})
        return row

    pgd_by_station = pgd.read_pgd_by_station(
        waveform_path,
        eval_args.pgd_window_start,
        eval_args.pgd_window_end,
        eval_args.min_pgd_m,
        eval_args.pgd_component,
        eval_args.noise_window_start,
        eval_args.noise_window_end,
    )
    row["pgd_candidate_station_count"] = len(pgd_by_station)
    if not pgd_by_station:
        row.update(
            {
                "pgd_status": "EXCLUDED_PGD",
                "exclusion_reason": "BELOW_PGD_THRESHOLD",
                "detail": f"no station PGD reached min_pgd_m={eval_args.min_pgd_m}",
            }
        )
        return row

    usable_for_formula = 0
    for station, pgd_metrics in pgd_by_station.items():
        station_meta = stations.get(station)
        if not station_meta:
            continue
        epicentral_distance_km = pgd.finite_float(station_meta.get("Distance_Km"))
        if not math.isfinite(epicentral_distance_km):
            continue
        depth_km = pgd.finite_float(event.get("depth_km"))
        distance_km = math.sqrt(epicentral_distance_km**2 + depth_km**2) if math.isfinite(depth_km) else epicentral_distance_km
        distance_km = distance_km if eval_args.distance == "hypocentral" else epicentral_distance_km
        distance_km = max(distance_km, eval_args.min_distance_km)
        if eval_args.max_distance_km > 0 and distance_km > eval_args.max_distance_km:
            continue
        if eval_args.max_pgd_time_offset > 0 and float(pgd_metrics["pgd_time_offset_s"]) > eval_args.max_pgd_time_offset:
            continue
        usable_for_formula += 1
    if usable_for_formula < eval_args.min_stations:
        row.update(
            {
                "pgd_status": "EXCLUDED_PGD",
                "exclusion_reason": "BELOW_STATION_COUNT_THRESHOLD",
                "detail": f"stations usable for PGD formula={usable_for_formula}; min_stations={eval_args.min_stations}",
            }
        )
        return row

    row.update(
        {
            "pgd_status": "EXCLUDED_PGD",
            "exclusion_reason": "NO_EVENT_ROWS",
            "detail": "PGD station candidates existed but no event/formula row was produced",
        }
    )
    return row


def build_inclusion_exclusion_rows(
    root: Path,
    args: argparse.Namespace,
    eval_args: SimpleNamespace,
    event_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    included = included_event_metrics(event_rows)
    rows: list[dict[str, object]] = []
    for event_dir in iter_normalized_event_dirs(root):
        event = pgd.load_json(event_dir / "event.json")
        event_id = event_id_value(event, event_dir)
        if event_id in included:
            row = base_inclusion_row(event_dir, event)
            row.update(included[event_id])
            row.update({"pgd_status": "INCLUDED_PGD_EVALUATED", "exclusion_reason": "", "detail": "event produced PGD formula rows"})
            rows.append(row)
            continue
        rows.append(classify_pgd_exclusion(event_dir, event, args, eval_args))
    return rows


def inclusion_exclusion_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    by_status = Counter(str(row.get("pgd_status") or "unknown") for row in rows)
    by_reason = Counter(str(row.get("exclusion_reason") or "INCLUDED") for row in rows)
    return {
        "total_normalized_events": len(rows),
        "pgd_evaluable_events": by_status.get("INCLUDED_PGD_EVALUATED", 0),
        "pgd_excluded_events": len(rows) - by_status.get("INCLUDED_PGD_EVALUATED", 0),
        "by_status": dict(sorted(by_status.items())),
        "by_exclusion_reason": dict(sorted(by_reason.items())),
    }


def write_inclusion_exclusion_md(path: Path, rows: list[dict[str, object]]) -> None:
    summary = inclusion_exclusion_summary(rows)
    lines = [
        "# PGD Inclusion/Exclusion",
        "",
        f"- Total normalized events: {summary['total_normalized_events']}",
        f"- PGD evaluable events: {summary['pgd_evaluable_events']}",
        f"- PGD excluded events: {summary['pgd_excluded_events']}",
        "",
        "## Exclusion Reasons",
        "",
        "| reason | count |",
        "|---|---:|",
    ]
    reasons = summary["by_exclusion_reason"]
    assert isinstance(reasons, dict)
    for reason, count in reasons.items():
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## Events", "", *markdown_table(rows, INCLUSION_FIELDS), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def comparison_row(
    comparison_group: str,
    comparison_value: str,
    formula: str,
    rows: list[dict[str, object]],
    residual_review_threshold: float,
) -> dict[str, object]:
    payload = pgd.summary_payload(rows)
    return {
        "comparison_group": comparison_group,
        "comparison_value": comparison_value,
        "formula": formula,
        "station_aggregation": rows[0].get("station_aggregation", "") if rows else "",
        "event_count": payload["event_count"],
        "high_medium_reliability_events": sum(1 for row in rows if row.get("pgd_reliability") in {"HIGH", "MEDIUM"}),
        "low_reliability_events": sum(1 for row in rows if row.get("pgd_reliability") == "LOW"),
        "residual_outlier_count": sum(
            1
            for row in rows
            if (abs_residual := pgd.finite_float(row.get("abs_residual_mw"))) >= residual_review_threshold
            and math.isfinite(abs_residual)
        ),
        "bias_mw": payload["bias_mw"],
        "mae_mw": payload["mae_mw"],
        "rmse_mw": payload["rmse_mw"],
        "median_abs_error_mw": payload["median_abs_error_mw"],
    }


def comparison_rows_for_group(
    event_rows: list[dict[str, object]],
    comparison_group: str,
    value_func: Any,
    residual_review_threshold: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    formula_order = [law.name for law in pgd.SCALING_LAWS]
    values = sorted({str(value_func(row) or "") for row in event_rows})
    for value in values:
        if not value:
            continue
        value_rows = [row for row in event_rows if str(value_func(row) or "") == value]
        for formula in formula_order:
            formula_rows = [row for row in value_rows if row.get("formula") == formula]
            if formula_rows:
                rows.append(comparison_row(comparison_group, value, formula, formula_rows, residual_review_threshold))
    return rows


def formula_comparison(event_rows: list[dict[str, object]], residual_review_threshold: float) -> list[dict[str, object]]:
    return comparison_rows_for_group(event_rows, "all", lambda _row: "ALL", residual_review_threshold)


def formula_breakdown(event_rows: list[dict[str, object]], residual_review_threshold: float) -> list[dict[str, object]]:
    rows = list(formula_comparison(event_rows, residual_review_threshold))
    rows.extend(comparison_rows_for_group(event_rows, "country", lambda row: row.get("country") or "unknown", residual_review_threshold))
    rows.extend(comparison_rows_for_group(event_rows, "region", lambda row: row.get("region") or "unknown", residual_review_threshold))
    rows.extend(
        comparison_rows_for_group(
            event_rows,
            "magnitude_bin",
            lambda row: pgd.magnitude_bin(float(row["usgs_magnitude"])),
            residual_review_threshold,
        )
    )
    rows.extend(
        comparison_rows_for_group(
            event_rows,
            "pgd_reliability",
            lambda row: row.get("pgd_reliability") or "unknown",
            residual_review_threshold,
        )
    )
    rows.extend(comparison_rows_for_group(event_rows, "source", lambda row: row.get("source") or "unknown", residual_review_threshold))
    return rows


def recommend_formula(formula_rows: list[dict[str, object]]) -> dict[str, object]:
    candidates = [
        row
        for row in formula_rows
        if row.get("comparison_group") == "all"
        and pgd.finite_float(row.get("event_count")) > 0
        and math.isfinite(pgd.finite_float(row.get("mae_mw")))
    ]
    if not candidates:
        return {
            "status": "NO_RECOMMENDATION",
            "reason": "No formula comparison rows with finite MAE were generated.",
            "recommended_formula": "",
            "station_aggregation": "",
            "criterion": "lowest_mae_mw",
        }
    best = min(
        candidates,
        key=lambda row: (
            pgd.finite_float(row.get("mae_mw")),
            pgd.finite_float(row.get("rmse_mw")),
            pgd.finite_float(row.get("median_abs_error_mw")),
            str(row.get("formula") or ""),
        ),
    )
    return {
        "status": "OK",
        "recommended_formula": best.get("formula", ""),
        "station_aggregation": best.get("station_aggregation", ""),
        "criterion": "lowest_mae_mw",
        "mae_mw": best.get("mae_mw", ""),
        "rmse_mw": best.get("rmse_mw", ""),
        "median_abs_error_mw": best.get("median_abs_error_mw", ""),
        "event_count": best.get("event_count", ""),
        "residual_outlier_count": best.get("residual_outlier_count", ""),
    }


def unique_event_count(event_rows: list[dict[str, object]]) -> int:
    return len({str(row.get("event_id") or "") for row in event_rows if row.get("event_id")})


def reliability_counts(event_rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for row in event_rows:
        event_id = str(row.get("event_id") or "")
        if not event_id or event_id in seen:
            continue
        seen.add(event_id)
        reliability = str(row.get("pgd_reliability") or "unknown")
        counts[reliability] = counts.get(reliability, 0) + 1
    return dict(sorted(counts.items()))


def release_residual_review_threshold(args: argparse.Namespace) -> float:
    threshold = args.release_residual_review_threshold
    return float(args.residual_review_threshold if threshold is None else threshold)


def release_gate_config(args: argparse.Namespace) -> dict[str, object]:
    return {
        "min_usable_stations": args.release_min_usable_stations,
        "allowed_reliability": sorted(set(args.release_allowed_reliability)),
        "min_median_pgd_snr": args.release_min_median_snr,
        "max_median_distance_km": args.release_max_median_distance_km,
        "residual_review_threshold_mw": release_residual_review_threshold(args),
        "residual_review_is_exclusion": False,
    }


def release_set_rows(
    event_rows: list[dict[str, object]],
    formula_recommendation: dict[str, object],
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    recommended_formula = str(formula_recommendation.get("recommended_formula") or "")
    if not recommended_formula:
        return []
    allowed_reliability = set(args.release_allowed_reliability)
    residual_threshold = release_residual_review_threshold(args)
    rows: list[dict[str, object]] = []
    for source_row in sorted(
        (row for row in event_rows if str(row.get("formula") or "") == recommended_formula),
        key=lambda row: (str(row.get("event_time") or ""), str(row.get("event_id") or "")),
    ):
        failure_reasons: list[str] = []
        review_reasons: list[str] = []
        usable_station_count = pgd.finite_float(source_row.get("usable_station_count"))
        median_snr = pgd.finite_float(source_row.get("median_pgd_snr"))
        median_distance = pgd.finite_float(source_row.get("median_distance_km"))
        abs_residual = pgd.finite_float(source_row.get("abs_residual_mw"))
        reliability = str(source_row.get("pgd_reliability") or "")

        if not math.isfinite(usable_station_count) or usable_station_count < args.release_min_usable_stations:
            failure_reasons.append("insufficient_usable_stations")
        if reliability not in allowed_reliability:
            failure_reasons.append("low_reliability")
        if not math.isfinite(median_snr):
            failure_reasons.append("missing_median_pgd_snr")
        elif median_snr < args.release_min_median_snr:
            failure_reasons.append("low_median_pgd_snr")
        if args.release_max_median_distance_km > 0:
            if not math.isfinite(median_distance):
                failure_reasons.append("missing_median_distance")
            elif median_distance > args.release_max_median_distance_km:
                failure_reasons.append("excessive_median_distance")
        release_candidate = not failure_reasons
        if release_candidate and math.isfinite(abs_residual) and abs_residual >= residual_threshold:
            review_reasons.append(f"abs_residual_mw>={pgd.fmt(residual_threshold, 3)}")
        review_required = release_candidate and bool(review_reasons)
        if not release_candidate:
            release_status = "EXCLUDED_RELEASE_SET"
        elif review_required:
            release_status = "NEEDS_RESIDUAL_REVIEW"
        else:
            release_status = "INCLUDED_RELEASE_SET"

        row = {field: source_row.get(field, "") for field in RELEASE_SET_FIELDS}
        row.update(
            {
                "release_status": release_status,
                "release_candidate": "yes" if release_candidate else "no",
                "release_ready": "yes" if release_status == "INCLUDED_RELEASE_SET" else "no",
                "review_required": "yes" if review_required else "no",
                "release_failure_reasons": ";".join(failure_reasons),
                "release_review_reasons": ";".join(review_reasons),
                "release_notes": "Residual threshold marks review only; it does not exclude candidates.",
            }
        )
        rows.append(row)
    return rows


def release_set_summary(
    release_rows: list[dict[str, object]],
    formula_recommendation: dict[str, object],
    args: argparse.Namespace,
) -> dict[str, object]:
    by_status = Counter(str(row.get("release_status") or "unknown") for row in release_rows)
    failure_counter: Counter[str] = Counter()
    review_counter: Counter[str] = Counter()
    for row in release_rows:
        failure_counter.update(reason for reason in str(row.get("release_failure_reasons") or "").split(";") if reason)
        review_counter.update(reason for reason in str(row.get("release_review_reasons") or "").split(";") if reason)
    return {
        "status": "OK" if release_rows else "NO_RELEASE_ROWS",
        "formula": formula_recommendation.get("recommended_formula", ""),
        "station_aggregation": formula_recommendation.get("station_aggregation", pgd.STATION_AGGREGATION),
        "gate": release_gate_config(args),
        "total_events": len(release_rows),
        "candidate_events": sum(1 for row in release_rows if row.get("release_candidate") == "yes"),
        "ready_events": sum(1 for row in release_rows if row.get("release_ready") == "yes"),
        "review_required_events": sum(1 for row in release_rows if row.get("review_required") == "yes"),
        "excluded_events": sum(1 for row in release_rows if row.get("release_candidate") != "yes"),
        "by_status": dict(sorted(by_status.items())),
        "by_failure_reason": dict(sorted(failure_counter.items())),
        "by_review_reason": dict(sorted(review_counter.items())),
    }


def science_release_rows(release_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in release_rows if row.get("release_status") == "INCLUDED_RELEASE_SET"]


def figure_role(path: Path) -> str:
    stem = path.stem
    if stem == "estimated_vs_usgs_by_region":
        return "formula fit diagnostic"
    if stem == "formula_mae_by_region":
        return "regional formula comparison"
    if stem == "residual_vs_usgs_magnitude":
        return "residual diagnostic"
    return "supporting figure"


def science_figure_manifest_rows(figure_paths: list[Path]) -> list[dict[str, object]]:
    return [
        {
            "figure_type": path.stem,
            "path": str(path),
            "role": figure_role(path),
        }
        for path in figure_paths
    ]


def write_science_narrative(path: Path, payload: dict[str, object]) -> None:
    counts = payload["counts"]
    assert isinstance(counts, dict)
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    recommendation = payload["formula_recommendation"]
    assert isinstance(recommendation, dict)
    release_summary = payload["pgd_release_set"]
    assert isinstance(release_summary, dict)
    inclusion = payload["pgd_inclusion_exclusion"]
    assert isinstance(inclusion, dict)
    residual_review = payload["residual_review"]
    assert isinstance(residual_review, list)
    figures = payload["figures"]
    assert isinstance(figures, list)

    review_status_counts = Counter(str(row.get("review_status") or "unknown") for row in residual_review)
    lines = [
        "# PGD Magnitude Science Narrative",
        "",
        "## Dataset Description",
        "",
        f"The normalized export produced {inclusion.get('total_normalized_events', 0)} events for PGD screening. "
        f"The current PGD run evaluated {counts.get('unique_events', 0)} events and {counts.get('station_rows', 0)} station/formula rows after country, metadata, waveform, and PGD threshold filters.",
        "",
        "## Median Aggregation And Formulas",
        "",
        f"The PGD event-level method uses one station aggregation method: `{parameters.get('station_aggregation', '')}`. "
        f"The report uses `{parameters.get('pgd_component', '')}` PGD and `{parameters.get('distance_mode', '')}` distance. "
        "The three formula candidates are `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019`; they are not station aggregation methods.",
        "",
        "## Formula Comparison",
        "",
        f"The recommended formula is `{recommendation.get('recommended_formula', '')}` using `{recommendation.get('criterion', '')}`. "
        f"Current overall MAE is {pgd.fmt(recommendation.get('mae_mw'), 3)} Mw, RMSE is {pgd.fmt(recommendation.get('rmse_mw'), 3)} Mw, and median absolute error is {pgd.fmt(recommendation.get('median_abs_error_mw'), 3)} Mw.",
        "",
        "## Release Set",
        "",
        f"The release gate evaluated {release_summary.get('total_events', 0)} events under `{release_summary.get('formula', '')}`. "
        f"{release_summary.get('ready_events', 0)} are ready, {release_summary.get('review_required_events', 0)} require residual review, and {release_summary.get('excluded_events', 0)} are excluded by hard quality gates.",
        "",
        "## Residual Behavior",
        "",
        f"The largest-residual queue contains {counts.get('residual_review_rows', 0)} rows. "
        f"The residual review threshold is {parameters.get('residual_review_threshold', '')} Mw for formula comparison counts and {release_summary.get('gate', {}).get('residual_review_threshold_mw', '')} Mw for release-set review marking.",
        "",
        "## Outlier Review Status",
        "",
        "Residual review status counts: "
        + ", ".join(f"{key}={value}" for key, value in sorted(review_status_counts.items()))
        + ".",
        "",
        "## Limitations",
        "",
        "The current release set is constrained by station count, PGD reliability, median SNR, and median distance. "
        "Legacy New Zealand package country labels are corrected only inside the PGD report layer. Residual review fields are still manual scientific annotations and should be completed before treating outlier interpretation as final.",
        "",
        "## Next Experiments",
        "",
        "Use the median aggregation baseline to test PGD component, distance mode, and calibration sensitivity. "
        "Do not reintroduce non-median station aggregation as a mainline method unless the science plan is explicitly revised.",
        "",
        "## Figures",
        "",
    ]
    if figures:
        lines.extend(f"- `{figure}`" for figure in figures)
    else:
        lines.append("- No figures generated.")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def summary_payload(
    *,
    args: argparse.Namespace,
    station_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
    formula_summary: list[dict[str, object]],
    magnitude_bin_summary: list[dict[str, object]],
    quality_filtered_magnitude_bin_summary: list[dict[str, object]],
    formula_comparison_rows: list[dict[str, object]],
    formula_breakdown_rows: list[dict[str, object]],
    formula_recommendation: dict[str, object],
    release_rows: list[dict[str, object]],
    release_summary: dict[str, object],
    inclusion_exclusion_rows: list[dict[str, object]],
    residual_outlier_rows: list[dict[str, object]],
    residual_review_rows: list[dict[str, object]],
    low_reliability: list[dict[str, object]],
    figure_paths: list[Path],
    status: str,
    message: str,
) -> dict[str, object]:
    return {
        "status": status,
        "message": message,
        "counts": {
            "event_rows": len(event_rows),
            "station_rows": len(station_rows),
            "unique_events": unique_event_count(event_rows),
            "formula_summary_rows": len(formula_summary),
            "magnitude_bin_summary_rows": len(magnitude_bin_summary),
            "quality_filtered_magnitude_bin_summary_rows": len(quality_filtered_magnitude_bin_summary),
            "formula_comparison_rows": len(formula_comparison_rows),
            "formula_breakdown_rows": len(formula_breakdown_rows),
            "release_set_rows": len(release_rows),
            "residual_outlier_rows": len(residual_outlier_rows),
            "residual_review_rows": len(residual_review_rows),
            "low_reliability_events": len(low_reliability),
        },
        "parameters": {
            "export_root": str(args.export_root),
            "pgd_window_seconds": [args.pgd_window_start, args.pgd_window_end],
            "pgd_component": args.pgd_component,
            "distance_mode": args.distance,
            "station_aggregation": pgd.STATION_AGGREGATION,
            "calibration": args.calibration,
            "countries": sorted(args.countries),
            "min_pgd_snr": args.min_pgd_snr,
            "quality_max_distance_km": args.quality_max_distance_km,
            "quality_max_pgd_time_offset": args.quality_max_pgd_time_offset,
            "outlier_limit": args.outlier_limit,
            "residual_review_threshold": args.residual_review_threshold,
            "release_gate": release_gate_config(args),
        },
        "formula_summary": json_safe(formula_summary),
        "magnitude_bin_summary": json_safe(magnitude_bin_summary),
        "quality_filtered_magnitude_bin_summary": json_safe(quality_filtered_magnitude_bin_summary),
        "formula_comparison": json_safe(formula_comparison_rows),
        "formula_breakdown": json_safe(formula_breakdown_rows),
        "formula_recommendation": json_safe(formula_recommendation),
        "pgd_release_set": json_safe(release_summary),
        "release_set": json_safe(release_rows),
        "pgd_inclusion_exclusion": json_safe(inclusion_exclusion_summary(inclusion_exclusion_rows)),
        "residual_outliers": json_safe(residual_outlier_rows),
        "residual_review": json_safe(residual_review_rows),
        "reliability_counts": reliability_counts(event_rows),
        "low_reliability_events": json_safe(low_reliability),
        "figures": [str(path) for path in figure_paths],
    }


def write_summary_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _ in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _ in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return lines


def write_summary_md(path: Path, payload: dict[str, object]) -> None:
    counts = payload["counts"]
    assert isinstance(counts, dict)
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    formula_summary = payload["formula_summary"]
    assert isinstance(formula_summary, list)
    magnitude_bin_summary = payload["magnitude_bin_summary"]
    assert isinstance(magnitude_bin_summary, list)
    quality_filtered_magnitude_bin_summary = payload["quality_filtered_magnitude_bin_summary"]
    assert isinstance(quality_filtered_magnitude_bin_summary, list)
    formula_comparison_rows = payload["formula_comparison"]
    assert isinstance(formula_comparison_rows, list)
    formula_recommendation = payload["formula_recommendation"]
    assert isinstance(formula_recommendation, dict)
    release_summary = payload["pgd_release_set"]
    assert isinstance(release_summary, dict)
    release_rows = payload["release_set"]
    assert isinstance(release_rows, list)
    pgd_inclusion_exclusion = payload["pgd_inclusion_exclusion"]
    assert isinstance(pgd_inclusion_exclusion, dict)
    residual_outlier_rows = payload["residual_outliers"]
    assert isinstance(residual_outlier_rows, list)
    residual_review = payload["residual_review"]
    assert isinstance(residual_review, list)
    low_reliability = payload["low_reliability_events"]
    assert isinstance(low_reliability, list)
    lines = [
        "# PGD Magnitude Report",
        "",
        f"- Status: `{payload['status']}`",
        f"- Message: {payload['message']}",
        f"- Unique events: {counts['unique_events']}",
        f"- Event/formula rows: {counts['event_rows']}",
        f"- Station/formula rows: {counts['station_rows']}",
        f"- PGD component: `{parameters['pgd_component']}`",
        f"- Distance mode: `{parameters['distance_mode']}`",
        f"- Station aggregation: `{parameters['station_aggregation']}`",
        f"- Calibration: `{parameters['calibration']}`",
        f"- Recommended formula: `{formula_recommendation.get('recommended_formula', '')}`",
        "",
        "## Formula Summary",
        "",
        *markdown_table(formula_summary, SUMMARY_FIELDS),
        "",
        "## Magnitude-bin Summary",
        "",
        *markdown_table(magnitude_bin_summary, BIN_SUMMARY_FIELDS),
        "",
        "## Quality-filtered Magnitude-bin Summary",
        "",
        *markdown_table(quality_filtered_magnitude_bin_summary, BIN_SUMMARY_FIELDS),
        "",
        "## Formula Comparison",
        "",
        *markdown_table(formula_comparison_rows, COMPARISON_FIELDS),
        "",
        "## PGD Release Set",
        "",
        f"- Formula: `{release_summary.get('formula', '')}`",
        f"- Candidate events: {release_summary.get('candidate_events', 0)}",
        f"- Ready events: {release_summary.get('ready_events', 0)}",
        f"- Review-required events: {release_summary.get('review_required_events', 0)}",
        f"- Excluded events: {release_summary.get('excluded_events', 0)}",
        "",
        *markdown_table(release_rows[:20], RELEASE_SET_FIELDS),
        "",
        "## PGD Inclusion/Exclusion",
        "",
        f"- Total normalized events: {pgd_inclusion_exclusion.get('total_normalized_events', 0)}",
        f"- PGD evaluable events: {pgd_inclusion_exclusion.get('pgd_evaluable_events', 0)}",
        f"- PGD excluded events: {pgd_inclusion_exclusion.get('pgd_excluded_events', 0)}",
        "",
        "## Largest Residuals",
        "",
        *markdown_table(residual_outlier_rows, RESIDUAL_FIELDS),
        "",
        "## Residual Review",
        "",
        *markdown_table(residual_review, RESIDUAL_REVIEW_FIELDS),
        "",
        "## Low Reliability Events",
        "",
        *markdown_table(
            low_reliability[:20],
            [
                "event_id",
                "country",
                "usgs_magnitude",
                "magnitude_bin",
                "usable_station_count",
                "pgd_reliability",
                "reliability_flags",
            ],
        ),
        "",
        "## Figures",
        "",
    ]
    figures = payload["figures"]
    assert isinstance(figures, list)
    if figures:
        lines.extend(f"- `{figure}`" for figure in figures)
    else:
        lines.append("- No figures generated.")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_formula_breakdown_md(
    path: Path,
    rows: list[dict[str, object]],
    formula_recommendation: dict[str, object],
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Median-only Formula Breakdown",
        "",
        f"- Station aggregation: `{pgd.STATION_AGGREGATION}`",
        "- The rows compare PGD scaling formulas; they are not station aggregation methods.",
        f"- Residual review threshold: `{args.residual_review_threshold}` Mw",
        f"- Recommended formula: `{formula_recommendation.get('recommended_formula', '')}`",
        f"- Recommendation criterion: `{formula_recommendation.get('criterion', '')}`",
        "",
        "## All Events",
        "",
        *markdown_table([row for row in rows if row.get("comparison_group") == "all"], COMPARISON_FIELDS),
        "",
        "## Breakdowns",
        "",
        *markdown_table([row for row in rows if row.get("comparison_group") != "all"], COMPARISON_FIELDS),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_report(args: argparse.Namespace) -> dict[str, object]:
    out_dir = args.out_dir
    figure_dir = out_dir / "figures"
    eval_args = evaluator_args(args, figure_dir)
    countries = set(args.countries)
    station_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []

    for event_dir in pgd.iter_event_dirs(args.export_root, countries):
        event_station_rows, event_event_rows = pgd.evaluate_event(event_dir, eval_args)
        station_rows.extend(event_station_rows)
        event_rows.extend(event_event_rows)

    raw_event_rows = list(event_rows)
    raw_formula_summary = pgd.summarize(raw_event_rows)
    if args.calibration == "leave-one-out-country-linear":
        event_rows = pgd.apply_leave_one_out_calibration(raw_event_rows)
    formula_summary = pgd.summarize(event_rows)
    magnitude_bin_summary = pgd.summarize_by_magnitude_bin(event_rows, quality_filtered=False)
    quality_filtered_magnitude_bin_summary = pgd.summarize_by_magnitude_bin(event_rows, quality_filtered=True)
    formula_comparison_rows = formula_comparison(event_rows, args.residual_review_threshold)
    formula_breakdown_rows = formula_breakdown(event_rows, args.residual_review_threshold)
    formula_recommendation = recommend_formula(formula_comparison_rows)
    release_rows = release_set_rows(event_rows, formula_recommendation, args)
    release_summary = release_set_summary(release_rows, formula_recommendation, args)
    inclusion_exclusion_rows = build_inclusion_exclusion_rows(args.export_root, args, eval_args, event_rows)
    residual_outlier_rows = residual_outliers(event_rows, args.outlier_limit)
    residual_review = residual_review_rows(residual_outlier_rows, out_dir / "residual_review.csv")
    low_reliability = pgd.low_reliability_events(event_rows)

    remove_stale_pre_median_contract_outputs(out_dir, figure_dir)

    write_csv(out_dir / "stations.csv", station_rows, STATION_FIELDS)
    write_csv(out_dir / "events.csv", event_rows, EVENT_FIELDS)
    write_csv(out_dir / "residuals.csv", residual_rows(event_rows), RESIDUAL_FIELDS)
    write_csv(out_dir / "residual_outliers.csv", residual_outlier_rows, RESIDUAL_FIELDS)
    write_csv(out_dir / "residual_review.csv", residual_review, RESIDUAL_REVIEW_FIELDS)
    write_csv(out_dir / "formula_summary.csv", formula_summary, SUMMARY_FIELDS)
    write_csv(out_dir / "formula_summary_raw.csv", raw_formula_summary, SUMMARY_FIELDS)
    write_csv(out_dir / "formula_summary_by_magnitude_bin.csv", magnitude_bin_summary, BIN_SUMMARY_FIELDS)
    write_csv(out_dir / "formula_summary_quality_filtered_by_magnitude_bin.csv", quality_filtered_magnitude_bin_summary, BIN_SUMMARY_FIELDS)
    write_csv(out_dir / "formula_comparison.csv", formula_comparison_rows, COMPARISON_FIELDS)
    write_csv(out_dir / "formula_breakdown.csv", formula_breakdown_rows, COMPARISON_FIELDS)
    write_formula_breakdown_md(out_dir / "formula_breakdown.md", formula_breakdown_rows, formula_recommendation, args)
    write_csv(out_dir / "release_set.csv", release_rows, RELEASE_SET_FIELDS)
    write_summary_json(out_dir / "release_set_summary.json", release_summary)
    write_csv(out_dir / "inclusion_exclusion.csv", inclusion_exclusion_rows, INCLUSION_FIELDS)
    write_inclusion_exclusion_md(out_dir / "inclusion_exclusion.md", inclusion_exclusion_rows)

    figure_paths: list[Path] = []
    if event_rows:
        pgd.write_plots(event_rows, formula_summary, figure_dir)
        figure_paths = sorted(path for path in figure_dir.glob("*.svg") if path.is_file())

    status = "OK" if event_rows else "NO_PGD_EVENTS"
    message = (
        "PGD report generated."
        if event_rows
        else "No PGD event rows generated. Check event countries, waveform amplitudes, station Distance_Km, or PGD thresholds."
    )
    payload = summary_payload(
        args=args,
        station_rows=station_rows,
        event_rows=event_rows,
        formula_summary=formula_summary,
        magnitude_bin_summary=magnitude_bin_summary,
        quality_filtered_magnitude_bin_summary=quality_filtered_magnitude_bin_summary,
        formula_comparison_rows=formula_comparison_rows,
        formula_breakdown_rows=formula_breakdown_rows,
        formula_recommendation=formula_recommendation,
        release_rows=release_rows,
        release_summary=release_summary,
        inclusion_exclusion_rows=inclusion_exclusion_rows,
        residual_outlier_rows=residual_outlier_rows,
        residual_review_rows=residual_review,
        low_reliability=low_reliability,
        figure_paths=figure_paths,
        status=status,
        message=message,
    )
    write_summary_json(out_dir / "summary.json", payload)
    write_summary_md(out_dir / "summary.md", payload)
    write_csv(out_dir / "science_release_events.csv", science_release_rows(release_rows), SCIENCE_RELEASE_FIELDS)
    write_csv(out_dir / "science_formula_summary.csv", formula_comparison_rows, COMPARISON_FIELDS)
    write_csv(out_dir / "science_figure_manifest.csv", science_figure_manifest_rows(figure_paths), SCIENCE_FIGURE_FIELDS)
    write_science_narrative(out_dir / "science_narrative.md", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_report(args)
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "out_dir": str(args.out_dir)}, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
