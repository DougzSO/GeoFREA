# Slope test: GLO-30, FABDEM and a 90 m support (COMMAND 100)

Diagnostic only; nothing in the pipeline changed. Scripts: `scripts/acquire_fabdem_test_100.py`, `scripts/audit_slope_dem_test_100.py`. Data: FABDEM V1-2 (University of Bristol), 7 tiles in
`GeoFREA_data/external/fabdem/` with the licence text and a manifest (URL, size, ETag, SHA-256, date). **Licence: CC BY-NC-SA 4.0**, read in `license.txt` published with the dataset
(the zips carry no readme or licence file): non-commercial and share-alike, to be cited as Hawker et al. 2022 (Environ. Res. Lett. 17, 034006); a derived table or figure in the thesis carries the same terms.

**Versions.** `glo30`: the DEM the pipeline uses (a DSM). `fabdem`: the same 30 m grid with forests and buildings removed. `smooth90`: GLO-30 after a 3 x 3 mean (90 m support), same gradient.
All three go through the F2a recipe (central differences, WGS84 geodesic spacing, 1 degree bins, pixel by sample centre) and `eligibility._steep_share`; a frame of two samples of the tile is
left out of all three so that they share one support. **E4** = share of a pixel's 30 m samples steeper than the threshold. Groups are the pixels where the class holds at least half of the 10 m
samples (shrubs 20, grassland 30, cropland 40); `all` is every in-country pixel with a slope.

## Tiles

| tile | country | place | pixels in the country |
|---|---|---|---|
| S18W051 | BRA | Cerrado, flat plateau | 10000 |
| S23W052 | BRA | Southeast pasture | 10000 |
| S13W046 | BRA | MATOPIBA | 10000 |
| N17E075 | IND | Deccan | 10000 |
| N27E073 | IND | Rajasthan | 10000 |
| N26E080 | IND | Gangetic plain | 10000 |
| N38W008 | PRT | Alentejo | 8416 |

## Summary

Eligible area (km2, before the minimum-area rules) summed over the tiles of a country and over all seven, `all` pixels. A ratio above 1 means the version keeps more land than GLO-30.

| technology | scenario | slope % | tiles | glo30 | fabdem | smooth90 | fabdem / glo30 | smooth90 / glo30 |
|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 3 | BRA | 6,201 | 6,879 | 6,482 | 1.11 | 1.05 |
| solar | restrictive | 3 | IND | 1,344 | 1,742 | 1,586 | 1.30 | 1.18 |
| solar | restrictive | 3 | PRT | 952 | 1,428 | 1,159 | 1.50 | 1.22 |
| solar | restrictive | 3 | all 7 | 8,497 | 10,049 | 9,227 | 1.18 | 1.09 |
| solar | central | 5 | BRA | 8,401 | 8,884 | 8,702 | 1.06 | 1.04 |
| solar | central | 5 | IND | 2,610 | 2,866 | 2,850 | 1.10 | 1.09 |
| solar | central | 5 | PRT | 1,917 | 2,393 | 2,263 | 1.25 | 1.18 |
| solar | central | 5 | all 7 | 12,929 | 14,143 | 13,814 | 1.09 | 1.07 |
| solar | permissive | 10 | BRA | 10,892 | 11,068 | 11,177 | 1.02 | 1.03 |
| solar | permissive | 10 | IND | 4,053 | 4,104 | 4,144 | 1.01 | 1.02 |
| solar | permissive | 10 | PRT | 3,525 | 3,753 | 3,893 | 1.06 | 1.10 |
| solar | permissive | 10 | all 7 | 18,471 | 18,925 | 19,214 | 1.02 | 1.04 |
| wind | restrictive | 10 | BRA | 25,940 | 26,393 | 26,587 | 1.02 | 1.02 |
| wind | restrictive | 10 | IND | 11,819 | 11,918 | 12,001 | 1.01 | 1.02 |
| wind | restrictive | 10 | PRT | 3,777 | 4,007 | 4,152 | 1.06 | 1.10 |
| wind | restrictive | 10 | all 7 | 41,536 | 42,318 | 42,739 | 1.02 | 1.03 |
| wind | central | 20 | BRA | 28,148 | 28,225 | 28,289 | 1.00 | 1.01 |
| wind | central | 20 | IND | 14,133 | 14,138 | 14,192 | 1.00 | 1.00 |
| wind | central | 20 | PRT | 4,915 | 4,957 | 5,044 | 1.01 | 1.03 |
| wind | central | 20 | all 7 | 47,196 | 47,320 | 47,525 | 1.00 | 1.01 |
| wind | permissive | 30 | BRA | 28,577 | 28,588 | 28,609 | 1.00 | 1.00 |
| wind | permissive | 30 | IND | 17,375 | 17,372 | 17,400 | 1.00 | 1.00 |
| wind | permissive | 30 | PRT | 5,235 | 5,243 | 5,267 | 1.00 | 1.01 |
| wind | permissive | 30 | all 7 | 51,186 | 51,203 | 51,276 | 1.00 | 1.00 |

Mean E4 over all in-country pixels of a tile at the PV thresholds, as a share of the GLO-30 value (a share of 0.2 means that 80 % of the GLO-30 cut is not there in FABDEM):

