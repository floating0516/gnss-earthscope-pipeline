#!/usr/bin/env python3
"""Shared helpers for Geoscience Australia 1 Hz GNSS downloader tools."""

from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

GA_RINEX_API_URL = "https://data.gnss.ga.gov.au/api/rinexFiles"
GA_METADATA_API_URL = "https://metadata.gnss.ga.gov.au/api/siteLogs"
EARTH_RADIUS_KM = 6371.0088
USER_AGENT = "gnss-earthscope-pipeline ga-downloader"


@dataclass(frozen=True)
class GaRinexFile:
    station: str
    filename: str
    url: str
    start_time: dt.datetime
    file_type: str
    file_period: str
    rinex_version: str
    metadata_status: str
    size_bytes: int | None = None

    @property
    def slot_key(self) -> tuple[str, dt.datetime]:
        return self.station, self.start_time


def _public_a_records(host: str, timeout: int) -> list[str]:
    query = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": host, "type": "A"})
    request = urllib.request.Request(query, headers={"Accept": "application/dns-json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    records: list[str] = []
    for answer in payload.get("Answer", []):
        if answer.get("type") == 1 and isinstance(answer.get("data"), str):
            records.append(answer["data"])
    return records


def _fetch_s3_bytes_with_public_dns(url: str, timeout: int) -> bytes:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    if not host.endswith(".s3.ap-southeast-2.amazonaws.com"):
        raise RuntimeError("public-DNS S3 fallback only supports GA S3 URLs")
    errors: list[str] = []
    for address in _public_a_records(host, timeout):
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--fail",
            "--http1.1",
            "-4",
            "--connect-timeout",
            str(min(timeout, 60)),
            "--max-time",
            str(timeout),
            "--resolve",
            f"{host}:443:{address}",
            url,
        ]
        env = {key: value for key, value in os.environ.items() if key.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
        result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if result.returncode == 0:
            return result.stdout
        errors.append(result.stderr.decode("utf-8", errors="replace").strip())
    raise RuntimeError("GA S3 public-DNS fallback failed: " + "; ".join(error for error in errors if error))


def fetch_bytes(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last_error: Exception | None = None
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 ** attempt, 10))
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname and parsed.hostname.endswith(".s3.ap-southeast-2.amazonaws.com"):
        try:
            return _fetch_s3_bytes_with_public_dns(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to fetch {url}: {last_error}; S3 fallback: {exc}") from exc
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_json(url: str, timeout: int = 60) -> object:
    return json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8"))


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


def normalize_doy(value: str | int) -> int:
    doy = int(value)
    if doy < 1 or doy > 366:
        raise ValueError(f"Invalid day-of-year: {value}")
    return doy


def normalize_station(value: str) -> str:
    text = value.strip().upper()
    if not text:
        return ""
    if text.endswith(".GNSS") or text.endswith(".GPS"):
        text = text.split(".", 1)[0]
    return text[:4]


def unique_stations(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        station = normalize_station(value)
        if not station or station.startswith("#"):
            continue
        if station in seen:
            continue
        seen.add(station)
        out.append(station)
    return out


def read_station_file(path: Path) -> list[str]:
    stations: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for part in re.split(r"[,\s]+", raw):
            station = normalize_station(part)
            if station and not station.startswith("#"):
                stations.append(station)
    return unique_stations(stations)


def floor_to_quarter_hour(value: dt.datetime) -> dt.datetime:
    minute = (value.minute // 15) * 15
    return value.replace(minute=minute, second=0, microsecond=0)


def iter_required_slots(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    current = floor_to_quarter_hour(start)
    slots: list[dt.datetime] = []
    while current < end:
        slots.append(current)
        current += dt.timedelta(minutes=15)
    return slots


def event_current_slot_window(event_time: dt.datetime) -> tuple[dt.datetime, dt.datetime, list[dt.datetime]]:
    slot_anchor = floor_to_quarter_hour(event_time)
    return slot_anchor, slot_anchor + dt.timedelta(minutes=15), [slot_anchor]


def event_three_slot_window(event_time: dt.datetime) -> tuple[dt.datetime, dt.datetime, list[dt.datetime]]:
    slot_anchor = floor_to_quarter_hour(event_time)
    slots = [
        slot_anchor - dt.timedelta(minutes=15),
        slot_anchor,
        slot_anchor + dt.timedelta(minutes=15),
    ]
    return slots[0], slots[-1] + dt.timedelta(minutes=15), slots


def event_day_window(event_time: dt.datetime, hours: float) -> tuple[dt.datetime, dt.datetime]:
    start = event_time - dt.timedelta(hours=hours)
    end = event_time + dt.timedelta(hours=hours)
    day_start = event_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = event_time.replace(hour=23, minute=59, second=59, microsecond=0)
    return max(start, day_start), min(end, day_end)


def build_rinex_query_url(
    stations: list[str],
    start: dt.datetime,
    end: dt.datetime,
    api_url: str = GA_RINEX_API_URL,
) -> str:
    params = {
        "stationId": ",".join(sorted(unique_stations(stations))),
        "startDate": iso_utc(start),
        "endDate": iso_utc(end),
        "filePeriod": "15M",
        "fileType": "obs",
    }
    return api_url + "?" + urllib.parse.urlencode(params)


def filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    disposition = query.get("response-content-disposition", [""])[0]
    match = re.search(r'filename="?([^";]+)', disposition)
    if match:
        return match.group(1)
    return Path(parsed.path).name


def parse_ga_rinex_rows(payload: object) -> list[GaRinexFile]:
    if not isinstance(payload, list):
        raise ValueError("GA RINEX API did not return a JSON list")
    files: list[GaRinexFile] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        station = normalize_station(str(row.get("siteId") or ""))
        url = str(row.get("fileLocation") or "")
        start_text = str(row.get("startDate") or "")
        if not station or not url or not start_text:
            continue
        file_period = str(row.get("filePeriod") or "")
        file_type = str(row.get("fileType") or "")
        if file_period != "15M" or file_type != "obs":
            continue
        filename = filename_from_url(url)
        files.append(
            GaRinexFile(
                station=station,
                filename=filename,
                url=url,
                start_time=parse_utc(start_text),
                file_type=file_type,
                file_period=file_period,
                rinex_version=str(row.get("rinexVersion") or ""),
                metadata_status=str(row.get("metadataStatus") or ""),
                size_bytes=int(row["fileSize"]) if row.get("fileSize") is not None else None,
            )
        )
    return sorted(files, key=lambda item: (item.station, item.start_time, item.filename))


def list_ga_files(
    stations: list[str],
    start: dt.datetime,
    end: dt.datetime,
    api_url: str = GA_RINEX_API_URL,
    chunk_size: int = 40,
) -> list[GaRinexFile]:
    result: list[GaRinexFile] = []
    station_list = unique_stations(stations)
    for index in range(0, len(station_list), chunk_size):
        chunk = station_list[index : index + chunk_size]
        url = build_rinex_query_url(chunk, start, end, api_url=api_url)
        try:
            payload = fetch_json(url, timeout=90)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        except RuntimeError as exc:
            if "HTTP Error 404" in str(exc):
                continue
            raise
        result.extend(parse_ga_rinex_rows(payload))
    return sorted(result, key=lambda item: (item.station, item.start_time, item.filename))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def split_rinex_header(path: Path) -> tuple[list[str], list[str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines):
        if "END OF HEADER" in line:
            return lines[: index + 1], lines[index + 1 :]
    raise ValueError(f"RINEX file has no END OF HEADER: {path}")


def rinex_interval_is_one_second(path: Path) -> bool:
    header, _ = split_rinex_header(path)
    for line in header:
        if "INTERVAL" not in line:
            continue
        try:
            return abs(float(line[:20].strip()) - 1.0) < 0.001
        except ValueError:
            return False
    return "_01S_" in path.name


def decompress_gzip(path: Path) -> Path:
    if path.suffix != ".gz":
        return path
    target = path.with_suffix("")
    with gzip.open(path, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return target


def convert_hatanaka(path: Path) -> Path:
    lower = path.name.lower()
    if not (lower.endswith(".crx") or re.search(r"\.\d{2}d$", lower)):
        return path
    converter = shutil.which("CRX2RNX") or shutil.which("crx2rnx")
    if converter is None:
        raise FileNotFoundError("CRX2RNX/crx2rnx not found in PATH")
    subprocess.run([converter, str(path)], check=True, cwd=str(path.parent))
    if lower.endswith(".crx"):
        target = path.with_suffix(".rnx")
    else:
        target = path.with_name(path.name[:-1] + "o")
    if not target.exists():
        candidates = sorted(path.parent.glob(path.stem + "*.rnx")) + sorted(path.parent.glob(path.stem[:-1] + "*.o"))
        if not candidates:
            raise FileNotFoundError(f"Converted RINEX not found for {path}")
        target = candidates[0]
    return target


def prepare_rinex_file(path: Path, prepared_dir: Path) -> Path:
    prepared_dir.mkdir(parents=True, exist_ok=True)
    work = prepared_dir / path.name
    if not work.exists() or work.stat().st_size == 0:
        shutil.copy2(path, work)
    work = decompress_gzip(work)
    work = convert_hatanaka(work)
    return work


def combine_rinex_files(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("No RINEX inputs to combine.")
    output.parent.mkdir(parents=True, exist_ok=True)
    first_header, first_body = split_rinex_header(inputs[0])
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for line in first_header:
            handle.write(line.rstrip("\n") + "\n")
        for line in first_body:
            handle.write(line.rstrip("\n") + "\n")
        for path in inputs[1:]:
            _, body = split_rinex_header(path)
            for line in body:
                handle.write(line.rstrip("\n") + "\n")


def splice_rinex_with_gfzrnx(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("No RINEX inputs to splice.")
    gfzrnx = shutil.which("gfzrnx")
    if gfzrnx is None:
        raise FileNotFoundError("gfzrnx not found in PATH")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [gfzrnx, "-finp", *[str(path) for path in inputs], "-fout", str(output), "-kv", "-try_append", "900"],
        check=True,
    )


def merge_rinex_files(inputs: list[Path], output: Path, method: str = "auto") -> str:
    if method not in {"auto", "gfzrnx", "python"}:
        raise ValueError(f"Unknown merge method: {method}")
    if method in {"auto", "gfzrnx"} and shutil.which("gfzrnx"):
        splice_rinex_with_gfzrnx(inputs, output)
        return "gfzrnx"
    if method == "gfzrnx":
        raise FileNotFoundError("gfzrnx requested but not found in PATH")
    combine_rinex_files(inputs, output)
    return "python"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2
    )
    return EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
