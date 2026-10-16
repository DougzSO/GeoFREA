# F5 on real data: run report (PRT and IND; BRA not run)

Run of 2026-10-16 on `main` after commit `5f624d1`. Inputs: the F3 and F4 outputs already in `GEOFREA_DATA_DIR` (`D:\Douglas\DOUTORADO\GeoFREA_data`). No code and no parameter was changed. The run is a development run (`--production` is refused while the F6 parameters are open); the turbine curve is the real IEA 3.4-130 table.

## 1. Status

| Country | F5 solar and wind | Sanity checks (step 2) | Next country |
|---|---|---|---|
| PRT | done | all pass | released |
| IND | done | **1 fails: rho/rho0 down to 0.51 in the Himalayan cells (OQ-059)**; the other checks pass | **BRA blocked, not run** |
| BRA | not run | not run | |

Following the rule of the command (a failed check blocks the next country, and an implausible result opens a new OQ and stops), BRA was not run. The completion criterion (checks pass in the three countries) is not met. OQ-059 records the numbers; the author decides whether the bound or the model changes.

## 2. Time and memory

F5 runs through `main.py` (`technical_potential` and the `potential_maps` support phase) for solar (6 GCMs, 37 members with the reference) and wind (5 GCMs, 31 members), in the three land scenarios, on the 100 m layer. Time is wall clock of the whole in-process call; memory is the peak working set of that process. The 150 m wind sensitivity is a separate call of `build_potential` with `hub_height_m = 150` set in memory (`parameters.json` untouched), all members and the three land scenarios; it is written to `technical_potential/sensitivity_150m/`.

| Country | F5 + maps, s | Peak working set, MB | 150 m wind sensitivity, s |
|---|---|---|---|
| PRT | 16 | 358 | 12 |
| IND | 242 | 1433 | 214 |

## 3. Sanity checks (step 2)

### PRT

| Check | Result | Detail |
|---|---|---|
| cf_range_nan_solar_central | PASS | rows 127502, cells 3446, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1558, 0.2073], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_restrictive | PASS | rows 124172, cells 3356, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1565, 0.2074], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_permissive | PASS | rows 128982, cells 3486, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1561, 0.2073], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_central | PASS | rows 108376, cells 3496, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0688, 0.5353], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_restrictive | PASS | rows 104439, cells 3369, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0691, 0.5353], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_permissive | PASS | rows 110298, cells 3558, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0675, 0.5354], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| rho_ratio_range | PASS | rho/rho0 at hub 100 m: reference [0.8623, 0.9886], warmest member [0.8460, 0.9748] |
| pv_thermal_factor | PASS | 1+gamma*dT over 128982 cell-members: [0.98300, 1.00000] (gamma -0.003; dT range [0.00, 5.67] K) |
| delta_rsds_range | PASS | delta_rsds [0.9887, 1.1537]; F4 declares no validity range for delta_rsds (only wind_factor_valid_range [0.5, 1.5] for delta_wind), observed range reported; share outside [0.9, 1.1]: 1.3793% |
| cf_net_over_gross | PASS | max \|CF_net/CF_gross - 0.866\| = 1.11e-16 over 323113 cell-members (gross computed again outside the pipeline for every scenario and member; 0 with zero gross CF, net also zero) |
| capacity_20_cells | PASS | solar/central: LUF 0.25, PD 50.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/restrictive: LUF 0.1, PD 45.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/permissive: LUF 0.35, PD 75.0, 20 cells, max \|dP\| 0.00e+00 MW; wind/central: LUF 0.15, PD 4.99, 20 cells, max \|dP\| 0.00e+00 MW; wind/restrictive: LUF 0.05, PD 3.32, 20 cells, max \|dP\| 0.00e+00 MW; wind/permissive: LUF 0.3, PD 7.12, 20 cells, max \|dP\| 0.00e+00 MW |
| sens150_cf_range | PASS | 150 m: CF [0.0835, 0.5589] |

The 10 extreme cells of rho/rho0 (5 lowest, 5 highest, reference climate, 100 m layer, with the density of the warmest member):

| cell_id | lat | lon | elevation, m | rho_ref, kg/m3 | rho/rho0 | rho/rho0, warmest member |
|---|---|---|---|---|---|---|
| 6915464 | 41.975 | -6.775 | 1345 | 1.0563 | 0.8623 | 0.8460 |
| 6937038 | 41.825 | -8.075 | 1351 | 1.0574 | 0.8631 | 0.8486 |
| 6922645 | 41.925 | -7.725 | 1350 | 1.0576 | 0.8634 | 0.8478 |
| 6915463 | 41.975 | -6.825 | 1269 | 1.0637 | 0.8683 | 0.8520 |
| 6922646 | 41.925 | -7.675 | 1283 | 1.0647 | 0.8691 | 0.8533 |
| 6929822 | 41.875 | -8.875 | 17 | 1.2097 | 0.9875 | 0.9738 |
| 6951422 | 41.725 | -8.875 | 15 | 1.2100 | 0.9878 | 0.9741 |
| 6973023 | 41.575 | -8.825 | 5 | 1.2100 | 0.9878 | 0.9740 |
| 6958623 | 41.675 | -8.825 | 11 | 1.2102 | 0.9879 | 0.9741 |
| 6922623 | 41.925 | -8.825 | 7 | 1.2110 | 0.9886 | 0.9748 |

