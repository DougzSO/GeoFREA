# Fix round of COMMAND 46 (2026-10-16)

Branch `stage-r/fix-46`, METHODOLOGY 15.0.0, not committed. Inputs: `docs/phases/F5/run_report_real.md` (first real run, METHODOLOGY 14.2.0), the final .tex of Groups 1 and 2, the verdicts of the command.

## 1. Diagnosis before editing

### 1a. Wind in India above 3000 m

- **In METHODOLOGY 14.2.0?** Only as a reporting sensitivity (M-F2b-06: `elevation_max_m` central null, `sensitivity` 3000 m, Tier 3; OQ-058). There was no rule that excludes the cells from the central results.
- **Implemented in F5?** Only the reporting rows. F5 wrote `central__below_3000m` rows in `potential_aggregates_wind.parquet` (the central totals without the cells above 3000 m) and F6/F7 wrote their own `below` outputs. No cell was excluded: the potential tables of the three scenarios held every candidate.
- **Did the round-44 totals include the cells?** Yes. F3 candidates are not filtered by altitude (`elevation_max_m` nominal was null), so the F5 totals of IND wind of the first real run include them. Reference member `m0`, from the potential tables of the run:

| Scenario | Cells above 3000 m | Of cells | GW above | GW total | Share of capacity | TWh/yr above | TWh/yr total | Share of energy | Mean CF above |
|---|---|---|---|---|---|---|---|---|---|
| restrictive | 945 | 56190 | 0.07 | 58.8 | 0.12% | 0.13 | 94.7 | 0.13% | 19.8% |
| central | 1316 | 62718 | 0.71 | 190.5 | 0.37% | 1.11 | 300.6 | 0.37% | 16.6% |
| permissive | 1407 | 65454 | 8.30 | 638.6 | 1.30% | 12.07 | 993.2 | 1.21% | 15.7% |

Highest wind candidate in the three scenarios: PRT 1356 m, BRA 1922 m, IND 6224 m. A limit of 3000 m therefore changes India only. **Central IND wind above 3000 m: 0.71 GW and 1.11 TWh/yr (0.37% of each).** This is the sensitivity of the exclusion; it is recorded here, in OQ-058 and in L-025.

**Implemented now:** `elevation_max_m` nominal 3000 m in `config/experiments.yaml` (wind only; Tier 3, no source; status `excluded_unsourced`), so F3 does not accept a wind cell above it as a candidate in any scenario (M-F3-04; the machinery `candidate_stability` and `_is_candidate` already existed and had never been given a value). `sensitivity` is now null: there are no `__below` rows in F5, F6 and F7 because they would equal the central rows. F3 reports the limit and the number of central cells it removed (`elevation_max_m`, `n_cells_excluded_by_elevation`). **Consequence:** the real F3 outputs of IND (wind) were computed before the rule and have to be produced again before the clean F5 round; the F5 code needed no change for this. The rule is technology-wide, not country-specific: it bites only in India because the other two countries have no wind candidate above 1922 m (a country-specific rule would put a country name in the method).

### 1b. The warnings that left PRT and IND in `ran_with_issues`

From the logs of the round-44 runs (`D:/tmp_diag/f5_PRT.log`, `f5_IND.log`), exactly six warnings in each country, one per layer, all OQ-053, none from another cause (no `no candidate cells`, no range error, no forcing warning):

