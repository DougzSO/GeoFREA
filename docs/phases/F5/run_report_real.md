# F5 on real data: run report (PRT, IND and BRA in one round)

Run of 2026-10-16/17 on `main` at commit `d6f4725` (METHODOLOGY 15.0.1, `parameters.json` and code as committed; nothing was changed after the commit). Inputs: the F3 outputs of this round and the F4 outputs already in `GEOFREA_DATA_DIR` (`D:\Douglas\DOUTORADO\GeoFREA_data`). The run is a development run (a production run is refused while the F6 parameters are open); the turbine curve is the real IEA 3.4-130 table. This report replaces the one of the first run (PRT and IND only, 14.2.0), which stopped at OQ-059.

## 1. Status

| Country | F3 | F5 solar and wind | Sanity checks | Warnings of the F5 log | Run status (CONVENTIONS) |
|---|---|---|---|---|---|
| PRT | run again, no warning | done | 15 of 15 pass | 0 | F5 `ran_clean` |
| IND | run again, no warning | done | 15 of 15 pass | 0 | F5 `ran_clean` |
| BRA | run again, no warning | done | 15 of 15 pass | 0 | F5 `ran_clean` |

The three countries ran in the same round, in the order PRT, IND, BRA, and every check passed before the next one started. No code and no parameter was changed after the commit. One finding is reported in section 4 (cells without elevation) and opened as OQ-060; it does not fail a check of the command.

## 2. How the round ran

- **Free commit memory before running** (command 50, step 1): limit 16.92 GB, used 7.98 GB, free 8.94 GB (at least 6 GB required). Physical memory free was 1.8 GB. The first attempt of the previous round had failed with 3.2 GB of free commit.
- **F3:** `main.py --phases land_eligibility`. The resume check of the manifest did not notice the change of `experiments.yaml` (the phase was resumed as `success`), so `--rerun land_eligibility` was used in the three countries. F3 of BRA: 574 s, peak resident memory 4.39 GB, `land_eligibility = success` in the manifest. The two earlier attempts had stopped with `MemoryError` while loading the fraction cache (2.76 GB resident, 3.2 GB of free commit).
- **F5:** `main.py --phases technical_potential,potential_maps --rerun` in the same process for each country, then the sanity and plausibility script, which works member by member (it never holds all the members).

### F3 before and after the rule of 3000 m (wind candidates, by country and scenario)

Before: outputs of the first real round (copied before running F3 again). After: this round. Area is the eligible area of the candidate cells.

| Country | Scenario | Cells before | Cells after | Area before, km2 | Area after, km2 | Highest elevation before, m | after, m |
|---|---|---|---|---|---|---|---|
| PRT | restrictive | 3,369 | 3,369 | 17,554.6 | 17,554.6 | 1356 | 1356 |
| PRT | central | 3,496 | 3,496 | 28,131.6 | 28,131.6 | 1351 | 1351 |
| PRT | permissive | 3,558 | 3,558 | 35,243.2 | 35,243.2 | 1350 | 1350 |
| IND | restrictive | 56,190 | 55,219 | 354,386.9 | 353,921.3 | 6119 | 2836 |
| IND | central | 62,718 | 61,366 | 509,049.5 | 507,112.0 | 6218 | 2992 |
| IND | permissive | 65,454 | 64,009 | 597,964.5 | 590,149.4 | 6224 | 2999 |
| BRA | restrictive | 175,154 | 175,154 | 1,436,798.7 | 1,436,798.7 | 1922 | 1922 |
| BRA | central | 181,277 | 181,276 | 2,195,742.8 | 2,195,742.7 | 1907 | 1907 |
| BRA | permissive | 183,324 | 183,323 | 2,626,407.7 | 2,626,407.6 | 1904 | 1904 |

Solar candidates (cells and area) are the same before and after in the three countries. Identity of the files by content (the file bytes always differ, because they carry the metadata of the run):

| Country | Files | Same content | Different content |
|---|---|---|---|
| PRT | 23 | 23 | none |
| IND | 23 | 16 | candidate_stability_wind.parquet, candidates_wind__central.parquet, candidates_wind__permissive.parquet, candidates_wind__restrictive.parquet, cells_wind__central.parquet, cells_wind__permissive.parquet, cells_wind__restrictive.parquet |
| BRA | 23 | 19 | candidates_wind__central.parquet, candidates_wind__permissive.parquet, cells_wind__central.parquet, cells_wind__permissive.parquet |

