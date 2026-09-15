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
| M-F1b-02 | Reports, never blocks | Standalone fallback with empty inputs | pass (pending audit) |

## Active implementation decisions

To be populated by the records migration task.

## Known issues

- Land-cover inspection for BRA takes about 37 minutes; candidate for per-tile caching, no priority.

## History

None.
