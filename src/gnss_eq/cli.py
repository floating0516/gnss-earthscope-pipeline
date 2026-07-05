from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gnss_eq import earthscope_event_import, monitor, preflight, usgs_triage, usgs_watcher


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "tools"
DOWNLOADER_TOOLS = TOOLS / "earthscope_downloader"
PRIDE_TOOLS = TOOLS / "pride_processor"
EARTHSCOPE_METADATA_URL = "https://web-services.unavco.org/backoffice-geoserver-test/gnss/ows"
DEFAULT_AVAILABILITY_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
CLASSIFY_BATCH_STATUS = SCRIPTS / "workflows" / "classify_batch_status.py"


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


def run_no_proxy_command(args: list[str], *, stdout: object | None = None) -> int:
    env = os.environ.copy()
    for key in PROXY_ENV_KEYS:
        env.pop(key, None)
    return subprocess.call(args, env=env, stdout=stdout)


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def load_script_module(path: Path, module_name: str) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def add_common_workflow_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hours", default="3")
    parser.add_argument("--interval", default="1")
    parser.add_argument("--max-stations", default="0")
    parser.add_argument("--process-jobs", type=positive_int, default=1)
    parser.add_argument("--run-root", default=str(ROOT / "runs"))
    parser.add_argument("--obs-root", default=str(ROOT / "data" / "obs"))
    parser.add_argument("--normalize-db", default=str(DEFAULT_AVAILABILITY_DB))
    parser.add_argument("--verified-files-db", default="")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--skip-process", action="store_true")
    parser.add_argument("--skip-plot", action="store_true")
    parser.add_argument("--post-seconds", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--cleanup-downloads", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup-pride-workdir", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup-obs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")


def cmd_run_event(args: argparse.Namespace) -> int:
    run_root = absolute_path(args.run_root)
    obs_root = absolute_path(args.obs_root)
    normalize_db = absolute_path(args.normalize_db)
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
        "--normalize-db",
        normalize_db,
        "--process-jobs",
        str(args.process_jobs),
    ]
    if args.stations:
        cmd.extend(["--stations", args.stations])
    if args.stations_file:
        cmd.extend(["--stations-file", args.stations_file])
    if int(args.max_stations) > 0:
        cmd.extend(["--max-stations", args.max_stations])
    if args.verified_files_db:
        cmd.extend(["--verified-files-db", absolute_path(args.verified_files_db)])
    for flag, enabled in [
        ("--skip-download", args.skip_download),
        ("--force-download", args.force_download),
        ("--allow-partial", args.allow_partial),
        ("--skip-process", args.skip_process),
        ("--skip-plot", args.skip_plot),
        ("--dry-run", args.dry_run),
    ]:
        if enabled:
            cmd.append(flag)
    if not args.cleanup_downloads:
        cmd.append("--no-cleanup-downloads")
    if not args.cleanup_pride_workdir:
        cmd.append("--no-cleanup-pride-workdir")
    if not args.cleanup_obs:
        cmd.append("--no-cleanup-obs")
    return run_command(cmd)


def cmd_run_batch(args: argparse.Namespace) -> int:
    run_root = absolute_path(args.run_root)
    obs_root = absolute_path(args.obs_root)
    normalize_db = absolute_path(args.normalize_db)
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
        "--normalize-db",
        normalize_db,
        "--process-jobs",
        str(args.process_jobs),
    ]
    if args.summary:
        cmd.extend(["--summary", args.summary])
    if int(args.max_stations) > 0:
        cmd.extend(["--max-stations", args.max_stations])
    if args.verified_files_db:
        cmd.extend(["--verified-files-db", absolute_path(args.verified_files_db)])
    for flag, enabled in [
        ("--skip-download", args.skip_download),
        ("--force-download", args.force_download),
        ("--no-allow-partial", args.no_allow_partial),
        ("--skip-process", args.skip_process),
        ("--skip-plot", args.skip_plot),
        ("--rerun-ok", args.rerun_ok),
        ("--dry-run", args.dry_run),
    ]:
        if enabled:
            cmd.append(flag)
    if not args.cleanup_downloads:
        cmd.append("--no-cleanup-downloads")
    if not args.cleanup_pride_workdir:
        cmd.append("--no-cleanup-pride-workdir")
    if not args.cleanup_obs:
        cmd.append("--no-cleanup-obs")
    return run_command(cmd)


