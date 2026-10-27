# Numerical audit of the technical potential (T-14, COMMAND 65)

Images archived on 2026-10-27 (COMMAND 72) in `GeoFREA_data/archive/docs_figures_audit_potential_65/` and removed from the repository, as for `display_resolution_67b.md`; the text names each file. 3 image link(s) in this report became text.

Written for Douglas. Read-only audit of the F3, F4 and F5 artifacts of the final round (2026-10-21/22) of PRT, IND and BRA, with `scripts/audit_potential.py` (outside the pipeline: it reads the artifacts and `config/parameters.json` and writes only here). Items 1 to 6 of T-14 of `docs/figures/GEOFREA_figuras_spec_v2.md`. Nothing in the pipeline was changed. **No bug was found, so no open question was opened.** Numbers: `audit_potential_65/<ISO3>.json`; curves: `audit_potential_65/<ISO3>_supply_curves.png`.

Run: one country at a time, free commit memory 6.9 GB before each (the first run of BRA stopped at once with a read error of pyarrow `OSError: Invalid argument` and passed when repeated; nothing in the artifacts changed). The artifacts are those of the central/restrictive/permissive land scenarios and of the 37 members of F4 (`m0` plus 6 GCMs x 3 SSPs x 2 windows). The F5 hashes of PRT and BRA are in `run_real_hashes.json` (final round); the IND ones are of the same F5 run and are recorded there after the ERA5 extension.

## 0. Conclusion per item

| Item | PRT | IND | BRA |
|---|---|---|---|
| 1 Wind against solar | ok | ok | ok |
| 2 Area weighting | ok | ok | ok |
| 3 Supply curves and CF bands | done | done | done |
| 4 Plausibility of the totals | ok | ok | ok |
| 5 Effective resolution | ok | ok | ok |
| 6 Climate forcing | table made; nothing indicates a bug | table made; nothing indicates a bug | table made; nothing indicates a bug |

## 0.1 Where 238.5 GW and 345.1 TWh of BRA wind come from

The spec (item 3) cites BRA wind 238.5 GW and 345.1 TWh per year with CF about 16.5%. Those are the **restrictive land scenario, member `m0` (reference climate)** of the same final round: 238.53 GW and 345.05 TWh (LUF 0.05 x PD 3.32 MW/km2 = 0.166 MW per eligible km2; energy-weighted CF 16.5%). The central scenario of the same round gives 1,643.45 GW and 2,297.21 TWh (CF 16.0%) and the permissive 5,610.03 GW and 7,727.82 TWh. The same 238.5 GW and 345.0 TWh are the restrictive row of `docs/phases/F5/run_report_real.md` and `potential_maps_absolute.md`; the spec's 345.1 is the rounding of 345.05. The members with a future climate are not the origin: the capacity of the restrictive scenario is between 234.8 and 238.5 GW in every member and mostly the energy changes with the member (332 to 503 TWh). So the number is correct and was taken from the wrong row; the figure to compare with the 19,188 GW of solar (central) is 1,643.45 GW and 2,297.21 TWh.

## 1. Wind against solar

### 1a. The ratio of the capacity densities, cell by cell (central scenario, reference member)

Capacity density = eligible area x LUF x PD / cell area, so the ratio solar/wind in a cell is the constant LUF x PD of solar over that of wind times the ratio of the two eligible shares. The constant is 12.5 / 0.7485 = 16.70 in PRT and BRA and 5.0 / 0.3743 = 13.36 in IND (LUF 0.1 for solar, 0.075 for wind). The ratio equals constant x share ratio in every cell (maximum relative error below 1e-15), and the capacity of every cell equals eligible area x LUF x PD (error below 3e-16); the energy equals P x CF x 8760 (error 0).

| Country | Constant | Cells in both | Wind only | Solar only | Ratio P5 | Median | P95 | Maximum | Cells within 1% of the constant |
|---|---|---|---|---|---|---|---|---|---|
| PRT | 16.70 | 3,449 | 51 | 0 | 5.86 | 12.14 | 16.08 | 16.70 | 0.9% |
| IND | 13.36 | 53,098 | 8,366 | 4,451 | 0.34 | 3.72 | 11.40 | 69.15 | 1.3% |
| BRA | 16.70 | 180,057 | 1,249 | 1 | 1.84 | 13.82 | 16.64 | 113.75 | 8.8% |

### 1b. Eligible share of the two technologies (all cells of the country, central scenario)

| Country | Cells | Mean share wind | Mean share solar | Identical share | Wind larger | Solar larger | Pearson | Spearman |
|---|---|---|---|---|---|---|---|---|
| PRT | 3,939 | 30.6% | 23.1% | 7.7% | 92.3% | 0.0% | 0.956 | 0.973 |
| IND | 112,948 | 16.0% | 4.9% | 33.2% | 61.8% | 5.0% | 0.647 | 0.882 |
| BRA | 286,043 | 26.0% | 18.0% | 30.6% | 69.4% | 0.0% | 0.848 | 0.931 |

Excluded area by term (km2, all cells; wind / solar) and share of cells where one is larger than the other:

| Country | Term | Wind | Solar | Cells wind larger | Cells solar larger |
|---|---|---|---|---|---|
| PRT | E1 | 19,895 | 19,895 | 0.0% | 0.0% |
| PRT | E2 | 523 | 523 | 0.0% | 0.0% |
| PRT | E3 | 21,778 | 21,778 | 0.0% | 0.0% |
| PRT | E4 | 12,395 | 28,126 | 0.0% | 99.7% |
| PRT | E5 | 29,955 | 34,954 | 0.0% | 97.8% |
| PRT | E6 | 8,490 | 8,490 | 0.0% | 0.0% |
| IND | E1 | 602,061 | 602,061 | 0.0% | 0.0% |
| IND | E2 | 19,291 | 19,291 | 0.0% | 0.0% |
| IND | E3 | 856,042 | 856,042 | 0.0% | 0.0% |
| IND | E4 | 419,528 | 589,637 | 0.0% | 89.7% |
| IND | E5 | 904,203 | 2,460,189 | 0.0% | 93.9% |
| IND | E6 | 1,599,115 | 1,599,115 | 0.0% | 0.0% |
| BRA | E1 | 2,636,933 | 2,636,933 | 0.0% | 0.0% |
| BRA | E2 | 53,252 | 53,252 | 0.0% | 0.0% |
| BRA | E3 | 2,498,464 | 2,498,464 | 0.0% | 0.0% |
| BRA | E4 | 549,383 | 1,381,698 | 0.0% | 97.4% |
| BRA | E5 | 5,026,367 | 5,718,203 | 0.0% | 59.6% |
| BRA | E6 | 91,150 | 91,150 | 0.0% | 0.0% |