### IND

| Check | Result | Detail |
|---|---|---|
| cf_range_nan_solar_central | PASS | rows 2004734, cells 54182, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1178, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_restrictive | PASS | rows 1793982, cells 48486, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1251, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_solar_permissive | PASS | rows 2074109, cells 56057, members 37, NaN 0, CF outside [0,1] 0, CF range [0.1158, 0.2509], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_central | PASS | rows 1944258, cells 62718, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0002, 0.5239], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_restrictive | PASS | rows 1741890, cells 56190, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0004, 0.5239], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| cf_range_nan_wind_permissive | PASS | rows 2029074, cells 65454, members 31, NaN 0, CF outside [0,1] 0, CF range [0.0000, 0.5682], absent cell-members 0 (declared masked in F4: 0 rows of the file) |
| rho_ratio_range | **FAIL** | rho/rho0 at hub 100 m: reference [0.5135, 0.9438], warmest member [0.5014, 0.9260] |
| pv_thermal_factor | PASS | 1+gamma*dT over 2074109 cell-members: [0.97758, 1.00000] (gamma -0.003; dT range [0.00, 7.47] K) |
| delta_rsds_range | PASS | delta_rsds [0.8366, 1.1906]; F4 declares no validity range for delta_rsds (only wind_factor_valid_range [0.5, 1.5] for delta_wind), observed range reported; share outside [0.9, 1.1]: 0.1872% |
| cf_net_over_gross | PASS | max \|CF_net/CF_gross - 0.866\| = 1.11e-16 over 5715222 cell-members (gross computed again outside the pipeline for every scenario and member; 0 with zero gross CF, net also zero) |
| capacity_20_cells | PASS | solar/central: LUF 0.1, PD 50.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/restrictive: LUF 0.05, PD 45.0, 20 cells, max \|dP\| 0.00e+00 MW; solar/permissive: LUF 0.25, PD 75.0, 20 cells, max \|dP\| 0.00e+00 MW; wind/central: LUF 0.075, PD 4.99, 20 cells, max \|dP\| 0.00e+00 MW; wind/restrictive: LUF 0.05, PD 3.32, 20 cells, max \|dP\| 0.00e+00 MW; wind/permissive: LUF 0.15, PD 7.12, 20 cells, max \|dP\| 0.00e+00 MW |
| sens150_cf_range | PASS | 150 m: CF [0.0007, 0.5647] |

The 10 extreme cells of rho/rho0 (5 lowest, 5 highest, reference climate, 100 m layer, with the density of the warmest member):

| cell_id | lat | lon | elevation, m | rho_ref, kg/m3 | rho/rho0 | rho/rho0, warmest member |
|---|---|---|---|---|---|---|
| 8501192 | 30.975 | 79.625 | 6218 | 0.6290 | 0.5135 | 0.5014 |
| 8501193 | 30.975 | 79.675 | 6122 | 0.6332 | 0.5169 | 0.5047 |
| 8926170 | 28.025 | 88.525 | 5773 | 0.6507 | 0.5312 | 0.5182 |
| 8933364 | 27.975 | 88.225 | 5779 | 0.6511 | 0.5315 | 0.5185 |
| 8277967 | 32.525 | 78.375 | 5901 | 0.6519 | 0.5321 | 0.5201 |
| 9336615 | 25.175 | 90.775 | -29 | 1.1545 | 0.9425 | 0.9244 |
| 9336612 | 25.175 | 90.625 | -28 | 1.1546 | 0.9425 | 0.9244 |
| 9336626 | 25.175 | 91.325 | -34 | 1.1550 | 0.9429 | 0.9250 |
| 9336625 | 25.175 | 91.275 | -39 | 1.1559 | 0.9436 | 0.9256 |
| 9343832 | 25.125 | 91.625 | -35 | 1.1562 | 0.9438 | 0.9260 |

