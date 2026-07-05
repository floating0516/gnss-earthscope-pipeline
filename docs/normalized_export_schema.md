# Normalized Export Schema

This document defines the current normalized event package contract.

Every completed event package contains:

```text
event.json
stations.csv
waveforms.csv.gz
provenance.json
```

`validate_normalized_export.py` enforces this schema for single-event validation and strict dataset validation:

```bash
python scripts/summaries/validate_normalized_export.py --root <export-root> --event-id <event_id>
python scripts/summaries/validate_normalized_export.py --root <export-root> --strict
```

Plain dataset scans without `--strict` remain compatible with legacy packages so existing exports can still be inventoried during migration.

## event.json

Schema version:

```json
{
  "schema_version": "normalized-event/v1"
}
```

Required v1 fields:

```text
event_id
source
event_authority
station_authority
event_time
latitude
longitude
depth_km
magnitude
magnitude_type
region
station_count
waveform_rows
```

Rules:

- `event_id`, `source`, `event_authority`, `station_authority`, `event_time`, and `region` are non-empty strings.
- `latitude`, `longitude`, `depth_km`, and `magnitude` are numbers or null.
- `magnitude_type` is a string or null.
- `station_count` and `waveform_rows` are non-negative integers and must match `stations.csv` and `waveforms.csv.gz`.

Legacy compatibility fields such as `date`, `stations`, `network`, `country`, `event_grade`, and `normalization` may remain present for older reports and plotting code.

## provenance.json

Schema version:

```json
{
  "schema_version": "provenance/v1"
}
```

Required top-level fields:

```text
event_id
station_count
waveform_rows
workflow
source
processing
quality
inputs
outputs
```

Required `workflow` fields:

```text
name
script
started_at
completed_at
git_commit
command
```

`git_commit` and `command` may be empty strings when unavailable. The other workflow fields must be non-empty strings.

Required `source` fields:

```text
name
event_authority
station_authority
downloader
```

Required `processing` fields:

```text
pride_processor
pdp3
crx2rnx
window_hours
sampling_hz
```

Required `quality` fields:

```text
quality_json
thresholds
summary_status
```

Rules:

- `quality.thresholds` is an object copied from `kin-quality/v1` output when available.
- `inputs` and `outputs` are lists.
- `station_count` and `waveform_rows` must match the package files.

## Source Values

Current source values are:

```text
earthscope
geonet
cddis
```

Other adapters remain research or parked unless explicitly promoted through `docs/source_promotion_checklist.md`.
