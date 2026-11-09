# Distance to the nearest substation: error of the isotropic scale (COMMAND 111)

Date: 2026-11-09. Read-only audit: no layer was run, no code, configuration or fixture was changed, nothing was committed. Data: the outputs of round 9c2dc3c8 (PRT, IND, BRA). The measurement scripts live outside the repository.

**Short answer.** The layer `poi` (and `grid`, `roads`, `rivers`, which share the function) converts a pixel-space Euclidean distance to kilometres with **one isotropic scale for the whole grid**, taken at the latitude of the centre of the grid. Away from that latitude, and in any country where a degree of longitude is much shorter than a degree of latitude, the distance is wrong by a factor that depends on the direction to the substation. Measured on 20,000 sampled eligible pixels per country, scenario and technology, the 95th percentile of the relative error is **14.5 % in PRT, 8.3 % in IND and 10.4 % in BRA** (central, solar), against a half-range of 4 % in the choice of the tortuosity L = 1.25 D (U[1.2, 1.3]). The share of pixels with an error above 5 % is about **72 % in PRT, 12 % in IND and 6 % in BRA**. Classification: **defect (b)**, not a defect of the fixture or of an expectation; the correction is an open decision of the author (section 7).

## 1. The method and where the scale is defined

Code: `calculate_wgs84_isotropic_distance` in `src/geofrea/grid_alignment/vector_alignment.py` (line 143), called by `rasterize_linear_distance` (line 290) and by `align_rivers` (line 379). The POI layer is `build_poi` in `grid_alignment/layers.py` (line 294), which burns the eligible substations (`select_poi`, `grid_alignment/poi.py`, M-F2a-09) into the pixels of the grid and calls `rasterize_linear_distance`.

1. The substations are points (a substation polygon is reduced to its representative point). Each point is burnt into the one pixel that contains it (`rasterize` with `all_touched=True` after `simplify`), and the mask is intersected with the country mask: a substation whose pixel lies outside the country is not burnt.
2. `dist_pixels = scipy.ndimage.distance_transform_edt(mask)`: Euclidean distance, in pixels, to the nearest burnt pixel (no `sampling` argument: the two axes weigh the same).
3. Scale, defined **once for the whole grid** (not per strip or block): `lat_center = transform.f + transform.e * (height / 2)`, the latitude of the middle row of the grid; `(lat_km_deg, lon_km_deg) = wgs84_km_per_degree(lat_center)` (Bowring series, `core/geodesy.py`, line 27); `px_scale_km = sqrt(|a| * lon_km_deg * |e| * lat_km_deg)`, the geometric mean of the kilometres per pixel along the two axes.
4. Result: `dist_km = dist_pixels * px_scale_km` (float32). The raster is stored uncapped; the flag `distance_capped` is a separate raster (M-F2a-03).

The method is the same for the three countries; only `lat_center` differs: PRT 39.575 degrees (grid 36.95 to 42.20), IND 21.800 (8.05 to 35.55), BRA -14.225 (-33.75 to 5.30); pixel 0.01 degree in all of them. Two consequences follow from the formula itself and do not depend on any data: (i) the scale is exact only at `lat_center`; (ii) even at `lat_center` the pixel is not square in kilometres, so the isotropic scale overstates east-west distances and understates north-south ones by about half the difference between the two scales. The docstring of `rasterize_linear_distance` calls the result a "geodesic distance-to-feature raster"; it is a one-scale approximation. The Bowring formula itself is accurate (it differs from the exact ellipsoid by 4e-7 or less at the centre latitudes).

The same function builds the layers `grid`, `poi`, `poi_sensitivity` (IND), `roads` and `rivers`. Not audited here: what consumes `rivers` (the river corridor of F3 uses its own anisotropic distance with `sampling=(dy_m, dx_m)` in `land_eligibility/fractions.py`).

## 2. Analytic error of the single scale (no layer run)

Error of the layer against the local WGS84 scale, in the two extreme directions (kilometres per degree computed on the ellipsoid at the pixel latitude): east-west `s_c / k_lon(phi) - 1` and north-south `s_c / k_lat(phi) - 1`, with `s_c` the scale of the layer at the latitude of the centre of the grid (kilometres per degree: PRT 97.67, IND 107.00, BRA 109.28). Any other direction lies between the two. 5-degree bands of the extent of each grid; the "range" is over the band edges and the two directions.

| Country | Band (deg) | Pixel latitude range in the grid | E-W error | N-S error | Range over band edges |
|---|---|---|---|---|---|
| PRT | 35 to 40 | 36.95 to 40.00 | +11.9 % | -12.0 % | -12.0 % to +14.4 % |
| PRT | 40 to 45 | 40.00 to 42.20 | +16.3 % | -12.1 % | -12.1 % to +18.3 % |
| IND | 5 to 10 | 8.05 to 10.00 | -2.7 % | -3.3 % | -3.3 % to -2.4 % |
| IND | 10 to 15 | 10.00 to 15.00 | -1.6 % | -3.3 % | -3.3 % to -0.5 % |
| IND | 15 to 20 | 15.00 to 20.00 | +0.8 % | -3.3 % | -3.3 % to +2.3 % |
| IND | 20 to 25 | 20.00 to 25.00 | +4.0 % | -3.4 % | -3.4 % to +6.0 % |
| IND | 25 to 30 | 25.00 to 30.00 | +8.3 % | -3.4 % | -3.5 % to +10.9 % |
| IND | 30 to 35 | 30.00 to 35.00 | +13.9 % | -3.5 % | -3.5 % to +17.2 % |
| IND | 35 to 40 | 35.00 to 35.55 | +17.6 % | -3.6 % | -3.6 % to +18.0 % |
| BRA | -35 to -30 | -33.75 to -30.00 | +15.5 % | -1.5 % | -1.5 % to +17.9 % |
| BRA | -30 to -25 | -30.00 to -25.00 | +10.6 % | -1.4 % | -1.4 % to +13.3 % |
| BRA | -25 to -20 | -25.00 to -20.00 | +6.2 % | -1.3 % | -1.4 % to +8.2 % |
| BRA | -20 to -15 | -20.00 to -15.00 | +2.9 % | -1.3 % | -1.3 % to +4.4 % |
| BRA | -15 to -10 | -15.00 to -10.00 | +0.5 % | -1.2 % | -1.2 % to +1.6 % |
| BRA | -10 to -5 | -10.00 to -5.00 | -1.0 % | -1.2 % | -1.5 % to -0.3 % |
| BRA | -5 to 0 | -5.00 to 0.00 | -1.7 % | -1.2 % | -1.8 % to -1.2 % |
| BRA | 0 to 5 | 0.00 to 5.00 | -1.7 % | -1.2 % | -1.8 % to -1.2 % |
| BRA | 5 to 10 | 5.00 to 5.30 | -1.4 % | -1.2 % | -1.5 % to -1.2 % |

