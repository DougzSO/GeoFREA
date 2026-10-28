# Wind capacity factor aggregated from the 0.01 degree pixels (COMMAND 74)

Date: 2026-10-28. Branch `feat/wind-cf-pixel`. METHODOLOGY 15.3.0 (M-F5-03, M-F3-05, display resolution), D-F5-038, L-004. Verdict on R71-01 of `docs/_audit/2026-10_general_audit_71.md` (section G.1).

## 1. What changed

Until now F5 applied the wind model (hub-height interpolation, density correction, Weibull integral over the power curve, retention) to the eligible-area-weighted means of `A`, `k` and air density of each 0.05 degree cell. The power curve is not linear, so this is not the mean of the pixel capacity factors. F5 now evaluates the same model on every eligible 0.01 degree pixel (5 x 5 per cell) and aggregates to the cell with the eligible area of the pixel as weight:

    CF_cell,m = sum_p w_p CF_p,m / sum_p w_p,     w_p = eligible fraction of the pixel in the scenario x geodesic pixel area

- Same curve, same density correction (folded into the Weibull scale), same retention `eta_loss`. `dT` and `delta_wind` are those of the cell (F4 has no finer resolution).
- `sum_p w_p` is the F3 `eligible_area_km2` of the cell; F5 refuses to run if they differ by more than 1e-4 (relative). On the 400 cells per scenario drawn by the independent check the gap is 6e-16 (BRA).
- The class flag and the density check keep reading the cell means, as before.
- Solar is unchanged (linear in PVOUT): its tables are identical in content to the previous round in PRT, IND and BRA (4 artifacts each).
- Blocks of at most 1 000 000 pixels (`PIXELS_PER_BLOCK`); CSR layout, one offset per candidate cell.
- Cost of the change in F3: each land scenario needs its own pixel eligible fraction, so F3 now also writes `eligible_fraction_<tech>__restrictive.tif` and `__permissive.tif` (27 `eligibility/` entries per country in the manifest instead of 23). F4 runs again in each country with the same content (its code fingerprint contains `land_eligibility.cells`).

## 2. Step 1: bias measured before the change (whole country, reference member m0, central scenario)

Signed difference `(CF_cell_mean - CF_pixel) / CF_pixel` over every candidate cell. Negative: the cell value was below the pixel mean.

| Country | Cells | Median | P5 | P95 | Share beyond +-1% | Largest | Cells with negative bias | National energy, cell mean | National energy, pixel | Effect on the total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PRT | 3 500 | -0.003% | -0.24% | +0.26% | 0.46% | 2.0% (+) | 55.7% | 48.9997 TWh | 48.9995 TWh | +0.0006% (-0.0003 TWh) |
| IND | 61 464 | -0.013% | -1.25% | +0.005% | 5.8% | 53.1% (-) | 87.5% | 299.495 TWh | 299.567 TWh | -0.024% (+0.071 TWh) |
| BRA | 181 306 | -0.165% | -1.16% | +0.030% | 6.8% | 28.9% (-) | 90.6% | 2 297.214 TWh | 2 300.271 TWh | -0.133% (+3.057 TWh) |

(The effect on the total is `E_cell / E_pixel - 1`, computed from the same capacity, so it is the bias of the national energy. In PRT the sign of the bias is symmetric; in IND and BRA the cell mean underestimates.) Raw numbers: `bias_<ISO>.json` of the working directory; thesis table `tab:g1_pixel_bias` in `docs/thesis/methods/group1_technical_potential.tex`.

Reading: the national total barely moves (at most 0.14%), but the capacity factor of 6% to 7% of the cells of India and Brazil was more than 1% too low, in a few by 29% to 53%. The cost of energy of a cell is inversely proportional to its energy, so those cells would have been ranked as costlier than they are in F6.

## 3. Step 5: new round against the current one (reference member m0)

Central wind potential. Capacity does not change (it does not depend on the capacity factor); only energy does.

| Country | Scenario | Capacity (GW) | Energy before (TWh/yr) | Energy after (TWh/yr) | Change |
|---|---|---:|---:|---:|---:|
| PRT | restrictive | 2.91 | 6.927 | 6.928 | +0.0028% |
| PRT | **central** | **21.05** | 48.9997 | **48.9995** | -0.0006% |
| PRT | permissive | 75.25 | 172.518 | 172.507 | -0.0067% |
| IND | restrictive | 58.76 | 94.63 | 94.65 | +0.0167% |
| IND | **central** | **189.81** | 299.495 | **299.567** | +0.0239% |
| IND | permissive | 630.41 | 981.31 | 981.65 | +0.0343% |
| BRA | restrictive | 238.53 | 345.05 | 345.41 | +0.1031% |
| BRA | **central** | **1 643.45** | 2 297.214 | **2 300.271** | +0.1331% |
| BRA | permissive | 5 610.03 | 7 727.82 | 7 739.63 | +0.1528% |

