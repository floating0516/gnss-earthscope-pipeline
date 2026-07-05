# Agent Instructions

This repository is a GNSS earthquake processing pipeline. The production mainline is EarthScope/GAGE plus GeoNet into validated normalized event packages.

## Mainline

- Treat EarthScope/GAGE and GeoNet as production sources.
- Treat CDDIS as a research line.
- Treat GA, RING, RENAG, and EPOS as parked adapters.
- Treat `exports/normalized-ok-stations-us-nz/` as the final data-product boundary.
- Treat `runs/` as workflow history, not final collection truth.

## Files And Data

- Do not commit bulk local products from `data/`, `runs/`, `exports/`, or `figure/`.
- Do not commit credentials, EarthScope auth material, `.mcp.json`, `docker-home/`, or `external/`.
- Use `tempfile.TemporaryDirectory()` or equivalent isolated temp paths for tests.
- Do not write audit/report artifacts into the repository unless the task explicitly asks for persistent files.

## Script Compatibility

- Do not move or rename source-specific scripts casually.
- Preserve wrapper paths under `scripts/workflows/`, `scripts/availability/`, `scripts/database/`, `scripts/normalize/`, and `tools/`.
- If a physical reorganization is required, migrate one source at a time and keep compatibility wrappers at old paths.

## Testing

- For Python behavior changes, write or update tests first and run the targeted test before implementation.
- Run `python -m unittest discover tests` before reporting a first-batch implementation complete.
- For shell workflow changes, run `bash -n` on the edited shell scripts.
- Prefer offline fixtures over network calls.
- Do not require EarthScope auth, GeoNet network access, PRIDE binaries, or real local `data/` products for unit tests.

## Workflow Rules

- Use `scripts/workflows/current_pipeline.sh` for the current EarthScope mainline.
- Use GeoNet-specific workflow scripts for GeoNet processing.
- Do not make `gnss-eq watch-usgs` an automatic production processor by default.
- Validate normalized exports with `scripts/summaries/validate_normalized_export.py` once available.

## Source Promotion

A source can move from research or parked to production only when it has:

- A clear event authority.
- A clear station-selection authority.
- A downloader or preparation layer.
- A documented event or batch workflow.
- Quality and normalization outputs compatible with the shared package contract.
- Tests or repeatable dry-run checks.
- Authentication, licensing, and citation notes.
