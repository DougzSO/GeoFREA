# F6 lcoe_modeling

Status: `in_progress`
Methodology items: M-F6-01 to M-F6-06, U-01 to U-04, V-02, V-03

## Contract

Requires: `potential_<tech>__central.parquet` (F5; `cell_id`, `member`, `P_MW`, `CF`, `E_MWh`), `candidates_<tech>__central.parquet` (F3; `dist_grid_km`, `dist_road_km`), `forcing.parquet` (F4; `dT` for the solar energy rescale) and `members.yaml` (F4), the technology registry, `parameters.json`, and `experiments.yaml` (`sampler`). Produces, per technology: `lcoe_summary_<tech>.parquet`, `design_matrix_<tech>.parquet`, `supply_curve_<tech>.parquet`; and the importable pure kernel `lcoe_modeling/kernel.py` (M-F6-05). F6 reads no F7 value: not `CF_min`, `q_ref`, `p_k` nor the F7 cell set (D-F6-001). Support phase `sample_size_convergence` (D-F6-004).

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|
| M-F6-01 | LCOE per cell and sample from CAPEX (plant, grid, substation, road), fixed and variable O&M, degradation and discounting; factored exactly so the variable O&M cancels and the numerator is one matrix product | `lcoe_modeling/kernel.py:lcoe_block`, `annuity_factor`, `energy_annuity_factor`, `capital_recovery_factor` | `test_lcoe_kernel.py::test_factored_kernel_equals_the_textbook_form_on_random_blocks`, `test_variable_om_adds_exactly_its_value_because_it_cancels_against_the_energy_denominator`, `test_lcoe_rises_with_capex_distance_and_discount_rate_and_falls_with_energy` | pass |
| V-02 | Closed forms: without degradation and with constant OPEX the LCOE is `(CAPEX * CRF + OPEX) / E`; `r = 0` gives `(CAPEX + n * OPEX) / (n * E)`; CRF and annuity against the explicit sum and the tabulated value | `kernel.py:lcoe_direct` (textbook reference), `capital_recovery_factor` | `test_without_degradation_and_with_constant_opex_the_lcoe_is_the_crf_form`, `test_at_a_zero_discount_rate_the_lcoe_is_total_cost_over_total_energy`, `test_crf_and_annuity_match_the_explicit_sum_and_the_tabulated_value`, `test_energy_annuity_matches_the_explicit_degraded_sum` | pass |
| D-F6-007 | Zero energy gives `+inf`, not an error; a negative or non-finite energy raises | `kernel.py:lcoe_block`, `_check_energy_not_negative` | `test_zero_energy_gives_plus_infinity_not_an_error_and_other_cells_stay_finite`, `test_energy_that_is_zero_only_at_one_sample_is_infinite_only_there`, `test_cells_with_negative_or_non_finite_values_and_negative_energy_raise` | pass |
| D-F6-010 | Integer lifetime; zero discount rate by the limit, with no division by zero; degradation in `[0, 1)` | `kernel.py:SampleInputs`, `annuity_factor`, `energy_annuity_factor` | `test_zero_discount_rate_is_the_limit_of_the_formula_with_no_division_by_zero`, `test_samples_outside_their_domain_raise` | pass |
| M-F6-05 | The kernel is a pure function importable by F7: arrays in, arrays out, no I/O | `kernel.py` (imports `numpy`, `dataclasses`, `collections` only) | `test_the_kernel_module_is_pure_it_imports_no_io_or_table_library` | pass |

## Active implementation decisions

