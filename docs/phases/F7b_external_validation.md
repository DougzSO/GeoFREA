# F7b external_validation

Status: `in_progress`
Methodology items: M-F7b-01 to M-F7b-04, V-06, L-016

## Contract

Requires: F3 eligibility, F6 nominal LCOE, GEM trackers. Produces: validation tables for T-R9.

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|

## Active implementation decisions

- **D-F7b-001 (2026-10-07, from F5-1):** the plant inventory is `raw/gem/<ISO3>/gem_solar_wind_<ISO3>.parquet`, GEM snapshot 2026-08-09, pinned by sha256 (D-F1-026). It is validation-only (V-06): no parameter, threshold or configuration value may be derived from it, and the tests in `tests/unit/test_gem_trackers.py` enforce that no other module reads it. Use `status == operating` (and `start_year`) for M-F7b-01/02; plants inside the mainland polygon only (islands excluded by OQ-039). GEM replaces GPPD here.

Verdicts of 2026-10-09 on `docs/_audit/2026-10_F7_design.md` (METHODOLOGY 7.2.0; D18 to D22 refer to that report).

- **D-F7b-002 — Exclusion test (D18; M-F7b-01).** F3 persists no per-pixel `E1` to `E6`. F7b evaluates the pure eligibility engine of F3 (M-F3-01) at the pixels of the GEM units, on the aligned layers, central scenario, and reports per constraint the capacity-weighted mean excluded share (primary) and the capacity share in pixels with an excluded share above 0, at least 0.5 and equal to 1 (sensitivity). Units outside the country grid are counted.
- **D-F7b-003 — Enrichment (D19; M-F7b-02).** Eligible-area-weighted deciles of the nominal LCOE at `m0` over the candidates (the denominator is 10 percent by construction); units in non-candidate cells are reported apart with their capacity share. The lowest deciles reported are `external_validation.enrichment_lowest_deciles`; the vintage and location-accuracy rows are sensitivity rows whose filters are configuration with a reason.
- **D-F7b-004 — Published estimates (D20; M-F7b-03, OQ-057).** `config/published_potential.yaml` (source, year, definition, tier per entry), read only by F7b; empty today. The table puts the F5 central-scenario potential at `m0` (with the land interval) beside each entry and says whether the definitions match; no number is computed from the published values.
- **D-F7b-005 — V-06 by test (D21).** The module allow-list of the guard gains F7b only; no phase except `results_synthesis` requires an F7b artifact; a synthetic-country test runs F5 to F7 with and without the unit file and requires identical tables; the config scan stays.
- **D-F7b-006 — Synthetic inventory (D22; A-06).** `raw/gem/ZZZ/gem_solar_wind_ZZZ.parquet` and its snapshot record with `synthetic: true`, units placed so that each metric is a hand computation; a production run refuses a synthetic inventory.

## Known issues

- Published estimates for M-F7b-03 have no source yet (OQ-057).

## History

- 2026-10-09: verdicts D18 to D22 of the F7 design report recorded; no phase code.
