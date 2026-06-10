#!/usr/bin/env python3
"""Compatibility wrapper for the raster event record-section plotter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
RASTER_SCRIPT = ROOT / "scripts" / "plotting" / "plot_event_record_sections_raster.py"

translated_args: list[str] = []
args = iter(sys.argv[1:])
for arg in args:
    if arg == "--out-name":
        next(args, None)
        continue
    translated_args.append(arg)

print(
    "plot_event_record_sections.py is deprecated; using raster PNG/PDF plotter.",
    file=sys.stderr,
)
raise SystemExit(subprocess.run([str(PYTHON), str(RASTER_SCRIPT), *translated_args], check=False).returncode)
