import datetime as dt
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quality" / "compute_kin_quality.py"
SPEC = importlib.util.spec_from_file_location("compute_kin_quality", MODULE_PATH)
compute_kin_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compute_kin_quality)


UTC = dt.timezone.utc
UNIX_EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)


def rows(*statuses):
    return [{"quality_status": status} for status in statuses]


def mjd_sod_from_gpst(value: dt.datetime) -> tuple[int, float]:
    delta = value - UNIX_EPOCH
    total_seconds = delta.days * compute_kin_quality.SECONDS_PER_DAY + delta.seconds + delta.microseconds / 1_000_000
    mjd = compute_kin_quality.MJD_UNIX_EPOCH + int(total_seconds // compute_kin_quality.SECONDS_PER_DAY)
    sod = total_seconds % compute_kin_quality.SECONDS_PER_DAY
    return mjd, sod


class TimeConversionTest(unittest.TestCase):
    def assert_gpst_converts_to_utc(self, gpst: dt.datetime, expected_utc: dt.datetime):
        mjd, sod = mjd_sod_from_gpst(gpst)

        self.assertEqual(compute_kin_quality.mjd_sod_to_utc(mjd, sod), expected_utc)

    def test_2026_gpst_converts_to_utc_with_18_second_offset(self):
        self.assert_gpst_converts_to_utc(
            dt.datetime(2026, 6, 24, 0, 0, 18, tzinfo=UTC),
            dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC),
        )

    def test_historical_offsets_before_2017(self):
        cases = [
            (
                dt.datetime(2014, 1, 1, 0, 0, 16, tzinfo=UTC),
                dt.datetime(2014, 1, 1, 0, 0, 0, tzinfo=UTC),
            ),
            (
                dt.datetime(2016, 1, 1, 0, 0, 17, tzinfo=UTC),
                dt.datetime(2016, 1, 1, 0, 0, 0, tzinfo=UTC),
            ),
        ]
        for gpst, expected_utc in cases:
            with self.subTest(gpst=gpst):
                self.assert_gpst_converts_to_utc(gpst, expected_utc)

    def test_gpst_sod_near_midnight_can_cross_to_previous_utc_day(self):
        self.assert_gpst_converts_to_utc(
            dt.datetime(2026, 6, 24, 0, 0, 5, tzinfo=UTC),
            dt.datetime(2026, 6, 23, 23, 59, 47, tzinfo=UTC),
        )

    def test_kin_to_enu_zero_offset_when_gpst_epoch_matches_utc_event_time(self):
        gpst = dt.datetime(2026, 6, 24, 0, 0, 18, tzinfo=UTC)
        mjd, sod = mjd_sod_from_gpst(gpst)
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            kin_path = Path(tmp) / "kin_2026175_test"
            kin_path.write_text(f"END OF HEADER\n{mjd} {sod:.0f} 1000 2000 3000\n", encoding="utf-8")

            series = compute_kin_quality.kin_to_enu(kin_path, event_time)

        self.assertEqual(series[0][0], event_time)
        self.assertEqual(series[0][1], 0.0)


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