Notes on the checks. (i) The check on the CF ratio recomputes the gross capacity factor outside the pipeline (same curve, member density, `delta_wind`) for every scenario and member; the ratio is 0.866 to rounding. (ii) The F4 declares a validity range only for `delta_wind` (0.5 to 1.5, masked cell-members are declared); for `delta_rsds` it declares none, so the observed range is reported (PRT 0.989 to 1.154, IND 0.837 to 1.191) and the check only requires finite positive values. (iii) No cell-member is absent in either country (the F4 masked file is empty for both). (iv) The capacity check uses 20 random cells per technology and scenario, drawn with seed 20261016, against `parameters.json` read separately.

### The failed check: rho/rho0 in India

The bound of the command is 0.75 to 1.05. In India the reference density at 100 m reaches rho/rho0 = 0.513 (6,218 m, Himalaya near 31.0 N 79.6 E) and 0.501 in the warmest member. The high side is fine (largest 0.944). Wind candidates below 0.75 (central candidate set, reference member):

| Scenario | wind cells | cells below 0.75 | share of cells | share of capacity | share of energy | GW below | TWh/yr below | lowest elevation below, m | cells above 3,000 m |
|---|---|---|---|---|---|---|---|---|---|
| restrictive | 56190 | 953 | 1.7% | 0.12% | 0.13% | 0.07 | 0.13 | 2550 | 945 |
| central | 62718 | 1406 | 2.2% | 0.38% | 0.37% | 0.72 | 1.11 | 2354 | 1316 |
| permissive | 65454 | 1561 | 2.4% | 1.33% | 1.23% | 8.51 | 12.17 | 2317 | 1407 |

rho/rho0 = 0.75 corresponds to about 2449 m in these cells. The affected cells have a mean CF of 15.9% (central) against 14.9% for all wind cells, because their wind is strong. This is the known altitude question (the 3,000 m sensitivity is reported by F5 as `central__below_3000m`, Tier 3, L-025); the new fact is that the density bound of this command is violated and by how much. Opened as OQ-059.

## 4. Plausibility (step 3, reported and not adjusted)

### 4.1 Capacity factor, reference member, central scenario

P5, P50 and P95 over the candidate cells, unweighted and weighted by capacity. Reference values: IRENA (2025), Renewable Power Generation Costs in 2024: PV global weighted average 17.4% (P5 11.5%, P95 22.6%; AC energy over DC capacity, p. 99, Table 3.2, no country value); onshore wind by country for projects commissioned in 2024, Table 2.2, p. 76 (Brazil 56%, India 39%; Portugal not listed; Spain 34%). Fleet capacity factor = annual generation / (mean of the installed capacity at the start and the end of the year x hours of the year).

| Country | Tech | P5 / P50 / P95 unweighted | P5 / P50 / P95 capacity-weighted | Weighted mean | IRENA 2024 | Fleet CF (year) |
|---|---|---|---|---|---|---|
| PRT | solar | 16.6% / 18.1% / 19.1% | 17.2% / 18.5% / 19.1% | 18.3% | 17.4% (global) | 16.9% (2024) |
| PRT | wind | 15.5% / 25.9% / 36.2% | 17.2% / 26.8% / 35.0% | 26.6% | n.r. | 27.8% (2024) |
| IND | solar | 17.1% / 18.2% / 20.0% | 17.5% / 19.1% / 20.1% | 18.9% | 17.4% (global) | not found |
| IND | wind | 4.3% / 14.9% / 27.5% | 8.6% / 17.6% / 28.9% | 18.0% | 39% | 22.4% (FY2023-24, low confidence) |

Fleet series used (the hours are 8,784, a leap year):

| Country | Tech | Generation, GWh | Mean capacity, MW | Fleet CF | Source |
|---|---|---|---|---|---|
| PRT | wind | 14,453 | 5,916 | 27.8% | DGEG, Estatisticas rapidas das renovaveis, dezembro/2024 (publicacao 241): wind 14,453 GWh in 2024; installed 5,893 MW (2023) and 5,938 MW (2024); 2023 and 2024 provisional |
| PRT | solar | 7,098 | 4,780 | 16.9% | same DGEG report: PV 7,098 GWh in 2024 (includes self-consumption units); installed 3,896 MW (2023) and 5,664 MW (2024) |
| BRA | wind | 107,654 | 29,100 | 42.1% | EPE, Anuario Estatistico de Energia Elétrica 2025 (base year 2024), factsheet: wind 107,654 GWh; installed 29,550 MW at end of 2024, +0.9 GW in the year |
| BRA | solar | 70,665 | 43,168 | 18.6% | same EPE factsheet: solar 70,665 GWh (about 58% distributed generation); 48,468 MW at end of 2024, +10.6 GW in the year |
| IND | wind | 83,385 | 42,313 | 22.4% | CEA via Saur Energy: wind 83,385 MU in FY2023-24; MNRE cumulative 40,686 MW (31.03.2023) and 43,940 MW (31.03.2024) as returned by a search snippet, not read on the MNRE page (low confidence) |

