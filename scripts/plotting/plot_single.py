#!/usr/bin/env python3
"""
Plot record section and/or station map for a single earthquake event.

Usage:
    uv run python scripts/plotting/plot_single.py <event_dir> [--outdir figure]
    uv run python scripts/plotting/plot_single.py tohoku-2011-japan --only map
    uv run python scripts/plotting/plot_single.py tohoku-2011-japan --only waveform
"""

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parents[2] / "src")
if _src in sys.path:
    sys.path.remove(_src)
sys.path.insert(0, _src)

from gnss_eq.plot_cli import plot_single_main

if __name__ == "__main__":
    plot_single_main()
