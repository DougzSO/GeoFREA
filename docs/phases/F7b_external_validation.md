# F7b external_validation

Status: `not_started`
Methodology items: M-F7b-01 to M-F7b-04, V-06, L-016

## Contract

Requires: F3 eligibility, F6 nominal LCOE, GEM trackers. Produces: validation tables for T-R9.

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|

## Active implementation decisions

- **D-F7b-001 (2026-10-07, from F5-1):** the plant inventory is `raw/gem/<ISO3>/gem_solar_wind_<ISO3>.parquet`, GEM snapshot 2026-08-09, pinned by sha256 (D-F1-026). It is validation-only (V-06): no parameter, threshold or configuration value may be derived from it, and the tests in `tests/unit/test_gem_trackers.py` enforce that no other module reads it. Use `status == operating` (and `start_year`) for M-F7b-01/02; plants inside the mainland polygon only (islands excluded by OQ-039). GEM replaces GPPD here.

## Known issues

None yet.

## History

None.
