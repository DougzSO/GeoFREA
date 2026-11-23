# F8 thesis build, COMMANDS 190, 190B and 190C (2026-11-22)

Real run of `results_synthesis` for PRT, IND and BRA (`--real-run`, `settings.figures` = `summary`: the T-* do not read it, V190). The T-R6 captions carry the sentence on the 0.1 degree runs (COMMAND 189A).

## Memory

| Country | peak RSS (MB) | cap in the manifest (MB) | peak_over_cap | wall (s) | note |
|---|---|---|---|---|---|
| PRT | 374 | 1536.0 | None | 19 | default cap |
| IND | 1724 | 1536.0 | 187.5 | 38 | default cap; 187.5 MB over it, inside the hard limit |
| BRA | 2814 | None | None | 61 | caps off (`GEOFREA_MEMORY_CAPS=0`, V179c); the first run with the default cap stopped at 1,926 MB in the T-O3 figure |

Cap fixed for `results_synthesis`: 3,520 MB (`config/memory_budget.json`; ceil(1.25 x 2,814) rounded up to 64 MB). `--plan` shows every phase `resume` in the three countries after the change.

## Essential outputs (T-M1 to T-R12 and T-O3)

Hash: SHA-256 of the concatenated SHA-256 of the files of the output (tables, figures and provenance files, sorted by name), first 12 hexadecimal digits. Directory: `outputs/thesis/`.

| T-* | PRT | IND | BRA | status |
|---|---|---|---|---|
| T-M1 | ce268fd2a11f | ce268fd2a11f | ce268fd2a11f | generated |
| T-M2 | c42470bbc49f | 40caa4fd7566 | 953b64b98ab5 | generated |
| T-M3 | d50a13cbecc2 | 065e72347a03 | 800f1ba26346 | generated |
| T-R1 | f86202b34afe | 43dd20075dbf | 614760996b70 | generated |
| T-R2 | 110dd32c6f3f | fd41db25c87f | df40a7ea3c91 | generated |
| T-R3 | 69b22b3fd6ab | df6889657aef | d973eed276e0 | generated |
| T-R4 | 392444f3e9e3 | 7d1c58e9ef3d | e3a32c361f17 | generated |
| T-R5 | 39d109b0342f | 0452f9e0bddf | 259a245de20b | generated |
| T-R6 | 83a9ea7ff71b | c45bab39839b | dc257bca503a | generated |
| T-R7 | fb89d5027bea | fb89d5027bea | fb89d5027bea | generated |
| T-R8 | 0fbbe71687df | 0db6355ecfaa | 3d6410bc86de | generated |
| T-R9 | 1fe3a7a5acea | fc84291d5e21 | 01d51124238c | generated |
| T-R10 | be9857e1a029 | bbda46a8522c | 050f85b84dd1 | not available (V174b): files written with the header only, no exposure threshold is registered |
| T-R11 | a1e889e40ee8 | f8e09ba9a1e5 | e3532658dde6 | generated |
| T-R12 | 4e6ef1f30e71 | 33128ab3caae | 79bfa7d14a5b | generated |
| T-O3 | a4d4bd7e1fab | b6f05ed53a43 | c2dc65e9d191 | generated |

`T-R6`: the R_exp column (H5b, `h5b_exposure_ratio`) is empty in the three countries, not available (V174b). T-M1 and T-R7 are cross-country outputs (one set of files, no ISO in the name), so the same files appear in the three columns.

## Items not built

| T-* | item | countries | reason |
|---|---|---|---|
| T-O1 | solar and wind | PRT, IND, BRA | no box to draw: the primary PRIM search ended as `no_cases`. T-O1 is not in the list of essential outputs of COMMAND 190. |

## hypothesis_profiles (M-F8-03)

`T-R8_hypothesis_profiles_<ISO>.json`: `schema_version` 1.0, two records per country (solar, wind), `test_values` false. Variants listed in each hypothesis include `window_2071-2100` and `scale_0p1deg`. `T-R8_hypothesis_summary.csv` labels: H1, H2 and H3 `consistent` in both technologies (3 of 3 testable: H1 partially_supported_core_stable, H2 and H3 not_supported); H4 comparative (not_testable per technology); H5 `not assessable` in both (0 testable: not_testable, target_not_met_at_reference, exposure_not_available).

## LaTeX compilation

Test document with the 105 `.tex` tables and the 45 PDF figures of `outputs/thesis`, MiKTeX `pdflatex` (two passes, `-file-line-error`, packages booktabs, longtable, array, graphicx, amsmath, float, hyperref): 150 pages, zero errors (`^!` lines), zero undefined references or citations, 70 overfull-box warnings of the wide tables (T-R6 and T-R2). PDF SHA-256 (first 16 digits): 3a44be3fca04c89c (not versioned; the test document is built in the scratchpad).