Reading: in PRT (latitude 37 to 42) a degree of longitude is 15 % shorter than a degree of latitude at the centre, so the layer is about +12 % to +16 % too long east-west and -12 % too short north-south everywhere in the country. In IND the north-south error is a constant -3 % and the east-west error grows from -3 % in the south to +18 % at the northern edge. In BRA the north-south error is -1.2 to -1.5 % and the east-west error reaches +15 % at -33 degrees. The error is **systematic and directional**, not noise.

## 3. Measurement on real data (round 9c2dc3c8)

Sources read: `grid_alignment/artifacts/<ISO>_poi_aligned.tif` (the layer, kilometres), `land_eligibility/artifacts/eligible_fraction_<tech>[__restrictive|__permissive].tif` (the eligible pixels of each scenario), `grid_alignment/artifacts/poi_counts.json`, and the substation vector (`raw/infrastructure_grid/<ISO>/<ISO>_grid_osm.geojson` plus `external/osm_substations/<ISO>_substations_osm.geojson`, merged and selected by `select_poi` at the threshold of config: PRT 150 kV, IND 220 kV, BRA 138 kV).

**Check that the vector is the one the layer used.** `select_poi` on these files returns 313 (PRT), 3239 (IND) and 3892 (BRA) eligible substations, equal to `eligible` in `poi_counts.json` (313, 3239, 3892). Of them 312, 3237 and 3888 fall on a pixel of distance 0 of the layer (the rest were not burnt, probably because they lie outside the country mask). The layer has 280, 3131 and 3645 substation pixels (several substations can share a pixel).

**Sample.** 20,000 pixels per country, scenario (central, restrictive, permissive) and technology (solar, wind), drawn at random (seed 20261109) from the pixels with an eligible fraction above 0 and a layer distance above 0, stratified in 5-degree latitude bands with equal allocation per band (a band with fewer pixels gives its share to the others); overall fractions are weighted by the number of eligible pixels of each band, so they describe the whole eligible area, not the sample.

**Reference distances.** For each sampled pixel centre, the nearest substation is found by nearest neighbour in ECEF coordinates (`scipy.spatial.cKDTree`), and the distance is the WGS84 geodesic (`pyproj.Geod`) to that point. Two calculations: (A) the substations are the **pixel centres of the layer's own substation pixels**: this isolates the error of the scale (same positions as the layer, only the metric differs); (B) the substations are the **vector points** that fall on a burnt pixel: total error, including the quantisation of each substation to its pixel (up to half a pixel diagonal, 0.78 km). Using all vector points in the extent instead changes the fractions in the third decimal at most (kept in the working files).

**Statistics.** Relative error = (layer - geodesic) / geodesic, on the pixels whose geodesic distance is at least 2 km (below that the quantisation of the substation, not the scale, dominates a relative figure); absolute error in km uses all pixels. Medians are signed; P95 and maximum are of the absolute value.

### 3.1 By country and latitude band (central scenario, solar and wind)

"Scale only" is calculation A; "Total" is calculation B. Bands are 5 degrees, named by their lower edge.

