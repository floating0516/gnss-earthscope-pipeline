from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class StationMapLabelPlacementTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.modules.setdefault("pygmt", types.SimpleNamespace())
        self.station_map = importlib.import_module("gnss_eq.plotting.station_map")

    def test_places_labels_away_from_epicenter_and_each_other(self):
        stations = [
            {"Station": "WEST", "Latitude": 10.4, "Longitude": -68.7},
            {"Station": "EAST", "Latitude": 10.4, "Longitude": -68.3},
            {"Station": "AIRS", "Latitude": 16.741, "Longitude": -62.214},
            {"Station": "OLVN", "Latitude": 16.750, "Longitude": -62.228},
        ]
        placements = self.station_map.station_label_placements(
            ev_lon=-68.5277,
            ev_lat=10.436,
            station_lons=[row["Longitude"] for row in stations],
            station_lats=[row["Latitude"] for row in stations],
            station_names=[row["Station"] for row in stations],
            region=[-72.0, -60.0, 9.5, 20.0],
        )

        by_name = {row["text"]: row for row in placements}
        self.assertLess(by_name["WEST"]["x"], -68.7)
        self.assertGreater(by_name["EAST"]["x"], -68.3)
        self.assertNotEqual((by_name["AIRS"]["x"], by_name["AIRS"]["y"]), (by_name["OLVN"]["x"], by_name["OLVN"]["y"]))
        self.assertFalse(self.station_map.label_boxes_overlap(by_name["AIRS"]["box"], by_name["OLVN"]["box"]))

    def test_station_labels_are_single_black_bold_text_layer(self):
        captured_text_calls = []

        class FakeFigure:
            def basemap(self, *args, **kwargs):
                return None

            def coast(self, *args, **kwargs):
                return None

            def grdimage(self, *args, **kwargs):
                return None

            def plot(self, *args, **kwargs):
                return None

            def meca(self, *args, **kwargs):
                return None

            def legend(self, *args, **kwargs):
                return None

            def text(self, *args, **kwargs):
                captured_text_calls.append(kwargs)

            def inset(self, *args, **kwargs):
                return self

            def savefig(self, *args, **kwargs):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        event = {
            "latitude": 10.436,
            "longitude": -68.5277,
            "depth_km": 20.294,
            "magnitude": 7.2,
            "date": "2026-06-24T22:04:33Z",
            "event": "M 7.2 - 23 km SE of Yumare, Venezuela",
            "strike": 0,
            "dip": 0,
            "rake": 0,
        }
        stations = pd.DataFrame(
            [
                {"Station": "CN40", "Latitude": 12.18, "Longitude": -68.958},
                {"Station": "CN57", "Latitude": 10.837, "Longitude": -60.938},
            ]
        )

        with (
            patch.object(self.station_map, "load_event", return_value=event),
            patch.object(self.station_map, "load_stations", return_value=stations),
            patch.object(self.station_map, "_local_30s_tiles", return_value=[]),
            patch.object(self.station_map.pygmt, "Figure", return_value=FakeFigure(), create=True),
            patch.object(self.station_map.pygmt, "makecpt", return_value=None, create=True),
        ):
            self.station_map.plot_station_map(Path("event"), Path("figure"), label_stations=True)

        label_calls = [call for call in captured_text_calls if call.get("text") in (["CN40"], ["CN57"])]
        self.assertEqual(len(label_calls), 2)
        self.assertTrue(all("black" in call["font"] for call in label_calls))
        self.assertTrue(all("Bold" in call["font"] for call in label_calls))
        self.assertTrue(all("white" not in call["font"] for call in label_calls))


if __name__ == "__main__":
    unittest.main()
