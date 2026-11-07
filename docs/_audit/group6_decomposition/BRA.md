# Group 6: change of the eligible area, BRA

Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.

| technology | scenario | area_old_km2 | area_new_km2 | change_pct | settlements_km2 | density_removed_km2 | slope_km2 | rivers_km2 | other_km2 | interaction_km2 | min_area_km2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | 1,067,836.8 | 929,546.7 | -12.95 | -25,454.5 | 12,055.2 | -717,007.6 | 834,529.7 | 0.0 | -241,858.2 | -554.7 |
| solar | central | 1,535,463.7 | 1,319,158.4 | -14.09 | -22,089.4 | 16,119.1 | -551,586.5 | 479,994.4 | 0.0 | -138,363.0 | -379.9 |
| solar | permissive | 1,767,652.6 | 1,793,549.2 | 1.47 | -14,331.4 | 19,561.8 | -194,114.5 | 286,329.1 | 0.0 | -71,548.5 | 0.0 |
| wind | restrictive | 1,437,315.0 | 2,242,028.3 | 55.99 | -45,331.3 | 21,468.8 | -223,514.3 | 1,486,194.3 | 0.0 | -372,603.3 | -61,500.8 |
| wind | central | 2,196,019.3 | 2,659,550.9 | 21.11 | -48,046.0 | 26,989.4 | -135,987.1 | 803,691.8 | 0.0 | -155,876.4 | -27,240.2 |
| wind | permissive | 2,626,760.7 | 2,842,440.8 | 8.21 | -40,791.0 | 29,766.1 | -147,126.2 | 435,690.0 | 0.0 | -61,858.7 | 0.0 |

## Limits of each criterion, old (before Group 6) and new, BRA

| technology | scenario | rivers_old | rivers_new | settlements_old | settlements_new | density_old | density_new | slope_old | slope_new | elevation_old | elevation_new | min_area_old | min_area_new |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 3 % (1.72 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 2.22 km2 |
| solar | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 5 % (2.86 deg) | no limit | no limit | cell >= 0.1 km2 | cluster >= 1.00 km2 |
| solar | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 0 m | 200 persons/km2 | not applied | 10 deg (17.6 %) | 10 % (5.71 deg) | no limit | no limit | cell >= 0.1 km2 | no floor |
| wind | restrictive | setback 1000 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.52, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 1000 m | 200 persons/km2 | not applied | 10.2 deg (18.0 %) | 10 % (5.71 deg) | 3000 m | 2000 m | cell >= 0.1 km2 | cluster >= 30.12 km2; pixel fraction >= 0.1 |
| wind | central | setback 500 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.5, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 800 m | 200 persons/km2 | not applied | 16.7 deg (30.0 %) | 20 % (11.31 deg) | 3000 m | 3000 m | cell >= 0.1 km2 | pixel fraction >= 0.1 |
| wind | permissive | setback 250 m; streams with Q >= 0 m3/s | W = 7.2 Q^0.48, buffer 30/50/100/200/500 m (width < 10/50/200/600 m) | none (density rule) | GHS-SMOD class >= 13, setback 500 m | 200 persons/km2 | not applied | 30 deg (57.7 %) | 30 % (16.70 deg) | 3000 m | no limit | cell >= 0.1 km2 | no floor |