def worklist_status(row: dict[str, str]) -> str:
    final_status = (row.get("final_status") or "").strip().upper()
    latest_workflow = (row.get("latest_workflow") or "").strip()
    batch_status = (row.get("status") or "").strip().upper()
    stations = (row.get("stations") or "").strip()

    if final_status in {"OK", "SKIPPED_EXISTING"}:
        return "DONE"
    if final_status.startswith("RETRY_"):
        return "READY_TO_RETRY"
    if final_status == "UNKNOWN_REVIEW" and not latest_workflow and stations and batch_status in {"", "PENDING", "READY", "TODO"}:
        return "READY_TO_RUN"
    return "NEEDS_REVIEW"


def prepare_worklist_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    prepared = []
    for row in rows:
        item = dict(row)
        status = worklist_status(item)
        item["worklist_status"] = status
        if status == "READY_TO_RUN":
            item["failure_class"] = ""
            item["next_action"] = "RUN_WORKFLOW"
        prepared.append(item)
    return prepared


def worklist_fieldnames(input_fieldnames: list[str]) -> list[str]:
    fields = list(input_fieldnames)
    for field in ["worklist_status", "final_status", "failure_class", "next_action", "latest_workflow"]:
        if field not in fields:
            fields.append(field)
    return fields


def write_worklist_tsv(rows: list[dict[str, str]], fieldnames: list[str], output: Path | None) -> None:
    handle = None
    try:
        if output is None:
            handle = sys.stdout
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            handle = output.open("w", newline="", encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    finally:
        if handle is not None and handle is not sys.stdout:
            handle.close()


def cmd_worklist(args: argparse.Namespace) -> int:
    classifier = load_script_module(CLASSIFY_BATCH_STATUS, "classify_batch_status")
    rows = classifier.classify_batch(Path(args.batch), Path(args.runs), Path(args.export_root))
    rows = prepare_worklist_rows(rows)
    with Path(args.batch).open(newline="", encoding="utf-8") as handle:
        input_fieldnames = csv.DictReader(handle).fieldnames or []
    fieldnames = worklist_fieldnames(input_fieldnames)

    output = Path(args.out) if args.out else None
    if args.format == "json":
        payload = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
        if output is None:
            print(payload, end="")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
    else:
        write_worklist_tsv(rows, fieldnames, output)
    return 0


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


def check_earthscope_auth() -> tuple[str, str]:
    login_hint = "run: es login"
    env = preflight.effective_env(strip_proxy=False)
    if shutil.which("es", path=env.get("PATH")) is None:
        return "MISSING", f"es command not found; {login_hint} after installing EarthScope CLI"
    try:
        result = subprocess.run(["es", "user", "get-access-token"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, env=env)
    except subprocess.TimeoutExpired:
        return "FAIL", f"token check timed out; {login_hint}"
    if result.returncode != 0:
        detail = next((line.strip() for line in result.stderr.splitlines() if line.strip()), "failed to obtain access token")
        return "FAIL", f"{detail}; {login_hint}"
    if not result.stdout.strip():
        return "FAIL", f"empty access token; {login_hint}"
    return "OK", "access token available"


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


def cmd_monitor(args: argparse.Namespace) -> int:
    report = monitor.build_monitor_report(
        source=args.source,
        limit=args.limit,
        earthscope_db=Path(absolute_path(args.earthscope_db)),
        earthscope_nonconus_db=Path(absolute_path(args.earthscope_nonconus_db)),
        geonet_db=Path(absolute_path(args.geonet_db)),
        runs_root=Path(absolute_path(args.runs_root)),
    )
    if args.format == "json":
        monitor.write_monitor_json(report)
    else:
        monitor.write_monitor_tsv(report)
    return 0


def cmd_triage_usgs(args: argparse.Namespace) -> int:
    report = usgs_triage.build_triage_report(
        state_db=Path(absolute_path(args.state_db)),
        source=args.source,
        limit=args.limit,
        min_magnitude=args.min_magnitude,
        earthscope_db=Path(absolute_path(args.earthscope_db)),
        earthscope_nonconus_db=Path(absolute_path(args.earthscope_nonconus_db)),
        geonet_db=Path(absolute_path(args.geonet_db)),
        runs_root=Path(absolute_path(args.runs_root)),
    )
    if args.format == "json":
        usgs_triage.write_triage_json(report)
    else:
        usgs_triage.write_triage_tsv(report)
    return 0


def cmd_import_usgs_earthscope_events(args: argparse.Namespace) -> int:
    report = earthscope_event_import.import_watched_events(
        state_db=Path(absolute_path(args.state_db)),
        target=args.target,
        event_ids=args.event_id,
        min_magnitude=args.min_magnitude,
        limit=args.limit,
        earthscope_db=Path(absolute_path(args.earthscope_db)),
        earthscope_nonconus_db=Path(absolute_path(args.earthscope_nonconus_db)),
        dry_run=args.dry_run,
        update_existing=args.update_existing,
    )
    if args.format == "json":
        earthscope_event_import.write_import_json(report)
    else:
        earthscope_event_import.write_import_tsv(report)
    return 0 if report.get("ok") else 1


def _run_review_step(cmd: list[str]) -> int:
    print(f"RUN\t{' '.join(shlex_quote(part) for part in cmd)}", file=sys.stderr)
    return run_no_proxy_command(cmd, stdout=sys.stderr)


def _earthscope_availability_update_cmd(db_path: Path, args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(SCRIPTS / "availability" / "update_earthscope_availability.py"),
        "--db",
        str(db_path),
        "--recent-days",
        str(args.recent_days),
        "--delay",
        str(args.delay),
        "--timeout",
        str(args.timeout),
        "--max-retries",
        str(args.max_retries),
        "--retry-delay",
        str(args.retry_delay),
    ]
    if args.force:
        cmd.append("--force")
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def _earthscope_rebuild_candidates_cmd(db_path: Path, metadata_root: Path, args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(SCRIPTS / "availability" / "rebuild_event_station_candidates.py"),
        "--db",
        str(db_path),
        "--metadata-root",
        str(metadata_root),
    ]
    for event_id in args.event_id or []:
        cmd.extend(["--event-id", event_id])
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def _geonet_rebuild_cmd(geonet_db: Path, args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(SCRIPTS / "database" / "build_geonet_nz_database.py"),
        "--db",
        str(geonet_db),
        "--min-magnitude",
        str(args.min_magnitude),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def _geonet_highrate_cmd(geonet_db: Path, args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        str(SCRIPTS / "availability" / "update_geonet_event_highrate_availability.py"),
        "--db",
        str(geonet_db),
        "--timeout",
        str(args.geonet_timeout),
    ]


def _review_usgs(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    state_db = Path(absolute_path(args.state_db))
    earthscope_db = Path(absolute_path(args.earthscope_db))
    earthscope_nonconus_db = Path(absolute_path(args.earthscope_nonconus_db))
    geonet_db = Path(absolute_path(args.geonet_db))
    runs_root = Path(absolute_path(args.runs_root))
    metadata_root = Path(absolute_path(args.earthscope_metadata_root))
    include_earthscope = args.source in {"all", "earthscope"}
    include_geonet = args.source in {"all", "geonet"}
    exit_code = 0

    if include_earthscope and not args.skip_refresh:
        for db_path in (earthscope_db, earthscope_nonconus_db):
            rc = _run_review_step(_earthscope_availability_update_cmd(db_path, args))
            if rc != 0:
                exit_code = rc
                break

    if exit_code == 0 and include_earthscope and not args.skip_import:
        import_report = earthscope_event_import.import_watched_events(
            state_db=state_db,
            target=args.target,
            event_ids=args.event_id,
            min_magnitude=args.min_magnitude,
            limit=args.limit,
            earthscope_db=earthscope_db,
            earthscope_nonconus_db=earthscope_nonconus_db,
            dry_run=args.dry_run,
            update_existing=args.update_existing,
        )
        if not import_report.get("ok"):
            exit_code = 1

    if exit_code == 0 and include_earthscope and not args.skip_rebuild_candidates:
        for db_path in (earthscope_db, earthscope_nonconus_db):
            rc = _run_review_step(_earthscope_rebuild_candidates_cmd(db_path, metadata_root, args))
            if rc != 0:
                exit_code = rc
                break

    if exit_code == 0 and include_geonet and args.refresh_geonet and not args.skip_refresh:
        exit_code = _run_review_step(_geonet_rebuild_cmd(geonet_db, args))
        if exit_code == 0 and not args.dry_run:
            exit_code = _run_review_step(_geonet_highrate_cmd(geonet_db, args))

    report = usgs_triage.build_triage_report(
        state_db=state_db,
        source=args.source,
        limit=args.limit,
        min_magnitude=args.min_magnitude,
        earthscope_db=earthscope_db,
        earthscope_nonconus_db=earthscope_nonconus_db,
        geonet_db=geonet_db,
        runs_root=runs_root,
    )
    return exit_code, report


def _write_review_report(args: argparse.Namespace, report: dict[str, object]) -> None:
    if args.format == "json":
        usgs_triage.write_triage_json(report)
    else:
        usgs_triage.write_triage_tsv(report)


def cmd_review_usgs(args: argparse.Namespace) -> int:
    exit_code, report = _review_usgs(args)
    _write_review_report(args, report)
    return exit_code


def _review_source_for_new_events(watch_args: argparse.Namespace, events: list[dict[str, object]]) -> tuple[str, bool]:
    if watch_args.review_source != "auto":
        return watch_args.review_source, watch_args.review_refresh_geonet
    sources = {usgs_triage.processing_source_for_event(event) for event in events}
    has_earthscope = "earthscope" in sources
    has_geonet = "geonet" in sources
    if has_earthscope and has_geonet:
        return "all", True
    if has_geonet:
        return "geonet", True
    return "earthscope", watch_args.review_refresh_geonet


def _reviewable_watch_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    reviewable = []
    for event in events:
        source = usgs_triage.processing_source_for_event(event)
        if source in {"earthscope", "geonet"}:
            reviewable.append(event)
    return reviewable


def _build_watch_review_args(watch_args: argparse.Namespace, events: list[dict[str, object]]) -> argparse.Namespace:
    event_ids = [str(event.get("event_id")) for event in events if event.get("event_id")]
    source, refresh_geonet = _review_source_for_new_events(watch_args, events)
    return argparse.Namespace(
        format=watch_args.review_format,
        source=source,
        state_db=watch_args.state_db,
        target=watch_args.review_target,
        event_id=event_ids,
        min_magnitude=watch_args.min_magnitude,
        limit=max(int(watch_args.review_limit), len(event_ids), 1),
        recent_days=watch_args.review_recent_days,
        earthscope_db=watch_args.review_earthscope_db,
        earthscope_nonconus_db=watch_args.review_earthscope_nonconus_db,
        earthscope_metadata_root=watch_args.review_earthscope_metadata_root,
        geonet_db=watch_args.review_geonet_db,
        runs_root=watch_args.review_runs_root,
        delay=watch_args.review_delay,
        timeout=watch_args.review_timeout,
        max_retries=watch_args.review_max_retries,
        retry_delay=watch_args.review_retry_delay,
        geonet_timeout=watch_args.review_geonet_timeout,
        force=watch_args.review_force,
        dry_run=watch_args.review_dry_run,
        update_existing=watch_args.review_update_existing,
        skip_refresh=watch_args.review_skip_refresh,
        skip_import=watch_args.review_skip_import,
        skip_rebuild_candidates=watch_args.review_skip_rebuild_candidates,
        refresh_geonet=refresh_geonet,
    )


def _prefetch_watch_review_metadata(review_args: argparse.Namespace, events: list[dict[str, object]]) -> None:
    if review_args.dry_run or review_args.skip_rebuild_candidates or review_args.source not in {"all", "earthscope"}:
        return
    token: str | None = None
    seen_days: set[str] = set()
    metadata_root = Path(absolute_path(review_args.earthscope_metadata_root))
    for event in events:
        if str(event.get("region") or "") != "americas":
            continue
        event_time = str(event.get("event_time_utc") or "")
        if not event_time:
            continue
        try:
            year, doy, _, _ = event_day(event_time)
            day_key = f"{year}-{doy}"
            if day_key in seen_days:
                continue
            seen_days.add(day_key)
            metadata_file = fetch_earthscope_metadata(event_time, metadata_root, token)
            print(f"REVIEW\tMETADATA\t{metadata_file}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"REVIEW\tMETADATA_WARN\t{event_time}\t{exc}", file=sys.stderr)


def _high_earthscope_events(report: dict[str, object]) -> list[dict[str, object]]:
    events = report.get("events", [])
    if not isinstance(events, list):
        return []
    return [
        event
        for event in events
        if isinstance(event, dict)
        and str(event.get("source") or "") == "earthscope"
        and str(event.get("priority") or "") == "HIGH"
        and str(event.get("suggested_action") or "") == "REVIEW_PREPARE_BATCH"
        and str(event.get("workflow_status") or "") != "WORKFLOW_EXISTS"
        and event.get("event_id")
    ]


def _current_pipeline_cmd(*parts: str) -> list[str]:
    return [str(SCRIPTS / "workflows" / "current_pipeline.sh"), *parts]


def _run_process_step(cmd: list[str]) -> int:
    print(f"PROCESS\tRUN\t{' '.join(shlex_quote(part) for part in cmd)}", file=sys.stderr)
    return run_no_proxy_command(cmd, stdout=sys.stderr)


def _process_high_earthscope_events(watch_args: argparse.Namespace, report: dict[str, object]) -> int:
    if watch_args.review_dry_run:
        print("PROCESS\tSKIP\treason=dry_run", file=sys.stderr)
        return 0
    if not watch_args.review_process_high:
        return 0

    for event in report.get("events", []):
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id") or "")
        if str(event.get("priority") or "") == "HIGH" and str(event.get("source") or "") == "geonet":
            print(f"PROCESS\tSKIP\tevent_id={event_id}\tsource=geonet\treason=unsupported", file=sys.stderr)

    exit_code = 0
    radius_km = int(watch_args.review_process_radius_km)
    for event in _high_earthscope_events(report):
        event_id = str(event["event_id"])
        batch_csv = f"data/batches/{event_id}-{radius_km}km.csv"
        print(f"PROCESS\tSTART\tevent_id={event_id}\tsource=earthscope\tradius_km={radius_km}", file=sys.stderr)
        export_cmd = _current_pipeline_cmd("export-batch", "--event-id", event_id, "--radius-km", str(radius_km))
        rc = _run_process_step(export_cmd)
        if rc != 0:
            print(f"PROCESS\tERROR\texit_code={rc}\tevent_id={event_id}\tstep=export-batch", file=sys.stderr)
            exit_code = rc
            break
        run_cmd = _current_pipeline_cmd(
            "run-batch",
            "--csv",
            batch_csv,
            "--timeout",
            str(watch_args.review_process_timeout),
            "--process-jobs",
            str(watch_args.review_process_jobs),
        )
        for flag, enabled in [
            ("--cleanup-pride-workdir", watch_args.review_process_cleanup_pride_workdir),
            ("--cleanup-obs", watch_args.review_process_cleanup_obs),
            ("--rerun-ok", watch_args.review_process_rerun_ok),
        ]:
            if enabled:
                run_cmd.append(flag)
        rc = _run_process_step(run_cmd)
        if rc != 0:
            print(f"PROCESS\tERROR\texit_code={rc}\tevent_id={event_id}\tstep=run-batch", file=sys.stderr)
            exit_code = rc
            break
        print(f"PROCESS\tDONE\tevent_id={event_id}\tcsv={batch_csv}", file=sys.stderr)
    return exit_code


def _run_watch_review_for_new_events(watch_args: argparse.Namespace, result: dict[str, object]) -> int:
    events = [event for event in result.get("events", []) if isinstance(event, dict)]
    reviewable_events = _reviewable_watch_events(events)
    unsupported_ids = [
        str(event.get("event_id"))
        for event in events
        if event.get("event_id") and usgs_triage.processing_source_for_event(event) == "unsupported_south_america"
    ]
    if events and not reviewable_events:
        print(f"REVIEW\tSKIP\tsource=unsupported_south_america\tevents={','.join(unsupported_ids)}", file=sys.stderr)
        return 0
    event_ids = [str(event.get("event_id")) for event in reviewable_events if event.get("event_id")]
    if not event_ids:
        return 0
    review_args = _build_watch_review_args(watch_args, reviewable_events)
    print(f"REVIEW\tSTART\tevents={','.join(event_ids)}\tsource={review_args.source}", file=sys.stderr)
    _prefetch_watch_review_metadata(review_args, reviewable_events)
    with redirect_stdout(sys.stderr):
        exit_code, report = _review_usgs(review_args)
        _write_review_report(review_args, report)
    status = "DONE" if exit_code == 0 else "ERROR"
    print(f"REVIEW\t{status}\texit_code={exit_code}\tevents={','.join(event_ids)}", file=sys.stderr)
    if exit_code:
        return int(exit_code) if watch_args.review_exit_on_error else 0
    process_exit_code = _process_high_earthscope_events(watch_args, report)
    if process_exit_code and not watch_args.review_exit_on_error:
        return 0
    return process_exit_code


def cmd_watch_usgs(args: argparse.Namespace) -> int:
    args.state_db = absolute_path(args.state_db)
    callback = None
    if args.review_new_events:
        callback = lambda result: _run_watch_review_for_new_events(args, result)
    return usgs_watcher.run_watch_loop(args, on_new_events=callback)


def cmd_check_env(_: argparse.Namespace) -> int:
    env = preflight.effective_env(strip_proxy=False)
    checks = preflight.command_checks(env)
    checks.extend(preflight.script_checks())
    failed = False
    for result in checks:
        print(f"{result.status}\t{result.name}\t{result.detail}")
        if result.failed:
            failed = True
    auth_status, auth_detail = check_earthscope_auth()
    print(f"{auth_status}\tEarthScope auth\t{auth_detail}")
    if auth_status != "OK":
        failed = True

    for key in ("PRIDE_BIN_DIR", "EARTHSCOPE_ENV_BIN", "LOCAL_BIN_DIR"):
        print(f"INFO\t{key}\t{os.environ.get(key) or '(not set)'}")
    return 1 if failed else 0


def cmd_preflight_earthscope(args: argparse.Namespace) -> int:
    results, exit_code = preflight.run_preflight(
        db=args.db,
        verified_files_db=args.verified_files_db or None,
        timeout=args.timeout,
        include_connectivity=not args.no_connectivity,
        include_database=not args.no_database,
    )
    write_preflight_report(args, results, exit_code)
    return exit_code


def cmd_preflight_geonet(args: argparse.Namespace) -> int:
    results, exit_code = preflight.run_geonet_preflight(
        db=args.db,
        timeout=args.timeout,
        include_database=not args.no_database,
    )
    write_preflight_report(args, results, exit_code)
    return exit_code


def write_preflight_report(args: argparse.Namespace, results: list[preflight.CheckResult], exit_code: int) -> None:
    json_out_value = getattr(args, "json_out", None)
    json_out = Path(json_out_value) if isinstance(json_out_value, (str, os.PathLike)) and json_out_value else None
    if json_out is not None:
        preflight.write_json(results, exit_code, path=json_out)
    if args.format == "json":
        if json_out is None:
            preflight.write_json(results, exit_code)
    else:
        preflight.write_tsv(results)


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

    worklist = sub.add_parser("worklist", help="Classify batch rows into ready, retry, review, and done worklists.")
    worklist.add_argument("--batch", required=True, help="Input batch CSV.")
    worklist.add_argument("--runs", default=str(ROOT / "runs"), help="Workflow runs root.")
    worklist.add_argument("--export-root", default=str(ROOT / "exports" / "normalized-ok-stations-us-nz"), help="Normalized export root.")
    worklist.add_argument("--format", choices=["tsv", "json"], default="tsv")
    worklist.add_argument("--out", help="Optional output path. Defaults to stdout.")
    worklist.set_defaults(func=cmd_worklist)

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

    preflight_cmd = sub.add_parser("preflight-earthscope", help="Run blocking EarthScope workflow readiness checks.")
    preflight_cmd.add_argument("--db", default=str(DEFAULT_AVAILABILITY_DB), help="Availability database path.")
    preflight_cmd.add_argument("--verified-files-db", default="", help="Optional verified-files database path.")
    preflight_cmd.add_argument("--timeout", type=float, default=30.0, help="Per-check timeout in seconds.")
    preflight_cmd.add_argument("--format", choices=["tsv", "json"], default="tsv")
    preflight_cmd.add_argument("--json-out", help="Optional path for a machine-readable JSON report.")
    preflight_cmd.add_argument("--no-connectivity", action="store_true", help="Skip authenticated EarthScope curl connectivity check.")
    preflight_cmd.add_argument("--no-database", action="store_true", help="Skip database path checks.")
    preflight_cmd.set_defaults(func=cmd_preflight_earthscope)

    geonet_preflight_cmd = sub.add_parser("preflight-geonet", help="Run blocking GeoNet workflow readiness checks.")
    geonet_preflight_cmd.add_argument("--db", default=str(preflight.DEFAULT_GEONET_DB), help="GeoNet availability database path.")
    geonet_preflight_cmd.add_argument("--timeout", type=float, default=30.0, help="Reserved per-check timeout in seconds.")
    geonet_preflight_cmd.add_argument("--format", choices=["tsv", "json"], default="tsv")
    geonet_preflight_cmd.add_argument("--json-out", help="Optional path for a machine-readable JSON report.")
    geonet_preflight_cmd.add_argument("--no-database", action="store_true", help="Skip database path checks.")
    geonet_preflight_cmd.set_defaults(func=cmd_preflight_geonet)

    monitor_cmd = sub.add_parser("monitor", help="Read-only status report for EarthScope and GeoNet workflow candidates.")
    monitor_cmd.add_argument("--format", choices=["tsv", "json"], default="tsv")
    monitor_cmd.add_argument("--source", choices=["all", "earthscope", "geonet"], default="all")
    monitor_cmd.add_argument("--limit", type=positive_int, default=20, help="Maximum candidate events per source.")
    monitor_cmd.add_argument("--earthscope-db", default=str(monitor.DEFAULT_EARTHSCOPE_DB), help="EarthScope USA availability database path.")
    monitor_cmd.add_argument(
        "--earthscope-nonconus-db",
        default=str(monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB),
        help="EarthScope non-CONUS availability database path.",
    )
    monitor_cmd.add_argument("--geonet-db", default=str(monitor.DEFAULT_GEONET_DB), help="GeoNet availability database path.")
    monitor_cmd.add_argument("--runs-root", default=str(monitor.DEFAULT_RUNS_ROOT), help="Workflow runs root to inspect for workflow-* outputs.")
    monitor_cmd.set_defaults(func=cmd_monitor)

    triage = sub.add_parser("triage-usgs", help="Read-only review of watched USGS events and suggested next commands.")
    triage.add_argument("--format", choices=["tsv", "json"], default="tsv")
    triage.add_argument("--source", choices=["all", "earthscope", "geonet"], default="all")
    triage.add_argument("--limit", type=positive_int, default=20, help="Maximum watched events to review.")
    triage.add_argument("--state-db", default=str(usgs_watcher.DEFAULT_STATE_DB), help="USGS watcher SQLite state database path.")
    triage.add_argument("--min-magnitude", type=float, default=6.0, help="Minimum watched event magnitude to review.")
    triage.add_argument("--earthscope-db", default=str(monitor.DEFAULT_EARTHSCOPE_DB), help="EarthScope USA availability database path.")
    triage.add_argument(
        "--earthscope-nonconus-db",
        default=str(monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB),
        help="EarthScope non-CONUS availability database path.",
    )
    triage.add_argument("--geonet-db", default=str(monitor.DEFAULT_GEONET_DB), help="GeoNet availability database path.")
    triage.add_argument("--runs-root", default=str(monitor.DEFAULT_RUNS_ROOT), help="Workflow runs root to inspect for workflow-* outputs.")
    triage.set_defaults(func=cmd_triage_usgs)

    import_events = sub.add_parser(
        "import-usgs-earthscope-events",
        help="Import watched Americas USGS events into EarthScope availability event tables.",
    )
    import_events.add_argument("--format", choices=["tsv", "json"], default="tsv")
    import_events.add_argument("--state-db", default=str(usgs_watcher.DEFAULT_STATE_DB), help="USGS watcher SQLite state database path.")
    import_events.add_argument("--target", choices=["auto", "usa", "nonconus"], default="auto")
    import_events.add_argument("--event-id", action="append", help="Import only this watched event id; can repeat.")
    import_events.add_argument("--min-magnitude", type=float, default=6.0)
    import_events.add_argument("--limit", type=positive_int, default=20)
    import_events.add_argument("--earthscope-db", default=str(monitor.DEFAULT_EARTHSCOPE_DB), help="EarthScope USA availability database path.")
    import_events.add_argument(
        "--earthscope-nonconus-db",
        default=str(monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB),
        help="EarthScope non-CONUS availability database path.",
    )
    import_events.add_argument("--dry-run", action="store_true")
    import_events.add_argument("--update-existing", action="store_true", help="Update rows that already exist instead of skipping them.")
    import_events.set_defaults(func=cmd_import_usgs_earthscope_events)

    review = sub.add_parser(
        "review-usgs",
        help="Safely refresh local availability state, import watched events, rebuild candidates, and triage USGS events.",
    )
    review.add_argument("--format", choices=["tsv", "json"], default="tsv")
    review.add_argument("--source", choices=["all", "earthscope", "geonet"], default="all")
    review.add_argument("--state-db", default=str(usgs_watcher.DEFAULT_STATE_DB), help="USGS watcher SQLite state database path.")
    review.add_argument("--target", choices=["auto", "usa", "nonconus"], default="auto")
    review.add_argument("--event-id", action="append", help="Limit EarthScope import/candidate rebuild to this watched event id; can repeat.")
    review.add_argument("--min-magnitude", type=float, default=6.0)
    review.add_argument("--limit", type=positive_int, default=20)
    review.add_argument("--recent-days", type=positive_int, default=7, help="EarthScope daily availability refresh window.")
    review.add_argument("--earthscope-db", default=str(monitor.DEFAULT_EARTHSCOPE_DB), help="EarthScope USA availability database path.")
    review.add_argument(
        "--earthscope-nonconus-db",
        default=str(monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB),
        help="EarthScope non-CONUS availability database path.",
    )
    review.add_argument("--earthscope-metadata-root", default=str(ROOT / "data" / "earthscope_metadata"), help="EarthScope metadata cache root.")
    review.add_argument("--geonet-db", default=str(monitor.DEFAULT_GEONET_DB), help="GeoNet availability database path.")
    review.add_argument("--runs-root", default=str(monitor.DEFAULT_RUNS_ROOT), help="Workflow runs root to inspect for workflow-* outputs.")
    review.add_argument("--delay", type=float, default=1.5)
    review.add_argument("--timeout", type=float, default=60.0)
    review.add_argument("--max-retries", type=int, default=3)
    review.add_argument("--retry-delay", type=float, default=30.0)
    review.add_argument("--geonet-timeout", type=positive_int, default=60)
    review.add_argument("--force", action="store_true")
    review.add_argument("--dry-run", action="store_true")
    review.add_argument("--update-existing", action="store_true", help="Update EarthScope event rows that already exist instead of skipping them.")
    review.add_argument("--skip-refresh", action="store_true", help="Skip availability refresh steps.")
    review.add_argument("--skip-import", action="store_true", help="Skip importing watched USGS events into EarthScope event tables.")
    review.add_argument("--skip-rebuild-candidates", action="store_true", help="Skip EarthScope candidate table rebuilds.")
    review.add_argument("--refresh-geonet", action="store_true", help="Also rebuild GeoNet event DB and event.highrate availability.")
    review.set_defaults(func=cmd_review_usgs)

    watch = sub.add_parser("watch-usgs", help="Continuously watch USGS for new Americas and New Zealand events.")
    watch.add_argument("--once", action="store_true", help="Poll once and exit instead of running a loop.")
    watch.add_argument("--interval", type=positive_int, default=300, help="Seconds between polling attempts.")
    watch.add_argument("--state-db", default=str(usgs_watcher.DEFAULT_STATE_DB), help="SQLite state database path.")
    watch.add_argument("--ignore-state", action="store_true", help="Use --lookback-minutes even when the state DB has a previous poll.")
    watch.add_argument("--scope", default="americas,nz", help="Comma-separated scope: americas, nz, or americas,nz.")
    watch.add_argument("--min-magnitude", type=float, default=6.0, help="Minimum USGS event magnitude.")
    watch.add_argument("--lookback-minutes", type=positive_int, default=1440, help="Cold-start query lookback window.")
    watch.add_argument("--overlap-minutes", type=positive_int, default=30, help="Overlap window after the first poll.")
    watch.add_argument("--limit", type=positive_int, default=2000, help="Maximum events returned per USGS bbox query.")
    watch.add_argument("--timeout", type=positive_int, default=30, help="USGS HTTP timeout in seconds.")
    watch.add_argument("--format", choices=["tsv", "jsonl"], default="tsv")
    watch.add_argument("--review-new-events", action="store_true", help="Run safe review-usgs automatically after newly recorded events.")
    watch.add_argument("--review-source", choices=["auto", "all", "earthscope", "geonet"], default="auto")
    watch.add_argument("--review-format", choices=["tsv", "json"], default="tsv")
    watch.add_argument("--review-limit", type=positive_int, default=20)
    watch.add_argument("--review-recent-days", type=positive_int, default=7)
    watch.add_argument("--review-target", choices=["auto", "usa", "nonconus"], default="auto")
    watch.add_argument("--review-earthscope-db", default=str(monitor.DEFAULT_EARTHSCOPE_DB), help="EarthScope USA availability database path for auto-review.")
    watch.add_argument(
        "--review-earthscope-nonconus-db",
        default=str(monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB),
        help="EarthScope non-CONUS availability database path for auto-review.",
    )
    watch.add_argument(
        "--review-earthscope-metadata-root",
        default=str(ROOT / "data" / "earthscope_metadata"),
        help="EarthScope metadata cache root for auto-review.",
    )
    watch.add_argument("--review-geonet-db", default=str(monitor.DEFAULT_GEONET_DB), help="GeoNet availability database path for auto-review.")
    watch.add_argument("--review-runs-root", default=str(monitor.DEFAULT_RUNS_ROOT), help="Workflow runs root for auto-review triage.")
    watch.add_argument("--review-delay", type=float, default=1.5)
    watch.add_argument("--review-timeout", type=float, default=60.0)
    watch.add_argument("--review-max-retries", type=int, default=3)
    watch.add_argument("--review-retry-delay", type=float, default=30.0)
    watch.add_argument("--review-geonet-timeout", type=positive_int, default=60)
    watch.add_argument("--review-force", action="store_true")
    watch.add_argument("--review-dry-run", action="store_true")
    watch.add_argument("--review-update-existing", action="store_true")
    watch.add_argument("--review-skip-refresh", action="store_true")
    watch.add_argument("--review-skip-import", action="store_true")
    watch.add_argument("--review-skip-rebuild-candidates", action="store_true")
    watch.add_argument("--review-refresh-geonet", action="store_true")
    watch.add_argument("--review-process-high", action="store_true", help="After auto-review, run the standard EarthScope workflow for HIGH events.")
    watch.add_argument("--review-process-radius-km", type=positive_int, default=200)
    watch.add_argument("--review-process-timeout", type=positive_int, default=3600)
    watch.add_argument("--review-process-jobs", type=positive_int, default=1)
    watch.add_argument("--review-process-cleanup-pride-workdir", action="store_true")
    watch.add_argument("--review-process-cleanup-obs", action="store_true")
    watch.add_argument("--review-process-rerun-ok", action="store_true")
    watch.add_argument("--review-exit-on-error", action="store_true", help="Stop watching when automatic review returns a non-zero exit code.")
    watch.set_defaults(func=cmd_watch_usgs)

    check = sub.add_parser("check-env", help="Check local runtime dependencies.")
    check.set_defaults(func=cmd_check_env)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
