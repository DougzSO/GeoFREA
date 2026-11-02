# Distance to the road D_road of the eligible area (COMMAND 86)

Central scenario, `dist_road_km` of the F3 candidates (eligible-area mean per 0.05 degree cell), each cell weighted by its eligible area. The road layer is the one
made before Group 3 (all road classes of the source); the next F2a round rebuilds it with the primary and secondary classes, so the figures are to be recomputed
(`python scripts/report_road_distance.py`) after that round. They size the road term that `road_cost_excluded` leaves out.

| Country | Technology | Cells | Eligible area (km2) | Median (km) | P90 (km) | Eligible area beyond 30 km |
|---|---|---|---|---|---|---|
| BRA | solar | 180058 | 1535068 | 2.4 | 9.0 | 0.6% |
| BRA | wind | 181306 | 2195664 | 2.3 | 8.5 | 0.5% |
| IND | solar | 57549 | 150673 | 1.0 | 4.2 | 0.8% |
| IND | wind | 61464 | 507185 | 0.9 | 2.6 | 0.2% |
| PRT | solar | 3449 | 21157 | 0.8 | 2.5 | 0.0% |
| PRT | wind | 3500 | 28122 | 0.8 | 2.4 | 0.0% |
