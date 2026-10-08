# LIMITATIONS.md: GeoFREA

Declared limitations of the method and every Tier 3 value. Each entry is written so it can be carried into the thesis limitations section.

Entry format: ID, statement, affected items, why it is accepted, where it is declared in the thesis (filled when written).

## Method limitations

| ID | Statement | Affects | Why accepted | Thesis section |
|---|---|---|---|---|
| L-001 | Solar potential assumes free-standing plants with c-Si modules at fixed optimum tilt (Global Solar Atlas PVOUT configuration); single-axis trackers are not modeled. | M-F5-02, T-R1, T-R2 | Only globally consistent PVOUT product available; trackers would require a separate irradiance model. | |
| L-002 | Climate change enters through annual-mean delta-change factors; seasonal redistribution of resource is not represented. | M-F4-03, M-F5-02, M-F5-03 | Atlas baselines are annual long-term averages; monthly baseline redistribution would require monthly atlas products and profiles. | |
| L-003 | Wind change factors from near-surface (10 m) `sfcWind` are applied at hub height, and Weibull shape `k` is held constant under climate change. | M-F5-03 | CMIP6 does not provide hub-height wind for the required ensemble; IPCC AR6 assigns low confidence to regional wind-speed trends, which is discussed alongside results. | |
| L-004 | Member CF ratios are evaluated at cell-mean Weibull parameters rather than per pixel. | M-F5-03 | Change factors are smooth at GCM resolution; the error is second order relative to cell-level resource heterogeneity. | |
| L-005 | Each GCM contributes a single realization; internal variability is not sampled. | M-F4-01 | Ensemble size is bounded by variable availability and computation; 30-year climatologies reduce internal-variability noise. | |
| L-006 | Climate of each window is held constant over the asset lifetime. | M-F6-01 | Annual trajectories add noise without changing results materially under discounting; two windows bracket the time dimension. | |
| L-007 | The 2071-2100 window extends beyond the lifetime of assets commissioned around 2030 and is interpreted as repowering or second-generation assets. | S-05, T-R6 | Needed to test H1 where SSPs diverge. | |
| L-008 | The reference climatology (1995-2014) does not coincide with the atlas reference periods (Global Solar Atlas: region-dependent start to 2024; Global Wind Atlas: see OQ-006). | M-F4-03 | Delta-change requires a common CMIP6 historical reference; 1995-2014 is the IPCC AR6 recent-past reference. | |
| L-009 | The transmission grid layer represents line location, not available connection capacity or voltage adequacy. | M-F2b-02, M-F6-01 | No consistent grid-capacity data exist for the three countries. | |
| L-010 | Exclusions are binary; social acceptance and other non-monetizable siting factors enter only through exclusions. | M-F2b-01 | Keeps every output in physical units; land-availability variants bound the effect (U-06). | |
| L-011 | Grid connection is costed per cell from eligible-area-weighted mean distance; shared connection infrastructure between neighboring cells is not modeled. | M-F6-01 | Cell decision unit (S-06); zones may be shown in F8 for presentation only. | |
| L-012 | Uncertain parameters are sampled independently; correlations (for example between CAPEX and discount rate) are not represented (verdict V5: independent sampling; no correlation without a sourced coefficient). | U-03, V5 | No defensible joint distributions for the three countries. | |
| L-013 | Results depend on the 0.05 degree aggregation (modifiable areal unit problem). | S-06, V-07 | Tested explicitly at 0.1 degree. | |
| L-014 | Extreme-wind context comes from ERA5 historical reanalysis and does not vary by SSP. | M-F1-05, M-F4-05, T-R10 | CMIP6 lacks consistent gust variables; low confidence in wind extremes trends. | |
| L-015 | Hazards without Tier 1-2 loss functions are reported as context and do not affect robustness metrics. | M-F4-05, H4 | Avoids driving results with unsourced values; exposure is still reported (T-R10). | |
| L-016 | External validation against existing plants measures plausibility, not accuracy, because plant locations reflect past auctions, policy, and grid access. | M-F7b-01 to M-F7b-04 | No ground truth for optimal siting exists. | |
| L-017 | The gust indicator (`fg10`, annual maximum, 1995-2014) is raw ERA5 reanalysis with no bias adjustment against station or other observed data. It is internally consistent for comparison across cells and years but is not an observed local gust value. | M-F1-05, M-F4-05, T-R10 | No bias-adjusted gust product exists at the required resolution/coverage across BRA, PRT, IND; CRAEI (which does bias-adjust its ISIMIP3b hazard channel, D-F4-001) has no gust product at all to adapt (D12). | |
| L-018 | The `grid` layer is OpenStreetMap power infrastructure of any voltage (lines and points), so distance to the grid is the distance to the nearest mapped feature, which can be a low-voltage line unable to absorb a utility-scale plant; the true connection point and the reinforcements it needs are not modeled. | M-F1-02, M-F2a-03, M-F3-03, M-F6-01 | No country-wide, voltage-resolved transmission dataset is available for BRA, PRT and IND; the effect is carried by the sampled grid-cost range (OQ-001). **Coverage measured 2026-10-06** (existing plants against the OSM layer, `docs/_audit/2026-10_plants_vs_osm_grid.md`): PRT complete (all plants within 14 km); BRA consistent (99.9% of capacity within 50 km; far distances are mostly real absence of grid); **IND incomplete** (24% of wind, 11% of solar, 41% of hydro units more than 50 km from a mapped feature; repeated 2026-10-07 with GEM, 5,727 IND units, same verdict as the 2020 GPPD list), so IND distances to the grid are overstated. | |
| L-019 | Connection CAPEX is linear in straight-line geodesic distance (`P x d x c`). Real costs also depend on voltage, line technology, capacity, terminal and reinforcement costs, losses and the actual route, and the cost-distance relation changes at long distances (HVDC vs HVAC), so the linear form is a first-order approximation, least reliable for remote cells. | M-F6-01, M-F2a-02, OQ-040, OQ-041 | Evidence supports distance entering cost continuously but gives no per-country voltage/technology/route data; the sampled `grid_cost_usd_per_mw_km` range (OQ-001) and the possible structural variant (OQ-041) carry the uncertainty. See `docs/_audit/2026-10_distance_connection_cost_evidence.md`. | |
| L-020 | The IND central candidate set rests on a Tier 3 population-density value (200 persons/km2, OQ-047). With the unsourced ranges (density, discharge, solar slope upper end) added, the candidate-set Jaccard of IND falls to about 0.67 (`docs/_audit/2026-10_systematic_review.md`, Appendix A.5). | M-F3-04, U-06, V1 | The sourced ranges alone leave the set stable (about 0.90); the unsourced ranges join the scenarios when OQ-047 is sourced. | |

## Scope boundaries

| ID | Statement |
|---|---|
| L-101 | Biomass is outside the thesis core; the technology registry allows later addition. |
| L-102 | GHG abatement is outside the thesis. |
| L-103 | Seismic hazard is not modeled. |
| L-104 | Sea-level rise and wildfire are not modeled (data limitations inherited from GEAR). |
| L-105 | Transport decarbonisation is permanently excluded. |

## Tier 3 values

| ID | Parameter path | Value | Rationale | Thesis section |
|---|---|---|---|---|
| L-203 | countries.BRA.technologies.wind.opex_fixed_frac | 0.0077 fraction/year | proxy: fixed O&M of another technology (solar O&M used for wind); production runs fail while `proxy` is true (U-05); pending OQ-016 | |