India solar is not given: the capacity series found (MNRE) is not on the same basis as the CEA generation (115,975 MU includes rooftop and the MNRE total used a different scope), so no consistent fleet CF could be formed. The Brazilian fleet is shown for context only, since BRA was not run. The sources `epeAnuario2025`, `ceaGeneration` and `dgegRenewables` of the .tex are the same institutions; the exact publications read here are above, and the bibliography file of the thesis was not available to compare keys.

### 4.2 Technical potential by land scenario (reference member)

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
| IND | wind | restrictive | 354,387 | 58.8 | 94.7 | 18.4% |
| IND | wind | central | 509,049 | 190.5 | 300.6 | 18.0% |
| IND | wind | permissive | 597,964 | 638.6 | 993.2 | 17.8% |

Permissive over restrictive:

| Country | Tech | GW ratio | TWh ratio | Product of the factors (area x LUF x PD) |
|---|---|---|---|---|
| PRT | solar | 8.9 | 8.9 | area 1.53 x LUF 3.50 x PD 1.67 = 8.9 |
| PRT | wind | 25.8 | 24.9 | area 2.01 x LUF 6.00 x PD 2.14 = 25.8 |
| IND | solar | 13.2 | 13.2 | area 1.58 x LUF 5.00 x PD 1.67 = 13.2 |
| IND | wind | 10.9 | 10.5 | area 1.69 x LUF 3.00 x PD 2.14 = 10.9 |

The ratios are the product of the three factors, as the method intends (the land range is the joint effect of exclusions, residual utilization and density, U-06). Order of magnitude: Portugal central wind 21 GW against about 5.9 GW installed; Portugal central PV 265 GW against 5.7 GW installed.

### 4.3 Share of the wind potential above the class limit (reference member)

| Country | Scenario | Cells flagged | Capacity share | Energy share | V_ave P50, m/s | V_ave max, m/s |
|---|---|---|---|---|---|---|
| PRT | restrictive | 69 of 3369 | 0.79% | 1.24% | 5.89 | 8.86 |
| PRT | central | 66 of 3496 | 0.74% | 1.19% | 5.83 | 8.85 |
| PRT | permissive | 64 of 3558 | 0.68% | 1.12% | 5.80 | 8.85 |
| IND | restrictive | 181 of 56190 | 0.07% | 0.15% | 4.84 | 10.02 |
| IND | central | 145 of 62718 | 0.08% | 0.16% | 4.74 | 10.28 |
| IND | permissive | 132 of 65454 | 0.12% | 0.24% | 4.70 | 10.49 |

### 4.4 Wind capacity factor at 100 m and at 150 m (reference member, central scenario)

| Country | CF difference (150 m minus 100 m) P5 / P50 / P95 | Relative difference P5 / P50 / P95 | CF at 150 m P5 / P50 / P95 | TWh/yr at 100 m | TWh/yr at 150 m |
|---|---|---|---|---|---|
| PRT | +0.025 / +0.053 / +0.075 | 9% / 21% / 31% | 19.0% / 31.6% / 41.3% | 49.0 | 59.0 |
| IND | +0.012 / +0.055 / +0.077 | 15% / 38% / 58% | 6.3% / 20.6% / 33.8% | 300.6 | 401.8 |

The 150 m run uses the 150 m Weibull layer and its density, with the same turbine; capacity is unchanged.

### 4.5 Change of the capacity factor by member against the reference (central scenario)

Per member: ratio CF(member)/CF(m0) per cell (P50) and the change of the energy over the cells present in every member (like-for-like, from the aggregates).

**PRT solar**: change of energy from -0.46% to +7.11% over 36 members; median cell ratio from 0.995 to 1.069.

