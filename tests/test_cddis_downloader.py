from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_PATH = Path(__file__).resolve().parents[1] / "tools" / "cddis_downloader"
COMMON_PATH = TOOLS_PATH / "cddis_common.py"
FETCH_PATH = TOOLS_PATH / "fetch_cddis_highrate.py"

COMMON_SPEC = importlib.util.spec_from_file_location("cddis_common", COMMON_PATH)
cddis_common = importlib.util.module_from_spec(COMMON_SPEC)
assert COMMON_SPEC.loader is not None
sys.modules["cddis_common"] = cddis_common
COMMON_SPEC.loader.exec_module(cddis_common)

FETCH_SPEC = importlib.util.spec_from_file_location("fetch_cddis_highrate", FETCH_PATH)
fetch_cddis_highrate = importlib.util.module_from_spec(FETCH_SPEC)
assert FETCH_SPEC.loader is not None
FETCH_SPEC.loader.exec_module(fetch_cddis_highrate)


class FakeCurlOk:
    returncode = 0
    stdout = ""
    stderr = ""


class FakeCurlFail:
    returncode = 22
    stdout = ""
    stderr = "curl: (22) The requested URL returned error: 401\n"


def cmr_payload() -> dict:
    return {
        "feed": {
            "entry": [
                {
                    "id": "G1-CDDIS",
                    "producer_granule_id": "gnss_data_highrate_2026_174_26o_23_daej174x00.26o.gz",
                    "time_start": "2026-06-23T23:00:00.000Z",
                    "time_end": "2026-06-23T23:14:00.000Z",
                    "links": [
                        {
                            "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                            "href": "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz",
                        },
                        {
                            "rel": "http://esipfed.org/ns/fedsearch/1.1/metadata#",
                            "href": "https://doi.org/10.5067/GNSS/GNSS_HIGHRATE_O_001",
                        },
                    ],
                },
                {
                    "id": "G2-CDDIS",
                    "producer_granule_id": "gnss_data_highrate_2026_174_26o_23_abcd174x00.26o.gz",
                    "time_start": "2026-06-23T23:00:00.000Z",
                    "time_end": "2026-06-23T23:14:00.000Z",
                    "links": [
                        {
                            "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                            "href": "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/abcd174x00.26o.gz",
                        }
                    ],
                },
            ]
        }
    }


