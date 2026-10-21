# Provenance of the transmission-grid data (OQ-063)

Written for Douglas, who completes the fields marked **[AUTHOR]**. Draft of COMMAND 58, completed in COMMAND 63 (2026-10-21). Nothing in the code uses
`grid.gpkg`: F2b reads the per-country OSM extract (`raw/infrastructure_grid/<ISO3>/<ISO3>_grid_osm.geojson`, `resolve_grid_path`). **The source of
the grid is not changed here.** Which source and which voltage level are the connection target is a decision of Group 3 (OQ-063, OQ-041).

## 1. The two files

| | `grid.gpkg` (global, local database) | `<ISO3>_grid_osm.geojson` (per country, what the pipeline reads) |
|---|---|---|
| Path | `D:\Douglas\DOUTORADO\database\raw\infrastructure\grid\grid.gpkg` | `GEOFREA_DATA_DIR/raw/infrastructure_grid/<ISO3>/` |
| Size | 724,566,016 bytes (724.6 MB) | PRT 4.5 MB, IND 34.8 MB, BRA 38.5 MB |
| Content | one layer `grid`, LineString, EPSG:4326, 3,678,243 lines, one field `source` | LineString (power lines) and Point (substations), OSM tags as properties (`power`, `voltage`, `operator`, ...) |
| Source attribute | `source` = `gridfinder` (1,858,899 lines) or `openstreetmap` (1,819,344 lines) | OSM tags; every line has `power=line` and a `voltage` tag |
| Date in the file | `gpkg_contents.last_change` = 2019-11-12T08:13:25Z; no version or origin attribute | none; the newest dated tags are `survey:date` 2025-05-10 and `check_date` 2024-12-08 (PRT), so the extract is from 2025-05 or later; the files were placed on 2026-10-14 (date of the copy) |
| Voltage | **none** | `voltage` on every line |

## 2. Source, version, licence and citation

### `source = gridfinder` and the file as a whole
- The file matches the file `grid.gpkg` of the dataset *Data from: Predictive mapping of the global power system using open data*: Zenodo record
  10.5281/zenodo.3628142, **version 1.1.1, published 2020-01-16**, which lists `grid.gpkg` at 724.6 MB (the local file has 724,566,016 bytes) and describes it as
  "vectorized predicted distribution and transmission line network, with existing OpenStreetMap lines tagged in the `source` column". The checksum was not
  compared (the record page read on 2026-10-21 does not show one in the text that was retrieved): **[AUTHOR]** confirm the MD5 of the Zenodo file against the local one.
- **Licence of the data:** Creative Commons Attribution 4.0 International (CC BY 4.0), as the Zenodo record states.
- **Citation:** Arderne, C., Zorn, C., Nicolas, C. & Koks, E. E. (2020). Predictive mapping of the global power system using open data. *Scientific Data* 7, 19.
  https://doi.org/10.1038/s41597-019-0347-4. Data: Arderne, C., Nicolas, C., Zorn, C. & Koks, E. E. (2020). Data from: Predictive mapping of the global power system
  using open data (v1.1.1). Zenodo. https://doi.org/10.5281/zenodo.3628142.
- The lines with `source = gridfinder` are **predicted** by the gridfinder method (night-time lights and road/settlement data; Arderne et al. 2020), not mapped.
  What the paper says about which voltage levels the prediction covers is not in the file; **[AUTHOR]** confirm from the paper (section "Methods") before it is quoted.

### `source = openstreetmap` in `grid.gpkg` and the per-country extracts
- OpenStreetMap lines: (c) OpenStreetMap contributors, **Open Database Licence (ODbL) 1.0**; attribution and share-alike apply to a database derived from them.
- Date of the OSM data in `grid.gpkg`: not in the file; the dataset is of 2019-2020 (last change 2019-11-12, record of 2020-01-16).
- Date of the per-country extracts: **[AUTHOR]** the date and the method (Overpass query, Geofabrik file) of the extraction. The newest tags in the PRT file are of 2025-05.

## 3. Does the grid distinguish voltage? Can the estimated medium-voltage lines be separated from the high-voltage ones?

- **`grid.gpkg`: no.** The only attribute is `source`. There is no voltage, no capacity and no date per line. The only split the file allows is
  predicted (`gridfinder`) against mapped (`openstreetmap`), which is not a split by voltage: the mapped lines are whatever the gridfinder build took from
  OSM, and the predicted lines carry no voltage. A medium-voltage estimate cannot be separated from a high-voltage line by an attribute. A proxy (a predicted line
  that does not overlap a mapped line) would be an inference from geometry, not a property of the data, and is not used.
