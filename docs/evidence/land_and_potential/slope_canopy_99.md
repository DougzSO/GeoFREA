# Slope x canopy (COMMAND 99, step 2)

Diagnostic only; nothing in the pipeline changed. Script: `scripts/audit_slope_canopy_99.py`. GLO-30 is a DSM, so tree canopy can read as slope.

**Cut** = E4 x geodesic pixel area (km2), over the in-country pixels with a slope and a land-cover value; E4 = share of the pixel's 30 m samples steeper than the
slope maximum of the scenario. **Classes** = WorldCover 10 m samples of the pixel. Slope bins (30 m) and class counts (10 m) are not co-registered inside a
0.01 degree pixel, so the overlap is given three ways: *independent* (e x F, the assumption F3 itself makes), and the *lower* and *upper* bounds any arrangement
inside the pixel allows (max(0, e + F - 1) and min(e, F)). The classes the land cover already excludes are those of the scenario (solar: 10, 40, 50, 70, 80, 90, 95;
wind: 10, 50, 70, 80, 90, 95).

## BRA

Country area with slope and land cover: 8,507,201 km2.

### Cut by class group (independent reading, km2)

| technology | scenario | slope max % | cut km2 | cut % of country | trees | shrubs | cropland | grassland | other |
|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 3 | 6,361,833 | 74.78 | 3,954,621 | 584,126 | 405,791 | 1,282,338 | 134,957 |
| solar | central | 5 | 5,000,241 | 58.78 | 3,257,209 | 406,585 | 271,249 | 966,970 | 98,228 |
| solar | permissive | 10 | 2,823,949 | 33.19 | 1,935,887 | 202,012 | 107,387 | 529,947 | 48,716 |
| wind | restrictive | 10 | 2,823,949 | 33.19 | 1,935,887 | 202,012 | 107,387 | 529,947 | 48,716 |
| wind | central | 20 | 1,145,107 | 13.46 | 785,918 | 85,936 | 25,137 | 231,139 | 16,978 |
| wind | permissive | 30 | 549,441 | 6.46 | 369,622 | 44,244 | 9,035 | 119,106 | 7,434 |

### Cut inside classes the land cover already excludes, and inside eligible classes (km2 and % of the cut)

| technology | scenario | cut km2 | in excluded: independent | % | in excluded: lower | % | in excluded: upper | % | in eligible classes: independent | % |
|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 6,361,833 | 4,453,669 | 70.0 | 4,170,183 | 65.6 | 4,748,161 | 74.6 | 1,908,164 | 30.0 |
| solar | central | 5,000,241 | 3,596,762 | 71.9 | 3,268,849 | 65.4 | 3,946,593 | 78.9 | 1,403,479 | 28.1 |
| solar | permissive | 2,823,949 | 2,077,212 | 73.6 | 1,792,526 | 63.5 | 2,364,388 | 83.7 | 746,737 | 26.4 |
| wind | restrictive | 2,823,949 | 1,969,824 | 69.8 | 1,697,609 | 60.1 | 2,277,771 | 80.7 | 854,124 | 30.2 |
| wind | central | 1,145,107 | 797,259 | 69.6 | 631,936 | 55.2 | 975,048 | 85.1 | 347,848 | 30.4 |
| wind | permissive | 549,441 | 374,371 | 68.1 | 269,030 | 49.0 | 483,897 | 88.1 | 175,070 | 31.9 |

### Is steepness higher under tree cover? Mean E4 in pixels dominated by one kind of cover (no independence assumption)

Pixels with at least 90 % of the samples in trees, against pixels with at least 90 % in shrubs, grassland or cropland. A DSM canopy artifact would make the first rate higher at the same terrain.