| Member | CF ratio P5 | P50 | P95 | Energy change, % |
|---|---|---|---|---|
| m_gfdl_esm4_ssp126_2041_2070 | 1.012 | 1.023 | 1.045 | +2.38 |
| m_gfdl_esm4_ssp126_2071_2100 | 1.017 | 1.027 | 1.048 | +2.85 |
| m_gfdl_esm4_ssp370_2041_2070 | 0.995 | 1.006 | 1.025 | +0.65 |
| m_gfdl_esm4_ssp370_2071_2100 | 0.995 | 1.010 | 1.048 | +1.24 |
| m_gfdl_esm4_ssp585_2041_2070 | 1.008 | 1.019 | 1.040 | +2.01 |
| m_gfdl_esm4_ssp585_2071_2100 | 0.994 | 1.011 | 1.049 | +1.30 |
| m_miroc6_ssp126_2041_2070 | 1.026 | 1.036 | 1.066 | +3.64 |
| m_miroc6_ssp126_2071_2100 | 1.030 | 1.038 | 1.068 | +3.98 |
| m_miroc6_ssp370_2041_2070 | 1.018 | 1.029 | 1.056 | +3.01 |
| m_miroc6_ssp370_2071_2100 | 1.022 | 1.035 | 1.067 | +3.59 |
| m_miroc6_ssp585_2041_2070 | 1.018 | 1.031 | 1.061 | +3.18 |
| m_miroc6_ssp585_2071_2100 | 1.024 | 1.044 | 1.085 | +4.46 |
| m_access_cm2_ssp126_2041_2070 | 1.027 | 1.039 | 1.059 | +3.82 |
| m_access_cm2_ssp126_2071_2100 | 1.036 | 1.050 | 1.077 | +5.00 |
| m_access_cm2_ssp370_2041_2070 | 1.013 | 1.023 | 1.043 | +2.35 |
| m_access_cm2_ssp370_2071_2100 | 1.013 | 1.030 | 1.057 | +3.01 |
| m_access_cm2_ssp585_2041_2070 | 1.023 | 1.039 | 1.066 | +3.93 |
| m_access_cm2_ssp585_2071_2100 | 1.026 | 1.050 | 1.083 | +4.97 |
| m_ipsl_cm6a_lr_ssp126_2041_2070 | 1.028 | 1.043 | 1.069 | +4.44 |
| m_ipsl_cm6a_lr_ssp126_2071_2100 | 1.034 | 1.048 | 1.069 | +4.87 |
| m_ipsl_cm6a_lr_ssp370_2041_2070 | 1.018 | 1.031 | 1.060 | +3.33 |
| m_ipsl_cm6a_lr_ssp370_2071_2100 | 1.028 | 1.050 | 1.087 | +5.18 |
| m_ipsl_cm6a_lr_ssp585_2041_2070 | 1.019 | 1.036 | 1.067 | +3.76 |
| m_ipsl_cm6a_lr_ssp585_2071_2100 | 1.039 | 1.069 | 1.120 | +7.11 |
| m_cnrm_cm6_1_ssp126_2041_2070 | 1.024 | 1.035 | 1.046 | +3.50 |
| m_cnrm_cm6_1_ssp126_2071_2100 | 1.019 | 1.028 | 1.037 | +2.76 |
| m_cnrm_cm6_1_ssp370_2041_2070 | 1.018 | 1.028 | 1.039 | +2.84 |
| m_cnrm_cm6_1_ssp370_2071_2100 | 1.015 | 1.032 | 1.044 | +3.08 |
| m_cnrm_cm6_1_ssp585_2041_2070 | 1.016 | 1.029 | 1.042 | +2.93 |
| m_cnrm_cm6_1_ssp585_2071_2100 | 1.017 | 1.035 | 1.050 | +3.44 |
| m_mri_esm2_0_ssp126_2041_2070 | 1.004 | 1.016 | 1.047 | +1.59 |
| m_mri_esm2_0_ssp126_2071_2100 | 0.997 | 1.008 | 1.040 | +0.90 |
| m_mri_esm2_0_ssp370_2041_2070 | 0.987 | 0.997 | 1.020 | -0.34 |
| m_mri_esm2_0_ssp370_2071_2100 | 0.985 | 0.995 | 1.022 | -0.46 |
| m_mri_esm2_0_ssp585_2041_2070 | 0.996 | 1.008 | 1.033 | +0.72 |
| m_mri_esm2_0_ssp585_2071_2100 | 0.994 | 1.009 | 1.042 | +0.87 |

**PRT wind**: change of energy from -9.84% to +6.78% over 30 members; median cell ratio from 0.900 to 1.077.