| tile | place | E4 3 % glo30 | fabdem / glo30 | smooth90 / glo30 | E4 5 % glo30 | fabdem / glo30 | smooth90 / glo30 | E4 10 % glo30 | fabdem / glo30 | smooth90 / glo30 |
|---|---|---|---|---|---|---|---|---|---|---|
| S18W051 | Cerrado, flat plateau | 0.555 | 0.83 | 0.95 | 0.309 | 0.76 | 0.86 | 0.096 | 0.61 | 0.63 |
| S23W052 | Southeast pasture | 0.806 | 0.94 | 0.99 | 0.589 | 0.91 | 0.95 | 0.177 | 0.90 | 0.77 |
| S13W046 | MATOPIBA | 0.232 | 0.80 | 0.89 | 0.091 | 0.77 | 0.81 | 0.030 | 0.86 | 0.82 |
| N17E075 | Deccan | 0.318 | 0.59 | 0.74 | 0.096 | 0.61 | 0.61 | 0.017 | 0.91 | 0.63 |
| N27E073 | Rajasthan | 0.369 | 0.56 | 0.71 | 0.181 | 0.61 | 0.64 | 0.044 | 0.75 | 0.57 |
| N26E080 | Gangetic plain | 0.315 | 0.25 | 0.58 | 0.169 | 0.17 | 0.32 | 0.036 | 0.12 | 0.08 |
| N38W008 | Alentejo | 0.775 | 0.87 | 0.95 | 0.586 | 0.84 | 0.89 | 0.279 | 0.84 | 0.75 |

## E4 mean by tile and class (area-weighted)

`pipeline` is the E4 of the aligned slope bins of the round, for reference: it differs from `glo30` only by the frame and the tile edge.

### Threshold 3 %

| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |
|---|---|---|---|---|---|---|---|---|
| S18W051 | all | 10000 | 0.555 | 0.463 | 0.525 | 0.83 | 0.95 | 0.555 |
| S18W051 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S18W051 | grassland | 414 | 0.572 | 0.451 | 0.535 | 0.79 | 0.93 | 0.572 |
| S18W051 | cropland | 7673 | 0.515 | 0.442 | 0.489 | 0.86 | 0.95 | 0.515 |
| S23W052 | all | 10000 | 0.806 | 0.757 | 0.795 | 0.94 | 0.99 | 0.806 |
| S23W052 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S23W052 | grassland | 2651 | 0.882 | 0.835 | 0.871 | 0.95 | 0.99 | 0.882 |
| S23W052 | cropland | 5079 | 0.797 | 0.754 | 0.787 | 0.95 | 0.99 | 0.797 |
| S13W046 | all | 10000 | 0.232 | 0.186 | 0.206 | 0.80 | 0.89 | 0.232 |
| S13W046 | shrubs | 5044 | 0.294 | 0.246 | 0.267 | 0.84 | 0.91 | 0.294 |
| S13W046 | grassland | 462 | 0.153 | 0.120 | 0.131 | 0.78 | 0.85 | 0.153 |
| S13W046 | cropland | 3047 | 0.080 | 0.057 | 0.063 | 0.72 | 0.79 | 0.080 |
| N17E075 | all | 10000 | 0.318 | 0.189 | 0.237 | 0.59 | 0.74 | 0.318 |
| N17E075 | shrubs | 2 | 0.908 | 0.869 | 0.895 | 0.96 | 0.99 | 0.908 |
| N17E075 | grassland | 3 | 0.628 | 0.467 | 0.524 | 0.74 | 0.83 | 0.628 |
| N17E075 | cropland | 9303 | 0.299 | 0.171 | 0.217 | 0.57 | 0.73 | 0.299 |
| N27E073 | all | 10000 | 0.369 | 0.208 | 0.264 | 0.56 | 0.71 | 0.369 |
| N27E073 | shrubs | 65 | 0.449 | 0.320 | 0.375 | 0.71 | 0.84 | 0.449 |
| N27E073 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N27E073 | cropland | 8356 | 0.342 | 0.186 | 0.238 | 0.54 | 0.70 | 0.342 |
| N26E080 | all | 10000 | 0.315 | 0.077 | 0.183 | 0.25 | 0.58 | 0.315 |
| N26E080 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | cropland | 8700 | 0.283 | 0.074 | 0.161 | 0.26 | 0.57 | 0.283 |
| N38W008 | all | 8416 | 0.775 | 0.676 | 0.734 | 0.87 | 0.95 | 0.775 |
| N38W008 | shrubs | 42 | 0.859 | 0.817 | 0.837 | 0.95 | 0.97 | 0.859 |
| N38W008 | grassland | 6520 | 0.795 | 0.692 | 0.751 | 0.87 | 0.94 | 0.795 |
| N38W008 | cropland | 381 | 0.563 | 0.433 | 0.506 | 0.77 | 0.90 | 0.563 |

### Threshold 5 %

| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |
|---|---|---|---|---|---|---|---|---|
| S18W051 | all | 10000 | 0.309 | 0.234 | 0.266 | 0.76 | 0.86 | 0.309 |
| S18W051 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S18W051 | grassland | 414 | 0.416 | 0.323 | 0.372 | 0.78 | 0.89 | 0.416 |
| S18W051 | cropland | 7673 | 0.250 | 0.192 | 0.213 | 0.77 | 0.85 | 0.250 |
| S23W052 | all | 10000 | 0.589 | 0.539 | 0.563 | 0.91 | 0.95 | 0.589 |
| S23W052 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S23W052 | grassland | 2651 | 0.712 | 0.658 | 0.684 | 0.92 | 0.96 | 0.712 |
| S23W052 | cropland | 5079 | 0.539 | 0.498 | 0.515 | 0.93 | 0.96 | 0.539 |
| S13W046 | all | 10000 | 0.091 | 0.070 | 0.074 | 0.77 | 0.81 | 0.091 |
| S13W046 | shrubs | 5044 | 0.117 | 0.096 | 0.099 | 0.82 | 0.85 | 0.117 |
| S13W046 | grassland | 462 | 0.048 | 0.035 | 0.036 | 0.73 | 0.75 | 0.048 |
| S13W046 | cropland | 3047 | 0.012 | 0.007 | 0.007 | 0.55 | 0.54 | 0.012 |
| N17E075 | all | 10000 | 0.096 | 0.058 | 0.058 | 0.61 | 0.61 | 0.096 |
| N17E075 | shrubs | 2 | 0.729 | 0.653 | 0.678 | 0.90 | 0.93 | 0.729 |
| N17E075 | grassland | 3 | 0.219 | 0.127 | 0.124 | 0.58 | 0.57 | 0.219 |
| N17E075 | cropland | 9303 | 0.081 | 0.046 | 0.046 | 0.57 | 0.56 | 0.081 |
| N27E073 | all | 10000 | 0.181 | 0.111 | 0.117 | 0.61 | 0.64 | 0.181 |
| N27E073 | shrubs | 65 | 0.257 | 0.185 | 0.193 | 0.72 | 0.75 | 0.257 |
| N27E073 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N27E073 | cropland | 8356 | 0.161 | 0.096 | 0.102 | 0.60 | 0.63 | 0.161 |
| N26E080 | all | 10000 | 0.169 | 0.029 | 0.055 | 0.17 | 0.32 | 0.169 |
| N26E080 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | cropland | 8700 | 0.148 | 0.026 | 0.045 | 0.18 | 0.30 | 0.148 |
| N38W008 | all | 8416 | 0.586 | 0.492 | 0.519 | 0.84 | 0.89 | 0.586 |
| N38W008 | shrubs | 42 | 0.791 | 0.764 | 0.768 | 0.97 | 0.97 | 0.791 |
| N38W008 | grassland | 6520 | 0.599 | 0.499 | 0.526 | 0.83 | 0.88 | 0.599 |
| N38W008 | cropland | 381 | 0.288 | 0.213 | 0.229 | 0.74 | 0.80 | 0.287 |

### Threshold 10 %

| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |
|---|---|---|---|---|---|---|---|---|
| S18W051 | all | 10000 | 0.096 | 0.058 | 0.060 | 0.61 | 0.63 | 0.096 |
| S18W051 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S18W051 | grassland | 414 | 0.169 | 0.124 | 0.127 | 0.73 | 0.75 | 0.169 |
| S18W051 | cropland | 7673 | 0.058 | 0.030 | 0.031 | 0.52 | 0.53 | 0.058 |
| S23W052 | all | 10000 | 0.177 | 0.159 | 0.137 | 0.90 | 0.77 | 0.177 |
| S23W052 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S23W052 | grassland | 2651 | 0.268 | 0.245 | 0.210 | 0.91 | 0.78 | 0.268 |
| S23W052 | cropland | 5079 | 0.118 | 0.109 | 0.090 | 0.92 | 0.76 | 0.118 |
| S13W046 | all | 10000 | 0.030 | 0.026 | 0.025 | 0.86 | 0.82 | 0.030 |
| S13W046 | shrubs | 5044 | 0.038 | 0.035 | 0.033 | 0.90 | 0.87 | 0.038 |
| S13W046 | grassland | 462 | 0.012 | 0.009 | 0.008 | 0.81 | 0.65 | 0.012 |
| S13W046 | cropland | 3047 | 0.002 | 0.001 | 0.001 | 0.58 | 0.43 | 0.002 |
| N17E075 | all | 10000 | 0.017 | 0.016 | 0.011 | 0.91 | 0.63 | 0.017 |
| N17E075 | shrubs | 2 | 0.379 | 0.360 | 0.344 | 0.95 | 0.91 | 0.379 |
| N17E075 | grassland | 3 | 0.016 | 0.012 | 0.002 | 0.76 | 0.14 | 0.016 |
| N17E075 | cropland | 9303 | 0.011 | 0.010 | 0.006 | 0.91 | 0.51 | 0.011 |
| N27E073 | all | 10000 | 0.044 | 0.033 | 0.025 | 0.75 | 0.57 | 0.044 |
| N27E073 | shrubs | 65 | 0.081 | 0.063 | 0.051 | 0.78 | 0.63 | 0.081 |
| N27E073 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N27E073 | cropland | 8356 | 0.037 | 0.028 | 0.021 | 0.75 | 0.57 | 0.037 |
| N26E080 | all | 10000 | 0.036 | 0.004 | 0.003 | 0.12 | 0.08 | 0.036 |
| N26E080 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | cropland | 8700 | 0.030 | 0.003 | 0.002 | 0.11 | 0.06 | 0.030 |
| N38W008 | all | 8416 | 0.279 | 0.236 | 0.209 | 0.84 | 0.75 | 0.279 |
| N38W008 | shrubs | 42 | 0.679 | 0.644 | 0.614 | 0.95 | 0.90 | 0.679 |
| N38W008 | grassland | 6520 | 0.272 | 0.226 | 0.196 | 0.83 | 0.72 | 0.272 |
| N38W008 | cropland | 381 | 0.049 | 0.040 | 0.028 | 0.82 | 0.57 | 0.049 |

### Threshold 20 %

| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |
|---|---|---|---|---|---|---|---|---|
| S18W051 | all | 10000 | 0.019 | 0.012 | 0.010 | 0.64 | 0.54 | 0.019 |
| S18W051 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S18W051 | grassland | 414 | 0.038 | 0.029 | 0.024 | 0.76 | 0.63 | 0.038 |
| S18W051 | cropland | 7673 | 0.007 | 0.003 | 0.002 | 0.40 | 0.27 | 0.007 |
| S23W052 | all | 10000 | 0.015 | 0.012 | 0.006 | 0.77 | 0.42 | 0.015 |
| S23W052 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S23W052 | grassland | 2651 | 0.020 | 0.016 | 0.008 | 0.82 | 0.39 | 0.020 |
| S23W052 | cropland | 5079 | 0.008 | 0.006 | 0.003 | 0.75 | 0.40 | 0.008 |
| S13W046 | all | 10000 | 0.011 | 0.011 | 0.009 | 0.97 | 0.85 | 0.011 |
| S13W046 | shrubs | 5044 | 0.016 | 0.016 | 0.014 | 0.99 | 0.89 | 0.016 |
| S13W046 | grassland | 462 | 0.002 | 0.002 | 0.001 | 0.89 | 0.58 | 0.002 |
| S13W046 | cropland | 3047 | 0.000 | 0.000 | 0.000 | 0.86 | 0.27 | 0.000 |
| N17E075 | all | 10000 | 0.003 | 0.004 | 0.002 | 1.07 | 0.55 | 0.003 |
| N17E075 | shrubs | 2 | 0.178 | 0.178 | 0.136 | 1.00 | 0.76 | 0.178 |
| N17E075 | grassland | 3 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 |
| N17E075 | cropland | 9303 | 0.001 | 0.001 | 0.001 | 1.18 | 0.42 | 0.001 |
| N27E073 | all | 10000 | 0.009 | 0.009 | 0.004 | 0.93 | 0.44 | 0.009 |
| N27E073 | shrubs | 65 | 0.019 | 0.018 | 0.009 | 0.95 | 0.49 | 0.019 |
| N27E073 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N27E073 | cropland | 8356 | 0.008 | 0.007 | 0.003 | 0.93 | 0.42 | 0.008 |
| N26E080 | all | 10000 | 0.001 | 0.000 | 0.000 | 0.39 | 0.05 | 0.001 |
| N26E080 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | cropland | 8700 | 0.001 | 0.000 | 0.000 | 0.24 | 0.02 | 0.001 |
| N38W008 | all | 8416 | 0.069 | 0.060 | 0.040 | 0.86 | 0.58 | 0.069 |
| N38W008 | shrubs | 42 | 0.384 | 0.356 | 0.279 | 0.93 | 0.73 | 0.384 |
| N38W008 | grassland | 6520 | 0.054 | 0.046 | 0.028 | 0.84 | 0.51 | 0.054 |
| N38W008 | cropland | 381 | 0.001 | 0.001 | 0.000 | 0.96 | 0.25 | 0.001 |

### Threshold 30 %

| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |
|---|---|---|---|---|---|---|---|---|
| S18W051 | all | 10000 | 0.005 | 0.004 | 0.003 | 0.82 | 0.62 | 0.005 |
| S18W051 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S18W051 | grassland | 414 | 0.011 | 0.009 | 0.007 | 0.81 | 0.60 | 0.011 |
| S18W051 | cropland | 7673 | 0.001 | 0.001 | 0.000 | 0.57 | 0.32 | 0.001 |
| S23W052 | all | 10000 | 0.002 | 0.002 | 0.001 | 0.71 | 0.26 | 0.002 |
| S23W052 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| S23W052 | grassland | 2651 | 0.003 | 0.002 | 0.001 | 0.67 | 0.24 | 0.003 |
| S23W052 | cropland | 5079 | 0.001 | 0.001 | 0.000 | 0.70 | 0.23 | 0.001 |
| S13W046 | all | 10000 | 0.005 | 0.005 | 0.004 | 1.00 | 0.82 | 0.005 |
| S13W046 | shrubs | 5044 | 0.009 | 0.009 | 0.007 | 1.00 | 0.84 | 0.009 |
| S13W046 | grassland | 462 | 0.001 | 0.001 | 0.000 | 0.93 | 0.73 | 0.001 |
| S13W046 | cropland | 3047 | 0.000 | 0.000 | 0.000 | 0.95 | 0.53 | 0.000 |
| N17E075 | all | 10000 | 0.001 | 0.001 | 0.000 | 1.09 | 0.36 | 0.001 |
| N17E075 | shrubs | 2 | 0.070 | 0.071 | 0.033 | 1.02 | 0.48 | 0.070 |
| N17E075 | grassland | 3 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 |
| N17E075 | cropland | 9303 | 0.000 | 0.000 | 0.000 | 1.12 | 0.31 | 0.000 |
| N27E073 | all | 10000 | 0.003 | 0.003 | 0.000 | 1.07 | 0.14 | 0.003 |
| N27E073 | shrubs | 65 | 0.006 | 0.006 | 0.001 | 1.06 | 0.16 | 0.006 |
| N27E073 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N27E073 | cropland | 8356 | 0.002 | 0.002 | 0.000 | 1.08 | 0.11 | 0.002 |
| N26E080 | all | 10000 | 0.000 | 0.000 | 0.000 | 0.98 | 0.02 | 0.000 |
| N26E080 | shrubs | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | grassland | 0 | nan | nan | nan | n/a | n/a | nan |
| N26E080 | cropland | 8700 | 0.000 | 0.000 | 0.000 | 1.06 | 0.00 | 0.000 |
| N38W008 | all | 8416 | 0.017 | 0.015 | 0.008 | 0.87 | 0.50 | 0.017 |
| N38W008 | shrubs | 42 | 0.153 | 0.143 | 0.090 | 0.94 | 0.59 | 0.153 |
| N38W008 | grassland | 6520 | 0.010 | 0.008 | 0.004 | 0.85 | 0.42 | 0.010 |
| N38W008 | cropland | 381 | 0.000 | 0.000 | 0.000 | 1.11 | 0.01 | 0.000 |

