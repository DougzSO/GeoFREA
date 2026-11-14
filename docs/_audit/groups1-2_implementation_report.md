# Groups 1 and 2: implementation report

Branch `stage-r/groups1-2`, from `main` at `3b29288`. Written 2026-10-16; committed afterwards in three commits (code and tests; METHODOLOGY, parameters and curve; records and .tex).

Inputs: `docs/phases/F5/audit_groups1-2.md`, `docs/METHODOLOGY.md` 14.1.1, `config/parameters.json`, `docs/OPEN_QUESTIONS.md`, the three .tex files. The bibliography file named in the command, `docs/thesis/references_stage_r.bib`, does not exist in the repository; it was not needed here.

## 1. What changed

### METHODOLOGY 14.2.0 (MINOR, as the command asked)

The changelog row lists only the four approved changes: (a) one turbine and the class flag, (b) the density rule, (c) scenario-coupled LUF and PD, (d) `t_ref = 2026` with the IRENA 2024 cohort, CAPEX on `[P5, 2 mean - P5]`, fixed O&M as a fraction, variable O&M zero, lifetime U[25, 30] centred on 30. Items edited: M-F5-01, M-F5-03, M-F5-06, new M-F6-07, U-03, U-05, Section 9 (config path). PV model and the meaning of `eta_loss` are untouched.

Note for the author: by the change protocol of Section 0, items (a) to (c) change a result definition, which is a MAJOR bump. The command said "nova versão menor", so 14.2.0 was used. Changing it to 15.0.0 is one edit.

### Code

| File | Change |
|---|---|
| `src/geofrea/core/config_schemas.py` | `IecClassBound`, `power_curves`, `iec_class_rule` removed; `ClassFlagRule` and `power_curve` (one curve id) added. |
| `src/geofrea/core/schemas.py` | `ScenarioValues` and `VerifiedValue.scenario_values` (central must equal `value`); `discount_rate` may be null; optional `commissioning_year`. |
| `src/geofrea/technical_potential/power_curve.py` | Loader reads `.csv` (provenance in `#` header lines) and `.yaml`. First node may have non-zero power (it is the cut-in); no zero-first-node rule; `cut_in_ms`, `reference_density_kg_m3`, licence, URL, commit fields. Zero below cut-in and above cut-out by rule, linear only inside; no node is added. |
| `src/geofrea/technical_potential/weibull_cf.py` | `member_air_density` (`rho_ref T*/(T*+dT)`); `wind_cf_member` takes `rho_ref`, `dT`, `rho0`, `T*`; `A_eq,m = delta_wind A_H (rho_m/rho0)^(1/3)`, no second rescale. |
| `src/geofrea/technical_potential/iec_class.py` | Class rule replaced by `exceeds_class` (strictly above the limit). |
| `src/geofrea/technical_potential/cf_models.py` | One curve per technology; `rho0` from the curve (constant 1.225 when the file has none); flag from the 100 m layer. |
| `src/geofrea/technical_potential/pipeline.py` | LUF and PD per land scenario (`scenario_values`); curve resolved from `config/turbines/`; new `class_flag_<tech>__<scenario>.parquet`; scenario parameters, `T*` and `rho0` recorded in the table provenance. |
| `src/geofrea/technical_potential/table_schemas.py` | `ClassFlagRow`. |
| `main.py` | `POWER_CURVES_DIR` points to `config/turbines`. The flag tables are not registered as phase artifacts (the orchestrator requires a declared `produces` set per technology, and only wind has them); their paths are in the `technical_potential` summary JSON. |
| `config/technologies.yaml` | Wind: `power_curve: iea_3.4_130`, `class_flag` (III, 7.5 m/s, 100 m layer). |
| `config/turbines/iea_3.4_130.csv` | New curve, see 2. |
| `config/parameters.json` | Groups 1 and 2, see 3. |
| `docs/LIMITATIONS.md` | L-027 to L-030, Tier 3 rows L-204 to L-207, L-203 marked RETIRED (its proxy was replaced). |

`T* = 288.15 K` is read from `geofrea.core.constants.ISA_T0_K` (already there), like `rho0` was, not duplicated in `parameters.json`. This departs from the command's list, which names T* among the `parameters.json` entries; it avoids two sources of truth. Say if you want a key.

### Tests

New or rewritten: `test_technical_potential_functions.py` (density at dT 0 and 3 K by hand, CF with and without correction against the independent quadrature, `eta_loss` once, first node non-zero with no ramp, the real curve against quadrature, CSV loader), `test_technical_potential_pipeline.py` (flag, LUF and PD per scenario, `eta_loss` once, fail-loud on a copy with the F5 values removed, the real countries resolve with a production-grade curve), new `test_groups12_parameters.py` (values against the .tex tables, mean of 10,000 CAPEX draws within 1 percent of the IRENA mean in all six cases, no proxy, no discount rate, loader audit). Updated for the new real parameters: `test_f6_parameters.py`, `test_lcoe_pipeline.py`, `test_parameter_contract.py`, `test_robustness_pipeline.py`, the ZZZ run scripts (`power_curve` key).

