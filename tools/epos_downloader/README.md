# EPOS Downloader

Status: parked exploratory adapter.

EPOS/GLASS is currently treated as a metadata discovery idea rather than a complete event-processing source. This directory exists only to document that status and prevent accidental production routing.

Known entry point:

```text
scripts/database/build_epos_usgs_highrate_europe_database.py
```

Known missing pieces:

- no complete downloader/preparation layer in `tools/epos_downloader/`;
- no production event workflow;
- no source-specific preflight;
- no normalized export contract test.

Use `docs/source_promotion_checklist.md` before moving this adapter into production.