## Eligible area by version (km2, before the minimum-area rules)

Slope thresholds of the scenarios: PV 3 / 5 / 10 %, wind 10 / 20 / 30 %. Eligible area by the F3 engine with the E4 of the version in place of the aligned one; all other exclusions are those of the round.

### solar

| tile | scenario | slope % | glo30 | fabdem | smooth90 | fabdem - glo30 | smooth90 - glo30 | fabdem / glo30 | smooth90 / glo30 |
|---|---|---|---|---|---|---|---|---|---|
| S18W051 | restrictive | 3 | 666 | 855 | 723 | +189 | +57 | 1.28 | 1.09 |
| S18W051 | central | 5 | 989 | 1,143 | 1,068 | +153 | +79 | 1.15 | 1.08 |
| S18W051 | permissive | 10 | 1,369 | 1,447 | 1,440 | +78 | +71 | 1.06 | 1.05 |
| S23W052 | restrictive | 3 | 506 | 669 | 542 | +163 | +37 | 1.32 | 1.07 |
| S23W052 | central | 5 | 1,203 | 1,387 | 1,301 | +184 | +98 | 1.15 | 1.08 |
| S23W052 | permissive | 10 | 2,797 | 2,868 | 2,973 | +71 | +176 | 1.03 | 1.06 |
| S13W046 | restrictive | 3 | 5,030 | 5,355 | 5,218 | +325 | +188 | 1.06 | 1.04 |
| S13W046 | central | 5 | 6,209 | 6,354 | 6,333 | +145 | +124 | 1.02 | 1.02 |
| S13W046 | permissive | 10 | 6,725 | 6,753 | 6,764 | +28 | +38 | 1.00 | 1.01 |
| N17E075 | restrictive | 3 | 524 | 640 | 592 | +116 | +68 | 1.22 | 1.13 |
| N17E075 | central | 5 | 1,104 | 1,164 | 1,163 | +60 | +59 | 1.05 | 1.05 |
| N17E075 | permissive | 10 | 1,667 | 1,672 | 1,683 | +5 | +16 | 1.00 | 1.01 |
| N27E073 | restrictive | 3 | 802 | 1,080 | 974 | +278 | +171 | 1.35 | 1.21 |
| N27E073 | central | 5 | 1,416 | 1,604 | 1,589 | +188 | +173 | 1.13 | 1.12 |
| N27E073 | permissive | 10 | 2,067 | 2,107 | 2,135 | +40 | +68 | 1.02 | 1.03 |
| N26E080 | restrictive | 3 | 18 | 22 | 21 | +3 | +2 | 1.19 | 1.12 |
| N26E080 | central | 5 | 90 | 98 | 98 | +9 | +8 | 1.10 | 1.09 |
| N26E080 | permissive | 10 | 319 | 325 | 326 | +6 | +7 | 1.02 | 1.02 |
| N38W008 | restrictive | 3 | 952 | 1,428 | 1,159 | +477 | +207 | 1.50 | 1.22 |
| N38W008 | central | 5 | 1,917 | 2,393 | 2,263 | +476 | +346 | 1.25 | 1.18 |
| N38W008 | permissive | 10 | 3,525 | 3,753 | 3,893 | +228 | +367 | 1.06 | 1.10 |

### wind

| tile | scenario | slope % | glo30 | fabdem | smooth90 | fabdem - glo30 | smooth90 - glo30 | fabdem / glo30 | smooth90 / glo30 |
|---|---|---|---|---|---|---|---|---|---|
| S18W051 | restrictive | 10 | 8,554 | 8,849 | 8,834 | +296 | +280 | 1.03 | 1.03 |
| S18W051 | central | 20 | 9,153 | 9,204 | 9,216 | +51 | +63 | 1.01 | 1.01 |
| S18W051 | permissive | 30 | 9,284 | 9,290 | 9,295 | +6 | +11 | 1.00 | 1.00 |
| S23W052 | restrictive | 10 | 7,293 | 7,420 | 7,618 | +127 | +325 | 1.02 | 1.04 |
| S23W052 | central | 20 | 8,727 | 8,752 | 8,793 | +24 | +65 | 1.00 | 1.01 |
| S23W052 | permissive | 30 | 8,962 | 8,967 | 8,974 | +5 | +13 | 1.00 | 1.00 |
| S13W046 | restrictive | 10 | 10,093 | 10,123 | 10,135 | +30 | +42 | 1.00 | 1.00 |
| S13W046 | central | 20 | 10,267 | 10,269 | 10,280 | +2 | +13 | 1.00 | 1.00 |
| S13W046 | permissive | 30 | 10,331 | 10,331 | 10,340 | -0 | +8 | 1.00 | 1.00 |
| N17E075 | restrictive | 10 | 4,374 | 4,381 | 4,399 | +7 | +25 | 1.00 | 1.01 |
| N17E075 | central | 20 | 5,298 | 5,297 | 5,309 | -1 | +10 | 1.00 | 1.00 |
| N17E075 | permissive | 30 | 6,771 | 6,770 | 6,775 | -1 | +4 | 1.00 | 1.00 |
| N27E073 | restrictive | 10 | 7,148 | 7,237 | 7,301 | +89 | +153 | 1.01 | 1.02 |
| N27E073 | central | 20 | 8,268 | 8,274 | 8,316 | +6 | +48 | 1.00 | 1.01 |
| N27E073 | permissive | 30 | 9,239 | 9,238 | 9,261 | -2 | +21 | 1.00 | 1.00 |
| N26E080 | restrictive | 10 | 297 | 301 | 301 | +3 | +4 | 1.01 | 1.01 |
| N26E080 | central | 20 | 567 | 567 | 568 | +0 | +0 | 1.00 | 1.00 |
| N26E080 | permissive | 30 | 1,364 | 1,364 | 1,364 | -0 | +0 | 1.00 | 1.00 |
| N38W008 | restrictive | 10 | 3,777 | 4,007 | 4,152 | +230 | +375 | 1.06 | 1.10 |
| N38W008 | central | 20 | 4,915 | 4,957 | 5,044 | +42 | +129 | 1.01 | 1.03 |
| N38W008 | permissive | 30 | 5,235 | 5,243 | 5,267 | +8 | +32 | 1.00 | 1.01 |

