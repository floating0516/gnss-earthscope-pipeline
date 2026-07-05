from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "tools"
DOWNLOADER_TOOLS = TOOLS / "earthscope_downloader"
GEONET_TOOLS = TOOLS / "geonet_downloader"
PRIDE_TOOLS = TOOLS / "pride_processor"
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
DEFAULT_GEONET_DB = ROOT / "data" / "geonet" / "geonet_m6plus.sqlite"
EARTHSCOPE_METADATA_URL = "https://web-services.unavco.org/backoffice-geoserver-test/gnss/ows"
PROXY_ENV_VARS = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
REQUIRED_COMMANDS = ("bash", "python3", "timeout", "curl", "jq", "grep", "gunzip", "CRX2RNX", "pdp3", "es")
GEONET_REQUIRED_COMMANDS = ("bash", "python3", "timeout", "grep", "gunzip", "CRX2RNX", "pdp3")
REQUIRED_SCRIPTS = (
    ("run-batch script", SCRIPTS / "workflows" / "run_event_batch_workflow.sh"),
    ("run-event script", SCRIPTS / "workflows" / "run_event_1hz_pride_workflow.sh"),
    ("summary updater script", SCRIPTS / "workflows" / "update_workflow_summary_status.py"),
    ("batch summary builder script", SCRIPTS / "workflows" / "build_event_batch_summary.py"),
    ("downloader script", DOWNLOADER_TOOLS / "download_earthscope_default.sh"),
    ("rinex3 downloader script", DOWNLOADER_TOOLS / "download_earthscope_rinex3.sh"),
    ("PRIDE processor script", PRIDE_TOOLS / "process_event_window.sh"),
    ("PRIDE cleaner script", PRIDE_TOOLS / "cleanup_pride_workdir.sh"),
    ("quality script", SCRIPTS / "quality" / "compute_kin_quality.py"),
    ("normalizer script", SCRIPTS / "normalize" / "normalize_pride_kin_event.py"),
    ("final plotter script", SCRIPTS / "plotting" / "plot_completed_normalized_event.py"),
)
GEONET_REQUIRED_SCRIPTS = (
    ("GeoNet run-batch script", SCRIPTS / "workflows" / "run_geonet_batch_workflow.sh"),
    ("GeoNet run-event script", SCRIPTS / "workflows" / "run_geonet_event_1hz_pride_workflow.sh"),
    ("summary updater script", SCRIPTS / "workflows" / "update_workflow_summary_status.py"),
    ("GeoNet rolling downloader script", GEONET_TOOLS / "fetch_geonet_1hz.py"),
    ("GeoNet event high-rate downloader script", GEONET_TOOLS / "fetch_geonet_event_highrate.py"),
    ("GeoNet station selector script", GEONET_TOOLS / "select_geonet_stations.py"),
    ("PRIDE processor script", PRIDE_TOOLS / "process_event_window.sh"),
    ("PRIDE cleaner script", PRIDE_TOOLS / "cleanup_pride_workdir.sh"),
    ("quality script", SCRIPTS / "quality" / "compute_kin_quality.py"),
    ("final plotter script", SCRIPTS / "plotting" / "plot_completed_normalized_event.py"),
)


@dataclass(frozen=True)
class CheckResult:
    status: str
    name: str
    detail: str
    fatal: bool = True

    @property
    def failed(self) -> bool:
        return self.fatal and self.status in {"MISSING", "FAIL"}


def effective_env(environ: dict[str, str] | None = None, *, strip_proxy: bool = True) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    path_parts = []
    for key in ("EARTHSCOPE_ENV_BIN", "PRIDE_BIN_DIR", "LOCAL_BIN_DIR"):
        value = env.get(key)
        if value:
            path_parts.append(value)
    if path_parts:
        path_parts.append(env.get("PATH", ""))
        env["PATH"] = os.pathsep.join(path_parts)
    if strip_proxy:
        for key in PROXY_ENV_VARS:
            env.pop(key, None)
    return env


