#!/usr/bin/env python3
"""
Batch plot all earthquake events: record section + station map.

Usage:
    uv run python scripts/plotting/plot_all.py [--outdir figure] [--events EVENT1 EVENT2 ...]
    uv run python scripts/plotting/plot_all.py --list
"""

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parents[2] / "src")
if _src in sys.path:
    sys.path.remove(_src)
sys.path.insert(0, _src)

from gnss_eq.plot_cli import plot_all_main

if __name__ == "__main__":
    plot_all_main()
