# Distance to the road D_road of the eligible area (COMMAND 86)

Central scenario, `dist_road_km` of the F3 candidates (eligible-area mean per 0.05 degree cell), each cell weighted by its eligible area. The road layer is the one
of the round of 2026-11-03 (F2a with `geospatial.road_classes`, F3 rerun in all three countries); the figures before it, made with every road class of the source,
were BRA 2.4 km median and 0.6% beyond 30 km. They size the road term that `road_cost_excluded` leaves out.

| Country | Technology | Cells | Eligible area (km2) | Median (km) | P90 (km) | Eligible area beyond 30 km |
|---|---|---|---|---|---|---|
| BRA | solar | 180058 | 1535068 | 5.6 | 20.5 | 4.2% |
| BRA | wind | 181306 | 2195664 | 5.3 | 19.3 | 3.6% |
| IND | solar | 57547 | 150665 | 3.0 | 15.3 | 4.0% |
| IND | wind | 61459 | 507102 | 2.2 | 8.1 | 0.7% |
| PRT | solar | 3449 | 21157 | 1.6 | 5.3 | 0.0% |
| PRT | wind | 3500 | 28122 | 1.6 | 5.2 | 0.0% |