| Member | CF ratio P5 | P50 | P95 | Energy change, % |
|---|---|---|---|---|
| m_gfdl_esm4_ssp126_2041_2070 | 0.963 | 0.978 | 0.985 | -2.43 |
| m_gfdl_esm4_ssp126_2071_2100 | 0.939 | 0.962 | 0.998 | -3.93 |
| m_gfdl_esm4_ssp370_2041_2070 | 0.929 | 0.953 | 0.999 | -4.98 |
| m_gfdl_esm4_ssp370_2071_2100 | 0.948 | 0.970 | 1.005 | -3.25 |
| m_gfdl_esm4_ssp585_2041_2070 | 0.953 | 0.972 | 1.005 | -3.07 |
| m_gfdl_esm4_ssp585_2071_2100 | 0.900 | 0.938 | 1.003 | -6.38 |
| m_access_cm2_ssp126_2041_2070 | 0.940 | 0.950 | 0.964 | -4.90 |
| m_access_cm2_ssp126_2071_2100 | 0.893 | 0.925 | 0.955 | -8.05 |
| m_access_cm2_ssp370_2041_2070 | 0.971 | 0.995 | 1.010 | -1.15 |
| m_access_cm2_ssp370_2071_2100 | 0.941 | 0.959 | 0.976 | -4.41 |
| m_access_cm2_ssp585_2041_2070 | 0.943 | 0.958 | 0.973 | -4.28 |
| m_access_cm2_ssp585_2071_2100 | 0.892 | 0.916 | 0.950 | -8.42 |
| m_ipsl_cm6a_lr_ssp126_2041_2070 | 0.943 | 0.954 | 0.968 | -4.54 |
| m_ipsl_cm6a_lr_ssp126_2071_2100 | 0.950 | 0.967 | 0.978 | -3.52 |
| m_ipsl_cm6a_lr_ssp370_2041_2070 | 0.911 | 0.928 | 0.948 | -7.07 |
| m_ipsl_cm6a_lr_ssp370_2071_2100 | 0.874 | 0.900 | 0.926 | -9.84 |
| m_ipsl_cm6a_lr_ssp585_2041_2070 | 0.927 | 0.946 | 0.965 | -5.57 |
| m_ipsl_cm6a_lr_ssp585_2071_2100 | 0.889 | 0.914 | 0.932 | -8.40 |
| m_cnrm_cm6_1_ssp126_2041_2070 | 0.971 | 0.989 | 1.009 | -1.31 |
| m_cnrm_cm6_1_ssp126_2071_2100 | 0.974 | 1.009 | 1.039 | +0.21 |
| m_cnrm_cm6_1_ssp370_2041_2070 | 1.000 | 1.027 | 1.052 | +2.24 |
| m_cnrm_cm6_1_ssp370_2071_2100 | 0.948 | 0.972 | 0.994 | -3.04 |
| m_cnrm_cm6_1_ssp585_2041_2070 | 0.970 | 0.988 | 1.000 | -1.45 |
| m_cnrm_cm6_1_ssp585_2071_2100 | 0.907 | 0.940 | 0.980 | -6.21 |
| m_mri_esm2_0_ssp126_2041_2070 | 1.003 | 1.021 | 1.034 | +1.92 |
| m_mri_esm2_0_ssp126_2071_2100 | 1.029 | 1.077 | 1.103 | +6.78 |
| m_mri_esm2_0_ssp370_2041_2070 | 1.009 | 1.049 | 1.068 | +4.19 |
| m_mri_esm2_0_ssp370_2071_2100 | 1.002 | 1.044 | 1.065 | +3.78 |
| m_mri_esm2_0_ssp585_2041_2070 | 0.998 | 1.030 | 1.046 | +2.47 |
| m_mri_esm2_0_ssp585_2071_2100 | 0.963 | 1.005 | 1.017 | -0.40 |

**IND solar**: change of energy from -6.53% to +3.43% over 36 members; median cell ratio from 0.931 to 1.043.

