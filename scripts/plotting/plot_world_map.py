#!/usr/bin/env python3
"""
Plot all GNSS earthquake events on a Pacific-centered world map.

Normalized GNSS earthquake events shown together:
  - Pacific-centered Robinson projection
  - Circles colored by source/region, with size scaled by magnitude
  - Large events drawn first so small events appear on top
  - Ocean bathymetry background; solid land color (no speckles)

Usage:
    uv run python scripts/plotting/plot_world_map.py [--outdir figure] [--dpi 200]
"""

import argparse
import json
import tempfile
from pathlib import Path

import pygmt

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = BASE_DIR / "exports" / "normalized-ok-stations-us-nz"
GMT_DATA_DIR = BASE_DIR / "data" / "gmt"
WORLD_RELIEF = next(
    (
        path
        for path in [
            GMT_DATA_DIR / "earth_relief_10m.grd",
            GMT_DATA_DIR / "earth_relief_10m.nc",
            GMT_DATA_DIR / "earth_relief_10m_p.grd",
        ]
        if path.exists()
    ),
    Path("@earth_relief_10m"),
)

MAGNITUDE_LEGEND_FILL = "170/170/170"
PEN_COLOR = "0.25p,white"
CATEGORY_COLORS = {
    "EarthScope / US": "204/187/68",
    "EarthScope / Americas": "238/102/119",
    "GeoNet / New Zealand": "34/136/51",
    "GA / Australia-SW Pacific": "170/51/119",
    "Unknown": "120/120/120",
}
CATEGORY_ORDER = [
    "EarthScope / US",
    "EarthScope / Americas",
    "GeoNet / New Zealand",
    "GA / Australia-SW Pacific",
    "Unknown",
]


def load_events(base: Path) -> list[dict]:
    events = []
    for p in sorted(base.glob("*/event.json")):
        if p.parent.name.startswith("."):
            continue
        with open(p, encoding="utf-8") as f:
            ev = json.load(f)
        if {"longitude", "latitude", "magnitude"} <= ev.keys():
            events.append(ev)
    return events


def mag_to_size(mag: float) -> float:
    """Size scale with moderate ratio: M6→0.09c, M7→0.17c, M8→0.32c, M9→0.58c."""
    return 0.09 * (1.85 ** (mag - 6.0))


def event_category(event: dict) -> str:
    region = str(event.get("region") or "")
    network = str(event.get("network") or "")
    subset = str(event.get("earthscope_subset") or "")
    if subset == "usa" or region == "US":
        return "EarthScope / US"
    if subset == "nonconus" or region == "Americas":
        return "EarthScope / Americas"
    if region == "NZ" or network == "GeoNet":
        return "GeoNet / New Zealand"
    if region == "AU-SW-Pacific" or network == "Geoscience Australia":
        return "GA / Australia-SW Pacific"
    return "Unknown"


def main():
    parser = argparse.ArgumentParser(description="Plot world event map")
    parser.add_argument("--dataset", type=Path, action="append", default=[], help="Normalized dataset directory; repeat to combine datasets")
    parser.add_argument("--outdir", type=str, default="figure")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    outdir = Path(args.outdir).expanduser()
    if not outdir.is_absolute():
        outdir = BASE_DIR / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    datasets = args.dataset or [DEFAULT_DATASET]
    resolved = []
    for dataset in datasets:
        path = dataset.expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        resolved.append(path)

    groups = [(path, load_events(path)) for path in resolved]
    all_events = [event for _, events in groups for event in events]
    if not all_events:
        raise SystemExit("No events found.")

    all_events.sort(key=lambda e: e["magnitude"], reverse=True)

    years = sorted(e["date"][:4] for e in all_events)
    year_range = f"{years[0]}-{years[-1]}"
    n_total = len(all_events)

    for path, events in groups:
        print(f"{path}: {len(events)} events")
    print(f"Total:            {n_total} events ({year_range})")

    pygmt.config(
        FONT_ANNOT_PRIMARY="9p,Helvetica,black",
        FONT_LABEL="10p,Helvetica,black",
        FONT_TITLE="16p,Helvetica-Bold,black",
        FONT_SUBTITLE="11p,Helvetica,gray40",
        MAP_FRAME_PEN="0.8p,black",
        MAP_GRID_PEN_PRIMARY="0.3p,gray70@50",
        MAP_TITLE_OFFSET="0.2c",
    )

    fig = pygmt.Figure()

    fig.basemap(
        region=[-180, 180, -75, 85],
        projection="R180/22c",
        frame=[
            "afg",
            f"WSnE+tGNSS Earthquake Events+s{year_range}; n = {n_total}",
        ],
    )

    pygmt.makecpt(cmap="geo", series=[-8000, 8000])
    fig.grdimage(str(WORLD_RELIEF), shading="+d+a45+nt0.3", cmap=True, transparency=45)

    fig.coast(
        shorelines="0.4p,gray30",
        borders="1/0.3p,gray60",
        land="gainsboro",
        resolution="l",
    )

    categories = {event_category(event) for event in all_events}
    for event in all_events:
        category = event_category(event)
        fig.plot(
            x=[event["longitude"]],
            y=[event["latitude"]],
            style="cc",
            size=[mag_to_size(event["magnitude"])],
            fill=CATEGORY_COLORS[category],
            pen=PEN_COLOR,
            transparency=0,
        )

    s6 = mag_to_size(6)
    s7 = mag_to_size(7)
    s8 = mag_to_size(8)
    s9 = mag_to_size(9)
    legend_spec = (
        "G 0.08c\n"
        "L 1.1 1 L Magnitude (size):\n"
        "G 0.06c\n"
        f"S 0.35c c {s6:.3f}c {MAGNITUDE_LEGEND_FILL} {PEN_COLOR} 0.82c  M 6\n"
        f"S 0.35c c {s7:.3f}c {MAGNITUDE_LEGEND_FILL} {PEN_COLOR} 0.82c  M 7\n"
        f"S 0.35c c {s8:.3f}c {MAGNITUDE_LEGEND_FILL} {PEN_COLOR} 0.82c  M 8\n"
        f"S 0.35c c {s9:.3f}c {MAGNITUDE_LEGEND_FILL} {PEN_COLOR} 0.82c  M 9\n"
        "G 0.10c\n"
        "L 1.1 1 L Source / region (color):\n"
        "G 0.06c\n"
    )
    for category in CATEGORY_ORDER:
        if category in categories:
            legend_spec += f"S 0.35c c 0.13c {CATEGORY_COLORS[category]} {PEN_COLOR} 0.82c  {category}\n"
    legend_spec += "G 0.05c\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(legend_spec)
        tmp_path = tmp.name

    fig.legend(
        spec=tmp_path,
        position="JBR+jBR+o0.4c/0.4c",
        box="+gwhite@30+p0.6p,gray40",
    )
    Path(tmp_path).unlink(missing_ok=True)

    out_path = outdir / "world_map.png"
    fig.savefig(str(out_path), dpi=args.dpi)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
