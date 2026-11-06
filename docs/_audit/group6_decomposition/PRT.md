# Group 6: change of the eligible area, PRT

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 15,691.9 | 4,354.6 | -72.25 | -1,549.1 | 954.6 | -15,592.2 | 5,687.8 | 0.0 | -815.2 | -23.1 |
| solar | central | 21,163.7 | 9,150.7 | -56.76 | -1,626.8 | 1,476.6 | -15,324.5 | 3,998.0 | 0.0 | -514.6 | -21.7 |
| solar | permissive | 24,045.4 | 19,528.5 | -18.78 | -1,344.9 | 2,183.2 | -8,139.8 | 2,793.7 | 0.0 | -9.1 | 0.0 |
| wind | restrictive | 17,548.4 | 18,275.7 | 4.14 | -3,091.4 | 1,905.0 | -7,296.2 | 11,350.4 | 0.0 | -450.2 | -1,690.2 |
| wind | central | 28,127.1 | 29,830.9 | 6.06 | -4,119.3 | 2,920.3 | -4,853.3 | 7,907.2 | 0.0 | 427.2 | -578.3 |
| wind | permissive | 35,231.5 | 35,812.4 | 1.65 | -3,863.4 | 3,506.6 | -4,840.4 | 4,487.1 | 0.0 | 1,291.0 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, PRT

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 10/30 m (width < 10 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 10 m | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 10/30 m (width < 10 m) | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 10 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
