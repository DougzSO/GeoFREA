# GeoFREA v1: record of the results and of the diagnosis

Written 2026-11-24 for the author and for readers of the thesis who need the v1 results as the development stage that led to v2. It summarises and does not recompute: every number comes from the source named in its section, and the scripts of the tag `v1.1` reproduce the artifacts. The source documents are in `docs/evidence/v1_diagnostics/` (`GeoFREA_v1_1_explained.md`, `exploratory_v1_1.md`, the synthesis `D0_synthesis.md` and the reports D1 to D5; they are written in Portuguese). Numbers use a decimal point and no thousands separator, as in the artifacts. Window 2041-2070, central land scenario and reference member `m0`, unless stated.

## 1. Status

| Item | Value |
|---|---|
| Tags | `v1.0` (pre-registered results), `v1.1` (v1.0 plus the exploratory analyses and the F7b variant), `v1-final` (last state with the v1 records in the work tree) |
| Pre-registration | tag `prereg-v1`; digest of the subset in `core/preregistration.py` |
| Countries and technologies | Brazil, India, Portugal; ground-mounted solar PV and onshore wind |
| Verdict | The pre-registered results of v1.0 stand as results of a development stage. The diagnosis of Section 5 motivated v2 (`docs/METHODOLOGY.md`, DEC-001). |

## 2. What v1 asked and how it worked

Question: which sites to prioritise for solar and wind, in a way that stays good across many climate futures, treating physical-climate and techno-economic uncertainty together. The decision unit was the 0.05 degree cell.

- **Chain.** F1 data acquisition, F1b audit, F2a alignment to a 0.01 degree grid, F2b siting layers, F3 land eligibility (three land scenarios: restrictive, central, permissive), F4 climate change factors, F5 technical potential, F6 LCOE, F7 robustness and hypotheses, F7b external validation, F8 synthesis.
- **Climate.** Six CMIP6 models (GFDL-ESM4, MIROC6, ACCESS-CM2, IPSL-CM6A-LR, CNRM-CM6-1, MRI-ESM2-0; the wind channel of MIROC6 was excluded, so wind had five), three SSPs, windows 2041-2070 (core) and 2071-2100, reference 1995-2014, delta-change factors.
- **Futures.** Climate members crossed with 4000 Latin hypercube draws of cost parameters: 72000 futures for solar and 60000 for wind per country (`GeoFREA_v1_1_explained.md`, section 5c, column "futuros").
- **Decision metrics.** Relative max-regret `MR` of the LCOE (primary), satisficing robustness `SR` under a minimum generation constraint, PRIM scenario discovery, top-k sets (k = 10% of the candidate cells), and an economic threshold `tau` calibrated to the IRENA reference plant.
- **Hypotheses.** H1 stability of the ranking across SSPs, H2 aggregation by Admin1 changes the selection, H3 robust against nominal shortlist, H4 dominant uncertainty axis differs between countries, H5 climate pressure on the economic potential that supports a national target.

## 3. Results of v1.0 (pre-registered)

Source of the tables of this section: `GeoFREA_v1_1_explained.md`, section 5, from `outputs/<ISO>/robustness_analysis/artifacts/` and `outputs/thesis/`.

### 3.1 Potential and cost

| Country | Tech | P central (GW) | P restrictive (GW) | P permissive (GW) | E central (TWh/yr) |
|---|---|---|---|---|---|
| PRT | solar | 153.3 | 32.01 | 563.8 | 247.3 |
| PRT | wind | 22.79 | 3.37 | 77.04 | 52.17 |
| IND | solar | 806.1 | 211.6 | 4890.8 | 1331.6 |
| IND | wind | 214.1 | 60.13 | 879.6 | 331.5 |
| BRA | solar | 16489.5 | 4183.0 | 47080.7 | 26741.6 |
| BRA | wind | 1990.7 | 372.2 | 6071.5 | 2712.2 |

| Country | Tech | LCOE p10 | LCOE p50 | LCOE p90 (USD/MWh) | tau | capacity with LCOE up to tau (GW) | share | candidate cells |
|---|---|---|---|---|---|---|---|---|
| PRT | solar | 47.04 | 50.38 | 53.5 | 54.53 | 152.3 | 0.9934 | 3415 |
| PRT | wind | 48.38 | 63.65 | 92.27 | 49.64 | 2.033 | 0.08918 | 3332 |
| IND | solar | 26.69 | 29.03 | 32.17 | 28.26 | 454.6 | 0.5639 | 93701 |
| IND | wind | 42.68 | 71.79 | 143.02 | 36.43 | 13.58 | 0.06342 | 75535 |
| BRA | solar | 47.71 | 52.3 | 59.59 | 43.97 | 12.35 | 0.0007487 | 190521 |
| BRA | wind | 63.44 | 144.37 | 383.54 | 31.95 | 2.01 | 0.00101 | 178289 |

The LCOE is the distribution across cells of the nominal LCOE of `m0`. Brazilian wind has the longest tail (p90 383.54 against p50 144.37).

### 3.2 Hypotheses (primary variant)

