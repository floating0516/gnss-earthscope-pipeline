"""Command-line entry points for GNSS earthquake data plotting."""

import argparse
import json
import traceback
from pathlib import Path

from gnss_eq.data_io import find_event_dirs

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BASE_DIR / "exports" / "normalized-ok-stations-us-nz"
DEFAULT_OUTDIR = BASE_DIR / "figure"


def _resolve_data_dir(value: str | None) -> Path:
    if not value:
        return DEFAULT_DATA_DIR
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def _resolve_outdir(value: str | None) -> Path:
    if not value:
        return DEFAULT_OUTDIR
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def _list_events(base: Path):
    """List all events with basic info."""
    dirs = find_event_dirs(base)
    print(f"Found {len(dirs)} events:\n")
    print(f"{'Directory':<45} {'Mag':>4} {'Stations':>8}  Event")
    print("-" * 100)
    for d in dirs:
        with open(d / "event.json", encoding="utf-8") as f:
            ev = json.load(f)
        print(f"{d.name:<45} {ev['magnitude']:>4.1f} {ev.get('stations', '?'):>8}  {ev['event']}")


def plot_all_main():
    """Batch plot all earthquake events: record section + station map."""
    parser = argparse.ArgumentParser(description="Batch plot all events")
    parser.add_argument("--base", type=str, default=str(DEFAULT_DATA_DIR), help="Normalized dataset directory")
    parser.add_argument("--outdir", type=str, default=str(DEFAULT_OUTDIR), help="Output directory")
    parser.add_argument("--events", nargs="*", help="Specific event dirs to plot (default: all)")
    parser.add_argument("--list", action="store_true", help="List all available events")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--skip-map", action="store_true", help="Skip station map")
    parser.add_argument("--skip-waveform", action="store_true", help="Skip record section")
    args = parser.parse_args()

    base = _resolve_data_dir(args.base)
    if args.list:
        _list_events(base)
        return

    from gnss_eq.plotting.record_section import plot_record_section

    outdir = _resolve_outdir(args.outdir)

    if args.events:
        event_dirs = [Path(e).expanduser() if Path(e).expanduser().is_absolute() else base / e for e in args.events]
    else:
        event_dirs = find_event_dirs(base)

    print(f"Processing {len(event_dirs)} events → {outdir}/\n")

    success = 0
    failed = []

    for i, event_dir in enumerate(event_dirs, 1):
        print(f"[{i}/{len(event_dirs)}] {event_dir.name}")

        if not event_dir.is_dir() or not (event_dir / "event.json").exists():
            print(f"  SKIP: not a valid event directory")
            continue

        event_failed = False
        try:
            if not args.skip_waveform:
                plot_record_section(event_dir, outdir, dpi=args.dpi)
        except Exception as e:
            event_failed = True
            print(f"  ERROR (record_section): {e}")
            traceback.print_exc()
            failed.append((event_dir.name, "record_section", str(e)))

        try:
            if not args.skip_map:
                from gnss_eq.plotting.station_map import plot_station_map
                plot_station_map(event_dir, outdir, dpi=args.dpi)
        except Exception as e:
            event_failed = True
            print(f"  ERROR (station_map): {e}")
            traceback.print_exc()
            failed.append((event_dir.name, "station_map", str(e)))

        if not event_failed:
            success += 1
        print()

    print(f"\nDone: {success}/{len(event_dirs)} events processed.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for name, stage, err in failed:
            print(f"  {name} [{stage}]: {err}")
        raise SystemExit(1)


def plot_single_main():
    """Plot record section and/or station map for a single earthquake event."""
    import sys

    parser = argparse.ArgumentParser(description="Plot single event")
    parser.add_argument("event_dir", type=str, help="Event directory name or path")
    parser.add_argument("--base", type=str, default=str(DEFAULT_DATA_DIR), help="Normalized dataset directory")
    parser.add_argument("--outdir", type=str, default=str(DEFAULT_OUTDIR), help="Output directory")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--only", choices=["map", "waveform"], help="Plot only map or waveform")
    args = parser.parse_args()

    from gnss_eq.plotting.record_section import plot_record_section

    base = _resolve_data_dir(args.base)
    event_dir = Path(args.event_dir).expanduser()
    if not event_dir.is_absolute():
        event_dir = base / event_dir

    if not event_dir.is_dir():
        print(f"Error: {event_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not (event_dir / "event.json").exists():
        print(f"Error: {event_dir} does not contain event.json", file=sys.stderr)
        sys.exit(1)

    outdir = _resolve_outdir(args.outdir)

    if args.only != "map":
        plot_record_section(event_dir, outdir, dpi=args.dpi)
    if args.only != "waveform":
        from gnss_eq.plotting.station_map import plot_station_map
        plot_station_map(event_dir, outdir, dpi=args.dpi)
