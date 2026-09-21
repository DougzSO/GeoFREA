# F1b data_quality_audit

Status: `built_pending_conformance`
Methodology items: M-F1b-01, M-F1b-02, V-04

## Contract

Requires: `acquisition_registry`. Produces: `audit_report` (per-layer summaries, anomalies). Blocks nothing.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F1b-01 | Expected resolutions and sanity ranges in configuration | Hardcoded in `audit.py` (`_EXPECTED_RESOLUTIONS_DEG`, `_RESOLUTION_TOLERANCE`, `_SOLAR_PVOUT_SANITY_RANGE`) | fail |
| M-F1b-01 | PVOUT unit reported as kWh/kWp/day | Labeled kWh/m²/day | fail |
| M-F1b-01 | Wind expected resolution matches GWA native grid | Expected 0.0083 degree; data at 0.0025 degree | fail |
| M-F1b-01 | Audit covers new layers (Weibull, air density, CMIP6, ERA5, GEM) | Not covered | fail |
| M-F1b-02 | Reports, never blocks | Verified: `data_quality_audit/audit.py:run_audit_phase` contains no `raise` statement; `AuditInputs` (schemas.py) defaults every field to `None`, degrading to "file not found" reporting rather than failing | pass |
| A-02 (vector clip path) | Invalid-geometry repair unconditional for every clip-path caller, not just suitability_criteria | `inspect_vector_layer()`'s clip path (`vector_inspection.py::_read_clipped_with_cache` -> `core/geo_utils.py::read_clipped_to_country`/`clip_vector_to_country`) now repairs before intersecting, same as every other caller — see docs/phases/core.md D-core-003. `VectorLayerInspection.geometry_repair` reports the count. | pass |

## Active implementation decisions

- **D-F1b-001 — Vector inspection distinguishes read_error from processing_error; WDPA repair is no longer audit-specific.** `inspect_vector_layer()` used to swallow both a file-open/clip failure and a downstream statistics failure into one `error` field, labeled "found (unreadable)" — indistinguishable without reading logs. Two try/except stages now set `error_type` (`"read_error"` | `"processing_error"`), and `VectorLayerSummary.status` mirrors that split in the audit report footer. Separately, the `[ERROR] found (unreadable)` PRT/protected case (`TopologyException: side location conflict`, confirmed pre-existing against unmodified commit `e1a57ed`, see History) was resolved as a side effect of moving invalid-geometry repair into the shared `clip_vector_to_country()` — not touched here directly. Real PRT run 2026-09-21: 14/184 WDPA features repaired (`Too few points in geometry component` x7, `Self-intersection` x5, `Ring Self-intersection` x2), `protected` now reports `[OK] found`.

## Known issues

- Land-cover inspection for BRA takes about 37 minutes; candidate for per-tile caching, no priority.
- `audit_report`'s artifact `schema_version` was bumped to `"2.0"` 2026-09-21 (main.py `_AUDIT_REPORT_SCHEMA_VERSION`) when `VectorLayerSummary.status`'s literal set changed — a manifest entry recorded under `"1.0"` now correctly raises `StaleManifestEntryError` on resume (METHODOLOGY A-02/A-09, docs/phases/core.md) instead of a raw Pydantic `ValidationError`. Any future breaking change to `AuditResult`'s shape needs the same bump.

## History

- WDPA "[ERROR] found (unreadable)" for PRT (`TopologyException: side location conflict`, first observed 2026-09-21 during a real E3 run) — confirmed pre-existing (reproduced against unmodified commit `e1a57ed` in a worktree, same file). Not a regression, not fixed directly; resolved as a side effect of D-F1b-001's shared-clip-path repair.
