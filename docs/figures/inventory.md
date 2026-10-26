# Figure inventory (COMMAND 56)

Every figure that the code or the repository scripts draw today, as of `main` at the start of COMMAND 56. Source: all of `src/` that calls matplotlib (13 modules), the PNG files under `GEOFREA_DATA_DIR/outputs/<ISO>/**/figures*` (size and dpi read from the files, read only) and `scripts/plot_plants_over_grid.py`. Nothing in this inventory was changed. The module that will replace the duplicated parts is `src/geofrea/viz/mapstyle.py` (`docs/figures/style_guide.md`).

Types: **raster** = continuous raster, **classes** = classified raster or choropleth with a legend, **choropleth** = admin1 units coloured by a value, **chart** = not a map. "Compass" and "scale" say whether the figure has a compass rose and a scale bar. "Aspect" is how the axes are scaled; "extent" is how the limits are computed.

## 1. Maps by phase

| # | Figure (file) | Module and function | Phase | Type | Colormap | Size (px) at dpi, in | Compass / scale | Aspect | Extent |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `climate_forcing/figures/<ISO>_<member>_<ssp>_<window>.png` (36 per country) | `climate_forcing/maps.py::plot_member` | F4 | raster, 3 panels (radiation ratio, wind ratio, dT) | `RdBu`, `RdBu`, `YlOrRd`; limits P1-P99 shared by all members, ratios symmetric about 1 | 1650x572 at 110 (15 x 5.2) | none / none | `equal` (set by `imshow`): a degree of longitude is drawn as long as a degree of latitude | bounds of the cell lattice of the member (`lattice_bounds`), no geometry, no margin |
| 2 | `overview/figures/<ISO>_aligned_layers.png` | `overview/figures.py::plot_aligned_layers` | overview | raster, 12 panels (3x4) | per panel: `terrain`, `magma`, `tab20`, `viridis` (log), `Blues`, `YlGnBu`, `YlOrBr`, `YlOrRd` x2, `viridis`, `cividis`, `plasma` | 1800x1300 at 100 (18 x 13) | arrow "N" and scale bar (`style.draw_overlay`) / yes | `1/cos(central lat)` in `draw_overlay` | raster bounds |
| 3 | `overview/figures/<ISO>_eligibility.png` | `overview/figures.py::plot_eligibility` | overview | raster + classes (2 x technologies) | `YlGn`; `ListedColormap` of 7 exclusion classes | 1400x1300 at 100 | arrow "N" and scale bar / yes | `1/cos` via `draw_overlay` | cell lattice bounds |
| 4 | `overview/figures/<ISO>_hazard_context.png` | `overview/figures.py::plot_hazard_context` | overview | raster, 6 panels | `YlOrRd`, `RdBu_r`, `Blues`, `RdBu`, `PuBu`, `viridis` | 1600x1000 at 100 | arrow "N" and scale bar / yes | `1/cos` via `draw_overlay` | raster bounds |
| 5 | `overview/figures/layers/<layer>__na__na__na.png` (distance to grid, to road; eligible share; excluded share E1-E6, per technology; 6 + 12 + 18 per country) | `overview/layer_maps.py::_draw` (called by `build_layer_maps`, `_cost_map`) | overview | raster | `viridis` (distances), `YlGn` (shares) | about 600x700 to 800x600 at 130 (7 x 6, tight) | none / none | `equal` (set by `imshow`) | cell lattice bounds or raster bounds |
| 6 | `overview/figures/<ISO>_gem_plants_over_grid.png` (IND, PRT) | `scripts/plot_plants_over_grid.py` | overview (script, not in `src/`) | raster + points | `Greys` | 1000x1000 at 100 (10 x 10) | none / none | `equal` | raster bounds |
| 7 | `technical_potential/figures/potential_density_<tech>__ref__na__na.png`, `capacity_factor_<tech>__ref__na__na.png` | `technical_potential/maps.py` -> `land_eligibility/map_raster.py::plot_grid` | F5 | raster | `viridis` (density), `magma` (CF); no norm, min-max limits | 735-908 x 731-814 at 150 (7 x 6, tight) | none / none | `equal` | cell lattice bounds (`cell_grid`) |
| 8 | `technical_potential/figures/potential_capacity_mw_cell_<tech>_central__ref__na__na.png`, `potential_energy_gwh_cell_...` | `technical_potential/absolute_maps.py::_plot_cells` | F5 | classes (7 quantile classes of the values above zero) | `cfg.palette` = `viridis` sampled at the class count; no-value cells `#d9d9d9` | 1855-2339 x 1762 at 300 (8 x 6.5, tight) | none / none | `equal` | cell lattice bounds |
| 9 | `technical_potential/figures/potential_capacity_gw_state_<tech>_<scenario>__ref__na__na.png`, `potential_energy_twh_state_...` (6 per technology) | `technical_potential/absolute_maps.py::_plot_states` | F5 | choropleth (6 Fisher-Jenks classes of the central state totals, last class open) | `viridis` | 1866-1942 x 1762 at 300 | none / none | `equal` | bounds of the admin1 geometry (matplotlib autoscale) |
| 10 | `technical_potential/figures_run_report/potential_<tech>__<scenario>.png` (**moved on 2026-10-20, COMMAND 59, to `GEOFREA_DATA_DIR/archive/figures_20261020/<ISO3>/technical_potential/figures_run_report/`**) | no producer in `src/` or `scripts/` (written by an ad hoc script that is not in the repository; cited in `docs/phases/F5/run_report_real.md`) | F5 | raster | not recorded | 1210x550 at 110 | not recorded | not recorded | not recorded |
| 11 | `lcoe_modeling/figures/lcoe_nominal_<tech>__ref__na__na.png` and, with `figures: all`, quantile and SSP maps | `lcoe_modeling/maps.py::build_lcoe_maps` -> `plot_grid` | F6 | raster | `viridis_r` | 150 dpi, 7 x 6 tight (F6 has no real run, no file in outputs) | none / none | `equal` | cell lattice bounds |
| 12 | thesis maps: LCOE, regret, climate change (3 SSP panels with stippling), potential and cost rasters | `results_synthesis/maps.py::draw_grid` (+ `climate_change.py::t_r3`, `potential_and_cost.py::_map_of_a_raster`, `ranking_figures.py::t_r4`) | F8 | raster | `RdBu` (climate change), `viridis`, `viridis_r`, `magma_r` | 6.3 in wide (160 mm), 200 dpi; PNG and PDF (`style.save_figure`) | none / none | `equal`; height from `map_aspect(grid)` = grid rows over columns, not geographic | grid bounds from the lattice |