def proxy_info(environ: dict[str, str] | None = None) -> CheckResult:
    env = os.environ if environ is None else environ
    configured = [key for key in PROXY_ENV_VARS if env.get(key)]
    detail = "set: " + ",".join(configured) if configured else "not set"
    return CheckResult("INFO", "proxy variables", f"{detail}; workflow checks run with proxy variables stripped", fatal=False)


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (Path.cwd() / path).resolve(strict=False)


def command_checks(env: dict[str, str], commands: tuple[str, ...] = REQUIRED_COMMANDS) -> list[CheckResult]:
    results = []
    path = env.get("PATH")
    for command in commands:
        resolved = shutil.which(command, path=path)
        status = "OK" if resolved else "MISSING"
        results.append(CheckResult(status, f"command {command}", resolved or ""))
    return results


def script_checks(scripts: tuple[tuple[str, Path], ...] = REQUIRED_SCRIPTS) -> list[CheckResult]:
    results = []
    for name, path in scripts:
        if path.suffix == ".py" and path.is_file():
            results.append(CheckResult("OK", name, str(path)))
        elif path.is_file() and os.access(path, os.X_OK):
            results.append(CheckResult("OK", name, str(path)))
        elif path.exists():
            results.append(CheckResult("FAIL", name, f"not executable: {path}"))
        else:
            results.append(CheckResult("MISSING", name, str(path)))
    return results


def database_checks(db: str | Path | None, verified_files_db: str | Path | None = None) -> list[CheckResult]:
    results = []
    db_path = resolve_path(db or DEFAULT_DB)
    results.append(CheckResult("OK" if db_path.is_file() else "MISSING", "availability DB", str(db_path)))
    if verified_files_db:
        verified_path = resolve_path(verified_files_db)
        results.append(CheckResult("OK" if verified_path.is_file() else "MISSING", "verified files DB", str(verified_path)))
    return results


def first_nonempty_line(text: str, default: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), default)


