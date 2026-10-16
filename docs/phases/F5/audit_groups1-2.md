# Audit of Groups 1 and 2: what F3, F5 and F6 implement against the .tex, and the numeric sources

Date: 2026-10-16. Nothing in the repository was edited by this audit; this file is the only new file. Nothing is corrected here: every divergence is listed for the author.

Inputs read: `docs/thesis/methods/group1_technical_potential.tex` (G1), `docs/thesis/methods/group2_core_costs.tex` (G2), `docs/thesis/theory/ch2_renewable_potential_foundations.tex` (CH2), `docs/METHODOLOGY.md` (M-F4-03 to M-F6-06), `docs/OPEN_QUESTIONS.md`, `docs/LIMITATIONS.md`, `config/parameters.json`, `config/technologies.yaml`, `config/experiments.yaml`, and the code of `land_eligibility`, `climate_forcing`, `technical_potential` and `lcoe_modeling` (`src/geofrea/`). Classes: MATCH (code does what the .tex says), PARAMETER_ONLY (the code can do it by entering values in the config), METHOD_CHANGE (the code or the .tex has to change).

Access limits of this audit (the sources were read over the network on 2026-10-16):

- IRENA 2024 costs report: full PDF (`IRENA_TEC_RPGC_in_2024_2025.pdf`, 51 MB), text extracted; page numbers below are the printed ones.
- IRENA 2023 financing report: full PDF read; the country values exist only as labels of the maps of Figures 3 and 4 (read from the rendered page); the Excel data appendix was not reachable.
- NREL ATB 2024: the NREL site moved to `atb.nlr.gov` (`atb.nrel.gov` does not resolve from this machine); the 2024 pages were read there.
- IEA-3.4-130-RWT: GitHub repository files and the NREL/TP-73492 report PDF read.
- Faiman (2008): the paper itself was not reachable; only the values that `pvlib` documents as Faiman's are verified (secondary).
- The thesis `.bib` is not in the repository. The only candidates are `C:\Users\User\Downloads\references.bib` and `references_organized.bib` (see Section 4).

## 1. Findings that change the .tex or the code (in order of consequence)

1. **IRENA states the PV total installed cost per kW of DC, not AC.** G2 (`subsec:g2_scope`, `subsec:g2_capex`, Table `tab:g2_capex`) converts the IRENA PV costs with ILR 1.25 on the premise that IRENA uses kW_ac. The report says "TIC data in this report are expressed as per kW of direct current (DC) for solar PV only" (IRENA 2024, p. 92, note 27). The ILR conversion lowers every PV cost by 20 % and has no basis; without it BRA PV is 724 USD/kW_dc, not 579.2. The `% verify` of G2 line 36 anticipated this case ("if it is DC, drop the ILR conversion"). OPEN.
2. **Source discount rates are nominal, post-tax, 2019-2021, and the G2 values are not reproduced by them.** IRENA 2023, p. 10: the rates are "nominal 'CoC after tax' ... expressed in nominal terms throughout". The map labels give solar BRA 7.6 %, IND 7.1 %, PRT 10 %; onshore wind BRA 6.8 %, IND 8.4 %, PRT no label. G2 Table `tab:g2_wacc` has 7.7 / 5.1 / 3.95 (PV) and 7.7 / 4.4 / 3.7 (wind), called "real". The statement that the Indian wind rate is lower than the PV rate is the opposite of the source (8.4 % wind, 7.1 % PV). OPEN.
3. **F5 solar has no Faiman model, no per-time-step evaluation, no `S_0`/`S_1` sums.** The code is `CF_m = (PVOUT/24) * delta_rsds * (1 + gamma * dT)` with annual-mean `dT` (METHOD_CHANGE for G1 `subsec:g1_pv_thermal`; items b and c).
4. **F5 `eta_loss` is a retention factor (`CF = eta_loss * I`), the .tex `eta_loss` is a loss fraction (`CF_net = CF_gross (1 - eta_loss)`).** Entering 0.134 in `parameters.json` would multiply the capacity factor by 0.134. The values have to be entered as 0.866 and [0.803, 0.932] (item c).
5. **LUF and PD are one value per technology in the code; G1 has three scenario values coupled to the F3 scenarios.** `pipeline.py:329-336` uses the same `luf` and `power_density_mw_per_km2` in the central, restrictive and permissive land scenarios (item j).
6. **F3 excludes cropland for solar in all three scenarios** (nominal level `cropland_excluded`); for wind cropland is allowed (nominal `forest_excluded`). The G1 argument for lower Indian PV LUF (competition with agriculture on land F3 does not exclude) double counts for solar (item h). OPEN.
7. **The air-density correction per climate member (G1 `eq:g1_density_member`) needs a reference mean temperature per cell that no F4 artifact holds.** The code keeps the GWA density fixed in every member (items d and f).
8. **Per-cell IEC class rule selects a curve in the code; G1 uses one curve and a screening flag.** One curve and one class are possible by configuration; the flag at 7.5 m/s does not exist (item d).
9. **The TIC and O&M numbers of the .tex are in the IRENA report, with the caveats of Section 3.** Every TIC (BRA, IND, Europe: weighted average, P5, P95) and every O&M figure of the command was found. The PRT wind O&M range (38 to 45) has no Portugal row in IRENA Table A3.

