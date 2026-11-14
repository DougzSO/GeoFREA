# Distance statistics of the round 1d34ab23 (COMMAND 116, item 6)

Written for: the author, as the source of the numbers the thesis text cites for the distance to roads and substations. Weights: the eligible area of the 0.05 degree cell, or its potential (mean over the climate members of `P_MW`); the distances are those of the cell (the mean over its eligible area, M-F3-03), not of each pixel. "before" is the round 9c2dc3c8 (isotropic scale), "after" the round 1d34ab23 (exact geodesic). Script: `scratchpad/stats_116.py` (not kept in the repository).

## PRT

### (a) road distance and (b) share of the potential beyond 100 km of a substation (eligible-area / potential weighted; before -> after)

| tech | scenario | median dist_road_km | eligible area > 30 km of a road | potential > 100 km of a substation | median dist_sub_km |
|---|---|---|---|---|---|
| solar | central | 1.49 -> 1.68 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 15.1 -> 15.4 |
| solar | restrictive | 1.55 -> 1.77 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 15.1 -> 15.4 |
| solar | permissive | 1.43 -> 1.62 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 14.9 -> 15.0 |
| wind | central | 1.57 -> 1.76 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 14.7 -> 14.9 |
| wind | restrictive | 1.61 -> 1.80 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 15.6 -> 15.7 |
| wind | permissive | 1.49 -> 1.70 | 0.0 % -> 0.0 % | 0.0 % -> 0.0 % | 14.3 -> 14.2 |

### (c) PV, central scenario: share of the potential by thermal zone (zones above T7 count as T7; 0 = no PVCZ land point)

- before: T0: 0.0 %, T4: 3.3 %, T5: 60.3 %, T6: 36.4 %; **T7 or hotter: 0.0 %**
- after: T0: 0.0 %, T4: 3.3 %, T5: 60.3 %, T6: 36.4 %; **T7 or hotter: 0.0 %**

### (d) relative change of dist_sub_km against the round before, by 5-degree latitude band (central scenario, cells with eligible area; median signed, P95 of the absolute change)

| tech | band | cells | median change | P95 abs change |
|---|---|---|---|---|
| solar | +35 to +40 | 1942 | +1.0 % | 14.7 % |
| solar | +40 to +45 | 1471 | +0.4 % | 15.1 % |
| solar | all | 3413 | +0.8 % | 14.9 % |
| wind | +35 to +40 | 1957 | +0.7 % | 14.6 % |
| wind | +40 to +45 | 1375 | +0.6 % | 15.1 % |
| wind | all | 3332 | +0.7 % | 14.8 % |

## IND

### (a) road distance and (b) share of the potential beyond 100 km of a substation (eligible-area / potential weighted; before -> after)

| tech | scenario | median dist_road_km | eligible area > 30 km of a road | potential > 100 km of a substation | median dist_sub_km |
|---|---|---|---|---|---|
| solar | central | 2.64 -> 2.83 | 2.8 % -> 2.8 % | 1.2 % -> 1.1 % | 20.1 -> 20.0 |
| solar | restrictive | 3.23 -> 3.43 | 3.6 % -> 3.7 % | 1.3 % -> 1.1 % | 20.8 -> 20.7 |
| solar | permissive | 2.23 -> 2.40 | 2.5 % -> 2.5 % | 1.4 % -> 1.2 % | 19.5 -> 19.5 |
| wind | central | 2.14 -> 2.33 | 0.8 % -> 0.8 % | 0.1 % -> 0.1 % | 18.1 -> 18.0 |
| wind | restrictive | 2.30 -> 2.49 | 1.0 % -> 1.0 % | 0.2 % -> 0.1 % | 18.2 -> 18.1 |
| wind | permissive | 1.95 -> 2.14 | 0.7 % -> 0.7 % | 0.2 % -> 0.1 % | 17.9 -> 17.9 |

### (c) PV, central scenario: share of the potential by thermal zone (zones above T7 count as T7; 0 = no PVCZ land point)

- before: T0: 0.2 %, T1: 1.1 %, T2: 0.5 %, T3: 0.0 %, T4: 0.0 %, T5: 0.2 %, T6: 13.0 %, T7: 85.0 %; **T7 or hotter: 85.0 %**
- after: T0: 0.2 %, T1: 1.1 %, T2: 0.5 %, T3: 0.0 %, T4: 0.0 %, T5: 0.2 %, T6: 13.0 %, T7: 85.0 %; **T7 or hotter: 85.0 %**

### (d) relative change of dist_sub_km against the round before, by 5-degree latitude band (central scenario, cells with eligible area; median signed, P95 of the absolute change)

