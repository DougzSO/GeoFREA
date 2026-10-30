## Phases by country, temperature and class

| country | phase | temp | n | awake med (s) | awake max (s) | cpu med (s) | cpu/wall | peak MB | class |
|---|---|---|---|---|---|---|---|---|---|
| BRA | climate_forcing | always | 16 | 172 | 205 | 142 | 0.83 | 3,389 | cpu |
| BRA | climate_maps | always | 8 | 60 | 614 | 58 | 0.96 | 2,322 | cpu |
| BRA | data_acquisition | always | 9 | 437 | 647 | 324 | 0.70 | 831 | mixed |
| BRA | data_quality_audit | warm | 8 | 523 | 6,563 | 368 | 0.77 | 4,027 | cpu |
| BRA | external_inputs | always | 3 | 0 | 0 | 0 | 0.25 | 253 | negligible |
| BRA | grid_alignment | cold | 2 | 18,840 | 18,840 | 22,081 | 1.17 | - | cpu |
| BRA | grid_alignment | warm | 6 | 36 | 129 | 30 | 0.83 | 436 | cpu |
| BRA | hazard_context | always | 12 | 187 | 297 | 148 | 0.83 | 3,182 | cpu |
| BRA | land_eligibility | always | 18 | 616 | 4,134 | 540 | 0.90 | 4,860 | cpu |
| BRA | overview | always | 10 | 206 | 247 | 182 | 0.89 | 3,332 | cpu |
| BRA | potential_maps | always | 15 | 146 | 1,258 | 110 | 0.95 | 1,613 | cpu |
| BRA | siting_layers | always | 7 | 57 | 62 | 29 | 0.52 | 522 | mixed |
| BRA | technical_potential | always | 12 | 672 | 1,293 | 630 | 0.95 | 2,269 | cpu |
| IND | climate_forcing | always | 12 | 132 | 153 | 111 | 0.85 | 1,815 | cpu |
| IND | climate_maps | always | 9 | 44 | 678 | 43 | 0.98 | 1,590 | cpu |
| IND | data_acquisition | always | 11 | 542 | 2,382 | 437 | 0.79 | 1,152 | cpu |
| IND | data_quality_audit | warm | 11 | 473 | 4,334 | 428 | 0.90 | 3,002 | cpu |
| IND | external_inputs | always | 4 | 0 | 1 | 0 | 0.23 | 253 | negligible |
| IND | grid_alignment | cold | 4 | 9,678 | 9,922 | 12,260 | 1.24 | 3,889 | cpu |
| IND | grid_alignment | warm | 4 | 67 | 75 | 60 | 0.86 | 408 | cpu |
| IND | hazard_context | always | 8 | 99 | 144 | 83 | 0.85 | 2,051 | cpu |
| IND | land_eligibility | always | 12 | 232 | 3,437 | 202 | 0.93 | 2,893 | cpu |
| IND | overview | always | 9 | 133 | 273 | 122 | 0.90 | 1,912 | cpu |
| IND | potential_maps | always | 18 | 137 | 2,634 | 134 | 0.92 | 1,096 | cpu |
| IND | siting_layers | always | 6 | 26 | 29 | 13 | 0.50 | 634 | mixed |
| IND | technical_potential | always | 15 | 233 | 2,445 | 221 | 0.96 | 1,230 | cpu |
| PRT | climate_forcing | always | 15 | 98 | 226 | 89 | 0.91 | 365 | cpu |
| PRT | climate_maps | always | 12 | 26 | 291 | 25 | 0.97 | 701 | cpu |
| PRT | data_acquisition | always | 13 | 38 | 168 | 14 | 0.37 | 338 | io_or_wait |
| PRT | data_quality_audit | warm | 16 | 58 | 404 | 51 | 0.87 | 1,037 | cpu |
| PRT | external_inputs | always | 5 | 0 | 1 | 0 | 0.20 | 340 | negligible |
| PRT | grid_alignment | cold | 5 | 294 | 648 | 306 | 0.87 | 2,292 | cpu |
| PRT | grid_alignment | warm | 8 | 12 | 25 | 9 | 0.76 | 332 | cpu |
| PRT | hazard_context | always | 12 | 30 | 35 | 28 | 0.94 | 928 | cpu |
| PRT | land_eligibility | always | 17 | 20 | 46 | 17 | 0.78 | 688 | cpu |
| PRT | overview | always | 14 | 65 | 90 | 62 | 0.94 | 923 | cpu |
| PRT | potential_maps | always | 24 | 57 | 462 | 51 | 0.92 | 786 | cpu |
| PRT | siting_layers | always | 10 | 3 | 3 | 1 | 0.34 | 570 | negligible |
| PRT | technical_potential | always | 22 | 14 | 210 | 13 | 0.91 | 659 | cpu |

## The 60 steps with the largest wall time

