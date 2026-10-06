# Distance to grid/roads and the connection-cost model — literature evidence and what applies to GeoFREA

Date: 2026-10-06. Status: evidence recorded; the methodology change (section 5) was **authorized and implemented on 2026-10-06**
(OQ-040 closed, METHODOLOGY 2.0.0, D-F2a-004); Douglas's stated direction for the cost model (OQ-041) is to preserve
the real distance and model connection cost as a function of distance and infrastructure characteristics; the
extension is deferred until sourced data exists. Related: `distance_cap_km` (M-F2a-03), `dist_grid_km`/`dist_road_km`
(M-F3-03), the CAPEX formula (M-F6-01), cost parameters (OQ-001), limitations L-018 and L-019.

The research below was written by Douglas (chat of 2026-10-06, "Evidências da literatura e implicações para o
tratamento da distância de conexão", sections 6-12) and is stored here so the reasoning can be recovered later.
Source existence and the numbers I could check were verified on 2026-10-06 (table in section 2); everything not
verified is marked as such and must be re-checked before it is cited in the thesis.

## 1. The question

`distance_cap_km` is the largest distance stored in the distance-to-grid, -roads and -rivers rasters: a pixel farther
than the cap carries the cap value (100 km today, `core/constants.py::LINEAR_FEATURE_MAX_DIST_KM`, no source).
The cap is applied only after the full distance is computed (`np.clip` in `grid_alignment/vector_alignment.py`),
so it saves no computation; it is a coding choice.

It was inert in the old design (distances fed proximity decays of 5-30 km). It is not inert now: the method
monetizes distance, `CAPEX_total = ... + P_MW*dist_grid_km*grid_cost_usd_per_mw_km + ... + dist_road_km*road_cost_usd_per_km`
(M-F6-01). A pixel beyond the cap is billed for the cap distance only, so its connection CAPEX, and therefore its
LCOE, is understated. The risk is in remote cells (BRA's Amazon and Pantanal are the likely case; PRT is not affected:
mainland max distance to the grid is 33.7 km, to roads 12.7 km, to rivers 7.0 km, measured on 93,149 pixels).

## 2. Sources and verification status

| # | Source | What was checked | Status |
|---|---|---|---|
| S1 | Cheng, C.; Blakers, A.; Weber, T.; Catchpole, K.; Nadolny, A. High-Resolution Siting of Utility-Scale Solar and Wind: Bridging Pixel-Level Costs and Regional Planning. *Energies* 18(16), 4361, 2025. DOI 10.3390/en18164361 | Exists. Abstract confirms 250 m pixels, "distance-weighted connection costs", and that ~15% of local government areas, mainly within 100 km of the existing 275-500 kV backbone, can host more than half of the least-cost capacity. | **Verified** (abstract) |
| S2 | Cheng, C.; Silalahi, D. F.; Roberts, L.; Nadolny, A.; Weber, T.; Blakers, A.; Catchpole, K. Heatmaps to Guide Siting of Solar and Wind Farms. *Energies* 18(4), 891, 2025. DOI 10.3390/en18040891 | Exists. Abstract confirms an indicative cost per pixel from resource, proximity to transmission and load centres, exclusions; Australia, South Korea, Indonesia; connection costs matter most in Australia and Indonesia, less in South Korea (small, dense grid). | **Verified** (abstract). The claim "overhead transmission adds relatively little up to ~100 km" was not found in the abstract. |
| S3 | DeSantis, D.; James, B. D.; Houchins, C.; Saur, G.; Lyubovsky, M. Cost of long-distance energy transmission by different carriers. *iScience* 24(12), 103495, 2021. DOI 10.1016/j.isci.2021.103495 | Exists; compares electricity, gas and liquid carriers; electricity is the costliest per delivered MWh (lower carrying capacity per line). | **Verified** existence and thrust. The figure ~US$41.5/MWh for 1,000 miles and the HVDC/HVAC crossover were **not verified**. |
| S4 | Jiang, H.; Yao, L.; Qin, J.; Bai, Y.; Brandt, M.; Lian, X.; Davis, S. J.; Lu, N.; Zhao, W.; Liu, T.; Zhou, C. Globally interconnected solar-wind system addresses future electricity demands. *Nature Communications* 16, 2025. DOI 10.1038/s41467-025-59879-9 | Exists. **Citation correction:** the first author is Jiang, H. (Lu, N., Zhao, W. and Liu, T. are co-authors), not "Lu, N. et al." as in the text received. The article number and the 10 km interconnectability value were **not verified**. | **Verified existence; citation corrected; 10 km unverified** |
| S5 | Jahangir, M. H.; Behrad, A.; Goodarzi, K. Techno-economic assessment of rural electrification using renewables: effects of climate and grid distance. *Energy Strategy Reviews* 65, 102225, 2026. DOI 10.1016/j.esr.2026.102225 | Not found by search. The ~70 km grid-extension break-even for Iran is unverified. | **Not verified** |
| S6 | Thunder Said Energy. Cost of grid interconnection (New Energies Research), 2026: ~US$100-300/kW interconnection, ~US$3-10/kW·km over ~10-70 km (10-100 km as a wide range). | Not opened. Industry research consultancy, not peer reviewed. | **Not verified; non-peer-reviewed** |
| S7 | IEA ETSAP. Technology Brief E12: Electricity Transmission and Distribution, 2014 (US$746-3,318/MW·km for 500-765 kV lines, plus substations and interconnections). | Not found by search. The author field in the text received is truncated ("VAHDA..."). | **Not verified; citation incomplete** |
| S8 | EPE (Brazil). Bases de Dados - Leilões de Transmissão (2026); Preços de Referência para Linhas de Transmissão Subterrâneas em CA, Ciclo de Planejamento 2026 (230, 345, 500 kV). | Not opened. Official Brazilian planning source. | **Not verified; primary Brazilian source for calibration** |

## 3. What the evidence says (Douglas's synthesis, with the caveats above)

- The literature has no universal distance limit between a plant and the grid. Distance matters more as it grows,
  but also depends on project capacity, voltage, existing infrastructure, line technology, losses and network
  reinforcements (S1, S2, S3, S6, S7).
- Spatially explicit siting studies put distance **into the site cost continuously** instead of cutting sites off
  at a distance (S1, S2). In S1, ~100 km from the 275-500 kV backbone is an economically relevant scale, not a
  viability boundary.
- Numbers that look like thresholds are context-specific: ~70 km in an Iranian rural-electrification study (S5, unverified);
  10 km as a conservative pre-filter in a global model (S4, unverified). Neither transfers as a cutoff.
- At long distances a single linear US$/MW·km constant is unsafe: technology (HVDC vs HVAC), losses, voltage and
  terminal costs change the cost-distance relation (S3, S7). Quoted per-kilometre figures also differ by roughly
  3x between sources and voltage classes (US$3-10/kW·km = US$3,000-10,000/MW·km in S6; US$746-3,318/MW·km for
  500-765 kV in S7): **a conflict to flag for OQ-001**, not to average.

## 4. What applies to GeoFREA, what is adapted, what is not applied

GeoFREA is a robustness (regret) framework: cost parameters are drawn from sourced ranges with an evidence tier
(U-05, U-07), and the method already treats distance as a monetized cost driver, not an exclusion (METHODOLOGY section
on territory, M-F2b-02, M-F6-01). That is the same stance as S1 and S2.

| Idea in the research | Verdict for GeoFREA | Reason |
|---|---|---|
| Do not truncate the distance used economically (`d_economic = d_real`) | **Applies** | Removes a bias that the current cap introduces into LCOE; agrees with S1/S2; no new data needed. |
| Keep `distance_cap_km` only as a storage/QC threshold with the `distance_capped` flag | **Applies, with a wording change to M-F2a-03** | M-F2a-03 currently says capped pixels carry the cap value. The raster should carry the raw distance; the cap becomes the threshold of the flag. |
| Treat 100 km as a viability limit or exclusion layer | **Does not apply** | No source supports a universal limit; an exclusion layer (an "E7") would be a scope change and would need its own evidence. |
| Linear `P x d x c` as a first-order cost | **Keep, declare limitation** | M-F6-01 already samples `grid_cost_usd_per_mw_km` over a range; the linearity at long distance is recorded as L-019. |
| Piecewise-linear connection cost | **Adapt: as a structural robustness variant, only with sourced breakpoints** | Breakpoints/marginal costs must come from data (Tier 1-2), not be chosen. GeoFREA's regret framework fits a structural variant (linear vs piecewise) better than a single "calibrated" shape. Deferred: OQ-041. |
| Losses `eta(d)` in delivered energy | **Defer** | Changes M-F5-05 (energy at the plant) and needs a sourced loss-per-distance relation; OQ-041. |
| Dependence on voltage, technology, capacity, POI, upgrades, route (least-cost path) | **Not applied now** | Needs per-country data that is not available for BRA/PRT/IND (only the Brazilian EPE bases are identified, S8) and extra parameters without Tier 1-2 sources would break U-07. Straight-line geodesic distance (M-F2a-02) stays; recorded as a limitation. |
| The 10 km interconnectability filter | **Does not apply** | A pre-selection hypothesis of a global model, not a siting rule. |
| Brazilian EPE parameters for calibration | **Applies later (Stage R)** | Natural Tier 1 source for BRA grid costs under OQ-001; equivalent sources for PRT and IND still to be identified. |

A property of GeoFREA's data matters for all of the above: the `grid` layer is OpenStreetMap power infrastructure
(`infrastructure/grid/<ISO3>_grid_osm.geojson`; BRA 20,633, PRT 7,767, IND 29,996 features, lines and points).
Distance is to the **nearest mapped feature of any voltage**, which can be a low-voltage line unable to absorb a
utility-scale plant. Declared as L-018.

## 5. What is proposed, for authorization (OQ-040)

1. **METHODOLOGY (minor version bump, needs authorization).**
   - M-F2a-03: distance rasters store the **uncapped geodesic distance**; `distance_cap_km` (a QC threshold, provisional
     100 km, no source) only sets a `distance_capped` flag raster (`distance > cap`); no value is truncated.
   - M-F3-03: `dist_grid_km` and `dist_road_km` are the eligible-area-weighted means of the **raw** distance, and the
     `distance_capped` share is the eligible-area share beyond the QC threshold (a quality indicator, not a cost input).
   - M-F6-01: formula unchanged; a note that it uses the raw distance and that the linear form is a first-order
     approximation (L-019).
2. **Code (G-3, cap part).** Raw distance rasters plus a flag raster; the threshold as a configuration parameter; tests;
   and a QC measurement of the share of in-country pixels beyond 50, 100 and 200 km to the grid and roads for BRA, IND
   and PRT, which shows whether the question matters in practice and feeds OQ-041.
3. **Records.** This document, OQ-040 (this change) and OQ-041 (extension of the connection-cost model: piecewise
   structural variant, losses, voltage/technology/route), the evidence leads in OQ-001, and L-018/L-019.
4. **Not proposed now.** No piecewise function, no loss model, no voltage/technology/route model, no exclusion by
   distance, and no new cost parameter without a sourced range.

Implemented: raw distances and flag rasters (`docs/phases/F2a_grid_alignment.md` D-F2a-004); METHODOLOGY bumped to 2.0.0 (MAJOR, because a result definition changes; the proposal text above said "minor", which did not follow the change protocol in METHODOLOGY section 0).

## 6. Leads for OQ-001 (grid, substation and road cost parameters) — Stage R input, not values

- Connection cost per km: US$3,000-10,000/MW·km (S6, unverified, industry) against US$746-3,318/MW·km for 500-765 kV
  lines (S7, unverified): a ~3x conflict by voltage class and source; keep the range wide and tiered.
- Interconnection per kW: US$100-300/kW (S6, unverified) is relevant for `substation_cost_usd_per_mw`
  (US$100-300/kW = US$100,000-300,000/MW).
- Brazil: EPE transmission databases and reference prices by voltage (S8) as the Tier 1 anchor.
- PRT and IND: equivalent official sources to be searched (not identified yet).
