from __future__ import annotations

import gzip
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class PgdComputationTest(unittest.TestCase):
    def test_reads_3d_pgd_and_pre_event_snr_from_waveforms(self):
        from gnss_eq.pgd import read_pgd_by_station

        rows = ["Station,Time_Offset_s,Component,Value_m"]
        for t in [-3.0, -2.0, -1.0]:
            rows.extend(
                [
                    f"AAAA,{t},E,0.001",
                    f"AAAA,{t},N,0.002",
                    f"AAAA,{t},U,0.002",
                ]
            )
        rows.extend(
            [
                "AAAA,10.0,E,0.030",
                "AAAA,10.0,N,0.040",
                "AAAA,10.0,U,0.000",
                "AAAA,20.0,E,0.000",
                "AAAA,20.0,N,0.000",
                "AAAA,20.0,U,0.060",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "waveforms.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
                handle.write("\n".join(rows) + "\n")

            pgd_by_station = read_pgd_by_station(
                path,
                window_start=0.0,
                window_end=600.0,
                min_pgd_m=1e-6,
                pgd_component="3d",
                noise_window_start=-300.0,
                noise_window_end=0.0,
            )

        pgd = pgd_by_station["AAAA"]
        self.assertAlmostEqual(pgd["pgd_m"], 0.060)
        self.assertAlmostEqual(pgd["pgd_cm"], 6.0)
        self.assertAlmostEqual(pgd["pgd_time_offset_s"], 20.0)
        self.assertAlmostEqual(pgd["pre_event_rms_m"], 0.003)
        self.assertAlmostEqual(pgd["pgd_snr"], 20.0)

    def test_quality_flags_reject_low_snr_late_and_short_noise_window(self):
        from gnss_eq.pgd import station_quality_flags

        usable, flags = station_quality_flags(
            {
                "pgd_snr": 2.5,
                "pgd_time_offset_s": 350.0,
                "noise_sample_count": 12.0,
            },
            distance_km=250.0,
            min_pgd_snr=3.0,
            quality_max_pgd_time_offset=300.0,
            quality_max_distance_km=0.0,
        )

        self.assertFalse(usable)
        self.assertEqual(flags, "low_pgd_snr,late_pgd_peak,short_noise_window")


if __name__ == "__main__":
    unittest.main()
