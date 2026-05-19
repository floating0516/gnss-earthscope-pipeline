from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import pandas as pd

REQUIRED_EVENT_FILES = {"event.json", "stations.csv", "waveforms.csv.gz"}


def find_event_dirs(base: Path | str) -> list[Path]:
    root = Path(base).expanduser().resolve(strict=False)
    if not root.exists():
        return []
    dirs: list[Path] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if (path / "event.json").exists():
            dirs.append(path)
    return dirs


def load_event(event_dir: Path | str) -> dict:
    with (Path(event_dir) / "event.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_stations(event_dir: Path | str) -> pd.DataFrame:
    return pd.read_csv(Path(event_dir) / "stations.csv")


def load_waveforms(event_dir: Path | str) -> pd.DataFrame:
    return pd.read_csv(Path(event_dir) / "waveforms.csv.gz", compression="gzip")


def hypocentral_distance(ev_lat: float, ev_lon: float, sta_lat: float, sta_lon: float, depth_km: float = 0.0) -> float:
    radius = 6371.0
    phi1 = math.radians(ev_lat)
    phi2 = math.radians(sta_lat)
    dphi = math.radians(sta_lat - ev_lat)
    dlambda = math.radians(sta_lon - ev_lon)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    surface_km = 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return math.hypot(surface_km, depth_km or 0.0)