| tech | band | cells | median change | P95 abs change |
|---|---|---|---|---|
| solar | +5 to +10 | 806 | +3.4 % | 9.0 % |
| solar | +10 to +15 | 7680 | +2.4 % | 7.8 % |
| solar | +15 to +20 | 18582 | +1.2 % | 7.2 % |
| solar | +20 to +25 | 33705 | -0.1 % | 6.7 % |
| solar | +25 to +30 | 24861 | -1.9 % | 8.8 % |
| solar | +30 to +35 | 7925 | -3.4 % | 13.1 % |
| solar | +35 to +40 | 135 | +1.4 % | 3.2 % |
| solar | all | 93694 | +0.1 % | 8.8 % |
| wind | +5 to +10 | 789 | +3.5 % | 9.3 % |
| wind | +10 to +15 | 6895 | +2.4 % | 8.0 % |
| wind | +15 to +20 | 17318 | +1.2 % | 7.2 % |
| wind | +20 to +25 | 29227 | -0.1 % | 6.8 % |
| wind | +25 to +30 | 19503 | -2.3 % | 8.9 % |
| wind | +30 to +35 | 2866 | -3.4 % | 12.6 % |
| wind | +35 to +40 | 2 | +2.3 % | 2.4 % |
| wind | all | 76600 | +0.2 % | 8.3 % |

## BRA

### (a) road distance and (b) share of the potential beyond 100 km of a substation (eligible-area / potential weighted; before -> after)

| tech | scenario | median dist_road_km | eligible area > 30 km of a road | potential > 100 km of a substation | median dist_sub_km |
|---|---|---|---|---|---|
| solar | central | 5.99 -> 6.28 | 5.2 % -> 5.4 % | 7.2 % -> 7.2 % | 38.2 -> 38.3 |
| solar | restrictive | 6.35 -> 6.64 | 6.0 % -> 6.2 % | 8.0 % -> 8.0 % | 39.5 -> 39.6 |
| solar | permissive | 5.65 -> 5.94 | 4.6 % -> 4.8 % | 6.3 % -> 6.4 % | 36.7 -> 36.7 |
| wind | central | 5.41 -> 5.63 | 3.8 % -> 3.9 % | 4.8 % -> 4.9 % | 32.1 -> 32.0 |
| wind | restrictive | 5.50 -> 5.77 | 3.9 % -> 4.0 % | 5.0 % -> 5.0 % | 33.0 -> 32.9 |
| wind | permissive | 5.36 -> 5.57 | 3.7 % -> 3.8 % | 4.8 % -> 4.8 % | 31.7 -> 31.6 |

### (c) PV, central scenario: share of the potential by thermal zone (zones above T7 count as T7; 0 = no PVCZ land point)

- before: T0: 0.2 %, T4: 0.2 %, T5: 4.0 %, T6: 44.6 %, T7: 50.9 %; **T7 or hotter: 50.9 %**
- after: T0: 0.2 %, T4: 0.2 %, T5: 4.0 %, T6: 44.6 %, T7: 50.9 %; **T7 or hotter: 50.9 %**

### (d) relative change of dist_sub_km against the round before, by 5-degree latitude band (central scenario, cells with eligible area; median signed, P95 of the absolute change)

| tech | band | cells | median change | P95 abs change |
|---|---|---|---|---|
| solar | -35 to -30 | 4118 | -5.2 % | 13.3 % |
| solar | -30 to -25 | 12186 | -4.2 % | 11.1 % |
| solar | -25 to -20 | 24524 | -1.9 % | 8.4 % |
| solar | -20 to -15 | 37185 | -0.7 % | 5.4 % |
| solar | -15 to -10 | 42731 | +0.3 % | 3.5 % |
| solar | -10 to -5 | 41730 | +1.0 % | 3.4 % |
| solar | -5 to +0 | 23997 | +1.5 % | 3.3 % |
| solar | +0 to +5 | 4040 | +1.5 % | 2.6 % |
| solar | all | 190511 | +0.5 % | 7.1 % |
| wind | -35 to -30 | 4059 | -5.2 % | 13.2 % |
| wind | -30 to -25 | 11627 | -4.2 % | 11.1 % |
| wind | -25 to -20 | 23600 | -1.9 % | 8.3 % |
| wind | -20 to -15 | 36121 | -0.7 % | 5.3 % |
| wind | -15 to -10 | 41616 | +0.3 % | 3.5 % |
| wind | -10 to -5 | 38509 | +1.0 % | 3.5 % |
| wind | -5 to +0 | 19385 | +1.5 % | 3.4 % |
| wind | +0 to +5 | 3361 | +1.4 % | 2.6 % |
| wind | all | 178278 | +0.4 % | 7.1 % |