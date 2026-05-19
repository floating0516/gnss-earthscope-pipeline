"""Plot record section (E/N/U) for a given earthquake event directory."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from gnss_eqdata.io import hypocentral_distance, load_event, load_stations, load_waveforms


def plot_record_section(event_dir: Path, outdir: Path, dpi: int = 150, out_stem: str = None):
    """Generate 3-panel record section plot."""
    event = load_event(event_dir)
    stations = load_stations(event_dir)
    waveforms = load_waveforms(event_dir)

    ev_lat = event["latitude"]
    ev_lon = event["longitude"]
    depth = event.get("depth_km") or 10.0
    mag = event["magnitude"]
    event_name = event["event"]
    date_str = event["date"][:10].replace("-", "/")

    stations = stations.dropna(subset=["Latitude", "Longitude"]).copy()
    if stations.empty:
        print(f"  [record_section] SKIP: no valid station coordinates")
        return None

    stations["hypo_dist_km"] = stations.apply(
        lambda row: hypocentral_distance(
            ev_lat, ev_lon, row["Latitude"], row["Longitude"], depth
        ),
        axis=1,
    )

    stations = stations[stations["hypo_dist_km"] <= 1000].copy()
    if stations.empty:
        print(f"  [record_section] SKIP: no stations within 1000 km")
        return None

    dist_map = dict(zip(stations["Station"], stations["hypo_dist_km"]))

    waveforms["dist_km"] = waveforms["Station"].map(dist_map)
    waveforms = waveforms.dropna(subset=["dist_km"])

    t_min = max(waveforms["Time_Offset_s"].min(), -100.0)
    t_max = min(waveforms["Time_Offset_s"].max(), 600.0)
    waveforms = waveforms[
        (waveforms["Time_Offset_s"] >= t_min) & (waveforms["Time_Offset_s"] <= t_max)
    ].copy()

    amp_abs = waveforms["Value_m"].abs()
    amp_abs = amp_abs[amp_abs <= 10.0]
    max_amp = amp_abs.quantile(0.98) if len(amp_abs) > 0 else 1e-3
    if max_amp == 0 or np.isnan(max_amp):
        max_amp = 1e-3

    max_amp_cm = max_amp * 100
    scale_options = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
    scale_cm = min(scale_options, key=lambda x: abs(x - max_amp_cm * 0.5))
    scale_m = scale_cm / 100.0

    dist_values = sorted(dist_map.values())
    dist_range = max(dist_values) - min(dist_values) if len(dist_values) > 1 else 100.0
    visual_amp = dist_range * 0.03
    norm_factor = visual_amp / max_amp

    components = ["E", "N", "U"]
    titles = ["East", "North", "Up"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 8), sharey=True)

    for ax, comp, title in zip(axes, components, titles):
        comp_data = waveforms[waveforms["Component"] == comp]

        for station_name, grp in comp_data.groupby("Station"):
            if station_name not in dist_map:
                continue
            dist = dist_map[station_name]
            grp_sorted = grp.sort_values("Time_Offset_s")
            t = grp_sorted["Time_Offset_s"].values
            amp = grp_sorted["Value_m"].values

            y = dist + amp * norm_factor
            ax.plot(t, y, "k-", linewidth=0.3, rasterized=True)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Time Relative to Origin (s)", fontsize=10)
        ax.set_xlim(t_min, t_max)
        ax.grid(False)

    axes[0].set_ylabel("Hypocentral Distance (km)", fontsize=10)

    pad = dist_range * 0.05
    y_min = min(dist_values) - pad
    y_max = max(dist_values) + pad
    for ax in axes:
        ax.set_ylim(max(0, y_min), y_max)

    ax0 = axes[0]
    x_range = ax0.get_xlim()
    y_range = ax0.get_ylim()
    bar_x = x_range[0] + (x_range[1] - x_range[0]) * 0.05
    bar_y = y_range[0] + (y_range[1] - y_range[0]) * 0.05
    bar_height = scale_m * norm_factor
    ax0.plot(
        [bar_x, bar_x], [bar_y, bar_y + bar_height], "r-", linewidth=2.5
    )
    if scale_cm >= 1:
        label = f"{int(scale_cm)} cm"
    elif scale_cm >= 0.1:
        label = f"{scale_cm:.1f} cm"
    else:
        label = f"{scale_cm * 10:.1f} mm"
    ax0.text(
        bar_x + (x_range[1] - x_range[0]) * 0.01,
        bar_y + bar_height / 2,
        label,
        color="red",
        fontsize=9,
        fontweight="bold",
        va="center",
    )

    fig.suptitle(f"{date_str}  Mw{mag}  {event_name.split(' - ')[-1] if ' - ' in event_name else event_name.split('M ')[1] if 'M ' in event_name else event_name}",
                 fontsize=11, y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    outdir.mkdir(parents=True, exist_ok=True)
    stem = out_stem if out_stem else event_dir.name
    out_path = outdir / (stem + "_record_section.png")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [record_section] saved: {out_path}")
    return out_path