| technology | scenario | tree pixels km2 | mean E4, tree pixels | open pixels km2 | mean E4, open pixels | ratio |
|---|---|---|---|---|---|---|
| solar | restrictive | 3,264,389 | 0.858 | 1,513,872 | 0.558 | 1.54 |
| solar | central | 3,264,389 | 0.711 | 1,513,872 | 0.350 | 2.03 |
| solar | permissive | 3,264,389 | 0.416 | 1,513,872 | 0.138 | 3.01 |
| wind | restrictive | 3,264,389 | 0.416 | 1,513,872 | 0.138 | 3.01 |
| wind | central | 3,264,389 | 0.156 | 1,513,872 | 0.046 | 3.39 |
| wind | permissive | 3,264,389 | 0.068 | 1,513,872 | 0.021 | 3.25 |

## IND

Country area with slope and land cover: 3,143,290 km2.

### Cut by class group (independent reading, km2)

| technology | scenario | slope max % | cut km2 | cut % of country | trees | shrubs | cropland | grassland | other |
|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 3 | 1,646,278 | 52.37 | 633,198 | 89,631 | 499,338 | 195,432 | 228,679 |
| solar | central | 5 | 1,212,951 | 38.59 | 560,911 | 65,661 | 251,247 | 158,376 | 176,755 |
| solar | permissive | 10 | 803,356 | 25.56 | 442,376 | 39,128 | 81,292 | 112,457 | 128,102 |
| wind | restrictive | 10 | 803,356 | 25.56 | 442,376 | 39,128 | 81,292 | 112,457 | 128,102 |
| wind | central | 20 | 549,787 | 17.49 | 324,277 | 21,366 | 24,828 | 78,156 | 101,160 |
| wind | permissive | 30 | 419,545 | 13.35 | 246,920 | 13,167 | 12,103 | 59,692 | 87,663 |

### Cut inside classes the land cover already excludes, and inside eligible classes (km2 and % of the cut)

| technology | scenario | cut km2 | in excluded: independent | % | in excluded: lower | % | in excluded: upper | % | in eligible classes: independent | % |
|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 1,646,278 | 1,194,630 | 72.6 | 1,058,827 | 64.3 | 1,316,553 | 80.0 | 451,648 | 27.4 |
| solar | central | 1,212,951 | 855,971 | 70.6 | 715,378 | 59.0 | 954,336 | 78.7 | 356,981 | 29.4 |
| solar | permissive | 803,356 | 551,266 | 68.6 | 456,848 | 56.9 | 616,489 | 76.7 | 252,091 | 31.4 |
| wind | restrictive | 803,356 | 469,973 | 58.5 | 410,822 | 51.1 | 556,779 | 69.3 | 333,383 | 41.5 |
| wind | central | 549,787 | 343,762 | 62.5 | 303,395 | 55.2 | 391,551 | 71.2 | 206,025 | 37.5 |
| wind | permissive | 419,545 | 263,024 | 62.7 | 228,671 | 54.5 | 299,843 | 71.5 | 156,521 | 37.3 |

### Is steepness higher under tree cover? Mean E4 in pixels dominated by one kind of cover (no independence assumption)

Pixels with at least 90 % of the samples in trees, against pixels with at least 90 % in shrubs, grassland or cropland. A DSM canopy artifact would make the first rate higher at the same terrain.

| technology | scenario | tree pixels km2 | mean E4, tree pixels | open pixels km2 | mean E4, open pixels | ratio |
|---|---|---|---|---|---|---|
| solar | restrictive | 336,025 | 0.962 | 988,969 | 0.290 | 3.32 |
| solar | central | 336,025 | 0.918 | 988,969 | 0.144 | 6.40 |
| solar | permissive | 336,025 | 0.806 | 988,969 | 0.057 | 14.08 |
| wind | restrictive | 336,025 | 0.806 | 988,969 | 0.057 | 14.08 |
| wind | central | 336,025 | 0.634 | 988,969 | 0.025 | 25.54 |
| wind | permissive | 336,025 | 0.494 | 988,969 | 0.014 | 35.16 |

## Check

The cut and the country area equal, to the km2, the sums of `excluded_area_km2_E4` and `cell_area_km2` of the F3 cell tables of the round (`cells_<tech>__<scenario>.parquet`).