## 2. Turbine curve (step 3)

`config/turbines/iea_3.4_130.csv`: 50 nodes, 3.0 to 25.0 m/s, "Rotor electrical power (W)" divided by 1000 from `performance/performance_ccblade.dat`. Source repository `IEAWindSystems/IEA-3.4-130-RWT` (formerly `IEAWindTask37`), commit `aacff396f46b35f7104d83be095f859684013405` (2026-09-15), Apache-2.0. The table is identical to the one read in the audit.

- First node 51.6 kW at 3.0 m/s (non-zero), cut-in 3, cut-out 25. `rated_power_kw` in the file is the largest node, 3370.105 kW (nameplate 3370.000; +0.003 percent), so the normalized curve stays at or below 1.
- Air density: the windIO yaml and the WISDEM inputs carry none. The OpenFAST AeroDyn file (line 16, `AirDens`) and the HAWC2 master file (line 283) of the same commit state 1.225 kg/m3 for their own models, which is not evidence for the CCBlade table. Following the command, `rho0 = 1.225` with `reference_density_verified: false`, and L-027 in LIMITATIONS.

Illustration (real curve, `A` = 6, 8, 10 m/s, `k` = 2, `rho_ref` = 1.15): CF 0.244, 0.424, 0.565 at dT = 0; 0.242, 0.422, 0.563 at dT = 3 K; without any density correction 0.256, 0.438, 0.577. With `eta_loss` 0.866 multiply by 0.866.

## 3. Wind power density (step 4)

Turbine data: 3.37 MW, rotor 129.822 m (yaml), nameplate rated.

| Spacing | D = 129.82 m | D = 130 m | .tex |
|---|---|---|---|
| 6D x 10D | 3.3327 | 3.3235 | 3.32 |
| 5D x 8D | 4.9990 | 4.9852 | 4.99 |
| 4D x 7D | 7.1415 | 7.1217 | 7.12 |

Largest difference 0.38 percent (below the 1 percent rule), so the .tex values 3.32 / 4.99 / 7.12 are kept.

## 4. `parameters.json` (step 5)

All three countries, both technologies. Every entry written has `verified = false`, `proxy = false`; the verification flags are the author's to flip. Costs carry `price_year = 2024`.

| Parameter | Value written |
|---|---|
| `luf` | `scenario_values` from `tab:g1_luf`; `value` = central; Tier 3 |
| `power_density_mw_per_km2` | PV 45 / 50 / 75 MW_dc/km2; wind 3.32 / 4.99 / 7.12; Tier 2 |
| `gamma` | -0.0030, uniform [-0.0032, -0.0028] |
| `eta_loss` | 0.866 (a retention factor), uniform [0.803, 0.932] |
| `hub_height_m` | 100 m; the 150 m run is a sensitivity (set 150) |
| `capex_usd_per_kw` | IRENA mean, uniform [P5, 2 mean - P5]; PV per kW DC with no ILR: BRA 724 [503, 945], IND 525 [415, 635], PRT 779 [524, 1034]; wind BRA 1307 [1015, 1599], IND 1110 [984, 1236], PRT 1659 [1211, 2107] |
| `opex_fixed_frac` | `tab:g2_opex` as printed; PRT wind computed (below) |
| `opex_var_usd_per_mwh` | 0.0 |
| `lifetime_years` | 30, uniform [25, 30] |
| `commissioning_year` | 2026 (new optional key, documentation only) |
| `discount_rate` | **not recorded**: value null, `pending_research` (see 5) |

PRT wind fixed O&M: the European rows of IRENA Table A3 (p. 209) are Sweden 45, Ireland 38, Germany 53, Denmark 40, Norway 45, Spain 29, United Kingdom 41, France 53. Range 29 to 53 USD/kW/yr, midpoint 41. Divided by 1659: central 0.024714, range 0.017480 to 0.031947. The .tex range 38 to 45 does not come from these rows; the .tex table still shows 0.0250 / 0.0229 to 0.0271 and needs the author's edit. Spain is the minimum, so the choice to count Norway as European does not move the range.

Removed: the earlier IRENA entries for capex, fixed O&M, lifetime and the two wind-O&M proxies (L-203). The old `discount_rate` values (BRA 0.077, IND 0.0708/0.0838, PRT 0.042/0.037) were also set to null, otherwise the loader would not list the discount rate as pending as the completion criterion expects; the previous values are in git. `discount_rate_increment` (0.0) was left; its note ("discount_rate above is already the final benchmark value") is now stale.

## 5. Discount rate, read only (step 6)

Nothing was written.

