# Effect of the exact population sum on the F3 results of IND (COMMANDS 89 and 91)

D-F2a-026 replaced the GDAL `Resampling.sum` of the population by the exact area-weighted sum. In IND the GDAL raster was wrong in **one pixel column (731)**: the source pixel edges fall 0.4996 to 0.4998 of a source pixel into one, GDAL resolved them by the origin of its warp chunk and the pixels of that column took about 8% too few people (2,265 pixels, rows 101 to 2,377, up to 729 people, 21%). The new raster equals the exact sum; the total of the country rises by 62,027 people (4e-5). BRA has the same cause on four columns and 923 pixels out of tolerance (at most 2.9 people), and no F3 result moved.

## What changed in the F3 of IND, against the output of 2026-11-02 (`backup_before_89/IND_elig`, F3 as it was before the cold round)

Where E6 (population density above the maximum) flips, the eligible fraction changes. Everything that differs is in that column:

| Artifact | Difference |
|---|---|
| `eligible_fraction_*` (6 rasters, 2,750 x 2,930 pixels) | 80 to 113 pixels each, **all in pixel column 731** |
| `eligible_area_km2_*`, `dominant_exclusion_*` (cell rasters, 549 x 586) | 82 to 86 and 4 to 5 cells, **all in cell column 146** (pixel column 731 / 5) |
| `cells_0p1deg_*` | 75 of 28,707 cells |
| `candidate_stability_*` | at most 70 cells change area; 2 (solar) and 5 (wind) cells are no longer candidates in any scenario; none enters |
| cells and candidates tables | the 91 cells of cell column 5109 of the global lattice change area, `candidate` and the eligible-area weighted means (`elevation_m` up to 131 m); candidates that left: solar 2 / 2 / 3 and wind 5 / 5 / 3 (central / permissive / restrictive), none entered |
| `dominant_exclusion` label | changes in 29 cells of wind permissive and a few in the other scenarios, with no area change beyond tolerance (ties between exclusions of nearly equal area) |
| the other columns of the tables | last bit of a float only (at most 9.5e-7), no cell enters or leaves |
| the summary `land_eligibility.json` | the counts of candidates and the areas that follow from the above |

The analysis was made row by row on the six solar and the six wind tables joined on `cell_id` (COMMAND 89) and, for the rasters and the stability and coarse tables, on 2026-11-04 (`scratchpad/ind_regions.py`).

## What the deferred check does with it

These 15 artifacts differ from the manifest of 2026-10-29 and are explained by this document; they are listed in `expected` of IND in `config/deferred_checks.yaml`. The same check against the round kept in the reference store on 2026-11-04 has no difference.