Change of the position of the cells in the ranking by capacity factor (central scenario, m0, candidate cells; the set of cells and their capacity do not change):

| Country | Cells | Spearman, CF | Share of the top 10% by CF that leaves it | Spearman, energy per cell | Top 10% by energy that leaves it | Cells whose CF moves > 1% | Median change of CF | P5 to P95 | Smallest to largest |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| PRT | 3 500 | 0.99998 | 0.86% | 0.9999984 | 0.00% | 0.46% | +0.003% | -0.26% to +0.24% | -2.0% to +1.1% |
| IND | 61 464 | 0.99998 | 0.10% | 0.9999985 | 0.05% | 5.9% | +0.013% | -0.005% to +1.26% | -4.8% to +113% |
| BRA | 181 306 | 0.99998 | 0.14% | 0.9999943 | 0.10% | 6.9% | +0.165% | -0.03% to +1.18% | -5.6% to +41% |

Climate effect on the wind energy (change against m0, like for like, central scenario, every member): the range moves by at most 0.018 percentage point in PRT, 0.009 in IND and 0.20 in BRA (BRA: -3.68% to +48.17% before, -3.67% to +47.98% after).

Other results:

- 16 of 16 checks pass in PRT, IND and BRA: the 15 checks of 49b plus `pixel_weights_equal_the_f3_eligible_area`. `cf_net_over_gross` is now computed by an independent route that reads the rasters again and weights the pixels outside the pipeline (400 cells per scenario, every member): largest deviation 8.9e-16 in BRA.
- Wind class flag: content identical in the three countries (cell means, reference climate). Solar tables: identical in content. Artifacts of F1 to F4: identical in content.
- Rank correlation is high because the set of cells is the same and the bias is mostly small; the ranking changes where it matters for the cost: the cells that were more than 1% too low (6% to 7% of the cells of IND and BRA) now sit higher.

## 4. Step 6: cost of the wind F5 per country

These are the times of the whole F5 phase (wind and solar); solar did not change, so the difference is the wind pixel evaluation.

| Country | Wall before | Wall after | CPU after | `peak_rss_mb` before | `peak_rss_mb` after |
|---|---:|---:|---:|---:|---:|
| PRT | 13.7 s | 209.7 s | 187.8 s | 327 | 411 |
| IND | 234.5 s | 2 444.8 s (40.7 min) | 2 383.5 s | 1 230 | 985 |
| BRA | 621.8 s | 45 516 s (wall clock, see below) | 10 442.5 s (2.9 h) | 2 269 | 2 208 |

- BRA: the wall time of the manifest includes a night in which the computer was suspended (the log has no entry between 21:41 and the resumption). The reliable figure is the CPU time, 2.9 h; the central scenario alone took 62 min of wall time before the suspension.
- The cost is about 33 microseconds per pixel in the Weibull integral, times 25 pixels per cell, times the members and scenarios. It was not optimised on purpose: the numerical method was not changed. Memory is bounded by the block size and stays at the level of the previous round.
- F5 is run once per round and the tables are cached by code fingerprint, so the cost is paid when the code or the inputs change.

## 5. Deviations from the command

1. F3 writes two more rasters per technology (the scenario pixel fractions) and its manifest has 27 `eligibility/` keys instead of 23 (D-F5-038): F5 cannot rebuild the fraction of a scenario from the central one, and weighting a scenario with the central fraction would be wrong. F3 and F4 ran again in the three countries; the content of every F3 and F4 artifact except those new rasters is identical.
2. The wind display layer shows an identity (1e-9) only for the wind model; solar keeps 1e-6 (float32 rasters).
3. The command asked for "the 15 checks of 49b"; there are 16 because the pixel route needs a check of the weights against the F3 eligible area.
4. `figures: all` is needed to rebuild the display layers (the runs of the round used `summary`): see section 6.

## 6. Display layer

The 0.01 degree layers are built by `potential_maps` only with `figures: all` and only for the countries where a cell would be drawn with more than 4 pixels (PRT; IND and BRA draw the cells). The round used `summary`, which left the PRT layer of the previous code in place, so `potential_maps` was run once more in PRT with `figures: all` (the setting was restored afterwards).

| Check, wind, PRT | Tolerance | Largest relative difference | Before the change |
|---|---:|---:|---:|
| capacity-factor (display layer aggregated to the cell against the F5 table) | 1e-9 | 8.5e-16 | 1.96% (tolerance 1%) |
| eligible-area | 1e-6 | 0 | 0 |
| capacity-density | 1e-6 | 5.4e-16 | 5.4e-16 |

Solar, PRT: capacity-factor 4.8e-16 (tolerance 1e-6). The aggregation of the wind display layer is an identity: both sides evaluate the same model on the same pixels with the same weights; the 1% tolerance of the earlier code is gone for wind.

Incident: two runs of this `potential_maps` were started at the same time by mistake; one failed with access denied on `potential_density_solar.tif` (the other had it open) and the other ran to the end, rc 0, 27 artifacts. No result depends on the failed one.