| Country | Band | Pixels (n sampled / in band) | Scale only: median (signed) | P95 abs. | max abs. | P95 abs. km | max abs. km | >1 % | >5 % | Total: P95 abs. | max abs. | P95 abs. km | >1 % | >5 % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 35 | 9825 / 40405 | -1.4 % | 12.2 % | 14.3 % | 3.06 | 5.07 | 94.9 % | 71.8 % | 14.7 % | 34.6 % | 3.17 | 94.1 % | 69.4 % |
| PRT solar | 40 | 9747 / 29009 | -0.6 % | 15.4 % | 17.9 % | 2.69 | 5.75 | 94.5 % | 73.8 % | 17.6 % | 36.9 % | 2.69 | 94.8 % | 71.0 % |
| PRT wind | 35 | 9846 / 34992 | -1.5 % | 12.0 % | 14.3 % | 3.16 | 5.54 | 95.1 % | 71.4 % | 14.4 % | 33.2 % | 3.30 | 94.4 % | 70.0 % |
| PRT wind | 40 | 9823 / 20134 | -0.7 % | 15.5 % | 17.9 % | 2.88 | 6.07 | 94.7 % | 73.9 % | 17.4 % | 38.2 % | 2.84 | 94.7 % | 70.9 % |
| IND solar | 5 | 2873 / 12057 | -3.0 % | 3.3 % | 3.3 % | 1.02 | 1.37 | 100.0 % | 0.0 % | 8.8 % | 29.4 % | 1.24 | 90.1 % | 19.5 % |
| IND solar | 10 | 2913 / 113286 | -2.4 % | 3.3 % | 3.3 % | 0.83 | 1.75 | 92.2 % | 0.0 % | 7.4 % | 28.4 % | 1.00 | 81.1 % | 15.4 % |
| IND solar | 15 | 2909 / 331640 | -1.2 % | 3.3 % | 3.3 % | 1.10 | 2.22 | 66.2 % | 0.0 % | 6.9 % | 31.2 % | 1.26 | 76.5 % | 11.9 % |
| IND solar | 20 | 2921 / 568125 | -0.1 % | 4.5 % | 5.9 % | 1.66 | 5.83 | 81.0 % | 2.3 % | 7.1 % | 32.7 % | 1.74 | 78.7 % | 13.9 % |
| IND solar | 25 | 2909 / 416788 | 2.2 % | 8.2 % | 10.9 % | 3.69 | 12.50 | 87.3 % | 31.0 % | 9.4 % | 23.3 % | 3.78 | 86.9 % | 33.1 % |
| IND solar | 30 | 2912 / 116376 | 3.3 % | 14.4 % | 16.6 % | 9.60 | 21.89 | 89.0 % | 43.3 % | 15.3 % | 33.2 % | 9.46 | 89.4 % | 47.0 % |
| IND solar | 35 | 2382 / 2382 | -1.6 % | 3.2 % | 3.5 % | 3.78 | 4.23 | 69.5 % | 0.0 % | 3.1 % | 3.4 % | 3.74 | 69.5 % | 0.0 % |
| IND wind | 5 | 3270 / 8730 | -3.0 % | 3.3 % | 3.3 % | 1.03 | 1.37 | 100.0 % | 0.0 % | 9.0 % | 29.9 % | 1.26 | 89.4 % | 19.5 % |
| IND wind | 10 | 3298 / 69939 | -2.4 % | 3.3 % | 3.3 % | 0.76 | 1.79 | 90.9 % | 0.0 % | 8.0 % | 28.4 % | 0.97 | 81.4 % | 18.2 % |
| IND wind | 15 | 3311 / 220632 | -1.3 % | 3.3 % | 3.3 % | 0.95 | 2.15 | 64.2 % | 0.0 % | 7.0 % | 22.7 % | 1.16 | 76.4 % | 11.9 % |
| IND wind | 20 | 3323 / 329333 | 0.2 % | 4.5 % | 5.9 % | 1.42 | 3.66 | 80.1 % | 2.6 % | 7.3 % | 21.8 % | 1.48 | 79.1 % | 16.0 % |
| IND wind | 25 | 3312 / 271473 | 2.6 % | 8.5 % | 10.7 % | 3.22 | 8.11 | 85.6 % | 33.9 % | 10.1 % | 26.2 % | 3.11 | 87.0 % | 38.0 % |
| IND wind | 30 | 3299 / 24001 | 3.6 % | 11.7 % | 14.3 % | 3.54 | 17.95 | 88.9 % | 44.6 % | 14.9 % | 31.4 % | 3.55 | 89.4 % | 52.4 % |
| IND wind | 35 | 6 / 6 | -2.4 % | 2.4 % | 2.4 % | 3.70 | 3.71 | 100.0 % | 0.0 % | 2.4 % | 2.4 % | 3.67 | 100.0 % | 0.0 % |
| BRA solar | -35 | 2490 / 93049 | 5.5 % | 14.7 % | 17.8 % | 7.08 | 12.66 | 84.7 % | 52.8 % | 15.6 % | 34.8 % | 7.14 | 87.7 % | 54.3 % |
| BRA solar | -30 | 2473 / 281282 | 4.1 % | 11.6 % | 13.1 % | 3.93 | 8.14 | 81.0 % | 45.4 % | 12.5 % | 26.2 % | 3.84 | 85.3 % | 47.2 % |
| BRA solar | -25 | 2470 / 557331 | 2.0 % | 6.3 % | 8.2 % | 1.81 | 6.36 | 73.0 % | 16.4 % | 9.3 % | 24.9 % | 1.85 | 79.6 % | 25.3 % |
| BRA solar | -20 | 2489 / 878932 | 0.7 % | 3.4 % | 4.3 % | 1.72 | 5.02 | 62.6 % | 0.0 % | 5.4 % | 25.7 % | 1.82 | 68.5 % | 6.4 % |
| BRA solar | -15 | 2490 / 948553 | -0.3 % | 1.2 % | 1.6 % | 0.76 | 1.72 | 27.6 % | 0.0 % | 3.6 % | 22.3 % | 0.95 | 46.2 % | 2.9 % |
| BRA solar | -10 | 2496 / 884499 | -1.1 % | 1.3 % | 1.5 % | 1.66 | 4.60 | 69.6 % | 0.0 % | 3.5 % | 19.2 % | 1.64 | 56.3 % | 1.8 % |
| BRA solar | -5 | 2496 / 440114 | -1.4 % | 1.8 % | 1.8 % | 5.64 | 14.96 | 100.0 % | 0.0 % | 3.3 % | 24.1 % | 5.64 | 74.4 % | 1.6 % |
| BRA solar | 0 | 2498 / 72631 | -1.5 % | 1.8 % | 1.8 % | 5.88 | 13.97 | 100.0 % | 0.0 % | 2.5 % | 21.1 % | 5.49 | 80.7 % | 0.8 % |
| BRA wind | -35 | 2491 / 86469 | 5.3 % | 14.6 % | 17.7 % | 7.30 | 12.68 | 83.4 % | 51.7 % | 15.4 % | 40.9 % | 7.26 | 86.5 % | 53.1 % |
| BRA wind | -30 | 2488 / 219651 | 4.4 % | 11.7 % | 13.2 % | 4.15 | 8.67 | 82.1 % | 46.4 % | 12.7 % | 25.6 % | 4.06 | 86.4 % | 49.7 % |
| BRA wind | -25 | 2479 / 476394 | 1.8 % | 6.2 % | 8.0 % | 1.82 | 5.46 | 72.5 % | 15.4 % | 9.1 % | 26.3 % | 1.83 | 81.0 % | 23.4 % |
| BRA wind | -20 | 2492 / 767202 | 0.8 % | 3.5 % | 4.4 % | 1.44 | 5.01 | 62.4 % | 0.0 % | 5.5 % | 25.7 % | 1.61 | 66.4 % | 6.3 % |
| BRA wind | -15 | 2492 / 860624 | -0.3 % | 1.2 % | 1.5 % | 0.77 | 1.49 | 27.2 % | 0.0 % | 3.8 % | 25.2 % | 0.94 | 45.8 % | 2.8 % |
| BRA wind | -10 | 2497 / 770817 | -1.1 % | 1.4 % | 1.5 % | 1.33 | 4.13 | 70.3 % | 0.0 % | 3.8 % | 30.4 % | 1.37 | 57.2 % | 2.6 % |
| BRA wind | -5 | 2497 / 279302 | -1.4 % | 1.7 % | 1.8 % | 1.72 | 14.03 | 100.0 % | 0.0 % | 3.4 % | 18.2 % | 1.87 | 73.3 % | 1.9 % |
| BRA wind | 0 | 2499 / 45456 | -1.5 % | 1.8 % | 1.8 % | 5.46 | 7.18 | 100.0 % | 0.0 % | 2.7 % | 19.0 % | 5.07 | 79.0 % | 1.1 % |

