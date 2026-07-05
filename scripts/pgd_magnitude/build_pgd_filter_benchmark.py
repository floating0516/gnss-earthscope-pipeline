#!/usr/bin/env python3
"""Build PGD filter benchmark scenarios from compact benchmark station rows."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract


DEFAULT_BENCHMARK_DIR = Path("reports/pgd_magnitude/benchmark/latest")
DEFAULT_OUT_DIR = DEFAULT_BENCHMARK_DIR / "filter_benchmark"
STATION_AGGREGATION = pgd_contract.STATION_AGGREGATION_METHOD


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    label: str
    tier: str
    min_pgd_cm: float | None = None
    min_snr: float | None = None
    max_time_offset_s: float | None = None
    max_distance_km: float | None = None
    min_stations: int = 1

    def filters_text(self) -> str:
        parts = []
        if self.min_pgd_cm is not None:
            parts.append(f"pgd_cm>={self.min_pgd_cm:g}")
        if self.min_snr is not None:
            parts.append(f"pgd_snr>={self.min_snr:g}")
        if self.max_time_offset_s is not None:
            parts.append(f"pgd_time_offset_s<={self.max_time_offset_s:g}")
        if self.max_distance_km is not None:
            parts.append(f"distance_km<={self.max_distance_km:g}")
        parts.append(f"min_stations>={self.min_stations}")
        return "; ".join(parts)

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "tier": self.tier,
            "min_pgd_cm": self.min_pgd_cm,
            "min_snr": self.min_snr,
            "max_time_offset_s": self.max_time_offset_s,
            "max_distance_km": self.max_distance_km,
            "min_stations": self.min_stations,
            "filters": self.filters_text(),
        }


SCENARIOS = [
    Scenario("all", "All stations, no quality filter", "ALL"),
    Scenario("pgd_ge_1cm", "Station PGD >= 1 cm", "AMPLITUDE", min_pgd_cm=1.0),
    Scenario("pgd_ge_2cm", "Station PGD >= 2 cm", "AMPLITUDE", min_pgd_cm=2.0),
    Scenario("pgd_ge_5cm", "Station PGD >= 5 cm", "AMPLITUDE", min_pgd_cm=5.0),
    Scenario("snr_ge_3", "Station PGD SNR >= 3", "SNR", min_snr=3.0),
    Scenario("snr_ge_5", "Station PGD SNR >= 5", "SNR", min_snr=5.0),
    Scenario("dist_le_300km", "Station distance <= 300 km", "DISTANCE", max_distance_km=300.0),
    Scenario("dist_le_200km", "Station distance <= 200 km", "DISTANCE", max_distance_km=200.0),
    Scenario(
        "quality_snr3_time300_dist300_min3sta",
        "Quality set: SNR >= 3, time <= 300 s, distance <= 300 km, min 3 stations",
        "QUALITY",
        min_snr=3.0,
        max_time_offset_s=300.0,
        max_distance_km=300.0,
        min_stations=3,
    ),
    Scenario(
        "strict_snr5_time300_dist300_min3sta",
        "Strict set: SNR >= 5, time <= 300 s, distance <= 300 km, min 3 stations",
        "STRICT",
        min_snr=5.0,
        max_time_offset_s=300.0,
        max_distance_km=300.0,
        min_stations=3,
    ),
]

SUMMARY_FIELDS = [
    "scenario_id",
    "scenario_label",
    "tier",
    "formula",
    "station_aggregation",
    "event_count",
    "excluded_event_count",
    "total_filtered_station_count",
    "median_station_count",
    "min_station_count",
    "bias_mw",
    "mae_mw",
    "rmse_mw",
    "median_abs_error_mw",
    "within_0_3_count",
    "within_0_5_count",
    "within_1_0_count",
    "over_1_0_count",
    "rank_by_mae",
    "recommended_formula",
    "filters",
]

EVENT_FIELDS = [
    "scenario_id",
    "scenario_label",
    "tier",
    "formula",
    "station_aggregation",
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
    "place",
    "usgs_magnitude",
    "station_count",
    "median_pgd_cm",
    "median_pgd_snr",
    "median_distance_km",
    "median_pgd_time_offset_s",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "filters",
]

EXCLUSION_FIELDS = [
    "scenario_id",
    "scenario_label",
    "tier",
    "event_id",
    "event_time",
    "country",
    "region",
    "source",
    "place",
    "usgs_magnitude",
    "total_station_count",
    "filtered_station_count",
    "min_stations",
    "exclusion_reason",
    "filters",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR, help="Compact PGD benchmark directory with stations.csv.")
    parser.add_argument("--stations-csv", type=Path, default=None, help="Override station rows CSV. Defaults to <benchmark-dir>/stations.csv.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for filter benchmark products.")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def median(values: list[float]) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def rmse(values: list[float]) -> float:
    return math.sqrt(mean([value * value for value in values])) if values else math.nan


def fmt(value: object, digits: int = 6) -> str:
    if isinstance(value, int):
        return str(value)
    number = finite_float(value)
    if math.isfinite(number):
        return f"{number:.{digits}f}"
    return "" if value is None else str(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_station_aggregation(rows: list[dict[str, str]]) -> list[str]:
    bad_values = sorted({str(row.get("station_aggregation") or "").strip() for row in rows if str(row.get("station_aggregation") or "").strip() != STATION_AGGREGATION})
    return bad_values


def station_key(row: dict[str, str]) -> tuple[str, str]:
    return str(row.get("event_id") or ""), str(row.get("station") or "")


def event_key(row: dict[str, str]) -> str:
    return str(row.get("event_id") or "")


def formula_key(row: dict[str, str]) -> str:
    return str(row.get("formula") or "")


def station_passes(row: dict[str, str], scenario: Scenario) -> bool:
    if scenario.min_pgd_cm is not None and finite_float(row.get("pgd_cm")) < scenario.min_pgd_cm:
        return False
    if scenario.min_snr is not None and finite_float(row.get("pgd_snr")) < scenario.min_snr:
        return False
    if scenario.max_time_offset_s is not None and finite_float(row.get("pgd_time_offset_s")) > scenario.max_time_offset_s:
        return False
    if scenario.max_distance_km is not None and finite_float(row.get("hypocentral_distance_km")) > scenario.max_distance_km:
        return False
    return True


def representative_event_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    events: dict[str, dict[str, str]] = {}
    for row in rows:
        events.setdefault(event_key(row), row)
    return events


def unique_station_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        unique.setdefault(station_key(row), row)
    return unique


def included_event_station_counts(rows: list[dict[str, str]], scenario: Scenario) -> tuple[dict[str, int], dict[str, int]]:
    all_unique = unique_station_rows(rows)
    total_counts: dict[str, int] = {}
    filtered_counts: dict[str, int] = {}
    for (event_id, _station), row in all_unique.items():
        total_counts[event_id] = total_counts.get(event_id, 0) + 1
        if station_passes(row, scenario):
            filtered_counts[event_id] = filtered_counts.get(event_id, 0) + 1
    return total_counts, filtered_counts


def scenario_event_rows(rows: list[dict[str, str]], scenario: Scenario, formulas: list[str]) -> list[dict[str, object]]:
    total_counts, filtered_counts = included_event_station_counts(rows, scenario)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        if formula_key(row) not in formulas:
            continue
        event_id = event_key(row)
        if filtered_counts.get(event_id, 0) < scenario.min_stations:
            continue
        if not station_passes(row, scenario):
            continue
        grouped.setdefault((event_id, formula_key(row)), []).append(row)

    event_rows: list[dict[str, object]] = []
    for (event_id, formula), station_rows in sorted(grouped.items()):
        estimates = [finite_float(row.get("estimated_mw")) for row in station_rows]
        estimates = [value for value in estimates if math.isfinite(value)]
        if not estimates:
            continue
        first = station_rows[0]
        magnitude = finite_float(first.get("usgs_magnitude"))
        estimate = median(estimates)
        residual = estimate - magnitude if math.isfinite(magnitude) else math.nan
        event_rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_label": scenario.label,
                "tier": scenario.tier,
                "formula": formula,
                "station_aggregation": STATION_AGGREGATION,
                "event_id": event_id,
                "event_time": first.get("event_time") or "",
                "country": first.get("country") or "",
                "region": first.get("region") or "",
                "source": first.get("source") or "",
                "place": first.get("place") or "",
                "usgs_magnitude": magnitude,
                "station_count": filtered_counts.get(event_id, len(station_rows)),
                "median_pgd_cm": median([finite_float(row.get("pgd_cm")) for row in station_rows if math.isfinite(finite_float(row.get("pgd_cm")))]),
                "median_pgd_snr": median([finite_float(row.get("pgd_snr")) for row in station_rows if math.isfinite(finite_float(row.get("pgd_snr")))]),
                "median_distance_km": median([finite_float(row.get("hypocentral_distance_km")) for row in station_rows if math.isfinite(finite_float(row.get("hypocentral_distance_km")))]),
                "median_pgd_time_offset_s": median([finite_float(row.get("pgd_time_offset_s")) for row in station_rows if math.isfinite(finite_float(row.get("pgd_time_offset_s")))]),
                "estimated_mw_median": estimate,
                "residual_mw": residual,
                "abs_residual_mw": abs(residual) if math.isfinite(residual) else math.nan,
                "filters": scenario.filters_text(),
            }
        )
    return event_rows


def scenario_exclusion_rows(rows: list[dict[str, str]], scenario: Scenario) -> list[dict[str, object]]:
    events = representative_event_rows(rows)
    total_counts, filtered_counts = included_event_station_counts(rows, scenario)
    excluded: list[dict[str, object]] = []
    for event_id, first in sorted(events.items()):
        filtered_count = filtered_counts.get(event_id, 0)
        if filtered_count >= scenario.min_stations:
            continue
        excluded.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_label": scenario.label,
                "tier": scenario.tier,
                "event_id": event_id,
                "event_time": first.get("event_time") or "",
                "country": first.get("country") or "",
                "region": first.get("region") or "",
                "source": first.get("source") or "",
                "place": first.get("place") or "",
                "usgs_magnitude": finite_float(first.get("usgs_magnitude")),
                "total_station_count": total_counts.get(event_id, 0),
                "filtered_station_count": filtered_count,
                "min_stations": scenario.min_stations,
                "exclusion_reason": "TOO_FEW_FILTERED_STATIONS",
                "filters": scenario.filters_text(),
            }
        )
    return excluded


def summarize_formula_rows(event_rows: list[dict[str, object]], scenario: Scenario, formulas: list[str], excluded_event_count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    by_formula: dict[str, list[dict[str, object]]] = {formula: [] for formula in formulas}
    for row in event_rows:
        by_formula.setdefault(str(row.get("formula") or ""), []).append(row)

    for formula in formulas:
        formula_rows = by_formula.get(formula, [])
        residuals = [finite_float(row.get("residual_mw")) for row in formula_rows if math.isfinite(finite_float(row.get("residual_mw")))]
        abs_residuals = [abs(value) for value in residuals]
        station_counts = [finite_float(row.get("station_count")) for row in formula_rows if math.isfinite(finite_float(row.get("station_count")))]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_label": scenario.label,
                "tier": scenario.tier,
                "formula": formula,
                "station_aggregation": STATION_AGGREGATION,
                "event_count": len(formula_rows),
                "excluded_event_count": excluded_event_count,
                "total_filtered_station_count": int(sum(station_counts)),
                "median_station_count": median(station_counts),
                "min_station_count": min(station_counts) if station_counts else math.nan,
                "bias_mw": mean(residuals),
                "mae_mw": mean(abs_residuals),
                "rmse_mw": rmse(residuals),
                "median_abs_error_mw": median(abs_residuals),
                "within_0_3_count": sum(value <= 0.3 for value in abs_residuals),
                "within_0_5_count": sum(value <= 0.5 for value in abs_residuals),
                "within_1_0_count": sum(value <= 1.0 for value in abs_residuals),
                "over_1_0_count": sum(value > 1.0 for value in abs_residuals),
                "rank_by_mae": "",
                "recommended_formula": "",
                "filters": scenario.filters_text(),
            }
        )
    ranked = sorted([row for row in rows if math.isfinite(finite_float(row.get("mae_mw")))], key=lambda row: (finite_float(row.get("mae_mw")), finite_float(row.get("rmse_mw")), str(row.get("formula") or "")))
    recommended = str(ranked[0]["formula"]) if ranked else ""
    for index, row in enumerate(ranked, start=1):
        row["rank_by_mae"] = index
        row["recommended_formula"] = recommended
    for row in rows:
        if not row["recommended_formula"]:
            row["recommended_formula"] = recommended
    return rows


def build_filter_benchmark(benchmark_dir: Path, stations_csv: Path, out_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, object]] = []
    if not stations_csv.exists():
        errors.append({"code": "MISSING_STATIONS_CSV", "message": "PGD benchmark stations.csv is missing.", "path": str(stations_csv)})
        return failure_payload(benchmark_dir, stations_csv, out_dir, errors)
    try:
        station_rows = read_csv(stations_csv)
    except (OSError, csv.Error) as exc:
        errors.append({"code": "READ_ERROR", "message": "Could not read PGD benchmark stations.csv.", "path": str(stations_csv), "detail": str(exc)})
        return failure_payload(benchmark_dir, stations_csv, out_dir, errors)
    if not station_rows:
        errors.append({"code": "EMPTY_STATIONS_CSV", "message": "PGD benchmark stations.csv has no rows.", "path": str(stations_csv)})
        return failure_payload(benchmark_dir, stations_csv, out_dir, errors)
    bad_station_aggregation = validate_station_aggregation(station_rows)
    if bad_station_aggregation:
        errors.append(
            {
                "code": "INVALID_STATION_AGGREGATION",
                "message": "PGD filter benchmark requires station_aggregation=median.",
                "values": bad_station_aggregation,
            }
        )
        return failure_payload(benchmark_dir, stations_csv, out_dir, errors)

    available_formulas = {formula_key(row) for row in station_rows}
    formulas = [formula for formula in pgd_contract.FORMULA_NAMES if formula in available_formulas]
    if not formulas:
        errors.append({"code": "NO_FORMULA_ROWS", "message": "No recognized PGD formula station rows found.", "formulas": list(pgd_contract.FORMULA_NAMES)})
        return failure_payload(benchmark_dir, stations_csv, out_dir, errors)

    all_event_rows: list[dict[str, object]] = []
    all_exclusion_rows: list[dict[str, object]] = []
    all_summary_rows: list[dict[str, object]] = []
    recommended_by_scenario: dict[str, str] = {}
    event_counts_by_scenario: dict[str, int] = {}

    for scenario in SCENARIOS:
        event_rows = scenario_event_rows(station_rows, scenario, formulas)
        exclusion_rows = scenario_exclusion_rows(station_rows, scenario)
        summary_rows = summarize_formula_rows(event_rows, scenario, formulas, excluded_event_count=len(exclusion_rows))
        recommended = str(summary_rows[0].get("recommended_formula") or "") if summary_rows else ""
        recommended_by_scenario[scenario.scenario_id] = recommended
        event_counts_by_scenario[scenario.scenario_id] = len({str(row.get("event_id") or "") for row in event_rows})
        all_event_rows.extend(event_rows)
        all_exclusion_rows.extend(exclusion_rows)
        all_summary_rows.extend(summary_rows)

    outputs = {
        "scenario_formula_summary": str(out_dir / "scenario_formula_summary.csv"),
        "scenario_event_errors": str(out_dir / "scenario_event_errors.csv"),
        "scenario_exclusions": str(out_dir / "scenario_exclusions.csv"),
        "summary": str(out_dir / "summary.json"),
        "readme": str(out_dir / "README.md"),
    }
    return {
        "schema_version": "pgd-filter-benchmark/v1",
        "workflow": "pgd_filter_benchmark",
        "status": "OK",
        "created_at": utc_now(),
        "benchmark_dir": str(benchmark_dir),
        "stations_csv": str(stations_csv),
        "out_dir": str(out_dir),
        "station_aggregation": STATION_AGGREGATION,
        "formulas": formulas,
        "scenario_count": len(SCENARIOS),
        "scenarios": [scenario.as_dict() for scenario in SCENARIOS],
        "recommended_by_scenario": recommended_by_scenario,
        "event_counts_by_scenario": event_counts_by_scenario,
        "counts": {
            "input_station_rows": len(station_rows),
            "input_unique_events": len({event_key(row) for row in station_rows}),
            "scenario_formula_summary_rows": len(all_summary_rows),
            "scenario_event_error_rows": len(all_event_rows),
            "scenario_exclusion_rows": len(all_exclusion_rows),
        },
        "outputs": outputs,
        "_rows": {
            "summary": all_summary_rows,
            "events": all_event_rows,
            "exclusions": all_exclusion_rows,
        },
    }


def failure_payload(benchmark_dir: Path, stations_csv: Path, out_dir: Path, errors: list[dict[str, object]]) -> dict[str, Any]:
    return {
        "schema_version": "pgd-filter-benchmark/v1",
        "workflow": "pgd_filter_benchmark",
        "status": "INVALID",
        "created_at": utc_now(),
        "benchmark_dir": str(benchmark_dir),
        "stations_csv": str(stations_csv),
        "out_dir": str(out_dir),
        "errors": errors,
    }


def write_readme(path: Path, payload: dict[str, Any]) -> None:
    summary_rows = payload.get("_rows", {}).get("summary", []) if isinstance(payload.get("_rows"), dict) else []
    lines = [
        "# PGD Filter Benchmark",
        "",
        "This report compares PGD formula errors after station-level quality filters. It consumes the compact benchmark `stations.csv`; it does not rescan waveform files.",
        "",
        "The station aggregation method remains `median`. The three labels are formulas/scaling laws, not aggregation methods.",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Formula | Events | MAE Mw | RMSE Mw | Median Abs Err | >1.0 Mw | Recommended |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {scenario_id} | {formula} | {event_count} | {mae_mw} | {rmse_mw} | {median_abs_error_mw} | {over_1_0_count} | {recommended_formula} |".format(
                scenario_id=row.get("scenario_id", ""),
                formula=row.get("formula", ""),
                event_count=fmt(row.get("event_count")),
                mae_mw=fmt(row.get("mae_mw"), 3),
                rmse_mw=fmt(row.get("rmse_mw"), 3),
                median_abs_error_mw=fmt(row.get("median_abs_error_mw"), 3),
                over_1_0_count=fmt(row.get("over_1_0_count")),
                recommended_formula=row.get("recommended_formula", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `scenario_formula_summary.csv`: formula metrics by filter scenario.",
            "- `scenario_event_errors.csv`: event/formula residuals after each scenario filter.",
            "- `scenario_exclusions.csv`: events excluded by each scenario and station-count gate.",
            "- `summary.json`: machine-readable scenario metadata and output paths.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> None:
    out_dir = Path(str(payload["out_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = payload.pop("_rows")
    write_csv(out_dir / "scenario_formula_summary.csv", rows["summary"], SUMMARY_FIELDS)
    write_csv(out_dir / "scenario_event_errors.csv", rows["events"], EVENT_FIELDS)
    write_csv(out_dir / "scenario_exclusions.csv", rows["exclusions"], EXCLUSION_FIELDS)
    write_json(out_dir / "summary.json", payload)
    payload["_rows"] = rows
    write_readme(out_dir / "README.md", payload)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    benchmark_dir = args.benchmark_dir
    stations_csv = args.stations_csv or benchmark_dir / "stations.csv"
    payload = build_filter_benchmark(benchmark_dir, stations_csv, args.out_dir)
    if payload["status"] != "OK":
        write_json(args.out_dir / "summary.json", payload)
        print(json.dumps({"status": payload["status"], "errors": payload.get("errors", []), "out_dir": str(args.out_dir)}, indent=2))
        return 1
    write_outputs(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "scenario_count": payload["scenario_count"],
                "out_dir": str(args.out_dir),
                "recommended_by_scenario": payload["recommended_by_scenario"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
