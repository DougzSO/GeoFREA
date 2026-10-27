# Display resolution of the maps (COMMAND 67b)

Branch `feat/display-resolution`. Decision record: D-core-047. Method: METHODOLOGY 15.2.4, section 11. Nothing in the analysis changes: no total, no LCOE, no analysis artifact, no figure under `GEOFREA_DATA_DIR/outputs/`.

## What changed

| Step | What |
|---|---|
| 2 | `MapFigure.px_per_cell(cell_deg)` counts the image pixels along one side of an analysis cell for the preset, the country and the width (`plan_display`). Above 4 it uses the finest display layer available. |
| 3 | `technical_potential/display_layers.py`: the 0.01° display layers (capacity factor by the F5 model itself, eligible fraction, capacity density, energy density), `display_<layer>_<tech>.tif` with `display_layers_<tech>.json` (own fingerprint, checks). `potential_maps` reads them when they exist. |
| 4 | `viz/display.py`: masked bilinear smoothing (normalised convolution), only for continuous fields; the subtitle says `display smoothing (source: <resolution>)`; `absolute_maps.display_smoothing: auto \| off` in `experiments.yaml` (default `auto`). |
| 5 | Neighbours are cut by the rectangle of the map (`clip_by_rect`), and the gap between two sources of border (GADM against Natural Earth) is closed with the colour of the neighbours. |
| 6 | The scale note is `Scale: 2nd–98th percentile`, `Scale: fixed` or `Scale: shared`, only when the scale cuts values; the numeric limits stay in the PNG metadata (`geofrea_scale_limits`). |
| 7 | The synthetic fields are a smooth trend plus correlated waves (3 cells and longer) and a small noise per pixel; the 0.05° and 0.01° layers are the same field. |

## Before and after (synthetic data, the same field)

Images archived in `GeoFREA_data/archive/docs_figures_67b` (before and after of PRT, LUX, CHE and BRA).

"Before" is the 0.05° cells as they are (`fine=False`, `display_smoothing="off"`); "after" is what the figure draws now.

| | Before | After | What was done |
|---|---|---|---|
| PRT, thesis | `PRT_before.png` | `PRT_after.png` | 11.7 px per cell → the 0.01° display layer (2.3 px): no smoothing needed |
| LUX, article_single | `LUX_before.png` | `LUX_after.png` | 25.8 px per cell → 0.01° layer (5.2 px, still above 4) → display smoothing |
| CHE, article_single | `CHE_before.png` | `CHE_after.png` | climate delta (a GCM field, no fine layer) → display smoothing from the 0.05° grid |
| BRA, thesis | `BRA_before.png` | `BRA_after.png` | 1.6 px per cell: nothing to do, identical |

The four examples of `docs/figures/examples/` were regenerated; CHL and IDN (classes and states, never smoothed) were not, as asked.

## Checks

| Check | Where | Result |
|---|---|---|
| Pixels per cell ≤ 4, or the subtitle declares the smoothing, for density, capacity factor and climate delta in the six archetypes (18 figures) | `test_display_resolution.py` | pass |
| No colour outside the country or in the middle of a no-data hole after smoothing | same | pass |
| Smoothed values stay between the smallest and the largest data value (no 0 leaks in) | same | pass |
| 0.01° → 0.05° aggregation: CF weighted by the eligible area within 1% in every cell; eligible area and capacity exact (1e-6, float32 of the stored rasters); a wrong analysis (5% CF, 1% area) is refused | same | pass |
| Classes, categories and states identical pixel by pixel with `auto` and `off` (PRT and LUX eligibility, IDN and CHE state) | same | pass |
| Neighbours inside the rectangle of the map and reaching its sides | same | pass |
| Perceptual-hash goldens (archetypes and style examples) refrozen after looking at the figures | `tests/fixtures` | refrozen |

## Limits (stated, not hidden)

- **Wired in COMMAND 70.** `potential_maps` builds the layers when the px-per-cell rule asks for them (PRT) and refuses, by layer, one that fails the aggregation check. See `docs/figures/display_layers_70.md`.
- The smoothing keeps the border of the data at the edge of the cells, so a thin strip of a coastal cell whose centre is outside the polygon stays empty (white, or the grey of "no potential").
- The gap between neighbours and country is closed up to 8 km; a larger mismatch of two border sources still shows white. The archetype fixtures have no Liechtenstein, so a small white sliver remains in the example of CHE.
- The real F5 PNGs keep their old look until the phase is rerun; no file in `outputs/` was touched.