### 3.2 By country, scenario and technology: fraction of pixels above 1 % and 5 %

| Country | Scenario / technology | Pixels sampled | Scale only: median (signed) | P95 abs. | max abs. | abs. km median / P95 / max | >1 % | >5 % | Total (vector): P95 abs. | max abs. | abs. km P95 / max | >1 % | >5 % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT | central/solar | 20000 | -0.8 % | 14.5 % | 17.9 % | 0.90 / 2.91 / 5.75 | 94.8 % | 72.6 % | 16.5 % | 36.9 % | 2.96 / 5.42 | 94.4 % | 70.1 % |
| PRT | central/wind | 20000 | -1.0 % | 14.6 % | 17.9 % | 0.94 / 3.05 / 6.07 | 94.9 % | 72.3 % | 16.2 % | 38.2 % | 3.10 / 6.54 | 94.5 % | 70.3 % |
| PRT | restrictive/solar | 20000 | -1.0 % | 14.5 % | 17.9 % | 0.91 / 2.96 / 5.83 | 95.0 % | 72.3 % | 16.4 % | 36.9 % | 3.02 / 5.50 | 94.4 % | 70.1 % |
| PRT | restrictive/wind | 20000 | -0.8 % | 14.5 % | 17.4 % | 1.00 / 3.18 / 5.83 | 95.0 % | 72.2 % | 15.6 % | 38.2 % | 3.20 / 5.50 | 94.5 % | 70.4 % |
| PRT | permissive/solar | 20000 | -0.8 % | 14.4 % | 17.9 % | 0.89 / 2.91 / 6.20 | 94.8 % | 72.2 % | 16.3 % | 33.2 % | 2.96 / 6.67 | 94.4 % | 70.2 % |
| PRT | permissive/wind | 20000 | -0.9 % | 14.4 % | 17.9 % | 0.88 / 2.91 / 6.00 | 94.8 % | 72.0 % | 16.4 % | 35.9 % | 2.99 / 6.47 | 94.3 % | 70.0 % |
| IND | central/solar | 20000 | -1.6 % | 8.3 % | 16.6 % | 0.51 / 3.50 / 21.89 | 81.1 % | 12.3 % | 10.3 % | 33.2 % | 3.50 / 21.56 | 81.4 % | 21.2 % |
| IND | central/wind | 20000 | -1.6 % | 8.8 % | 14.3 % | 0.39 / 1.86 / 17.95 | 79.2 % | 12.1 % | 10.7 % | 31.4 % | 1.92 / 17.61 | 81.3 % | 22.6 % |
| IND | restrictive/solar | 20000 | -1.6 % | 8.1 % | 16.6 % | 0.52 / 3.88 / 22.05 | 79.5 % | 11.0 % | 10.2 % | 29.8 % | 3.86 / 21.73 | 81.0 % | 19.8 % |
| IND | restrictive/wind | 20000 | -1.5 % | 8.6 % | 13.6 % | 0.37 / 1.62 / 8.20 | 81.3 % | 14.5 % | 10.9 % | 32.6 % | 1.70 / 7.77 | 81.4 % | 24.7 % |
| IND | permissive/solar | 20000 | -1.6 % | 8.4 % | 16.6 % | 0.50 / 3.60 / 21.47 | 81.4 % | 13.3 % | 10.5 % | 31.0 % | 3.58 / 21.15 | 82.4 % | 22.6 % |
| IND | permissive/wind | 20000 | -1.7 % | 8.5 % | 14.2 % | 0.43 / 2.20 / 17.30 | 81.3 % | 12.5 % | 10.5 % | 33.2 % | 2.26 / 16.96 | 81.2 % | 21.7 % |
| BRA | central/solar | 20000 | -0.7 % | 10.4 % | 17.8 % | 0.53 / 4.35 / 14.96 | 63.8 % | 6.4 % | 11.1 % | 34.8 % | 4.26 / 14.64 | 64.7 % | 10.3 % |
| BRA | central/wind | 20000 | -0.7 % | 10.3 % | 17.7 % | 0.51 / 3.94 / 14.03 | 62.1 % | 6.3 % | 11.0 % | 40.9 % | 3.95 / 13.70 | 63.7 % | 10.4 % |
| BRA | restrictive/solar | 20000 | -0.7 % | 10.1 % | 17.7 % | 0.54 / 4.37 / 13.96 | 64.0 % | 6.5 % | 11.1 % | 38.5 % | 4.32 / 13.64 | 64.5 % | 10.5 % |
| BRA | restrictive/wind | 20000 | -0.7 % | 10.4 % | 17.3 % | 0.51 / 3.99 / 11.15 | 61.3 % | 6.0 % | 11.1 % | 33.4 % | 3.91 / 11.38 | 61.9 % | 10.2 % |
| BRA | permissive/solar | 20000 | -0.7 % | 10.1 % | 17.5 % | 0.53 / 4.51 / 17.94 | 63.5 % | 6.3 % | 10.9 % | 31.4 % | 4.41 / 17.77 | 64.3 % | 10.4 % |
| BRA | permissive/wind | 20000 | -0.7 % | 10.1 % | 17.6 % | 0.54 / 4.42 / 18.03 | 64.2 % | 6.3 % | 11.0 % | 30.7 % | 4.35 / 17.63 | 64.1 % | 10.6 % |

