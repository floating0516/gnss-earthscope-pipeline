# GA Downloader

Status: parked exploratory adapter.

This directory retains Geoscience Australia downloader helpers for prior Australian and southwest Pacific experiments. It is not part of the current production pipeline.

Entry points:

```text
fetch_ga_1hz.py
ga_common.py
select_ga_stations.py
```

Known missing pieces:

- no current production batch gate;
- no dedicated source preflight;
- no full normalized export parity gate in the mainline test suite;
- no documented promotion decision.

Use `docs/source_promotion_checklist.md` before moving this adapter into production.