| Warning (logger `geofrea.technical_potential.input_ranges`) | PRT | IND |
|---|---|---|
| `wind: weibull_a_100m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |
| `wind: weibull_k_100m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |
| `wind: weibull_a_150m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |
| `wind: weibull_k_150m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |
| `wind: weibull_a_200m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |
| `wind: weibull_k_200m has no sanity range (OQ-053); its values are not range-checked` | 1 | 1 |

The warning is per layer and technology, not per cell; the cells it left unchecked are all the wind candidate cells: PRT 3,369 / 3,496 / 3,558 (restrictive / central / permissive) and IND 56,190 / 62,718 / 65,454. Solar produced no warning.

## 2. What was changed

| Step | Change |
|---|---|
| 3 METHODOLOGY 15.0.0 | Header and one changelog row that replaces the 14.2.0 row and describes the current content. Items: density at every altitude with the ISA consistency check (M-F5-03, M-F5-06), the 3000 m exclusion (M-F2b-06, M-F3-04), the Weibull flag (M-F5-06), `t_ref` 2024, regional IRENA 2024 real after-tax discount rate, integer lifetime 25 to 30 (M-F6-07, U-03), T-R6 and M-F6-06 wording for the altitude sensitivity. |
| 3a density | `geofrea/technical_potential/density_check.py`: `isa_density_ratio` = `rho_ref / rho_ISA(z + H)` with the ISO 2533 density (`siting_layers/sanity.isa_density_kg_m3`), bounds 0.90 and 1.10. F5 computes it per candidate cell, logs the counts as information and writes `density_ratio_isa` and `density_outside_isa_check` in the class-flag table. Never an error, nothing removed. The correction itself was already applied at every altitude; a test now proves it is not truncated (CF at 0.5 of the curve density equals the CF at the curve density with the scale times `0.5^(1/3)`). |
| 3b exclusion | See 1a. |
| 4 parameters.json | `discount_rate` for the six cases (tier 2, range tier 3, uniform, IRENA 2025 Figure 1.13, `price_year` 2024, `proxy` false, `verified` false); `commissioning_year` 2024; `lifetime_years` 30 with `discrete_uniform` on 25 to 30, range tier 2 as in the .tex (the previous range tier was 3, 'author judgment'; the .tex says Tier 2 for value and range); `discount_rate_increment` source and note updated (its `verified` flag, set by the author earlier, is unchanged); capex notes no longer speak of a 2026 vintage. |
| 4 sampler and loader | `ParameterRange.distribution` accepts `discrete_uniform` (integer bounds enforced); `UncertainSpec` and `_transform` in `lcoe_modeling/sampling.py` draw the integers 25..30 with equal probability from the Latin hypercube strata; the design-matrix rounding is a no-op for it. |
| 5 OQ-053 | `audit.yaml` `derived_ranges.weibull_a/weibull_k.flag_range` (A [1, 15], k [1, 4], tier 3) as a flag, not a checked range: `count_outside_flag_range` marks and counts, the log line is information, `weibull_outside_flag_range` is a column of the class-flag table. The same numbers apply to the 150 m and 200 m layers (the command named only the 100 m layer; without this the other two layers would keep warning and no run could be clean); this extension is for the author to confirm. Cells outside the range exist (table below), so the ranges were not changed and OQ-053 stays open. |
| 6 class flag | `class_flag_<tech>__<scenario>` are registered artifacts of `technical_potential` only for a technology whose registry entry has a `class_flag` (wind), computed in `main._build_phase_specs`; solar has none, so the phase contract is not uniform. Schema version of the table 1.0 to 1.1. |
| 8 LIMITATIONS | L-025 rewritten for the exclusion; L-028 and L-030 say 2024; L-034 and L-035 RETIRED (not deleted) and replaced by L-042 (the 2024-vintage counterfactual); L-039 (discrete lifetime), L-040 (regional WACC, Asian value likely low for India), L-041 (PV connection on the plant side only, wind undefined); new L-043 (Weibull flag), and Tier 3 rows L-207 (lifetime), L-209 (discount-rate range), L-210 (3000 m), L-211 (Weibull flag). |
| 9 records | OQ-022 and OQ-059 removed from `OPEN_QUESTIONS.md` and closed in the F6 (D-F6-022) and F5 (D-F5-025) records; OQ-053 rewritten and kept (step 5 case); OQ-058 rewritten and kept; D-F3-015 in the F3 record. |
| 10 PROGRESS.json | `executed_real` does not appear (it was never written; the first-round state uses `ran_with_issues`/`not_run`). `methodology_version` 15.0.0; F3, F5 and F6 summaries updated. |
| 11 bibliography | `docs/thesis/references_stage_r.bib` did not exist in the repository. It was built from the author's `references_cleaned.bib` (Downloads, 2026-10-16): the 23 cited entries copied unchanged. The .tex also cite `bryantlempert2010` and `friedmanfisher1999`, which that file does not have; two entries were added from my knowledge and carry a `note` asking for a check before submission. All 25 `\cite` keys of the three .tex exist in the new file (`D:/tmp_diag/cites46.py`). |

## 3. Weibull cells outside the Tier 3 flag range (step 5, not changed)

Wind candidate tables of the first real run (F3 outputs, before the 3000 m rule), A in [1, 15] m/s and k in [1, 4]; cells below / above, minimum and maximum in brackets.

| Country / scenario | Cells | A 100 m | k 100 m | A 150 m | k 150 m | A 200 m | k 200 m |
|---|---|---|---|---|---|---|---|
| PRT/restrictive | 3369 | 0 / 0 (2.97-9.99) | 0 / 0 (1.03-2.67) | 0 / 0 (3.17-10.47) | 0 / 0 (1.01-2.61) | 0 / 0 (3.30-10.82) | 2 / 0 (0.99-2.55) |
| PRT/central | 3496 | 0 / 0 (2.93-9.98) | 0 / 0 (1.03-2.67) | 0 / 0 (3.14-10.47) | 0 / 0 (1.01-2.61) | 0 / 0 (3.29-10.92) | 2 / 0 (0.99-2.56) |
| PRT/permissive | 3558 | 0 / 0 (2.91-9.97) | 0 / 0 (1.03-2.68) | 0 / 0 (3.12-10.47) | 0 / 0 (1.01-2.61) | 0 / 0 (3.27-10.92) | 2 / 0 (0.99-2.56) |
| IND/restrictive | 56190 | 0 / 0 (1.36-11.12) | 57 / 0 (0.79-3.43) | 0 / 0 (1.51-11.43) | 58 / 0 (0.79-3.27) | 0 / 0 (1.62-12.10) | 53 / 0 (0.79-3.14) |
| IND/central | 62718 | 1 / 0 (0.88-11.44) | 220 / 0 (0.78-3.43) | 0 / 0 (1.03-11.78) | 211 / 0 (0.78-3.26) | 0 / 0 (1.15-12.11) | 205 / 0 (0.78-3.14) |
| IND/permissive | 65454 | 7 / 0 (0.81-11.67) | 315 / 0 (0.73-3.43) | 1 / 0 (0.92-11.98) | 308 / 0 (0.73-3.26) | 0 / 0 (1.04-12.21) | 294 / 0 (0.73-3.14) |
| BRA/restrictive | 175154 | 0 / 0 (1.50-13.36) | 9 / 2594 (0.85-4.96) | 0 / 0 (1.72-14.24) | 9 / 1039 (0.87-4.64) | 0 / 0 (1.88-14.84) | 9 / 442 (0.87-4.45) |
| BRA/central | 181277 | 0 / 0 (1.50-13.01) | 20 / 2604 (0.85-4.96) | 0 / 0 (1.70-13.92) | 21 / 1035 (0.87-4.65) | 0 / 0 (1.79-14.54) | 22 / 437 (0.87-4.45) |
| BRA/permissive | 183324 | 0 / 0 (1.50-12.91) | 22 / 2589 (0.86-4.97) | 0 / 0 (1.67-13.83) | 23 / 1027 (0.87-4.66) | 0 / 0 (1.77-14.48) | 24 / 439 (0.88-4.46) |

Reading: PRT has no cell outside at 100 m (two with k just below 1 at 200 m). IND has 220 central cells with k below 1 (down to 0.78) and one with A below 1. BRA has 2,604 central cells with k above 4 (up to 4.96) and 20 with k below 1. No cell has A above 15 m/s. The flag counts them and changes no result; the author decides whether to widen k, source the range or keep it (OQ-053).

## 4. Verification

- **Suite:** 1383 passed, 4 warnings in 745 s (12 min 25 s), full suite on branch stage-r/fix-46 (0 failures).
- **Loader validator** (`audit_parameters`, `D:/tmp_diag/validator46.py`), PRT, IND and BRA, solar and wind:

```
PRT errors 14 warnings 6
   F5 pending: none
   F6 pending: ['degradation_rate', 'grid_cost_usd_per_mw_km', 'road_cost_usd_per_km', 'substation_cost_usd_per_mw'] | other F6 keys: none
   F7 pending: ['cf_min', 'tau_lcoe_usd_per_mwh', 'top_k_percent']
   warning: PRT solar discount_rate: Tier 3 range (U-07)
   warning: PRT solar luf: Tier 3 value (U-07)
   warning: PRT wind discount_rate: Tier 3 range (U-07)
   warning: PRT wind luf: Tier 3 value (U-07)
   warning: PRT wind eta_loss: Tier 3 value (U-07)
   warning: PRT wind eta_loss: Tier 3 range (U-07)
