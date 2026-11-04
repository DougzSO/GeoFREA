# Substations of the POI layer by country (COMMAND 84, OQ-067)

Source: OSM `power=substation` as nodes, ways and relations (Overpass, `scripts/fetch_osm_substations.py`); lines from the raw grid extract.
Tolerance for the voltage of a substation without a tag: 50.0 m. A node inside a polygon is dropped; the point is the `representative_point`.

| Country | V_th (kV) | Read | Nodes | Polygons | Duplicates dropped | With tag | Inferred | Excluded (no voltage) | Below V_th | Eligible (pass V_th) |
|---|---|---|---|---|---|---|---|---|---|---|
| BRA | 138 | 8666 | 9 | 8653 | 4 | 2102 | 4889 | 1671 | 3099 | 3892 |
| IND | 220 | 17104 | 215 | 16841 | 48 | 9456 | 1161 | 6439 | 7378 | 3239 |
| PRT | 150 | 16112 | 676 | 15433 | 3 | 3177 | 461 | 12471 | 3325 | 313 |