The three scenarios and the two technologies give the same picture (fractions within a few points of each other in a country): the error belongs to the layer, not to the eligible area chosen. The "total" error is larger in the tail (maximum 30 to 41 %) because of the quantisation of the substation at small distances; its P95 in km is almost the same as the scale-only P95, so the scale, not the quantisation, sets the error in kilometres.

Appendix, by band for every scenario and technology (scale only):

| Country | Scenario / technology | Band | n | Scale only: P95 abs. | max abs. | P95 abs. km | >1 % | >5 % |
|---|---|---|---|---|---|---|---|---|
| PRT | central/solar | 35 | 9825 | 12.2 % | 14.3 % | 3.06 | 94.9 % | 71.8 % |
| PRT | central/solar | 40 | 9747 | 15.4 % | 17.9 % | 2.69 | 94.5 % | 73.8 % |
| PRT | central/wind | 35 | 9846 | 12.0 % | 14.3 % | 3.16 | 95.1 % | 71.4 % |
| PRT | central/wind | 40 | 9823 | 15.5 % | 17.9 % | 2.88 | 94.7 % | 73.9 % |
| PRT | restrictive/solar | 35 | 9845 | 12.2 % | 14.3 % | 3.09 | 95.1 % | 71.4 % |
| PRT | restrictive/solar | 40 | 9804 | 15.5 % | 17.9 % | 2.72 | 94.7 % | 73.6 % |
| PRT | restrictive/wind | 35 | 9875 | 12.1 % | 14.1 % | 3.22 | 95.1 % | 72.0 % |
| PRT | restrictive/wind | 40 | 9849 | 15.4 % | 17.4 % | 3.09 | 94.8 % | 72.7 % |
| PRT | permissive/solar | 35 | 9829 | 12.3 % | 14.3 % | 3.05 | 95.3 % | 71.4 % |
| PRT | permissive/solar | 40 | 9735 | 15.4 % | 17.9 % | 2.65 | 94.2 % | 73.3 % |
| PRT | permissive/wind | 35 | 9851 | 12.3 % | 14.3 % | 3.06 | 94.9 % | 71.3 % |
| PRT | permissive/wind | 40 | 9743 | 15.5 % | 17.9 % | 2.68 | 94.7 % | 72.9 % |
| IND | central/solar | 5 | 2873 | 3.3 % | 3.3 % | 1.02 | 100.0 % | 0.0 % |
| IND | central/solar | 10 | 2913 | 3.3 % | 3.3 % | 0.83 | 92.2 % | 0.0 % |
| IND | central/solar | 15 | 2909 | 3.3 % | 3.3 % | 1.10 | 66.2 % | 0.0 % |
| IND | central/solar | 20 | 2921 | 4.5 % | 5.9 % | 1.66 | 81.0 % | 2.3 % |
| IND | central/solar | 25 | 2909 | 8.2 % | 10.9 % | 3.69 | 87.3 % | 31.0 % |
| IND | central/solar | 30 | 2912 | 14.4 % | 16.6 % | 9.60 | 89.0 % | 43.3 % |
| IND | central/solar | 35 | 2382 | 3.2 % | 3.5 % | 3.78 | 69.5 % | 0.0 % |
| IND | central/wind | 5 | 3270 | 3.3 % | 3.3 % | 1.03 | 100.0 % | 0.0 % |
| IND | central/wind | 10 | 3298 | 3.3 % | 3.3 % | 0.76 | 90.9 % | 0.0 % |
| IND | central/wind | 15 | 3311 | 3.3 % | 3.3 % | 0.95 | 64.2 % | 0.0 % |
| IND | central/wind | 20 | 3323 | 4.5 % | 5.9 % | 1.42 | 80.1 % | 2.6 % |
| IND | central/wind | 25 | 3312 | 8.5 % | 10.7 % | 3.22 | 85.6 % | 33.9 % |
| IND | central/wind | 30 | 3299 | 11.7 % | 14.3 % | 3.54 | 88.9 % | 44.6 % |
| IND | central/wind | 35 | 6 | 2.4 % | 2.4 % | 3.70 | 100.0 % | 0.0 % |
| IND | restrictive/solar | 5 | 2923 | 3.3 % | 3.3 % | 1.05 | 100.0 % | 0.0 % |
| IND | restrictive/solar | 10 | 2958 | 3.3 % | 3.3 % | 0.82 | 91.8 % | 0.0 % |
| IND | restrictive/solar | 15 | 2968 | 3.3 % | 3.3 % | 1.03 | 65.5 % | 0.0 % |
| IND | restrictive/solar | 20 | 2969 | 4.5 % | 6.0 % | 1.83 | 80.3 % | 2.7 % |
| IND | restrictive/solar | 25 | 2969 | 7.9 % | 10.7 % | 4.15 | 86.4 % | 30.4 % |
| IND | restrictive/solar | 30 | 2966 | 15.1 % | 16.6 % | 11.73 | 88.0 % | 42.7 % |
| IND | restrictive/solar | 35 | 2105 | 3.1 % | 3.5 % | 3.78 | 69.5 % | 0.0 % |
| IND | restrictive/wind | 5 | 3236 | 3.3 % | 3.3 % | 1.03 | 100.0 % | 0.0 % |
| IND | restrictive/wind | 10 | 3288 | 3.3 % | 3.3 % | 0.76 | 88.1 % | 0.0 % |
| IND | restrictive/wind | 15 | 3316 | 3.3 % | 3.3 % | 0.96 | 69.6 % | 0.0 % |
| IND | restrictive/wind | 20 | 3321 | 4.5 % | 6.0 % | 1.29 | 79.9 % | 1.8 % |
| IND | restrictive/wind | 25 | 3313 | 8.4 % | 10.7 % | 3.48 | 88.0 % | 36.1 % |
| IND | restrictive/wind | 30 | 3312 | 11.3 % | 13.6 % | 1.66 | 89.5 % | 45.7 % |
| IND | permissive/solar | 5 | 2840 | 3.3 % | 3.3 % | 0.97 | 100.0 % | 0.0 % |
| IND | permissive/solar | 10 | 2863 | 3.3 % | 3.3 % | 0.80 | 94.3 % | 0.0 % |
| IND | permissive/solar | 15 | 2868 | 3.3 % | 3.3 % | 1.05 | 63.9 % | 0.0 % |
| IND | permissive/solar | 20 | 2870 | 4.6 % | 5.9 % | 1.68 | 81.3 % | 3.0 % |
| IND | permissive/solar | 25 | 2866 | 8.2 % | 10.8 % | 3.90 | 87.6 % | 30.8 % |
| IND | permissive/solar | 30 | 2869 | 14.7 % | 16.6 % | 9.55 | 88.6 % | 42.8 % |
| IND | permissive/solar | 35 | 2699 | 3.2 % | 3.5 % | 3.78 | 69.1 % | 0.0 % |
| IND | permissive/wind | 5 | 3275 | 3.3 % | 3.3 % | 1.00 | 100.0 % | 0.0 % |
| IND | permissive/wind | 10 | 3308 | 3.3 % | 3.3 % | 0.82 | 93.4 % | 0.0 % |
| IND | permissive/wind | 15 | 3311 | 3.3 % | 3.3 % | 1.06 | 67.2 % | 0.0 % |
| IND | permissive/wind | 20 | 3317 | 4.7 % | 5.9 % | 1.68 | 80.9 % | 3.6 % |
| IND | permissive/wind | 25 | 3317 | 8.3 % | 10.9 % | 3.18 | 87.5 % | 32.1 % |
| IND | permissive/wind | 30 | 3301 | 12.2 % | 14.2 % | 4.14 | 88.7 % | 41.7 % |
| IND | permissive/wind | 35 | 11 | 2.4 % | 2.4 % | 3.68 | 100.0 % | 0.0 % |
| BRA | central/solar | -35 | 2490 | 14.7 % | 17.8 % | 7.08 | 84.7 % | 52.8 % |
| BRA | central/solar | -30 | 2473 | 11.6 % | 13.1 % | 3.93 | 81.0 % | 45.4 % |
| BRA | central/solar | -25 | 2470 | 6.3 % | 8.2 % | 1.81 | 73.0 % | 16.4 % |
| BRA | central/solar | -20 | 2489 | 3.4 % | 4.3 % | 1.72 | 62.6 % | 0.0 % |
| BRA | central/solar | -15 | 2490 | 1.2 % | 1.6 % | 0.76 | 27.6 % | 0.0 % |
| BRA | central/solar | -10 | 2496 | 1.3 % | 1.5 % | 1.66 | 69.6 % | 0.0 % |
| BRA | central/solar | -5 | 2496 | 1.8 % | 1.8 % | 5.64 | 100.0 % | 0.0 % |
| BRA | central/solar | 0 | 2498 | 1.8 % | 1.8 % | 5.88 | 100.0 % | 0.0 % |
| BRA | central/wind | -35 | 2491 | 14.6 % | 17.7 % | 7.30 | 83.4 % | 51.7 % |
| BRA | central/wind | -30 | 2488 | 11.7 % | 13.2 % | 4.15 | 82.1 % | 46.4 % |
| BRA | central/wind | -25 | 2479 | 6.2 % | 8.0 % | 1.82 | 72.5 % | 15.4 % |
| BRA | central/wind | -20 | 2492 | 3.5 % | 4.4 % | 1.44 | 62.4 % | 0.0 % |
| BRA | central/wind | -15 | 2492 | 1.2 % | 1.5 % | 0.77 | 27.2 % | 0.0 % |
| BRA | central/wind | -10 | 2497 | 1.4 % | 1.5 % | 1.33 | 70.3 % | 0.0 % |
| BRA | central/wind | -5 | 2497 | 1.7 % | 1.8 % | 1.72 | 100.0 % | 0.0 % |
| BRA | central/wind | 0 | 2499 | 1.8 % | 1.8 % | 5.46 | 100.0 % | 0.0 % |
| BRA | restrictive/solar | -35 | 2493 | 14.6 % | 17.7 % | 7.04 | 85.2 % | 53.9 % |
| BRA | restrictive/solar | -30 | 2481 | 11.6 % | 13.2 % | 3.73 | 82.8 % | 46.6 % |
| BRA | restrictive/solar | -25 | 2473 | 6.4 % | 8.2 % | 1.82 | 73.7 % | 16.5 % |
| BRA | restrictive/solar | -20 | 2490 | 3.4 % | 4.4 % | 1.63 | 61.6 % | 0.0 % |
| BRA | restrictive/solar | -15 | 2494 | 1.2 % | 1.6 % | 0.73 | 27.7 % | 0.0 % |
| BRA | restrictive/solar | -10 | 2495 | 1.3 % | 1.5 % | 1.52 | 70.7 % | 0.0 % |
| BRA | restrictive/solar | -5 | 2499 | 1.8 % | 1.8 % | 5.25 | 100.0 % | 0.0 % |
| BRA | restrictive/solar | 0 | 2496 | 1.8 % | 1.8 % | 5.75 | 100.0 % | 0.0 % |
| BRA | restrictive/wind | -35 | 2494 | 14.4 % | 17.3 % | 7.03 | 83.7 % | 52.4 % |
| BRA | restrictive/wind | -30 | 2492 | 11.9 % | 13.1 % | 4.20 | 81.0 % | 46.8 % |
| BRA | restrictive/wind | -25 | 2474 | 6.3 % | 8.2 % | 1.73 | 73.8 % | 16.1 % |
| BRA | restrictive/wind | -20 | 2488 | 3.4 % | 4.4 % | 1.50 | 61.4 % | 0.0 % |
| BRA | restrictive/wind | -15 | 2493 | 1.2 % | 1.5 % | 0.77 | 27.8 % | 0.0 % |
| BRA | restrictive/wind | -10 | 2495 | 1.4 % | 1.5 % | 1.25 | 70.1 % | 0.0 % |
| BRA | restrictive/wind | -5 | 2495 | 1.7 % | 1.8 % | 1.56 | 100.0 % | 0.0 % |
| BRA | restrictive/wind | 0 | 2499 | 1.8 % | 1.8 % | 5.59 | 100.0 % | 0.0 % |
| BRA | permissive/solar | -35 | 2487 | 14.5 % | 17.5 % | 7.14 | 83.4 % | 51.1 % |
| BRA | permissive/solar | -30 | 2476 | 11.5 % | 13.1 % | 3.70 | 81.5 % | 45.3 % |
| BRA | permissive/solar | -25 | 2469 | 6.3 % | 8.2 % | 1.78 | 71.1 % | 16.5 % |
| BRA | permissive/solar | -20 | 2486 | 3.4 % | 4.4 % | 1.61 | 61.9 % | 0.0 % |
| BRA | permissive/solar | -15 | 2491 | 1.2 % | 1.6 % | 0.76 | 26.6 % | 0.0 % |
| BRA | permissive/solar | -10 | 2490 | 1.3 % | 1.5 % | 1.56 | 70.2 % | 0.0 % |
| BRA | permissive/solar | -5 | 2495 | 1.8 % | 1.8 % | 6.43 | 100.0 % | 0.0 % |
| BRA | permissive/solar | 0 | 2496 | 1.8 % | 1.8 % | 6.05 | 100.0 % | 0.0 % |
| BRA | permissive/solar | 5 | 24 | 1.2 % | 1.2 % | 3.04 | 100.0 % | 0.0 % |
| BRA | permissive/wind | -35 | 2485 | 14.6 % | 17.6 % | 6.75 | 84.4 % | 51.1 % |
| BRA | permissive/wind | -30 | 2473 | 11.7 % | 13.2 % | 4.03 | 82.0 % | 45.9 % |
| BRA | permissive/wind | -25 | 2470 | 6.3 % | 8.2 % | 1.79 | 72.9 % | 15.9 % |
| BRA | permissive/wind | -20 | 2490 | 3.5 % | 4.3 % | 1.65 | 62.2 % | 0.0 % |
| BRA | permissive/wind | -15 | 2489 | 1.2 % | 1.6 % | 0.75 | 27.2 % | 0.0 % |
| BRA | permissive/wind | -10 | 2491 | 1.4 % | 1.5 % | 1.70 | 71.0 % | 0.0 % |
| BRA | permissive/wind | -5 | 2492 | 1.7 % | 1.8 % | 6.20 | 100.0 % | 0.0 % |
| BRA | permissive/wind | 0 | 2494 | 1.8 % | 1.8 % | 5.99 | 100.0 % | 0.0 % |
| BRA | permissive/wind | 5 | 24 | 1.2 % | 1.2 % | 3.04 | 100.0 % | 0.0 % |