## Eligible area by class (km2)

Pixels where the class holds at least half of the samples. Cropland is excluded for PV by the land cover, eligible for wind.

### solar

| tile | scenario | slope % | class | area km2 | glo30 | fabdem | smooth90 |
|---|---|---|---|---|---|---|---|
| S18W051 | restrictive | 3 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | restrictive | 3 | grassland | 487 | 134 | 170 | 145 |
| S18W051 | restrictive | 3 | cropland | 9,017 | 351 | 416 | 373 |
| S18W051 | central | 5 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | central | 5 | grassland | 487 | 181 | 209 | 194 |
| S18W051 | central | 5 | cropland | 9,017 | 528 | 579 | 559 |
| S18W051 | permissive | 10 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | permissive | 10 | grassland | 487 | 257 | 271 | 270 |
| S18W051 | permissive | 10 | cropland | 9,017 | 678 | 702 | 702 |
| S23W052 | restrictive | 3 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | restrictive | 3 | grassland | 3,025 | 225 | 312 | 244 |
| S23W052 | restrictive | 3 | cropland | 5,783 | 170 | 208 | 179 |
| S23W052 | central | 5 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | central | 5 | grassland | 3,025 | 564 | 669 | 619 |
| S23W052 | central | 5 | cropland | 5,783 | 397 | 435 | 419 |
| S23W052 | permissive | 10 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | permissive | 10 | grassland | 3,025 | 1,477 | 1,522 | 1,594 |
| S23W052 | permissive | 10 | cropland | 5,783 | 803 | 811 | 831 |
| S13W046 | restrictive | 3 | shrubs | 6,065 | 3,761 | 3,994 | 3,897 |
| S13W046 | restrictive | 3 | grassland | 556 | 351 | 365 | 360 |
| S13W046 | restrictive | 3 | cropland | 3,663 | 377 | 391 | 387 |
| S13W046 | central | 5 | shrubs | 6,065 | 4,683 | 4,778 | 4,767 |
| S13W046 | central | 5 | grassland | 556 | 397 | 403 | 402 |
| S13W046 | central | 5 | cropland | 3,663 | 426 | 430 | 430 |
| S13W046 | permissive | 10 | shrubs | 6,065 | 5,069 | 5,084 | 5,091 |
| S13W046 | permissive | 10 | grassland | 556 | 415 | 416 | 417 |
| S13W046 | permissive | 10 | cropland | 3,663 | 436 | 436 | 437 |
| N17E075 | restrictive | 3 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | restrictive | 3 | grassland | 4 | 1 | 1 | 1 |
| N17E075 | restrictive | 3 | cropland | 10,934 | 443 | 531 | 496 |
| N17E075 | central | 5 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | central | 5 | grassland | 4 | 2 | 2 | 2 |
| N17E075 | central | 5 | cropland | 10,934 | 923 | 964 | 966 |
| N17E075 | permissive | 10 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | permissive | 10 | grassland | 4 | 2 | 2 | 2 |
| N17E075 | permissive | 10 | cropland | 10,934 | 1,390 | 1,392 | 1,400 |
| N27E073 | restrictive | 3 | shrubs | 71 | 21 | 26 | 24 |
| N27E073 | restrictive | 3 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | restrictive | 3 | cropland | 9,151 | 473 | 631 | 572 |
| N27E073 | central | 5 | shrubs | 71 | 34 | 38 | 37 |
| N27E073 | central | 5 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | central | 5 | cropland | 9,151 | 815 | 914 | 906 |
| N27E073 | permissive | 10 | shrubs | 71 | 48 | 49 | 49 |
| N27E073 | permissive | 10 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | permissive | 10 | cropland | 9,151 | 1,153 | 1,172 | 1,186 |
| N26E080 | restrictive | 3 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | restrictive | 3 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | restrictive | 3 | cropland | 9,611 | 14 | 17 | 16 |
| N26E080 | central | 5 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | central | 5 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | central | 5 | cropland | 9,611 | 78 | 85 | 85 |
| N26E080 | permissive | 10 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | permissive | 10 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | permissive | 10 | cropland | 9,611 | 288 | 293 | 294 |
| N38W008 | restrictive | 3 | shrubs | 41 | 4 | 5 | 4 |
| N38W008 | restrictive | 3 | grassland | 6,313 | 831 | 1,263 | 1,022 |
| N38W008 | restrictive | 3 | cropland | 369 | 27 | 36 | 31 |
| N38W008 | central | 5 | shrubs | 41 | 6 | 7 | 7 |
| N38W008 | central | 5 | grassland | 6,313 | 1,699 | 2,134 | 2,018 |
| N38W008 | central | 5 | cropland | 369 | 48 | 53 | 52 |
| N38W008 | permissive | 10 | shrubs | 41 | 10 | 11 | 12 |
| N38W008 | permissive | 10 | grassland | 6,313 | 3,158 | 3,362 | 3,491 |
| N38W008 | permissive | 10 | cropland | 369 | 67 | 68 | 69 |