PRT is identical in all 23 files. IND changes only in the wind candidates and cells (7 files), as expected. **BRA was expected to be identical and is not**: 4 files (wind, central and permissive) differ by one candidate, cell 14287116 (lat -9.225, lon -64.175, 0.128 km2 central), which has no elevation in the DEM (NaN). See section 4.

## 3. Time and memory

| Country | F5 + maps, s | Peak working set, MB | 150 m wind sensitivity (checks script), s |
|---|---|---|---|
| PRT | 16 | 367 | 10 |
| IND | 209 | 1584 | 181 |
| BRA | 606 | 3364 | 542 |

BRA: 606 s and a peak working set of 3,364 MB (the 150 m sensitivity is a second F5 call for wind). The IND sensitivity with the cells above 3000 m took 189 s (section 5.7).

## 4. Sanity checks

### PRT

| Check | Result | Detail |
|---|---|---|
| rho_ref_over_rho_isa | PASS | blocks only above 0.1% of the eligible cells; central: 0 of 3496 eligible cells outside [0.9, 1.1] (0.0000%), range [0.986, 0.999], P1 0.986, P99 0.998; restrictive: 0 of 3369 eligible cells outside [0.9, 1.1] (0.0000%), range [0.985, 0.999], P1 0.986, P99 0.998; permissive: 0 of 3558 eligible cells outside [0.9, 1.1] (0.0000%), range [0.986, 0.999], P1 0.986, P99 0.998 |
| weibull_validity_limits | PASS | cells outside A in (0, 25] and k in (0, 10] at 100, 150 and 200 m, three scenarios: 0 |
| cf_range_nan_solar_central | PASS | rows 127502, cells 3446, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1558, 0.2073], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_restrictive | PASS | rows 124172, cells 3356, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1565, 0.2074], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_permissive | PASS | rows 128982, cells 3486, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1561, 0.2073], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_central | PASS | rows 108376, cells 3496, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0688, 0.5353], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_restrictive | PASS | rows 104439, cells 3369, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0691, 0.5353], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_permissive | PASS | rows 110298, cells 3558, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0675, 0.5354], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| pv_thermal_factor | PASS | 1+gamma*dT over 128982 cell-members, member by member: [0.98300, 1.00000] (gamma -0.003) |
| delta_rsds_range | PASS | delta_rsds [0.9887, 1.1537]; F4 declares no validity range for delta_rsds (only wind_factor_valid_range [0.5, 1.5] for delta_wind), observed range reported; share outside [0.9, 1.1]: 1.3793% |
| cf_net_over_gross | PASS | max \|CF_net/CF_gross - 0.866\| = 1.11e-16 over 323113 wind cell-members, member by member (gross computed again outside the pipeline; 0 with zero gross CF, net also zero) |
| no_wind_cell_above_3000m | PASS | central: max elevation of the cells with potential 1351 m, above 3000 m: 0, cells with no elevation (NaN): 0; restrictive: max elevation of the cells with potential 1356 m, above 3000 m: 0, cells with no elevation (NaN): 0; permissive: max elevation of the cells with potential 1350 m, above 3000 m: 0, cells with no elevation (NaN): 0 |
| capacity_20_cells | PASS | solar/central: LUF 0.25, PD 50.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/restrictive: LUF 0.1, PD 45.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/permissive: LUF 0.35, PD 75.0, 20 cells, max \|dP\| 0.00e+00 MW; wind/central: LUF 0.15, PD 4.99, 20 cells, max \|dP\| 0.00e+00 MW; wind/restrictive: LUF 0.05, PD 3.32, 20 cells, max \|dP\| 0.00e+00 MW; wind/permissive: LUF 0.3, PD 7.12, 20 cells, max \|dP\| 0.00e+00 MW |
| sens150_no_phase_warning | PASS | warnings in the 150 m run: 0  |
| sens150_cf_range | PASS | 150 m: CF [0.0835, 0.5589], NaN 0 |

For information (not a criterion of this round): rho/rho0 at hub height, reference [0.862, 0.989], warmest member [0.846, 0.975]. rho_ref / rho_ISA(z + H), central: 0.986 to 0.999, 0 cells outside 0.90 to 1.10; candidate cells with no elevation: 0.

