# Design note — land-availability parameters as ranges, sampled instead of strict/lenient variants

Date: 2026-10-07. Status: proposal for Douglas's verdict (OQ-049). Nothing here is built except what is marked "built".
Requested by Douglas on 2026-10-07: use ranges for as many parameters as possible, by default taken from referenced literature
(thesis and articles), and let a user of the future online platform change the ranges and try combinations.

## 1. Where things stand

- Built: `land_availability` in `config/experiments.yaml` declares, per technology, a central value and an optional `low`-`high`
  range with its source and status (`land_eligibility/parameters.py`); the engine is a pure function of one `ParameterSet`
  (`eligibility.py:eligible_fraction`). Only the central set is run (F3 phase). Riparian shares are already computed for the lowest,
  central and highest setback.
- Central values and ranges after Douglas's decisions of 2026-10-07: wind slope 16.7 deg (10.2-30); solar slope 10 deg (no range yet);
  population density 200 persons/km2 (150-300, set by Douglas as an example, not a citation); riparian setback 0.5 km (0.25-1.0);
  IUCN: every designation (levels `all_designated`, `ia_ib_ii`, `ia_ib`, `all_assigned`); excluded land-cover classes as named levels;
  minimum eligible area 0.1 km2 (no range yet).
- Not built: sampling, the discharge parameter below, and every consumer of more than one parameter set.

## 2. Proposal

**2.1 One new continuous parameter: minimum river discharge for E3** (`riparian_min_discharge_m3s`, `DIS_AV_CMS` in HydroRIVERS).
Central 0 (every stream, as now); range 0 to 10 m3/s (no source; the PRT measurements, 24.5% of the land excluded at 0, 9.2% at 1,
3.8% at 5, 2.5% at 10 and 1.1% at 50 m3/s, show what the range spans). Engine change: riparian shares for a grid of discharge
thresholds (for example 0, 1, 5, 10) times the setbacks, each from its own distance transform, interpolated for a draw (the share is
monotone in both). Cost: one extra distance pass per discharge threshold (BRA about 15 min each).

**2.2 Sampling.** A draw is one `ParameterSet` per technology: continuous parameters from their range (Latin hypercube or Sobol, the
sampler already configured for U-04), categorical parameters from their named levels with equal weights unless the config gives
weights. A parameter with no range stays at its central value and is listed as fixed in the output metadata. Number of draws K to be
chosen with the convergence rule of U-04 (start 500 for the cost factors; for land availability fewer are likely enough because the
eligibility is cheap and smooth, to be tested).

**2.3 Outputs of F3.** Keep the nominal tables as now (`candidates_<tech>.parquet`). Add, per technology, a matrix
`eligible_area_km2` of cell by draw (float32; BRA 286,000 cells x 50 draws is about 57 MB), the draw table (parameter values and a
hash), and the union of candidate cells over the draws (a cell is a candidate in a draw if its area reaches that draw's minimum).
Resource and distance means stay weighted by the nominal eligible area (an approximation to be checked by recomputing them for a few
draws), so the per-draw cost is only the pixel operations and the 5 x 5 sums.

**2.4 Downstream.** F5 computes capacity per cell for each draw (`eligible_area x LUF x PD`); F7 treats the land-availability draw as one
more uncertain factor of the state of the world, next to climate member and cost parameters, so robustness (regret, satisficing)
and the sensitivity table T-R2 come from the same ensemble; T-R2 becomes a ranking of how much each land parameter moves the result
(not a strict/lenient pair). The explorer (E1) offers the ranges as sliders over precomputed draws; a user-supplied
`land_availability` block with the same schema is validated and fails loudly if a value is outside its declared bounds.

**2.5 What changes in METHODOLOGY (MAJOR, 6.0.0).** U-06 (variants replaced by ranges), U-03 and U-04 (land-availability parameters
join the uncertain parameters and the sampler), M-F3-02 (a set per draw), M-F5-01 (capacity per draw), M-F7 (state of the world
includes the land draw), T-R2 (from draws). The 5.0.0 text of M-F2b-06 already announces the replacement.

## 3. Decisions needed from Douglas

1. Approve the design (draws of parameter sets, matrix per cell and draw, land availability as an uncertain factor in F7).
2. Draws: sampled jointly with the other uncertain factors (one ensemble, simpler regret) or as a separate outer loop (clearer
   sensitivity to land alone). Recommendation: jointly, plus a one-factor-at-a-time table for T-R2.
3. Whether resource and distance means may stay weighted by the nominal eligible area (recommended) or must be recomputed per draw.
4. The range of the discharge parameter and the unsourced ends (solar slope, minimum area, density 150-300): literature search in
   Stage R; until then they are flagged `range_set_by_douglas_unsourced` or `range_pending`, never presented as cited.

## 4. Order of work if approved

(1) discharge parameter and its shares; (2) sampler over `land_availability` and the per-draw eligibility matrix; (3) tests (monotone
areas in every parameter, draw reproducibility from a seed, V-03 per draw); (4) METHODOLOGY 6.0.0; (5) F5 onward consume the matrix.
