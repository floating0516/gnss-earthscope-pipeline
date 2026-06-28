# Data source status

This document is the repository's current source-priority map. It describes which GNSS data sources are maintained as operational workflow lines, which ones are still research prototypes, and which ones are retained only as parked exploratory adapters.

## Current priorities

1. **Primary operational sources**: EarthScope/GAGE and GeoNet.
2. **Research source**: CDDIS.
3. **Parked exploratory sources**: GA/Geoscience Australia, RING/FReDNet, EPOS/GLASS, and RENAG.
4. **Read-only reference source**: historical normalized paper/collector data.

The current repository layout intentionally keeps source-specific scripts in their existing locations. Many workflows, tests, and CLI/MCP entry points depend on those paths, so this status document clarifies priority without moving files.

## Source status table

| Source | Status | Region / role | Workflow support | Auth / access | Primary entry points | Test coverage | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EarthScope/GAGE | Primary operational | United States and EarthScope-covered nearby Americas/non-CONUS events | Current main workflow, batch export/run, PRIDE, quality, normalization, plotting | EarthScope `es login` token | `scripts/workflows/current_pipeline.sh`, `scripts/workflows/run_event_batch_workflow.sh`, `scripts/workflows/run_event_1hz_pride_workflow.sh`, `tools/earthscope_downloader/`, `scripts/availability/update_earthscope_availability.py` | CLI, MCP, preflight, normalize, quality tests | Default maintained pipeline. Use this first for EarthScope-backed events. |
| GeoNet | Primary operational | New Zealand, Kermadec, and related southwest Pacific events | Dedicated event and batch workflows with shared PRIDE/quality/plotting | Public GeoNet HTTP/S3 access; no EarthScope token | `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`, `scripts/workflows/run_geonet_batch_workflow.sh`, `tools/geonet_downloader/`, `scripts/database/build_geonet_nz_database.py`, `scripts/availability/update_geonet_event_highrate_availability.py` | MCP coverage for `source="geonet"`; workflow code is source-specific | Main non-EarthScope operational line. |
| CDDIS | Research / experimental | Global IGS high-rate fallback and comparison source | Prototype event and batch workflows, downloader, preparation, availability, station metadata, normalization | NASA Earthdata/CDDIS access | `scripts/workflows/run_cddis_event_1hz_pride_workflow.sh`, `scripts/workflows/run_cddis_event_batch_workflow.sh`, `tools/cddis_downloader/`, `scripts/availability/update_cddis_*.py`, `scripts/database/*cddis*.py`, `scripts/normalize/normalize_cddis_pride_kin_event.py` | Extensive CDDIS-specific unit tests | Keep as research. Do not treat as stable mainline until event coverage, auth, and workflow reliability are validated. |
| GA / Geoscience Australia | Parked exploratory | Australia and southwest Pacific prototype adapter | Existing event/batch workflow and normalizer are retained | Public GA API / signed file locations | `scripts/workflows/run_ga_event_1hz_pride_workflow.sh`, `scripts/workflows/run_ga_batch_workflow.sh`, `tools/ga_downloader/`, `scripts/database/build_ga_au_database.py`, `scripts/normalize/normalize_ga_pride_kin_event.py` | No dedicated tests found | Keep for reference and prior outputs, but it is not a current research priority. |
| RING / FReDNet | Parked exploratory | Italy / Adriatic regional exploration | Event workflow and downloader exist; no current batch mainline | Provider-specific public access | `scripts/workflows/run_ring_event_1hz_pride_workflow.sh`, `tools/ring_downloader/`, `scripts/database/build_ring_usgs_database.py`, `scripts/availability/update_ring_highrate_availability.py` | No dedicated tests found | Retained as exploratory regional code. |
| EPOS / GLASS | Parked exploratory | European high-rate metadata discovery layer | Database/discovery scripts only; no complete event workflow | EPOS/GLASS provider-dependent access | `scripts/database/build_epos_usgs_highrate_europe_database.py` | No dedicated tests found | Treat as metadata discovery, not a runnable processing source. |
| RENAG | Parked exploratory | France/Alps regional trial | Inventory/listing and database trial scripts; no complete event workflow | Public RENAG access patterns | `tools/renag_downloader/`, `scripts/database/build_renag_usgs_database.py` | No dedicated tests found | Retained for future regional experiments. |
| Paper / historical normalized data | Read-only reference | Previously collected normalized events | Query/reference only; no downloader or workflow | Local historical data directory | `source="paper"` in `src/gnss_eq/mcp_server.py` | MCP tests cover source behavior | Use only to identify existing normalized data, not to process new events. |

## Operational boundaries

- EarthScope/GAGE and GeoNet are the maintained workflow lines to use for new processing work.
- CDDIS may be used for research experiments and validation, but it should be described as experimental in reports and workflow notes.
- GA, RING, EPOS, and RENAG code should remain available for reference, but new work should not default to those sources unless the research focus changes.
- `source="paper"` is a read-only comparison/reference source.

## Path compatibility policy

Do not move or rename existing source scripts casually. These paths are compatibility surfaces for workflows, tests, and CLI/MCP wrappers:

- `scripts/workflows/`
- `scripts/availability/`
- `scripts/database/`
- `scripts/normalize/`
- `tools/`

If physical reorganization becomes necessary later, migrate one source at a time and keep wrapper scripts at the old paths until all callers have moved.

## Adding or reviving a source

A source should not be promoted to primary operational status until it has:

1. A clear event/station selection authority.
2. A source-specific downloader or preparation layer.
3. A documented event or batch workflow.
4. Quality and normalization outputs compatible with the shared pipeline.
5. Tests or repeatable dry-run checks covering the source-specific path.
6. Clear documentation of authentication, licensing, and citation requirements.

Until those conditions are met, keep the source marked as research or parked.