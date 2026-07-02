# Refine USGS Region Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop routing South America USGS events to EarthScope, while preserving the existing watcher discovery scope and existing watcher SQLite rows.

**Architecture:** Keep `usgs_watcher.region` as the broad query/discovery region (`americas`, `new_zealand`) to avoid a state DB migration. Add a triage-time processing route that maps each watched event to `earthscope`, `geonet`, or `unsupported_south_america` using event coordinates and USGS place text. Use that route in triage, auto-review source selection, priority/action decisions, and suggested commands.

**Tech Stack:** Python standard library, SQLite-backed watcher/availability DBs, `unittest`, existing `gnss_eq.cli`, `gnss_eq.usgs_triage`, and `gnss_eq.usgs_watcher`.

---

## File Structure

- Modify: `src/gnss_eq/usgs_triage.py`
  - Add deterministic processing-route helpers.
  - Keep `build_triage_report()` read-only.
  - Emit unsupported South America events in `--source all`, but not under `--source earthscope`.
- Modify: `src/gnss_eq/cli.py`
  - Make `watch-usgs --review-new-events --review-source auto` skip source refresh when all new events are unsupported South America.
  - Keep EarthScope and GeoNet review behavior unchanged for reviewable events.
- Modify: `tests/test_usgs_triage.py`
  - Cover South America route classification and triage output.
- Modify: `tests/test_cli.py`
  - Cover auto-review skipping unsupported South America and mixed-source behavior.
- Modify after code is green: `docs/data_sources.md`
  - Document that South America is discovered by watcher but not routed to EarthScope.

## Route Rules

Keep watcher broad regions as-is:

```text
watcher region=americas    -> broad discovery bucket
watcher region=new_zealand -> broad discovery bucket
```

Add triage processing source:

```text
new_zealand                                      -> geonet
americas + South America detector matches        -> unsupported_south_america
americas + no South America detector match       -> earthscope
other                                            -> unknown
```

South America detector:

```text
place contains one of:
  Argentina, Bolivia, Brazil, Chile, Colombia, Ecuador, Falkland,
  French Guiana, Guyana, Paraguay, Peru, Suriname, Uruguay, Venezuela

or coordinate fallback:
  -60 <= latitude <= 5 and -82 <= longitude <= -34
```

The place-text rule intentionally catches northern South America, where latitude alone overlaps Central America and the Caribbean.

## Task 1: Add Processing Route Tests

**Files:**
- Modify: `tests/test_usgs_triage.py`

- [x] **Step 1: Write failing tests for South America and EarthScope routing**

Append tests to `UsgsTriageTest`:

```python
    def test_south_america_event_is_not_routed_to_earthscope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            create_watcher_db(watcher_db)
            conn = sqlite3.connect(watcher_db)
            try:
                conn.execute(
                    """
                    INSERT INTO usgs_watcher_events(
                        event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
                        latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
                        detail_url, scope, region, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "us-chile",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:01:00Z",
                        "2026-01-01T00:01:00Z",
                        "2026-01-01T00:01:00Z",
                        -30.0,
                        -71.0,
                        20.0,
                        7.0,
                        "mww",
                        "near the coast of central Chile",
                        "M 7.0 - near the coast of central Chile",
                        "https://earthquake.usgs.gov/earthquakes/eventpage/us-chile",
                        "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-chile&format=geojson",
                        "americas,nz",
                        "americas",
                        "{}",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            report_all = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="all",
                earthscope_db=root / "missing-earthscope.sqlite",
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
                limit=10,
            )
            report_earthscope = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="earthscope",
                earthscope_db=root / "missing-earthscope.sqlite",
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
                limit=10,
            )

        south = [event for event in report_all["events"] if event["event_id"] == "us-chile"][0]
        self.assertEqual(south["source"], "unsupported_south_america")
        self.assertEqual(south["priority"], "SKIP")
        self.assertEqual(south["suggested_action"], "CHECK_CDDIS_OR_OTHER_SOURCE")
        self.assertNotIn("us-chile", [event["event_id"] for event in report_earthscope["events"]])
```

- [x] **Step 2: Write failing test for northern South America place-text detection**

Append:

```python
    def test_venezuela_place_text_is_south_america_even_at_caribbean_latitude(self):
        event = {
            "region": "americas",
            "latitude": 10.4351,
            "longitude": -68.4716,
            "place": "28 km SE of Yumare, Venezuela",
            "title": "M 7.5 - 28 km SE of Yumare, Venezuela",
        }

        self.assertEqual(usgs_triage.processing_source_for_event(event), "unsupported_south_america")
```