class CddisCommonTest(unittest.TestCase):
    def test_station_normalization(self):
        stations = cddis_common.unique_stations(["daej", "DAEJ.GNSS", "abcd.gps", "", "ABCD"])

        self.assertEqual(stations, ["DAEJ", "ABCD"])

    def test_station_file_ignores_inline_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stations.txt"
            path.write_text("daej  # Korea station\nabcd.gps\n", encoding="utf-8")

            stations = cddis_common.read_station_file(path)

        self.assertEqual(stations, ["DAEJ", "ABCD"])

    def test_build_cmr_url(self):
        start = cddis_common.parse_utc("2026-06-23T23:00:00Z")
        end = cddis_common.parse_utc("2026-06-23T23:15:00+00:00")

        url = cddis_common.build_cmr_url(start, end, page_size=10, page_num=2)

        self.assertIn("collection_concept_id=C1422090772-CDDIS", url)
        self.assertIn("temporal=2026-06-23T23%3A00%3A00Z%2C2026-06-23T23%3A15%3A00Z", url)
        self.assertIn("page_size=10", url)
        self.assertIn("page_num=2", url)

    def test_granules_from_cmr_payload_extracts_cddis_data_links(self):
        granules = cddis_common.granules_from_cmr_payload(cmr_payload())

        self.assertEqual([granule.station4 for granule in granules], ["DAEJ", "ABCD"])
        self.assertEqual(granules[0].filename, "daej174x00.26o.gz")
        self.assertTrue(granules[0].url.startswith("https://cddis.nasa.gov/archive/gnss/data/highrate/"))

    def test_station_filtering_matches_filename_station(self):
        granules = cddis_common.granules_from_cmr_payload(cmr_payload())

        selected = cddis_common.filter_granules_by_station(granules, ["DAEJ"])

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].filename, "daej174x00.26o.gz")

    def test_directory_html_extracts_window_granules(self):
        html = '<a href="daej174x00.26o.gz">daej</a><a href="daej174x30.26o.gz">late</a>'
        start = cddis_common.parse_utc("2026-06-23T23:00:00Z")
        end = cddis_common.parse_utc("2026-06-23T23:15:00Z")

        granules = cddis_common.granules_from_directory_html(
            html,
            "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/",
            start,
            end,
        )

        self.assertEqual(len(granules), 1)
        self.assertEqual(granules[0].filename, "daej174x00.26o.gz")
        self.assertEqual(granules[0].station4, "DAEJ")

    def test_curl_download_uses_earthdata_netrc_and_cookies(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "daej174x00.26o.gz"

            def fake_run(command, **kwargs):
                Path(command[command.index("-o") + 1]).write_bytes(b"gzip")
                return FakeCurlOk()

            with patch.object(cddis_common.subprocess, "run", side_effect=fake_run) as run:
                status, reason = cddis_common.curl_download(
                    "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz",
                    target,
                    cookie_file=Path(tmp) / "cookies",
                )

        self.assertEqual(status, "OK")
        self.assertEqual(reason, "")
        command = run.call_args.args[0]
        self.assertIn("-L", command)
        self.assertIn("-n", command)
        self.assertIn("-b", command)
        self.assertIn("-c", command)
        self.assertIn("--fail", command)
        self.assertNotIn("es", command)
        self.assertNotIn("Authorization: Bearer", " ".join(command))

    def test_curl_download_reports_earthdata_auth_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "daej174x00.26o.gz"
            with patch.object(cddis_common.subprocess, "run", return_value=FakeCurlFail()):
                status, reason = cddis_common.curl_download(
                    "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz",
                    target,
                    cookie_file=Path(tmp) / "cookies",
                )

        self.assertEqual(status, "FAIL")
        self.assertIn("CDDIS/Earthdata authorization failed", reason)
        self.assertFalse(target.exists())


class FetchCddisHighrateTest(unittest.TestCase):
    def test_dry_run_writes_manifests_without_downloads(self):
        granules = cddis_common.granules_from_cmr_payload(cmr_payload())
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_cddis_highrate, "query_cmr_granules", return_value=granules):
                with patch.object(fetch_cddis_highrate, "curl_download") as download:
                    rc = fetch_cddis_highrate.main(
                        [
                            "--start-time",
                            "2026-06-23T23:00:00Z",
                            "--end-time",
                            "2026-06-23T23:15:00Z",
                            "--stations",
                            "DAEJ",
                            "--out-dir",
                            tmp,
                            "--dry-run",
                        ]
                    )

            summary = json.loads((Path(tmp) / "cddis-summary.json").read_text(encoding="utf-8"))
            downloads = (Path(tmp) / "cddis-downloads.tsv").read_text(encoding="utf-8")
            query = (Path(tmp) / "cddis-query-results.tsv").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        download.assert_not_called()
        self.assertEqual(summary["provider"], "CDDIS")
        self.assertEqual(summary["selected_granules"], 1)
        self.assertIn("DRY_RUN", downloads)
        self.assertIn("DAEJ", query)
        self.assertIn("ABCD", query)

    def test_download_failure_returns_nonzero_and_records_manifest(self):
        granules = cddis_common.granules_from_cmr_payload(cmr_payload())[:1]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_cddis_highrate, "query_cmr_granules", return_value=granules):
                with patch.object(fetch_cddis_highrate, "curl_download", return_value=("FAIL", "CDDIS/Earthdata authorization failed")):
                    rc = fetch_cddis_highrate.main(
                        [
                            "--start-time",
                            "2026-06-23T23:00:00Z",
                            "--end-time",
                            "2026-06-23T23:15:00Z",
                            "--stations",
                            "DAEJ",
                            "--out-dir",
                            tmp,
                        ]
                    )
            downloads = (Path(tmp) / "cddis-downloads.tsv").read_text(encoding="utf-8")

        self.assertEqual(rc, 1)
        self.assertIn("FAIL", downloads)
        self.assertIn("CDDIS/Earthdata authorization failed", downloads)

    def test_auto_mode_falls_back_to_directory_query(self):
        granules = cddis_common.granules_from_cmr_payload(cmr_payload())[:1]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_cddis_highrate, "query_cmr_granules", side_effect=RuntimeError("CMR query failed with HTTP 500")):
                with patch.object(fetch_cddis_highrate, "query_directory_granules", return_value=granules):
                    rc = fetch_cddis_highrate.main(
                        [
                            "--start-time",
                            "2026-06-23T23:00:00Z",
                            "--end-time",
                            "2026-06-23T23:15:00Z",
                            "--stations",
                            "DAEJ",
                            "--out-dir",
                            tmp,
                            "--dry-run",
                        ]
                    )
            summary = json.loads((Path(tmp) / "cddis-summary.json").read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(summary["query_mode"], "directory")
        self.assertIn("CMR failed", summary["query_warnings"][0])

    def test_cmr_mode_failure_writes_failure_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_cddis_highrate, "query_cmr_granules", side_effect=RuntimeError("CMR query failed with HTTP 500")):
                rc = fetch_cddis_highrate.main(
                    [
                        "--start-time",
                        "2026-06-23T23:00:00Z",
                        "--end-time",
                        "2026-06-23T23:15:00Z",
                        "--out-dir",
                        tmp,
                        "--query-mode",
                        "cmr",
                        "--dry-run",
                    ]
                )
            summary = json.loads((Path(tmp) / "cddis-summary.json").read_text(encoding="utf-8"))

        self.assertEqual(rc, 1)
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("CMR query failed", summary["reason"])

    def test_invalid_time_window_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                fetch_cddis_highrate.main(
                    [
                        "--start-time",
                        "2026-06-23T23:15:00Z",
                        "--end-time",
                        "2026-06-23T23:00:00Z",
                        "--out-dir",
                        tmp,
                        "--dry-run",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
