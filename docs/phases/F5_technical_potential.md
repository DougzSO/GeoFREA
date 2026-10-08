# F5 technical_potential

Status: `in_progress`
Methodology items: M-F5-01 to M-F5-06, M-F4-07, V-02, V-03

## Contract

Requires: `candidates_<tech>__<scenario>.parquet` (F3; scenarios central, restrictive, permissive), `forcing.parquet`, `forcing_masked.parquet` and `members.yaml` (F4), technology registry, parameters, and for wind a power curve of `config/power_curves/`. Produces: `potential_<tech>__<scenario>.parquet` (`cell_id`, `member`, `P_MW`, `CF`, `E_MWh`) and `potential_aggregates_<tech>.parquet` (one row per land scenario and member; series *all present cells* and *like-for-like*). F6 and F7 read only the central scenario. The reference grid is not required.

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|
| M-F5-01 | `P_MW = eligible_area_km2 * LUF * PD` | `technical_potential/capacity.py:capacity_mw` | `test_technical_potential_functions.py::test_capacity_and_energy_closed_form`, `test_capacity_rejects_out_of_domain_inputs` | pass |
| M-F5-02 | Solar `CF0 = pvout / 24`; member `CF0 * delta_rsds * (1 + gamma * dT)` | `solar.py:solar_cf_reference`, `solar_cf_member` | `test_pvout_to_cf_units_only`, `test_solar_member_reference_factors_return_cf0_and_gamma_sign` | pass |
| M-F5-03 | Power-law `A_H`, linear `k_H` and `rho_H`; no extrapolation | `wind_profile.py:bracket_heights`, `weibull_scale_at_height`, `linear_at_height`, `resource_at_hub_height` | `test_power_law_*`, `test_linear_interpolation_midpoint_and_ends`, `test_hub_height_outside_the_data_heights_raises` | pass |
| M-F5-03 | Density folded into the scale; exact piecewise-linear Weibull integral; member and ratio form (D-F5-001, D-F5-002) | `weibull_cf.py:equivalent_scale`, `weibull_capacity_factor`, `wind_cf_reference`, `wind_cf_member`, `member_cf_ratio` | `test_weibull_cf_matches_numerical_integration_over_a_grid` (rtol 1e-6 against `quad`), `test_density_folds_into_the_scale`, `test_ratio_form_equals_direct_form` | pass |
| M-F5-03 | Power curve file, validation, hash, synthetic refused in production (D-F5-003) | `power_curve.py:PowerCurve`, `load_power_curve`, `curve_file_sha256`, `assert_curve_usable` | `test_power_curve_validation`, `test_loader_checks_the_stem_and_the_file`, `test_synthetic_curve_is_refused_in_production_only` | pass |
| M-F5-05 | `E = P_MW * CF * 8760` | `capacity.py:annual_energy_mwh`; constant `core/constants.py:HOURS_PER_YEAR` | `test_capacity_and_energy_closed_form` | pass (the value 8760 awaits the author's check in the diff, D-F5-009) |
| D-F5-008 | Rescale of the stored CF to another `gamma` or `eta_loss` | `rescale.py:rescale_cf_wind`, `rescale_cf_solar` | `test_rescale_*` | pass |
| V-02 | Weibull CF against integration; PVOUT units; power-law interpolation | see the rows above | `test_technical_potential_functions.py` | pass |

## Active implementation decisions

Recorded before any code (Douglas's verdicts of 2026-10-08 on `docs/_audit/2026-10_F5_design.md`, METHODOLOGY 7.1.0; section and decision numbers D1 to D16 refer to that report). No production value is entered by these decisions.

- **D-F5-001 — Integration of the Weibull (D1; M-F5-03, V-02).** The tabulated curve is read as piecewise linear and each segment is integrated in closed form with `scipy.special.gammainc`; no speed step exists. `scipy.integrate.quad` is only the reference of the test.
- **D-F5-002 — Test tolerance (D2; V-02).** Relative tolerance 1e-6 between the exact integral and `quad` (`quad` with `epsrel = 1e-10` and breakpoints at the curve nodes), written in the test and here.
- **D-F5-003 — IEC curve while OQ-005 is open (D3; M-F5-03, A-09).** The `PowerCurve` schema and its loader exist; no real curve file exists. One synthetic curve lives in `tests/fixtures/` with `synthetic: true` and is refused in a production run. Wind F5 for BRA, PRT and IND fails loudly until OQ-005 closes.
- **D-F5-004 — Curve provenance and class rule (D4; M-F5-03, OQ-005).** The curve file (`config/power_curves/<curve_id>.yaml`) carries the table and the U-05 provenance; `technologies.yaml` carries `power_curves` (class to curve id) and `iec_class_rule` (the class thresholds, D-F5-017), both `null` today. Rule: class per cell from the mean wind speed at hub height in the reference climate, fixed across members. The thresholds are OQ-005.
- **D-F5-005 — Three land scenarios at cell level (D5; M-F5-06, U-08).** One potential file per technology and scenario; F6 and F7 read only `__central`. The climate effect is computed inside each scenario, never across scenarios.
- **D-F5-006 — Masked cell-members (D6; M-F4-07, M-F5-06, M-F7-01).** The aggregates carry both series and the climate effect uses like-for-like. The F7 set is the central candidates present in every member of the core window; cells with a masked member form the class *climate-data-invalid*, reported with count and map, outside the ranking.
- **D-F5-007 — Wind mask removes the solar row too (D7).** The literal M-F4-07 rule is kept: a cell-member masked for `delta_wind` is absent for both technologies, counted per technology.
- **D-F5-008 — Uncertain parameters in F6 (D8; U-03).** The potential table keeps the five columns of M-F5-06 at the nominal `gamma` and `eta_loss`. F5 exports `rescale_cf_wind` and `rescale_cf_solar` for F6.
- **D-F5-009 — Constants (D9; M-F5-03, M-F5-05).** `rho0` and the hours per year go in `core/constants.py` with the standard cited. The author checks the numbers in the diff; none is entered by this record.
- **D-F5-010 — C2 hook (D10; M-F5-04).** No code for `L_C2` until OQ-007 passes; the table metadata states `c2_applied: false`.
- **D-F5-011 — Required parameters (D11; A-04).** `required_parameters` per technology in `technologies.yaml` (solar: `luf`, `power_density_mw_per_km2`, `gamma`; wind: `luf`, `power_density_mw_per_km2`, `eta_loss`, `hub_height_m`); `core/production.py::audit_parameters` refuses a missing or null one in a production run. `parameters.json` holds the five keys as U-05 objects with `value: null` and `status: pending_research` for BRA, PRT and IND (OQ-004, OQ-005, OQ-023).
- **D-F5-012 — Hub height (D12; M-F5-03).** `hub_height_m` moved from `technologies.yaml` to `parameters.json`. Domain: within the data heights 100 to 200 m; outside, F5 raises.
- **D-F5-013 — Fixture (D13; A-06).** The F5 test builds its own `forcing.parquet` (round known factors, one declared masked cell-member) from the ZZZ candidate cells. F4 on ZZZ (miniature CMIP6) goes to COMMAND 16. ZZZ test values in `parameters.json` are flagged `synthetic`: `luf` 0.5, `power_density_mw_per_km2` 10.0, `gamma` -0.005, `eta_loss` 0.9, `hub_height_m` 125.0.
- **D-F5-014 — Memory (D14; A-10).** A loop over members, one member in memory at a time; no `memory` section in `settings.yaml` for F5.
- **D-F5-015 — Maps (D15; A-07, A-08).** The first commit has tables only; a second commit adds the COG of `P_MW/cell_area` and `CF` at `m0` (central scenario) and the T-R1 figure.
- **D-F5-016 — Phase and DAG (D16; A-01, A-02).** `requires`: candidates per scenario, `forcing`, `forcing_masked`, `members`, registry, parameters. `produces`: the two potential artifacts. Staleness follows content (A-02).

## Known issues

- The registry names and comments of `technologies.yaml` were wrong (Weibull A and k swapped, no `m` suffix, solar layer `pvout`); corrected 2026-10-08 to the F3 candidate column names. F3 still hardcodes the layer names in `land_eligibility/pipeline.py::_required_resources`; F5 reads the registry.
- No `forcing.parquet` exists for ZZZ (D-F5-013).

## History

- 2026-10-08: design report and verdicts D1 to D16; METHODOLOGY 7.1.0; `parameters.json` and `technologies.yaml` extended; no phase code.
