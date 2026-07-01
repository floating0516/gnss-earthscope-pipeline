#!/usr/bin/env python3
"""Query and download NASA CDDIS high-rate GNSS granules for a UTC window."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cddis_common import (
    CDDIS_HIGHRATE_COLLECTION,
    CMR_GRANULES_URL,
    CddisGranule,
    curl_download,
    filter_granules_by_station,
    iso_utc,
    parse_utc,
    query_cmr_granules,
    query_directory_granules,
    read_station_file,
    unique_stations,
    write_json,
    write_tsv,
)

QUERY_FIELDS = [
    "provider",
    "collection_concept_id",
    "granule_id",
    "producer_granule_id",
    "granule_start_utc",
    "granule_end_utc",
    "station4",
    "station9",
    "filename",
    "url",
    "selected",
]

DOWNLOAD_FIELDS = [
    "provider",
    "filename",
    "url",
    "local_file",
    "status",
    "size_bytes",
    "reason",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-time", required=True, help="UTC window start, e.g. 2026-06-23T23:00:00Z")
    parser.add_argument("--end-time", required=True, help="UTC window end, e.g. 2026-06-23T23:15:00Z")
    parser.add_argument("--out-dir", required=True, help="Output directory for CDDIS files and manifests")
    parser.add_argument("--stations", default="", help="Station codes separated by comma/space")
    parser.add_argument("--stations-file", help="Optional station-code file")
    parser.add_argument("--collection-concept-id", default=CDDIS_HIGHRATE_COLLECTION)
    parser.add_argument("--cmr-url", default=CMR_GRANULES_URL)
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--timeout", type=int, default=180, help="Curl/CMR timeout in seconds")
    parser.add_argument("--cookie-file", default=str(Path.home() / ".urs_cookies"), help="Earthdata cookie jar path")
    parser.add_argument("--query-mode", choices=["auto", "cmr", "directory"], default="auto")
    parser.add_argument("--rinex-subdir", help="CDDIS high-rate subdirectory such as 26o; default is YYo from start time")
    parser.add_argument("--dry-run", action="store_true", help="Query CMR and write manifests without downloading files")
    parser.add_argument("--overwrite", action="store_true", help="Redownload files even when a non-empty local file exists")
    parser.add_argument("station_args", nargs="*")
    return parser.parse_args(argv)


def parse_station_args(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.stations:
        values.extend(args.stations.replace(",", " ").split())
    if args.stations_file:
        values.extend(read_station_file(Path(args.stations_file)))
    values.extend(args.station_args)
    return unique_stations(values)


def granule_query_row(granule: CddisGranule, *, collection_concept_id: str, selected: bool) -> dict[str, str]:
    return {
        "provider": "CDDIS",
        "collection_concept_id": collection_concept_id,
        "granule_id": granule.granule_id,
        "producer_granule_id": granule.producer_granule_id,
        "granule_start_utc": granule.start_utc,
        "granule_end_utc": granule.end_utc,
        "station4": granule.station4,
        "station9": granule.station9,
        "filename": granule.filename,
        "url": granule.url,
        "selected": "YES" if selected else "NO",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start = parse_utc(args.start_time)
    end = parse_utc(args.end_time)
    if end <= start:
        raise SystemExit("--end-time must be later than --start-time")
    if args.page_size < 1:
        raise SystemExit("--page-size must be positive")

    stations = parse_station_args(args)
    out_dir = Path(args.out_dir).expanduser()
    files_dir = out_dir / "files"
    query_tsv = out_dir / "cddis-query-results.tsv"
    downloads_tsv = out_dir / "cddis-downloads.tsv"
    summary_json = out_dir / "cddis-summary.json"

    print(f"CDDIS window UTC: {iso_utc(start)} -> {iso_utc(end)}", file=sys.stderr)
    print(f"Stations: {len(stations) if stations else 'all'}", file=sys.stderr)
    print(f"Output: {out_dir}", file=sys.stderr)

    query_mode_used = args.query_mode
    query_warnings: list[str] = []
    try:
        if args.query_mode == "directory":
            all_granules = query_directory_granules(
                start,
                end,
                rinex_subdir=args.rinex_subdir,
                timeout=args.timeout,
                cookie_file=Path(args.cookie_file),
            )
        else:
            all_granules = query_cmr_granules(
                start,
                end,
                collection_concept_id=args.collection_concept_id,
                cmr_url=args.cmr_url,
                page_size=args.page_size,
                timeout=args.timeout,
            )
            if args.query_mode == "auto" and not all_granules:
                query_warnings.append("CMR returned no granules; used authenticated CDDIS directory listing fallback")
                query_mode_used = "directory"
                all_granules = query_directory_granules(
                    start,
                    end,
                    rinex_subdir=args.rinex_subdir,
                    timeout=args.timeout,
                    cookie_file=Path(args.cookie_file),
                )
    except RuntimeError as exc:
        if args.query_mode == "auto":
            query_warnings.append(f"CMR failed ({exc}); used authenticated CDDIS directory listing fallback")
            query_mode_used = "directory"
            try:
                all_granules = query_directory_granules(
                    start,
                    end,
                    rinex_subdir=args.rinex_subdir,
                    timeout=args.timeout,
                    cookie_file=Path(args.cookie_file),
                )
            except RuntimeError as fallback_exc:
                write_tsv(query_tsv, [], QUERY_FIELDS)
                write_tsv(downloads_tsv, [], DOWNLOAD_FIELDS)
                write_json(
                    summary_json,
                    {
                        "provider": "CDDIS",
                        "collection_concept_id": args.collection_concept_id,
                        "query_mode": query_mode_used,
                        "query_warnings": query_warnings,
                        "start_time_utc": iso_utc(start),
                        "end_time_utc": iso_utc(end),
                        "stations": stations,
                        "dry_run": args.dry_run,
                        "status": "FAIL",
                        "reason": str(fallback_exc),
                        "total_granules_seen": 0,
                        "selected_granules": 0,
                        "downloaded_count": 0,
                        "skipped_existing_count": 0,
                        "failed_count": 0,
                        "query_results_tsv": str(query_tsv),
                        "downloads_tsv": str(downloads_tsv),
                        "summary_json": str(summary_json),
                        "files_dir": str(files_dir),
                    },
                )
                print(f"CDDIS query failed: {fallback_exc}", file=sys.stderr)
                return 1
        else:
            write_tsv(query_tsv, [], QUERY_FIELDS)
            write_tsv(downloads_tsv, [], DOWNLOAD_FIELDS)
            write_json(
                summary_json,
                {
                    "provider": "CDDIS",
                    "collection_concept_id": args.collection_concept_id,
                    "query_mode": query_mode_used,
                    "query_warnings": query_warnings,
                    "start_time_utc": iso_utc(start),
                    "end_time_utc": iso_utc(end),
                    "stations": stations,
                    "dry_run": args.dry_run,
                    "status": "FAIL",
                    "reason": str(exc),
                    "total_granules_seen": 0,
                    "selected_granules": 0,
                    "downloaded_count": 0,
                    "skipped_existing_count": 0,
                    "failed_count": 0,
                    "query_results_tsv": str(query_tsv),
                    "downloads_tsv": str(downloads_tsv),
                    "summary_json": str(summary_json),
                    "files_dir": str(files_dir),
                },
            )
            print(f"CDDIS query failed: {exc}", file=sys.stderr)
            return 1

    selected_granules = filter_granules_by_station(all_granules, stations)
    selected_urls = {granule.url for granule in selected_granules}

    query_rows = [
        granule_query_row(
            granule,
            collection_concept_id=args.collection_concept_id,
            selected=granule.url in selected_urls,
        )
        for granule in all_granules
    ]
    write_tsv(query_tsv, query_rows, QUERY_FIELDS)

    download_rows: list[dict[str, str]] = []
    for granule in selected_granules:
        target = files_dir / granule.filename
        status = "DRY_RUN"
        reason = ""
        if not args.dry_run:
            status, reason = curl_download(
                granule.url,
                target,
                timeout=args.timeout,
                cookie_file=Path(args.cookie_file),
                overwrite=args.overwrite,
            )
        download_rows.append(
            {
                "provider": "CDDIS",
                "filename": granule.filename,
                "url": granule.url,
                "local_file": str(target),
                "status": status,
                "size_bytes": "" if not target.exists() else str(target.stat().st_size),
                "reason": reason,
            }
        )
    write_tsv(downloads_tsv, download_rows, DOWNLOAD_FIELDS)

    downloaded_count = sum(1 for row in download_rows if row["status"] == "OK")
    skipped_count = sum(1 for row in download_rows if row["status"] == "SKIP")
    failed_count = sum(1 for row in download_rows if row["status"] == "FAIL")
    summary = {
        "provider": "CDDIS",
        "collection_concept_id": args.collection_concept_id,
        "query_mode": query_mode_used,
        "query_warnings": query_warnings,
        "start_time_utc": iso_utc(start),
        "end_time_utc": iso_utc(end),
        "stations": stations,
        "dry_run": args.dry_run,
        "total_granules_seen": len(all_granules),
        "selected_granules": len(selected_granules),
        "downloaded_count": downloaded_count,
        "skipped_existing_count": skipped_count,
        "failed_count": failed_count,
        "query_results_tsv": str(query_tsv),
        "downloads_tsv": str(downloads_tsv),
        "summary_json": str(summary_json),
        "files_dir": str(files_dir),
    }
    write_json(summary_json, summary)

    for warning in query_warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Query mode: {query_mode_used}", file=sys.stderr)
    print(f"Granules: {len(all_granules)}", file=sys.stderr)
    print(f"Selected granules: {len(selected_granules)}", file=sys.stderr)
    if args.dry_run:
        print("Dry run: downloads skipped", file=sys.stderr)
        return 0
    print(f"Downloaded: {downloaded_count}; skipped: {skipped_count}; failed: {failed_count}", file=sys.stderr)
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
