# GNSS EarthScope GA Pipeline

This repository contains an isolated GNSS earthquake-processing pipeline for
USGS earthquake events, EarthScope 1 Hz GNSS data, and Geoscience Australia (GA)
high-rate GNSS workflows.

Large local data products are intentionally not committed. The repository keeps
source code, workflow scripts, documentation, and only a small set of selected
figures for quick visual reference.

## Example outputs

The full `data/`, `runs/`, `exports/`, and bulk `figure/` directories are local
pipeline products and are ignored by git. The selected figures below are copied
under `docs/images/` for README display only.

### Global station/event coverage

![Global GNSS station/event map](docs/images/world_map.png)

### Event with the most normalized stations

Petrolia, California, 2021-12-20 (`nc73666231`) has the largest normalized
station count in this workspace: 96 stations.

![Petrolia station map](docs/images/petrolia-20211220-california_station_map.png)

![Petrolia waveform record section](docs/images/petrolia-20211220-california_record_section.png)

It is intentionally separated from the older collection data in:

- `../openclaw-gnss-collector-agent/data/gnss_data`
- `../openclaw-gnss-collector-agent/data/velocity_data`
- `../openclaw-gnss-collector-agent/data/raw`
- `../openclaw-gnss-collector-agent/data/image_digitized`

Those older directories are historical data collections and must not be used as
the station-selection authority for this pipeline.

## Strict Station Rule

Station candidates must come from EarthScope same-day 1 Hz availability plus
EarthScope metadata coordinates.

The authoritative local database for this workspace is:

```text
data/earthscope_availability/earthscope_1hz.sqlite
```

The candidate table is:

```text
event_earthscope_station_candidates
```

Do not use local normalized inventory files under the older collector repo as a
substitute for EarthScope availability/metadata candidates.

## Directory Layout

```text
gnss-earthscope-pipeline/
├── README.md
├── data/
│   ├── earthscope_availability/
│   │   └── earthscope_1hz.sqlite
│   ├── earthscope_metadata/
│   ├── batches/
│   ├── obs/
│   └── summaries/
├── runs/
├── scripts/
│   ├── current_pipeline.sh
│   ├── run_event_batch_workflow.sh
│   ├── run_event_1hz_pride_workflow.sh
│   ├── update_earthscope_availability.py
│   └── compute_kin_quality.py
├── tools/
│   ├── earthscope_downloader/
│   │   ├── download_earthscope_default.sh
│   │   ├── download_earthscope_rinex3.sh
│   │   ├── download_earthscope_rinex2.sh
│   │   └── select_stations_by_radius.py
│   └── pride_processor/
│       ├── process_event_window.sh
│       └── plot_enu_svg.py
└── src/
    └── gnss_eq/
```

## Entry Point

Use only this wrapper for the current pipeline:

```bash
scripts/current_pipeline.sh paths
scripts/current_pipeline.sh list-events
scripts/current_pipeline.sh sync-existing-labels --reset
scripts/current_pipeline.sh rebuild-candidates
scripts/current_pipeline.sh refresh-verified-files --missing-only
scripts/current_pipeline.sh export-batch --event-id ci38457511 --radius-km 200
scripts/current_pipeline.sh run-batch --csv data/batches/ci38457511-200km.csv --timeout 3600
```

The wrapper fixes these paths:

- DB: `data/earthscope_availability/earthscope_1hz.sqlite`
- metadata cache: `data/earthscope_metadata`
- batch CSVs: `data/batches`
- downloaded/converted observations: `data/obs`
- workflow outputs: `runs`

PRIDE runs copy each input RINEX observation from `data/obs/<event-id>/` into
the per-station PRIDE working directory because `pdp3` runs in that station
directory and expects local inputs. For large 1 Hz events this duplicates the
observation files. Pass `--cleanup-pride-workdir` to remove those copied RINEX
files plus reproducible PRIDE products/intermediates after plots and quality
reports are written; `kin_*`, logs, summaries, plots, and manifests are kept.

By default the canonical `data/obs/<event-id>/` observation cache is also kept
so failed or exploratory runs can be repeated without downloading again. If the
event has been successfully solved and the `kin_*` files are the only required
result, pass `--cleanup-obs` as well. That removes the event's canonical
RINEX/observation files from `data/obs/<event-id>/` after successful kin
generation. A space-saving batch run normally uses both cleanup flags:

```bash
scripts/current_pipeline.sh run-batch --csv data/batches/example.csv --cleanup-pride-workdir --cleanup-obs
```

The collector, EarthScope downloader, and PRIDE wrapper code needed by the
current pipeline has been copied into this workspace. The workflow now calls the
local tools under:

- `tools/earthscope_downloader`
- `tools/pride_processor`

External programs such as `es`, `curl`, `jq`, `CRX2RNX`, and `pdp3` remain
runtime dependencies installed on the machine; they are not copied into this
workspace.

## Existing Normalized Data

Some USGS events already exist in the historical normalized GNSS dataset:

```text
../openclaw-gnss-collector-agent/data/gnss_data/normalized
```

Those files are used only as existing-data labels, not as the station-selection
authority for this EarthScope pipeline. Run:

```bash
scripts/current_pipeline.sh sync-existing-labels --reset
```

This writes `HAS_NORMALIZED` labels into `usgs_m6plus_events_usa` using
`event.json.usgs_event_id`. `list-events` displays the label. `export-batch` and
`run-batch` skip labeled events by default; pass `--include-existing` when a
deliberate rerun is needed.

## Phase 1 Baseline

The current Phase 1 baseline is documented in:

```text
docs/phase1-baseline-report.md
```

As of 2026-04-28, the candidate and verified-file tables are aligned:

- `event_earthscope_station_candidates`: 2822 rows
- `event_earthscope_station_verified_files`: 2822 rows
- verified status: all `VERIFIED`
- consistency failures: 0 rows without verification, 0 orphan verification rows,
  0 events where 200 km station count exceeds 300 km station count

## Phase 2 Run

The current Phase 2 real-run report is documented in:

```text
docs/phase2-run-report.md
```

As of 2026-04-28, two `NEW` events have completed the full pipeline in this
isolated workspace:

- `ak0138esnzr`: 3 stations, workflow OK, quality WARN because AB49 has 1 gap.
- `us7000kg30`: 7 stations, workflow OK, quality OK.