- **The per-country OSM extract: yes.** Every line has a `voltage` tag (volts, sometimes several values separated by `;`; the highest is taken). Within the mask:

| Voltage class (highest value of the tag) | PRT lines | PRT km | IND lines | IND km | BRA lines | BRA km |
|---|---|---|---|---|---|---|
| >= 220 kV | 1,630 | 6,011.0 | 12,742 | 178,438.2 | 3,121 | 159,880.7 |
| 100-219 kV | 753 | 1,925.7 | 6,527 | 77,289.0 | 5,747 | 73,109.4 |
| 36-99 kV | 3,457 | 9,137.5 | 5,244 | 25,025.6 | 6,326 | 65,389.9 |
| < 36 kV | 390 | 358.4 | 1,966 | 5,367.6 | 250 | 1,476.7 |
| **Total** | **6,230** | **17,432.7** | **26,479** | **286,120.6** | **15,444** | **299,856.7** |

## 4. Per country: lines and km by source, against the extract the pipeline reads

Lines cut at the country mask (the contiguous mask of F1, simplified to 0.01 degree for the cut), geodesic length on WGS84. The extract counts are lines only (the Point
substations are not counted). Script and logs: `D:\tmp_diag\r58\grid_compare_progress.py`, `D:\tmp_diag\r62\osm_voltage.py`.

| Country | `grid.gpkg` lines | km | gridfinder lines | km | openstreetmap lines | km | OSM extract lines | km |
|---|---|---|---|---|---|---|---|---|
| PRT | 16,425 | 27,893.4 | 7,076 | 13,995.5 | 9,349 | 13,897.9 | 6,230 | 17,432.7 |
| IND | 551,086 | 926,446.4 | 254,821 | 503,892.8 | 296,265 | 422,553.6 | 26,479 | 286,120.6 |
| BRA | 149,869 | 508,312.4 | 76,383 | 275,288.6 | 73,486 | 233,023.9 | 15,444 | 299,856.7 |

Readings (what the numbers show; the causes are not established):
- PRT: the extract has **more** mapped length (17,433 km) than the mapped lines of `grid.gpkg` (13,898 km): the extract is newer.
- IND: the mapped lines of `grid.gpkg` hold **48% more** length (422,554 km) than the extract (286,121 km), and the file adds 503,893 km of predicted lines.
  The extract is the smaller source in IND (OQ-041: the OSM grid is incomplete there).
- BRA: the extract (299,857 km) has 29% more length than the mapped lines of `grid.gpkg` (233,024 km).
- The lines of `grid.gpkg` are shorter on average than those of the extract in all three countries (PRT 1.7 km against 2.8 km, IND 1.7 km against 10.8 km,
  BRA 3.4 km against 19.4 km per line), so line counts of the two files cannot be compared: only length is.

### The blocks that the contiguous mask added to IND (about 171,446 km2: the north block and Arunachal Pradesh)

| | lines | km |
|---|---|---|
| `grid.gpkg`, total | 5,290 | 11,393.6 |
| of which gridfinder (predicted) | 2,940 | 8,286.1 |
| of which openstreetmap | 2,350 | 3,107.5 |
| OSM extract of the pipeline | **0** | **0.0** |
| for comparison: `grid.gpkg` in the old mask of IND | 545,851 | 915,052.8 |

The extract of the pipeline holds no line in the added blocks, so `dist_grid_km` there is the distance to the nearest line outside them (or is undefined at the
cap, M-F2a-03). `grid.gpkg` has 11,394 km there, 27% of it mapped. This is the number that bears on a change of source; the choice is Group 3's.

## 5. Open items

| Item | Who |
|---|---|
| MD5 of the local `grid.gpkg` against the Zenodo record 3628142 v1.1.1 | **[AUTHOR]** |
| Method and date of the per-country OSM extracts; whether to refresh them | **[AUTHOR]** |
| What the paper says about the voltage levels that gridfinder predicts, if it is quoted in the thesis | **[AUTHOR]** |
| Whether the connection target uses the OSM extract, `grid.gpkg` or both, and the voltage level that counts as the target (OQ-041, OQ-063) | Group 3 |