## 2. Code against the .tex (items a to j)

| Item | What the code does (file:line) | What the .tex specifies | Class |
|---|---|---|---|
| a. PV assembly | F5 has no mounting model. The resource is the Global Solar Atlas `pvout_kwh_kwp_day`, `CF0 = PVOUT / 24` (`technical_potential/solar.py:23`; `cf_models.py:113-121`). LIMITATIONS L-001: PVOUT is free-standing c-Si at fixed optimum tilt; trackers are not modeled. | G1 `subsec:g1_pd`: PD for the mounting that F5 models only (fixed 45/50/75, tracking 30/40/50 MW_dc/km2); a tracking density is never combined with a fixed-tilt CF. | MATCH when only the fixed-tilt PD (45/50/75) enters `parameters.json`. The tracking row and the `% verify` (command 41) are answered: F5 models fixed tilt implicitly through PVOUT. |
| b. PV thermal model | None. No cell or module temperature, no wind input, no hourly or daily series. PVOUT "already includes reference-climate thermal losses" (METHODOLOGY M-F5-02, line 258); the member correction is `delta_rsds * (1 + gamma * dT)` with `dT` and `delta_rsds` annual means of monthly climatologies (`climate_forcing/change_factors.py:66-68`). | G1 `subsec:g1_pv_thermal`: Faiman module temperature (`U0` 25.0, `U1` 6.84) plus `Delta T_ref` 3 K, evaluated at each time step with the reference-period wind of the PV baseline dataset. CH2 `subsec:pv_temperature`: a factor at mean temperature "misstates the loss". | METHOD_CHANGE (code or .tex). The code applies the mean-temperature factor the theory chapter warns against. |
| c. gamma and eta_loss in F6 | gamma: F5 stores the CF at the nominal gamma; F6 rescales it with `(1 + gamma dT)/(1 + gamma_nom dT)` per cell and member (`technical_potential/rescale.py:25-37`, `lcoe_modeling/inputs.py:277`); in the reference member `dT = 0`, so gamma has no effect there. It does not recompute a series and does not use `S0 + gamma*S1`. eta_loss: F5 stores `CF = eta_loss * I(A_eq, k)`, i.e. the net CF (`weibull_cf.py:116-133`); F6 rescales by `x / nominal` (`rescale.py:12-22`), exact because the CF is linear in eta_loss. F5 does not store a gross CF. | gamma: `CF(gamma) = S0 + gamma S1` from two sums stored by F5 (`eq:g1_cf_linear_gamma`). eta_loss: `CF_net = CF_gross (1 - eta_loss)`, applied once (`eq:wind_net_cf`), central 0.134, range [0.068, 0.197]. | gamma: METHOD_CHANGE. eta_loss: PARAMETER_ONLY with a unit trap: the code key `eta_loss` is `1 - loss` (0.866; range 0.803 to 0.932). The one application is satisfied (F6 never applies it twice). The combination of the four components is arithmetically consistent (min 6.8 %, central 13.4 %, max 19.7 %). |
| d. Wind curves, class rule, density | Curves: one file per IEC class (`power_curve.py:27-93`), `technologies.yaml` `power_curves` and `iec_class_rule` are `null` (lines 121, 128); `config/power_curves/` does not exist (only `tests/fixtures/power_curves/synthetic_curve.yaml`). Class: first class whose upper bound is not below the annual mean speed at hub height, fixed across members (`iec_class.py:25-52`, `cf_models.py:176-180`). Density: `v_eq = v (rho/rho0)^(1/3)` folded into the Weibull scale, `A_eq = A_H (rho_H/rho0)^(1/3)` (`weibull_cf.py:29-48`); `rho0 = 1.225` (`core/constants.py:57`); `rho_H` is the GWA layer `air_density_<h>m` extracted by F1 (`technologies.yaml:68,71,74`), interpolated linearly to hub height (`wind_profile.py:71-91`). The density is the same in every member. | G1: one turbine (IEA 3.4-130), one curve in every cell, the class rule only as a screening flag at 7.5 m/s that changes nothing. `eq:wind_density_correction`; `rho` of cell `i` is the GWA 100 m layer; member density `eq:g1_density_member`. | Density formula: MATCH. GWA layer in use: MATCH. One curve for all cells: PARAMETER_ONLY (one entry in `power_curves`, one-entry `iec_class_rule` with a null bound; `iec_class.py:46` accepts it). The 7.5 m/s flag: METHOD_CHANGE (not implemented). Member density (`eq:g1_density_member`): METHOD_CHANGE (not implemented). |
| e. Weibull layer and the F4 wind factor | Hub height from `hub_height_m` in `parameters.json`, 100 to 200 m; `A` by power law between the bracketing heights, `k` and `rho` linear (`wind_profile.py:41-68,94-120`); at 100 m the interpolation returns the 100 m layer exactly. The F4 factor multiplies the scale: `A_eq,m = delta_wind * A_eq`, `k` unchanged (`weibull_cf.py:116-133`; METHODOLOGY M-F5-03). | G1: the 100 m layer, no shear correction to the 110 m hub; 150 m layer once per country as a sensitivity; the F4 factor "as specified in METHODOLOGY (F4)". | PARAMETER_ONLY: `hub_height_m = 100` gives the 100 m layer; the 150 m sensitivity is a second run with `hub_height_m = 150` (the code has no sensitivity switch). F4 entry: MATCH. |
| f. Reference mean temperature per cell (F4) | Not available. `forcing.parquet` holds `cell_id, member, delta_rsds, dT, delta_wind, dT_isolated_native_cell` (`climate_forcing/table_schemas.py`, METHODOLOGY M-F4-06). `mean_ref(tas)` is computed inside `change_factors.py:11,66-68` and only the difference leaves it. `hazard_context.parquet` has heat-day indicators, no mean temperature. | `eq:g1_density_member` needs `T_bar_ref_i` (annual mean, K). | METHOD_CHANGE: F4 has to write the reference `tas` annual mean per cell (and F5 has to read it); not specified in METHODOLOGY. |
| g. AC output and clipping | None. PVOUT is per kWp (DC); no inverter, no clipping, no ILR in `src/` or `config/`. Wind: the curve is capped at the rated power. | G1: "inverter clipping is not represented unless F5 models AC output"; PV capacity, PD and costs are DC. | MATCH. |
| h. F3 exclusions (wind and solar) | E1 protected areas, E2 lakes, E3 riparian setback, E4 slope, E5 land cover, E6 population density (`land_eligibility/eligibility.py:1-13,130-154`). Cropland (WorldCover 40) **is excluded for solar**: nominal level `cropland_excluded` = [10, 40, 50, 70, 80, 90, 95] (`config/experiments.yaml:167-172`) and the level is categorical, held at the central value in all three land scenarios (`land_eligibility/scenarios.py:65-69`). For wind the nominal level is `forest_excluded` = [10, 50, 70, 80, 90, 95]: cropland is **allowed**; `forest_and_cropland_excluded` exists as an alternative level (`experiments.yaml:230-237`). Nothing else encodes agricultural use or tenure. | G1 `subsec:g1_luf`: lower Indian LUF for "competition with agricultural use on land that F3 does not exclude"; `% verify: METHODOLOGY (F3) does not exclude cropland; otherwise ... double counts`. | Wind: MATCH (cropland is not excluded, the argument does not double count). Solar: the `% verify` condition fails; the argument double counts for PV. Not one of the three classes; recorded as OPEN (author verdict, Section 6). |
| i. F6 LCOE and sampling | Form: `LCOE = opex_var + [P U + P d_grid c_grid + d_road c_road] / (E A_e)` with `U = 1000 capex (1 + f A_o) + substation`, exact factored form of the textbook sum with degradation (`lcoe_modeling/kernel.py:8-17,271`). capex: sampled between `range.min` and `range.max` of `parameters.json`, `uniform` or `triangular` with the mode at the nominal (`sampling.py:42-48`, `core/schemas.py:70`). `opex_fixed_frac`: a fraction of CAPEX per year, sampled the same way. `discount_rate`: real; no nominal-to-real conversion exists (OQ-054: "no inflation value is assumed"); sampled uniform or triangular. `lifetime_years`: drawn continuous, rounded to whole years in the design matrix (`design.py:27-32`); the kernel rejects a non-integer (`kernel.py:189-191`). Variable O&M exists (`opex_var_usd_per_mwh`, required, not sampled; `technologies.yaml:42,114`). | G2: `LCOE = (I CRF + F)/E` (`eq:theory_lcoe`); CAPEX uniform on `[P5, 2 c_bar - P5]` (`eq:g2_capex_interval`); `f` uniform; real discount rate, uniform, converted with Fisher and central-bank targets when the source is nominal; lifetime 30, U[25, 30]; variable O&M set to zero. | LCOE form: MATCH (the kernel adds the Group 3 terms, degradation and substation; with `d = 0` and no grid or road terms it equals `eq:theory_lcoe`). capex, `f`, discount rate, lifetime: PARAMETER_ONLY (enter min, max, `uniform`; the nominal is the interval midpoint, which `UncertainSpec` accepts). Lifetime rounding: the draw of U[25, 30] rounds to 25 and 30 with probability 0.1 each and to 26 to 29 with 0.2 each (design-matrix property, not stated in G2). Variable O&M: PARAMETER_ONLY (value 0 with a source; a null value is refused in a production run). |
| j. Keys of `parameters.json` | See the table below. | | |

