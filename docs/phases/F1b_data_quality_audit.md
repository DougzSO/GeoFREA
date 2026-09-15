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

## Active implementation decisions

None. The 2026-09 records audit (`docs/_audit/2026-09_records.md` section 4) classifies no still-valid `METHODOLOGY_REVISION` entry under `data_quality_audit`; audit-depth and summary-shape decisions from that period are recorded under `data_acquisition` (see `F1_data_acquisition.md` D-F1-002, D-F1-005).

## Known issues

- Land-cover inspection for BRA takes about 37 minutes; candidate for per-tile caching, no priority.

## History

None.