| Member | CF ratio P5 | P50 | P95 | Energy change, % |
|---|---|---|---|---|
| m_gfdl_esm4_ssp126_2041_2070 | 1.011 | 1.023 | 1.035 | +2.11 |
| m_gfdl_esm4_ssp126_2071_2100 | 1.023 | 1.042 | 1.064 | +3.38 |
| m_gfdl_esm4_ssp370_2041_2070 | 0.919 | 0.931 | 0.950 | -6.31 |
| m_gfdl_esm4_ssp370_2071_2100 | 0.922 | 0.933 | 0.946 | -6.53 |
| m_gfdl_esm4_ssp585_2041_2070 | 0.965 | 0.978 | 0.990 | -2.05 |
| m_gfdl_esm4_ssp585_2071_2100 | 0.971 | 0.991 | 1.014 | -1.00 |
| m_miroc6_ssp126_2041_2070 | 0.995 | 1.004 | 1.012 | +0.30 |
| m_miroc6_ssp126_2071_2100 | 1.006 | 1.014 | 1.036 | +1.26 |
| m_miroc6_ssp370_2041_2070 | 0.957 | 0.966 | 0.976 | -2.98 |
| m_miroc6_ssp370_2071_2100 | 0.952 | 0.960 | 0.973 | -3.86 |
| m_miroc6_ssp585_2041_2070 | 0.980 | 0.990 | 0.997 | -1.00 |
| m_miroc6_ssp585_2071_2100 | 0.971 | 0.980 | 0.995 | -1.94 |
| m_access_cm2_ssp126_2041_2070 | 1.005 | 1.015 | 1.035 | +1.25 |
| m_access_cm2_ssp126_2071_2100 | 1.013 | 1.030 | 1.057 | +2.33 |
| m_access_cm2_ssp370_2041_2070 | 0.918 | 0.946 | 0.966 | -5.29 |
| m_access_cm2_ssp370_2071_2100 | 0.915 | 0.942 | 0.973 | -6.29 |
| m_access_cm2_ssp585_2041_2070 | 0.976 | 0.983 | 0.999 | -1.82 |
| m_access_cm2_ssp585_2071_2100 | 0.959 | 0.986 | 1.012 | -2.46 |
| m_ipsl_cm6a_lr_ssp126_2041_2070 | 0.986 | 1.006 | 1.010 | +0.27 |
| m_ipsl_cm6a_lr_ssp126_2071_2100 | 0.981 | 1.001 | 1.013 | +0.13 |
| m_ipsl_cm6a_lr_ssp370_2041_2070 | 0.958 | 0.968 | 0.974 | -3.25 |
| m_ipsl_cm6a_lr_ssp370_2071_2100 | 0.944 | 0.966 | 0.982 | -3.85 |
| m_ipsl_cm6a_lr_ssp585_2041_2070 | 0.952 | 0.970 | 0.980 | -3.27 |
| m_ipsl_cm6a_lr_ssp585_2071_2100 | 0.940 | 0.970 | 0.993 | -3.83 |
| m_cnrm_cm6_1_ssp126_2041_2070 | 1.016 | 1.026 | 1.035 | +2.29 |
| m_cnrm_cm6_1_ssp126_2071_2100 | 1.022 | 1.039 | 1.051 | +3.43 |
| m_cnrm_cm6_1_ssp370_2041_2070 | 0.948 | 0.964 | 0.982 | -3.46 |
| m_cnrm_cm6_1_ssp370_2071_2100 | 0.933 | 0.948 | 0.973 | -4.98 |
| m_cnrm_cm6_1_ssp585_2041_2070 | 0.979 | 0.992 | 1.004 | -0.95 |
| m_cnrm_cm6_1_ssp585_2071_2100 | 0.956 | 0.978 | 0.998 | -2.40 |
| m_mri_esm2_0_ssp126_2041_2070 | 1.002 | 1.014 | 1.039 | +0.99 |
| m_mri_esm2_0_ssp126_2071_2100 | 1.013 | 1.043 | 1.069 | +3.03 |
| m_mri_esm2_0_ssp370_2041_2070 | 0.916 | 0.932 | 0.952 | -5.96 |
| m_mri_esm2_0_ssp370_2071_2100 | 0.930 | 0.939 | 0.960 | -6.03 |
| m_mri_esm2_0_ssp585_2041_2070 | 0.961 | 0.974 | 0.986 | -2.69 |
| m_mri_esm2_0_ssp585_2071_2100 | 0.969 | 0.990 | 1.010 | -1.86 |

**IND wind**: change of energy from -7.41% to +12.27% over 30 members; median cell ratio from 0.936 to 1.156.

| Member | CF ratio P5 | P50 | P95 | Energy change, % |
|---|---|---|---|---|
| m_gfdl_esm4_ssp126_2041_2070 | 0.868 | 0.958 | 1.004 | -4.43 |
| m_gfdl_esm4_ssp126_2071_2100 | 0.868 | 0.975 | 1.018 | -3.28 |
| m_gfdl_esm4_ssp370_2041_2070 | 0.859 | 0.947 | 1.075 | -3.59 |
| m_gfdl_esm4_ssp370_2071_2100 | 0.878 | 0.972 | 1.169 | -0.37 |
| m_gfdl_esm4_ssp585_2041_2070 | 0.865 | 0.936 | 1.018 | -5.02 |
| m_gfdl_esm4_ssp585_2071_2100 | 0.896 | 1.004 | 1.211 | +2.98 |
| m_access_cm2_ssp126_2041_2070 | 0.997 | 1.055 | 1.134 | +5.17 |
| m_access_cm2_ssp126_2071_2100 | 1.006 | 1.053 | 1.101 | +5.25 |
| m_access_cm2_ssp370_2041_2070 | 0.899 | 0.992 | 1.034 | +0.41 |
| m_access_cm2_ssp370_2071_2100 | 0.920 | 1.034 | 1.089 | +3.40 |
| m_access_cm2_ssp585_2041_2070 | 0.969 | 1.045 | 1.103 | +4.44 |
| m_access_cm2_ssp585_2071_2100 | 0.971 | 1.107 | 1.264 | +10.17 |
| m_ipsl_cm6a_lr_ssp126_2041_2070 | 0.840 | 0.947 | 0.994 | -7.10 |
| m_ipsl_cm6a_lr_ssp126_2071_2100 | 0.839 | 0.947 | 0.995 | -7.41 |
| m_ipsl_cm6a_lr_ssp370_2041_2070 | 0.905 | 1.037 | 1.181 | +2.54 |
| m_ipsl_cm6a_lr_ssp370_2071_2100 | 0.893 | 1.137 | 1.338 | +10.51 |
| m_ipsl_cm6a_lr_ssp585_2041_2070 | 0.880 | 0.984 | 1.092 | -2.93 |
| m_ipsl_cm6a_lr_ssp585_2071_2100 | 0.893 | 1.156 | 1.297 | +12.27 |
| m_cnrm_cm6_1_ssp126_2041_2070 | 0.984 | 1.028 | 1.063 | +1.93 |
| m_cnrm_cm6_1_ssp126_2071_2100 | 0.994 | 1.046 | 1.088 | +4.88 |
| m_cnrm_cm6_1_ssp370_2041_2070 | 0.924 | 0.959 | 0.992 | -3.40 |
| m_cnrm_cm6_1_ssp370_2071_2100 | 0.899 | 0.955 | 1.006 | -3.01 |
| m_cnrm_cm6_1_ssp585_2041_2070 | 0.952 | 0.979 | 1.022 | -1.35 |
| m_cnrm_cm6_1_ssp585_2071_2100 | 0.934 | 1.048 | 1.120 | +5.38 |
| m_mri_esm2_0_ssp126_2041_2070 | 0.980 | 1.019 | 1.077 | +1.99 |
| m_mri_esm2_0_ssp126_2071_2100 | 1.017 | 1.041 | 1.113 | +3.87 |
| m_mri_esm2_0_ssp370_2041_2070 | 0.900 | 0.953 | 1.016 | -2.91 |
| m_mri_esm2_0_ssp370_2071_2100 | 0.915 | 0.974 | 1.054 | -1.42 |
| m_mri_esm2_0_ssp585_2041_2070 | 0.940 | 0.992 | 1.061 | -0.07 |
| m_mri_esm2_0_ssp585_2071_2100 | 0.975 | 1.085 | 1.149 | +8.67 |

