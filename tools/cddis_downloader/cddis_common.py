#!/usr/bin/env python3
"""Shared helpers for NASA CDDIS high-rate GNSS prototype downloads."""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
CDDIS_HIGHRATE_COLLECTION = "C1422090772-CDDIS"
CDDIS_HIGHRATE_URL_PREFIX = "https://cddis.nasa.gov/archive/gnss/data/highrate/"
USER_AGENT = "gnss-earthscope-pipeline cddis-downloader"


@dataclass(frozen=True)
class CddisGranule:
    granule_id: str
    producer_granule_id: str
    start_utc: str
    end_utc: str
    url: str
    filename: str
    station4: str
    station9: str


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_station(value: str) -> str:
    text = value.strip().upper()
    if not text:
        return ""
    if text.endswith(".GNSS") or text.endswith(".GPS"):
        text = text.split(".", 1)[0]
    return text[:4]


def unique_stations(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    stations: list[str] = []
    for value in values:
        station = normalize_station(value)
        if not station or station.startswith("#"):
            continue
        if station in seen:
            continue
        seen.add(station)
        stations.append(station)
    return stations


def read_station_file(path: Path) -> list[str]:
    stations: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0]
        for part in re.split(r"[,\s]+", line):
            station = normalize_station(part)
            if station:
                stations.append(station)
    return unique_stations(stations)


def build_cmr_url(
    start: dt.datetime,
    end: dt.datetime,
    *,
    collection_concept_id: str = CDDIS_HIGHRATE_COLLECTION,
    cmr_url: str = CMR_GRANULES_URL,
    page_size: int = 2000,
    page_num: int = 1,
) -> str:
    params = {
        "collection_concept_id": collection_concept_id,
        "temporal": f"{iso_utc(start)},{iso_utc(end)}",
        "page_size": str(page_size),
        "page_num": str(page_num),
        "sort_key": "start_date",
    }
    return cmr_url + "?" + urllib.parse.urlencode(params)


def fetch_json(url: str, timeout: int = 60) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Client-Id": "gnss-earthscope-pipeline-cddis", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"CMR query failed with HTTP {exc.code}: {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"CMR query failed: {exc}") from exc


def safe_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"unsafe CDDIS filename from URL: {url}")
    return name


def station_ids_from_filename(filename: str) -> tuple[str, str]:
    stem = filename.split(".", 1)[0].upper()
    first_part = stem.split("_", 1)[0]
    station9 = first_part[:9] if len(first_part) >= 9 else ""
    station4 = first_part[:4]
    return station4, station9


def granules_from_cmr_payload(payload: object) -> list[CddisGranule]:
    if not isinstance(payload, dict):
        return []
    feed = payload.get("feed")
    if not isinstance(feed, dict):
        return []
    entries = feed.get("entry", [])
    if not isinstance(entries, list):
        return []

    seen_urls: set[str] = set()
    granules: list[CddisGranule] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        links = entry.get("links", [])
        if not isinstance(links, list):
            continue
        for link in links:
            if not isinstance(link, dict):
                continue
            href = str(link.get("href") or "")
            if not href.startswith(CDDIS_HIGHRATE_URL_PREFIX):
                continue
            if href == CDDIS_HIGHRATE_URL_PREFIX.rstrip("/") or href.rstrip("/") == CDDIS_HIGHRATE_URL_PREFIX.rstrip("/"):
                continue
            rel = str(link.get("rel") or "")
            if "metadata" in rel or "documentation" in rel or "browse" in rel:
                continue
            if href in seen_urls:
                continue
            filename = safe_filename_from_url(href)
            station4, station9 = station_ids_from_filename(filename)
            seen_urls.add(href)
            granules.append(
                CddisGranule(
                    granule_id=str(entry.get("id") or ""),
                    producer_granule_id=str(entry.get("producer_granule_id") or entry.get("title") or ""),
                    start_utc=str(entry.get("time_start") or ""),
                    end_utc=str(entry.get("time_end") or ""),
                    url=href,
                    filename=filename,
                    station4=station4,
                    station9=station9,
                )
            )
    return granules


def query_cmr_granules(
    start: dt.datetime,
    end: dt.datetime,
    *,
    collection_concept_id: str = CDDIS_HIGHRATE_COLLECTION,
    cmr_url: str = CMR_GRANULES_URL,
    page_size: int = 2000,
    timeout: int = 60,
) -> list[CddisGranule]:
    granules: list[CddisGranule] = []
    seen_urls: set[str] = set()
    page_num = 1
    while True:
        url = build_cmr_url(
            start,
            end,
            collection_concept_id=collection_concept_id,
            cmr_url=cmr_url,
            page_size=page_size,
            page_num=page_num,
        )
        page_granules = granules_from_cmr_payload(fetch_json(url, timeout=timeout))
        for granule in page_granules:
            if granule.url in seen_urls:
                continue
            seen_urls.add(granule.url)
            granules.append(granule)
        if len(page_granules) < page_size:
            break
        page_num += 1
    return granules