### wind

| tile | scenario | slope % | class | area km2 | glo30 | fabdem | smooth90 |
|---|---|---|---|---|---|---|---|
| S18W051 | restrictive | 10 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | restrictive | 10 | grassland | 487 | 327 | 343 | 342 |
| S18W051 | restrictive | 10 | cropland | 9,017 | 7,302 | 7,497 | 7,493 |
| S18W051 | central | 20 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | central | 20 | grassland | 487 | 374 | 377 | 379 |
| S18W051 | central | 20 | cropland | 9,017 | 7,674 | 7,705 | 7,711 |
| S18W051 | permissive | 30 | shrubs | 0 | 0 | 0 | 0 |
| S18W051 | permissive | 30 | grassland | 487 | 384 | 385 | 385 |
| S18W051 | permissive | 30 | cropland | 9,017 | 7,749 | 7,752 | 7,753 |
| S23W052 | restrictive | 10 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | restrictive | 10 | grassland | 3,025 | 1,810 | 1,860 | 1,942 |
| S23W052 | restrictive | 10 | cropland | 5,783 | 4,506 | 4,551 | 4,642 |
| S23W052 | central | 20 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | central | 20 | grassland | 3,025 | 2,424 | 2,432 | 2,450 |
| S23W052 | central | 20 | cropland | 5,783 | 5,080 | 5,089 | 5,102 |
| S23W052 | permissive | 30 | shrubs | 0 | 0 | 0 | 0 |
| S23W052 | permissive | 30 | grassland | 3,025 | 2,527 | 2,529 | 2,531 |
| S23W052 | permissive | 30 | cropland | 5,783 | 5,164 | 5,166 | 5,168 |
| S13W046 | restrictive | 10 | shrubs | 6,065 | 5,239 | 5,255 | 5,261 |
| S13W046 | restrictive | 10 | grassland | 556 | 462 | 463 | 464 |
| S13W046 | restrictive | 10 | cropland | 3,663 | 3,319 | 3,321 | 3,322 |
| S13W046 | central | 20 | shrubs | 6,065 | 5,350 | 5,351 | 5,358 |
| S13W046 | central | 20 | grassland | 556 | 468 | 468 | 468 |
| S13W046 | central | 20 | cropland | 3,663 | 3,327 | 3,327 | 3,328 |
| S13W046 | permissive | 30 | shrubs | 6,065 | 5,389 | 5,389 | 5,396 |
| S13W046 | permissive | 30 | grassland | 556 | 470 | 470 | 470 |
| S13W046 | permissive | 30 | cropland | 3,663 | 3,331 | 3,331 | 3,331 |
| N17E075 | restrictive | 10 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | restrictive | 10 | grassland | 4 | 3 | 3 | 3 |
| N17E075 | restrictive | 10 | cropland | 10,934 | 4,060 | 4,064 | 4,078 |
| N17E075 | central | 20 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | central | 20 | grassland | 4 | 3 | 3 | 3 |
| N17E075 | central | 20 | cropland | 10,934 | 4,924 | 4,923 | 4,928 |
| N17E075 | permissive | 30 | shrubs | 2 | 0 | 0 | 0 |
| N17E075 | permissive | 30 | grassland | 4 | 3 | 3 | 3 |
| N17E075 | permissive | 30 | cropland | 10,934 | 6,334 | 6,334 | 6,335 |
| N27E073 | restrictive | 10 | shrubs | 71 | 48 | 50 | 50 |
| N27E073 | restrictive | 10 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | restrictive | 10 | cropland | 9,151 | 6,191 | 6,255 | 6,302 |
| N27E073 | central | 20 | shrubs | 71 | 57 | 57 | 57 |
| N27E073 | central | 20 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | central | 20 | cropland | 9,151 | 7,119 | 7,123 | 7,154 |
| N27E073 | permissive | 30 | shrubs | 71 | 63 | 63 | 64 |
| N27E073 | permissive | 30 | grassland | 0 | 0 | 0 | 0 |
| N27E073 | permissive | 30 | cropland | 9,151 | 7,942 | 7,940 | 7,956 |
| N26E080 | restrictive | 10 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | restrictive | 10 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | restrictive | 10 | cropland | 9,611 | 276 | 279 | 279 |
| N26E080 | central | 20 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | central | 20 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | central | 20 | cropland | 9,611 | 534 | 534 | 534 |
| N26E080 | permissive | 30 | shrubs | 0 | 0 | 0 | 0 |
| N26E080 | permissive | 30 | grassland | 0 | 0 | 0 | 0 |
| N26E080 | permissive | 30 | cropland | 9,611 | 1,307 | 1,307 | 1,307 |
| N38W008 | restrictive | 10 | shrubs | 41 | 9 | 10 | 11 |
| N38W008 | restrictive | 10 | grassland | 6,313 | 3,206 | 3,410 | 3,541 |
| N38W008 | restrictive | 10 | cropland | 369 | 206 | 208 | 211 |
| N38W008 | central | 20 | shrubs | 41 | 17 | 18 | 20 |
| N38W008 | central | 20 | grassland | 6,313 | 4,193 | 4,226 | 4,295 |
| N38W008 | central | 20 | cropland | 369 | 223 | 223 | 223 |
| N38W008 | permissive | 30 | shrubs | 41 | 23 | 23 | 25 |
| N38W008 | permissive | 30 | grassland | 6,313 | 4,444 | 4,450 | 4,465 |
| N38W008 | permissive | 30 | cropland | 369 | 228 | 228 | 228 |

