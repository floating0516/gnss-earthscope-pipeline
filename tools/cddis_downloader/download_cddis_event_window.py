#!/usr/bin/env python3
"""Download CDDIS high-rate granules selected for an event candidate set."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from cddis_common import curl_download, write_tsv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"
DEFAULT_OUT_ROOT = ROOT / "data" / "cddis_highrate" / "events"

REQUEST_FIELDS = [
    "event_id",
    "station4",
    "radius_km",
    "distance_km",
    "filename",
    "url",
    "window_start_utc",
    "window_end_utc",
]

DOWNLOAD_FIELDS = [
    "event_id",
    "station4",
    "filename",
    "url",
    "local_file",
    "status",
    "size_bytes",
    "reason",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--radius-km", type=float, required=True)
    parser.add_argument("--out-dir", help="Output directory; default data/cddis_highrate/events/<event-id>")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cookie-file", default=str(Path.home() / ".urs_cookies"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def read_candidates(conn: sqlite3.Connection, event_id: str, radius_km: float) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT event_id, station4, radius_km, distance_km, filenames, urls,
                   window_start_utc, window_end_utc
            FROM event_cddis_station_candidates
            WHERE event_id = ? AND radius_km = ?
            ORDER BY distance_km, station4
            """,
            (event_id, radius_km),
        )
    )


def request_rows(candidates: list[sqlite3.Row]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        filenames = str(candidate["filenames"] or "").split()
        urls = str(candidate["urls"] or "").split()
        for filename, url in zip(filenames, urls):
            key = (str(candidate["station4"]), url)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "event_id": str(candidate["event_id"]),
                    "station4": str(candidate["station4"]),
                    "radius_km": f"{float(candidate['radius_km']):.0f}",
                    "distance_km": f"{float(candidate['distance_km']):.3f}",
                    "filename": filename,
                    "url": url,
                    "window_start_utc": str(candidate["window_start_utc"]),
                    "window_end_utc": str(candidate["window_end_utc"]),
                }
            )
    return rows


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUT_ROOT / args.event_id
    files_dir = out_dir / "files"
    manifests_dir = out_dir / "manifests"
    requested_tsv = manifests_dir / "cddis-event-requested.tsv"
    downloaded_tsv = manifests_dir / "cddis-event-downloaded.tsv"
    summary_json = manifests_dir / "cddis-event-summary.json"

    conn = sqlite3.connect(Path(args.db).expanduser())
    try:
        candidates = read_candidates(conn, args.event_id, args.radius_km)
    finally:
        conn.close()

    requests = request_rows(candidates)
    write_tsv(requested_tsv, requests, REQUEST_FIELDS)

    downloads: list[dict[str, str]] = []
    for row in requests:
        target = files_dir / row["station4"].lower() / row["filename"]
        status = "DRY_RUN"
        reason = ""
        if not args.dry_run:
            status, reason = curl_download(
                row["url"],
                target,
                timeout=args.timeout,
                cookie_file=Path(args.cookie_file),
                overwrite=args.overwrite,
            )
        downloads.append(
            {
                "event_id": row["event_id"],
                "station4": row["station4"],
                "filename": row["filename"],
                "url": row["url"],
                "local_file": str(target),
                "status": status,
                "size_bytes": "" if not target.exists() else str(target.stat().st_size),
                "reason": reason,
            }
        )
    write_tsv(downloaded_tsv, downloads, DOWNLOAD_FIELDS)

    ok_count = sum(1 for row in downloads if row["status"] == "OK")
    skip_count = sum(1 for row in downloads if row["status"] == "SKIP")
    fail_count = sum(1 for row in downloads if row["status"] == "FAIL")
    summary = {
        "provider": "CDDIS",
        "event_id": args.event_id,
        "radius_km": args.radius_km,
        "candidate_count": len(candidates),
        "requested_file_count": len(requests),
        "downloaded_count": ok_count,
        "skipped_existing_count": skip_count,
        "failed_count": fail_count,
        "dry_run": args.dry_run,
        "out_dir": str(out_dir),
        "requested_tsv": str(requested_tsv),
        "downloaded_tsv": str(downloaded_tsv),
        "summary_json": str(summary_json),
    }
    write_json(summary_json, summary)

    print(f"CDDIS event: {args.event_id}", file=sys.stderr)
    print(f"Radius: {args.radius_km:.0f} km", file=sys.stderr)
    print(f"Candidates: {len(candidates)}; requested files: {len(requests)}", file=sys.stderr)
    if args.dry_run:
        print("Dry run: downloads skipped", file=sys.stderr)
        return 0 if requests else 1
    print(f"Downloaded: {ok_count}; skipped: {skip_count}; failed: {fail_count}", file=sys.stderr)
    return 1 if fail_count or not requests else 0


if __name__ == "__main__":
    raise SystemExit(main())