### IND

| Check | Result | Detail |
|---|---|---|
| rho_ref_over_rho_isa | PASS | blocks only above 0.1% of the eligible cells; central: 0 of 61366 eligible cells outside [0.9, 1.1] (0.0000%), range [0.926, 0.999], P1 0.930, P99 0.955; restrictive: 0 of 55219 eligible cells outside [0.9, 1.1] (0.0000%), range [0.925, 0.974], P1 0.930, P99 0.950; permissive: 0 of 64009 eligible cells outside [0.9, 1.1] (0.0000%), range [0.924, 0.989], P1 0.930, P99 0.957 |
| weibull_validity_limits | PASS | cells outside A in (0, 25] and k in (0, 10] at 100, 150 and 200 m, three scenarios: 0 |
| cf_range_nan_solar_central | PASS | rows 2004734, cells 54182, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1178, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_restrictive | PASS | rows 1793982, cells 48486, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1251, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_permissive | PASS | rows 2074109, cells 56057, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1158, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_central | PASS | rows 1902346, cells 61366, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0002, 0.5239], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_restrictive | PASS | rows 1711789, cells 55219, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0004, 0.5239], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_permissive | PASS | rows 1984279, cells 64009, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0000, 0.5682], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| pv_thermal_factor | PASS | 1+gamma*dT over 2074109 cell-members, member by member: [0.97758, 1.00000] (gamma -0.003) |
| delta_rsds_range | PASS | delta_rsds [0.8366, 1.1906]; F4 declares no validity range for delta_rsds (only wind_factor_valid_range [0.5, 1.5] for delta_wind), observed range reported; share outside [0.9, 1.1]: 0.1872% |
| cf_net_over_gross | PASS | max \|CF_net/CF_gross - 0.866\| = 1.11e-16 over 5598414 wind cell-members, member by member (gross computed again outside the pipeline; 0 with zero gross CF, net also zero) |
| no_wind_cell_above_3000m | PASS | central: max elevation of the cells with potential 2992 m, above 3000 m: 0, cells with no elevation (NaN): 0; restrictive: max elevation of the cells with potential 2836 m, above 3000 m: 0, cells with no elevation (NaN): 0; permissive: max elevation of the cells with potential 2999 m, above 3000 m: 0, cells with no elevation (NaN): 0 |
| capacity_20_cells | PASS | solar/central: LUF 0.1, PD 50.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/restrictive: LUF 0.05, PD 45.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/permissive: LUF 0.25, PD 75.0, 20 cells, max \|dP\| 0.00e+00 MW; wind/central: LUF 0.075, PD 4.99, 20 cells, max \|dP\| 0.00e+00 MW; wind/restrictive: LUF 0.05, PD 3.32, 20 cells, max \|dP\| 0.00e+00 MW; wind/permissive: LUF 0.15, PD 7.12, 20 cells, max \|dP\| 0.00e+00 MW |
| sens150_no_phase_warning | PASS | warnings in the 150 m run: 0  |
| sens150_cf_range | PASS | 150 m: CF [0.0007, 0.5647], NaN 0 |

For information (not a criterion of this round): rho/rho0 at hub height, reference [0.710, 0.944], warmest member [0.693, 0.926]. rho_ref / rho_ISA(z + H), central: 0.926 to 0.999, 0 cells outside 0.90 to 1.10; candidate cells with no elevation: 0.

### BRA

