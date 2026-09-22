"""Cartography for suitability_criteria (Fase 2b) — one PNG per criterion.

Ported from legacy geoworld_framework's src/processors/criteria_builder.py
(`CriteriaBuilder._plot_criterion_map`, L641-743). Reimplemented locally
and NOT routed through a shared/generic renderer — see
docs/architecture/suitability_criteria_audit.md sec 7 D7 (decision
2026-09-10): "cartografia da Fase 2b fica isolada por ora ... sem
estender o renderer genérico". No such renderer exists in GeoFREA yet
either way (legacy's GeoWorldStyler was never ported).

Deliberately narrower than legacy's GeoWorldStyler-backed original:
  - No segmented scale bar (GeoWorldStyler private helper, never ported
    — cartographic decoration, not scientific content). A compass rose
    WAS added 2026-09-14 (Douglas, D7 cartography pass) — see
    `_draw_compass_rose` — small nautical-style 8-point star, top-right
    corner, "N" only; reimplemented locally, not a GeoWorldStyler port.
  - No admin1 region labels — SuitabilityCriteriaInputs carries no
    admin_gdf (that boundary layer is not wired into this phase).
  - context_gdf (neighbouring countries) is accepted but is always None
    today (suitability_criteria/adapter.py does not populate it yet);
    handled the same way legacy does — silently skipped when absent.
Ported faithfully: basemap (mainland + optional context countries),
per-criterion colormap/vmax, the protected_areas overlay+legend special
case, colorbar, mean/std/IQR stats strip, title/subtitle, CRS footer.
`lakes_exclusion`/`river_solar`/`river_wind` moved to the same
categorical-legend treatment as `protected_areas` 2026-09-14 (see
`_CATEGORICAL_CRITERIA` — these are strictly {0, 1} criteria, not
faithful to legacy's own continuous-colorbar rendering of them, a
deliberate cartography-only improvement, not a scoring change).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from rasterio.transform import Affine

from geofrea.core.constants import NODATA_FLOAT

logger = logging.getLogger(__name__)

# criterion -> (title, unit, cmap_name, invert). Ported verbatim from
# legacy's configs/settings.yaml `visualization.criteria_meta` (L124-140).
# `proximity_plants` dropped — not a GeoFREA canonical criterion (see
# suitability_criteria/schemas.py::CANONICAL_CRITERIA). `slope_degrees`
# kept even though it is cartography-only, not a canonical criterion.
_CRITERION_META: dict[str, tuple[str, str, str, bool]] = {
    "solar_resource": ("Solar Resource (PVOUT)", "Potential (normalized)", "YlOrRd", False),
    "wind_resource": ("Wind Resource (Power Density)", "Potential (normalized)", "Blues", False),
    "terrain_score": ("Terrain Suitability (Slope + TRI)", "Score (0-1)", "RdYlGn", False),
    "lc_biomass": ("Land Cover Suitability - Biomass", "Score (0-1)", "RdYlGn", False),
    "biomass_resource": ("Biomass Resource (Yield by LC)", "Potential (normalized)", "Greens", False),
    "pop_suitability": ("Population Suitability", "Score (0-1)", "RdYlGn", False),
    "road_suitability": ("Proximity to Roads", "Score (0-1)", "RdYlGn", False),
    "slope_degrees": ("Slope", "Degrees", "YlOrRd", False),
    "protected_areas": ("Protected Areas Constraint", "Score (0-1)", "RdYlGn", False),
    "lakes_exclusion": ("Lakes Exclusion (HydroLAKES)", "Binary (0=lake, 1=ok)", "RdYlGn", False),
    "river_solar": ("River Buffer - Solar/Wind", "Score (0-1)", "RdYlGn", False),
    "river_wind": ("River Buffer - Wind", "Score (0-1)", "RdYlGn", False),
    "river_biomass": ("River Access - Biomass", "Score (0-1)", "Blues", False),
    "grid_suitability": ("Power Grid Proximity (OSM)", "Score (0-1)", "RdYlGn", False),
}

_COUNTRY_BORDER = "#1A1A1A"
_OCEAN_BG = "#D6EAF8"
_FIG_BG = "#F8F9FA"
_CTX_FILL = "#E8E8E8"
_CTX_EDGE = "#B0B0B0"
_RESTRICTED_COLOR = "#C0392B"  # legacy's CONTOUR_P90_COLOR, reused for the protected overlay
_FREE_TERRITORY_COLOR = "#E8E8E8"
_AVAILABLE_COLOR = "#27AE60"

# Criteria that are strictly {0, 1} by construction (see criteria_functions.py
# docstrings: lakes_exclusion is a hard lake/land mask, river_solar/river_wind
# are a riparian safety SETBACK, not a resource-quality gradient — confirmed
# 2026-09-14 both from code inspection, DECISIONS.md 2026-09-10 "suitability_
# criteria parameter calibration" ("promoted from soft criterion to hard
# exclusion... since it represents a safety setback, not a preference"), and a
# live comparison of the aligned distance raster against the raw HydroRIVERS
# vector confirming the mapped "speckle" is the real dendritic river network,
# not a rasterization artifact). A continuous colorbar over a value that only
# ever takes two values is misleading (implies gradation that doesn't exist),
# so these get the same categorical-legend treatment as protected_areas
# instead of _add_colorbar. criterion -> (label for score==1, label for
# score==0); color is always _AVAILABLE_COLOR / _RESTRICTED_COLOR.
_CATEGORICAL_CRITERIA: dict[str, tuple[str, str]] = {
    "lakes_exclusion": ("Land (available)", "Lake (excluded)"),
    "river_solar": ("Beyond river safety buffer (available)", "Within river safety buffer (excluded)"),
    "river_wind": ("Beyond river safety buffer (available)", "Within river safety buffer (excluded)"),
}

_BUF_TOP, _BUF_BOTTOM, _BUF_SIDES = 0.095, 0.105, 0.065
_TOP_IN, _BOT_IN, _LEFT_IN, _RIGHT_IN = 1.10, 2.0, 0.80, 1.55
_FIG_H_MAX = 24.0
_FIG_WIDTH_MIN = 10.0
_DPI = 150

# Criteria plotted with bilinear (vs. nearest) interpolation, matching
# legacy's own list (criteria_builder.py L703-707). proximity_plants is
# not a GeoFREA criterion but kept in the tuple for a faithful port.
_BILINEAR_CRITERIA = ("proximity_plants", "protected_areas", "solar_resource")


def _ax_bounds(
    minx: float, maxx: float, miny: float, maxy: float
) -> tuple[float, float, float, float]:
    lon_span, lat_span = maxx - minx, maxy - miny
    bt, bb, bs = _BUF_TOP * lat_span, _BUF_BOTTOM * lat_span, _BUF_SIDES * lon_span
    return minx - bs, maxx + bs, miny - bb, maxy + bt


def _create_figure(
    minx: float, maxx: float, miny: float, maxy: float
) -> tuple[plt.Figure, plt.Axes]:
    ax_minx, ax_maxx, ax_miny, ax_maxy = _ax_bounds(minx, maxx, miny, maxy)
    lat_ax, lon_ax = ax_maxy - ax_miny, ax_maxx - ax_minx
    mid_lat = (miny + maxy) / 2.0
    cos_lat = math.cos(math.radians(mid_lat))
    visual_aspect = (lat_ax / lon_ax) / cos_lat

    if visual_aspect < 0.85:
        map_width_in = max(_FIG_WIDTH_MIN, 13.5)
    elif visual_aspect < 1.10:
        map_width_in = max(_FIG_WIDTH_MIN, 11.5)
    else:
        map_width_in = max(_FIG_WIDTH_MIN, 10.0)

    map_height_in = map_width_in * visual_aspect
    max_h_allowed = _FIG_H_MAX - (_TOP_IN + _BOT_IN)
    if map_height_in > max_h_allowed:
        map_height_in = max_h_allowed
        map_width_in = map_height_in / visual_aspect

    fig_w = map_width_in + _LEFT_IN + _RIGHT_IN
    fig_h = map_height_in + _TOP_IN + _BOT_IN

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=_DPI)
    fig.patch.set_facecolor(_FIG_BG)

    ax = fig.add_axes(
        [_LEFT_IN / fig_w, _BOT_IN / fig_h, map_width_in / fig_w, map_height_in / fig_h]
    )
    ax.set_facecolor(_OCEAN_BG)
    ax.set_xlim(ax_minx, ax_maxx)
    ax.set_ylim(ax_miny, ax_maxy)
    return fig, ax


def _draw_basemap(
    ax: plt.Axes,
    crs: str,
    mainland_gdf: gpd.GeoDataFrame,
    context_gdf: gpd.GeoDataFrame | None,
) -> None:
    if context_gdf is not None:
        try:
            context_gdf.to_crs(crs).plot(
                ax=ax, color=_CTX_FILL, edgecolor=_CTX_EDGE, linewidth=1.0, zorder=1
            )
        except Exception as exc:  # noqa: BLE001 — context countries are map decoration only
            logger.debug("context_gdf basemap layer skipped: %s", exc)
    mainland_gdf.to_crs(crs).boundary.plot(
        ax=ax, color=_COUNTRY_BORDER, linewidth=1.5, zorder=5
    )


def _axes_center_x(fig: plt.Figure) -> float:
    map_axes = [a for a in fig.axes if not getattr(a, "_is_cbar_ax", False)]
    if not map_axes:
        return 0.5
    pos = map_axes[0].get_position()
    return pos.x0 + pos.width / 2.0


def _add_colorbar(fig: plt.Figure, im, unit_label: str) -> None:
    ax = im.axes
    pos = ax.get_position()
    cax_h = pos.height * 0.68
    cax_y = pos.y0 + (pos.height - cax_h) / 2
    cax = fig.add_axes([pos.x1 + 0.028, cax_y, 0.038, cax_h])
    cax._is_cbar_ax = True
    cbar = fig.colorbar(im, cax=cax, orientation="vertical")
    cbar.set_label(unit_label, fontsize=16.8, labelpad=12, fontweight="bold")
    cbar.ax.tick_params(labelsize=15)


def _add_title(fig: plt.Figure, title_main: str, title_sub: str) -> None:
    top_margin_frac = _TOP_IN / fig.get_figheight()
    ax_top = 1.0 - top_margin_frac
    y_main = ax_top + top_margin_frac * (0.60 if title_sub else 0.45)
    fig.text(
        0.5, y_main, title_main, ha="center", va="center",
        fontsize=26.4, fontweight="bold", color="#1A1A1A", transform=fig.transFigure,
    )
    if title_sub:
        y_sub = y_main - top_margin_frac * 0.35
        fig.text(
            0.5, y_sub, title_sub, ha="center", va="center",
            fontsize=20.4, fontweight="bold", color="#444444", transform=fig.transFigure,
        )


def _add_footer(fig: plt.Figure, crs_metadata: str) -> None:
    fig.text(
        0.98, 0.015, crs_metadata, ha="right", va="bottom",
        fontsize=11, color="#888888", style="italic", transform=fig.transFigure,
    )


def _add_stats_strip(fig: plt.Figure, valid_data: np.ndarray) -> None:
    ax_cx = _axes_center_x(fig)
    text = (
        f"Valid pixels: {len(valid_data):,}  |  "
        f"Mean: {valid_data.mean():.3f} +/- {valid_data.std():.3f}  |  "
        f"IQR: {np.percentile(valid_data, 25):.3f}-{np.percentile(valid_data, 75):.3f}"
    )
    fig.text(ax_cx, 0.025, text, ha="center", fontsize=21.6, color="#222222", transform=fig.transFigure)


def _apply_decorations(ax: plt.Axes, minx: float, maxx: float, miny: float, maxy: float) -> None:
    is_geographic = abs(minx) <= 180 and abs(maxy) <= 90
    mid_lat = (miny + maxy) / 2.0
    cos_mid_lat = math.cos(math.radians(mid_lat)) if is_geographic else 1.0
    ax.set_aspect(1.0 / cos_mid_lat if is_geographic else 1.0, adjustable="box")
    ax.set_xlabel("Longitude", fontsize=19.2, labelpad=8, color="#333333")
    ax.set_ylabel("Latitude", fontsize=19.2, labelpad=8, color="#333333")
    ax.tick_params(labelsize=16.8, colors="#333333", width=1.2, length=4)
    ax.grid(False)


def _make_cmap(name: str, reverse: bool) -> mcolors.Colormap:
    full_name = name + "_r" if reverse else name
    return plt.get_cmap(full_name).with_extremes(under="none", bad="none")


def _compass_spike(angle_rad: float, length: float, half_width: float) -> list[tuple[float, float]]:
    """Vertices of one kite-shaped compass-rose spike, tip at `angle_rad`.

    A slender dart from the center out to `length` at `angle_rad`, with
    shoulders (width `half_width`, perpendicular to the spike) placed a
    short way out from the center — the shape a compass rose's points
    are conventionally drawn as, not a plain triangle from the full
    base.
    """
    ux, uy = math.cos(angle_rad), math.sin(angle_rad)
    px, py = -uy, ux
    shoulder_t = 0.09 * length
    tip = (length * ux, length * uy)
    right = (shoulder_t * ux - half_width * px, shoulder_t * uy - half_width * py)
    left = (shoulder_t * ux + half_width * px, shoulder_t * uy + half_width * py)
    return [(0.0, 0.0), right, tip, left]


# 8 directions, starting North and going clockwise: (angle_deg, is_cardinal).
# Cardinal (N/E/S/W) spikes are longer and wider than the intercardinal
# (NE/SE/SW/NW) ones — the classic compass-rose distinction Douglas asked
# for, 2026-09-14 (see DECISIONS.md same date, compass rose redesign).
_COMPASS_DIRECTIONS: tuple[tuple[float, bool], ...] = (
    (90, True), (45, False), (0, True), (315, False),
    (270, True), (225, False), (180, True), (135, False),
)
_COMPASS_CARDINAL_LEN, _COMPASS_CARDINAL_HALF_W = 0.92, 0.10
_COMPASS_INTER_LEN, _COMPASS_INTER_HALF_W = 0.52, 0.05


def _draw_compass_rose(fig: plt.Figure, ax: plt.Axes) -> None:
    """Small nautical-style 8-point compass rose, top-right corner of the map.

    A fixed-size (physical-inch) inset Axes with its own equal-aspect
    data space, positioned just inside `ax`'s own top-right corner —
    independent of `ax`'s data aspect (lon/lat maps are rarely square
    in display space, so a rose drawn directly in `ax.transAxes` would
    come out visibly stretched). Marked `_is_cbar_ax = True` (reusing
    `_add_colorbar`'s flag, not a real colorbar) so `_axes_center_x` —
    which centers the stats strip under the map, not under this
    decoration — skips it, same as it already skips the real colorbar
    axes.

    2026-09-14 redesign (Douglas): the first version (i) clipped the
    "N" label against the map's own top edge — its ylim was [-1, 1],
    same as the star's own radius, leaving the label (placed just
    outside that radius) no room inside the inset axes' data space —
    and (ii) drew a plain 8-point star with all spikes the same size.
    Fixed here by reserving explicit headroom in `ylim` for the label
    (so it is genuinely inside the inset's own data space, not just
    "not clipped by luck") and by giving the 4 cardinal spikes (N/E/S/W)
    a distinct longer/thicker shape from the 4 intercardinal ones —
    the "clean/modern" compass-rose style (outlined ring + a thicker
    cross over thinner diagonals), chosen over a vintage multi-ring
    rose as the simpler one to render legibly at this small a size.
    """
    r = 1.0
    label_headroom = 0.85
    xlim = (-1.15, 1.15)
    ylim = (-1.15, 1.15 + label_headroom)
    x_span, y_span = xlim[1] - xlim[0], ylim[1] - ylim[0]

    pos = ax.get_position()
    fig_w_in, fig_h_in = fig.get_size_inches()
    width_in = 0.55
    height_in = width_in * (y_span / x_span)
    margin_in = 0.16  # clearance from the map's own top/right edge

    x0 = (pos.x1 * fig_w_in - width_in - margin_in) / fig_w_in
    y0 = (pos.y1 * fig_h_in - height_in - margin_in) / fig_h_in
    rose_ax = fig.add_axes([x0, y0, width_in / fig_w_in, height_in / fig_h_in])
    rose_ax._is_cbar_ax = True
    rose_ax.set_xlim(*xlim)
    rose_ax.set_ylim(*ylim)
    rose_ax.set_aspect("equal")
    rose_ax.axis("off")
    rose_ax.patch.set_alpha(0)

    rose_ax.add_patch(
        mpatches.Circle((0, 0), r, fill=False, edgecolor="#1A1A1A", linewidth=0.9, zorder=9)
    )
    for angle_deg, is_cardinal in _COMPASS_DIRECTIONS:
        length, half_w = (
            (_COMPASS_CARDINAL_LEN, _COMPASS_CARDINAL_HALF_W)
            if is_cardinal
            else (_COMPASS_INTER_LEN, _COMPASS_INTER_HALF_W)
        )
        verts = _compass_spike(math.radians(angle_deg), length, half_w)
        rose_ax.add_patch(
            mpatches.Polygon(
                verts, closed=True, facecolor="#4A4A4A", edgecolor="#1A1A1A",
                linewidth=0.5, zorder=10,
            )
        )
    rose_ax.add_patch(
        mpatches.Circle((0, 0), 0.09, facecolor="#F8F9FA", edgecolor="#1A1A1A", linewidth=0.5, zorder=11)
    )
    rose_ax.text(
        0, r + 0.14, "N", ha="center", va="bottom",
        fontsize=10.5, fontweight="bold", color="#1A1A1A", zorder=12,
    )


def plot_criterion_map(
    score: np.ndarray,
    transform: Affine,
    crs: str,
    criterion: str,
    country_name: str,
    mainland_gdf: gpd.GeoDataFrame,
    out_path: Path,
    context_gdf: gpd.GeoDataFrame | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    """Render one criterion's score/degrees raster as a styled PNG.

    Mirrors legacy `_plot_criterion_map` behaviour: nodata/negative
    pixels are transparent, `protected_areas` gets a categorical
    overlay+legend instead of a colorbar, `slope_degrees` has no fixed
    vmax (it is not normalized to [0,1]), and the footer carries a
    mean/std/IQR stats strip computed over the valid pixels.

    Args:
        score: The criterion's raw score/degrees array (NODATA_FLOAT for
            invalid pixels, matching what save_criterion_raster writes).
        transform: The canonical grid Affine transform.
        crs: The canonical grid CRS string.
        criterion: One of CANONICAL_CRITERIA, or "slope_degrees".
        country_name: Country label for the subtitle (ISO3 code today).
        mainland_gdf: Mainland country polygon(s), used for the basemap
            and (for protected_areas) the free-territory fill.
        out_path: Destination PNG path (parent dirs created).
        context_gdf: Optional neighbouring-country polygons; skipped
            silently if reprojection fails, same as legacy.
        vmin/vmax: Optional overrides; default is 0.0 / 1.0 except for
            slope_degrees, whose vmax is derived from the data.
    """
    title, unit, cmap_name, invert = _CRITERION_META.get(
        criterion, (criterion.replace("_", " ").title(), "Score (0-1)", "RdYlGn_r", False)
    )

    plot_data = score.astype(np.float64).copy()
    plot_data[(score == NODATA_FLOAT) | (score < 0)] = np.nan

    h_px, w_px = score.shape
    extent = [
        transform.c,
        transform.c + transform.a * w_px,
        transform.f + transform.e * h_px,
        transform.f,
    ]
    minx, miny, maxx, maxy = mainland_gdf.total_bounds

    fig, ax = _create_figure(minx, maxx, miny, maxy)
    _draw_basemap(ax, crs, mainland_gdf, context_gdf)

    if criterion == "protected_areas":
        mainland_gdf.to_crs(crs).plot(ax=ax, color=_FREE_TERRITORY_COLOR, edgecolor="none", zorder=2)
        restricted = plot_data.copy()
        restricted[restricted >= 1.0] = np.nan
        restricted[np.isfinite(restricted)] = 0.5
        cmap_r = mcolors.ListedColormap([_RESTRICTED_COLOR]).with_extremes(bad="none")
        ax.imshow(
            restricted, extent=extent, origin="upper", cmap=cmap_r,
            vmin=0.0, vmax=1.0, zorder=3, interpolation="nearest", alpha=0.85,
        )
        mainland_gdf.to_crs(crs).boundary.plot(ax=ax, color=_COUNTRY_BORDER, linewidth=0.8, zorder=4)
        ax.legend(
            handles=[
                mpatches.Patch(color=_RESTRICTED_COLOR, alpha=0.85, label="Protected / Restricted (WDPA)"),
                mpatches.Patch(color=_FREE_TERRITORY_COLOR, label="Free territory"),
            ],
            loc="lower right", bbox_to_anchor=(0.98, 0.03), fontsize=16.8,
            framealpha=0.95, edgecolor="#AAAAAA", fancybox=True,
        )
    elif criterion in _CATEGORICAL_CRITERIA:
        label_high, label_low = _CATEGORICAL_CRITERIA[criterion]
        cmap_cat = mcolors.ListedColormap([_RESTRICTED_COLOR, _AVAILABLE_COLOR]).with_extremes(bad="none")
        ax.imshow(
            plot_data, extent=extent, origin="upper", cmap=cmap_cat,
            vmin=0.0, vmax=1.0, zorder=2, interpolation="nearest",
        )
        ax.legend(
            handles=[
                mpatches.Patch(color=_AVAILABLE_COLOR, label=label_high),
                mpatches.Patch(color=_RESTRICTED_COLOR, label=label_low),
            ],
            loc="lower right", bbox_to_anchor=(0.98, 0.03), fontsize=16.8,
            framealpha=0.95, edgecolor="#AAAAAA", fancybox=True,
        )
    else:
        interp = "bilinear" if criterion in _BILINEAR_CRITERIA else "nearest"
        vmax_val = vmax if vmax is not None else (None if criterion == "slope_degrees" else 1.0)
        im = ax.imshow(
            plot_data, extent=extent, origin="upper",
            cmap=_make_cmap(cmap_name, reverse=invert), vmin=vmin or 0.0, vmax=vmax_val,
            zorder=2, interpolation=interp,
        )
        _add_colorbar(fig, im, unit)

    _apply_decorations(ax, minx, maxx, miny, maxy)
    _draw_compass_rose(fig, ax)
    _add_footer(fig, f"CRS: {crs or 'EPSG:4326'}")
    _add_title(fig, title, country_name)

    valid_data = plot_data[np.isfinite(plot_data)]
    if len(valid_data) > 0:
        _add_stats_strip(fig, valid_data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), bbox_inches="tight", pad_inches=0.10, dpi=_DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
