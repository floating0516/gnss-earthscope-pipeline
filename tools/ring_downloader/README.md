# RING Downloader

Status: parked exploratory adapter.

This directory retains RING/FReDNet high-rate GNSS discovery and download helpers. It is not part of the current production pipeline.

Entry points:

```text
fetch_ring_highrate.py
ring_common.py
ring_station_inventory.py
```

Known missing pieces:

- no current production batch mainline;
- no source-specific preflight;
- no shared normalized export contract test;
- no active operator runbook.

Use `docs/source_promotion_checklist.md` before moving this adapter into production.