IND errors 14 warnings 7
   F5 pending: none
   F6 pending: ['degradation_rate', 'grid_cost_usd_per_mw_km', 'road_cost_usd_per_km', 'substation_cost_usd_per_mw'] | other F6 keys: none
   F7 pending: ['cf_min', 'tau_lcoe_usd_per_mwh', 'top_k_percent']
   warning: IND solar discount_rate: Tier 3 range (U-07)
   warning: IND solar luf: Tier 3 value (U-07)
   warning: IND wind opex_fixed_frac: Tier 3 range (U-07)
   warning: IND wind discount_rate: Tier 3 range (U-07)
   warning: IND wind luf: Tier 3 value (U-07)
   warning: IND wind eta_loss: Tier 3 value (U-07)
   warning: IND wind eta_loss: Tier 3 range (U-07)
BRA errors 14 warnings 7
   F5 pending: none
   F6 pending: ['degradation_rate', 'grid_cost_usd_per_mw_km', 'road_cost_usd_per_km', 'substation_cost_usd_per_mw'] | other F6 keys: none
   F7 pending: ['cf_min', 'tau_lcoe_usd_per_mwh', 'top_k_percent']
   warning: BRA solar discount_rate: Tier 3 range (U-07)
   warning: BRA solar luf: Tier 3 value (U-07)
   warning: BRA wind opex_fixed_frac: Tier 3 range (U-07)
   warning: BRA wind discount_rate: Tier 3 range (U-07)
   warning: BRA wind luf: Tier 3 value (U-07)
   warning: BRA wind eta_loss: Tier 3 value (U-07)
   warning: BRA wind eta_loss: Tier 3 range (U-07)
