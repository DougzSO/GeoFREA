# PV potential and eligible area by thermal zone (COMMAND 84)

Central scenario, solar. Zone of the cell = PVCZ-2019 nearest land point (T7 holds T7 and above; `no zone` = no land point within 50 km). Potential = capacity averaged over the climate members. The sensitivity `pv_hot_zone_degradation` (0.94 %/yr, Straub-Mueck 2025, global median) applies to the share in T7. Computed from existing F3 and F5 outputs; the `pvcz_zone` column itself is written by F3 at the next round.

## BRA

| Zone | Cells | Eligible area (km2) | Area share | Capacity (MW) | Potential share | Energy share |
|---|---|---|---|---|---|---|
| no zone | 469 | 2226 | 0.145% | 27824 | 0.145% | 0.134% |
| T4 | 1517 | 5695 | 0.371% | 71192 | 0.371% | 0.330% |
| T5 | 22956 | 93150 | 6.068% | 1164381 | 6.068% | 5.706% |
| T6 | 78526 | 763157 | 49.715% | 9539459 | 49.715% | 49.941% |
| T7+ | 76590 | 670839 | 43.701% | 8385489 | 43.701% | 43.890% |

## IND

| Zone | Cells | Eligible area (km2) | Area share | Capacity (MW) | Potential share | Energy share |
|---|---|---|---|---|---|---|
| no zone | 69 | 259 | 0.172% | 1294 | 0.172% | 0.178% |
| T1 | 2962 | 4026 | 2.672% | 20128 | 2.672% | 2.919% |
| T2 | 1115 | 1448 | 0.961% | 7240 | 0.961% | 1.030% |
| T3 | 242 | 160 | 0.106% | 798 | 0.106% | 0.102% |
| T4 | 144 | 160 | 0.106% | 799 | 0.106% | 0.093% |
| T5 | 761 | 435 | 0.289% | 2176 | 0.289% | 0.256% |
| T6 | 6680 | 21199 | 14.070% | 105995 | 14.070% | 14.009% |
| T7+ | 45576 | 122987 | 81.625% | 614936 | 81.625% | 81.414% |

## PRT

| Zone | Cells | Eligible area (km2) | Area share | Capacity (MW) | Potential share | Energy share |
|---|---|---|---|---|---|---|
| no zone | 2 | 1 | 0.002% | 6 | 0.002% | 0.002% |
| T4 | 225 | 730 | 3.450% | 9124 | 3.450% | 3.283% |
| T5 | 2564 | 13690 | 64.706% | 171126 | 64.706% | 64.362% |
| T6 | 658 | 6737 | 31.841% | 84208 | 31.841% | 32.353% |
