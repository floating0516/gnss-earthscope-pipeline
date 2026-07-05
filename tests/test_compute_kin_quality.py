import argparse
import datetime as dt
import importlib.util
import json
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


def quality_args(**overrides):
    values = {
        "expected_hours_each_side": 0.0,
        "expected_seconds": 119.0,
        "min_epochs": 60,
        "min_coverage_ratio": 0.80,
        "min_station_health_ratio": 0.80,
        "max_pre_rms_cm": 10.0,
        "max_epoch_jump_cm": 50.0,
        "event_step_window": 30.0,
        "allow_partial_failures": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def write_kin(path: Path, event_time: dt.datetime, offsets: list[int], xyz_rows: list[tuple[float, float, float]]) -> None:
    lines = ["END OF HEADER"]
    for offset, (x, y, z) in zip(offsets, xyz_rows):
        gpst = event_time + dt.timedelta(seconds=offset + 18)
        mjd, sod = mjd_sod_from_gpst(gpst)
        lines.append(f"{mjd} {sod:.0f} {x:.6f} {y:.6f} {z:.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_clean_kin(path: Path, event_time: dt.datetime, offsets: list[int] | None = None) -> None:
    offsets = offsets if offsets is not None else list(range(-60, 60))
    write_kin(path, event_time, offsets, [(1000.0, 2000.0, 3000.0) for _ in offsets])


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
        summary = compute_kin_quality.aggregate(rows("OK", "OK", "OK", "WARN", "WARN"))

        self.assertEqual(summary["status"], "WARN")
        self.assertEqual(summary["station_health_ratio"], 0.6)

    def test_event_quality_fails_partial_failures_without_allow_partial(self):
        summary = compute_kin_quality.aggregate(rows("OK", "OK", "OK", "WARN", "FAIL"))

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["fail_station_count"], 1)

    def test_event_quality_warns_partial_failures_when_allowed(self):
        summary = compute_kin_quality.aggregate(rows("OK", "OK", "OK", "WARN", "FAIL"), allow_partial_failures=True)

        self.assertEqual(summary["status"], "WARN")
        self.assertEqual(summary["fail_station_count"], 1)

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


class StationQualityTest(unittest.TestCase):
    def test_clean_continuous_station_is_ok(self):
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            kin_path = Path(tmp) / "kin_2026175_abcd"
            write_clean_kin(kin_path, event_time)

            row = compute_kin_quality.summarize_file(kin_path, event_time, quality_args())

        self.assertEqual(row["station"], "ABCD")
        self.assertEqual(row["quality_status"], "OK")
        self.assertEqual(row["quality_flags"], "")

    def test_low_coverage_station_fails(self):
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            kin_path = Path(tmp) / "kin_2026175_abcd"
            write_clean_kin(kin_path, event_time, offsets=list(range(-5, 5)))

            row = compute_kin_quality.summarize_file(kin_path, event_time, quality_args(expected_seconds=119.0))

        self.assertEqual(row["quality_status"], "FAIL")
        self.assertIn("too_few_epochs", row["quality_flags"])
        self.assertIn("short_coverage", row["quality_flags"])

    def test_high_pre_event_rms_station_warns(self):
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        offsets = list(range(-60, 60))
        xyz_rows = [
            (1000.0 + (1.0 if offset % 2 else -1.0), 2000.0, 3000.0)
            if offset < 0
            else (1000.0, 2000.0, 3000.0)
            for offset in offsets
        ]
        with tempfile.TemporaryDirectory() as tmp:
            kin_path = Path(tmp) / "kin_2026175_abcd"
            write_kin(kin_path, event_time, offsets, xyz_rows)

            row = compute_kin_quality.summarize_file(
                kin_path,
                event_time,
                quality_args(max_epoch_jump_cm=500.0),
            )

        self.assertEqual(row["quality_status"], "WARN")
        self.assertIn("high_pre_event_rms", row["quality_flags"])

    def test_gap_downgrades_station_to_warn(self):
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        offsets = list(range(-60, 0)) + list(range(10, 70))
        with tempfile.TemporaryDirectory() as tmp:
            kin_path = Path(tmp) / "kin_2026175_abcd"
            write_clean_kin(kin_path, event_time, offsets=offsets)

            row = compute_kin_quality.summarize_file(kin_path, event_time, quality_args(expected_seconds=129.0))

        self.assertEqual(row["quality_status"], "WARN")
        self.assertIn("gaps:1", row["quality_flags"])


class QualityJsonContractTest(unittest.TestCase):
    def test_quality_json_includes_schema_thresholds_and_policy(self):
        event_time = dt.datetime(2026, 6, 24, 0, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kin_path = root / "kin_2026175_abcd"
            out_json = root / "quality.json"
            write_clean_kin(kin_path, event_time)

            rc = compute_kin_quality.main(
                [
                    "--event-time",
                    "2026-06-24T00:00:00Z",
                    "--expected-seconds",
                    "119",
                    "--out-json",
                    str(out_json),
                    str(kin_path),
                ]
            )
            payload = json.loads(out_json.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["schema_version"], "kin-quality/v1")
        self.assertEqual(payload["thresholds"]["min_epochs"], 60)
        self.assertEqual(payload["thresholds"]["min_coverage_ratio"], 0.8)
        self.assertEqual(payload["policy"]["allow_partial_failures"], False)


if __name__ == "__main__":
    unittest.main()
