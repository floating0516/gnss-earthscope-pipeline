import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compute_kin_quality.py"
SPEC = importlib.util.spec_from_file_location("compute_kin_quality", MODULE_PATH)
compute_kin_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compute_kin_quality)


def rows(*statuses):
    return [{"quality_status": status} for status in statuses]


class AggregateQualityTest(unittest.TestCase):
    def test_event_quality_ok_at_80_percent_station_health(self):
        summary = compute_kin_quality.aggregate(rows("OK", "OK", "OK", "OK", "WARN"))

        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["station_health_ratio"], 0.8)

    def test_event_quality_warn_below_80_percent_station_health(self):
        summary = compute_kin_quality.aggregate(rows("OK", "OK", "OK", "WARN", "FAIL"))

        self.assertEqual(summary["status"], "WARN")
        self.assertEqual(summary["station_health_ratio"], 0.6)

    def test_event_quality_uses_configured_station_health_threshold(self):
        summary = compute_kin_quality.aggregate(
            rows("OK", "OK", "OK", "OK", "WARN"),
            min_station_health_ratio=0.81,
        )

        self.assertEqual(summary["status"], "WARN")
        self.assertEqual(summary["min_station_health_ratio"], 0.81)

    def test_event_quality_fails_without_stations(self):
        summary = compute_kin_quality.aggregate([])

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["station_count"], 0)


if __name__ == "__main__":
    unittest.main()
