# Source Promotion Checklist

A data source is production only after it passes this checklist. Until then it remains research or parked.

## 1. Authority

- Event authority is documented.
- Station authority is documented.
- Event IDs and aliases are stable enough for provenance and de-duplication.

## 2. Access

- Downloader or preparation script exists.
- Authentication requirements are documented.
- Licensing, citation, and use restrictions are documented.
- Network failure modes are clear enough to classify retries versus abandonment.

## 3. Workflow

- Single-event workflow exists or a production wrapper maps into the shared workflow.
- Batch workflow exists or the source has a documented reason for single-event only.
- Preflight checks source-specific prerequisites.
- Failure summaries include machine-readable stage, failure code, message, and next action.

## 4. Product Contract

Each completed event must produce:

```text
event.json
stations.csv
waveforms.csv.gz
provenance.json
```

The package must pass:

```bash
python scripts/summaries/validate_normalized_export.py --root <export-root> --event-id <event_id>
```

Dataset-level indexes must be rebuildable:

```bash
python scripts/normalize/rebuild_normalized_manifest.py --root <export-root> --write
python scripts/summaries/validate_normalized_export.py --root <export-root> --strict
```

## 5. Quality and Reports

- The source records quality thresholds and policy in provenance.
- WARN and FAIL semantics match the production quality contract.
- Dataset report and inclusion/exclusion report can read the source packages.
- PGD report either supports the source or documents why it is excluded.

## 6. Tests

- Unit tests use `tempfile` and do not depend on real large data.
- Offline smoke or dry-run coverage exists.
- Shell workflows pass `bash -n`.
- Full tests pass with:

```bash
PYTHONPATH=src python3 -m unittest discover tests
```

## 7. Decision

Promotion requires an explicit documentation update in `docs/data_sources.md` and `docs/mainline_operating_model.md`.

Do not promote a source only because one event succeeded manually.