Keys of `parameters.json` (U-05 scheme: `value`, `unit`, `source`, `tier`, `range`, `verified`, ..., `price_year`) for the parameters of the two .tex:

| Parameter of the .tex | Key in `parameters.json` | State |
|---|---|---|
| LUF (3 scenario values) | `luf` | Exists, one `value` (null for BRA, PRT, IND) and an optional `range`; the three-scenario coupling has no key and no code (`technical_potential/pipeline.py:329-336`). METHOD_CHANGE. |
| PD solar (fixed-tilt 45/50/75), PD wind (3.32/4.99/7.12) | `power_density_mw_per_km2` | Exists, one value, unit `MW/km2` (null). Same coupling gap as LUF. No key for the mounting configuration. |
| eta_loss, components | `eta_loss` (wind) | Exists (null); one combined value; retention semantics; the four component losses have no keys (only the combination enters the code). |
| Hub height, 100 m (150 m sensitivity) | `hub_height_m` (wind) | Exists (null). |
| gamma, range | `gamma` (solar) | Exists (null), `1/K`. |
| `U0`, `U1`, `Delta T_ref` | none | Missing; no code reads them. |
| ILR, 1.25 (1.15 to 1.30) | none | Missing; no code reads it. If IRENA PV costs are already DC (Section 3a), the ILR is not needed by the cost conversion. |
| `t_ref` 2026 (vintage) | none | Missing (a statement, not a model input). |
| IEC class bounds, 7.5 m/s flag | `technologies.yaml` `iec_class_rule` (null) | Not in `parameters.json`; the flag does not exist. |
| Reference turbine (rated, rotor, hub, curve) | `config/power_curves/<id>.yaml` (directory absent) | Missing. A curve needs `source` and `tier` (`power_curve.py:84-87`). |
| `rho0` 1.225 | `core/constants.py:57` | Exists as a constant, not a parameter. |
| capex (USD/kW, PV in kW_dc) | `capex_usd_per_kw` | Exists with values, no range for BRA, PRT, IND; `price_year` field exists in the schema (`core/schemas.py:160`) and the entries have none. Current values differ from G2 (below). |
| Fixed O&M fraction | `opex_fixed_frac` | Exists with values, no range. |
| Variable O&M | `opex_var_usd_per_mwh` | Exists (null); G2 sets it to zero. |
| Discount rate | `discount_rate` (also `discount_rate_increment` 0.0, not in the .tex) | Exists with values, no range. No key for expected inflation. |
| Lifetime | `lifetime_years` | Exists (25 for BRA, PRT, IND), no range. G2 central 30. |