Recorded before any code (Douglas's verdicts of 2026-10-09 on `docs/_audit/2026-10_F6_design.md`, METHODOLOGY 7.1.2; D1 to D16 refer to that report). No production value is entered by these decisions; the synthetic country carries test values only (D-F6-014).

- **D-F6-001 — F6 to F7 interface (D1; M-F6-05, M-F7-10).** Option (a): F7 recomputes the LCOE of each future by calling the pure F6 kernel, in two passes per member; nothing sample-level is persisted. F6 does not depend on `CF_min` (OQ-008), `q_ref` (OQ-020) or the F7 set.
- **D-F6-002 — Exact quantiles by cell block (D2; M-F6-04, A-10).** Per member, cells are processed in blocks with all samples of a block in memory, so p10, p50 and p90 are exact. The block size comes from `memory.max_batch_gb` (D-F6-005). Batching along samples (approximate quantiles) is not used. METHODOLOGY M-F6-04 states the cell axis since 7.1.2.
- **D-F6-003 — What the summaries cover (D3; M-F6-04).** Mean, variance, p10, p50 and p90 use only the Latin hypercube draws (`s >= 1`); the nominal vector `s0` is its own column (`lcoe_nominal`) and is not among them. Quantile: linear interpolation (Hyndman-Fan type 7); variance: `ddof = 1`. F7 takes its P90 over the same set (the wording of M-F7-03 awaits the author's authorization).
- **D-F6-004 — Sample size protocol as a support phase (D4; U-04, V-05).** `sample_size_convergence` is registered in the DAG and the manifest and calls the F6 and F7 kernels with sizes doubled from `sampler.initial_size`. Until F7 exists it uses a provisional MR (module marked `PROVISIONAL`, no `CF_min`: a cell is feasible when its energy is positive), to be replaced by F7's. Convergence: the Jaccard distance (1 - Jaccard) between the top-k sets of consecutive sizes is below `sampler.convergence_tolerance` (0.01, U-04); the adopted size is the larger of the first converged pair; a ceiling `sampler.max_size_for_convergence` stops a case that does not converge. The reading of "changes by less than 0.01" as a Jaccard distance is an interpretation the author may overrule. The phase needs `p_k` (OQ-021) and the ceiling; in the real countries it runs only once their parameters have ranges. The adopted size goes into this record when a real run converges.
- **D-F6-005 — Memory budget (D5; A-10).** `settings.yaml` `memory.max_batch_gb = 1`. Cells per block = floor(`max_batch_gb` * 1e9 / (4 * 8 * (N + 1))), where 4 counts the live cell-by-sample arrays at the peak; the value is logged.
- **D-F6-006 — Distributions (D6; M-F6-02, U-05).** Uniform when the source gives a minimum and a maximum; triangular, with the mode at the nominal, only when the source states a most likely value equal to the stored nominal. The choice is the `range.distribution` field of each parameter and country; no default is written in code.
- **D-F6-007 — Zero energy (D7; M-F6-01).** `E = 0` gives `LCOE = +inf`, not an error. The summaries keep the order statistics, mean and variance run over the finite draws, and `n_nonfinite` (count over the draws) is persisted. Such cells fall below `CF_min` and do not enter F7. A negative or non-finite energy, or a non-finite cost term, raises (A-09).
- **D-F6-008 — Currency and base year (D8; S-07).** Constant 2024 USD. A cost parameter carries `price_year` (U-05 entry); F6 raises, listing the parameter, if it is null or not 2024. No deflator code exists; a conversion from another year needs a sourced deflator, and its absence is OQ-054 (which also asks whether the stored discount rates are real).
- **D-F6-009 — Variable O&M name and unread keys (D9; M-F6-01).** The key is `opex_var_usd_per_mwh` (USD/MWh) in `parameters.json`, the schema and the ZZZ block, as M-F6-01 names it; a test checks that the name and the stored unit agree. `discount_rate_increment` is not read by F6 (M-F6-01 has no premium term; `discount_rate` is final).
- **D-F6-010 — Lifetime and degenerate rates (D10; M-F6-01).** The sampled `lifetime_years` is rounded to the nearest integer year in the design matrix, so the stored design is what the kernel used. `discount_rate = 0` is evaluated by the limit of the closed form (`CRF -> 1/n`, annuity `n`), never by a division by zero. Range validation refuses a negative discount rate, a degradation outside `[0, 1)` and a lifetime below one year.
- **D-F6-011 — Members (D11).** All 37 members of `members.yaml`, both windows; a cell-member masked by M-F4-07 has no F5 row and so no F6 row. F7 uses the core window only (D-F5-006).
- **D-F6-012 — Energy rescale in the CF registry (D12; D-F5-008).** The `CfModel` registered under `cf_model` names the sampled parameter that scales the energy (`sampled_parameter_key`) and returns the rescale as `factor = a_c + b_c * x_s` (`rescale_terms`), so F6 holds no technology name (A-04). The factor is 1 at the nominal value.
- **D-F6-013 — Outputs (D13; M-F6-06).** `design_matrix_<tech>.parquet` per technology (a run has two and the design depends on each technology's parameters); the supply curve at cell resolution per member (`member, rank, cell_id, lcoe_nominal, cum_P_GW, cum_E_TWh`), since F8 may not recompute (M-F8-01); statistics in float64.
- **D-F6-014 — Synthetic country (D14; A-06).** ZZZ carries the four new keys, a nonzero variable O&M, a range for every uncertain parameter and `price_year = 2024` on the cost parameters, all `synthetic: true` test values listed in the commit message for the author's check. BRA, PRT and IND carry the new keys with `value: null`, `status: pending_research` (OQ-001, OQ-019).
- **D-F6-015 — Phase and DAG (D15; A-01, A-02).** `lcoe_modeling` requires the F5 central potential tables, the F3 central candidates, `forcing` and `members`, and produces the three tables per technology. It is not in `run.target_phases` until the real parameters exist, like F5. The maps (`lcoe_maps`) are a later, separate phase.
- **D-F6-016 — Registry (D16; A-04).** `required_parameters` gains `opex_var_usd_per_mwh` (not uncertain). F5 reads only the keys it needs, so the new key does not make F5 refuse a country. `uncertain_parameters` already lists the F6 keys; `--production` refuses a missing value or range with the full list.

## Known issues

- OQ-001, OQ-016 to OQ-019, OQ-022 and the F5 blocks (OQ-004, OQ-005, OQ-023) keep F6 from a first real run; BRA, PRT and IND fail loudly listing every missing value, range and price year.
- OQ-017: the CAPEX source must say whether it includes grid connection (finding 4 of the design report); no value is entered.
- The F7 wording of M-F7-03 (P90 over the draws only) awaits the author's authorization.

## History

- 2026-10-09: design report, verdicts D1 to D16, METHODOLOGY 7.1.2, parameter keys and ZZZ test values; no phase code.
- 2026-10-09: commit A, the pure LCOE kernel with its V-02 closed-form tests.