Cells where the solar share is larger than the wind share (wind has requirements solar does not have: the resource layers and the 3000 m limit of D-F3-015):

| Country | Cells | Above 3000 m | Wind resource missing | Other |
|---|---|---|---|---|
| PRT | 0 | 0 | 0 | 0 |
| IND | 5,659 | 103 | 5,495 | 61 |
| BRA | 17 | 0 | 9 | 8 |

### 1c. Energy density against the CF of the technology itself (cells with potential, central, reference member)

| Country | Tech | Energy density vs CF (Pearson / Spearman) | Capacity density vs CF | Energy per eligible km2 vs CF | Energy density vs eligible share |
|---|---|---|---|---|---|
| PRT | wind | 0.385 / 0.404 | 0.155 / 0.189 | 1.000 / 1.000 | 0.950 / 0.965 |
| PRT | solar | 0.514 / 0.522 | 0.490 / 0.496 | 1.000 / 1.000 | 0.999 / 0.999 |
| IND | wind | 0.636 / 0.667 | 0.442 / 0.468 | 1.000 / 1.000 | 0.918 / 0.965 |
| IND | solar | 0.381 / 0.408 | 0.360 / 0.376 | 1.000 / 1.000 | 0.999 / 0.999 |
| BRA | wind | 0.819 / 0.818 | 0.424 / 0.486 | 1.000 / 1.000 | 0.760 / 0.871 |
| BRA | solar | 0.459 / 0.462 | 0.410 / 0.417 | 1.000 / 1.000 | 0.997 / 0.998 |

Between the two technologies (cells in both): energy density wind against solar, Pearson / Spearman, and CF wind against CF solar:

| Country | Energy density wind vs solar | CF wind vs CF solar |
|---|---|---|
| PRT | 0.913 / 0.935 | 0.279 / 0.296 |
| IND | 0.709 / 0.660 | 0.549 / 0.561 |
| BRA | 0.523 / 0.595 | 0.192 / 0.246 |

**Conclusion, item 1: ok.** (a) The densities of the two technologies are not the same field: the observed ratio is the constant only where the shares are equal (about 1% of the cells in PRT) and its median is 12.1 in PRT, 3.7 in IND and 13.8 in BRA. (b) The shares are not identical: in no country is the solar share larger than the wind share for the exclusion terms; wind is the larger one in 92% (PRT), 62% (IND) and 69% (BRA) of the cells, because the slope limit (E4) and the land-cover classes (E5: cropland excluded for solar and allowed for wind) differ, while protected areas, water, riparian and population (E1, E2, E3, E6) are the same. The cells where solar is larger are wind cells without a resource value or above 3000 m (IND 5,659 cells, 5,495 with no wind resource: the north block and Arunachal of L-047; BRA 17 cells). The similar pattern of PRT wind and solar comes from the shared terms (Pearson of the shares 0.96); the share of one technology is not being used for the other. (c) The resource appears: the energy per eligible km2 follows the CF exactly (Pearson 1.0, by construction E = P x CF x 8760 with P proportional to the area), and the energy density per cell is dominated by the eligible share (0.76 to 0.999) with the CF as a second factor (0.38 to 0.82 for wind in PRT, IND and BRA). In solar the CF varies little (0.12 to 0.22 in BRA), so the solar energy-density map is almost the map of the eligible share. For a figure that has to show the resource, the energy per eligible km2 or the CF is the variable; the density per cell shows where the land is.

## 2. Area weighting

The area of every cell in the F3 table is the area of the cell inside the country (a cell cut by the border or the coast is smaller than the full cell); the totals are sums of `P_MW` and `E_MWh` of the cells, which are eligible area (km2) x LUF x PD. The formula of the spec, R^2 x dlon x (sin lat2 - sin lat1) with R = 6371.0088 km, is compared with the table for the cells that are not cut by the border (relative difference above -1%).

| Country | Cells cut by the border | Full cells: table against formula (min / max) | Area of the cell at the lowest / highest |latitude| | Area decreases with latitude |
|---|---|---|---|---|
| PRT | 10.9% | 0.04% / 0.15% | 1.077 (lat 37.0 / 42.1) | True |
| IND | 3.2% | -0.42% / 0.00% | 1.216 (lat 8.1 / 35.5) | True |
| BRA | 1.4% | -0.45% / -0.04% | 1.202 (lat 0.0 / 33.7) | True |

Total with and without weighting (central scenario, reference member; `GW`):

| Country | Tech | Table (real area) | Cell count x mean area | Effect | Constant equatorial area (30.91 km2) | Effect |
|---|---|---|---|---|---|---|
| PRT | wind | 21.05 | 20.35 | -3.34% | 27.91 | +32.60% |
| PRT | solar | 264.46 | 255.47 | -3.40% | 350.46 | +32.52% |
| IND | wind | 189.81 | 187.13 | -1.41% | 207.85 | +9.50% |
| IND | solar | 753.37 | 760.36 | +0.93% | 844.55 | +12.10% |
| BRA | wind | 1,643.45 | 1,654.80 | +0.69% | 1,719.89 | +4.65% |
| BRA | solar | 19,188.34 | 19,182.21 | -0.03% | 19,936.75 | +3.90% |

