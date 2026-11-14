# Inventory of numeric parameters in `config/` and what should become a range

Date: 2026-10-08. Status: proposal for Douglas's verdict. Nothing here changes a file in `config/`.
Asked by Douglas on 2026-10-08: since the framework has many parameters, review all of those in the configuration files and
use ranges instead of single values wherever that is possible.

## 1. What the configuration files hold today

| File | Numeric content | Ranges today |
|---|---|---|
| `config/experiments.yaml`, `land_availability` | Land-availability parameters, 2 technologies (slope, density, riparian setback, discharge, minimum area, plus two categorical sets) | Yes: nominal plus low-high for slope (wind and solar), density, setback, discharge; minimum area has none; sources and status declared |
| `config/experiments.yaml`, `uncertain_parameters` | Names of 10 cost and performance parameters that F6 must sample (U-03): `capex_usd_per_kw`, `opex_fixed_frac`, `discount_rate`, `lifetime_years`, `degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`, `gamma` (solar), `eta_loss` (wind) | Names only; the schema (U-05) requires a `range` for each, **none exists yet** |
| `config/parameters.json` | 88 parameters (64 per country and technology: CAPEX, fixed O&M, variable O&M, lifetime, discount rate, discount increment, slope threshold; 24 legacy `criteria`) | **0 of 88 have a range** (U-05 `range` is null everywhere) |
| `config/technologies.yaml` | Hub heights per country, IEC class rule, resource layer names | Hub heights and IEC rule are `null` (OQ-019, OQ-005) |
| `config/experiments.yaml`, `gcm_ensemble` | `wind_factor_valid_range` [0.5, 1.5] (unsourced, OQ-043), neighbourhood size 3, GCM list | Plausibility bound, already a range with a sensitivity (D-F4-018) |
| `config/settings.yaml` | `distance_cap_km` 100, grid resolutions | Definitions or display flags, not scientific uncertainties |
| `config/audit.yaml` | Audit thresholds (quality checks) | Quality gates, not scientific uncertainties |

## 2. Classification

**A. Already a range:** land-availability parameters above (sources still pending for density, discharge and the 15 degree end of solar slope).

**B. Scientific and uncertain, no range yet: these are the ones to convert.**
- Economics (F6): CAPEX, fixed O&M, variable O&M, lifetime, discount rate (and its country increment), degradation rate, grid cost per MW-km, substation cost, road cost. Single values exist per country for the first five; the last four have no value anywhere (F6 not started).
- Performance (F5): solar temperature coefficient `gamma`, wind loss factor `eta_loss`, wind hub height, power-curve class (IEC), solar land-use factor (LUF) and wind power density (PD), solar `delta_rsds`-based capacity model constants.
- Land availability, remaining: minimum eligible area (no range), `iucn` and land-cover levels (named, weights not defined).

**C. Definitions, not uncertainties (stay single values, declared as such):** grid resolution, cell lattice, `distance_cap_km` (a flag threshold), audit thresholds, GCM list, time windows, seeds.

**D. Legacy `criteria.*` in `parameters.json` (24 entries) that duplicate or contradict `land_availability`:** `slope_threshold_deg` solar 5 and wind 25, country slope thresholds 10 and 12, `river_safety_buffer_km` 0.5, `pop_density_threshold` 200. They feed only the legacy `suitability_criteria` phase (outside the default run). After the land-availability block became authoritative for F3 there are two sources of truth; proposal: mark those entries as legacy-only in the file and stop reading them anywhere else.

## 3. The consequence for how the ranges are used

The number of ranged parameters decides the method:
- **Land availability** has four continuous ranged parameters. Three levels each gives 81 combinations, cheap on the F3 engine (pixel operations), so the full grid is fine and deterministic.
- **Everything in B together** is some 15 to 20 more parameters per technology. A grid of three levels each would be 3^16, about 43 million combinations: impossible. Sampling (Latin hypercube, seed recorded) is the only way to cover so many dimensions with a few hundred runs; this is why U-03/U-04 already prescribe it for the cost parameters.
- **Joint use in F7** (36 climate members, cost draws, land scenarios): 81 land scenarios times 500 cost draws times 36 members is 1.5 million states per cell, too many for 286,000 cells. So land scenarios must enter the ensemble as one more sampled factor (each draw picks a land scenario among the 81, equal weights), while the land results are still reported as a table over all 81 for the central cost set. Sampling therefore stays for the many parameters; what changes is that land availability is not "drawn at random" in its own table.

## 4. Proposed order

1. Douglas confirms the classification (sections 2 B and C) and the decision on section 2 D.
2. Land availability: the grid of 81 combinations and one-at-a-time sweeps (METHODOLOGY 7.0.0), as agreed.
3. Ranges for B: each needs a literature source (Stage R), kept as `unsourced` until then, as for density and discharge. Candidate sources are in `docs/_audit/` (CAPEX and O&M: IRENA, NREL ATB; discount rate: country WACC studies; gamma: module datasheets and SAM; losses: wind-farm availability and wake studies).
4. F5/F6 read the ranges through the same schema (nominal, low, high, unit, source, status), so a platform user can edit any of them.
