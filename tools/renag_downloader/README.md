# RENAG Downloader

Status: parked exploratory adapter.

This directory retains RENAG listing and inventory helpers for France and Alps regional exploration. It is not part of the current production pipeline.

Entry points:

```text
list_renag_1hz.py
renag_common.py
renag_station_inventory_from_day.py
```

Known missing pieces:

- no complete production event workflow;
- no batch workflow;
- no source-specific preflight;
- no normalized export parity gate.

Use `docs/source_promotion_checklist.md` before moving this adapter into production.