| Check | Result | Detail |
|---|---|---|
| rho_ref_over_rho_isa | PASS | blocks only above 0.1% of the eligible cells; central: 0 of 181276 eligible cells outside [0.9, 1.1] (0.0000%), range [0.936, 0.989], P1 0.939, P99 0.981; restrictive: 0 of 175154 eligible cells outside [0.9, 1.1] (0.0000%), range [0.936, 0.989], P1 0.939, P99 0.981; permissive: 0 of 183323 eligible cells outside [0.9, 1.1] (0.0000%), range [0.936, 0.989], P1 0.939, P99 0.981 |
| weibull_validity_limits | PASS | cells outside A in (0, 25] and k in (0, 10] at 100, 150 and 200 m, three scenarios: 0 |
| cf_range_nan_solar_central | PASS | rows 6661517, cells 180041, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1175, 0.2221], absent cell-members 0 (declared masked in F4: 42947 rows of the file) |
| cf_range_nan_solar_restrictive | PASS | rows 6432080, cells 173840, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1204, 0.2222], absent cell-members 0 (declared masked in F4: 42947 rows of the file) |
| cf_range_nan_solar_permissive | PASS | rows 6730189, cells 181897, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1175, 0.2221], absent cell-members 0 (declared masked in F4: 42947 rows of the file) |
| cf_range_nan_wind_central | PASS | rows 5611070, cells 181276, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0018, 0.7353], absent cell-members 8486 (declared masked in F4: 42947 rows of the file) |
| cf_range_nan_wind_restrictive | PASS | rows 5422369, cells 175154, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0018, 0.7429], absent cell-members 7405 (declared masked in F4: 42947 rows of the file) |
| cf_range_nan_wind_permissive | PASS | rows 5674113, cells 183323, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0018, 0.7357], absent cell-members 8900 (declared masked in F4: 42947 rows of the file) |
| pv_thermal_factor | PASS | 1+gamma*dT over 6730189 cell-members, member by member: [0.97831, 1.00291] (gamma -0.003) |
| delta_rsds_range | PASS | delta_rsds [0.9238, 1.1138]; F4 declares no validity range for delta_rsds (only wind_factor_valid_range [0.5, 1.5] for delta_wind), observed range reported; share outside [0.9, 1.1]: 0.0284% |
| cf_net_over_gross | PASS | max \|CF_net/CF_gross - 0.866\| = 1.11e-16 over 16707552 wind cell-members, member by member (gross computed again outside the pipeline; 0 with zero gross CF, net also zero) |
| no_wind_cell_above_3000m | PASS | central: max elevation of the cells with potential 1907 m, above 3000 m: 0, cells with no elevation (NaN): 0; restrictive: max elevation of the cells with potential 1922 m, above 3000 m: 0, cells with no elevation (NaN): 0; permissive: max elevation of the cells with potential 1904 m, above 3000 m: 0, cells with no elevation (NaN): 0 |
| capacity_20_cells | PASS | solar/central: LUF 0.25, PD 50.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/restrictive: LUF 0.1, PD 45.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/permissive: LUF 0.35, PD 75.0, 20 cells, max \|dP\| 0.00e+00 MW; wind/central: LUF 0.15, PD 4.99, 20 cells, max \|dP\| 0.00e+00 MW; wind/restrictive: LUF 0.05, PD 3.32, 20 cells, max \|dP\| 0.00e+00 MW; wind/permissive: LUF 0.3, PD 7.12, 20 cells, max \|dP\| 0.00e+00 MW |
| sens150_no_phase_warning | PASS | warnings in the 150 m run: 0  |
| sens150_cf_range | PASS | 150 m: CF [0.0040, 0.7532], NaN 0 |

For information (not a criterion of this round): rho/rho0 at hub height, reference [0.780, 0.978], warmest member [0.765, 0.965]. rho_ref / rho_ISA(z + H), central: 0.936 to 0.989, 0 cells outside 0.90 to 1.10; candidate cells with no elevation: 0.

### Finding: cells without elevation (OQ-060)

The rule of 3000 m is implemented as `elevation <= limit`, which is false when the DEM has no value for the cell (NaN, eligible-area-weighted mean over no valid pixel). Those cells left the wind candidates, although there is no evidence that they are above 3000 m. Candidates removed with NaN elevation, before the rule (central; restrictive and permissive in brackets):

| Country | Cells removed in total | of which NaN elevation | Area of the NaN cells, km2 |
|---|---|---|---|
| PRT | 0 | 0 (0, 0) | 0 |
| IND | 1,352 | 36 (26, 38) | 35.7 (25.6, 44.0) |
| BRA | 0 | 1 (0, 1) | 0.128 (0, 0.161) |

So the cells really above 3000 m in IND are 1,316 in the central scenario (0.71 GW and 1.11 TWh/yr in the reference member), not 1,352. The effect on the totals is tiny (0.007% of the Indian and 0.00001% of the Brazilian central eligible wind area). The command asked to stop on an unexpected result and the author said to go on, so the rule was left as it is and the question is OQ-060 (a correction is two lines in F3 plus a new F3 run).

