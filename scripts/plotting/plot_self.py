#!/usr/bin/env python3
"""
Batch plot all earthquake events from GNSS_EQDATA_self.

Figures are saved to GNSS_EQDATA/figures with short names following the
convention: {location}-{YYYYMMDD}-{country}, e.g. culverden-20161113-new-zealand.

Usage:
    uv run python scripts/plotting/plot_self.py [--outdir figure] [--events EVENT1 ...]
    uv run python scripts/plotting/plot_self.py --list
    uv run python scripts/plotting/plot_self.py --skip-map
    uv run python scripts/plotting/plot_self.py --skip-waveform
"""

import argparse
import json
import re
import sys
import traceback
from collections import Counter
from pathlib import Path

_here = Path(__file__).resolve().parent
_src = str(_here.parents[1] / "src")
if _src in sys.path:
    sys.path.remove(_src)
sys.path.insert(0, _src)

from gnss_eq.data_io import find_event_dirs
from gnss_eq.plotting.record_section import plot_record_section
from gnss_eq.plotting.station_map import plot_station_map

BASE_DIR = _here.parents[1]
SELF_DIR = BASE_DIR / "exports" / "normalized-ok-stations-us-nz"


def _extract_location(place: str) -> str:
    """Extract key location name from USGS place string."""
    if " of " in place:
        loc = place.split(" of ")[-1]
    else:
        loc = place
    if "," in loc:
        loc = loc.split(",")[0]
    loc = re.sub(r"^\d+\s+", "", loc)
    loc = loc.strip().lower()
    loc = re.sub(r"[^a-z0-9\s]", "", loc).strip()
    loc = re.sub(r"\s+", "-", loc)
    return loc or "unknown"


def _extract_country(event: dict) -> str:
    region = event.get("region", "")
    country = event.get("country", "")
    place = event.get("place", "").lower()
    if region == "NZ" or country.lower() in {"new zealand", "nz"}:
        return "new-zealand"
    for keyword, name in [
        ("alaska", "alaska"),
        (", ca", "california"),
        ("california", "california"),
        ("hawaii", "hawaii"),
        ("puerto rico", "puerto-rico"),
        ("idaho", "idaho"),
    ]:
        if keyword in place:
            return name
    if country:
        return re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")
    return region.lower() if region else "unknown"


def make_short_name(event: dict) -> str:
    place = event.get("place", "")
    date = event.get("date", "")
    date_str = date[:10].replace("-", "")
    loc = _extract_location(place)
    country = _extract_country(event)
    return f"{loc}-{date_str}-{country}"


def assign_short_names(event_dirs: list) -> dict:
    """Generate short names for all events, resolving duplicates with -2/-3 suffix."""
    base_names = {}
    for d in event_dirs:
        json_path = d / "event.json"
        if not json_path.exists():
            base_names[d] = d.name
            continue
        with open(json_path, encoding="utf-8") as f:
            ev = json.load(f)
        base_names[d] = make_short_name(ev)

    counts = Counter(base_names.values())
    seen = Counter()
    final = {}
    for d in event_dirs:
        base = base_names[d]
        if counts[base] == 1:
            final[d] = base
        else:
            seen[base] += 1
            if seen[base] == 1:
                final[d] = base
            else:
                final[d] = f"{base}-{seen[base]}"
    return final


def _list_events(base: Path):
    dirs = find_event_dirs(base)
    names = assign_short_names(dirs)
    print(f"Found {len(dirs)} events in {base.name}:\n")
    print(f"{'Short Name':<50} {'Mag':>4} {'Sta':>4}  Original Directory")
    print("-" * 120)
    for d in dirs:
        with open(d / "event.json", encoding="utf-8") as f:
            ev = json.load(f)
        print(f"{names[d]:<50} {ev['magnitude']:>4.1f} {ev.get('stations', '?'):>4}  {d.name}")


def main():
    parser = argparse.ArgumentParser(description="Batch plot GNSS_EQDATA_self events")
    parser.add_argument("--base", type=Path, default=SELF_DIR, help="Normalized dataset directory")
    parser.add_argument("--outdir", type=str, default="figure")
    parser.add_argument("--events", nargs="*", help="Specific event dir names (default: all)")
    parser.add_argument("--list", action="store_true", help="List events with short names")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--skip-map", action="store_true")
    parser.add_argument("--skip-waveform", action="store_true")
    args = parser.parse_args()

    base = args.base.expanduser()
    if not base.is_absolute():
        base = BASE_DIR / base

    if args.list:
        _list_events(base)
        return

    outdir = Path(args.outdir).expanduser()
    if not outdir.is_absolute():
        outdir = BASE_DIR / outdir

    if args.events:
        event_dirs = [base / e for e in args.events]
    else:
        event_dirs = find_event_dirs(base)

    short_names = assign_short_names(event_dirs)

    print(f"Processing {len(event_dirs)} events from {base.name} → {outdir}/\n")

    success = 0
    failed = []

    for i, event_dir in enumerate(event_dirs, 1):
        stem = short_names[event_dir]
        print(f"[{i}/{len(event_dirs)}] {event_dir.name}  →  {stem}")

        if not event_dir.is_dir() or not (event_dir / "event.json").exists():
            print("  SKIP: not a valid event directory")
            continue

        event_failed = False
        try:
            if not args.skip_waveform:
                plot_record_section(event_dir, outdir, dpi=args.dpi, out_stem=stem)
        except Exception as e:
            event_failed = True
            print(f"  ERROR (record_section): {e}")
            traceback.print_exc()
            failed.append((event_dir.name, "record_section", str(e)))

        try:
            if not args.skip_map:
                plot_station_map(event_dir, outdir, dpi=args.dpi, out_stem=stem)
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


if __name__ == "__main__":
    main()