## 4. Effect on L and on the line cost term

In the connection cost the line length is L = tortuosity_grid x D with tortuosity_grid = 1.25, range U[1.2, 1.3] for the three countries (`config/parameters.json`, Tier 3, author judgment), so a relative error of D is the same relative error of L and of `c_line x L`; the choice of the tortuosity moves L by +-0.05 / 1.25 = +-4 %. `line_cost_per_km` (c_line, config units): PRT 0.362 MEUR/km, IND 1.1 INR crore/km, BRA 598,332 BRL/km. The figures below are products of these config values with the measured distance errors (central scenario, solar); no cost model was run and no cost was invented.

| Country | c_line (config) | D geodesic median / P95 (km), central solar | L = 1.25 D median / P95 (km) | Half-range of the tortuosity choice at the P95 D (+-0.05 x D, km of L) | Error of the layer, P95 abs. (km of D, central solar) | Error in L = 1.25 x that (km) | P95 relative error of D / 4 % (the tortuosity half-range, 0.05 / 1.25) | Error in c_line x L, P95 (config unit) | Tortuosity half-range in c_line x L at P95 D (config unit) | Error in c_line x L, max |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT | 0.362 MEUR/km | 12.5 / 30.3 | 15.6 / 37.9 | 1.52 | 2.90 | 3.63 | 3.6 (14.5 %) | 1.31 MEUR | 0.548 MEUR | 2.6 MEUR |
| IND | 1.1 INR crore/km | 21.0 / 126.3 | 26.3 / 157.8 | 6.31 | 3.50 | 4.37 | 2.1 (8.3 %) | 4.81 INR crore | 6.94 INR crore | 30.1 INR crore |
| BRA | 598332 BRL/km | 34.3 / 134.1 | 42.9 / 167.6 | 6.70 | 4.34 | 5.43 | 2.6 (10.4 %) | 3.25e+06 BRL | 4.01e+06 BRL | 1.12e+07 BRL |

