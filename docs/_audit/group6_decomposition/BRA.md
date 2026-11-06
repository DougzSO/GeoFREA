# Group 6: change of the eligible area, BRA

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 1,067,836.8 | 694,056.3 | -35.00 | -19,409.4 | 9,192.2 | -1,024,299.8 | 636,339.1 | 0.0 | 24,785.8 | -388.4 |
| solar | central | 1,535,463.7 | 1,130,464.6 | -26.38 | -18,750.7 | 13,682.8 | -900,470.8 | 407,445.5 | 0.0 | 93,399.6 | -305.5 |
| solar | permissive | 1,767,652.6 | 1,717,530.5 | -2.84 | -13,502.5 | 18,430.5 | -386,935.9 | 269,770.1 | 0.0 | 62,115.7 | 0.0 |
| wind | restrictive | 1,437,315.0 | 2,150,819.0 | 49.64 | -42,470.6 | 20,113.9 | -432,093.6 | 1,392,404.6 | 0.0 | -160,396.3 | -64,054.0 |
| wind | central | 2,196,019.3 | 2,640,018.1 | 20.22 | -47,461.1 | 26,660.8 | -192,576.5 | 793,907.0 | 0.0 | -108,804.0 | -27,727.5 |
| wind | permissive | 2,626,760.7 | 2,836,253.7 | 7.98 | -40,660.2 | 29,670.6 | -164,074.3 | 434,292.2 | 0.0 | -49,735.2 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, BRA

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