## 5. Plausibility (reported and not adjusted)

### 5.1 Capacity factor, reference member, central scenario

P5, P50 and P95 over the candidate cells, unweighted and weighted by capacity. Reference values: IRENA (2025), Renewable Power Generation Costs in 2024: PV global weighted average 17.4% (AC energy over DC capacity, no country value); onshore wind of projects commissioned in 2024, India 39% and Brazil 56% (no value for Portugal). Fleet CF is generation over mean installed capacity over the 8,784 hours of 2024 (India: FY2023-24).

| Country | Tech | P5 / P50 / P95 unweighted | P5 / P50 / P95 capacity-weighted | Weighted mean | IRENA 2024 | Fleet CF (year) |
|---|---|---|---|---|---|---|
| PRT | solar | 16.6% / 18.1% / 19.1% | 17.2% / 18.5% / 19.1% | 18.3% | 17.4% (global) | 16.9% (2024) |
| PRT | wind | 15.5% / 25.9% / 36.2% | 17.2% / 26.8% / 35.0% | 26.6% | n.r. | 27.8% (2024) |
| IND | solar | 17.1% / 18.2% / 20.0% | 17.5% / 19.1% / 20.1% | 18.9% | 17.4% (global) | not formed |
| IND | wind | 4.3% / 14.8% / 27.4% | 8.6% / 17.6% / 28.9% | 18.0% | 39% | 22.4% (FY2023-24, low confidence) |
| BRA | solar | 16.4% / 18.2% / 19.8% | 16.8% / 18.6% / 20.0% | 18.5% | 17.4% (global) | 18.6% (2024) |
| BRA | wind | 2.6% / 11.6% / 32.2% | 4.9% / 14.0% / 34.0% | 16.0% | 56% | 42.1% (2024) |

| Country | Tech | Generation, GWh | Mean capacity, MW | Fleet CF | Source |
|---|---|---|---|---|---|
| PRT | wind | 14,453 | 5,916 | 27.8% | DGEG, Estatisticas rapidas das renovaveis, dezembro/2024 (publicacao 241): wind 14,453 GWh in 2024; installed 5,893 MW (2023) and 5,938 MW (2024); provisional |
| PRT | solar | 7,098 | 4,780 | 16.9% | same DGEG report: PV 7,098 GWh in 2024 (includes self-consumption units); installed 3,896 MW (2023) and 5,664 MW (2024) |
| BRA | wind | 107,654 | 29,100 | 42.1% | EPE, Anuario Estatistico de Energia Eletrica 2025 (base year 2024), factsheet: wind 107,654 GWh; installed 29,550 MW at end of 2024, +0.9 GW in the year |
| BRA | solar | 70,665 | 43,168 | 18.6% | same EPE factsheet: solar 70,665 GWh (about 58% distributed generation); 48,468 MW at end of 2024, +10.6 GW in the year |
| IND | wind | 83,385 | 42,313 | 22.4% | CEA via Saur Energy: wind 83,385 MU in FY2023-24; MNRE cumulative 40,686 MW (31.03.2023) and 43,940 MW (31.03.2024) from a search snippet, not read on the MNRE page (low confidence) |

India solar has no consistent fleet CF (the MNRE capacity and the CEA generation are on different scopes). The bibliography keys of the sources (`epeAnuario2025`, `ceaGeneration`, `dgegRenewables`) are in `references_stage_r.bib`.

**Reading of Brazil.** The wind CF is low in the all-land statistics (weighted mean 16.0%, P50 11.6%, P95 32.2%) against the fleet's 42% and IRENA's 56%, but the candidate set is all the eligible land, mostly Amazon and Cerrado with little wind. The best cells are the fleet's: 2,824 cells (33.1 GW, 2.0% of the central capacity) have CF of 40% or more, about the installed fleet (29.6 GW), and the maximum is 73.5%. Solar is at the fleet value (18.5% against 18.6%, which includes distributed generation). No result is implausible by the rule of the command, so no OQ was opened for it.

### 5.2 Technical potential by land scenario (reference member)