Reading. In relative terms the P95 error of D is 3.6 times the half-range of the tortuosity in PRT, 2.1 times in IND and 2.6 times in BRA, and 72 %, 12 % and 6 % of the eligible pixels are off by more than 5 %. In absolute terms the error of the line is a few kilometres (P95 of L: 3.6 km in PRT, 4.4 km in IND, 5.4 km in BRA; maximum about 22 km in BRA); compared with the tortuosity half-range at the P95 distance it is 2.4 times in PRT and 0.7 to 0.8 times in IND and BRA, whose far pixels are far from every substation and carry a large tortuosity swing in kilometres. Two differences matter more than the size: the tortuosity draw is the **same multiplier for every cell** of a draw (it shifts all costs together), while the scale error is a **fixed distortion that depends on position and on the direction to the substation**, so it changes which cell is cheaper than another; and it is the same in every future, in the three scenarios (it does not average out across the draws of the design).

## 5. Classification

Criterion proposed in the command: adequate if the error is within the noise of the choice of L (4 %).

| Country | P95 relative error | Pixels above 5 % | Verdict |
|---|---|---|---|
| PRT | 14.5 % (max 17.9 %) | about 72 % | **defect (b)**: the error is above the noise for most of the country, and the cause (anisotropy at 37-42 degrees) is in the formula |
| IND | 8.3 % (max 16.6 %) | about 12 % | **defect (b)** in the tail: the median error is small (-1.6 %), the error is large in the north (+13 to +18 % east-west beyond 30 degrees) |
| BRA | 10.4 % (max 17.8 %) | about 6 % | **defect (b)** in the tail: small near the centre of the grid, large in the south (+10 to +18 % east-west south of -25 degrees) |