**IRENA 2024 (Renewable Power Generation Costs in 2024).** It documents the method and not the values. Annex I, p. 206 to 207, states that the LCOE uses "the calibrated benchmark tool for the real after-tax WACC values by country and technology" shown in **Figure A1 (p. 207)**, for deployment in 2024, with WACC values for a year based on macro data of the previous year (p. 41). Figure A1 is a choropleth map with a colour scale (solar 2.3 to 23.5 percent, onshore wind 2.3 to 23.5 percent) and **no country labels**, so no country value can be read. Two inconsistencies in the report: the figure is titled "real after-tax", the legend says "WACC nominal"; and Box A.2 (p. 206) says the tool produces nominal values converted to real by assuming 2.39 percent inflation. Countries outside the benchmark decline linearly to 5 percent (OECD and China) or 7.5 percent (elsewhere) in 2024. So: value not documented per country, type stated as real after-tax, year 2024 (WACC of 2023 data).

**IRENA 2023 (cost of financing).** The data appendix with country values was not reachable. From the map labels (Figures 3 and 4, p. 11), already in the audit: solar BRA 7.6, IND 7.1, PRT 10 percent; onshore wind BRA 6.8, IND 8.4 percent, no label for Portugal (Spain 4.3). These are nominal, post-tax, surveyed 2019 to 2021 (p. 10). The 10 percent of PV Portugal is confirmed as a label, with the 0.1 point rounding. There is no onshore-wind value for Portugal in the reachable material.

Consequence for the author: the 2024 LCOE of IRENA uses real rates that the report does not tabulate, and the 2023 values are nominal. The conversion with a central-bank inflation target (eq:theory_fisher) is the .tex route, but both the survey period and the nominal basis differ from the 2024 LCOE year. OQ-022 and OQ-054 stay open.

## 6. Does the IRENA 2024 total installed cost include grid connection? (step 7)

- **PV.** Yes, plant-side. Annex I, Table A2 (p. 208), lists in the PV BoS hardware category "Grid connection": "All medium voltage cables and connectors; Switch gears and control boards; Transformers and/or transformer stations; Substation and housing; Meter(s)", and under installation "Access and internal roads" and "Installation of grid connection components". The breakdown figure (Figure 3.4, p. 96 to 97) shows the same category. The report does not say that a line to a distant transmission node is included.
- **Onshore wind.** Not found. The onshore chapter (p. 73) says turbines are about 75 percent of the total installed cost and gives no scope sentence. The only sentence on who owns the grid connection asset is in the offshore chapter (p. 118: "Grid connection assets in China, for example, are developed by project owners or the transmission network owner, while in Denmark and the Netherlands they are developed and owned by the network operator"), and concerns offshore.

So the .tex sentence "IRENA total installed costs include the cost of connecting the plant to the grid" holds for PV with the plant-side limit, and is not supported for onshore wind.

## 7. Diff summary (step 10)

See `git diff --stat` in Section 9. `config/parameters.json` is rewritten for the six technology blocks of BRA, IND, PRT; the ZZZ block is unchanged.

## 8. Loader validator (step 9)

`audit_parameters` for BRA, PRT, IND, solar and wind (the same result in all six):

| Phase | Open |
|---|---|
| F5 | none |
| F6 | `discount_rate`; Group 3: `degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km` |
| F7 (outside this command) | `cf_min`, `tau_lcoe_usd_per_mwh`, `top_k_percent` |

No proxy error. Warnings are only the Tier 3 entries (2 for solar, 4 to 5 for wind per country).

## 9. Suite and diff

Full suite: **1369 passed**, 0 failed (12 min), against 1321 before. No commit.

Changes outside the plan, forced by the method change:

- `docs/_audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py`: the by-hand wind CF now uses the member density `rho_ref T*/(T*+dT)`. It is the independent check of the ZZZ2 run, and it agrees with the pipeline.
- `tests/synthetic/test_zzz2_end_to_end.py`: the expected wind `r_loss` of H5 moves from 0.0521657 to 0.0551514, because the member density now follows `dT` (the other expected statistics are unchanged). The value is the pipeline's, confirmed by the updated by-hand validation.

`git diff --stat`: 23 tracked files changed, +1466 / -632, mostly `config/parameters.json` (six technology blocks rewritten) and the F5 tests. New untracked: `config/turbines/iea_3.4_130.csv`, `tests/unit/test_groups12_parameters.py`, this report. The audit file, the three .tex files and `docs/thesis/theory/` were untracked before this work.

## 10. For the author

1. METHODOLOGY bump: 14.2.0 as commanded, 15.0.0 by the protocol (changes a result definition).
2. The .tex tables that no longer match the file: PRT wind O&M (0.0247, 0.0175 to 0.0319 instead of 0.0250, 0.0229 to 0.0271); `tab:g2_capex` still shows ILR-converted PV values; the .tex density equation and the flag are now implemented as written.
3. `rho0 = 1.225` is unverified (L-027); `T*` is a constant, not a `parameters.json` key.
4. The lifetime draw is continuous and rounded, so 25 and 30 have half the weight of 26 to 29 (L-029).
5. Open: discount rate (Section 5), Group 3, F7 thresholds, and the `verified` flags of every new entry.