**Conclusion, item 2: ok.** The table follows the formula within -0.45% to +0.15% for the full cells (the sphere against the ellipsoid of the pipeline), the area falls with the latitude in the three countries, and the totals are sums of the real area. In BRA the cell at the equator is 1.20 times the cell at 33.7 degrees (the spec's 17% less at 33 degrees S: 1/1.202 = 0.83). Ignoring the weighting would change the totals by -3.3% to -3.4% (PRT), -1.4% to +0.9% (IND) and +0.7% to 0.0% (BRA) with the mean area and by +33% (PRT), +10% to +12% (IND) and +4% to +5% (BRA) with a constant equatorial area.

## 3. Supply curves and CF bands (no resource cut)

Cells with potential, sorted from the highest CF down, cumulative GW and TWh against CF; three land scenarios, reference member. Nothing was cut or added: the totals of the curves are the totals of F5. (No LCOE axis: F6 has not run.)

[PRT supply curves: image archived as `PRT_supply_curves.png`]

[IND supply curves: image archived as `IND_supply_curves.png`]

[BRA supply curves: image archived as `BRA_supply_curves.png`]

### Bands of CF, solar

| Country | Scenario | Total GW | Total TWh | Energy-weighted CF | <0.15 GW / TWh | 0.15-0.25 | 0.25-0.35 | >0.35 |
|---|---|---|---|---|---|---|---|---|
| PRT | restrictive | 70.58 | 113.47 | 18.4% | 0.00 / 0.00 (0%) | 70.58 / 113.47 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| PRT | central | 264.46 | 424.63 | 18.3% | 0.00 / 0.00 (0%) | 264.46 / 424.63 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| PRT | permissive | 631.04 | 1,012.63 | 18.3% | 0.00 / 0.00 (0%) | 631.04 / 1,012.63 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| IND | restrictive | 242.01 | 403.10 | 19.0% | 0.23 / 0.28 (0%) | 241.78 / 402.82 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| IND | central | 753.37 | 1,253.59 | 19.0% | 1.33 / 1.62 (0%) | 752.04 / 1,251.96 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| IND | permissive | 3,230.93 | 5,374.13 | 19.0% | 7.69 / 9.43 (0%) | 3,223.24 / 5,364.70 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| BRA | restrictive | 4,803.24 | 7,797.53 | 18.5% | 2.11 / 2.70 (0%) | 4,801.13 / 7,794.83 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| BRA | central | 19,188.34 | 31,068.30 | 18.5% | 12.35 / 15.72 (0%) | 19,176.00 / 31,052.58 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |
| BRA | permissive | 46,390.81 | 75,034.37 | 18.5% | 34.36 / 43.69 (0%) | 46,356.44 / 74,990.68 (100%) | 0.00 / 0.00 (0%) | 0.00 / 0.00 (0%) |

### Bands of CF, wind

| Country | Scenario | Total GW | Total TWh | Energy-weighted CF | <0.15 GW / TWh | 0.15-0.25 | 0.25-0.35 | >0.35 |
|---|---|---|---|---|---|---|---|---|
| PRT | restrictive | 2.91 | 6.93 | 27.2% | 0.06 / 0.06 (2%) | 0.88 / 1.69 (30%) | 1.80 / 4.61 (62%) | 0.17 / 0.57 (6%) |
| PRT | central | 21.05 | 49.00 | 26.6% | 0.62 / 0.67 (3%) | 7.30 / 13.95 (35%) | 12.06 / 30.83 (57%) | 1.07 / 3.54 (5%) |
| PRT | permissive | 75.25 | 172.52 | 26.2% | 2.65 / 2.86 (4%) | 27.69 / 52.32 (37%) | 41.37 / 105.60 (55%) | 3.54 / 11.73 (5%) |
| IND | restrictive | 58.76 | 94.63 | 18.4% | 18.21 / 18.51 (31%) | 31.72 / 54.13 (54%) | 8.55 / 21.07 (15%) | 0.28 / 0.92 (0%) |
| IND | central | 189.81 | 299.50 | 18.0% | 63.30 / 62.94 (33%) | 99.51 / 169.36 (52%) | 26.22 / 64.62 (14%) | 0.79 / 2.57 (0%) |
| IND | permissive | 630.41 | 981.31 | 17.8% | 219.30 / 213.47 (35%) | 323.79 / 550.64 (51%) | 84.84 / 209.11 (13%) | 2.47 / 8.09 (0%) |
| BRA | restrictive | 238.53 | 345.05 | 16.5% | 122.64 / 102.33 (51%) | 76.01 / 129.38 (32%) | 28.77 / 73.51 (12%) | 11.11 / 39.83 (5%) |
| BRA | central | 1,643.45 | 2,297.21 | 16.0% | 890.17 / 725.76 (54%) | 496.02 / 841.30 (30%) | 186.52 / 476.88 (11%) | 70.74 / 253.26 (4%) |
| BRA | permissive | 5,610.03 | 7,727.82 | 15.7% | 3,102.94 / 2,511.55 (55%) | 1,658.05 / 2,807.60 (30%) | 617.39 / 1,578.61 (11%) | 231.65 / 830.06 (4%) |

Share of capacity in brackets. **Reading:** in solar the CF stays between 0.12 and 0.22, so nearly all the capacity sits in the 0.15-0.25 band (PRT 100%); the resource cut that would matter is wind. In wind, the central scenario puts 54% of the BRA capacity below CF 0.15 and 30% between 0.15 and 0.25 (IND: 33% and 52%), which is why the average CF is 16% in BRA and 18% in IND. The cut is `CF_min` (OQ-008, Group 4) and was not applied.

## 4. Plausibility of the totals

| Country | Consumption (TWh, year) | Source |
|---|---|---|
| PRT | 50.7 (2023) | REN, electricity supplied by the public grid in 2023 (REN press release of 2024-01-02, 'Renewable energy generation sets new record in 2023') |
| IND | 1,505.9 (2022) | Government statistics reported by the press: 1,505.91 billion units consumed in FY2022-23 (the full year FY2023-24 was not found; April-January of FY2023-24 was 1,354.97 BU, +7.5%) |
| BRA | 616.3 (2023) | IBGE Anuario Estatistico do Brasil 2024, table 3105, reproducing the BEN 2024 (EPE, base year 2023): total electricity consumption 616.3 TWh (read from the table, to confirm in the EPE report) |

The consumption figures are orders of magnitude for the ratio, not inputs: IND is the FY2022-23 press figure of government statistics (the FY2023-24 year was not found) and BRA is read from a table of the IBGE yearbook that reproduces the BEN 2024 (to be confirmed in the EPE report). The comparison with published potentials is OQ-057 (Group 7).

| Country | Tech | Scenario | Eligible fraction of the country | LUF x PD (MW/km2) | Maximum observed density | Maximum / ceiling | Cells with share >= 0.999 | GW | TWh | TWh / consumption |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT | solar | restrictive | 17.7% | 0.1 x 45 = 4.5 | 3.971 | 88.2% | 0 of 3,358 | 70.58 | 113.47 | 2.24 |
| PRT | solar | central | 23.8% | 0.25 x 50 = 12.5 | 11.57 | 92.6% | 0 of 3,449 | 264.46 | 424.63 | 8.38 |
| PRT | solar | permissive | 27.1% | 0.35 x 75 = 26.25 | 25.01 | 95.3% | 0 of 3,489 | 631.04 | 1,012.63 | 19.97 |
| PRT | wind | restrictive | 19.8% | 0.05 x 3.32 = 0.166 | 0.1602 | 96.5% | 0 of 3,371 | 2.91 | 6.93 | 0.14 |
| PRT | wind | central | 31.7% | 0.15 x 4.99 = 0.7485 | 0.7381 | 98.6% | 0 of 3,500 | 21.05 | 49.00 | 0.97 |
| PRT | wind | permissive | 39.7% | 0.3 x 7.12 = 2.136 | 2.107 | 98.7% | 0 of 3,561 | 75.25 | 172.52 | 3.40 |
| IND | solar | restrictive | 3.4% | 0.05 x 45 = 2.25 | 2.25 | 100.0% | 1 of 51,289 | 242.01 | 403.10 | 0.27 |
| IND | solar | central | 4.8% | 0.1 x 50 = 5 | 5 | 100.0% | 2 of 57,549 | 753.37 | 1,253.59 | 0.83 |
| IND | solar | permissive | 5.5% | 0.25 x 75 = 18.75 | 18.75 | 100.0% | 5 of 59,623 | 3,230.93 | 5,374.13 | 3.57 |
| IND | wind | restrictive | 11.3% | 0.05 x 3.32 = 0.166 | 0.166 | 100.0% | 4 of 55,302 | 58.76 | 94.63 | 0.06 |
| IND | wind | central | 16.2% | 0.075 x 4.99 = 0.3743 | 0.3743 | 100.0% | 26 of 61,464 | 189.81 | 299.50 | 0.20 |
| IND | wind | permissive | 19.1% | 0.15 x 7.12 = 1.068 | 1.068 | 100.0% | 77 of 64,113 | 630.41 | 981.31 | 0.65 |
| BRA | solar | restrictive | 12.6% | 0.1 x 45 = 4.5 | 4.5 | 100.0% | 3 of 173,859 | 4,803.24 | 7,797.53 | 12.65 |
| BRA | solar | central | 18.0% | 0.25 x 50 = 12.5 | 12.5 | 100.0% | 14 of 180,058 | 19,188.34 | 31,068.30 | 50.41 |
| BRA | solar | permissive | 20.8% | 0.35 x 75 = 26.25 | 26.25 | 100.0% | 20 of 181,923 | 46,390.81 | 75,034.37 | 121.75 |
| BRA | wind | restrictive | 16.9% | 0.05 x 3.32 = 0.166 | 0.166 | 100.0% | 12 of 175,183 | 238.53 | 345.05 | 0.56 |
| BRA | wind | central | 25.8% | 0.15 x 4.99 = 0.7485 | 0.7485 | 100.0% | 66 of 181,306 | 1,643.45 | 2,297.21 | 3.73 |
| BRA | wind | permissive | 30.9% | 0.3 x 7.12 = 2.136 | 2.136 | 100.0% | 121 of 183,351 | 5,610.03 | 7,727.82 | 12.54 |

**Conclusion, item 4: ok.** The totals are those of the final round (BRA solar 19,188.34 GW and 31,068.30 TWh; IND 753.37 GW; PRT 264.46 GW). The ceilings are LUF x PD of each scenario as the spec expects (central: solar 12.5 in BRA and PRT, 5.0 in IND; wind 0.7485 in BRA and PRT, 0.3743 in IND), and no cell goes above them (maximum / ceiling at most 100.0%). The maxima observed are **not** the ~10, ~9 and ~3 of the spec: in the final-round tables they are 12.5 (BRA solar), 11.57 (PRT solar) and 5.0 (IND solar); the share below 1 explains the maximum only in PRT (0.926 of the ceiling). In IND and BRA a few cells are entirely eligible (IND solar 2 and wind 26 cells, BRA solar 14 and wind 66 cells, up to 0.04% of the candidates), so the maximum is the ceiling. I did not find where the ~10, ~9 and ~3 come from (probably the limits of a colour scale of an earlier figure); it is not a defect of the table.

## 5. Effective resolution of the figures

| Country | Columns of the analysis grid | Rasters of F5 | Rasters of F3 | Rasters of F2a / F2b | Width of the F5 figures (px) | Image pixels per analysis cell (upper bound): F5 / climate forcing / overview |
|---|---|---|---|---|---|---|
| PRT | 67 | 0.05 deg | 0.01 deg, 0.05 deg | 0.01 deg | 2244 | 33.5 / 24.6 / 26.9 |
| IND | 586 | 0.05 deg | 0.01 deg, 0.05 deg | 0.01 deg | 2244 | 3.8 / 2.8 / 3.1 |
| BRA | 785 | 0.05 deg | 0.01 deg, 0.05 deg | 0.01 deg | 2244 | 2.9 / 2.1 / 2.3 |

**Conclusion, item 5: ok, the pipeline is consistent.** The potential, the CF, the eligibility and the density rasters of the three countries are on the same 0.05 degree grid (the F3 cell tables, 0.05; the aligned layers of F2a and F2b, 0.01); the maps of F5 draw one pixel per 0.05 degree cell (comment of `absolute_maps.py`), and every F5 figure has the same width, 2,244 px. The difference of texture is the number of cells across that width: about 33 image pixels per cell in PRT (67 columns), 3.8 in IND (586) and 2.9 in BRA (785). PRT looks coarse and BRA looks fine because the same width holds 67 or 785 cells, not because the grids differ. The climate-forcing figures draw the 0.05 degree lattice with values that come from a GCM cell of 1 degree or more (members.yaml: 1.0 x 1.25 degrees for GFDL-ESM4; the other GCMs are of the same order or coarser), so they suggest a resolution that the data do not have (as the spec says). The land-eligibility phase writes no figure in the final round.

## 6. Climate forcing by GCM, SSP and window

MIROC6 has no wind channel in F4 (`resource_wind: false`, 5 GCMs for wind), so its wind columns are empty and the wind ensemble means are of 5 GCMs. Mean, minimum and maximum over the cells of the country of the solar ratio (`delta_rsds`), the wind ratio (`delta_wind`) and the warming (`dT`, K); and the change of the energy of the central scenario (like for like, F5) against `m0`.

### PRT

| GCM | SSP | Window | Solar ratio mean (min-max) | Wind ratio mean (min-max) | dT mean (min-max) | dE solar | dE wind |
|---|---|---|---|---|---|---|---|
| ACCESS-CM2 | SSP1-2.6 | 2041-2070 | 1.047 (1.029-1.070) | 0.978 (0.975-0.983) | 1.96 (1.64-2.15) | +3.8% | -4.9% |
| ACCESS-CM2 | SSP1-2.6 | 2071-2100 | 1.061 (1.037-1.091) | 0.966 (0.950-0.980) | 2.24 (1.85-2.45) | +5.0% | -8.1% |
| ACCESS-CM2 | SSP3-7.0 | 2041-2070 | 1.033 (1.015-1.057) | 0.999 (0.988-1.009) | 2.36 (1.92-2.67) | +2.3% | -1.1% |
| ACCESS-CM2 | SSP3-7.0 | 2071-2100 | 1.045 (1.017-1.080) | 0.984 (0.974-0.992) | 3.77 (2.85-4.41) | +3.0% | -4.4% |
| ACCESS-CM2 | SSP5-8.5 | 2041-2070 | 1.050 (1.022-1.082) | 0.983 (0.977-0.991) | 2.45 (1.87-2.87) | +3.9% | -4.3% |
| ACCESS-CM2 | SSP5-8.5 | 2071-2100 | 1.068 (1.027-1.108) | 0.966 (0.956-0.979) | 4.51 (3.35-5.34) | +5.0% | -8.4% |
| CNRM-CM6-1 | SSP1-2.6 | 2041-2070 | 1.038 (1.021-1.055) | 0.996 (0.984-1.008) | 0.89 (0.57-1.17) | +3.5% | -1.3% |
| CNRM-CM6-1 | SSP1-2.6 | 2071-2100 | 1.031 (1.017-1.047) | 1.005 (0.985-1.022) | 0.89 (0.52-1.22) | +2.8% | +0.2% |
| CNRM-CM6-1 | SSP3-7.0 | 2041-2070 | 1.032 (1.016-1.048) | 1.015 (0.999-1.029) | 1.36 (0.86-1.83) | +2.8% | +2.2% |
| CNRM-CM6-1 | SSP3-7.0 | 2071-2100 | 1.041 (1.016-1.063) | 0.990 (0.974-1.002) | 2.99 (2.28-3.64) | +3.1% | -3.0% |
| CNRM-CM6-1 | SSP5-8.5 | 2041-2070 | 1.035 (1.014-1.053) | 0.996 (0.985-1.004) | 1.76 (1.21-2.28) | +2.9% | -1.4% |
| CNRM-CM6-1 | SSP5-8.5 | 2071-2100 | 1.047 (1.020-1.069) | 0.977 (0.956-0.996) | 4.04 (3.09-4.86) | +3.4% | -6.2% |
| GFDL-ESM4 | SSP1-2.6 | 2041-2070 | 1.029 (1.009-1.059) | 0.989 (0.971-0.995) | 0.87 (0.63-1.02) | +2.4% | -2.4% |
| GFDL-ESM4 | SSP1-2.6 | 2071-2100 | 1.031 (1.015-1.060) | 0.985 (0.971-1.003) | 0.62 (0.38-0.86) | +2.9% | -3.9% |
| GFDL-ESM4 | SSP3-7.0 | 2041-2070 | 1.013 (0.994-1.037) | 0.980 (0.948-1.002) | 1.42 (1.08-1.67) | +0.6% | -5.0% |
| GFDL-ESM4 | SSP3-7.0 | 2071-2100 | 1.024 (0.996-1.069) | 0.990 (0.969-1.011) | 2.64 (1.80-3.14) | +1.2% | -3.2% |
| GFDL-ESM4 | SSP5-8.5 | 2041-2070 | 1.028 (1.007-1.052) | 0.990 (0.977-1.007) | 1.71 (1.22-2.00) | +2.0% | -3.1% |
| GFDL-ESM4 | SSP5-8.5 | 2071-2100 | 1.026 (0.995-1.071) | 0.978 (0.958-1.012) | 2.97 (1.79-3.50) | +1.3% | -6.4% |
| IPSL-CM6A-LR | SSP1-2.6 | 2041-2070 | 1.050 (1.026-1.081) | 0.979 (0.965-0.984) | 1.09 (0.55-1.43) | +4.4% | -4.5% |
| IPSL-CM6A-LR | SSP1-2.6 | 2071-2100 | 1.054 (1.031-1.081) | 0.985 (0.973-0.989) | 1.30 (0.76-1.67) | +4.9% | -3.5% |
| IPSL-CM6A-LR | SSP3-7.0 | 2041-2070 | 1.041 (1.015-1.075) | 0.967 (0.949-0.972) | 1.74 (1.03-2.18) | +3.3% | -7.1% |
| IPSL-CM6A-LR | SSP3-7.0 | 2071-2100 | 1.066 (1.024-1.111) | 0.955 (0.927-0.959) | 3.46 (2.26-4.14) | +5.2% | -9.8% |
| IPSL-CM6A-LR | SSP5-8.5 | 2041-2070 | 1.047 (1.016-1.084) | 0.976 (0.963-0.982) | 2.16 (1.32-2.70) | +3.8% | -5.6% |
| IPSL-CM6A-LR | SSP5-8.5 | 2071-2100 | 1.091 (1.032-1.154) | 0.962 (0.942-0.978) | 4.69 (2.98-5.68) | +7.1% | -8.4% |
| MIROC6 | SSP1-2.6 | 2041-2070 | 1.044 (1.027-1.083) | no wind channel | 1.00 (0.38-1.57) | +3.6% | n/a |
| MIROC6 | SSP1-2.6 | 2071-2100 | 1.046 (1.030-1.087) | no wind channel | 1.06 (0.30-1.74) | +4.0% | n/a |
| MIROC6 | SSP3-7.0 | 2041-2070 | 1.037 (1.018-1.075) | no wind channel | 1.32 (0.55-2.03) | +3.0% | n/a |
| MIROC6 | SSP3-7.0 | 2071-2100 | 1.047 (1.025-1.094) | no wind channel | 2.53 (1.39-3.59) | +3.6% | n/a |
| MIROC6 | SSP5-8.5 | 2041-2070 | 1.041 (1.020-1.081) | no wind channel | 1.69 (0.77-2.51) | +3.2% | n/a |
| MIROC6 | SSP5-8.5 | 2071-2100 | 1.062 (1.028-1.117) | no wind channel | 3.62 (1.97-5.03) | +4.5% | n/a |
| MRI-ESM2-0 | SSP1-2.6 | 2041-2070 | 1.024 (1.006-1.063) | 1.011 (0.999-1.018) | 1.20 (0.73-1.43) | +1.6% | +1.9% |
| MRI-ESM2-0 | SSP1-2.6 | 2071-2100 | 1.015 (0.997-1.057) | 1.037 (1.009-1.047) | 0.68 (0.20-0.94) | +0.9% | +6.8% |
| MRI-ESM2-0 | SSP3-7.0 | 2041-2070 | 1.005 (0.989-1.035) | 1.024 (1.000-1.032) | 1.56 (1.00-1.86) | -0.3% | +4.2% |
| MRI-ESM2-0 | SSP3-7.0 | 2071-2100 | 1.006 (0.989-1.044) | 1.023 (0.995-1.033) | 2.25 (1.42-2.77) | -0.5% | +3.8% |
| MRI-ESM2-0 | SSP5-8.5 | 2041-2070 | 1.017 (0.999-1.049) | 1.016 (0.995-1.024) | 1.87 (1.18-2.27) | +0.7% | +2.5% |
| MRI-ESM2-0 | SSP5-8.5 | 2071-2100 | 1.024 (1.001-1.065) | 1.003 (0.977-1.015) | 3.33 (2.09-4.04) | +0.9% | -0.4% |

Ensemble mean by SSP and window: SSP1-2.6 2041-2070: solar 1.039, wind 0.991, dT 1.17; SSP1-2.6 2071-2100: solar 1.040, wind 0.995, dT 1.13; SSP3-7.0 2041-2070: solar 1.027, wind 0.997, dT 1.63; SSP3-7.0 2071-2100: solar 1.038, wind 0.989, dT 2.94; SSP5-8.5 2041-2070: solar 1.036, wind 0.992, dT 1.94; SSP5-8.5 2071-2100: solar 1.053, wind 0.977, dT 3.86. Sanity of the spec (solar ratio of SSP1-2.6 2071-2100 above SSP3-7.0 2041-2070): true in 5 of 6 GCMs. The change of the wind energy against the cube of the wind ratio has Pearson 0.995 and that of the solar energy against the solar ratio 0.974 (36 members); range of dE: solar -0.5% to +7.1%, wind -9.8% to +6.8%.

### IND

| GCM | SSP | Window | Solar ratio mean (min-max) | Wind ratio mean (min-max) | dT mean (min-max) | dE solar | dE wind |
|---|---|---|---|---|---|---|---|
| ACCESS-CM2 | SSP1-2.6 | 2041-2070 | 1.034 (1.008-1.136) | 1.018 (0.960-1.054) | 1.95 (1.30-2.74) | +1.2% | +5.2% |
| ACCESS-CM2 | SSP1-2.6 | 2071-2100 | 1.051 (1.016-1.191) | 1.018 (0.967-1.050) | 2.10 (1.36-2.98) | +2.3% | +5.3% |
| ACCESS-CM2 | SSP3-7.0 | 2041-2070 | 0.946 (0.861-1.029) | 0.991 (0.944-1.020) | 2.22 (1.50-2.74) | -5.1% | +0.4% |
| ACCESS-CM2 | SSP3-7.0 | 2071-2100 | 0.956 (0.851-1.070) | 1.005 (0.922-1.055) | 4.08 (2.86-4.87) | -6.1% | +3.4% |
| ACCESS-CM2 | SSP5-8.5 | 2041-2070 | 1.000 (0.960-1.070) | 1.013 (0.951-1.054) | 2.78 (1.89-3.67) | -1.7% | +4.5% |
| ACCESS-CM2 | SSP5-8.5 | 2071-2100 | 1.013 (0.951-1.122) | 1.034 (0.916-1.113) | 5.38 (3.84-6.70) | -2.3% | +10.2% |
| CNRM-CM6-1 | SSP1-2.6 | 2041-2070 | 1.031 (0.979-1.059) | 1.010 (0.984-1.030) | 1.65 (1.09-2.19) | +2.2% | +1.9% |
| CNRM-CM6-1 | SSP1-2.6 | 2071-2100 | 1.045 (0.978-1.077) | 1.014 (0.988-1.039) | 1.82 (1.19-2.25) | +3.2% | +4.9% |
| CNRM-CM6-1 | SSP3-7.0 | 2041-2070 | 0.967 (0.925-1.017) | 0.987 (0.970-1.006) | 1.86 (1.36-3.13) | -3.5% | -3.4% |
| CNRM-CM6-1 | SSP3-7.0 | 2071-2100 | 0.959 (0.915-1.034) | 0.983 (0.951-1.014) | 3.51 (2.70-5.70) | -5.1% | -3.0% |
| CNRM-CM6-1 | SSP5-8.5 | 2041-2070 | 1.001 (0.955-1.053) | 0.994 (0.968-1.018) | 2.48 (1.82-3.87) | -1.1% | -1.3% |
| CNRM-CM6-1 | SSP5-8.5 | 2071-2100 | 0.996 (0.913-1.072) | 1.011 (0.953-1.061) | 5.08 (3.66-7.77) | -2.6% | +5.4% |
| GFDL-ESM4 | SSP1-2.6 | 2041-2070 | 1.030 (0.995-1.142) | 0.985 (0.932-1.046) | 0.78 (0.27-1.63) | +2.0% | -4.4% |
| GFDL-ESM4 | SSP1-2.6 | 2071-2100 | 1.052 (1.006-1.171) | 0.989 (0.932-1.047) | 0.78 (0.25-1.85) | +3.3% | -3.3% |
| GFDL-ESM4 | SSP3-7.0 | 2041-2070 | 0.937 (0.890-1.073) | 0.983 (0.917-1.071) | 1.27 (0.64-2.28) | -6.2% | -3.6% |
| GFDL-ESM4 | SSP3-7.0 | 2071-2100 | 0.942 (0.892-1.072) | 0.994 (0.906-1.087) | 2.59 (1.54-3.86) | -6.4% | -0.3% |
| GFDL-ESM4 | SSP5-8.5 | 2041-2070 | 0.988 (0.960-1.112) | 0.979 (0.911-1.048) | 1.55 (0.88-2.41) | -2.0% | -5.0% |
| GFDL-ESM4 | SSP5-8.5 | 2071-2100 | 1.008 (0.969-1.153) | 1.007 (0.907-1.104) | 3.16 (1.99-4.51) | -1.1% | +3.0% |
| IPSL-CM6A-LR | SSP1-2.6 | 2041-2070 | 1.006 (0.961-1.023) | 0.973 (0.867-1.008) | 1.34 (0.83-2.83) | +0.2% | -7.1% |
| IPSL-CM6A-LR | SSP1-2.6 | 2071-2100 | 1.006 (0.951-1.031) | 0.972 (0.867-1.015) | 1.28 (0.95-2.79) | +0.1% | -7.4% |
| IPSL-CM6A-LR | SSP3-7.0 | 2041-2070 | 0.971 (0.946-0.987) | 1.008 (0.869-1.078) | 2.12 (1.49-3.49) | -3.2% | +2.6% |
| IPSL-CM6A-LR | SSP3-7.0 | 2071-2100 | 0.972 (0.869-0.998) | 1.033 (0.811-1.129) | 4.10 (2.79-6.17) | -3.9% | +10.6% |
| IPSL-CM6A-LR | SSP5-8.5 | 2041-2070 | 0.975 (0.934-1.000) | 0.988 (0.854-1.051) | 2.45 (1.74-4.23) | -3.3% | -2.9% |
| IPSL-CM6A-LR | SSP5-8.5 | 2071-2100 | 0.981 (0.833-1.013) | 1.035 (0.765-1.116) | 5.49 (3.69-8.15) | -3.9% | +12.4% |
| MIROC6 | SSP1-2.6 | 2041-2070 | 1.009 (0.975-1.051) | no wind channel | 0.85 (0.12-1.85) | +0.3% | n/a |
| MIROC6 | SSP1-2.6 | 2071-2100 | 1.025 (0.992-1.078) | no wind channel | 0.97 (0.28-1.77) | +1.2% | n/a |
| MIROC6 | SSP3-7.0 | 2041-2070 | 0.969 (0.951-1.000) | no wind channel | 1.15 (0.24-2.31) | -3.0% | n/a |
| MIROC6 | SSP3-7.0 | 2071-2100 | 0.967 (0.937-1.014) | no wind channel | 2.06 (0.70-4.03) | -3.9% | n/a |
| MIROC6 | SSP5-8.5 | 2041-2070 | 0.996 (0.963-1.045) | no wind channel | 1.73 (1.01-2.97) | -1.1% | n/a |
| MIROC6 | SSP5-8.5 | 2071-2100 | 0.993 (0.934-1.062) | no wind channel | 3.05 (1.97-5.49) | -2.1% | n/a |
| MRI-ESM2-0 | SSP1-2.6 | 2041-2070 | 1.026 (1.003-1.068) | 1.007 (0.846-1.067) | 1.32 (0.54-1.90) | +1.0% | +2.0% |
| MRI-ESM2-0 | SSP1-2.6 | 2071-2100 | 1.054 (1.009-1.107) | 1.017 (0.752-1.085) | 1.58 (0.87-2.20) | +3.0% | +3.9% |
| MRI-ESM2-0 | SSP3-7.0 | 2041-2070 | 0.938 (0.909-0.982) | 0.982 (0.823-1.053) | 1.52 (0.99-2.59) | -5.9% | -2.9% |
| MRI-ESM2-0 | SSP3-7.0 | 2071-2100 | 0.951 (0.916-0.983) | 0.990 (0.803-1.079) | 2.93 (1.98-4.13) | -6.0% | -1.4% |
| MRI-ESM2-0 | SSP5-8.5 | 2041-2070 | 0.985 (0.961-1.030) | 0.993 (0.596-1.072) | 2.20 (1.15-3.23) | -2.7% | -0.0% |
| MRI-ESM2-0 | SSP5-8.5 | 2071-2100 | 1.008 (0.955-1.060) | 1.022 (0.597-1.107) | 4.17 (2.81-5.16) | -1.9% | +8.7% |

Ensemble mean by SSP and window: SSP1-2.6 2041-2070: solar 1.023, wind 0.998, dT 1.31; SSP1-2.6 2071-2100: solar 1.039, wind 1.002, dT 1.42; SSP3-7.0 2041-2070: solar 0.955, wind 0.990, dT 1.69; SSP3-7.0 2071-2100: solar 0.958, wind 1.001, dT 3.21; SSP5-8.5 2041-2070: solar 0.991, wind 0.993, dT 2.20; SSP5-8.5 2071-2100: solar 1.000, wind 1.022, dT 4.39. Sanity of the spec (solar ratio of SSP1-2.6 2071-2100 above SSP3-7.0 2041-2070): true in 6 of 6 GCMs. The change of the wind energy against the cube of the wind ratio has Pearson 0.982 and that of the solar energy against the solar ratio 0.970 (36 members); range of dE: solar -6.4% to +3.3%, wind -7.4% to +12.4%.

### BRA

| GCM | SSP | Window | Solar ratio mean (min-max) | Wind ratio mean (min-max) | dT mean (min-max) | dE solar | dE wind |
|---|---|---|---|---|---|---|---|
| ACCESS-CM2 | SSP1-2.6 | 2041-2070 | 1.030 (0.991-1.069) | 1.030 (0.984-1.108) | 2.01 (0.93-2.40) | +3.1% | +11.4% |
| ACCESS-CM2 | SSP1-2.6 | 2071-2100 | 1.032 (0.996-1.075) | 1.026 (0.979-1.109) | 2.09 (1.12-2.43) | +3.5% | +10.2% |
| ACCESS-CM2 | SSP3-7.0 | 2041-2070 | 1.016 (0.967-1.038) | 1.033 (0.982-1.089) | 2.57 (1.32-3.10) | +1.3% | +7.9% |
| ACCESS-CM2 | SSP3-7.0 | 2071-2100 | 1.025 (0.949-1.064) | 1.069 (0.993-1.209) | 4.62 (2.55-5.73) | +1.7% | +14.6% |
| ACCESS-CM2 | SSP5-8.5 | 2041-2070 | 1.028 (0.968-1.071) | 1.052 (0.995-1.159) | 3.15 (1.60-3.96) | +2.3% | +11.9% |
| ACCESS-CM2 | SSP5-8.5 | 2071-2100 | 1.042 (0.951-1.103) | 1.101 (0.991-1.296) | 6.06 (3.31-7.23) | +3.2% | +19.7% |
| CNRM-CM6-1 | SSP1-2.6 | 2041-2070 | 1.007 (0.990-1.025) | 1.011 (0.975-1.037) | 1.31 (0.56-1.89) | +0.2% | +0.7% |
| CNRM-CM6-1 | SSP1-2.6 | 2071-2100 | 1.011 (0.993-1.033) | 1.017 (0.988-1.051) | 1.46 (0.91-1.92) | +0.7% | +3.3% |
| CNRM-CM6-1 | SSP3-7.0 | 2041-2070 | 1.000 (0.979-1.022) | 1.028 (0.973-1.089) | 2.08 (1.27-2.72) | -0.8% | +2.7% |
| CNRM-CM6-1 | SSP3-7.0 | 2071-2100 | 1.000 (0.937-1.035) | 1.057 (0.981-1.170) | 3.94 (2.07-4.77) | -1.2% | +7.9% |
| CNRM-CM6-1 | SSP5-8.5 | 2041-2070 | 1.003 (0.969-1.022) | 1.033 (0.983-1.101) | 2.46 (1.40-3.03) | -0.4% | +4.9% |
| CNRM-CM6-1 | SSP5-8.5 | 2071-2100 | 1.009 (0.939-1.043) | 1.094 (0.985-1.286) | 5.31 (2.84-6.22) | -0.8% | +13.3% |
| GFDL-ESM4 | SSP1-2.6 | 2041-2070 | 1.017 (0.982-1.066) | 1.063 (0.834-1.500) | 1.03 (0.48-1.64) | +0.8% | +12.5% |
| GFDL-ESM4 | SSP1-2.6 | 2071-2100 | 1.016 (0.981-1.066) | 1.079 (0.811-1.500) | 0.85 (0.17-1.47) | +0.9% | +18.0% |
| GFDL-ESM4 | SSP3-7.0 | 2041-2070 | 1.005 (0.976-1.039) | 1.087 (0.961-1.500) | 1.71 (0.89-2.69) | -0.6% | +14.6% |
| GFDL-ESM4 | SSP3-7.0 | 2071-2100 | 1.011 (0.956-1.064) | 1.120 (0.969-1.500) | 3.31 (1.92-4.93) | -0.4% | +19.5% |
| GFDL-ESM4 | SSP5-8.5 | 2041-2070 | 1.016 (0.983-1.050) | 1.115 (0.914-1.500) | 2.04 (1.07-2.97) | +0.6% | +27.0% |
| GFDL-ESM4 | SSP5-8.5 | 2071-2100 | 1.023 (0.963-1.085) | 1.158 (0.917-1.500) | 3.92 (2.23-5.83) | +0.6% | +32.1% |
| IPSL-CM6A-LR | SSP1-2.6 | 2041-2070 | 1.009 (0.965-1.050) | 1.026 (0.949-1.156) | 1.20 (0.75-1.52) | +0.2% | +5.3% |
| IPSL-CM6A-LR | SSP1-2.6 | 2071-2100 | 1.012 (0.975-1.061) | 1.039 (0.941-1.169) | 1.22 (0.77-1.61) | +0.3% | +9.9% |
| IPSL-CM6A-LR | SSP3-7.0 | 2041-2070 | 1.001 (0.953-1.051) | 1.061 (0.957-1.244) | 2.09 (1.40-2.90) | -1.7% | +12.1% |
| IPSL-CM6A-LR | SSP3-7.0 | 2071-2100 | 1.017 (0.938-1.080) | 1.131 (0.963-1.385) | 4.11 (2.66-5.43) | -0.8% | +25.7% |
| IPSL-CM6A-LR | SSP5-8.5 | 2041-2070 | 1.014 (0.954-1.059) | 1.119 (0.942-1.450) | 2.55 (1.61-3.46) | -0.2% | +32.9% |
| IPSL-CM6A-LR | SSP5-8.5 | 2071-2100 | 1.039 (0.938-1.114) | 1.198 (0.963-1.500) | 5.49 (3.33-7.31) | +0.7% | +48.2% |
| MIROC6 | SSP1-2.6 | 2041-2070 | 1.016 (0.972-1.062) | no wind channel | 0.87 (-0.31-1.54) | +0.9% | n/a |
| MIROC6 | SSP1-2.6 | 2071-2100 | 1.021 (0.978-1.075) | no wind channel | 1.07 (0.25-1.90) | +1.4% | n/a |
| MIROC6 | SSP3-7.0 | 2041-2070 | 1.014 (0.981-1.047) | no wind channel | 1.56 (0.67-2.58) | +0.9% | n/a |
| MIROC6 | SSP3-7.0 | 2071-2100 | 1.018 (0.974-1.060) | no wind channel | 2.74 (1.38-4.15) | +1.1% | n/a |
| MIROC6 | SSP5-8.5 | 2041-2070 | 1.017 (0.977-1.051) | no wind channel | 1.90 (0.83-3.21) | +0.9% | n/a |
| MIROC6 | SSP5-8.5 | 2071-2100 | 1.025 (0.958-1.068) | no wind channel | 3.29 (1.61-4.96) | +1.1% | n/a |
| MRI-ESM2-0 | SSP1-2.6 | 2041-2070 | 1.018 (0.986-1.049) | 1.003 (0.944-1.036) | 1.14 (-0.49-2.46) | +1.3% | +2.8% |
| MRI-ESM2-0 | SSP1-2.6 | 2071-2100 | 1.010 (0.966-1.040) | 0.990 (0.882-1.058) | 1.09 (-0.97-3.01) | -0.0% | -3.7% |
| MRI-ESM2-0 | SSP3-7.0 | 2041-2070 | 0.993 (0.950-1.031) | 0.997 (0.960-1.093) | 1.68 (1.15-3.83) | -1.9% | -1.0% |
| MRI-ESM2-0 | SSP3-7.0 | 2071-2100 | 0.989 (0.924-1.042) | 0.994 (0.937-1.125) | 2.76 (2.01-4.96) | -2.6% | -2.8% |
| MRI-ESM2-0 | SSP5-8.5 | 2041-2070 | 1.005 (0.958-1.043) | 1.009 (0.973-1.074) | 1.98 (1.13-4.04) | -0.6% | +3.3% |
| MRI-ESM2-0 | SSP5-8.5 | 2071-2100 | 1.005 (0.945-1.065) | 1.004 (0.959-1.108) | 3.53 (2.59-5.55) | -1.5% | +0.7% |

Ensemble mean by SSP and window: SSP1-2.6 2041-2070: solar 1.016, wind 1.027, dT 1.26; SSP1-2.6 2071-2100: solar 1.017, wind 1.030, dT 1.30; SSP3-7.0 2041-2070: solar 1.005, wind 1.041, dT 1.95; SSP3-7.0 2071-2100: solar 1.010, wind 1.074, dT 3.58; SSP5-8.5 2041-2070: solar 1.014, wind 1.066, dT 2.35; SSP5-8.5 2071-2100: solar 1.024, wind 1.111, dT 4.60. Sanity of the spec (solar ratio of SSP1-2.6 2071-2100 above SSP3-7.0 2041-2070): true in 6 of 6 GCMs. The change of the wind energy against the cube of the wind ratio has Pearson 0.965 and that of the solar energy against the solar ratio 0.876 (36 members); range of dE: solar -2.6% to +3.5%, wind -3.7% to +48.2%.

**Conclusion, item 6: the table is made and nothing indicates a bug.** (i) The ordering the spec flags (BRA solar higher in SSP1-2.6 at the end of the century than in SSP3-7.0 at mid-century) is in 6 of 6 GCMs in BRA and IND and in 5 of 6 in PRT, so it is not a property of ACCESS-CM2 alone; it follows the GCMs' own cloud and aerosol response and cannot be checked against another source here. (ii) The energy follows the forcing: the change of the wind energy tracks the cube of the wind ratio (Pearson 0.96 to 0.995) and that of the solar energy tracks the solar ratio (0.88 to 0.97). (iii) The BRA wind has the largest change: IPSL-CM6A-LR SSP5-8.5 2071-2100 has a mean wind ratio of 1.198 (1.5 at the upper limit of the valid range in 0.01% of the cells) and +48% of energy; the capacity does not change, only the energy. This is a climate signal of that GCM in the north-east of Brazil, in the range of what the factor allows [0.5, 1.5], and it is for the thesis to discuss (ensemble spread), not a defect of the computation. (iv) The ensemble mean is what the spec (decision 6) asks to be drawn, with the agreement hatching.

## 7. What the audit did not do

It does not compare the totals with published potentials (OQ-057), does not check the sub-pixel shares of F3 (checked in COMMANDS 52 to 58), and does not give an LCOE curve (F6 has not run). The consumption figures above are to be confirmed before they enter the thesis.
