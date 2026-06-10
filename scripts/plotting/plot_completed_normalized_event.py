#!/usr/bin/env python3
"""Plot the normalized event matching a completed workflow summary."""

from __future__ import annotations

import argparse
import json
import re
import sys
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

BASE_DIR = _here.parent
DEFAULT_NORMALIZED_ROOT = BASE_DIR / "exports" / "normalized-ok-stations-us-nz"
DEFAULT_OUTDIR = BASE_DIR / "figure"


def _extract_location(place: str) -> str:
    loc = place.split(" of ")[-1] if " of " in place else place
    loc = loc.split(",")[0]
    loc = re.sub(r"^\d+\s+", "", loc).strip().lower()
    loc = re.sub(r"[^a-z0-9\s]", "", loc).strip()
    return re.sub(r"\s+", "-", loc) or "unknown"


def _extract_country(event: dict) -> str:
    region = event.get("region", "")
    country = event.get("country", "")
    place = event.get("place", "").lower()
    if region == "NZ" or country.lower() in {"new zealand", "nz"}:
        return "new-zealand"
    for keyword, name in [("alaska", "alaska"), (", ca", "california"), ("california", "california"), ("hawaii", "hawaii"), ("puerto rico", "puerto-rico"), ("idaho", "idaho")]:
        if keyword in place:
            return name
    if country:
        return re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")
    return region.lower() if region else "unknown"


def make_short_name(event: dict) -> str:
    return f"{_extract_location(event.get('place', ''))}-{event.get('date', '')[:10].replace('-', '')}-{_extract_country(event)}"


def assign_short_names(event_dirs: list[Path]) -> dict[Path, str]:
    base_names = {}
    for d in event_dirs:
        with (d / "event.json").open(encoding="utf-8") as handle:
            base_names[d] = make_short_name(json.load(handle))
    counts = Counter(base_names.values())
    seen = Counter()
    final = {}
    for d in event_dirs:
        base = base_names[d]
        if counts[base] == 1:
            final[d] = base
        else:
            seen[base] += 1
            final[d] = base if seen[base] == 1 else f"{base}-{seen[base]}"
    return final


def workflow_event_id(summary_path: Path) -> str:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return str(payload.get("event", {}).get("id") or payload.get("event_id") or "").strip()


def event_id_matches(event: dict, event_id: str) -> bool:
    ids = [event.get("event_id"), event.get("usgs_event_id"), event.get("geonet_event_id"), event.get("usgs_matched_event_id")]
    return event_id in {str(value).strip() for value in ids if value}


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot normalized event for a completed workflow summary")
    parser.add_argument("--workflow-summary", type=Path, required=True)
    parser.add_argument("--normalized-root", type=Path, default=DEFAULT_NORMALIZED_ROOT)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--skip-map", action="store_true")
    parser.add_argument("--skip-waveform", action="store_true")
    args = parser.parse_args()

    event_id = workflow_event_id(args.workflow_summary)
    if not event_id:
        raise SystemExit(f"Could not read event id from {args.workflow_summary}")

    event_dirs = find_event_dirs(args.normalized_root)
    matches = []
    for event_dir in event_dirs:
        with (event_dir / "event.json").open(encoding="utf-8") as handle:
            event = json.load(handle)
        if event_id_matches(event, event_id):
            matches.append(event_dir)

    if not matches:
        print(f"No normalized event found for {event_id}; skipping final normalized plots.")
        return
    if len(matches) > 1:
        raise SystemExit(f"Multiple normalized events found for {event_id}: {', '.join(d.name for d in matches)}")

    names = assign_short_names(event_dirs)
    event_dir = matches[0]
    stem = names[event_dir]
    args.outdir.mkdir(parents=True, exist_ok=True)

    print(f"Plotting normalized event {event_id}: {event_dir.name} → {args.outdir}")
    if not args.skip_waveform:
        print(plot_record_section(event_dir, args.outdir, dpi=args.dpi, out_stem=stem))
    if not args.skip_map:
        print(plot_station_map(event_dir, args.outdir, dpi=args.dpi, out_stem=stem))


if __name__ == "__main__":
    main()
