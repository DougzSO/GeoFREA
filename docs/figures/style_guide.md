# Map style guide (COMMAND 56)

One module draws every map: `src/geofrea/viz/mapstyle.py`. This guide says what it does and why; the examples are drawn by `scripts/make_style_guide_examples.py` from invented countries (`src/geofrea/viz/examples.py`), not from results. No existing figure uses the module yet (`docs/figures/inventory.md`).

| Tall country, 190 mm | Wide country, 190 mm | Small country, 90 mm |
|---|---|---|
| ![tall](examples/example_tall.png) | ![wide](examples/example_wide.png) | ![small](examples/example_small.png) |

## Rules

| # | Rule | In the module |
|---|---|---|
| a | Print sizes in millimetres: 190 mm (full page) and 90 mm (half column). The height follows the aspect of the extent (at most 230 mm: a very tall country gets a narrower map in the same width). The legend goes to the right of a tall map (height over width above 1) and below a wide one. | `FULL_WIDTH_MM`, `HALF_WIDTH_MM`, `compute_layout`, `legend_position` |
| b | Fonts are set at the final print size: title 10 pt, labels 8 pt, legend 8 pt, one sans family (DejaVu Sans). The figure has its exact print size (an overlay axes with 1 unit = 1 mm), so a point is a point. Degrees read `40°S`, `50°W`. | `TITLE_PT`, `LABEL_PT`, `LEGEND_PT`, `format_degrees` |
| c | Geographic aspect for lon/lat maps: `1 / cos(central latitude)`. `imshow` resets the aspect to 1, so `raster_map` passes it to `imshow`. | `geographic_aspect`, `map_height_over_width` |
| d | The extent comes from the geometry of the country plus 3% on each side. The geometry is first reduced to the contiguous territory (METHODOLOGY 15.2.0: largest polygon plus the polygons touching it or within 1 km), so an ocean island (Trindade, Fernando de Noronha) never stretches the map. | `country_extent`, `contiguous_geometry` |
| e | Compass rose (8 triangles) and scale bar go to the corner of the map with the least occupancy: for each of the four corners, the share of the box that holds data pixels and the share that lies inside the country polygon; the larger counts. A corner is free at or below 1%. Elements may share a free corner (stacked). With no free corner the element goes outside the map (the compass at the right of the header, the others in a footer strip) and never over data. The scale bar is calculated at the central latitude, rounded to 1, 2 or 5 x 10^n km (the closest to 20% of the map width, so between 12% and 32%). | `place_furniture`, `occupancy`, `draw_compass`, `draw_scale_bar`, `scale_bar_length_km` |
| f | Neighbouring countries in very light grey (`#ececec`), the sea white. | `new_map(neighbours=...)` |
| g | One colormap per kind of variable, the same in every country: `viridis` for potential and energy, `magma` for capacity factor, `RdBu` (or `BrBG`) centred on zero for climate deltas (ratios centred on 1 with `diverging_center=1`). | `COLORMAPS`, `colormap_for` |
| h | Continuous variables: limits at the 2nd and 98th percentiles; a logarithmic norm when P98 / P50 is above 20 (a power norm with exponent 0.5 if the lower limit is not positive, as when many cells are zero); the colour bar gets `extend` arrows where values lie outside. Diverging variables are symmetric about the centre. | `robust_norm`, `NormInfo` |
| i | PNG only, 300 dpi, exact print size (no `bbox_inches="tight"`): 190 mm is 2244 px. | `save_png` |
| j | Titles are short: `<ISO> · <Technology> · <Variable>` (10 pt, bold). The scenario and the climate go on a second, smaller line (8 pt). The national total goes in a discreet text box in a free corner of the map, not in the title. | `format_title`, `new_map(subtitle=, total_text=)` |

## Use

```python
from geofrea.viz import mapstyle as ms

canvas = ms.raster_map(
    grid, grid_extent, country_geometry,          # grid: 2-D array, NaN = no data; geometry in lon/lat
    iso="BRA", technology="Solar PV", variable="Installable capacity",
    label="MW per cell", kind="potential",
    subtitle="Central scenario · reference climate",
    total_text="National total\n19,189 GW", width_mm=ms.FULL_WIDTH_MM,
    neighbours=neighbours_gdf,
)
ms.save_png(canvas, "potential.png")
```

`new_map(...)` gives the axes (`canvas.ax`), the legend slot (`canvas.cax`) and the title and furniture without drawing data, for classes or choropleth maps: draw on `canvas.ax` and fill `canvas.cax` with a legend.

## Classed maps, circles and the resolution of the potential maps (COMMAND 60)

`mapstyle` also draws what the maps of `potential_maps` need beyond a continuous raster:

