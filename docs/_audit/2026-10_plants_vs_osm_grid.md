# Existing power plants against the OSM grid layer — is a large `dist_grid_km` a mapping gap? (L-018, OQ-041)

## Update 2026-10-07: repeated with GEM (GPPD replaced, D-F1-026)

The first run (below, 2026-10-06) used WRI GPPD, whose records stop at 2020. It was repeated with the Global Energy Monitor
Global Integrated Power Tracker (snapshot 2026-08-09, operating units of every fuel, >= 1 MW, inside the mainland polygon),
which holds 3 to 13 times more solar and wind units. `scripts/qc_plants_vs_grid.py` now reads GEM. **The reading does not change.**

| Country | Plants (GEM) | Median km | > 50 km (% of plants) | > 50 km (% of MW) | > 100 km (% of plants) | Reading |
|---|---:|---:|---:|---:|---:|---|
| PRT | 595 | 1.0 | 0.0 | 0.0 | 0.0 | OSM grid complete (every plant within 14 km). |
| BRA | 6,042 | 1.1 | 0.4 | 0.0 | 0.0 | Consistent with the real network; the few far units are small solar plants (one 2 MW unit at 430 km). |
| IND | 5,727 | 2.1 | 12.7 | 14.3 | 4.8 | **Incomplete OSM grid**: 24% of wind, 11% of solar and 41% of hydro units sit more than 50 km from a mapped feature. Same pattern as with GPPD (15.7% of plants, 14.7% of MW). |

Caveat: GEM locations carry an accuracy flag (`Location accuracy`) that this check does not use, so part of the far solar and
wind units may be mislocated rather than disconnected; the hydro and nuclear points show the same gap in IND. Output as printed
by the script (GEM):

```
Plants with capacity >= 1.0 MW inside the mainland, distance to the OSM grid (km, aligned F2a raster)

## PRT: 600 plants, 595 inside the mainland grid, 20757 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 595 | 1.0 | 2.8 | 13.7 | 3.4 | 0.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| bioenergy | 12 | 0.0 | 0.9 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hydropower | 35 | 0.0 | 1.0 | 6.6 | 2.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| oil/gas | 19 | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| utility-scale solar | 168 | 1.0 | 3.9 | 9.6 | 7.7 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| wind | 361 | 1.0 | 2.8 | 13.7 | 1.7 | 0.3 | 0.0 | 0.0 | 0.0 | 0.0 |

farthest 5: wind 3 MW at 14 km; utility-scale solar 14 MW at 10 km; utility-scale solar 2 MW at 9 km; utility-scale solar 1 MW at 9 km; utility-scale solar 2 MW at 9 km 

## IND: 5738 plants, 5727 inside the mainland grid, 475720 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 5727 | 2.1 | 63.7 | 284.6 | 36.9 | 29.5 | 20.5 | 12.7 | 4.8 | 14.3 |
| bioenergy | 136 | 1.5 | 29.7 | 112.1 | 36.0 | 23.5 | 14.7 | 5.1 | 1.5 | 4.1 |
| coal | 858 | 0.0 | 22.6 | 165.7 | 20.3 | 16.1 | 9.7 | 5.1 | 2.3 | 5.5 |
| hydropower | 212 | 15.7 | 162.2 | 239.0 | 57.1 | 53.3 | 47.2 | 41.0 | 28.8 | 53.3 |
| nuclear | 19 | 0.0 | 88.6 | 88.6 | 31.6 | 31.6 | 31.6 | 21.1 | 0.0 | 14.1 |
| oil/gas | 99 | 0.0 | 29.9 | 219.1 | 21.2 | 13.1 | 11.1 | 9.1 | 7.1 | 3.6 |
| utility-scale solar | 3724 | 2.4 | 54.7 | 284.6 | 38.6 | 30.1 | 19.8 | 11.0 | 2.9 | 19.7 |
| wind | 679 | 3.9 | 106.6 | 169.9 | 44.6 | 39.6 | 32.1 | 24.0 | 10.9 | 19.9 |

farthest 5: utility-scale solar 1 MW at 285 km; utility-scale solar 1 MW at 249 km; utility-scale solar 3 MW at 244 km; hydropower 180 MW at 239 km; utility-scale solar 2 MW at 238 km 

## BRA: 6052 plants, 6042 inside the mainland grid, 203697 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 6042 | 1.1 | 7.6 | 430.3 | 14.7 | 5.3 | 1.3 | 0.4 | 0.0 | 0.0 |
| bioenergy | 621 | 1.1 | 8.7 | 75.1 | 18.2 | 8.7 | 1.1 | 0.3 | 0.0 | 0.1 |
| coal | 13 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| hydropower | 193 | 0.0 | 1.5 | 14.4 | 3.1 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| oil/gas | 132 | 0.0 | 1.1 | 4.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| utility-scale solar | 3946 | 1.5 | 8.7 | 430.3 | 15.9 | 5.9 | 1.9 | 0.5 | 0.1 | 0.2 |
| wind | 1135 | 1.5 | 5.6 | 20.8 | 12.5 | 2.6 | 0.0 | 0.0 | 0.0 | 0.0 |

farthest 5: utility-scale solar 2 MW at 430 km; utility-scale solar 4 MW at 172 km; utility-scale solar 3 MW at 87 km; utility-scale solar 1 MW at 76 km; bioenergy 3 MW at 75 km
```

