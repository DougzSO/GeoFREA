# Group 6: change of the eligible area, IND

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 108,171.6 | 94,038.9 | -13.07 | -101,012.4 | 83,526.0 | -33,324.2 | 69,986.7 | 0.0 | -31,319.2 | -1,989.6 |
| solar | central | 151,213.3 | 161,224.5 | 6.62 | -98,839.4 | 121,710.0 | -26,163.7 | 44,984.4 | 0.0 | -30,642.2 | -1,037.9 |
| solar | permissive | 172,822.6 | 260,840.4 | 50.93 | -64,420.2 | 161,737.3 | -11,567.7 | 34,127.0 | 0.0 | -31,858.7 | 0.0 |
| wind | restrictive | 354,785.9 | 362,215.2 | 2.09 | -373,733.4 | 309,035.7 | -23,160.7 | 258,942.2 | 0.0 | -80,688.8 | -82,965.7 |
| wind | central | 509,642.2 | 573,071.6 | 12.45 | -418,772.1 | 397,744.1 | -23,069.2 | 147,007.4 | 0.0 | -17,940.3 | -21,540.3 |
| wind | permissive | 599,422.3 | 823,558.7 | 37.39 | -383,221.8 | 471,895.8 | -54,967.8 | 99,571.4 | 0.0 | 90,858.8 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, IND

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 200 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 100 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 200 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 100 m | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
