# Group 6: change of the eligible area, PRT

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 15,691.9 | 7,113.4 | -54.67 | -1,890.6 | 1,165.0 | -13,638.9 | 6,941.5 | 0.0 | -1,129.5 | -25.9 |
| solar | central | 21,163.7 | 12,261.6 | -42.06 | -1,854.6 | 1,683.3 | -12,567.6 | 4,557.7 | 0.0 | -694.5 | -26.4 |
| solar | permissive | 24,045.4 | 21,479.6 | -10.67 | -1,416.6 | 2,299.7 | -6,133.6 | 2,942.8 | 0.0 | -258.1 | 0.0 |
| wind | restrictive | 17,548.4 | 20,300.3 | 15.68 | -3,266.7 | 2,013.0 | -5,573.7 | 11,994.2 | 0.0 | -913.1 | -1,501.7 |
| wind | central | 28,127.1 | 30,451.7 | 8.26 | -4,179.5 | 2,963.0 | -4,080.2 | 8,022.8 | 0.0 | 155.8 | -557.3 |
| wind | permissive | 35,231.5 | 36,066.6 | 2.37 | -3,885.5 | 3,526.6 | -4,467.5 | 4,512.8 | 0.0 | 1,148.7 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, PRT

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 10/30 m (width < 10 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 10 m | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30 m | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 10/30 m (width < 10 m) | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 10 m | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
