# Mainline Operating Model

## 1. Project Goal

This repository produces reproducible 1 Hz GNSS earthquake data products. The production path converts processable earthquake events into validated normalized event packages, then derives manifests, figures, reports, and run status summaries from those packages.

The mainline is:

```text
event discovery -> candidate stations -> 1 Hz download -> PRIDE PPP-AR -> kin quality
-> normalized event package -> manifest/report/figure -> rerunnable status ledger
```

The project should optimize the reliability and traceability of this path before expanding source coverage.

## 2. Production Sources

The production sources are:

- EarthScope/GAGE for the United States and nearby EarthScope-covered Americas events.
- GeoNet for New Zealand, Kermadec, and related southwest Pacific events.

Both production sources must end in the same normalized package contract:

```text
event.json
stations.csv
waveforms.csv.gz
provenance.json
```

Source-specific behavior belongs in event metadata and provenance, not in a separate final-data shape.

## 3. Research And Parked Sources

CDDIS is a research source. It can be used for experiments, fallback studies, and validation, but it is not the default production path.

GA/Geoscience Australia, RING/FReDNet, EPOS/GLASS, and RENAG are parked exploratory adapters. Keep their code available for reference, but do not route new production work through them unless a source-promotion decision is made.

Historical paper or collector data is read-only reference data. It can mark existing normalized coverage but must not replace current source-specific station availability as station-selection authority.

## 4. Final Product Definition

The final product is a normalized export root, currently:

```text
exports/normalized-ok-stations-us-nz/
```

Each completed event package must contain:

```text
<event-package>/
  event.json
  stations.csv
  waveforms.csv.gz
  provenance.json
```

Dataset-level indexes are derived products:

```text
manifest.tsv
event_summary.csv
file_inventory.tsv
mechanism_manifest.tsv
```

`runs/` is workflow history, not final collection truth. `data/` is local state and cache. `figure/` and `reports/` are derived outputs.

## 5. Event DONE

An event is DONE only when all of these are true:

- `event.json` exists and is valid JSON.
- `stations.csv` exists and contains at least one station row.
- `waveforms.csv.gz` exists and contains at least one waveform row.
- `provenance.json` exists and records source, workflow, quality, and normalization context.
- The event appears in `manifest.tsv`.
- The event appears in `event_summary.csv`.
- `file_inventory.tsv` references existing package files.
- A final figure exists, or the workflow records a machine-readable plot skip/failure reason.

Event DONE is based on the normalized package, not on a workflow exit code alone.

## 6. Batch DONE

A batch is DONE only when every row has a terminal status:

```text
OK
SKIPPED_EXISTING
CLASSIFIED_*
ABANDONED_*
```

The resumable statuses are:

```text
blank
FAIL
TIMEOUT
RETRY_*
UNKNOWN_REVIEW
```

A batch summary should explain the latest workflow directory, download status, observation status, PRIDE status, kin count, quality status, normalized status, plot status, final status, failure class, and suggested next action.

## 7. Dataset DONE

The dataset is DONE only when the normalized export validator passes:

```text
manifest event IDs == event_summary event IDs == complete package event IDs
```

The validator must also check:

- Required package files are present.
- JSON files parse.
- CSV and GZIP CSV files parse.
- `stations.csv` stations are represented in `waveforms.csv.gz`.
- `file_inventory.tsv` paths exist.
- There are no orphan package directories or index rows.

Dataset DONE should be reproducible from command-line validation, not manual directory counts.

## 8. Source Promotion Rules

A research or parked source can only be promoted after it has:

- A clear event authority.
- A clear station-selection authority.
- A downloader or preparation layer.
- A documented event or batch workflow.
- Quality and normalization outputs compatible with the production contract.
- Offline tests or repeatable dry-run checks.
- Authentication, licensing, and citation notes.

Until then, keep it marked as research or parked.

## 9. What Not To Optimize Yet

Do not prioritize these before export validation and status accounting are stable:

- Adding more data sources.
- Running more events only to increase counts.
- Reorganizing source-specific script paths.
- Building scientific reports on unvalidated packages.
- Turning `watch-usgs` into an unattended production processor.
- Rewriting shell workflows wholesale.

## 10. Standard Command Sequence

EarthScope mainline:

```bash
gnss-eq check-env
scripts/workflows/current_pipeline.sh paths
scripts/workflows/current_pipeline.sh update-availability
scripts/workflows/current_pipeline.sh rebuild-candidates
scripts/workflows/current_pipeline.sh list-events
scripts/workflows/current_pipeline.sh export-batch --event-id EVENT_ID --radius-km 200
scripts/workflows/current_pipeline.sh run-batch --csv data/batches/EVENT_ID-200km.csv
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz
```

GeoNet mainline:

```bash
python scripts/database/build_geonet_nz_database.py --help
python scripts/availability/update_geonet_event_highrate_availability.py --help
scripts/workflows/run_geonet_batch_workflow.sh --help
scripts/workflows/run_geonet_event_1hz_pride_workflow.sh --help
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz
```

Shared verification:

```bash
python -m unittest discover tests
python scripts/summaries/validate_normalized_export.py --root exports/normalized-ok-stations-us-nz --strict
```