| Hypothesis | Result | Numbers |
|---|---|---|
| H1 | partially supported, stable core, in the six pairs | core share `C_k` from 0.8532 to 0.9737, above the threshold 0.60; vulnerable share `V_k` 0 in five pairs and 0.002947 in BRA solar, below 0.20; reference `p_k^2` about 0.01 |
| H2 | not supported in the six pairs | overlap `O` from 0.3197 to 0.5097, above `gamma` = 0.30 |
| H3 | not supported in the six pairs | share `D` from 0 to 0.009224, far below `delta` = 0.20; price `Pi` from -0.0009942 to 0.001057; benefit `B` from 0.001071 to 0.007432 |
| H4 | not supported for both technologies | five of six pairs have zero displacement on both axes; IND solar is climate-dominated (`rho` = 1, `D_clim` = 0.001533) |
| H5 | not assessable | no national target in PRT solar, PRT wind, BRA wind; target not met at reference in IND wind and BRA solar; IND solar has slack `H_0` = 12.29 TWh/yr and `R_loss` = 3.816, but the joint verdict is missing because no hazard channel has a threshold |
| PRIM | `no_cases` in the six pairs | 72000 futures (solar) and 60000 (wind); 0 cases |

Sensitivity: the verdicts of H1, H3 and H5 do not change in any variant of any pair; H2 changes verdict in part of the variants because it depends on `gamma` (9 of 20 variants in PRT solar, 6 of 20 in PRT wind, 4 of 21 in IND solar, 9 of 21 in IND wind, 10 of 21 in BRA solar, 4 of 20 in BRA wind); the 0.1 degree scale ran from F3 to F7 in the three countries (BRA F7 6233 s). Source: `GeoFREA_v1_1_explained.md`, section 5e.

### 3.3 External validation (F7b)

Mean share of the capacity of existing plants (GEM) that falls in pixels excluded by at least one constraint: 0.7391 (PRT solar), 0.747 (PRT wind), 0.7687 (IND solar), 0.8369 (IND wind), 0.5132 (BRA solar), 0.3319 (BRA wind) (`GeoFREA_v1_1_explained.md`, section 5d). The enrichment ratio of the cheapest LCOE decile is from 2.955 (IND solar) to 9.238 (BRA wind). Published potentials were registered for Brazil only: wind 143 GW (Amarante, 2001) and 14580.0 GW (Eurek et al., 2017) against 1990.7 GW of F5; solar 307 GW and 28519.0 GW (EPE, 2018) against 16489.5 GW.

Thesis outputs: 17 per country (170 files) in `outputs/thesis/`.

## 4. What the v1.0 results say, and what they do not

The ranking of cells barely changes between climate futures (H1 core stable, H3 and H4 with near-zero displacement, PRIM with no cases) and the regional aggregation overlaps strongly with the cell selection (H2). That is a property of the design, shown by the diagnosis below, and not proof that climate does not matter: the climate enters only as a change of irradiance, temperature and wind speed that shifts the cost of all cells together, and v1.0 measures exposure to extremes, not loss. This is the reason v2 changes the question (DEC-001).

## 5. Diagnosis of v1.0 (D1 to D5)

Source: `D0_synthesis.md` (table of findings N1 to N23, with classes A defect of code, B property of the design to declare, C choice of calibration or threshold, D effect of input data). Numbers below are from its table; the origin section of each is in that table.

| Finding | Content | Class |
|---|---|---|
| N1 | `tau` comes from the IRENA reference plant. The economic domain (capacity with LCOE up to `tau`) is 0.075% in BRA solar, 0.103% in BRA wind, 6.3% in IND wind, 8.9% in PRT wind, and 99.3% in PRT solar | C |
| N2 | Between `tau` and the cells there are three basis differences: life (25 against 30 years: from -1.40 to -3.63 USD/MWh), O&M, and degradation | C |
| N3 | `SR` = 0 in 83.4% of the cells of BRA wind and 79.7% of IND wind: satisficing does not discriminate | C |
| N4 | H5 at the edge in IND solar and BRA solar | B |
| N5 | The LHS parameters of most weight (capex, O&M, rate, life) shift all cells of a country together; the cell x future interaction is from 0.13% to 1.75% of the variance of log(LCOE) on the climate axis; the Spearman of the nominal ranking with each future has a minimum of 0.892 | B |
| N6 | `MR` follows the nominal LCOE: Spearman from 0.930 to 0.999 | B |
| N7 | Two displacement measures answer differently (`V_k` 0 in five pairs against a worst rank beyond 2k in 0.00% to 3.55% of the top-k) | B |
| N8 | Exploratory top-k of 1% and m = k/2: `V_k` from 0 to 0.138 (IND solar), below 0.20 in every pair | C |
| N9 | `O` of H2 from 0.320 to 0.510 in the six pairs, driven by 1 to 3 Admin1 regions | B |
| N10 | The H2 verdict changes with `gamma` and with the partition (18 to 37 regions) | C |
| N11 | Land cover of 2020 already shows later plants as built (solar: 0.100 against 0.011 in PRT, 0.164 against 0.019 in IND, 0.048 against 0.005 in BRA) | D |
| N12 | Exact E5 from 0.23 to 0.56 in four pairs, 82% to 95% from the classes the central scenario excludes | C |
| N13 | The GEM location is approximate for most units: in IND wind only 58 of 679 units (9.4% of the capacity) are exact; in BRA solar 601 of 3946 | D |
| N14 to N16 | The central scenario is stricter than the practice of existing plants on slope (E4), settlements (E6) and protected areas (E1: 8% to 28% of the capacity inside protected areas in five of six pairs) | C |
| N17 | The class "old plant in a now restricted area" cannot be assessed (no `STATUS_YR` in the project WDPA) | D |
| N18 | The 0.01 degree pixel (about 1.1 km) mixes the plant footprint with its surroundings | B |
| N19 | The convergence phase ranked 178285 cells in BRA wind against 171181 in F7 (difference 7104 `incomplete_ensemble` cells); the only code defect (A) | A |
| N20 | PRT solar: `1 - Jaccard` of 0.0116, 0.0231, 0.0116 from 500 to 4000 draws; 1 swap per step at 8000 and 16000 (0.0058) | B, C |
| N21 | BRA wind: 35.0% of the cells (62437) have LCOE above 200 USD/MWh and change only the size of the top-k (17119 with them, 11444 without) | B |
| N22 | The top-k is by cell count, not capacity: from 0.6% (BRA solar) to 33.5% (PRT wind) of the nominal top-k is below 1 MW | B |
| N23 | The five lowest-LCOE cells of BRA wind have CF from 0.642 to 0.691, reproduced from the Global Wind Atlas | D |