def earthscope_auth_check(env: dict[str, str], timeout: float) -> tuple[CheckResult, str | None]:
    if shutil.which("es", path=env.get("PATH")) is None:
        return CheckResult("MISSING", "EarthScope auth", "es command not found; run: es login after installing EarthScope CLI"), None
    try:
        result = subprocess.run(
            ["es", "user", "get-access-token"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("FAIL", "EarthScope auth", "token check timed out; run: es login"), None
    if result.returncode != 0:
        return CheckResult("FAIL", "EarthScope auth", f"{first_nonempty_line(result.stderr, 'failed to obtain access token')}; run: es login"), None
    token = result.stdout.strip()
    if not token:
        return CheckResult("FAIL", "EarthScope auth", "empty access token; run: es login"), None
    return CheckResult("OK", "EarthScope auth", "access token available"), token


def connectivity_url() -> str:
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "gnss:metadata_search_data_availability",
        "outputFormat": "application/json",
        "viewparams": "start_date:2020-01-01;end_date:2020-01-02;sample_interval:<=1;data_type:rinex;",
    }
    return f"{EARTHSCOPE_METADATA_URL}?{urlencode(params)}"


def parse_http_code(stdout: str) -> int | None:
    for part in stdout.split():
        if part.startswith("http_code="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def earthscope_connectivity_check(env: dict[str, str], token: str | None, timeout: float) -> CheckResult:
    if not token:
        return CheckResult("FAIL", "EarthScope connectivity", "skipped because EarthScope auth failed")
    if shutil.which("curl", path=env.get("PATH")) is None:
        return CheckResult("MISSING", "EarthScope connectivity", "curl command not found")
    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "-sS",
                "--connect-timeout",
                str(timeout),
                "--max-time",
                str(timeout),
                "--header",
                f"Authorization: Bearer {token}",
                "-o",
                os.devnull,
                "-w",
                "http_code=%{http_code}",
                connectivity_url(),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 5,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("FAIL", "EarthScope connectivity", "curl check timed out in proxy-stripped workflow environment")
    http_code = parse_http_code(result.stdout)
    if result.returncode != 0:
        detail = first_nonempty_line(result.stderr, "unknown curl error")
        return CheckResult("FAIL", "EarthScope connectivity", f"curl failed in proxy-stripped workflow environment: {detail}")
    if http_code is None:
        return CheckResult("FAIL", "EarthScope connectivity", "curl did not report an HTTP status")
    if http_code in {401, 403}:
        return CheckResult("FAIL", "EarthScope authorization", f"HTTP {http_code}; run: es login or confirm EarthScope data access")
    if not 200 <= http_code < 400:
        return CheckResult("FAIL", "EarthScope connectivity", f"HTTP {http_code} from EarthScope metadata endpoint")
    return CheckResult("OK", "EarthScope connectivity", f"HTTP {http_code} from EarthScope metadata endpoint")


def run_preflight(
    *,
    db: str | Path | None = None,
    verified_files_db: str | Path | None = None,
    timeout: float = 30.0,
    include_connectivity: bool = True,
    include_database: bool = True,
    environ: dict[str, str] | None = None,
) -> tuple[list[CheckResult], int]:
    env = effective_env(environ, strip_proxy=True)
    results = [proxy_info(environ)]
    results.extend(command_checks(env, REQUIRED_COMMANDS))
    results.extend(script_checks(REQUIRED_SCRIPTS))
    if include_database:
        results.extend(database_checks(db, verified_files_db))
    auth_result, token = earthscope_auth_check(env, timeout)
    results.append(auth_result)
    if include_connectivity:
        results.append(earthscope_connectivity_check(env, token, timeout))
    failed = sum(1 for result in results if result.failed)
    if failed:
        results.append(CheckResult("PREFLIGHT_FAILED", "EarthScope preflight", f"{failed} blocking check(s); batch not started", fatal=False))
        return results, 2
    results.append(CheckResult("PREFLIGHT_OK", "EarthScope preflight", "all blocking checks passed", fatal=False))
    return results, 0


def run_geonet_preflight(
    *,
    db: str | Path | None = None,
    timeout: float = 30.0,
    include_database: bool = True,
    environ: dict[str, str] | None = None,
) -> tuple[list[CheckResult], int]:
    _ = timeout  # Reserved for future GeoNet connectivity checks.
    env = effective_env(environ, strip_proxy=True)
    results = [proxy_info(environ)]
    results.extend(command_checks(env, GEONET_REQUIRED_COMMANDS))
    results.extend(script_checks(GEONET_REQUIRED_SCRIPTS))
    if include_database:
        results.extend(database_checks(db or DEFAULT_GEONET_DB))
    failed = sum(1 for result in results if result.failed)
    if failed:
        results.append(CheckResult("PREFLIGHT_FAILED", "GeoNet preflight", f"{failed} blocking check(s); batch not started", fatal=False))
        return results, 2
    results.append(CheckResult("PREFLIGHT_OK", "GeoNet preflight", "all blocking checks passed", fatal=False))
    return results, 0


def write_tsv(results: list[CheckResult], output=None) -> None:
    if output is None:
        output = sys.stdout
    for result in results:
        print(f"{result.status}\t{result.name}\t{result.detail}", file=output)


def write_json(results: list[CheckResult], exit_code: int, output=None, path: Path | None = None) -> None:
    payload = {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "checks": [asdict(result) for result in results],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    if output is None:
        output = sys.stdout
    print(text, file=output, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run EarthScope workflow preflight checks.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Availability database path.")
    parser.add_argument("--verified-files-db", default="", help="Optional verified-files database path.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-check timeout in seconds.")
    parser.add_argument("--format", choices=["tsv", "json"], default="tsv")
    parser.add_argument("--no-connectivity", action="store_true", help="Skip the authenticated EarthScope curl connectivity check.")
    parser.add_argument("--no-database", action="store_true", help="Skip database path checks.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results, exit_code = run_preflight(
        db=args.db,
        verified_files_db=args.verified_files_db or None,
        timeout=args.timeout,
        include_connectivity=not args.no_connectivity,
        include_database=not args.no_database,
    )
    if args.format == "json":
        write_json(results, exit_code)
    else:
        write_tsv(results)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