| Piece | In the module | Rule |
|---|---|---|
| Choropleth with classes | `draw_choropleth`, `draw_classed_legend`, `ClassedLegend` | The classes come from the data (`absolute_maps.class_breaks`), the same in every map of a variable; the legend lists the intervals (the last one open, "> limit"), a "no potential" entry in the grey of the style, and its title is the unit. The legend takes the strip to the right of a tall map and a row below a wide one; `legend_space` says how much room it needs and `new_map(legend_side_mm=, legend_below_mm=)` reserves it. |
| Proportional circles | `circle_radius_mm`, `draw_circles`, `nice_values_below` | The **area** of a circle is proportional to the value (radius with the square root); the largest circle has a radius of 9 mm on paper (`CIRCLE_MAX_MM`) and one reference value is used for every map of the same quantity, so that scenarios can be compared; a positive value is never smaller than 0.35 mm. The legend shows three round values (1, 2 or 5 times a power of ten, a tenth of each other). Circles are drawn largest first, semi-transparent, over the choropleth, at a point inside the largest part of the unit. |
| Furniture | `new_map` | The compass, the scale bar and the total box are placed on the layout the map is drawn on; a footer strip for an element that finds no free corner shrinks a map limited by the height of the sheet, and the placement is repeated on the new layout (before, a compass placed in the upper left corner of the larger map could end up above the smaller one). |

**Resolution of the potential maps.** The cell of the analysis is 0.05 degree: the eligible share (F3), the capacity factor and the potential (F5) are defined per cell of this size, and the maps draw **one pixel per cell** with `interpolation="nearest"`. Nothing is interpolated, smoothed or resampled, and no map is drawn finer than its data. The coarse look of a small country (PRT: about 90 x 70 cells) is therefore the real resolution of the analysis, not a defect of the figure; a finer picture would need a finer cell in F2a-F3 (a change of `scale.cell_deg`, which changes the results, not the figures). The limits file of each technology records `resolution.cell_deg` and the way each colour scale was chosen.

**Density, not total.** Per cell the maps show capacity density (MW per km2) and energy density (GWh per km2 per year) over the land area of the cell inside the territory (`cell_area_km2` of F3); per state they show the same densities over the land area of the state (the sum of its cells), because a total per state is dominated by the size of the state; the totals (GW, TWh per year) are the circles. The classed maps of MW and GWh per cell of the earlier version are drawn only with `absolute_maps.per_cell: true`.

**Neighbours.** The neighbouring countries come from Natural Earth 1:50m (`scripts/acquire_natural_earth.py`, `raw/natural_earth/_global/`), cut to the window of the map and without the territory itself; when the file is missing the maps are drawn without neighbours and the log says so.

## Limits of this version

- One map per figure; state maps are full-page (190 mm): the long title and the 9 mm circles do not fit a half column. The overview and F4 figures with several panels (inventory section 1, items 2-4 and 1) need a panel layout that is not written.
- The 3% margin is applied to the contiguous territory; admin1 boundaries are not drawn by `new_map` (a choropleth draws its own units).
- Text widths used to size the furniture before drawing are an estimate (0.62 em per character); the tests measure the real boxes.
- Fonts depend on the DejaVu Sans that ships with matplotlib. A machine with another font set draws other pixel widths, so the visual regression allows a small difference (see below).

## Tests

`tests/unit/test_mapstyle.py` (44 tests):

- Extent without the far island, with 3%; aspect; degree labels; norms (linear, log, power, diverging, extend); colormaps; rounded scale-bar lengths; layout (right for tall, below for wide); PNG pixels and dpi; fonts.
- **Overlap**: for the tall, the wide and the small synthetic country, the real boxes of the compass, the scale bar and the total box (measured from the drawn artists, in millimetres) do not intersect the title, the legend (colour bar with its tick labels and name) or each other; those over the map have no data pixel and no polygon area under them; everything stays inside the figure.
- **Visual regression**: no `pytest-mpl` or `imagehash` is installed, so the test uses a 256-bit difference hash of the PNG (PIL and numpy) against `tests/fixtures/mapstyle/hashes.json` and allows 12 differing bits and 2 px of size. A removed compass changes the hash (checked). To refreeze after an intended change of the look: `GEOFREA_UPDATE_MAPSTYLE_BASELINES=1 pytest tests/unit/test_mapstyle.py`, then look at the three examples.

`tests/unit/test_mapstyle_classed.py` (23 tests): the circle scale (area proportional to the value, zero has no circle, a tiny value is still visible), the round legend values, the room the legend asks for; on a state map of each synthetic country (the far island inside one of the states): **no overlap** of the real boxes of the legend, title, compass, scale bar and total, **no circle** on any of them or on the legend, everything inside the figure, the extent without the island, the same circle scale for a reference, the legend holding every class, the "no potential" entry and the circle sizes; the perceptual-hash regression of the three state maps (`state_tall`, `state_wide`, `state_small` in `hashes.json`).