The fixture does not see it because the synthetic country sits at -4.9 degrees, where the two axes differ by 0.3 % (the ZZZ validator has two checks, one for conformity with the method and one sanity check against the geodesic with 0.5 % tolerance; both pass, COMMAND 110). This is a statement about the layer, not about the validator.

## 6. What a correction would invalidate (not applied; trial edits in copies outside the repository)

I changed copies of `src` outside the repository with a trivial AST edit and measured the code fingerprints (`closure_fingerprint` of the 19 phases, `function_fingerprint` of the 13 caches).

| Where the correction is made | Phase fingerprints that change | Cache fingerprints that change |
|---|---|---|
| Inside `calculate_wgs84_isotropic_distance` (`grid_alignment/vector_alignment.py`) | 1 of 19: `grid_alignment` | 4 of 13: `aligned_layer.grid`, `aligned_layer.poi`, `aligned_layer.rivers`, `aligned_layer.roads` |
| In `core/geodesy.py::wgs84_km_per_degree` (shared by many modules) | 17 of 19: `climate_forcing`, `climate_maps`, `data_quality_audit`, `external_validation`, `grid_alignment`, `hazard_context`, `land_eligibility`, `lcoe_maps`, `lcoe_modeling`, `overview`, `potential_maps`, `results_synthesis`, `robustness_analysis`, `robustness_maps`, `sample_size_convergence`, `siting_layers`, `technical_potential` | 6 of 13: the four above plus `aligned_layer.glo30` and `aligned_layer.fabdem_slope` |

Only F2a changes by fingerprint when the edit stays inside the function, but the artifacts it writes change in content (`<ISO>_poi_aligned.tif`, `_grid_`, `_roads_`, `_rivers_` and their `_capped` flags), so the phases that read them recompute by the content of their inputs: F2b `siting_layers`, F3 `land_eligibility` (`dist_sub_km`, `dist_road_km` of the candidate tables), and the phases that read the candidates (F5 `technical_potential` and its maps). F6 and the later phases have not been run on a real country (the round of 9c2dc3c8 ends at `potential_maps`), so nothing real downstream of F5 would be redone.

Cost, from the wall times of round 9c2dc3c8 (`outputs/<ISO>/unattended_check.json`, the round that ran F2a with cold layers; a re-run recomputes only the four layers whose cache key changes, and I did not measure that cost): F2a + F2b + F3 + F5 + `potential_maps` = PRT 45 + 35 + 29 + 6 + 10 = 125 s; IND 2,186 + 57 + 186 + 79 + 20 = 2,528 s (42 min); BRA 4,761 + 98 + 578 + 229 + 38 = 5,704 s (95 min). The F2a figures of IND and BRA are an upper bound for the layers affected here.

The deferred content check (`config/deferred_checks.yaml`) compares the three countries with the latest reference round (9c2dc3c8, `expected` empty) and stops a run at the first difference that no configuration change explains; raster differences are compared with the tolerance of `core.equivalence`. A distance that moves by up to 18 % is outside any such tolerance, so a corrected layer needs `expected` entries pinned to 9c2dc3c8 for the artifacts of the four layers and of every phase that reads them, for PRT, IND and BRA, or a new accepted round; that is the content check that IND and BRA are still waiting for.

## 7. Open decision, awaiting the author's verdict (nothing was changed)

The layer is classified as a defect (b). Options, none chosen:

1. Leave the layer and declare the limitation with the figures of section 3, if the error is judged acceptable for the thesis comparison (it is not within the 4 % of the tortuosity choice for most of PRT).
2. Correct the scale along the latitude: compute the distance transform with the two axes weighted separately (`sampling=(dy_km, dx_km)` at the grid centre, as `fractions.py` already does for the river corridor) and, for IND and BRA, by latitude strip. This removes the anisotropy at the centre and most of the error in PRT; the strip join needs a rule.
3. Correct with the geodesic: nearest burnt pixel by ECEF nearest neighbour and the WGS84 geodesic to it, in blocks. Exact up to the quantisation of the substation (0.78 km); the cost of one distance raster per layer is the main unknown and was not measured.
4. Either correction also applies to `grid`, `roads` and `rivers` (same function); whether they are corrected together is part of the decision.

Whichever is chosen, F6 has not been run on a real country, so the correction costs the F2a to F5 rerun above and an `expected` declaration (or a new accepted round); it needs a METHODOLOGY entry (the scale is part of M-F2a-03) and its own fingerprint check. The ZZZ validator will need its conformity check (a) rewritten to the new method.
