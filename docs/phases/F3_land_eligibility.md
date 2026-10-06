# F3 land_eligibility

Status: `in_progress`
Methodology items: M-F3-01 to M-F3-06, U-06, V-07

## Contract

Requires: `siting_layers`, parameters, land-availability variants. Produces: `candidates_<tech>.parquet`, pixel and cell eligibility COGs, dominant-exclusion COG, 0.1 degree aggregation for V-07.

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|
| M-F3-01 | Pixel eligibility = NOT (E1..E6) AND required layers valid | `land_eligibility/cells.py:pixel_eligibility` (kernel; real E layers come from F2b/H-3) | `tests/unit/test_land_eligibility_cells.py` | partial |
| M-F3-03 | 5 x 5 pixel aggregation: geodesic cell/eligible/excluded areas, dominant exclusion, area-weighted resource and distance means, flag share | `cells.py:aggregate_to_cells`, `pixel_row_area_km2` (kernel on synthetic grids) | same | partial |
| M-F3-04 | Candidate filter by `min_eligible_area_km2` | `cells.py:candidate_cells` | same | partial |
| M-F3-05 | Stable `cell_id` | `cells.py:cell_id`, `cell_row_col`, `cell_center` (global lattice, D-F3-001) | same | pass (id); parquet/COG outputs not built |
| M-F3-06 | 0.1 degree aggregation (V-07) | `cells.py:coarse_cell_id` (index only; aggregation pending I-3) | same | partial |

## Active implementation decisions

- **D-F3-001 — `cell_id` is a global lattice index, with `row`, `col` and the cell center stored beside it (2026-10-06, Douglas's verdict).** The decision unit is a 0.05 degree cell (S-06, 5 x 5 pixels of the 0.01 degree grid, M-F2a-01). Cells live on one global lattice anchored at the north-west corner (90 N, 180 W): `row` counts southward, `col` eastward, `cell_id = row * 7200 + col` (3600 x 7200 = 25,920,000 ids, fits int32). Output tables carry `cell_id`, `row`, `col`, `lat_c`, `lon_c` (M-F3-05 only requires the id; the other columns are for joins and human reading). Why this and not another indexing: (a) the id is an identifier only and changes no number in any result; what it governs is joins between phases, reruns, the order used to break ties, and traceability. (b) A country-bounding-box index would renumber a country whenever its polygon or extent changes (the PRT `mainland_only` change of 2026-10-06 would have renumbered every PRT cell) and would not be comparable across countries. (c) A string of center coordinates is stable but heavy and fragile as a join key. (d) A Morton/Z-order code adds spatial locality that nothing here needs. (e) The anchor (90, -180) is an exact multiple of 0.05 (1800 and -3600 steps), so the 0.01 pixels nest 5 x 5 and the 0.1 degree V-07 cells nest 2 x 2 in the same index (`coarse_cell_id`). All arithmetic is on integers (rounded step counts), never on compared float coordinates. A cell on a border has the same id in both countries; the key is (country, `cell_id`), and each country's `cell_area_km2` is its own land area inside the cell. Implementation: `src/geofrea/land_eligibility/cells.py`. The grid it aggregates must be the F2a grid snapped to the 0.05 lattice (`GridNotOnLatticeError` otherwise).

## Known issues

None yet.

## History

None.