## 2. Charts (not maps)

| Figure | Module and function | Phase | Type | Size | Notes |
|---|---|---|---|---|---|
| supply curve `supply_curve_<tech>.png` | `lcoe_modeling/maps.py::_supply_curve_figure` | F6 | chart | 7 x 5 in, 150 dpi, tight | |
| DAG of the pipeline (T-M1) | `results_synthesis/dag.py::t_m1` | F8 | chart | 6.3 x 1.6 in wide, 200 dpi | |
| T-O3 supply curves, T-R5 ranking and bars, T-R7 d_clim bars, T-O2 scatter, T-O1 bounds, T-R4 box plots | `potential_and_cost.py::t_o3`, `ranking_figures.py::t_r5`, `robustness_tables.py::t_r7`, `::t_o2`, `::t_o1`, `ranking_figures.py::t_r4` (right panel) | F8 | chart | `style.new_figure` / `style.plt.subplots`, 6.3 in wide x fraction, 200 dpi | one look from `results_synthesis/style.py` (DejaVu Sans 8 pt, title 9 pt) |

## 3. What each family looks like today

- **Fonts.** F8 sets 8 pt body, 9 pt title, DejaVu Sans (`results_synthesis/style.py`). Every other module sets sizes by hand and in points of a figure that is scaled when the PNG is used (titles 9-11 pt, labels 7-8 pt, legend 7 pt) on figures of 7 to 18 in: a 15 in figure shrunk to the 190 mm page (7.5 in) shows its 8 pt text at about 4 pt.
- **Sizes and dpi.** Many different sizes (in the table above) and six dpi values (100, 110, 130, 150, 200, 300) among the PNG files. Only F5 per-cell and per-state maps are at 300 dpi. None is in print millimetres.
- **Degrees.** Axis labels are `Longitude (deg)` and `Latitude (deg)` with plain numbers; the format `40°S` exists only in `craei-brazil`.
- **Aspect.** `imshow` forces `equal`, so the maps are stretched at every latitude except 0, except where `overview/style.py::draw_overlay` sets `1/cos` afterwards (figures 2-4); items 1, 5, 6, 7, 8, 9, 11 and 12 stay `equal`.
- **Extent.** From the cell lattice, the raster bounds or matplotlib autoscale. No figure takes it from the country geometry; the 3% margin and the exclusion of far islands do not exist. With the contiguous mask (COMMAND 55) the lattice no longer includes the far islands, but that is a property of the mask, not of the figure code.
- **Neighbours and sea.** No figure draws the neighbouring countries. The sea is white by the absence of data.
- **Compass and scale.** Only the three overview figures that call `draw_overlay` (2, 3, 4) have them, fixed at the lower left (scale bar) and upper right (arrow), without checking what lies there; the scale bar's length is a quarter of the width rounded down.
- **Colormaps.** No rule. Potential and energy use `viridis` (config `palette`), CF `magma`, LCOE `viridis_r`, ratio deltas `RdBu`, temperature change `YlOrRd` in F4 and `RdBu_r` in the hazard figure for the same kind of variable (a change).
- **Colour limits.** Min-max (F5 rasters, overview layers), P1-P99 (F4), quantile or Fisher-Jenks classes (F5 absolute maps), log of the values (population panel). No colorbar `extend`.
- **Titles.** Free text of 40 to 90 characters with the scenario and totals inside (`absolute_maps.py`: `<ISO> <tech>, reference climate, central land scenario: installable capacity per cell\nNational total ... GW`).
- **Output.** PNG; F8 also PDF. Saves use `bbox_inches="tight"`, so the figure size in pixels depends on the content.