---

## Original run 2026-10-06 (WRI GPPD)

Date: 2026-10-06. Script: `scripts/qc_plants_vs_grid.py` (reads the aligned F2a grid-distance rasters and the WRI GPPD
plant list; run with `GEOFREA_DATA_DIR` set). Question raised by the distance QC in `docs/phases/F2a_grid_alignment.md`
D-F2a-011: 23% of BRA and 9% of IND lie more than 100 km from the mapped grid. Existing plants are connected to the real
grid, so the distance from each plant (>= 1 MW, inside the mainland) to the OSM layer says where the layer is incomplete.

## Result

| Country | Plants | Median km | > 50 km (% of plants) | > 50 km (% of MW) | > 100 km (% of plants) | Reading |
|---|---:|---:|---:|---:|---:|---|
| PRT | 434 | 1.0 | 0.0 | 0.0 | 0.0 | OSM grid is complete (every plant within 14 km). |
| BRA | 2,342 | 1.1 | 1.7 | 0.1 | 1.2 | Consistent with the real network: the far plants are small oil units (isolated Amazon systems), 99.9% of capacity within 50 km. The 23% of land beyond 100 km is mostly real absence of grid (Amazon, Pantanal), not a mapping gap. |
| IND | 1,564 | 3.0 | 15.7 | 14.7 | 6.1 | **Incomplete OSM grid**: 22% of wind, 13% of solar and 38% of hydro plants (by count) sit more than 50 km from a mapped feature, although they are connected. Distances in IND are overstated, most in the Himalaya and the south-west. |

By technology (share of plants beyond 50 km): IND wind 22.2%, solar 12.6%, hydro 37.6% (25.4% beyond 100 km), coal 9.5%;
BRA wind 0.0%, solar 0.0%, hydro 0.1%, oil 5.0%; PRT 0.0% everywhere.

Full tables as printed by the script:

```
Plants with capacity >= 1.0 MW inside the mainland, distance to the OSM grid (km, aligned F2a raster)

## PRT: 469 plants, 434 inside the mainland grid, 14555 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 434 | 1.0 | 3.5 | 13.7 | 5.8 | 1.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| Biomass | 19 | 0.0 | 1.0 | 1.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hydro | 112 | 1.0 | 5.2 | 13.7 | 10.7 | 3.6 | 0.0 | 0.0 | 0.0 | 0.0 |
| Solar | 68 | 1.0 | 5.3 | 8.8 | 10.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Waste | 22 | 1.0 | 1.9 | 9.8 | 4.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Wind | 207 | 1.0 | 2.8 | 13.7 | 2.4 | 0.5 | 0.0 | 0.0 | 0.0 | 0.0 |

farthest 5: Hydro 1 MW at 14 km; Wind 3 MW at 14 km; Hydro 1 MW at 14 km; Hydro 4 MW at 13 km; Hydro 3 MW at 11 km 

## IND: 1589 plants, 1564 inside the mainland grid, 307942 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 1564 | 3.0 | 69.5 | 239.0 | 40.7 | 34.0 | 24.0 | 15.7 | 6.1 | 14.7 |
| Biomass | 50 | 1.3 | 32.6 | 87.4 | 40.0 | 34.0 | 12.0 | 8.0 | 0.0 | 9.2 |
| Coal | 253 | 1.1 | 49.4 | 153.8 | 29.6 | 24.1 | 16.6 | 9.5 | 3.2 | 7.8 |
| Gas | 67 | 0.0 | 40.2 | 219.1 | 25.4 | 23.9 | 13.4 | 7.5 | 6.0 | 4.4 |
| Hydro | 213 | 6.8 | 154.8 | 239.0 | 53.5 | 48.4 | 42.7 | 37.6 | 25.4 | 52.4 |
| Oil | 16 | 3.3 | 24.2 | 25.5 | 43.8 | 37.5 | 6.2 | 0.0 | 0.0 | 0.0 |
| Solar | 850 | 3.4 | 57.9 | 162.4 | 41.8 | 34.0 | 22.5 | 12.6 | 1.9 | 17.9 |
| Wind | 108 | 3.1 | 110.2 | 147.4 | 43.5 | 35.2 | 30.6 | 22.2 | 12.0 | 25.3 |

farthest 5: Hydro 180 MW at 239 km; Hydro 36 MW at 230 km; Hydro 4 MW at 225 km; Gas 291 MW at 219 km; Hydro 540 MW at 213 km 

## BRA: 2360 plants, 2342 inside the mainland grid, 139955 MW
| group | n | median_km | p90_km | max_km | >5km_%n | >10km_%n | >25km_%n | >50km_%n | >100km_%n | >50km_%MW |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 2342 | 1.1 | 7.7 | 669.2 | 14.5 | 7.4 | 3.0 | 1.7 | 1.2 | 0.1 |
| Biomass | 444 | 1.1 | 8.5 | 52.6 | 18.2 | 7.9 | 0.9 | 0.2 | 0.0 | 0.0 |
| Coal | 19 | 1.1 | 2.2 | 4.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Gas | 116 | 1.1 | 4.7 | 164.4 | 10.3 | 8.6 | 6.0 | 6.0 | 2.6 | 0.2 |
| Hydro | 700 | 1.1 | 9.3 | 53.5 | 20.4 | 9.4 | 2.6 | 0.1 | 0.0 | 0.0 |
| Oil | 621 | 1.1 | 6.9 | 669.2 | 12.1 | 9.0 | 6.6 | 5.0 | 3.9 | 2.2 |
| Solar | 24 | 1.1 | 9.1 | 19.7 | 12.5 | 12.5 | 0.0 | 0.0 | 0.0 | 0.0 |
| Waste | 12 | 1.1 | 2.2 | 7.9 | 8.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Wind | 403 | 1.1 | 3.9 | 14.9 | 6.0 | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 |

farthest 5: Oil 5 MW at 669 km; Oil 3 MW at 615 km; Oil 5 MW at 593 km; Oil 2 MW at 590 km; Oil 2 MW at 578 km
```

## Caveats

- GPPD coordinates are reported by the plant owners and some are approximate (a few km), so a distance of 5-10 km is not
  evidence of a gap; the 50 km and 100 km columns are what carries the conclusion.
- "Most in the Himalaya and the south-west" for IND is my reading of where the far plants are (hydro in the mountains, wind in
  the south-west), not a mapped result; this document does not include a map.
- Hydro plants in a mountain valley can lie far from a mapped feature and still connect through a long line; this check
  shows the OSM layer is thin there, not that the line is absent.
- The test measures consistency of the layer with known connected assets. It cannot say how much capacity a mapped line can
  absorb (voltage, L-018), and it does not give a corrected distance.

## What it changes

- L-018 now states the measured coverage per country (PRT complete, BRA consistent, IND incomplete).
- OQ-041 gets a concrete first step: for IND the distance to the OSM grid cannot be billed as is without a coverage
  correction or a second source (for example the national transmission map, a Stage R item), whereas PRT and BRA can use the
  OSM distance with the L-018 caveat.
- No distance value was altered and no cap or correction was introduced: the rasters keep the real geodesic distance
  (OQ-040). Correcting IND's distance needs a sourced dataset, not a guess.
