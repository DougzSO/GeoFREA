# Group 6: change of the eligible area, IND

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 108,171.6 | 75,895.1 | -29.84 | -89,052.9 | 73,636.8 | -55,321.3 | 61,700.5 | 0.0 | -21,493.6 | -1,746.0 |
| solar | central | 151,213.3 | 144,360.7 | -4.53 | -92,581.0 | 114,003.5 | -44,877.0 | 42,136.0 | 0.0 | -24,559.1 | -975.0 |
| solar | permissive | 172,822.6 | 253,893.9 | 46.91 | -63,155.8 | 158,562.8 | -19,495.6 | 33,457.2 | 0.0 | -28,297.3 | 0.0 |
| wind | restrictive | 354,785.9 | 356,541.2 | 0.49 | -366,545.2 | 303,092.0 | -38,303.4 | 253,961.8 | 0.0 | -68,570.0 | -81,879.9 |
| wind | central | 509,642.2 | 572,040.4 | 12.24 | -417,098.9 | 396,154.8 | -27,309.4 | 146,420.0 | 0.0 | -14,298.3 | -21,470.0 |
| wind | permissive | 599,422.3 | 823,084.7 | 37.31 | -382,692.7 | 471,244.3 | -56,664.9 | 99,433.9 | 0.0 | 92,341.8 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, IND

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 200 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 100 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 200 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 100 m | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