## 4. Duplicated patterns

| Pattern | Where | Count |
|---|---|---|
| Place a lattice of cells on lon/lat (`CELL_ORIGIN_LON + col0 * cell`, `north - row0 * cell`) and compute the extent | `absolute_maps._plot_cells`, `map_raster.plot_grid`, `climate_forcing/maps.plot_member`, `overview/layer_maps._cell_grid`, `results_synthesis/maps.grid_extent`/`table_grid` | 5 |
| `imshow(np.ma.masked_invalid(grid), extent, origin="upper", cmap, vmin, vmax)` + `set_title` + `Longitude (deg)`/`Latitude (deg)` + `colorbar(shrink=0.8-0.85)` + `savefig(dpi, bbox_inches="tight")` + `plt.close` | `map_raster.plot_grid`, `overview/layer_maps._draw`, `results_synthesis/maps.draw_grid`, `climate_forcing/maps.plot_member` | 4 |
| A scale bar computed from the central latitude with a rounded length | `overview/style._scale_bar` (1, 2, 5, 10, ... list) | 1 in the repository; a second, better one in `craei-brazil` |
| A north arrow | `overview/style.draw_overlay` | 1 (a single arrow, not a rose) |
| Class limits, quantile and Fisher-Jenks, with rounding to significant figures | `technical_potential/absolute_maps.class_breaks` only | 1 (not duplicated, but not reusable by other modules) |
| The country outline from the `_0_mainland.shp` file | `overview/style.country_outline`, `absolute_maps` (union of admin1 units) | 2 different sources of the same border |
| `matplotlib.use("Agg")` at import | `absolute_maps`, `climate_forcing/maps`, `results_synthesis/style` and others | several |
| A list of per-panel `(column, title, cmap, kind)` tuples | `climate_forcing/maps.PANELS`, `overview/figures.ALIGNED_PANELS`, `HAZARD_PANELS` | 3 |
| Percentile limits | `climate_forcing/maps.color_limits` (P1-P99) | 1 |
| Fonts, sizes and `rc` | `results_synthesis/style._RC` and hand-set `fontsize=` in most of the other modules | many places | |

## 5. What `mapstyle` replaces, when a figure is migrated

Items 1-5, 7-9, 11 and 12 of section 1 draw one map on one axes and can move to `mapstyle.raster_map` or `mapstyle.new_map`; items 2-4 and 12 have several panels and need a panel layout that `mapstyle` does not have yet (COMMAND 56 does not migrate any figure). Items 6 and 10 are outside `src/`. The class-based legends of items 8-9 will use the legend slot of the canvas (`canvas.cax`) with a patch legend instead of a colour bar.

**COMMAND 66.** `mapstyle.py` is now `MapFigure` with a fixed layout, presets, the semantic palette and scales, title rules, file names and PNG metadata (`docs/figures/style_guide.md`, D-core-045). The figures listed above were not redrawn.

## 6. After COMMAND 68

Every figure of sections 1 and 2 except the thesis figures of F8 (item 12) and the audit charts of `scripts/audit_potential.py` now goes through `viz/` (`MapFigure`, `PanelFigure`, `charts`); items 2-9 and 11 were moved by family, one commit each, and the three real countries were redrawn. The old files are in `GEOFREA_DATA_DIR/archive/figures_20261026/`. The static test `tests/unit/test_no_maps_outside_mapfigure.py` keeps `matplotlib.pyplot` inside `viz/` and in those two places. What was drawn, per country and phase, with one before/after pair per family, is in `docs/figures/migration_68.md`.