- [x] **Step 3: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_usgs_triage -v
```

Expected: FAIL because `processing_source_for_event()` does not exist and South America currently routes through `earthscope`.

## Task 2: Implement Triage-Time Processing Route

**Files:**
- Modify: `src/gnss_eq/usgs_triage.py`

- [x] **Step 1: Add constants and route helpers**

Add near `PRIORITY_RANK`:

```python
SOUTH_AMERICA_PLACE_TERMS = (
    "argentina",
    "bolivia",
    "brazil",
    "chile",
    "colombia",
    "ecuador",
    "falkland",
    "french guiana",
    "guyana",
    "paraguay",
    "peru",
    "suriname",
    "uruguay",
    "venezuela",
)


def _event_text(event: dict[str, Any]) -> str:
    return " ".join(str(event.get(key) or "") for key in ("place", "title")).lower()


def _event_float(event: dict[str, Any], key: str) -> float | None:
    try:
        return float(event.get(key))
    except (TypeError, ValueError):
        return None


def _is_south_america_event(event: dict[str, Any]) -> bool:
    text = _event_text(event)
    if any(term in text for term in SOUTH_AMERICA_PLACE_TERMS):
        return True
    latitude = _event_float(event, "latitude")
    longitude = _event_float(event, "longitude")
    if latitude is None or longitude is None:
        return False
    return -60.0 <= latitude <= 5.0 and -82.0 <= longitude <= -34.0


def processing_source_for_event(event: dict[str, Any]) -> str:
    region = str(event.get("region") or "")
    if region == "new_zealand":
        return "geonet"
    if region == "americas":
        if _is_south_america_event(event):
            return "unsupported_south_america"
        return "earthscope"
    return "unknown"
```

- [x] **Step 2: Route through the new helper**

Replace `_source_for_region()` usage in `_triage_event()`:

```python
    source = processing_source_for_event(event)
```

Keep `_source_for_region()` only if other callers still use it; otherwise remove it.

- [x] **Step 3: Make unsupported source low-risk and explicit**

Update `_priority()` signature and call site:

```python
def _priority(source: str, stations_200km: int, workflow_status: str, existing_data_status: str) -> str:
    if source == "unsupported_south_america":
        return "SKIP"
    if workflow_status == "WORKFLOW_EXISTS" or existing_data_status == "HAS_NORMALIZED":
        return "SKIP"
    if stations_200km >= 20:
        return "HIGH"
    if stations_200km >= 5:
        return "MEDIUM"
    return "LOW"
```

Call:

```python
    priority = _priority(source, stations_200km, workflow_status, existing_data_status)
```

- [x] **Step 4: Add unsupported suggested action and reason**

Update `_suggested_action()`:

```python
def _suggested_action(priority: str, workflow_status: str, availability: dict[str, Any] | None, db_available: bool, source: str) -> str:
    if source == "unsupported_south_america":
        return "CHECK_CDDIS_OR_OTHER_SOURCE"
    if workflow_status == "WORKFLOW_EXISTS":
        return "SKIP_WORKFLOW_EXISTS"
    if not db_available:
        return "CHECK_LOCAL_DB"
    if availability is None:
        return "UPDATE_AVAILABILITY_THEN_REVIEW"
    if priority in {"HIGH", "MEDIUM"}:
        return "REVIEW_PREPARE_BATCH"
    return "LOW_PRIORITY_REVIEW"
```

Call:

```python
    action = _suggested_action(priority, workflow_status, availability, db_available.get(source, False), source)
```

Update `_reason()`:

```python
    if action == "CHECK_CDDIS_OR_OTHER_SOURCE":
        return "South America is outside the current EarthScope processing coverage; review CDDIS or another global source"
```

- [x] **Step 5: Add CDDIS-oriented suggested commands**

Update `_suggested_commands()` before the final fallback:

```python
    if source == "unsupported_south_america":
        return [
            f"python3 scripts/database/import_usgs_events_to_cddis.py --min-magnitude 6.0",
            f"python3 scripts/availability/rebuild_cddis_event_station_candidates.py --event-id {event_id} --clear-event",
            "scripts/workflows/run_cddis_event_batch_workflow.sh --help",
        ]
```

- [x] **Step 6: Run route tests**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_usgs_triage -v
```

Expected: PASS.

## Task 3: Prevent Auto-Review From Refreshing EarthScope For Unsupported South America

**Files:**
- Modify: `src/gnss_eq/cli.py`
- Modify: `tests/test_cli.py`

- [x] **Step 1: Write failing CLI callback test**

Append to `CliMonitorCommandTest`:

```python
    def test_watch_usgs_review_new_events_skips_unsupported_south_america(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(cli.usgs_watcher, "run_watch_loop", return_value=0) as run_watch_loop:
                rc = cli.main(
                    [
                        "watch-usgs",
                        "--once",
                        "--review-new-events",
                        "--review-dry-run",
                        "--state-db",
                        str(root / "watcher.sqlite"),
                    ]
                )

            self.assertEqual(rc, 0)
            callback = run_watch_loop.call_args.kwargs["on_new_events"]

            with patch.object(cli, "_review_usgs", side_effect=AssertionError("review should not run")):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                    callback(
                        {
                            "events": [
                                {
                                    "event_id": "us-chile",
                                    "region": "americas",
                                    "latitude": -30.0,
                                    "longitude": -71.0,
                                    "place": "near the coast of central Chile",
                                }
                            ]
                        }
                    )

        self.assertIn("REVIEW\tSKIP", stderr.getvalue())
        self.assertIn("unsupported_south_america", stderr.getvalue())
```

- [x] **Step 2: Add helper to filter reviewable watch events**

In `src/gnss_eq/cli.py`, add:

```python
def _reviewable_watch_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    reviewable = []
    for event in events:
        if not isinstance(event, dict):
            continue
        source = usgs_triage.processing_source_for_event(event)
        if source in {"earthscope", "geonet"}:
            reviewable.append(event)
    return reviewable
```

- [x] **Step 3: Use reviewable events in auto-review**

At the start of `_run_watch_review_for_new_events()` after `events = ...`:

```python
    reviewable_events = _reviewable_watch_events(events)
    unsupported_ids = [
        str(event.get("event_id"))
        for event in events
        if isinstance(event, dict)
        and event.get("event_id")
        and usgs_triage.processing_source_for_event(event) == "unsupported_south_america"
    ]
    if events and not reviewable_events:
        print(f"REVIEW\tSKIP\tsource=unsupported_south_america\tevents={','.join(unsupported_ids)}", file=sys.stderr)
        return 0
```

Then build event IDs from `reviewable_events` rather than `events`:

```python
    event_ids = [str(event.get("event_id")) for event in reviewable_events if event.get("event_id")]
```

Pass `reviewable_events` into `_build_watch_review_args()` and `_prefetch_watch_review_metadata()`.

- [x] **Step 4: Update auto source selection to use processing route**

Replace `_review_source_for_new_events()` internals:

```python
    sources = {usgs_triage.processing_source_for_event(event) for event in events}
    has_earthscope = "earthscope" in sources
    has_geonet = "geonet" in sources
```

- [x] **Step 5: Run CLI tests**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_cli.CliMonitorCommandTest -v
```

Expected: PASS.

## Task 4: Verify Watcher Backward Compatibility

**Files:**
- No production file changes in this task.
- Do not migrate `data/live/usgs_watcher.sqlite`.

- [x] **Step 1: Keep watcher region test stable**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_usgs_watcher -v
```

Expected: PASS. `classify_region(34.0, -118.0)` should still return `americas`; watcher remains a discovery layer.

- [x] **Step 2: Run integrated targeted tests**

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_usgs_triage tests.test_cli tests.test_usgs_watcher -v
```

Expected: PASS.

- [x] **Step 3: Commit route behavior**

```bash
git add src/gnss_eq/usgs_triage.py src/gnss_eq/cli.py tests/test_usgs_triage.py tests/test_cli.py
git commit -m "fix: refine USGS processing source routing"
```

## Task 5: Document The Routing Semantics

**Files:**
- Modify: `docs/data_sources.md`

- [x] **Step 1: Add a short routing note**

Add to the USGS/watcher section:

```markdown
USGS watcher regions are broad discovery regions. `americas` is not equivalent to EarthScope processability: triage reclassifies South America events as unsupported by the current EarthScope workflow and suggests CDDIS or another global source review instead.
```

- [x] **Step 2: Run docs-neutral checks**

Run:

```bash
git diff --check
```

Expected: no output and exit 0.

- [x] **Step 3: Commit docs**

```bash
git add docs/data_sources.md
git commit -m "docs: clarify USGS routing regions"
```

## Final Verification

Run:

```bash
PYTHONPATH=src:. python3 -m unittest discover tests -v
bash -n scripts/workflows/*.sh
git diff --check
```

Expected:

```text
OK
```

for the unittest suite, no output from `bash -n`, and no output from `git diff --check`.

## Deployment Note

After merging or pushing, restart `GNSS:watch-usgs` so new auto-review routing is active. Existing watcher rows do not need migration because triage computes the processing route dynamically from each event.