def iter_hour_starts(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    current = start.replace(minute=0, second=0, microsecond=0)
    hours: list[dt.datetime] = []
    while current < end:
        hours.append(current)
        current += dt.timedelta(hours=1)
    return hours


def cddis_hour_directory_url(hour_start: dt.datetime, rinex_subdir: str | None = None) -> str:
    value = hour_start.astimezone(dt.timezone.utc)
    subdir = rinex_subdir or f"{value.year % 100:02d}o"
    doy = int(value.strftime("%j"))
    return f"{CDDIS_HIGHRATE_URL_PREFIX}{value.year}/{doy:03d}/{subdir}/{value.hour:02d}/"


def curl_fetch_text(url: str, *, timeout: int = 180, cookie_file: Path | None = None) -> str:
    cookie = str(cookie_file or Path.home() / ".urs_cookies")
    command = [
        "curl",
        "-L",
        "-n",
        "-b",
        cookie,
        "-c",
        cookie,
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(min(timeout, 60)),
        "--max-time",
        str(timeout),
        url,
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        detail = first_nonempty_line(result.stderr, f"curl exited {result.returncode}")
        if "401" in detail or "403" in detail:
            detail = f"CDDIS/Earthdata authorization failed: {detail}"
        raise RuntimeError(f"CDDIS directory query failed: {detail}")
    return result.stdout


def hrefs_from_directory_html(html: str) -> list[str]:
    hrefs: list[str] = []
    for match in re.finditer(r'''href=["']([^"']+)["']''', html, flags=re.IGNORECASE):
        href = match.group(1).strip()
        if not href or href.startswith("?") or href.startswith("#") or href.startswith("/") or href == "../":
            continue
        hrefs.append(href)
    return hrefs


def granule_start_from_url(url: str) -> dt.datetime | None:
    parsed = urllib.parse.urlparse(url)
    parts = parsed.path.strip("/").split("/")
    try:
        index = parts.index("highrate")
        year = int(parts[index + 1])
        doy = int(parts[index + 2])
        hour = int(parts[index + 4])
    except (ValueError, IndexError):
        return None

    filename = safe_filename_from_url(url)
    match = re.search(r"_(\d{11})_15M_01S", filename)
    if match:
        text = match.group(1)
        return dt.datetime.strptime(text, "%Y%j%H%M").replace(tzinfo=dt.timezone.utc)

    match = re.match(r"^[A-Za-z0-9]{4}(\d{3})[a-xA-X](\d{2})\.\d{2}[A-Za-z](?:\.(?:gz|Z))?$", filename)
    if match:
        doy = int(match.group(1))
        minute = int(match.group(2))
        return dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1, hours=hour, minutes=minute)
    return dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1, hours=hour)


def granules_from_directory_html(html: str, directory_url: str, start: dt.datetime, end: dt.datetime) -> list[CddisGranule]:
    granules: list[CddisGranule] = []
    for href in hrefs_from_directory_html(html):
        url = urllib.parse.urljoin(directory_url, href)
        try:
            filename = safe_filename_from_url(url)
        except ValueError:
            continue
        if not (filename.endswith(".gz") or filename.endswith(".Z")):
            continue
        granule_start = granule_start_from_url(url)
        if granule_start is None:
            continue
        granule_end = granule_start + dt.timedelta(minutes=15)
        if not (granule_start < end and granule_end > start):
            continue
        station4, station9 = station_ids_from_filename(filename)
        granules.append(
            CddisGranule(
                granule_id="",
                producer_granule_id=filename,
                start_utc=iso_utc(granule_start),
                end_utc=iso_utc(granule_end),
                url=url,
                filename=filename,
                station4=station4,
                station9=station9,
            )
        )
    return granules


def query_directory_granules(
    start: dt.datetime,
    end: dt.datetime,
    *,
    rinex_subdir: str | None = None,
    timeout: int = 180,
    cookie_file: Path | None = None,
) -> list[CddisGranule]:
    granules: list[CddisGranule] = []
    seen_urls: set[str] = set()
    for hour_start in iter_hour_starts(start, end):
        directory_url = cddis_hour_directory_url(hour_start, rinex_subdir=rinex_subdir)
        for granule in granules_from_directory_html(curl_fetch_text(directory_url, timeout=timeout, cookie_file=cookie_file), directory_url, start, end):
            if granule.url in seen_urls:
                continue
            seen_urls.add(granule.url)
            granules.append(granule)
    return granules


def filter_granules_by_station(granules: list[CddisGranule], stations: list[str]) -> list[CddisGranule]:
    station_set = set(unique_stations(stations))
    if not station_set:
        return granules
    return [granule for granule in granules if granule.station4 in station_set or granule.station9[:4] in station_set]


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def curl_download(
    url: str,
    target: Path,
    *,
    timeout: int = 180,
    cookie_file: Path | None = None,
    overwrite: bool = False,
) -> tuple[str, str]:
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return "SKIP", "existing file"

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    cookie = str(cookie_file or Path.home() / ".urs_cookies")
    command = [
        "curl",
        "-L",
        "-n",
        "-b",
        cookie,
        "-c",
        cookie,
        "--fail",
        "--connect-timeout",
        str(min(timeout, 60)),
        "--max-time",
        str(timeout),
        "-o",
        str(tmp),
        url,
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        detail = first_nonempty_line(result.stderr, f"curl exited {result.returncode}")
        if "401" in detail or "403" in detail:
            detail = f"CDDIS/Earthdata authorization failed: {detail}"
        return "FAIL", detail
    tmp.replace(target)
    return "OK", ""


def first_nonempty_line(text: str, default: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), default)
