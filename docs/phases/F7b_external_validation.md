# F7b external_validation

Status: `built_on_synthetic_country`
Methodology items: M-F7b-01 to M-F7b-04, V-06, L-016

## Contract

Requires: the aligned layers and siting layers (as F3), `land_eligibility` (the candidate tables), `lcoe_summary_<tech>` (nominal LCOE at `m0`), `potential_<tech>__<scenario>` (F5), the plant inventory `raw/gem/<ISO3>/gem_solar_wind_<ISO3>.parquet` and `config/published_potential.yaml`. Produces, under `external_validation[__<scale id>]/artifacts/`: `exclusion_shares.parquet` (M-F7b-01), `enrichment.parquet` (M-F7b-02), `published_comparison.parquet` (M-F7b-03) and `validation_units.parquet` (one row per operating unit, the basis of T-R9). No other phase requires any of them (V-06).

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|
| M-F7b-01, D-F7b-002 | Excluded share per constraint (E1 to E6 and combined) at the pixels of the operating units: capacity-weighted mean (primary), capacity share above 0, at least 0.5 and equal to 1; units outside the grid and in invalid pixels counted apart; the engine is F3's `eligible_fraction` on layers from `prepare_shared_layers`, nothing read from a stored per-pixel layer | `external_validation/exclusion.py:exclusion_rows`, `pipeline.py`, `land_eligibility/pipeline.py:prepare_shared_layers` | `test_external_validation.py::test_the_excluded_share_is_the_capacity_weighted_mean_and_counts_units_off_the_grid_and_in_invalid_pixels`, `test_zzz_end_to_end.py::test_f7b_excluded_shares_under_the_units_equal_the_hand_computation` | pass |
| M-F7b-02, D-F7b-003 | Eligible-area-weighted deciles of the nominal LCOE at `m0`; capacity and area by decile; enrichment ratio of the lowest `d` deciles from `external_validation.enrichment_lowest_deciles`; units in non-candidate cells reported apart; vintage and location-accuracy sets only when configured | `enrichment.py`, `inventory.py:row_sets` | `test_external_validation.py` (deciles, ratio, null cases, sets), `test_zzz_end_to_end.py::test_f7b_enrichment_equals_a_hand_recomputation_from_the_candidates_and_the_nominal_lcoe` | pass |
| M-F7b-03, D-F7b-004 | Published estimates beside F5's potential at `m0` (central, restrictive, permissive); nothing computed from the published number; empty and flagged while `config/published_potential.yaml` has no entry (OQ-057) | `published.py` | `test_the_comparison_puts_the_estimate_beside_f5_at_the_reference_member_and_computes_nothing_from_it`, `test_f7b_published_comparison_is_empty_and_flagged_while_there_are_no_entries` | pass (no entry yet) |
| M-F7b-04 | Interpretation (plausibility evidence, not accuracy) in the provenance of every table | `pipeline.py` | `test_f7b_published_comparison_is_empty_and_flagged_while_there_are_no_entries` | pass |
| V-06, D-F7b-005 | Only `external_validation/inventory.py` reads the inventory; F7b is a sink of the graph; F5, F6 and F7 tables are identical with the inventory absent; the config scan covers `published_potential.yaml` | `inventory.py` | `test_gem_trackers.py::test_v06_no_other_module_imports_the_tracker`, `test_v06_no_plant_derived_value_in_config`, `test_main.py::test_external_validation_is_a_sink_whose_tables_no_other_phase_requires`, `test_zzz_end_to_end.py::test_v06_f5_to_f7_do_not_change_when_the_plant_inventory_is_absent` | pass |
| D-F7b-006, A-06 | Synthetic inventory in ZZZ with `synthetic: true`; a production run refuses it | `scripts/generate_zzz_fixture.py:gen_gem_inventory`, `inventory.py:load_inventory` | `test_a_synthetic_inventory_is_refused_in_a_production_run_and_accepted_otherwise` | pass |
| V-07, A-08 | Runs at 0.05 and 0.1 degree with the same code; the pixel-level exclusion table does not change with the cell size | `core/scale.py`, `pipeline.py` | `test_f7b_runs_at_the_coarse_scale_and_the_pixel_level_exclusions_do_not_change` | pass |

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
- Nothing in F7b runs on a real country until the real plant inventory is acquired (`scripts/acquire_gem_trackers.py`) and F3 to F6 have run on real values.
- The ZZZ pixels are uniform in slope and almost so in the other layers: the hand computations exercise the mechanism, not the spatial agreement of the exclusion set with real plants.

## History

- 2026-10-09: verdicts D18 to D22 of the F7 design report recorded; no phase code.
- 2026-10-09: F7b built on the synthetic country: exclusion shares at the plant pixels through F3's `prepare_shared_layers` and eligibility engine, deciles and enrichment, the published-estimate table (empty), the unit table, the synthetic ZZZ inventory and the V-06 guards.