| Country | Tech | Scenario | Eligible area, km2 | GW | TWh/yr | CF (energy-weighted) |
|---|---|---|---|---|---|---|
| PRT | solar | restrictive | 15,696 | 70.6 | 113.6 | 18.4% |
| PRT | solar | central | 21,162 | 264.5 | 424.7 | 18.3% |
| PRT | solar | permissive | 24,046 | 631.2 | 1,012.9 | 18.3% |
| PRT | wind | restrictive | 17,555 | 2.9 | 6.9 | 27.2% |
| PRT | wind | central | 28,132 | 21.1 | 49.0 | 26.6% |
| PRT | wind | permissive | 35,243 | 75.3 | 172.6 | 26.2% |
| IND | solar | restrictive | 104,623 | 235.4 | 391.0 | 19.0% |
| IND | solar | central | 145,679 | 728.4 | 1,208.3 | 18.9% |
| IND | solar | permissive | 165,693 | 3,106.7 | 5,150.4 | 18.9% |
| IND | wind | restrictive | 353,921 | 58.8 | 94.6 | 18.4% |
| IND | wind | central | 507,112 | 189.8 | 299.4 | 18.0% |
| IND | wind | permissive | 590,149 | 630.3 | 981.1 | 17.8% |
| BRA | solar | restrictive | 1,067,243 | 4,802.6 | 7,796.5 | 18.5% |
| BRA | solar | central | 1,535,078 | 19,188.5 | 31,068.5 | 18.5% |
| BRA | solar | permissive | 1,767,254 | 46,390.4 | 75,033.8 | 18.5% |
| BRA | wind | restrictive | 1,436,799 | 238.5 | 345.0 | 16.5% |
| BRA | wind | central | 2,195,743 | 1,643.5 | 2,297.3 | 16.0% |
| BRA | wind | permissive | 2,626,408 | 5,610.0 | 7,727.8 | 15.7% |

Permissive over restrictive:

| Country | Tech | GW ratio | TWh ratio | area x LUF x PD |
|---|---|---|---|---|
| PRT | solar | 8.9 | 8.9 | area 1.53 x LUF 3.50 x PD 1.67 = 8.9 |
| PRT | wind | 25.8 | 24.9 | area 2.01 x LUF 6.00 x PD 2.14 = 25.8 |
| IND | solar | 13.2 | 13.2 | area 1.58 x LUF 5.00 x PD 1.67 = 13.2 |
| IND | wind | 10.7 | 10.4 | area 1.67 x LUF 3.00 x PD 2.14 = 10.7 |
| BRA | solar | 9.7 | 9.6 | area 1.66 x LUF 3.50 x PD 1.67 = 9.7 |
| BRA | wind | 23.5 | 22.4 | area 1.83 x LUF 6.00 x PD 2.14 = 23.5 |

The ratios are the product of the three factors, as the method intends (U-06). Brazil's central potential is 19.2 TW of PV and 1.64 TW of wind, from 1.5 and 2.2 million km2 of eligible land at the residual utilization and power density of `parameters.json`; they are technical potentials and are not compared with installed capacity.

### 5.3 Share of the wind potential above the class limit (reference member)

| Country | Scenario | Cells flagged | Capacity share | Energy share | V_ave P50, m/s | V_ave max, m/s |
|---|---|---|---|---|---|---|
| PRT | restrictive | 69 of 3369 | 0.79% | 1.24% | 5.89 | 8.86 |
| PRT | central | 66 of 3496 | 0.74% | 1.19% | 5.83 | 8.85 |
| PRT | permissive | 64 of 3558 | 0.68% | 1.12% | 5.80 | 8.85 |
| IND | restrictive | 46 of 55219 | 0.05% | 0.11% | 4.83 | 8.68 |
| IND | central | 43 of 61366 | 0.04% | 0.09% | 4.74 | 8.68 |
| IND | permissive | 46 of 64009 | 0.04% | 0.08% | 4.70 | 9.58 |
| BRA | restrictive | 2476 of 175154 | 1.92% | 5.30% | 4.50 | 11.97 |
| BRA | central | 2401 of 181276 | 1.75% | 5.00% | 4.43 | 11.66 |
| BRA | permissive | 2381 of 183323 | 1.70% | 4.91% | 4.41 | 11.57 |

### 5.4 Wind capacity factor at 100 m and at 150 m (reference member, central)

