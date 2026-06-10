#!/usr/bin/env python3
"""Plot a synthetic three-component GNSS displacement record section.

The script generates synthetic GNSS/event displacement waveforms and renders
them as three image-style record sections: East, North, and Vertical.  The data
generation is intentionally isolated from the plotting routine so the synthetic
arrays can later be replaced by real GNSS displacement matrices.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm


RNG_SEED = 20260429
OUTPUT_FILE = "synthetic_gnss_record_section.png"


def build_record_section_colormap() -> LinearSegmentedColormap:
    """Return a low-saturation gray-blue colormap for waveform sections."""
    colors = [
        (0.02, 0.025, 0.03),   # near black
        (0.16, 0.19, 0.22),    # dark gray-blue
        (0.36, 0.43, 0.49),    # muted blue-gray
        (0.66, 0.72, 0.76),    # pale blue-gray
        (0.94, 0.95, 0.94),    # off-white
    ]
    return LinearSegmentedColormap.from_list("jgr_gray_blue", colors, N=256)


def smooth_along_time(data: np.ndarray, width: int) -> np.ndarray:
    """Apply a short moving average along time to make low-frequency drift."""
    kernel = np.ones(width, dtype=float) / width
    return np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, data)


def ricker_wavelet(time: np.ndarray, center: np.ndarray, frequency: float) -> np.ndarray:
    """Vectorized Ricker-like pulse for coherent seismic wave packets."""
    tau = time[None, :] - center[:, None]
    x = np.pi * frequency * tau
    return (1.0 - 2.0 * x**2) * np.exp(-x**2)


def generate_distances(
    n_traces: int = 430,
    max_distance_km: float = 600.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Create a near-uniform but slightly irregular station-distance axis."""
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)

    distances = np.linspace(0.0, max_distance_km, n_traces)
    distances += rng.normal(0.0, 3.5, size=n_traces)
    distances = np.clip(distances, 0.0, max_distance_km)
    distances.sort()
    return distances


def generate_component(
    component: str,
    time: np.ndarray,
    distances: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate one synthetic component as a distance-by-time matrix.

    Replace this function with real data loading for production use.  The
    returned array should have shape ``(n_stations, n_times)``, ordered by
    increasing epicentral distance.
    """
    n_traces = distances.size
    n_times = time.size

    # Component-specific choices mimic different GNSS displacement responses.
    if component == "East":
        phase_shift = 0.0
        amp_scale = 1.05
        noise_scale = 0.18
        drift_scale = 0.11
        main_freq = 0.070
    elif component == "North":
        phase_shift = 3.0
        amp_scale = 0.92
        noise_scale = 0.20
        drift_scale = 0.13
        main_freq = 0.062
    elif component == "Vertical":
        phase_shift = 7.0
        amp_scale = 0.64
        noise_scale = 0.28
        drift_scale = 0.20
        main_freq = 0.055
    else:
        raise ValueError(f"Unknown component: {component}")

    # Coherent arrivals: time increases with distance, producing a tilted band.
    arrival_main = 16.0 + distances / 4.15 + phase_shift
    arrival_late = 44.0 + distances / 3.25 + 0.45 * phase_shift

    near_field = np.exp(-distances / 285.0)
    long_duration = 1.0 + 1.0 * np.exp(-distances / 150.0)
    trace_amp_jitter = rng.lognormal(mean=0.0, sigma=0.18, size=n_traces)
    polarity = rng.choice([-1.0, 1.0], size=n_traces, p=[0.42, 0.58])
    amplitude = amp_scale * (0.18 + 1.65 * near_field) * trace_amp_jitter * polarity

    main_packet = ricker_wavelet(time, arrival_main, main_freq / long_duration)
    late_packet = ricker_wavelet(time, arrival_late, 0.045 / long_duration)

    # Ringing coda makes the energy band look less like a single clean pulse.
    tau = time[None, :] - arrival_main[:, None]
    coda = np.where(
        tau > 0,
        np.sin(2.0 * np.pi * (0.040 + 0.00003 * distances[:, None]) * tau)
        * np.exp(-tau / (26.0 + 35.0 * near_field[:, None])),
        0.0,
    )

    signal = amplitude[:, None] * (
        1.25 * main_packet
        + 0.42 * late_packet
        + 0.36 * coda
    )

    # Fine horizontal texture: station-by-station offsets, colored noise, drift.
    white_noise = rng.normal(0.0, noise_scale, size=(n_traces, n_times))
    colored_noise = smooth_along_time(rng.normal(0.0, noise_scale, size=(n_traces, n_times)), 5)
    low_frequency = smooth_along_time(rng.normal(0.0, drift_scale, size=(n_traces, n_times)), 31)
    station_bias = rng.normal(0.0, 0.055, size=(n_traces, 1))

    # Slight distance-parallel striping, stronger on the vertical component.
    stripe_strength = 0.035 if component != "Vertical" else 0.075
    stripes = stripe_strength * np.sin(2.0 * np.pi * distances[:, None] / 18.0)
    stripes *= 1.0 + 0.25 * np.sin(2.0 * np.pi * time[None, :] / 58.0)

    data = signal + white_noise + colored_noise + low_frequency + station_bias + stripes

    # Gentle trace normalization keeps near-field strong while avoiding clipping.
    scale = np.percentile(np.abs(data), 98.7)
    return data / scale


def plot_record_section(
    time: np.ndarray,
    distances: np.ndarray,
    components: dict[str, np.ndarray],
    output_file: str = OUTPUT_FILE,
) -> None:
    """Plot East/North/Vertical record sections and save a 300 dpi PNG."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        }
    )

    cmap = build_record_section_colormap()
    fig, axes = plt.subplots(1, 3, figsize=(13, 7), sharex=True, sharey=True)
    fig.patch.set_facecolor("#e6eaec")

    extent = [time.min(), time.max(), distances.min(), distances.max()]
    for ax, name in zip(axes, ["East", "North", "Vertical"], strict=True):
        data = components[name]

        # Symmetric percentile clipping preserves weak texture without overexposure.
        clip = np.percentile(np.abs(data), 98.8)
        norm = TwoSlopeNorm(vmin=-clip, vcenter=0.0, vmax=clip)

        ax.imshow(
            data,
            extent=extent,
            origin="lower",
            aspect="auto",
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
        )

        ax.set_title(name, fontsize=15, pad=10)
        ax.set_xlabel("Time past OT (s)", fontsize=13)
        ax.set_xlim(0, 200)
        ax.set_ylim(0, 600)
        ax.set_xticks([0, 50, 100, 150, 200])
        ax.set_yticks([0, 100, 200, 300, 400, 500, 600])
        ax.tick_params(labelsize=11, length=4)
        ax.grid(False)
        ax.set_facecolor("#c5cdd1")

        for spine in ax.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("black")

    axes[0].set_ylabel("Distance (km)", fontsize=13)

    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.105, top=0.90, wspace=0.16)
    fig.savefig(output_file, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()


def main() -> None:
    """Generate synthetic data and draw the three-component record section."""
    rng = np.random.default_rng(RNG_SEED)
    time = np.arange(0.0, 201.0, 1.0)
    distances = generate_distances(n_traces=430, max_distance_km=600.0, rng=rng)

    components = {
        name: generate_component(name, time, distances, rng)
        for name in ["East", "North", "Vertical"]
    }

    plot_record_section(time, distances, components, OUTPUT_FILE)


if __name__ == "__main__":
    main()
