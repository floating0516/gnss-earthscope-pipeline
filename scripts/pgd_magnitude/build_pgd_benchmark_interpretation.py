#!/usr/bin/env python3
"""Build a PGD benchmark interpretation report and SVG figures."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract


DEFAULT_FILTER_DIR = Path("reports/pgd_magnitude/benchmark/latest/filter_benchmark")
DEFAULT_OUT_DIR = DEFAULT_FILTER_DIR / "interpretation"
FORMULAS = list(pgd_contract.FORMULA_NAMES)
FORMULA_COLORS = {"melgar_2015": "#4c78a8", "crowell_2016_gfast": "#f58518", "ruhl_2019": "#54a24b"}
KEY_SCENARIOS = {
    "all": "all",
    "quality": "quality_snr3_time300_dist300_min3sta",
    "strict": "strict_snr5_time300_dist300_min3sta",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filter-dir", type=Path, default=DEFAULT_FILTER_DIR, help="PGD filter benchmark directory.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Interpretation output directory.")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def finite_int(value: object) -> int:
    number = finite_float(value)
    return int(number) if math.isfinite(number) else 0


def fmt(value: object, digits: int = 3) -> str:
    number = finite_float(value)
    if math.isfinite(number):
        return f"{number:.{digits}f}"
    return "" if value is None else str(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def svg_escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2.0
    return dst_min + (value - src_min) * (dst_max - dst_min) / (src_max - src_min)


def write_svg(path: Path, width: int, height: int, body: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def load_inputs(filter_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    summary_path = filter_dir / "scenario_formula_summary.csv"
    events_path = filter_dir / "scenario_event_errors.csv"
    exclusions_path = filter_dir / "scenario_exclusions.csv"
    metadata_path = filter_dir / "summary.json"
    missing = [str(path) for path in [summary_path, events_path, exclusions_path, metadata_path] if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing PGD filter benchmark inputs: " + ", ".join(missing))
    return read_csv(summary_path), read_csv(events_path), read_csv(exclusions_path), read_json(metadata_path)


def ranked_rows(summary_rows: list[dict[str, str]], scenario_id: str) -> list[dict[str, str]]:
    rows = [row for row in summary_rows if row.get("scenario_id") == scenario_id]
    return sorted(rows, key=lambda row: (finite_int(row.get("rank_by_mae")) or 99, finite_float(row.get("mae_mw")), row.get("formula", "")))


def best_row(summary_rows: list[dict[str, str]], scenario_id: str) -> dict[str, str]:
    rows = ranked_rows(summary_rows, scenario_id)
    return rows[0] if rows else {}


def formula_row(summary_rows: list[dict[str, str]], scenario_id: str, formula: str) -> dict[str, str]:
    return next((row for row in summary_rows if row.get("scenario_id") == scenario_id and row.get("formula") == formula), {})


def scenario_highlight(summary_rows: list[dict[str, str]], scenario_id: str) -> dict[str, object]:
    best = best_row(summary_rows, scenario_id)
    return {
        "scenario_id": scenario_id,
        "recommended_formula": best.get("recommended_formula") or best.get("formula") or "",
        "event_count": finite_int(best.get("event_count")),
        "excluded_event_count": finite_int(best.get("excluded_event_count")),
        "best_mae_mw": finite_float(best.get("mae_mw")),
        "best_rmse_mw": finite_float(best.get("rmse_mw")),
        "best_median_abs_error_mw": finite_float(best.get("median_abs_error_mw")),
        "filters": best.get("filters") or "",
    }


def build_highlights(summary_rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    return {name: scenario_highlight(summary_rows, scenario_id) for name, scenario_id in KEY_SCENARIOS.items()}


def selected_summary_rows(summary_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    order = [
        "all",
        "pgd_ge_1cm",
        "pgd_ge_2cm",
        "pgd_ge_5cm",
        "snr_ge_3",
        "snr_ge_5",
        "dist_le_300km",
        "dist_le_200km",
        KEY_SCENARIOS["quality"],
        KEY_SCENARIOS["strict"],
    ]
    selected = []
    for scenario_id in order:
        selected.extend([row for row in summary_rows if row.get("scenario_id") == scenario_id])
    return selected


def plot_scenario_mae_rmse(summary_rows: list[dict[str, str]], path: Path) -> None:
    rows = selected_summary_rows(summary_rows)
    width = 1280
    height = 520
    left = 70
    top = 45
    plot_w = width - 110
    plot_h = 300
    max_value = max([finite_float(row.get("rmse_mw")) for row in rows] + [1.0])
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">PGD filter scenarios: formula MAE</text>']
    body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
    for tick in [0.0, max_value / 2.0, max_value]:
        y = scale(tick, 0.0, max_value, top + plot_h, top)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#ddd"/>')
        body.append(f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" font-family="sans-serif">{tick:.2f}</text>')
    bar_w = plot_w / max(len(rows), 1) * 0.7
    for index, row in enumerate(rows):
        value = finite_float(row.get("mae_mw"))
        center = left + (index + 0.5) * plot_w / max(len(rows), 1)
        bar_h = scale(value, 0.0, max_value, 0.0, plot_h)
        formula = row.get("formula", "")
        body.append(
            f'<rect x="{center - bar_w / 2:.1f}" y="{top + plot_h - bar_h:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{FORMULA_COLORS.get(formula, "#777")}">'
            f'<title>{svg_escape(row.get("scenario_id"))} {svg_escape(formula)} MAE={value:.3f} RMSE={fmt(row.get("rmse_mw"))}</title></rect>'
        )
        if formula == FORMULAS[-1]:
            body.append(f'<text x="{center:.1f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="9" font-family="sans-serif" transform="rotate(55 {center:.1f} {top + plot_h + 18})">{svg_escape(row.get("scenario_id"))}</text>')
    legend_x = 960
    for offset, formula in enumerate(FORMULAS):
        y = 400 + offset * 18
        body.append(f'<rect x="{legend_x}" y="{y - 10}" width="10" height="10" fill="{FORMULA_COLORS[formula]}"/>')
        body.append(f'<text x="{legend_x + 16}" y="{y}" font-size="12" font-family="sans-serif">{formula}</text>')
    write_svg(path, width, height, body)


def plot_event_count_vs_mae(summary_rows: list[dict[str, str]], path: Path) -> None:
    rows = selected_summary_rows(summary_rows)
    width = 760
    height = 460
    left = 70
    top = 45
    plot_w = 610
    plot_h = 310
    event_counts = [finite_float(row.get("event_count")) for row in rows]
    maes = [finite_float(row.get("mae_mw")) for row in rows]
    max_count = max(event_counts + [1.0])
    max_mae = max(maes + [1.0])
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">Event count vs formula MAE</text>']
    body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
    for tick in [0.0, max_count / 2.0, max_count]:
        x = scale(tick, 0.0, max_count, left, left + plot_w)
        body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#eee"/>')
        body.append(f'<text x="{x:.1f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="10" font-family="sans-serif">{tick:.0f}</text>')
    for tick in [0.0, max_mae / 2.0, max_mae]:
        y = scale(tick, 0.0, max_mae, top + plot_h, top)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#eee"/>')
        body.append(f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" font-family="sans-serif">{tick:.2f}</text>')
    for row in rows:
        x = scale(finite_float(row.get("event_count")), 0.0, max_count, left, left + plot_w)
        y = scale(finite_float(row.get("mae_mw")), 0.0, max_mae, top + plot_h, top)
        formula = row.get("formula", "")
        radius = 5 if finite_int(row.get("rank_by_mae")) == 1 else 3.5
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{FORMULA_COLORS.get(formula, "#777")}" fill-opacity="0.75"><title>{svg_escape(row.get("scenario_id"))} {svg_escape(formula)} events={row.get("event_count")} MAE={row.get("mae_mw")}</title></circle>')
    body.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" font-size="12" font-family="sans-serif">event count</text>')
    body.append(f'<text x="20" y="{top + plot_h / 2:.1f}" transform="rotate(-90 20 {top + plot_h / 2:.1f})" text-anchor="middle" font-size="12" font-family="sans-serif">MAE Mw</text>')
    write_svg(path, width, height, body)


def plot_estimated_vs_catalog(event_rows: list[dict[str, str]], scenario_id: str, path: Path, title: str) -> None:
    rows = [row for row in event_rows if row.get("scenario_id") == scenario_id]
    width = 600
    height = 520
    left = 70
    top = 50
    plot_w = 420
    plot_h = 360
    values = [finite_float(row.get("usgs_magnitude")) for row in rows] + [finite_float(row.get("estimated_mw_median")) for row in rows]
    finite_values = [value for value in values if math.isfinite(value)]
    axis_min = min([5.8] + finite_values)
    axis_max = max([8.0] + finite_values)
    body = [f'<text x="20" y="28" font-size="18" font-family="sans-serif">{svg_escape(title)}</text>']
    body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top}" stroke="#444" stroke-dasharray="4 4"/>')
    for tick in [6.0, 7.0, 8.0]:
        x = scale(tick, axis_min, axis_max, left, left + plot_w)
        y = scale(tick, axis_min, axis_max, top + plot_h, top)
        body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#eee"/>')
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#eee"/>')
        body.append(f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" font-size="10" font-family="sans-serif">{tick:.0f}</text>')
        body.append(f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" font-family="sans-serif">{tick:.0f}</text>')
    for row in rows:
        formula = row.get("formula", "")
        x = scale(finite_float(row.get("usgs_magnitude")), axis_min, axis_max, left, left + plot_w)
        y = scale(finite_float(row.get("estimated_mw_median")), axis_min, axis_max, top + plot_h, top)
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{FORMULA_COLORS.get(formula, "#777")}" fill-opacity="0.7"><title>{svg_escape(row.get("event_id"))} {svg_escape(formula)} residual={row.get("residual_mw")}</title></circle>')
    for offset, formula in enumerate(FORMULAS):
        y = 440 + offset * 18
        body.append(f'<circle cx="390" cy="{y - 4}" r="4" fill="{FORMULA_COLORS[formula]}"/>')
        body.append(f'<text x="402" y="{y}" font-size="12" font-family="sans-serif">{formula}</text>')
    body.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" font-size="12" font-family="sans-serif">catalog Mw</text>')
    body.append(f'<text x="22" y="{top + plot_h / 2:.1f}" transform="rotate(-90 22 {top + plot_h / 2:.1f})" text-anchor="middle" font-size="12" font-family="sans-serif">estimated Mw</text>')
    write_svg(path, width, height, body)


def plot_residual_diagnostics(event_rows: list[dict[str, str]], path: Path) -> None:
    rows = [row for row in event_rows if row.get("scenario_id") == "all" and row.get("formula") == "ruhl_2019"]
    panels = [
        ("median_distance_km", "distance km"),
        ("median_pgd_snr", "PGD SNR"),
        ("median_pgd_time_offset_s", "peak time s"),
    ]
    width = 1080
    height = 420
    body = ['<text x="20" y="28" font-size="18" font-family="sans-serif">All-event ruhl_2019 residual diagnostics</text>']
    for panel_index, (field, label) in enumerate(panels):
        left = 65 + panel_index * 340
        top = 55
        plot_w = 260
        plot_h = 260
        xs = [finite_float(row.get(field)) for row in rows if math.isfinite(finite_float(row.get(field)))]
        ys = [finite_float(row.get("abs_residual_mw")) for row in rows if math.isfinite(finite_float(row.get("abs_residual_mw")))]
        x_min = min(xs + [0.0])
        x_max = max(xs + [1.0])
        y_min = 0.0
        y_max = max(ys + [1.0])
        body.append(f'<text x="{left + plot_w / 2:.1f}" y="48" text-anchor="middle" font-size="13" font-family="sans-serif">abs residual vs {svg_escape(label)}</text>')
        body.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#777"/>')
        for row in rows:
            x_value = finite_float(row.get(field))
            y_value = finite_float(row.get("abs_residual_mw"))
            if not math.isfinite(x_value) or not math.isfinite(y_value):
                continue
            x = scale(x_value, x_min, x_max, left, left + plot_w)
            y = scale(y_value, y_min, y_max, top + plot_h, top)
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{FORMULA_COLORS["ruhl_2019"]}" fill-opacity="0.7"><title>{svg_escape(row.get("event_id"))} abs residual={y_value:.3f}</title></circle>')
        body.append(f'<text x="{left + plot_w / 2:.1f}" y="{top + plot_h + 18}" text-anchor="middle" font-size="11" font-family="sans-serif">{svg_escape(label)}</text>')
        body.append(f'<text x="{left - 38}" y="{top + plot_h / 2:.1f}" transform="rotate(-90 {left - 38} {top + plot_h / 2:.1f})" text-anchor="middle" font-size="11" font-family="sans-serif">abs residual Mw</text>')
    write_svg(path, width, height, body)


def write_figures(summary_rows: list[dict[str, str]], event_rows: list[dict[str, str]], figure_dir: Path) -> dict[str, dict[str, str]]:
    outputs = {
        "scenario_mae_rmse": {"path": str(figure_dir / "scenario_mae_rmse.svg"), "scenario_id": "all_scenarios"},
        "event_count_vs_mae": {"path": str(figure_dir / "event_count_vs_mae.svg"), "scenario_id": "all_scenarios"},
        "estimated_vs_catalog_all": {"path": str(figure_dir / "estimated_vs_catalog_all.svg"), "scenario_id": KEY_SCENARIOS["all"]},
        "estimated_vs_catalog_quality": {"path": str(figure_dir / "estimated_vs_catalog_quality.svg"), "scenario_id": KEY_SCENARIOS["quality"]},
        "estimated_vs_catalog_strict": {"path": str(figure_dir / "estimated_vs_catalog_strict.svg"), "scenario_id": KEY_SCENARIOS["strict"]},
        "residual_diagnostics": {"path": str(figure_dir / "residual_diagnostics.svg"), "scenario_id": KEY_SCENARIOS["all"]},
    }
    plot_scenario_mae_rmse(summary_rows, Path(outputs["scenario_mae_rmse"]["path"]))
    plot_event_count_vs_mae(summary_rows, Path(outputs["event_count_vs_mae"]["path"]))
    plot_estimated_vs_catalog(event_rows, KEY_SCENARIOS["all"], Path(outputs["estimated_vs_catalog_all"]["path"]), "ALL: estimated vs catalog Mw")
    plot_estimated_vs_catalog(event_rows, KEY_SCENARIOS["quality"], Path(outputs["estimated_vs_catalog_quality"]["path"]), "QUALITY: estimated vs catalog Mw")
    plot_estimated_vs_catalog(event_rows, KEY_SCENARIOS["strict"], Path(outputs["estimated_vs_catalog_strict"]["path"]), "STRICT: estimated vs catalog Mw")
    plot_residual_diagnostics(event_rows, Path(outputs["residual_diagnostics"]["path"]))
    return outputs


def interpretation_payload(
    *,
    filter_dir: Path,
    out_dir: Path,
    summary_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    exclusion_rows: list[dict[str, str]],
    filter_summary: dict[str, Any],
    figures: dict[str, dict[str, str]],
) -> dict[str, Any]:
    highlights = build_highlights(summary_rows)
    amplitude_1 = scenario_highlight(summary_rows, "pgd_ge_1cm")
    amplitude_2 = scenario_highlight(summary_rows, "pgd_ge_2cm")
    return {
        "schema_version": "pgd-benchmark-interpretation/v1",
        "workflow": "pgd_benchmark_interpretation",
        "status": "OK",
        "created_at": utc_now(),
        "filter_dir": str(filter_dir),
        "out_dir": str(out_dir),
        "station_aggregation": pgd_contract.STATION_AGGREGATION_METHOD,
        "formulas": FORMULAS,
        "highlights": highlights,
        "amplitude_filter_finding": {
            "pgd_ge_1cm_event_count": amplitude_1["event_count"],
            "pgd_ge_2cm_event_count": amplitude_2["event_count"],
            "interpretation": "PGD amplitude thresholds at 1 cm and 2 cm do not materially reduce the current benchmark sample.",
        },
        "input_counts": {
            "scenario_formula_summary_rows": len(summary_rows),
            "scenario_event_error_rows": len(event_rows),
            "scenario_exclusion_rows": len(exclusion_rows),
        },
        "filter_summary": filter_summary,
        "figures": figures,
        "outputs": {
            "markdown": str(out_dir / "pgd_benchmark_interpretation.md"),
            "json": str(out_dir / "pgd_benchmark_interpretation.json"),
            "figures_dir": str(out_dir / "figures"),
        },
    }


def write_markdown(path: Path, payload: dict[str, Any], summary_rows: list[dict[str, str]]) -> None:
    highlights = payload["highlights"]
    lines = [
        "# PGD Benchmark Interpretation",
        "",
        "This report interprets the PGD formula benchmark across ALL, QUALITY, and STRICT data tiers.",
        "",
        "The station aggregation method is fixed to `median`; `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas/scaling laws.",
        "",
        "## Tier Summary",
        "",
        "| Tier | Scenario | Events | Recommended formula | Best MAE | Best RMSE |",
        "|---|---|---:|---|---:|---:|",
    ]
    for tier in ["all", "quality", "strict"]:
        item = highlights[tier]
        lines.append(
            f"| {tier.upper()} | `{item['scenario_id']}` | {item['event_count']} | `{item['recommended_formula']}` | {fmt(item['best_mae_mw'])} | {fmt(item['best_rmse_mw'])} |"
        )
    lines.extend(
        [
            "",
            "## Main Interpretation",
            "",
            "- ALL is the coverage baseline and should remain in the benchmark package.",
            "- QUALITY is the main formula-comparison tier because it balances error reduction with enough events to inspect.",
            "- STRICT is a high-confidence reference tier. It should not replace ALL or QUALITY because the sample is small.",
            "- PGD amplitude thresholds at 1 cm and 2 cm do not materially change the current sample, so they are weak primary filters.",
            "",
            "## Formula Metrics By Scenario",
            "",
            "| Scenario | Formula | Events | Bias | MAE | RMSE | Median Abs Err | >1 Mw | Rank |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in selected_summary_rows(summary_rows):
        lines.append(
            f"| `{row.get('scenario_id')}` | `{row.get('formula')}` | {row.get('event_count')} | {fmt(row.get('bias_mw'))} | {fmt(row.get('mae_mw'))} | {fmt(row.get('rmse_mw'))} | {fmt(row.get('median_abs_error_mw'))} | {row.get('over_1_0_count')} | {row.get('rank_by_mae')} |"
        )
    lines.extend(
        [
            "",
            "## Figures",
            "",
        ]
    )
    for name, info in payload["figures"].items():
        rel = Path(info["path"]).name if name.startswith("estimated") else Path(info["path"]).name
        lines.append(f"- `{name}`: `figures/{rel}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_interpretation(filter_dir: Path, out_dir: Path) -> dict[str, Any]:
    summary_rows, event_rows, exclusion_rows, filter_summary = load_inputs(filter_dir)
    figure_dir = out_dir / "figures"
    figures = write_figures(summary_rows, event_rows, figure_dir)
    payload = interpretation_payload(
        filter_dir=filter_dir,
        out_dir=out_dir,
        summary_rows=summary_rows,
        event_rows=event_rows,
        exclusion_rows=exclusion_rows,
        filter_summary=filter_summary,
        figures=figures,
    )
    write_json(out_dir / "pgd_benchmark_interpretation.json", payload)
    write_markdown(out_dir / "pgd_benchmark_interpretation.md", payload, summary_rows)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = build_interpretation(args.filter_dir, args.out_dir)
    except Exception as exc:  # noqa: BLE001
        error_payload = {
            "schema_version": "pgd-benchmark-interpretation/v1",
            "workflow": "pgd_benchmark_interpretation",
            "status": "INVALID",
            "created_at": utc_now(),
            "filter_dir": str(args.filter_dir),
            "out_dir": str(args.out_dir),
            "error": str(exc),
        }
        write_json(args.out_dir / "pgd_benchmark_interpretation.json", error_payload)
        print(json.dumps({"status": "INVALID", "error": str(exc), "out_dir": str(args.out_dir)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": payload["status"],
                "out_dir": str(args.out_dir),
                "highlights": payload["highlights"],
                "figure_count": len(payload["figures"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