Tests that passed: the LCOE rebuilt from tables equals F6 (difference 0) in the six pairs; `tau` recomputed equals the registered one; the statistics of H2 and H3 were reproduced; E5 and E4 recomputed with error 0 against F7b.

## 6. Exploratory analyses of v1.1

Declared before they were computed (v1 DEC-098) and with one definition corrected afterwards (v1 DEC-100); they changed no pre-registered verdict. Source: `exploratory_v1_1.md` and `GeoFREA_v1_1_explained.md`, section 6A.

- **H5c, cost of reaching the target without `tau`.** Maximum increase of the marginal cost `Delta_MC`: IND solar 7.82% (target 447 GW, G = 759.4 TWh/yr), IND wind 18.98% (138 GW, 257.2 TWh/yr), BRA solar 2.20% (90 GW, 160.3 TWh/yr). The first calculation converted the target through `tau` and gave 113.3% of the F7 set energy in IND wind; the corrected definition gives 77.6%. At the levels of 5%, 10% and 25% of the set energy, `Delta_MC` is from 0.74% (PRT solar) to 8.44% (IND wind).
- **VUL, own vulnerability.** `VUL_clim` (largest relative increase of the LCOE of a cell over the central members) has median from 0.29% (PRT solar) to 11.55% (IND wind); `VUL_tec` median from 18.7% to 31.5%, almost the same in every cell of a country; the sign of its correlation with the LCOE differs between pairs.
- **`V_f`, why PRIM ended with no cases.** The largest share of capacity displaced in any future is 4.22% (BRA solar), against the PRIM threshold 0.20.
- **`tau` on the cell basis.** With the life and O&M that F6 applies to the cells, `tau` is lower by 4.4% (BRA wind) to 11.7% (IND solar), and the capacity below it falls (PRT solar 152.3 to 87.1 GW; BRA solar 12.3 to 0.0 GW).
- **F7b with exact location only.** The combined excluded share falls from 0.837 to 0.535 in IND wind (58 units) and from 0.513 to 0.409 in BRA solar (601 units); it barely changes in PRT and BRA wind.

## 7. Reproduction and costs

- **Code and environment.** `git checkout v1.1`, with the `ci/constraints.txt` of that tag (Python 3.11 or 3.12). The synthetic world and the regression fixtures (tag `regression-fixtures-v1`) run in CI.
- **Cost.** The chain from F2b onward costs 13.7 h of cold wall time for the three countries combined, dominated by Brazil (`D0_synthesis.md`, section 4: `lcoe_modeling` 1.5 / 22.8 / 52.2 min and `sample_size_convergence` 1.2 / 8.8 / 20.6 min for PRT / IND / BRA, with F7, its maps and the synthesis on top).
- **Data.** Inputs are in `GeoFREA_data/raw`; the v1.1 outputs stay in `GeoFREA_data/outputs/<ISO>/` until the v2 against v1.1 comparison exists. After it, the outputs that only v1 uses (`lcoe_modeling`, `robustness_analysis`, `exploratory_analysis` and the `__0p1deg` folders) and `raw/cmip6` move to `_arquivo_GeoFREA/v1/data/`, and this section records their original paths so that v1 can be restored and reproduced.

## 8. What carries over to v2

`docs/v1/inheritance.md` lists, one row per item of the registers (M-, DEC, OQ, L) that holds in v2: v1 ID, summary, destination, what changed. Items that only describe v1 appear there by ID and the word "historical".
