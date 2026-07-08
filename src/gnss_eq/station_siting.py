"""Station siting metadata helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable

SITING_EXPORT_FIELDS = [
    "Monument_Style",
    "Station_Siting_Type",
    "Station_Siting_Type_Zh",
    "Siting_Category",
    "Rooftop_Status",
    "Bedrock_Bolted_Mast_Status",
    "Siting_Source",
]


def _clean_station(value: object) -> str:
    return str(value or "").strip().upper()[:4]


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def unknown_siting_export(source: str = "") -> dict[str, str]:
    return {
        "Monument_Style": "UNKNOWN",
        "Station_Siting_Type": "unknown",
        "Station_Siting_Type_Zh": "未知",
        "Siting_Category": "unknown",
        "Rooftop_Status": "unknown",
        "Bedrock_Bolted_Mast_Status": "unknown",
        "Siting_Source": source,
    }


def classify_monument_style(monument_style: object, source: str = "EarthScope DAI") -> dict[str, str]:
    raw = _clean_text(monument_style).upper()
    if not raw or raw in {"NAN", "NONE", "NULL", "UNKNOWN"}:
        return unknown_siting_export(source)

    result = {
        "Monument_Style": raw,
        "Siting_Source": source,
        "Bedrock_Bolted_Mast_Status": "not classified as bedrock-bolted in DAI",
    }
    if "BEDROCK" in raw:
        result.update(
            {
                "Station_Siting_Type": "bedrock_bolted",
                "Station_Siting_Type_Zh": "基岩螺栓",
                "Siting_Category": "bedrock/foundation monument",
                "Rooftop_Status": "no evidence of rooftop",
                "Bedrock_Bolted_Mast_Status": "yes",
            }
        )
    elif "WALL" in raw and "BUILDING" in raw:
        result.update(
            {
                "Station_Siting_Type": "building_wall",
                "Station_Siting_Type_Zh": "建筑墙体",
                "Siting_Category": "building wall",
                "Rooftop_Status": "no, but building-mounted",
            }
        )
    elif "ROOF" in raw and ("EQUIPMENT" in raw or "ROOM" in raw):
        result.update(
            {
                "Station_Siting_Type": "equipment_room_roof",
                "Station_Siting_Type_Zh": "机房楼顶",
                "Siting_Category": "roof/building",
                "Rooftop_Status": "yes",
            }
        )
    elif "ROOF" in raw:
        result.update(
            {
                "Station_Siting_Type": "roof",
                "Station_Siting_Type_Zh": "楼顶",
                "Siting_Category": "roof/building",
                "Rooftop_Status": "yes",
            }
        )
    elif any(token in raw for token in ["SHALLOW", "DEEP", "DRILLED", "BRACED", "PILLAR", "MAST", "CONCRETE"]):
        result.update(
            {
                "Station_Siting_Type": "ground_station",
                "Station_Siting_Type_Zh": "地面基站",
                "Siting_Category": "ground/foundation monument",
                "Rooftop_Status": "no evidence of rooftop",
            }
        )
    elif raw == "OTHER" or "OTHER" in raw:
        result.update(
            {
                "Station_Siting_Type": "other",
                "Station_Siting_Type_Zh": "其他",
                "Siting_Category": "other",
                "Rooftop_Status": "unknown",
            }
        )
    else:
        result.update(
            {
                "Station_Siting_Type": "unknown",
                "Station_Siting_Type_Zh": "未知",
                "Siting_Category": "unknown",
                "Rooftop_Status": "unknown",
            }
        )
    return {field: result.get(field, "") for field in SITING_EXPORT_FIELDS}


def ensure_station_siting_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS station_siting_metadata (
            provider TEXT NOT NULL,
            station TEXT NOT NULL,
            station9 TEXT NOT NULL DEFAULT '',
            station_name TEXT NOT NULL DEFAULT '',
            latitude REAL,
            longitude REAL,
            monument_style TEXT NOT NULL DEFAULT '',
            station_siting_type TEXT NOT NULL,
            station_siting_type_zh TEXT NOT NULL,
            siting_category TEXT NOT NULL,
            rooftop_status TEXT NOT NULL,
            bedrock_bolted_mast_status TEXT NOT NULL,
            siting_source TEXT NOT NULL,
            siting_source_url TEXT NOT NULL DEFAULT '',
            raw_metadata_json TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (provider, station)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_siting_station ON station_siting_metadata(station)")


def upsert_station_siting(
    conn: sqlite3.Connection,
    *,
    provider: str,
    station: str,
    monument_style: object = "",
    station9: object = "",
    station_name: object = "",
    latitude: float | None = None,
    longitude: float | None = None,
    siting_source: str = "",
    source_url: str = "",
    raw_metadata: object | None = None,
    updated_at: str,
) -> None:
    station_code = _clean_station(station)
    if not station_code:
        return
    source = siting_source or provider
    classified = classify_monument_style(monument_style, source)
    conn.execute(
        """
        INSERT INTO station_siting_metadata (
            provider, station, station9, station_name, latitude, longitude,
            monument_style, station_siting_type, station_siting_type_zh, siting_category,
            rooftop_status, bedrock_bolted_mast_status, siting_source, siting_source_url,
            raw_metadata_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider, station) DO UPDATE SET
            station9 = excluded.station9,
            station_name = excluded.station_name,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            monument_style = excluded.monument_style,
            station_siting_type = excluded.station_siting_type,
            station_siting_type_zh = excluded.station_siting_type_zh,
            siting_category = excluded.siting_category,
            rooftop_status = excluded.rooftop_status,
            bedrock_bolted_mast_status = excluded.bedrock_bolted_mast_status,
            siting_source = excluded.siting_source,
            siting_source_url = excluded.siting_source_url,
            raw_metadata_json = excluded.raw_metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            provider,
            station_code,
            _clean_text(station9),
            _clean_text(station_name),
            latitude,
            longitude,
            classified["Monument_Style"],
            classified["Station_Siting_Type"],
            classified["Station_Siting_Type_Zh"],
            classified["Siting_Category"],
            classified["Rooftop_Status"],
            classified["Bedrock_Bolted_Mast_Status"],
            classified["Siting_Source"],
            _clean_text(source_url),
            json.dumps(raw_metadata or {}, ensure_ascii=False, sort_keys=True),
            updated_at,
        ),
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def read_station_siting_exports(
    conn: sqlite3.Connection,
    stations: Iterable[str],
    *,
    provider: str | None = None,
) -> dict[str, dict[str, str]]:
    station_codes = sorted({_clean_station(station) for station in stations if _clean_station(station)})
    result = {station: unknown_siting_export() for station in station_codes}
    if not station_codes or not _table_exists(conn, "station_siting_metadata"):
        return result

    placeholders = ",".join("?" for _ in station_codes)
    params: list[object] = list(station_codes)
    provider_clause = ""
    if provider:
        provider_clause = " AND provider = ?"
        params.append(provider)

    rows = conn.execute(
        f"""
        SELECT station, monument_style, station_siting_type, station_siting_type_zh,
               siting_category, rooftop_status, bedrock_bolted_mast_status, siting_source
        FROM station_siting_metadata
        WHERE station IN ({placeholders}){provider_clause}
        """,
        params,
    ).fetchall()
    for row in rows:
        station = _clean_station(row["station"] if isinstance(row, sqlite3.Row) else row[0])
        values = dict(row) if isinstance(row, sqlite3.Row) else {
            "station": row[0],
            "monument_style": row[1],
            "station_siting_type": row[2],
            "station_siting_type_zh": row[3],
            "siting_category": row[4],
            "rooftop_status": row[5],
            "bedrock_bolted_mast_status": row[6],
            "siting_source": row[7],
        }
        result[station] = {
            "Monument_Style": _clean_text(values.get("monument_style")) or "UNKNOWN",
            "Station_Siting_Type": _clean_text(values.get("station_siting_type")) or "unknown",
            "Station_Siting_Type_Zh": _clean_text(values.get("station_siting_type_zh")) or "未知",
            "Siting_Category": _clean_text(values.get("siting_category")) or "unknown",
            "Rooftop_Status": _clean_text(values.get("rooftop_status")) or "unknown",
            "Bedrock_Bolted_Mast_Status": _clean_text(values.get("bedrock_bolted_mast_status")) or "unknown",
            "Siting_Source": _clean_text(values.get("siting_source")),
        }
    return result
