from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gnss_eq.station_siting import (
    SITING_EXPORT_FIELDS,
    classify_monument_style,
    ensure_station_siting_table,
    read_station_siting_exports,
    upsert_station_siting,
)


class StationSitingMetadataTest(unittest.TestCase):
    def test_classifies_common_earthscope_monument_styles(self):
        roof = classify_monument_style("BUILDING ROOF")
        wall = classify_monument_style("BUILDING WALL")
        ground = classify_monument_style("SHALLOW-DRILLED BRACED")
        bedrock = classify_monument_style("BEDROCK-BOLTED MAST")
        unknown = classify_monument_style("")
        geonet_unknown = classify_monument_style("UNKNOWN", source="GeoNet station inventory")

        self.assertEqual(roof["Station_Siting_Type"], "roof")
        self.assertEqual(roof["Station_Siting_Type_Zh"], "楼顶")
        self.assertEqual(roof["Rooftop_Status"], "yes")

        self.assertEqual(wall["Station_Siting_Type"], "building_wall")
        self.assertEqual(wall["Station_Siting_Type_Zh"], "建筑墙体")
        self.assertEqual(wall["Rooftop_Status"], "no, but building-mounted")

        self.assertEqual(ground["Station_Siting_Type"], "ground_station")
        self.assertEqual(ground["Station_Siting_Type_Zh"], "地面基站")

        self.assertEqual(bedrock["Station_Siting_Type"], "bedrock_bolted")
        self.assertEqual(bedrock["Bedrock_Bolted_Mast_Status"], "yes")

        self.assertEqual(unknown["Station_Siting_Type"], "unknown")
        self.assertEqual(unknown["Station_Siting_Type_Zh"], "未知")
        self.assertEqual(geonet_unknown["Bedrock_Bolted_Mast_Status"], "unknown")

    def test_upserts_and_reads_export_fields(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_station_siting_table(conn)
        upsert_station_siting(
            conn,
            provider="EarthScope",
            station="cn57",
            monument_style="BUILDING WALL",
            station_name="CN57Toco_TTO2021",
            latitude=10.837,
            longitude=-60.938,
            siting_source="EarthScope DAI",
            source_url="https://example.invalid/dai",
            updated_at="2026-07-09T00:00:00Z",
        )

        by_station = read_station_siting_exports(conn, ["CN57", "MISS"], provider="EarthScope")

        self.assertEqual(set(SITING_EXPORT_FIELDS), set(by_station["CN57"]))
        self.assertEqual(by_station["CN57"]["Monument_Style"], "BUILDING WALL")
        self.assertEqual(by_station["CN57"]["Station_Siting_Type_Zh"], "建筑墙体")
        self.assertEqual(by_station["CN57"]["Siting_Source"], "EarthScope DAI")
        self.assertEqual(by_station["MISS"]["Station_Siting_Type"], "unknown")


if __name__ == "__main__":
    unittest.main()