Current `parameters.json` against G2 (these are older entries, to be replaced, listed only so the author sees the gap): BRA solar capex 672 (source text "IRENA 2025, Table 3.1, Brazil-specific"; the 2024 report's Table 3.1 gives 724), BRA wind 976, IND solar 691 (the global weighted average, not India's 525), IND wind 1041 (global weighted average; G2 uses India's 1110), PRT solar 823, PRT wind 976; discount rates BRA 0.077 (both), IND 0.0708 and 0.0838, PRT 0.042 and 0.037; lifetime 25.

Other code observations that touch the .tex:

- `pipeline.py:362` and METHODOLOGY M-F5-05 use 8760 h/yr; CH2 `eq:theory_energy` uses 8760. MATCH.
- The power-curve loader requires the first node to have zero power (`power_curve.py:74-75`) and treats the last node as the declared cut-out (`power_curve.py:78-80`). The IEA table starts at 3.0 m/s with 51.6 kW (Section 3d), so a zero node has to be added below cut-in when the curve file is written.
- The wind density `eq:g1_density_member` and the screening flag, if adopted, are new outputs of F4 and F5 that the METHODOLOGY does not yet specify.

## 3. Sources (items a to e)

### 3a. IRENA, Renewable Power Generation Costs in 2024 (full report, printed pages)

| Question | Finding | Page and table |
|---|---|---|
| TIC of solar PV, Brazil | weighted average 724; P5 503; P95 1152 (2024 USD/kW) | Table 3.1, p. 95 |
| TIC of solar PV, India | 525; 415; 831 | Table 3.1, p. 95 |
| TIC of solar PV, Europe | 779; 524; 1312 | Table 3.1, p. 95 |
| TIC of onshore wind, Brazil | 1307; 1015; 1628 | Table 2.1, p. 71 |
| TIC of onshore wind, India | 1110; 984; 1270 | Table 2.1, p. 71 |
| TIC of onshore wind, Europe | 1659; 1211; 2232 | Table 2.1, p. 71 |
| PV cost basis | kW of **DC**: "TIC data in this report are expressed as per kW of direct current (DC) for solar PV only" | p. 92, note 27 (the same statement for the PV capacity factor, p. 99, note 32) |
| TIC includes grid connection? | PV: the BoS breakdown has a "Grid connection" category (medium-voltage cables and connectors, switchgear and control boards, transformers or transformer stations, substation and housing, meters) and the installation category lists "Access and internal roads" (Annex I, Table A2, p. 208; Figure 3.4, p. 96-97). These are plant-side assets; the report does not say that a line to a distant transmission node is included. Wind: no sentence on the scope of the TIC was found (turbines are about 75 % of the TIC, p. 73). | p. 96-97, 208-209 |
| Price year | all TIC, LCOE in 2024 USD (table headings "2024 USD/kW"; Summary p. 3, note 1) | Tables S1, 2.1, 3.1 |
| Global weighted-average capacity factor 2024 | PV 17.4 % (5th 11.5 %, 95th 22.6 %), reported on DC capacity; onshore wind 34 % (36 % in 2023) | Table 3.2, p. 99 (note 32); p. 76 |
| Country capacity factors reported | wind 2024: Brazil 56 %, India 39 % | Table 2.2, p. 76 |
| PV O&M 6.99 | average all-in O&M of the surveyed projects, 2024, all countries (China 3.2 to Japan 10.7 USD/kW/yr) | p. 100-101 |
| PV O&M 11.0 and 20.7 | LCOE assumptions for projects commissioned in 2024: 10.95 (non-OECD) and 20.73 (OECD) | Table A4, p. 210; note 34, p. 100 |
| PV O&M 18.2 | OECD LCOE assumption 2021 to 2023 | Table A4, p. 210 |
| PV O&M 13.1 | global weighted-average utility-scale O&M, 2024, "estimated, total all-in O&M costs" | p. 100 |
| Wind O&M 29 (Brazil), 23 (India) | LCOE assumptions, 2024 USD/kW/yr | Table A3, p. 209 |
| Wind O&M 38 and 45 | 38: Ireland, Australia, "Other non-OECD"; 45: Sweden, Norway, United States, "Other OECD". Portugal has no row. | Table A3, p. 209 |
| Another Brazil wind O&M figure | full-service contract O&M in Brazil about 20 USD/kW/yr (a different series from the 29) | p. 80 |
| O&M basis (kW_ac or kW_dc) | not stated for the 13.1 and the 6.99; the United States series cited is on AC (p. 100) | p. 100 |

### 3b. IRENA, The cost of financing for renewable power (2023)

- Rate type: "the nominal 'CoC after tax' often also referred to as nominal 'post-tax WACC' ... These rates are expressed in nominal terms throughout this report, meaning that they are not adjusted for inflation" (p. 10). Survey period 2019-2021 (Figures 3 and 4); "post-tax" and "nominal" also in the figure notes.
- Utility-scale solar PV (Figure 3, p. 11, map labels): Brazil 7.6 %, India 7.1 %, Portugal 10 %. Onshore wind (Figure 4, p. 11): Brazil 6.8 %, India 8.4 %; no value is labelled for Portugal (Spain 4.3 %). The labels are rounded to 0.1 point; the data appendix (Excel) with country values was not reachable, so intervals or other decimals are not verified.
- The regional simple averages in the text (p. 10-11): solar 6.6 % Latin America, 4 % Western Europe; onshore wind 6.4 % Latin America, 3.3 % Western Europe.

### 3c. NREL ATB 2024 (read at `atb.nlr.gov`)

- Technical life, "Technical Lifetimes for Technologies" table (`/electricity/2024/definitions`): land-based wind 30 years; solar utility-scale PV 30 years. The ATB separates the technical life from the cost recovery period (a default option of 20 or 30 years); the 30 is the technical life.
- ILR: "a DC-to-AC ratio, or inverter loading ratio (ILR), of 1.34 for the Base Year and future years (Ramasamy et al., 2023)" (`/electricity/2024/utility-scale_pv`). The page adds that the ATB capacity factors are for a one-axis tracking system with ILR 1.34, and that the PV industry quotes CAPEX in USD/kW_dc while the electric utility industry quotes it in USD/kW_ac.

### 3d. IEA-3.4-130-RWT (GitHub `IEAWindTask37/IEA-3.4-130-RWT` and NREL/TP-73492)

- Rated electrical power 3.37 MW (`yaml/IEA-3.4-130-RWT.yaml` `rated_power: 3370000.0`; report Table 2), rotor diameter 129.82 m (the report says 130 m), hub height 110 m, `turbine_class: III`, `turbulence_class: A`, cut-in 3 m/s, cut-out 25 m/s. Specific power recomputed: 3.37e6 / (pi/4 x 129.82^2) = 254.6 W/m2 (G1: about 254).
- Reference density of the power curve: **not found.** No air-density value for the power table appears in the yaml, the `.dat` header or the report text searched; the density basis of the curve is not stated (the code and G1 take 1.225).
- Ready power-curve table: **it exists**, so "BLOCKED: curve requires simulation" does not apply: `performance/performance_ccblade.dat` (50 rows, wind speed 3.0 to 25.0 m/s, "Rotor electrical power (W)" in column 4, also rotor power, thrust and coefficients). It is the output of the CCBlade aerodynamic model, not a measurement. Examples: 3.0 m/s 51.6 kW, 5.77 m/s 688.9 kW, 7.29 m/s 1389.0 kW, 8.87 m/s 2506.6 kW, 11.37 m/s and above 3370 kW. The first node is not zero (see Section 2).
- Licence: Apache-2.0 (`LICENSE`).

### 3e. Faiman (2008)

- The paper was not reachable. The `pvlib.temperature.faiman` documentation gives the defaults `u0 = 25.0` W/m2/K and `u1 = 6.84` W/m2/K/(m/s) as "determined by Faiman for 7 silicon modules in the Negev desert on an open rack at 30.9 degrees tilt" (secondary source). The per-module ranges (G1: 23.5 to 26.5 and 6.25 to 7.68) and the wind measurement height of the calibration are not verified.

## 4. Each number of the .tex

| Where | Number | Verdict | Source value and note |
|---|---|---|---|
| G2 `tab:g2_capex` | PV BRA 724, 503/1152; IND 525, 415/831; PRT (Europe) 779, 524/1312 | OK | IRENA Table 3.1, p. 95 |
| G2 `tab:g2_capex` | wind BRA 1307, 1015/1628; IND 1110, 984/1270; PRT (Europe) 1659, 1211/2232 | OK | IRENA Table 2.1, p. 71 |
| G2 `tab:g2_capex`, `subsec:g2_scope` | PV central 579.2, 420.0, 623.2 and ranges 402.4-756.0, 332.0-508.0, 419.2-827.2 (the IRENA value divided by ILR 1.25) | DIVERGE | IRENA states PV TIC per kW DC (p. 92). Without the ILR division: 724, 525, 779 and, with `[P5, 2 c_bar - P5]`, 503-945, 415-635, 524-1034 (USD/kW_dc). The arithmetic of the table is internally consistent. |
| G2 `tab:g2_capex` | wind central and ranges 1015-1599, 984-1236, 1211-2107 | OK | `2 c_bar - P5` recomputed from the IRENA values |
| G2 `subsec:g2_scope` | "IRENA expresses capacity in AC terms" | DIVERGE | DC for PV (p. 92, p. 99) |
| G2 `subsec:g2_capex` | "IRENA total installed costs include the cost of connecting the plant to the grid" | OK with a limit (PV) / NOT_FOUND (wind) | PV: plant-side grid connection and internal and access roads are in the breakdown (p. 96-97, 208); nothing about a line to the transmission network; wind: no scope sentence found |
| G2 `tab:g2_opex` | PV 6.99 | OK | survey average all-in O&M, p. 100-101 |
| G2 `tab:g2_opex` | PV 11.0 | OK | non-OECD LCOE assumption for 2024 (10.95), Table A4, p. 210; it is an assumption, not a measurement or a contract price |
| G2 `tab:g2_opex` | PV 13.1 | OK | global weighted-average all-in O&M 2024, p. 100. The text of G2 says 13.1 covers "contract prices and all-in costs"; the 6.99 is also all-in |
| G2 `tab:g2_opex` | wind 29 (BRA), 23 (IND) | OK | Table A3, p. 209 (LCOE assumptions) |
| G2 `tab:g2_opex` | wind PRT 38 to 45 | OK as numbers / NOT_FOUND for Portugal | 38 and 45 are in Table A3 (see 3a); Portugal has no row. "Other OECD" is 45 |
| G2 `tab:g2_opex` | PV PRT 18.2 to 20.7 | OK | OECD, Table A4 (18.2 for 2021-2023, 20.7 for 2024) |
| G2 `tab:g2_opex` | the fractions (0.0124, 0.0097-0.0181, 0.0171, ..., 0.0250, 0.0229-0.0271) | OK | recomputed: O&M divided by the IRENA weighted-average TIC; they depend on the AC/DC point above (the PV fractions use the DC cost, the O&M basis is not stated) |
| G2 `tab:g2_wacc` | PV BRA 7.7 % (6.7-8.7) | DIVERGE | IRENA 2023 Fig. 3: 7.6 %, nominal post-tax, 2019-2021 |
| G2 `tab:g2_wacc` | PV IND 5.1 % (4.0-6.2) | DIVERGE | 7.1 % nominal post-tax (Fig. 3) |
| G2 `tab:g2_wacc` | PV PRT 3.95 % (3.7-4.2) | DIVERGE | 10 % nominal post-tax (Fig. 3) |
| G2 `tab:g2_wacc` | wind BRA 7.7 % (6.7-8.7) | DIVERGE | 6.8 % (Fig. 4) |
| G2 `tab:g2_wacc` | wind IND 4.4 % (3.8-5.0) | DIVERGE | 8.4 % (Fig. 4); the source has wind above PV, the .tex says the opposite |
| G2 `tab:g2_wacc` | wind PRT 3.7 % (2.7-4.7) | NOT_FOUND | no Portugal label in Fig. 4 |
| G2 `tab:g2_wacc` | every range | NOT_FOUND | the figures give no intervals; the data appendix was not reachable |
| G2 `subsec:g2_wacc` | "real after-tax" | DIVERGE | the source rates are nominal, post-tax; conversion with inflation targets 3.0 / 4.0 / 2.0 % is not in the sources of this audit (not checked) |
| G2 `subsec:g2_lifetime` | 30 years for PV and wind | OK | ATB 2024 technical life, both 30 |
| G2 `subsec:g2_ilr` | NREL ILR 1.34 | OK | ATB 2024 PV page |
| G2 `subsec:g2_ilr` | ILR 1.25 (1.15-1.30) | NOT_FOUND | author judgment (the .tex says so); no source |
| G1 `subsec:g1_plausibility` | 17.4 % (PV) and 34 % (wind) global CF 2024 | OK | p. 99 and p. 76; the PV value is on DC capacity |
| G1 `subsec:g1_turbine` | 3.37 MW, 130 m, hub 110 m, class IIIA, about 254 W/m2 | OK | yaml and report (rotor 129.82 m) |
| G1 `subsec:g1_pd` | PD wind 3.32 / 4.99 / 7.12 MW/km2 | OK | recomputed from 3.37 MW, D = 130 m: 3.32, 4.99, 7.12 (with D = 129.82 m: 3.33, 5.00, 7.14) |
| G1 `subsec:g1_turbine` | reference density of the curve 1.225 | NOT_FOUND | not stated in the repository files or the report searched |
| G1 `subsec:g1_turbine` | "power curve taken from the published model", licence | OK / OK | table `performance_ccblade.dat`; Apache-2.0 |
| G1 `subsec:g1_pv_thermal` | `U0` 25.0, `U1` 6.84 | OK (secondary) | `pvlib` documentation of Faiman's defaults, 7 silicon modules, Negev |
| G1 `subsec:g1_pv_thermal` | ranges 23.5-26.5, 6.25-7.68; wind measurement height | NOT_FOUND | the paper was not reachable |
| G1 `subsec:g1_pv_thermal` | `Delta T_ref` 3 K (Gilman 2018), gamma -0.0030 and the TOPCon range | NOT CHECKED | outside the items of this audit |
| G1, CH2 | GWA values (ERA5 2008-2017, heights, gross CF of three 3.45 MW turbines, CFSR density), IRENA 2025 report (`irena2026costs2025`) | NOT CHECKED | outside the items of this audit; the GWA version, period, heights and gross capacity-factor layers were researched separately in this session from secondary sources (the BAMS paper itself was not reachable) |

## 5. Bibliography: the \cite keys of the three .tex against the .bib

The thesis `.bib` is not in the repository. Two files in `C:\Users\User\Downloads\` were compared: `references.bib` (2026-09-30 09:40) and `references_organized.bib` (09:47). Both have 147 entries and the same keys, with no repeated key. They contain **none of the 28 keys** cited by the three .tex (the files predate the .tex of 2026-10-16). All 28 are therefore missing.

| Key | Cited in | In the .bib |
|---|---|---|
| bamisile2025 | G1, CH2 | missing |
| bolinger2022 | G1, CH2 | missing |
| bortolotti2019 | G1, CH2 | missing |
| ceaGeneration | G1 | missing |
| davis2023globalwindatlas | G1, CH2 | missing under this key; the same paper is `Davis2023The` (BAMS 2023, doi 10.1175/bams-d-21-0075.1) in both files |
| dgegRenewables | G1 | missing |
| dtuwind2019gwa3release | G1, CH2 | missing |
| epeAnuario2025 | G1 | missing |
| faiman2008 | G1, CH2 | missing |
| gilman2018 | G1, CH2 | missing |
| gwaV3dataset | G1, CH2 | missing |
| harrisonatlas2022 | G1, CH2 | missing |
| heinrichs2026 | CH2 | missing |
| iec6140012025 | G1, CH2 | missing |
| iec61400122022 | G1, CH2 | missing |
| irena2023financing | G2, CH2 | missing |
| irena2025costs2024 | G1, G2 | missing |
| irena2026costs2025 | G2 | missing |
| itrpv2025 | G1, CH2 | missing |
| larsen2022 | G1, CH2 | missing |
| leefields2021 | G1, CH2 | missing (the CH2 comment already says it must be added) |
| lopez2012 | G1, CH2 | missing |
| mckenna2022 | CH2 | missing |
| nrelATB2024PV | G2, CH2 | missing |
| nrelATB2024definitions | G2 | missing |
| ong2013 | G1, CH2 | missing |
| turkovska2021 | G1, CH2 | missing |
| turkovska2024 | G1, CH2 | missing |

Duplicated keys in the .bib: none. Two keys of the .tex that name one source: none found. Bibliographic data from this audit for the entries that are missing: IRENA 2024 costs report (Abu Dhabi, 2025); IRENA 2023 financing report (Abu Dhabi, May 2023); ATB 2024 pages (NREL, now `atb.nlr.gov`); Bortolotti et al. 2019, NREL/TP-73492 (the repository README gives the citation).

## 6. OPEN, awaiting author verdict

1. PV cost basis: IRENA states kW_dc; G2 divides by ILR 1.25. Decide whether the conversion is dropped (PV CAPEX 724, 525, 779 USD/kW_dc and the ranges of Section 4) and whether the ILR remains as a documented design parameter only.
2. Discount rates: the source is nominal, post-tax, 2019-2021, with labels 7.6, 7.1, 10 (PV) and 6.8, 8.4 (wind), none for Portugal wind. Decide the values, the conversion to real (the inflation values and their source are not in the repository: OQ-054) and the Indian ordering statement in G2.
3. PV thermal model: the code uses `PVOUT * delta_rsds * (1 + gamma dT)` with annual means; G1 specifies a Faiman model per time step with `S_0` and `S_1`. Decide which one stands (this changes F4 or F5, or G1).
4. `eta_loss` meaning: retention in the code, loss fraction in the .tex. Decide the convention before values are entered (0.866 and 0.803 to 0.932 for the .tex values).
5. LUF and PD: one value per technology in the code, three scenario-coupled values in G1.
6. Cropland in F3: excluded for solar in every scenario, allowed for wind. Decide whether the Indian PV LUF justification stands, or whether the F3 level changes for solar.
7. Member air density (`eq:g1_density_member`) and the 7.5 m/s screening flag: not implemented; F4 holds no reference temperature per cell.
8. Wind curve: IEA table available (CCBlade output, first node 51.6 kW at 3 m/s, reference density undocumented); decide the zero node below cut-in, the density basis and the `power_curves` and `iec_class_rule` entries.
9. PRT wind O&M (38 to 45): Portugal has no row in IRENA Table A3; decide the assignment ("Other OECD" 45, or the 38 to 45 bracket).
10. PV O&M basis (per kW_ac or kW_dc) is not stated by IRENA; the PV O&M fractions divide by a DC cost.
11. Faiman per-module ranges and the calibration wind height: the paper is needed.
12. The thesis `.bib` with the 28 keys is not available; `Davis2023The` is the key of `davis2023globalwindatlas`.
13. Sources not read in this audit: `irena2026costs2025`, Gilman 2018, the GWA statements about CFSR density and the Vestas turbines, the inflation targets of the three central banks, the ITRPV and Bamisile support for the TOPCon interval.