## 5. Reading of the results (reported, nothing adjusted)

- Portugal: modeled PV CF (weighted mean 18.3%) and wind CF (26.6%) bracket the 2024 fleet (16.9% and 27.8%); the PV value is above the IRENA global 17.4%, as expected for a high-irradiance country with a fixed-tilt DC baseline.
- India: PV CF 18.9% (P5 to P95 17.5% to 20.1%); wind weighted mean 18.0%, P50 17.6%, below the 2024 fleet indication of about 22% and far below the 39% IRENA reports for projects commissioned in 2024. The candidate set covers all eligible land, not the best sites (the map of the wind CF shows the Gujarat, Rajasthan, Karnataka and Tamil Nadu bands at about 0.25 to 0.40, with a few cells above 0.5); the weighted P95 is 28.9% and the largest cell CF 0.52. The gap to the new-project value is the difference between a country-wide potential and a selection of sites.
- The climate change of the PV energy is small (PRT up to +7.1%, IND from -6.5% to +3.4%); wind changes from -9.8% to +6.8% (PRT) and from -7.4% to +12.3% (IND).
- The permissive to restrictive ratios (8.9 and 25.8 in Portugal, 13.2 and 10.9 in India) are the product of area, LUF and PD, so they are by construction.

## 6. Artifacts

In `D:\Douglas\DOUTORADO\GeoFREA_data\outputs\<ISO3>\technical_potential\`: `artifacts\potential_<tech>__<scenario>.parquet` (3 scenarios x 2 technologies), `potential_aggregates_<tech>.parquet`, `class_flag_wind__<scenario>.parquet`, the COG of the phase (`potential_density_<tech>.tif`, `capacity_factor_<tech>.tif`) and its PNG maps in `figures\`; `sensitivity_150m\` (wind, hub 150 m); `figures_run_report\potential_<tech>__<scenario>.png`, one map per potential file (CF at m0 and capacity density).

| Country | Files of the potential | Map |
|---|---|---|
| PRT | `potential_solar__restrictive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_solar__restrictive.png` |
| PRT | `potential_solar__central.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_solar__central.png` |
| PRT | `potential_solar__permissive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_solar__permissive.png` |
| PRT | `potential_wind__restrictive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_wind__restrictive.png` |
| PRT | `potential_wind__central.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_wind__central.png` |
| PRT | `potential_wind__permissive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\PRT\technical_potential\figures_run_report\potential_wind__permissive.png` |
| IND | `potential_solar__restrictive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_solar__restrictive.png` |
| IND | `potential_solar__central.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_solar__central.png` |
| IND | `potential_solar__permissive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_solar__permissive.png` |
| IND | `potential_wind__restrictive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_wind__restrictive.png` |
| IND | `potential_wind__central.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_wind__central.png` |
| IND | `potential_wind__permissive.parquet` | `D:/Douglas/DOUTORADO/GeoFREA_data/outputs\IND\technical_potential\figures_run_report\potential_wind__permissive.png` |

The scripts of this run (driver and checks) are in the session scratch directory and are not part of the repository; the numbers above come from them.
