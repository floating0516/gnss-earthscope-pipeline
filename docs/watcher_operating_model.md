# USGS Watcher Operating Model

The USGS watcher is a discovery and triage layer. It should not automatically turn every newly seen earthquake into a download, PPP, normalization, or plotting run.

## Purpose

`gnss-eq watch-usgs` keeps a local state database of candidate USGS events from broad discovery regions. Those regions intentionally include events that are not processable by the current EarthScope or GeoNet production workflows.

`gnss-eq review-usgs` and the USGS triage report are the routing step. They decide whether an event should become an EarthScope batch, a GeoNet batch, a CDDIS research candidate, or a parked-source review item.

## Default Rule

Events are not automatically processed by default.

The normal sequence is:

```bash
gnss-eq watch-usgs --scope americas,nz
gnss-eq review-usgs --source all --format tsv
gnss-eq review-usgs --source all --format json
```

Only after review should an operator create or run production work:

```bash
scripts/workflows/current_pipeline.sh export-batch --event-id <usgs_event_id> --radius-km 200
scripts/workflows/current_pipeline.sh run-batch --csv data/batches/<batch>.csv --timeout 3600
scripts/workflows/run_geonet_batch_workflow.sh --help
```

## Routing Policy

EarthScope/GAGE is the production route for USGS events in supported United States and nearby EarthScope-covered Americas regions.

GeoNet is the production route for New Zealand, Kermadec, and related southwest Pacific events where the GeoNet pipeline has station and high-rate availability.

CDDIS is a research route. South America and other global events may be tagged as CDDIS research candidates, but they should not enter the production normalized export without an explicit promotion decision.

GA, RING, RENAG, and EPOS are parked adapters. A watcher result may mention them as a review hint, but they are not automatic production routes.

## Required Review Outputs

Each triaged watcher event should expose:

- `recommended_source`
- `routing_reason`
- `processable_by_earthscope`
- `processable_by_geonet`
- `research_candidate_cddis`
- `parked_source_candidate`

These fields make the distinction between discovery scope and processing scope explicit.

## Approval Boundary

Automatic processing may be added only behind an explicit opt-in flag or external scheduler approval. Any such mode must record the command, routing decision, source, thresholds, and operator policy in provenance.

Until that exists, `watch-usgs` and `review-usgs` remain discovery, alerting, and routing tools, not production execution tools.
