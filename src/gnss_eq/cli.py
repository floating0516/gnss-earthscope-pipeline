from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "tools"
DOWNLOADER_TOOLS = TOOLS / "earthscope_downloader"
PRIDE_TOOLS = TOOLS / "pride_processor"
EARTHSCOPE_METADATA_URL = "https://web-services.unavco.org/backoffice-geoserver-test/gnss/ows"
DEFAULT_AVAILABILITY_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"


def absolute_path(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path.resolve(strict=False))


def run_command(args: list[str], dry_print: bool = False) -> int:
    if dry_print:
        print(" ".join(shlex_quote(arg) for arg in args))
        return 0
    return subprocess.call(args)


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def add_common_workflow_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hours", default="3")
    parser.add_argument("--interval", default="1")
    parser.add_argument("--max-stations", default="0")
    parser.add_argument("--run-root", default=str(ROOT / "runs"))
    parser.add_argument("--obs-root", default=str(ROOT / "data" / "obs"))
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--skip-process", action="store_true")
    parser.add_argument("--skip-plot", action="store_true")
    parser.add_argument("--post-seconds", default="200")
    parser.add_argument("--cleanup-downloads", action="store_true", default=True)
    parser.add_argument("--cleanup-pride-workdir", action="store_true", default=True)
    parser.add_argument("--cleanup-obs", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")


def cmd_run_event(args: argparse.Namespace) -> int:
    run_root = absolute_path(args.run_root)
    obs_root = absolute_path(args.obs_root)
    cmd = [
        str(SCRIPTS / "workflows" / "run_event_1hz_pride_workflow.sh"),
        "--event-id",
        args.event_id,
        "--event-time",
        args.event_time,
        "--hours",
        args.hours,
        "--interval",
        args.interval,
        "--run-root",
        run_root,
        "--obs-root",
        obs_root,
        "--post-seconds",
        args.post_seconds,
    ]
    if args.stations:
        cmd.extend(["--stations", args.stations])
    if args.stations_file:
        cmd.extend(["--stations-file", args.stations_file])
    if int(args.max_stations) > 0:
        cmd.extend(["--max-stations", args.max_stations])
    for flag, enabled in [
        ("--skip-download", args.skip_download),
        ("--force-download", args.force_download),
        ("--allow-partial", args.allow_partial),
        ("--skip-process", args.skip_process),
        ("--skip-plot", args.skip_plot),
        ("--cleanup-downloads", args.cleanup_downloads),
        ("--cleanup-pride-workdir", args.cleanup_pride_workdir),
        ("--cleanup-obs", args.cleanup_obs),
        ("--dry-run", args.dry_run),
    ]:
        if enabled:
            cmd.append(flag)
    return run_command(cmd)


def cmd_run_batch(args: argparse.Namespace) -> int:
    run_root = absolute_path(args.run_root)
    obs_root = absolute_path(args.obs_root)
    csv_path = args.csv
    if csv_path == "-":
        state_csv = Path(args.state_csv) if args.state_csv else ROOT / "data" / "batches" / f"stdin-batch-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
        state_csv.parent.mkdir(parents=True, exist_ok=True)
        state_csv.write_text(sys.stdin.read())
        csv_path = str(state_csv)
        print(f"State CSV: {csv_path}", file=sys.stderr)

    cmd = [
        str(SCRIPTS / "workflows" / "run_event_batch_workflow.sh"),
        "--csv",
        csv_path,
        "--timeout",
        str(args.timeout),
        "--hours",
        args.hours,
        "--interval",
        args.interval,
        "--run-root",
        run_root,
        "--obs-root",
        obs_root,
        "--post-seconds",
        args.post_seconds,
    ]
    if args.summary:
        cmd.extend(["--summary", args.summary])
    if int(args.max_stations) > 0:
        cmd.extend(["--max-stations", args.max_stations])
    for flag, enabled in [
        ("--skip-download", args.skip_download),
        ("--force-download", args.force_download),
        ("--no-allow-partial", args.no_allow_partial),
        ("--skip-process", args.skip_process),
        ("--skip-plot", args.skip_plot),
        ("--cleanup-downloads", args.cleanup_downloads),
        ("--cleanup-pride-workdir", args.cleanup_pride_workdir),
        ("--cleanup-obs", args.cleanup_obs),
        ("--rerun-ok", args.rerun_ok),
        ("--dry-run", args.dry_run),
    ]:
        if enabled:
            cmd.append(flag)
    return run_command(cmd)


def cmd_quality(args: argparse.Namespace) -> int:
    kin_files = list(args.kin_files)
    if args.kin_manifest:
        kin_files.extend(
            line.strip()
            for line in Path(args.kin_manifest).read_text().splitlines()
            if line.strip()
        )
    cmd = [
        sys.executable,
        str(SCRIPTS / "quality" / "compute_kin_quality.py"),
        "--event-time",
        args.event_time,
        "--expected-hours-each-side",
        str(args.expected_hours_each_side),
        "--min-epochs",
        str(args.min_epochs),
        "--min-coverage-ratio",
        str(args.min_coverage_ratio),
        "--max-pre-rms-cm",
        str(args.max_pre_rms_cm),
        "--max-epoch-jump-cm",
        str(args.max_epoch_jump_cm),
        "--event-step-window",
        str(args.event_step_window),
    ]
    if args.out_tsv:
        cmd.extend(["--out-tsv", args.out_tsv])
    if args.out_json:
        cmd.extend(["--out-json", args.out_json])
    cmd.extend(kin_files)
    return run_command(cmd)


def cmd_update_availability(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        str(SCRIPTS / "availability" / "update_earthscope_availability.py"),
        "--db",
        args.db,
        "--delay",
        str(args.delay),
        "--timeout",
        str(args.timeout),
        "--max-retries",
        str(args.max_retries),
        "--retry-delay",
        str(args.retry_delay),
    ]
    if args.date:
        cmd.extend(["--date", args.date])
    if args.recent_days is not None:
        cmd.extend(["--recent-days", str(args.recent_days)])
    if args.start_date:
        cmd.extend(["--start-date", args.start_date])
    if args.end_date:
        cmd.extend(["--end-date", args.end_date])
    if args.force:
        cmd.append("--force")
    if args.dry_run:
        cmd.append("--dry-run")
    return run_command(cmd)


def cmd_select_stations(args: argparse.Namespace) -> int:
    script = DOWNLOADER_TOOLS / "select_stations_by_radius.py"
    cmd = [
        sys.executable,
        str(script),
        "--event-id",
        args.event_id,
        "--latitude",
        str(args.latitude),
        "--longitude",
        str(args.longitude),
        "--magnitude",
        str(args.magnitude),
        "--min-sampling-hz",
        str(args.min_sampling_hz),
        "--output-root",
        args.output_root,
    ]
    for inventory in args.inventory:
        cmd.extend(["--inventory", inventory])
    if args.radius_km:
        cmd.extend(["--radius-km", str(args.radius_km)])
    if args.print_stations:
        cmd.append("--print-stations")
    return run_command(cmd)


def read_table(path: str) -> list[dict[str, str]]:
    if path == "-":
        text = sys.stdin.read()
        if not text.strip():
            return []
        if text.lstrip().startswith("["):
            return json.loads(text)
        return list(csv.DictReader(text.splitlines()))

    source = Path(path)
    text = source.read_text()
    if source.suffix.lower() == ".json" or text.lstrip().startswith("["):
        return json.loads(text)
    return list(csv.DictReader(text.splitlines()))


def format_station_list(stations_file: Path, max_stations: int) -> str:
    stations = [line.strip().upper() for line in stations_file.read_text().splitlines() if line.strip()]
    if max_stations > 0:
        stations = stations[:max_stations]
    return " ".join(stations)


def event_day(value: str) -> tuple[str, str, str, str]:
    dt = datetime.fromisoformat(parse_utc(value).replace("Z", "+00:00"))
    year = dt.strftime("%Y")
    doy = dt.strftime("%j")
    start = dt.strftime("%Y-%m-%d")
    end = datetime.fromtimestamp(dt.timestamp() + 86400, tz=timezone.utc).strftime("%Y-%m-%d")
    return year, doy, start, end


def event_date(value: str) -> str:
    return event_day(value)[2]


def earthscope_token() -> str:
    result = subprocess.run(["es", "user", "get-access-token"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"failed to obtain EarthScope token: {result.stderr.strip()}")
    return result.stdout.strip()


def fetch_earthscope_metadata(event_time: str, cache_root: Path, token: str | None) -> Path:
    year, doy, start, end = event_day(event_time)
    cache_dir = cache_root / year
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"earthscope-metadata-{year}-{doy}-le1.json"
    if cache_file.exists() and cache_file.stat().st_size > 0:
        return cache_file

    if token is None:
        token = earthscope_token()

    query = (
        f"{EARTHSCOPE_METADATA_URL}?"
        "service=WFS&version=1.0.0&request=GetFeature"
        "&typeName=gnss%3Ametadata_search_data_availability"
        "&outputFormat=application%2Fjson"
        f"&viewparams=start_date:{start};end_date:{end};sample_interval:%3C%3D1;data_type:rinex;"
    )
    request = Request(query, headers={"Authorization": f"Bearer {token}", "User-Agent": "gnss-earthscope-pipeline/0.1"})
    with urlopen(request, timeout=120) as response:
        cache_file.write_bytes(response.read())
    return cache_file


def read_available_1hz_stations(metadata_file: Path) -> set[str]:
    payload = json.loads(metadata_file.read_text())
    stations = set()
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        try:
            sample_interval = float(props.get("sample_interval"))
        except (TypeError, ValueError):
            continue
        site_code = str(props.get("site_code") or "").strip().upper()
        if site_code and sample_interval == 1.0:
            stations.add(site_code)
    return stations


def read_available_stations_from_db(db_path: Path, date: str) -> set[str] | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT status FROM daily_listing WHERE date = ?", (date,)).fetchone()
        if not row or row[0] != "OK":
            return None
        return {
            str(item[0]).upper()
            for item in conn.execute(
                "SELECT station FROM station_day_availability WHERE date = ? AND has_1hz = 1",
                (date,),
            )
        }
    finally:
        conn.close()


def read_selected_stations(selection_csv: Path) -> list[str]:
    with selection_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    stations = []
    for row in rows:
        station = (row.get("Station") or row.get("station") or "").strip().upper()
        if station:
            stations.append(station)
    return stations


def cmd_prepare_batch(args: argparse.Namespace) -> int:
    events = read_table(args.events)
    output_root = Path(args.selection_output_root)
    batch_rows: list[dict[str, str]] = []
    token: str | None = None

    for row in events:
        event_id = (row.get("event_id") or row.get("id") or "").strip()
        event_time = (row.get("event_time") or row.get("time_utc") or "").strip()
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        magnitude = row.get("magnitude") or row.get("mag")

        if not event_id or not event_time or latitude in {None, ""} or longitude in {None, ""} or magnitude in {None, ""}:
            print(f"Skipping incomplete event row: {row}", file=sys.stderr)
            continue

        cmd = [
            sys.executable,
            str(DOWNLOADER_TOOLS / "select_stations_by_radius.py"),
            "--event-id",
            event_id,
            "--latitude",
            str(latitude),
            "--longitude",
            str(longitude),
            "--magnitude",
            str(magnitude),
            "--min-sampling-hz",
            str(args.min_sampling_hz),
            "--output-root",
            str(output_root),
        ]
        for inventory in args.inventory:
            cmd.extend(["--inventory", inventory])
        if args.radius_km:
            cmd.extend(["--radius-km", str(args.radius_km)])

        if args.verbose:
            print(" ".join(shlex_quote(part) for part in cmd), file=sys.stderr)

        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr, end="")
            print(result.stderr, file=sys.stderr, end="")
            if args.keep_failed:
                batch_rows.append({"event_id": event_id, "event_time": event_time, "stations": "", "status": "NO_STATIONS"})
                continue
            return result.returncode

        selection_dir = output_root / event_id
        stations_file = selection_dir / "stations.txt"
        selection_csv = selection_dir / "stations_within_radius.csv"
        selected_stations = read_selected_stations(selection_csv) if selection_csv.exists() else [
            line.strip().upper() for line in stations_file.read_text().splitlines() if line.strip()
        ]

        if args.earthscope_availability:
            try:
                available: set[str] | None = None
                availability_date = event_date(event_time)
                if args.availability_source in {"sqlite", "auto"}:
                    available = read_available_stations_from_db(Path(args.availability_db), availability_date)
                    if available is not None and args.verbose:
                        print(
                            f"Using SQLite EarthScope availability for {event_id} on {availability_date}: "
                            f"{len(available)} stations",
                            file=sys.stderr,
                        )
                if available is None:
                    if args.availability_source == "sqlite":
                        raise RuntimeError(
                            f"availability DB has no OK daily listing for {availability_date}: {args.availability_db}"
                        )
                    metadata_file = fetch_earthscope_metadata(event_time, Path(args.metadata_cache_root), token)
                    available = read_available_1hz_stations(metadata_file)
                    if args.verbose:
                        print(
                            f"Using WFS EarthScope availability for {event_id} on {availability_date}: "
                            f"{len(available)} stations",
                            file=sys.stderr,
                        )
                selected_stations = [station for station in selected_stations if station in available]
            except Exception as exc:  # noqa: BLE001
                if args.allow_unverified_stations:
                    print(f"WARNING: EarthScope availability check failed for {event_id}: {exc}", file=sys.stderr)
                else:
                    print(f"EarthScope availability check failed for {event_id}: {exc}", file=sys.stderr)
                    return 1

        if args.max_stations > 0:
            selected_stations = selected_stations[: args.max_stations]
        stations = " ".join(selected_stations)
        status = "" if stations else "NO_STATIONS"
        if not stations and not args.keep_failed:
            print(f"No stations selected for event: {event_id}", file=sys.stderr)
            return 1
        batch_rows.append({"event_id": event_id, "event_time": event_time, "stations": stations, "status": status})

    fieldnames = ["event_id", "event_time", "stations", "status"]
    if args.output == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(batch_rows)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(batch_rows)
        print(f"Batch CSV: {out}", file=sys.stderr)
    return 0


def parse_utc(value: str) -> str:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def cmd_search_events(args: argparse.Namespace) -> int:
    params = {
        "format": "geojson",
        "orderby": args.orderby,
    }
    optional = {
        "starttime": args.starttime,
        "endtime": args.endtime,
        "minmagnitude": args.min_magnitude,
        "maxmagnitude": args.max_magnitude,
        "latitude": args.latitude,
        "longitude": args.longitude,
        "maxradiuskm": args.max_radius_km,
        "limit": args.limit,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "gnss-earthscope-pipeline/0.1"})
    with urlopen(request, timeout=args.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    features = payload.get("features", [])
    rows = []
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        event_time = datetime.fromtimestamp(props.get("time", 0) / 1000, tz=timezone.utc)
        rows.append(
            {
                "event_id": feature.get("id", ""),
                "event_time": event_time.isoformat().replace("+00:00", "Z"),
                "magnitude": props.get("mag", ""),
                "place": props.get("place", ""),
                "longitude": coords[0],
                "latitude": coords[1],
                "depth_km": coords[2],
                "usgs_url": props.get("url", ""),
            }
        )

    if args.format == "csv":
        fieldnames = ["event_id", "event_time", "magnitude", "longitude", "latitude", "depth_km", "place", "usgs_url"]
        if args.output and args.output != "-":
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    elif args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_check_env(_: argparse.Namespace) -> int:
    checks = [
        ("bash", shutil.which("bash")),
        ("python3", shutil.which("python3")),
        ("timeout", shutil.which("timeout")),
        ("pdp3", shutil.which("pdp3")),
        ("run-event script", str(SCRIPTS / "workflows" / "run_event_1hz_pride_workflow.sh") if (SCRIPTS / "workflows" / "run_event_1hz_pride_workflow.sh").exists() else None),
        ("run-batch script", str(SCRIPTS / "workflows" / "run_event_batch_workflow.sh") if (SCRIPTS / "workflows" / "run_event_batch_workflow.sh").exists() else None),
        ("downloader script", str(DOWNLOADER_TOOLS / "download_earthscope_default.sh") if (DOWNLOADER_TOOLS / "download_earthscope_default.sh").exists() else None),
        ("PRIDE processor script", str(PRIDE_TOOLS / "process_event_window.sh") if (PRIDE_TOOLS / "process_event_window.sh").exists() else None),
        ("ENU plot script", str(PRIDE_TOOLS / "plot_enu_svg.py") if (PRIDE_TOOLS / "plot_enu_svg.py").exists() else None),
        ("select-stations script", str(DOWNLOADER_TOOLS / "select_stations_by_radius.py") if (DOWNLOADER_TOOLS / "select_stations_by_radius.py").exists() else None),
    ]
    failed = False
    for name, value in checks:
        status = "OK" if value else "MISSING"
        print(f"{status}\t{name}\t{value or ''}")
        if not value and name in {"bash", "python3", "timeout", "run-event script", "run-batch script"}:
            failed = True
    pride_bin = os.environ.get("PRIDE_BIN_DIR")
    earthscope_bin = os.environ.get("EARTHSCOPE_ENV_BIN")
    print(f"INFO\tPRIDE_BIN_DIR\t{pride_bin or '(not set)'}")
    print(f"INFO\tEARTHSCOPE_ENV_BIN\t{earthscope_bin or '(not set)'}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gnss-eq", description="GNSS earthquake workflow CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_event = sub.add_parser("run-event", help="Run one 1 Hz GNSS + PRIDE event workflow.")
    run_event.add_argument("--event-id", required=True)
    run_event.add_argument("--event-time", required=True)
    run_event.add_argument("--stations")
    run_event.add_argument("--stations-file")
    run_event.add_argument("--allow-partial", action="store_true")
    add_common_workflow_flags(run_event)
    run_event.set_defaults(func=cmd_run_event)

    run_batch = sub.add_parser(
        "run-batch",
        help="Run resumable CSV batch workflow. Rows with status=OK are skipped unless --rerun-ok is set.",
    )
    run_batch.add_argument("--csv", required=True, help="Batch CSV path, or '-' to read CSV from stdin into a state file.")
    run_batch.add_argument("--state-csv", help="State CSV path used when --csv - is provided.")
    run_batch.add_argument("--timeout", default="3600")
    run_batch.add_argument("--summary")
    run_batch.add_argument("--rerun-ok", action="store_true")
    run_batch.add_argument("--no-allow-partial", action="store_true")
    add_common_workflow_flags(run_batch)
    run_batch.set_defaults(func=cmd_run_batch)

    quality = sub.add_parser("quality", help="Compute epoch coverage, ENU RMS, and jump metrics from kin_* files.")
    quality.add_argument("--event-time", required=True)
    quality.add_argument("--expected-hours-each-side", type=float, default=0.0)
    quality.add_argument("--kin-manifest", help="Text file containing one kin_* path per line.")
    quality.add_argument("--out-tsv")
    quality.add_argument("--out-json")
    quality.add_argument("--min-epochs", type=int, default=60)
    quality.add_argument("--min-coverage-ratio", type=float, default=0.80)
    quality.add_argument("--max-pre-rms-cm", type=float, default=10.0)
    quality.add_argument("--max-epoch-jump-cm", type=float, default=50.0)
    quality.add_argument("--event-step-window", type=float, default=30.0)
    quality.add_argument("kin_files", nargs="*")
    quality.set_defaults(func=cmd_quality)

    update = sub.add_parser("update-availability", help="Build/update the local EarthScope 1 Hz availability SQLite DB.")
    scope = update.add_mutually_exclusive_group()
    scope.add_argument("--date", help="Single UTC date, YYYY-MM-DD.")
    scope.add_argument("--recent-days", type=int, help="Update the last N UTC dates including today.")
    update.add_argument("--start-date", help="Start UTC date, YYYY-MM-DD.")
    update.add_argument("--end-date", help="End UTC date, YYYY-MM-DD.")
    update.add_argument("--db", default=str(ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"))
    update.add_argument("--delay", type=float, default=1.5)
    update.add_argument("--timeout", type=float, default=60.0)
    update.add_argument("--max-retries", type=int, default=3)
    update.add_argument("--retry-delay", type=float, default=30.0)
    update.add_argument("--force", action="store_true")
    update.add_argument("--dry-run", action="store_true")
    update.set_defaults(func=cmd_update_availability)

    select = sub.add_parser("select-stations", help="Select GNSS stations by event radius.")
    select.add_argument("--event-id", required=True)
    select.add_argument("--latitude", type=float, required=True)
    select.add_argument("--longitude", type=float, required=True)
    select.add_argument("--magnitude", type=float, required=True)
    select.add_argument("--inventory", action="append", required=True)
    select.add_argument("--radius-km", type=float)
    select.add_argument("--min-sampling-hz", type=float, default=1.0)
    select.add_argument("--output-root", default=str(ROOT / "data" / "station_selection"))
    select.add_argument("--print-stations", action="store_true")
    select.set_defaults(func=cmd_select_stations)

    prepare = sub.add_parser("prepare-batch", help="Select stations for searched events and write run-batch CSV.")
    prepare.add_argument("--events", required=True, help="Event CSV/JSON from search-events, or '-' for stdin.")
    prepare.add_argument("--inventory", action="append", required=True)
    prepare.add_argument("--output", default="-", help="Batch CSV output path, or '-' for stdout.")
    prepare.add_argument("--selection-output-root", default=str(ROOT / "data" / "station_selection"))
    prepare.add_argument("--radius-km", type=float)
    prepare.add_argument("--min-sampling-hz", type=float, default=1.0)
    prepare.add_argument("--max-stations", type=int, default=0)
    prepare.add_argument(
        "--earthscope-availability",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Filter selected stations through EarthScope same-day 1 Hz availability. Enabled by default.",
    )
    prepare.add_argument(
        "--availability-source",
        choices=["auto", "sqlite", "wfs"],
        default="auto",
        help="Availability source. auto uses SQLite when the event day is indexed, then falls back to WFS metadata.",
    )
    prepare.add_argument("--availability-db", default=str(DEFAULT_AVAILABILITY_DB))
    prepare.add_argument("--metadata-cache-root", default=str(ROOT / "data" / "earthscope_metadata"))
    prepare.add_argument(
        "--allow-unverified-stations",
        action="store_true",
        help="Continue with radius-selected stations if the EarthScope availability check fails.",
    )
    prepare.add_argument("--keep-failed", action="store_true", help="Keep events with no selected stations as status=NO_STATIONS.")
    prepare.add_argument("--verbose", action="store_true")
    prepare.set_defaults(func=cmd_prepare_batch)

    search = sub.add_parser("search-events", help="Search USGS events and emit JSON or CSV.")
    search.add_argument("--starttime", type=parse_utc)
    search.add_argument("--endtime", type=parse_utc)
    search.add_argument("--min-magnitude", type=float)
    search.add_argument("--max-magnitude", type=float)
    search.add_argument("--latitude", type=float)
    search.add_argument("--longitude", type=float)
    search.add_argument("--max-radius-km", type=float)
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--orderby", default="time", choices=["time", "time-asc", "magnitude", "magnitude-asc"])
    search.add_argument("--timeout", type=int, default=30)
    search.add_argument("--format", choices=["json", "csv"], default="json")
    search.add_argument("--output", help="Write output file. Use --format csv for pipeline-friendly event tables.")
    search.set_defaults(func=cmd_search_events)

    check = sub.add_parser("check-env", help="Check local runtime dependencies.")
    check.set_defaults(func=cmd_check_env)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