| country | phase | step | temp | n | awake med (s) | awake max (s) | class (inherited from phase) |
|---|---|---|---|---|---|---|---|
| BRA | grid_alignment | slope_counts | cold | 2 | 4,780 | 4,883 | cpu |
| BRA | grid_alignment | elevation | cold | 2 | 4,312 | 4,385 | cpu |
| BRA | grid_alignment | rivers | cold | 2 | 3,141 | 3,525 | cpu |
| BRA | data_quality_audit | land_cover | always | 8 | 64 | 3,469 | cpu |
| BRA | grid_alignment | land_cover | cold | 2 | 3,063 | 3,065 | cpu |
| IND | grid_alignment | slope_counts | cold | 2 | 2,389 | 2,472 | cpu |
| IND | grid_alignment | elevation | cold | 3 | 2,305 | 2,435 | cpu |
| IND | data_quality_audit | protected | always | 11 | 5 | 2,208 | cpu |
| BRA | grid_alignment | population | cold | 2 | 1,842 | 2,022 | cpu |
| IND | grid_alignment | land_cover | cold | 3 | 1,910 | 1,938 | cpu |
| IND | grid_alignment | roads | cold | 3 | 1,607 | 1,644 | cpu |
| BRA | data_quality_audit | rivers | always | 8 | 21 | 1,275 | cpu |
| IND | data_quality_audit | roads | always | 11 | 14 | 1,249 | cpu |
| BRA | grid_alignment | roads | cold | 2 | 1,120 | 1,178 | cpu |
| BRA | data_quality_audit | roads | always | 8 | 14 | 1,028 | cpu |
| IND | grid_alignment | rivers | cold | 3 | 610 | 879 | cpu |
| IND | grid_alignment | population | cold | 3 | 609 | 618 | cpu |
| IND | data_quality_audit | rivers | always | 11 | 8 | 495 | cpu |
| BRA | data_quality_audit | population | always | 8 | 122 | 323 | cpu |
| PRT | grid_alignment | roads | cold | 5 | 73 | 208 | cpu |
| PRT | data_quality_audit | land_cover | always | 16 | 4 | 170 | cpu |
| BRA | data_quality_audit | lakes | always | 8 | 2 | 167 | cpu |
| PRT | data_quality_audit | roads | always | 16 | 4 | 144 | cpu |
| PRT | grid_alignment | elevation | cold | 5 | 85 | 129 | cpu |
| BRA | data_quality_audit | protected | always | 8 | 22 | 116 | cpu |
| IND | data_quality_audit | population | always | 11 | 76 | 102 | cpu |
| PRT | grid_alignment | slope_counts | cold | 3 | 83 | 102 | cpu |
| PRT | grid_alignment | land_cover | cold | 4 | 58 | 100 | cpu |
| BRA | grid_alignment | lakes | cold | 2 | 78 | 82 | cpu |
| BRA | grid_alignment | land_cover | warm | 6 | 0 | 67 | cpu |
| IND | grid_alignment | lakes | cold | 3 | 50 | 64 | cpu |
| IND | data_quality_audit | lakes | always | 11 | 21 | 64 | cpu |
| PRT | grid_alignment | land_cover | always | 1 | 62 | 62 | cpu |
| BRA | data_quality_audit | weibull_a | always | 8 | 32 | 58 | cpu |
| BRA | data_quality_audit | wind | always | 8 | 32 | 55 | cpu |
| BRA | data_quality_audit | weibull_k | always | 8 | 30 | 49 | cpu |
| IND | data_quality_audit | wind | always | 11 | 27 | 48 | cpu |
| BRA | data_quality_audit | air_density | always | 8 | 28 | 46 | cpu |
| IND | data_quality_audit | land_cover | always | 11 | 38 | 46 | cpu |
| IND | data_quality_audit | air_density | always | 11 | 25 | 42 | cpu |
| IND | data_quality_audit | weibull_k | always | 11 | 26 | 41 | cpu |
| IND | data_quality_audit | weibull_a | always | 11 | 25 | 38 | cpu |
| BRA | grid_alignment | population | warm | 6 | 0 | 38 | cpu |
| IND | grid_alignment | grid_distance | cold | 3 | 29 | 36 | cpu |
| PRT | grid_alignment | population | cold | 5 | 18 | 35 | cpu |
| BRA | grid_alignment | grid_distance | cold | 2 | 25 | 32 | cpu |
| IND | data_quality_audit | borders | always | 11 | 24 | 29 | cpu |
| IND | data_quality_audit | admin1 | always | 11 | 23 | 24 | cpu |
| IND | data_quality_audit | solar | always | 11 | 11 | 24 | cpu |
| BRA | data_quality_audit | elevation | always | 4 | 9 | 22 | mixed |
| PRT | grid_alignment | rivers | cold | 5 | 9 | 19 | cpu |
| BRA | grid_alignment | wind_wind_speed_100m | cold | 2 | 17 | 18 | cpu |
| PRT | grid_alignment | roads | warm | 8 | 0 | 18 | cpu |
| BRA | grid_alignment | wind_air_density_100m | cold | 2 | 16 | 17 | cpu |
| BRA | grid_alignment | wind_wind_speed_150m | cold | 2 | 16 | 17 | cpu |
| BRA | grid_alignment | wind_weibull_k_150m | cold | 2 | 16 | 17 | cpu |
| BRA | grid_alignment | wind_weibull_k_200m | cold | 2 | 16 | 17 | cpu |
| IND | grid_alignment | population | warm | 5 | 0 | 16 | cpu |
| BRA | grid_alignment | wind_weibull_a_150m | cold | 2 | 16 | 16 | cpu |
| BRA | grid_alignment | wind_wind_speed_200m | cold | 2 | 16 | 16 | cpu |

## Executions classed suspended (wall time not a cost)

| country | date | phase | wall (s) | slept (s) | cpu (s) | cpu/wall |
|---|---|---|---|---|---|---|
| PRT | 2026-10-19 15:06 | siting_layers | 6 | 0 | 1 | 0.18 |
| PRT | 2026-10-19 15:06 | land_eligibility | 129 | 0 | 34 | 0.27 |
| BRA | 2026-10-21 22:07 | grid_alignment | 42,176 | 23,469 | 21,048 | 0.50 |
| BRA | 2026-10-27 20:36 | technical_potential | 45,516 | 34,795 | 10,442 | 0.23 |
| IND | 2026-10-28 22:12 | grid_alignment | 31,913 | 25,035 | 9,967 | 0.31 |