| Country | CF difference (150 m minus 100 m) P5 / P50 / P95 | Relative difference P5 / P50 / P95 | CF at 150 m P5 / P50 / P95 | TWh/yr at 100 m | at 150 m |
|---|---|---|---|---|---|
| PRT | +0.025 / +0.053 / +0.075 | 9% / 21% / 31% | 19.0% / 31.6% / 41.3% | 49.0 | 59.0 |
| IND | +0.017 / +0.056 / +0.077 | 18% / 38% / 58% | 6.3% / 20.6% / 33.8% | 299.4 | 400.6 |
| BRA | +0.020 / +0.050 / +0.084 | 20% / 44% / 97% | 4.9% / 16.7% / 39.9% | 2297.3 | 3098.7 |

### 5.5 Change by member against the reference (central scenario)

**PRT solar**: change of energy from -0.46% to +7.11% over 36 members (like-for-like); median cell ratio from 0.995 to 1.069.

**PRT wind**: change of energy from -9.84% to +6.78% over 30 members (like-for-like); median cell ratio from 0.900 to 1.077.

**IND solar**: change of energy from -6.53% to +3.43% over 36 members (like-for-like); median cell ratio from 0.931 to 1.043.

**IND wind**: change of energy from -7.40% to +12.38% over 30 members (like-for-like); median cell ratio from 0.937 to 1.158.

**BRA solar**: change of energy from -2.64% to +3.48% over 36 members (like-for-like); median cell ratio from 0.973 to 1.034.

**BRA wind**: change of energy from -3.68% to +48.17% over 30 members (like-for-like); median cell ratio from 0.968 to 1.544.

The member-by-member table is in `D:/tmp_diag/f5_check3_<ISO>.json` (not part of the repository).

### 5.6 Distribution of the Weibull A and k (central wind candidates; information, no warning)

| Country | Var. | Height m | Cells | P1 | P50 | P99 | Min | Max | k < 1 | k > 4 |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT | A | 100 | 3,496 | 4.02 | 6.56 | 8.80 | 2.93 | 9.98 |  |  |
| PRT | A | 150 | 3,496 | 4.41 | 7.28 | 9.38 | 3.14 | 10.47 |  |  |
| PRT | A | 200 | 3,496 | 4.66 | 7.79 | 9.84 | 3.29 | 10.92 |  |  |
| PRT | k | 100 | 3,496 | 1.20 | 2.04 | 2.54 | 1.03 | 2.67 | 0 | 0 |
| PRT | k | 150 | 3,496 | 1.19 | 1.99 | 2.48 | 1.01 | 2.61 | 0 | 0 |
| PRT | k | 200 | 3,496 | 1.18 | 1.96 | 2.44 | 0.99 | 2.56 | 2 | 0 |
| IND | A | 100 | 61,366 | 2.05 | 5.34 | 7.50 | 0.88 | 9.76 |  |  |
| IND | A | 150 | 61,366 | 2.25 | 6.06 | 8.25 | 1.03 | 11.11 |  |  |
| IND | A | 200 | 61,366 | 2.39 | 6.61 | 8.85 | 1.15 | 12.11 |  |  |
| IND | k | 100 | 61,366 | 1.17 | 2.12 | 2.89 | 0.78 | 3.43 | 117 | 0 |
| IND | k | 150 | 61,366 | 1.17 | 2.09 | 2.82 | 0.78 | 3.26 | 115 | 0 |
| IND | k | 200 | 61,366 | 1.16 | 2.05 | 2.76 | 0.78 | 3.14 | 117 | 0 |
| BRA | A | 100 | 181,276 | 2.61 | 4.99 | 8.58 | 1.50 | 13.01 |  |  |
| BRA | A | 150 | 181,276 | 3.10 | 5.65 | 9.37 | 1.70 | 13.92 |  |  |
| BRA | A | 200 | 181,276 | 3.45 | 6.14 | 10.02 | 1.79 | 14.54 |  |  |
| BRA | k | 100 | 181,276 | 1.49 | 2.29 | 4.10 | 0.85 | 4.96 | 20 | 2604 |
| BRA | k | 150 | 181,276 | 1.46 | 2.22 | 3.86 | 0.87 | 4.65 | 21 | 1035 |
| BRA | k | 200 | 181,276 | 1.43 | 2.17 | 3.69 | 0.87 | 4.45 | 22 | 437 |

### 5.7 Comparison with the first real run (PRT and IND)

Content of the potential tables (all members), first run (14.2.0) against this round:

| Country | Tech | Scenario | Rows before | Rows after | Identical | Cells removed | Rest identical |
|---|---|---|---|---|---|---|---|
| PRT | solar | central | 127,502 | 127,502 | yes |  |  |
| PRT | solar | restrictive | 124,172 | 124,172 | yes |  |  |
| PRT | solar | permissive | 128,982 | 128,982 | yes |  |  |
| PRT | wind | central | 108,376 | 108,376 | yes |  |  |
| PRT | wind | restrictive | 104,439 | 104,439 | yes |  |  |
| PRT | wind | permissive | 110,298 | 110,298 | yes |  |  |
| IND | solar | central | 2,004,734 | 2,004,734 | yes |  |  |
| IND | solar | restrictive | 1,793,982 | 1,793,982 | yes |  |  |
| IND | solar | permissive | 2,074,109 | 2,074,109 | yes |  |  |
| IND | wind | central | 1,944,258 | 1,902,346 | no | 1352 | yes |
| IND | wind | restrictive | 1,741,890 | 1,711,789 | no | 971 | yes |
| IND | wind | permissive | 2,029,074 | 1,984,279 | no | 1445 | yes |

PRT and the solar of IND are identical; only the wind of IND changes, by the cells removed (the rest of the rows is identical), as expected. The density criterion of the first run is gone (the density correction applies at every altitude; the check is `rho_ref / rho_ISA(z + H)`).

**IND wind, central scenario, with and without the cells above 3000 m** (the F5 on the F3 candidates of the first round, written apart in `sensitivity_above3000m`; the cells without elevation are in the first figures and out of the second):

| Scenario | GW without | GW with | TWh/yr without | TWh/yr with |
|---|---|---|---|---|
| restrictive | 58.8 | 58.8 | 94.6 | 94.7 |
| central | 189.8 | 190.5 | 299.4 | 300.6 |
| permissive | 630.3 | 638.6 | 981.1 | 993.2 |

The difference also includes the 36 central cells without elevation (2.7% of the 1,352 cells removed); the cells above 3000 m alone are 0.71 GW and 1.11 TWh/yr in the central scenario.

## 6. Reading

- The three countries pass every check and the log of F5 has no warning, so F5 is `ran_clean` in PRT, IND and BRA. The Weibull layers no longer warn (validity limits of OQ-053), and no cell is outside them in any of the three heights.
- Plausibility holds in the three: PV near the fleet value in PRT and BRA, wind below the fleet in IND and BRA because the candidate set is all eligible land and not the best sites (BRA: the best 2% of the capacity reach the fleet's CF); PRT wind brackets the fleet (26.6% weighted mean against 27.8%).
- The 150 m layer raises the wind CF by +0.05 in the median in the three countries.
- OQ-060 (cells without elevation) was the one open point of this round; it was closed on 2026-10-18 (METHODOLOGY 15.0.2, D-F3-018). The numbers of this report are those of the round of 2026-10-17; the solar candidates of IND (14 central cells) and BRA (1) of the later run are in `docs/phases/core/revalidation_52.md`.

## 7. Artifacts

In `GEOFREA_DATA_DIR\outputs\<ISO3>\technical_potential\`: `artifacts\` (potential tables, aggregates, class-flag tables, `weibull_distribution_wind.csv`, COG rasters), `sensitivity_150m\`, `sensitivity_above3000m\` (IND), `figures_run_report\` (one map per potential file). Hashes of every file: `docs/phases/F5/run_real_hashes.json`.

| Country | Map files (one per potential file) |
|---|---|
| PRT | `D:\Douglas\DOUTORADO\GeoFREA_data\outputs\PRT\technical_potential\figures_run_report\potential_<tech>__<scenario>.png` (6 files: solar and wind, three scenarios) |
| IND | `D:\Douglas\DOUTORADO\GeoFREA_data\outputs\IND\technical_potential\figures_run_report\potential_<tech>__<scenario>.png` (6 files: solar and wind, three scenarios) |
| BRA | `D:\Douglas\DOUTORADO\GeoFREA_data\outputs\BRA\technical_potential\figures_run_report\potential_<tech>__<scenario>.png` (6 files: solar and wind, three scenarios) |

The scripts of the run (driver, checks, comparisons) are in the session scratch directory and are not part of the repository.