## Check of the engine against the round

`round raster` = `eligible_fraction_<tech>[__scenario].tif` of the round (after the minimum-area rules, with the siting-resource validity) x pixel area, over the tile. `engine, pipeline bins` =
the engine here with the aligned slope bins of the round (before the minimum-area rules); the gap to the round raster is the minimum-area rules and the resource validity. `engine, own bins` =
the engine with the bins this script builds from GLO-30: the gap to `pipeline bins` is the frame of two samples and the tile edge.

| tile | technology | scenario | round raster | engine, pipeline bins | engine, own bins (glo30) |
|---|---|---|---|---|---|
| S18W051 | solar | restrictive | 665.8 | 665.8 | 665.8 |
| S18W051 | solar | central | 989.4 | 989.4 | 989.3 |
| S18W051 | solar | permissive | 1,369.4 | 1,369.4 | 1,369.4 |
| S18W051 | wind | restrictive | 8,538.6 | 8,553.4 | 8,553.6 |
| S18W051 | wind | central | 9,148.0 | 9,153.2 | 9,153.2 |
| S18W051 | wind | permissive | 9,283.8 | 9,283.8 | 9,283.8 |
| S23W052 | solar | restrictive | 505.8 | 505.8 | 505.8 |
| S23W052 | solar | central | 1,202.9 | 1,202.9 | 1,202.9 |
| S23W052 | solar | permissive | 2,797.2 | 2,797.2 | 2,797.1 |
| S23W052 | wind | restrictive | 7,271.2 | 7,293.3 | 7,293.2 |
| S23W052 | wind | central | 8,716.5 | 8,727.3 | 8,727.3 |
| S23W052 | wind | permissive | 8,961.7 | 8,961.7 | 8,961.7 |
| S13W046 | solar | restrictive | 5,029.6 | 5,029.6 | 5,029.7 |
| S13W046 | solar | central | 6,209.1 | 6,209.1 | 6,209.2 |
| S13W046 | solar | permissive | 6,725.4 | 6,725.4 | 6,725.5 |
| S13W046 | wind | restrictive | 10,086.4 | 10,093.2 | 10,093.2 |
| S13W046 | wind | central | 10,265.4 | 10,267.3 | 10,267.4 |
| S13W046 | wind | permissive | 10,331.4 | 10,331.4 | 10,331.4 |
| N17E075 | solar | restrictive | 522.8 | 523.7 | 523.7 |
| N17E075 | solar | central | 1,102.9 | 1,103.8 | 1,103.8 |
| N17E075 | solar | permissive | 1,667.4 | 1,667.4 | 1,667.4 |
| N17E075 | wind | restrictive | 4,078.3 | 4,374.1 | 4,374.0 |
| N17E075 | wind | central | 5,235.0 | 5,298.4 | 5,298.4 |
| N17E075 | wind | permissive | 6,770.8 | 6,770.8 | 6,770.8 |
| N27E073 | solar | restrictive | 802.3 | 802.3 | 802.5 |
| N27E073 | solar | central | 1,416.2 | 1,416.2 | 1,416.4 |
| N27E073 | solar | permissive | 2,067.1 | 2,067.1 | 2,067.2 |
| N27E073 | wind | restrictive | 7,096.2 | 7,147.4 | 7,147.6 |
| N27E073 | wind | central | 8,255.8 | 8,267.5 | 8,267.6 |
| N27E073 | wind | permissive | 9,239.4 | 9,239.4 | 9,239.4 |
| N26E080 | solar | restrictive | 7.5 | 18.3 | 18.3 |
| N26E080 | solar | central | 78.0 | 89.8 | 89.8 |
| N26E080 | solar | permissive | 318.8 | 318.8 | 318.8 |
| N26E080 | wind | restrictive | 119.4 | 297.4 | 297.4 |
| N26E080 | wind | central | 500.3 | 567.2 | 567.2 |
| N26E080 | wind | permissive | 1,364.4 | 1,364.4 | 1,364.4 |
| N38W008 | solar | restrictive | 951.1 | 951.7 | 951.7 |
| N38W008 | solar | central | 1,915.9 | 1,917.2 | 1,917.0 |
| N38W008 | solar | permissive | 3,525.5 | 3,525.5 | 3,525.4 |
| N38W008 | wind | restrictive | 3,710.6 | 3,777.0 | 3,777.0 |
| N38W008 | wind | central | 4,894.7 | 4,914.6 | 4,914.6 |
| N38W008 | wind | permissive | 5,234.6 | 5,234.6 | 5,234.7 |
