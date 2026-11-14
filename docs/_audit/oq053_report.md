# OQ-053 closed: validity limits for the Weibull layers (COMMAND 48, 2026-10-16)

Branch `stage-r/oq053`, METHODOLOGY 15.0.1, not committed.

## 1. Rule

- `config/audit.yaml` `derived_ranges.weibull_a.validity_range = [0, 25]` (m/s) and `weibull_k.validity_range = [0, 10]`, meaning the intervals (0, 25] and (0, 10]: the lower bound is excluded, the upper included. Tier 3, no source; the same at 100, 150 and 200 m.
- `input_ranges.validate_candidates` raises `InputRangeError` for a candidate cell outside or not finite: the message names the layer, `n of N` cells, the extremes, the first `cell_id` and the first five (lat, lon). F5 stops before computing anything. The limits test validity, not plausibility.
- The plausibility flag of 15.0.0 (A in [1, 15], k in [1, 4], column `weibull_outside_flag_range`, counts in the scenario summary) is removed. The Weibull layers have a range, so F5 emits no warning about them (the six OQ-053 warnings of the first real run are gone).
- New `technical_potential/weibull_report.py`: `weibull_distribution_report` gives, per variable and height, the number of cells, P1, P50, P99, the extremes and, for k, the cells below 1 and above 4. F5 writes it as `weibull_distribution_<tech>.csv` in its output and logs one information line; the file is listed in the technology summary (`TechPotential.weibull_distribution`) but is not a registered artifact. The class-flag table loses the Weibull column (schema 1.2).

## 2. Check on the real rasters (step 6, read only)

Script `D:/tmp_diag/raster_limits.py` read the 18 siting-layer rasters (`GEOFREA_DATA_DIR/outputs/<ISO>/siting_layers/artifacts/weibull_{a,k}_{100,150,200}m.tif`, 0.01 degree), block by block, ignoring nodata, and counted the pixels with value <= 0 or above the cap. Nothing was written under `database/raw` or anywhere else.

| Country | Layer | Valid pixels | Minimum | Maximum | <= 0 | Above cap |
|---|---|---|---|---|---|---|
| PRT | a_100m | 93,149 | 2.715 | 11.031 | 0 | 0 |
| PRT | k_100m | 93,149 | 1.006 | 2.775 | 0 | 0 |
| PRT | a_150m | 93,149 | 2.925 | 11.578 | 0 | 0 |
| PRT | k_150m | 93,149 | 0.978 | 2.695 | 0 | 0 |
| PRT | a_200m | 93,149 | 3.072 | 11.983 | 0 | 0 |
| PRT | k_200m | 93,149 | 0.958 | 2.634 | 0 | 0 |
| IND | a_100m | 2,607,874 | 0.486 | 20.416 | 0 | 0 |
| IND | k_100m | 2,607,874 | 0.559 | 3.783 | 0 | 0 |
| IND | a_150m | 2,607,874 | 0.536 | 19.976 | 0 | 0 |
| IND | k_150m | 2,607,874 | 0.561 | 3.594 | 0 | 0 |
| IND | a_200m | 2,607,874 | 0.565 | 19.637 | 0 | 0 |
| IND | k_200m | 2,607,874 | 0.552 | 3.447 | 0 | 0 |
| BRA | a_100m | 7,099,634 | 0.836 | 15.453 | 0 | 0 |
| BRA | k_100m | 7,099,634 | 0.806 | 5.400 | 0 | 0 |
| BRA | a_150m | 7,099,634 | 1.110 | 16.074 | 0 | 0 |
| BRA | k_150m | 7,099,634 | 0.822 | 5.216 | 0 | 0 |
| BRA | a_200m | 7,099,634 | 1.308 | 16.489 | 0 | 0 |
| BRA | k_200m | 7,099,634 | 0.829 | 5.066 | 0 | 0 |

**Pixels outside the limits: 0** in the three countries and the three heights. The candidate tables of the first real run (wind, three scenarios; step-5 numbers of `docs/phases/F5/fix_round_46.md`) are inside too: the smallest A is 0.81 m/s, the largest 14.5 m/s, the smallest k 0.73 and the largest 4.97.

## 3. Distribution report on the real candidates (information)

Same function F5 now calls, applied read only to the central wind candidate tables of the first real run:

| Country | Var. | Height m | Cells | P1 | P50 | P99 | Min | Max | k < 1 | k > 4 |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT | A | 100 | 3,496 | 4.02 | 6.56 | 8.80 | 2.93 | 9.98 |  |  |
| PRT | A | 150 | 3,496 | 4.41 | 7.28 | 9.38 | 3.14 | 10.47 |  |  |
| PRT | A | 200 | 3,496 | 4.66 | 7.79 | 9.84 | 3.29 | 10.92 |  |  |
| PRT | k | 100 | 3,496 | 1.20 | 2.04 | 2.54 | 1.03 | 2.67 | 0 | 0 |
| PRT | k | 150 | 3,496 | 1.19 | 1.99 | 2.48 | 1.01 | 2.61 | 0 | 0 |
| PRT | k | 200 | 3,496 | 1.18 | 1.96 | 2.44 | 0.99 | 2.56 | 2 | 0 |
| IND | A | 100 | 62,718 | 2.05 | 5.34 | 7.60 | 0.88 | 11.44 |  |  |
| IND | A | 150 | 62,718 | 2.25 | 6.05 | 8.31 | 1.03 | 11.78 |  |  |
| IND | A | 200 | 62,718 | 2.39 | 6.60 | 8.88 | 1.15 | 12.11 |  |  |
| IND | k | 100 | 62,718 | 1.10 | 2.11 | 2.89 | 0.78 | 3.43 | 220 | 0 |
| IND | k | 150 | 62,718 | 1.11 | 2.08 | 2.82 | 0.78 | 3.26 | 211 | 0 |
| IND | k | 200 | 62,718 | 1.11 | 2.04 | 2.76 | 0.78 | 3.14 | 205 | 0 |
| BRA | A | 100 | 181,277 | 2.61 | 4.99 | 8.58 | 1.50 | 13.01 |  |  |
| BRA | A | 150 | 181,277 | 3.10 | 5.65 | 9.37 | 1.70 | 13.92 |  |  |
| BRA | A | 200 | 181,277 | 3.45 | 6.14 | 10.02 | 1.79 | 14.54 |  |  |
| BRA | k | 100 | 181,277 | 1.49 | 2.29 | 4.10 | 0.85 | 4.96 | 20 | 2604 |
| BRA | k | 150 | 181,277 | 1.46 | 2.22 | 3.86 | 0.87 | 4.65 | 21 | 1035 |
| BRA | k | 200 | 181,277 | 1.43 | 2.17 | 3.69 | 0.87 | 4.45 | 22 | 437 |

The tails the earlier flag counted are physical and are reported here and not as warnings: IND has 220 cells with k < 1 at 100 m, BRA has 2,604 with k > 4 (trade-wind regimes) and 20 with k < 1.

## 4. Documents

| Item | Change |
|---|---|
| METHODOLOGY 15.0.1 | PATCH row of the changelog (the rule, no result change because no cell is outside); V-04 and M-F5-06 text. |
| LIMITATIONS | L-043 (the flag) RETIRED, not deleted; L-211 rewritten as the Tier 3 entry of the limits. |
| OPEN_QUESTIONS | OQ-053 removed (`grep OQ-053 docs/OPEN_QUESTIONS.md` is empty). |
| F5 record | D-F5-026 closes OQ-053; history line. |
| PROGRESS.json | `methodology_version` 15.0.1; the F5 summary no longer says OQ-053 is open. |
| `references_stage_r.bib` | The two `note` fields asking for a check were removed from `bryantlempert2010` and `friedmanfisher1999`. Volume, number, pages and DOI agree with what the file already had: Bryant and Lempert, Technol. Forecast. Soc. Change 77(1), 34-49; Friedman and Fisher, Statistics and Computing 9(2), 123-143. This is a comparison with my own knowledge of the two papers; I did not open the journals' pages. |
| `.tex` against `parameters.json` and `config` | 98 comparisons of Groups 1 and 2, 0 divergences; the paragraph on data-validity bounds in `group1_technical_potential.tex` (A <= 0 or > 25, k <= 0 or > 10 stop the run; k < 1 and k > 4 reported as tails; Tier 3) agrees with `audit.yaml`. All 25 `\cite` keys exist in the `.bib`. The `.tex` file was already modified in the working tree before this round (the author's edit), and was kept. |
| Other | `scripts/f2b_sanity_report.py` and `siting_layers/sanity.py` texts no longer say that Weibull has no range; `test_siting_sanity` updated. |

## 5. Tests

New or rewritten in `tests/unit/test_technical_potential_pipeline.py`: k = 10.5 stops the phase with the count and the coordinates; k = 0, k < 0, A = 0, A = 25.5 and a non-finite A stop it; k = 4.5, k = 0.8, k = 10, A = 25 and A = 0.5 stop nothing and generate no warning; the distribution file exists with its columns, percentiles and k counts and logs no warning; the limits of `audit.yaml` at every height.

- **Suite:** 1393 passed, 4 warnings in 732 s (12 min 12 s), full suite on branch stage-r/oq053 (0 failures).

## 6. Diff

```
config/audit.yaml                                  |  20 ++--
 docs/LIMITATIONS.md                                |   4 +-
 docs/METHODOLOGY.md                                |   7 +-
 docs/OPEN_QUESTIONS.md                             |   1 -
 docs/PROGRESS.json                                 |   4 +-
 docs/phases/F5_technical_potential.md              |   2 +
 docs/thesis/methods/group1_technical_potential.tex |  17 ++-
 docs/thesis/references_stage_r.bib                 |   8 +-
 scripts/f2b_sanity_report.py                       |   8 +-
 src/geofrea/config_models/audit.py                 |  26 ++---
 src/geofrea/siting_layers/sanity.py                |   2 +-
 src/geofrea/technical_potential/input_ranges.py    |  82 ++++++--------
 src/geofrea/technical_potential/pipeline.py        |  55 ++++------
 src/geofrea/technical_potential/table_schemas.py   |   5 +-
 tests/unit/test_siting_sanity.py                   |   8 +-
 tests/unit/test_technical_potential_pipeline.py    | 120 ++++++++++++++-------
 16 files changed, 197 insertions(+), 172 deletions(-)
```

Untracked: `src/geofrea/technical_potential/weibull_report.py`.

## 7. For the author

1. The 150 m and 200 m limits are the same numbers as for 100 m, as the command said (three heights).
2. The `.tex` of Group 1 differs from the last commit by your edit; it is in the diff and I did not change it.
3. F3 for IND wind and the clean F5 round (PRT, IND, BRA) are still to run; with the limits the round has no input warning to leave `ran_with_issues`.
