# CDDIS Research Line

CDDIS is retained as a global IGS high-rate research and comparison path. It is not part of the default EarthScope/GAGE plus GeoNet production mainline.

## Current Role

CDDIS can help answer questions that the production sources do not cover:

- whether a global event has enough public high-rate GNSS data to be worth further work;
- whether a South America or other non-EarthScope event can be reconstructed through IGS stations;
- whether PRIDE, quality, normalization, and PGD products behave consistently outside the production regions.

## Entry Points

Relevant local entry points include:

```text
tools/cddis_downloader/
scripts/workflows/run_cddis_event_1hz_pride_workflow.sh
scripts/workflows/run_cddis_event_batch_workflow.sh
scripts/availability/update_cddis_*.py
scripts/database/*cddis*.py
scripts/normalize/normalize_cddis_pride_kin_event.py
```

## Boundary

CDDIS outputs should be described as research or experimental unless the source is explicitly promoted. Do not mix CDDIS packages into the production normalized export by default.

Research runs should write to a source-specific output root or a clearly labeled temporary/report root. If a CDDIS event is promoted, it must satisfy the same normalized package contract:

```text
event.json
stations.csv
waveforms.csv.gz
provenance.json
```

## Promotion Requirements

Before CDDIS enters the production export, the project needs:

- a documented event and station authority;
- repeatable authentication and downloader setup;
- event and batch workflow documentation;
- compatibility with the shared quality and normalization contract;
- validator coverage for CDDIS event packages;
- offline or dry-run tests;
- clear licensing, citation, and provenance notes.

Use `docs/source_promotion_checklist.md` as the formal gate.
