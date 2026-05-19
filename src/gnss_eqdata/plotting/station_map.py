"""Plot station map with PyGMT for a given earthquake event directory."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pygmt

from gnss_eqdata.io import load_event, load_stations

BASE_DIR = Path(__file__).resolve().parents[3]
GMT_DATA_DIR = BASE_DIR / "data" / "gmt"
RELIEF_30S_TILE_DIR = GMT_DATA_DIR / "earth_relief_30s_p"
RELIEF_30S_CACHE_DIR = GMT_DATA_DIR / "cache"
STATION_RELIEF = Path("@earth_relief_30s")


def _tile_lon_name(lon: int) -> str:
    if lon < 0:
        return f"W{abs(lon):03d}"
    return f"E{lon:03d}"


def _tile_lat_name(lat: int) -> str:
    if lat < 0:
        return f"S{abs(lat):02d}"
    return f"N{lat:02d}"


def _tile_path(lat_base: int, lon_base: int) -> Path:
    return RELIEF_30S_TILE_DIR / f"{_tile_lat_name(lat_base)}{_tile_lon_name(lon_base)}.earth_relief_30s_p.nc"


def _required_tiles(region: list[float]) -> list[Path]:
    west, east, south, north = region
    lon_start = math.floor(west / 15.0) * 15
    lon_stop = math.floor((east - 1e-9) / 15.0) * 15
    lat_start = math.floor(south / 15.0) * 15
    lat_stop = math.floor((north - 1e-9) / 15.0) * 15
    tiles = []
    for lat_base in range(lat_start, lat_stop + 1, 15):
        for lon_base in range(lon_start, lon_stop + 1, 15):
            normalized_lon = ((lon_base + 180) % 360) - 180
            tiles.append(_tile_path(lat_base, normalized_lon))
    return tiles


def _snap_region_to_30s(region: list[float]) -> list[float]:
    inc = 1.0 / 120.0
    west, east, south, north = region
    return [
        math.floor(west / inc) * inc,
        math.ceil(east / inc) * inc,
        math.floor(south / inc) * inc,
        math.ceil(north / inc) * inc,
    ]


def _region_cache_name(region: list[float]) -> str:
    parts = [round(value, 3) for value in region]
    safe = "_".join(str(part).replace("-", "m").replace(".", "p") for part in parts)
    return f"earth_relief_30s_{safe}.grd"


def _local_30s_tiles(region: list[float]) -> list[Path]:
    if not RELIEF_30S_TILE_DIR.is_dir():
        return [STATION_RELIEF]
    tiles = _required_tiles(region)
    missing = [tile.name for tile in tiles if not tile.exists()]
    if missing:
        raise FileNotFoundError("missing 30s relief tiles: " + ", ".join(missing))
    return tiles



def determine_region(ev_lon, ev_lat, stations, padding_deg=1.0):
    """Determine map region based on station distribution and epicenter."""
    valid_stations = stations.dropna(subset=["Latitude", "Longitude"])
    all_lons = np.append(valid_stations["Longitude"].values, ev_lon)
    all_lats = np.append(valid_stations["Latitude"].values, ev_lat)

    lon_min, lon_max = all_lons.min(), all_lons.max()
    if lon_max - lon_min > 180:
        all_lons = np.where(all_lons < 0, all_lons + 360, all_lons)
        ev_lon = ev_lon + 360 if ev_lon < 0 else ev_lon
        lon_min, lon_max = all_lons.min(), all_lons.max()

    lat_min, lat_max = all_lats.min(), all_lats.max()

    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    pad_lon = max(padding_deg, lon_range * 0.15)
    pad_lat = max(padding_deg, lat_range * 0.15)

    region = [
        lon_min - pad_lon,
        lon_max + pad_lon,
        lat_min - pad_lat,
        lat_max + pad_lat,
    ]

    if region[1] - region[0] > 350:
        region[0] = lon_min - 2
        region[1] = lon_max + 2
    region[2] = max(region[2], -90)
    region[3] = min(region[3], 90)

    return region


def _plot_longitudes(ev_lon: float, stations: pd.DataFrame, region: list[float]) -> tuple[float, np.ndarray]:
    if region[0] >= 0 or region[1] > 180:
        return (ev_lon + 360 if ev_lon < 0 else ev_lon, np.where(stations["Longitude"].values < 0, stations["Longitude"].values + 360, stations["Longitude"].values))
    return ev_lon, stations["Longitude"].values


def plot_station_map(event_dir: Path, outdir: Path, dpi: int = 150, out_stem: str = None):
    """Generate station map with topography, beachball, and inset globe."""
    event = load_event(event_dir)
    stations = load_stations(event_dir)

    ev_lat = event["latitude"]
    ev_lon = event["longitude"]
    depth = event.get("depth_km") or 10.0
    mag = event["magnitude"]

    stations = stations.dropna(subset=["Latitude", "Longitude"]).copy()
    if stations.empty:
        print(f"  [station_map] SKIP: no valid station coordinates")
        return None
    date_str = event["date"][:10].replace("-", "/")
    event_label = event["event"]

    strike = event.get("strike", 0)
    dip = event.get("dip", 90)
    rake = event.get("rake", 0)

    if "M " in event_label:
        short_name = event_label.split(" - ")[-1] if " - " in event_label else event_label.split("M ")[1].split(",")[0] if "," in event_label else event_label
    else:
        short_name = event_label
    title = f"{date_str} M@-w@-{mag} {short_name}"
    title = title.replace('"', '')

    region = determine_region(ev_lon, ev_lat, stations)
    relief_tiles = _local_30s_tiles(region)
    plot_ev_lon, station_lons = _plot_longitudes(ev_lon, stations, region)

    lon_span = region[1] - region[0]
    center_lat = (region[2] + region[3]) / 2

    fig = pygmt.Figure()

    fig.basemap(region=region, projection=f"M15c", frame=["af", f"+t{title}"])
    fig.coast(
        shorelines="0.5p,black",
        borders=["1/0.5p,gray50", "2/0.3p,gray70"],
        water="lightskyblue",
        land="white",
        resolution="f",
    )
    pygmt.makecpt(cmap="gray", series=[-6000, 6000])
    for relief_tile in relief_tiles:
        fig.grdimage(str(relief_tile), region=region, shading="+d+a45+nt0.4",
                     cmap=True, transparency=65)

    n_stations = len(stations)
    fig.plot(
        x=station_lons,
        y=stations["Latitude"].values,
        style="c0.25c",
        pen="0.8p,blue",
        fill="white",
        label=f"GNSS ({n_stations})",
    )

    if strike != 0 or dip != 0 or rake != 0:
        focal_mech = dict(
            strike=strike, dip=dip, rake=rake, magnitude=mag
        )
        fig.meca(
            spec=focal_mech,
            longitude=plot_ev_lon,
            latitude=ev_lat,
            depth=depth,
            scale="0.6c",
            compression_fill="black",
            extension_fill="white",
        )
    else:
        fig.plot(
            x=[plot_ev_lon],
            y=[ev_lat],
            style="a0.6c",
            fill="red",
            pen="0.5p,black",
        )

    fig.legend(position="JTL+jTL+o0.2c", box="+gwhite+p0.5p")

    map_width_km = lon_span * 111 * np.cos(np.radians(center_lat))
    scale_length = int(10 ** (np.floor(np.log10(map_width_km / 4))))
    if map_width_km / 4 > scale_length * 5:
        scale_length *= 5
    elif map_width_km / 4 > scale_length * 2:
        scale_length *= 2
    fig.basemap(map_scale=f"jBR+w{scale_length}k+o0.5c/0.5c+f")

    with fig.inset(position="jTR+w3c+o0.2c"):
        fig.coast(
            region="g",
            projection=f"G{ev_lon}/{ev_lat}/3c",
            land="gray90",
            water="white",
            borders="1/0.2p,gray50",
            shorelines="0.2p,gray30",
            frame="g",
        )
        fig.plot(x=[ev_lon], y=[ev_lat], style="a0.3c", fill="red", pen="0.3p,black")

    outdir.mkdir(parents=True, exist_ok=True)
    stem = out_stem if out_stem else event_dir.name
    out_path = outdir / (stem + "_station_map.png")
    fig.savefig(str(out_path), dpi=dpi)
    print(f"  [station_map] saved: {out_path}")
    return out_path
