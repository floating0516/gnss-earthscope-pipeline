"""Shared GNSS peak ground displacement calculations."""

from __future__ import annotations

import csv
import gzip
import math
from collections import defaultdict
from pathlib import Path


def finite_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def displacement_amplitude(e: float, n: float, u: float, pgd_component: str = "3d") -> float:
    if pgd_component == "horizontal":
        return math.hypot(e, n)
    return math.sqrt(e * e + n * n + u * u)


def rms(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else math.nan


def read_pgd_by_station(
    waveform_path: Path,
    window_start: float,
    window_end: float,
    min_pgd_m: float,
    pgd_component: str,
    noise_window_start: float,
    noise_window_end: float,
) -> dict[str, dict[str, float]]:
    """Read normalized waveforms and compute per-station PGD plus pre-event SNR."""
    pgd_components: dict[str, dict[float, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    noise_components: dict[str, dict[float, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    with gzip.open(waveform_path, "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            offset = finite_float(row.get("Time_Offset_s"))
            if not math.isfinite(offset):
                continue
            component = str(row.get("Component") or "").upper()
            if component not in {"E", "N", "U"}:
                continue
            value = finite_float(row.get("Value_m"))
            if not math.isfinite(value):
                continue
            station = str(row.get("Station") or "").upper()
            if window_start <= offset <= window_end:
                pgd_components[station][offset][component] = value
            if noise_window_start <= offset < noise_window_end:
                noise_components[station][offset][component] = value

    result: dict[str, dict[str, float]] = {}
    for station, by_time in pgd_components.items():
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
            amplitude = displacement_amplitude(e, n, u, pgd_component)
            if not math.isfinite(pgd_m) or amplitude > pgd_m:
                pgd_m = amplitude
                pgd_time = offset
                pgd_e = e
                pgd_n = n
                pgd_u = u
        noise_amplitudes = []
        for values in noise_components.get(station, {}).values():
            if {"E", "N", "U"}.issubset(values):
                noise_amplitudes.append(displacement_amplitude(values["E"], values["N"], values["U"], pgd_component))
        pre_event_rms_m = rms(noise_amplitudes)
        pgd_snr = pgd_m / pre_event_rms_m if math.isfinite(pre_event_rms_m) and pre_event_rms_m > 0 else math.nan
        if math.isfinite(pgd_m) and pgd_m >= min_pgd_m:
            result[station] = {
                "pgd_m": pgd_m,
                "pgd_cm": pgd_m * 100.0,
                "pgd_time_offset_s": pgd_time,
                "pgd_e_m": pgd_e,
                "pgd_n_m": pgd_n,
                "pgd_u_m": pgd_u,
                "pgd_sample_count": float(sample_count),
                "pre_event_rms_m": pre_event_rms_m,
                "pre_event_rms_cm": pre_event_rms_m * 100.0 if math.isfinite(pre_event_rms_m) else math.nan,
                "noise_sample_count": float(len(noise_amplitudes)),
                "pgd_snr": pgd_snr,
            }
    return result


def station_quality_flags(
    pgd: dict[str, float],
    distance_km: float,
    *,
    min_pgd_snr: float,
    quality_max_pgd_time_offset: float,
    quality_max_distance_km: float,
) -> tuple[bool, str]:
    flags = []
    snr = float(pgd.get("pgd_snr", math.nan))
    if not math.isfinite(snr):
        flags.append("no_pre_event_noise")
    elif snr < min_pgd_snr:
        flags.append("low_pgd_snr")
    if quality_max_distance_km > 0 and distance_km > quality_max_distance_km:
        flags.append("far_station")
    if quality_max_pgd_time_offset > 0 and float(pgd["pgd_time_offset_s"]) > quality_max_pgd_time_offset:
        flags.append("late_pgd_peak")
    if float(pgd.get("noise_sample_count", 0.0)) < 30:
        flags.append("short_noise_window")
    return not flags, ",".join(flags)
