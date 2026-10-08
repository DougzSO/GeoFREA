# GeoFREA: project summary

Orientation document. It holds no decisions of its own: the method is defined only in `docs/METHODOLOGY.md` (cited by item ID below), open items live only in `docs/OPEN_QUESTIONS.md`, limitations only in `docs/LIMITATIONS.md`, and status only in `docs/PROGRESS.json`. If this file disagrees with any of them, they win and this file is corrected.

Summarizes METHODOLOGY version: 7.0.0

## What GeoFREA is

A spatially explicit, open-data framework that estimates technical potential and site-level LCOE of utility-scale solar PV and onshore wind on a 0.05 degree cell grid in Brazil, Portugal and India (S-01, S-02, S-06), and ranks cells by how well their economic ranking holds across climate futures and techno-economic uncertainty (RO4).

Climate change enters as change in the mean resource (irradiance, temperature, wind) from a 6-GCM CMIP6 ensemble under SSP1-2.6, SSP3-7.0 and SSP5-8.5, for 2041-2070 (core) and 2071-2100 (sensitivity), against 1995-2014 (S-03 to S-05, M-F4-01 to M-F4-03). Climate hazards enter LCOE only where a Tier 1-2 loss function exists (M-F4-05, OQ-007); otherwise they are context indicators (L-015).

## Pipeline

| Phase | Module | Role |
|---|---|---|
| F1, F1b | `data_acquisition`, `data_quality_audit` | Raw layers with provenance; audit |
| F2a, F2b | `grid_alignment`, `siting_layers` | 0.01 degree grid; exclusion, cost-driver and resource layers in physical units |
| F3 | `land_eligibility` | Eligible share per pixel, cell aggregation, candidate table |
| F4 | `climate_forcing` | Change factors per cell and climate member; hazard context |
| F5 | `technical_potential` | Capacity, capacity factor, energy per cell and member |
| F6 | `lcoe_modeling` | LCOE kernel; Latin hypercube parameter samples (design matrix) |
| F7 | `robustness_analysis` | Regret, satisficing, axis decomposition, PRIM, H1-H5 tests |
| F7b | `external_validation` | Plausibility against existing plants (GEM) |
| F8, E1 | `results_synthesis`, `explorer` | Thesis outputs; precomputed static explorer |

## Uncertainty, in one paragraph

Climate is a discrete, unweighted set of members (U-01, U-02). Techno-economic parameters are sampled by Latin hypercube in F6 and consumed by F7 (M-F6-02, U-03). Land-availability parameters are declared as central values with ranges where a source gives one (M-F2b-06); land is not a factor of the futures of F7, and its ranges are reported through three named scenarios (U-06). Every main result is reported as a central value with its range, stating which axis the range comes from: land scenarios, parameter samples or climate members (U-08).

The results come in three blocks: the potential (eligible area, GW, TWh, LCOE and supply curves, with the land range); the effect of climate on that potential, computed at fixed central land with the land range beside it; and the robustness of the siting ranking across climate members and parameter samples (MR, satisficing, H1-H5).

## Where to look

- Current status per phase and country: `docs/PROGRESS.json`
- Decisions per phase: `docs/phases/<phase>.md`
- Thesis outputs and their phases: METHODOLOGY Section 10

## Outside the current method

A web platform where users adjust parameters within sourced ranges and see maps and numbers update, built on precomputed results for the three countries; and extension to further countries through configuration only (A-04, A-05).