```

  F5: no pending item in the three countries. F6: pending only the Group 3 values and the degradation (`degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`); `discount_rate` is recorded. The F7 values (`cf_min`, `tau_lcoe_usd_per_mwh`, `top_k_percent`) are F7 items and stay open. The Tier 3 warnings are the declared Tier 3 values (U-07).
- **.tex against `parameters.json`** (`D:/tmp_diag/tex_vs_params46.py`, 98 comparisons): LUF triples, power densities, retention, gamma, hub height, CAPEX (mean, range, and `P5` / `2 mean - P5`), fixed O&M fractions and ranges, variable O&M, discount rates and ranges, lifetime, `t_ref`: 0 divergences.
- **New tests:** ISA ratio at 0 m and 4000 m, a sea-level density on a 4000 m cell outside the check, bounds 0.90/1.10 and non-finite values; density correction not truncated (5 density ratios from 0.5 to 1.05); wind-only exclusion above 3000 m in F3 (solar keeps the high cells, restrictive/central/permissive all filtered, the cells stay in the cell tables); lifetime draw (10,000 draws, each year 1/6 within 1 percentage point, nothing else drawn); discrete uniform needs integer bounds; the validator with `discount_rate` filled; the Weibull flag ranges (values, every height, marking and counting without removal or warning). Tests that described the previous state were rewritten: the altitude-sensitivity machinery of F5, F6 and F7 is still exercised on a copy of the configuration that reports a sensitivity instead of excluding.

## 5. For the author

1. **OQ-053:** the flag range leaves 220 (IND) and 2,604 (BRA) central cells outside at 100 m. Decide: keep, widen k, or source.
2. **Confirm the extension of the Weibull flag range to the 150 m and 200 m layers.** It is what lets a run have no warning.
3. **The 3000 m rule is technology-wide** (it changes India only). The country-specific alternative was not chosen.
4. **F3 must be run again for IND wind**, then F5 in PRT, IND and BRA in one round (the clean round).
5. **`references_stage_r.bib`:** two entries added by me (PRIM references) need a check.
6. **Lifetime range tier:** set to 2 to match the .tex (it was 3 before).
