"""Cartography for suitability_criteria (Fase 2b) — one PNG per criterion.

Ported from legacy geoworld_framework's src/processors/criteria_builder.py
(`CriteriaBuilder._plot_criterion_map`, L641-743). Reimplemented locally
and NOT routed through a shared/generic renderer — see
docs/architecture/suitability_criteria_audit.md sec 7 D7 (decision
2026-09-10): "cartografia da Fase 2b fica isolada por ora ... sem
estender o renderer genérico". No such renderer exists in GeoFREA yet
either way (legacy's GeoWorldStyler was never ported).

Deliberately narrower than legacy's GeoWorldStyler-backed original:
  - No compass rose / segmented scale bar (GeoWorldStyler private
    helpers, never ported — cartographic decoration, not scientific
    content).
  - No admin1 region labels — SuitabilityCriteriaInputs carries no
    admin_gdf (that boundary layer is not wired into this phase).
  - context_gdf (neighbouring countries) is accepted but is always None
    today (suitability_criteria/adapter.py does not populate it yet);
    handled the same way legacy does — silently skipped when absent.
Ported faithfully: basemap (mainland + optional context countries),
per-criterion colormap/vmax, the protected_areas overlay+legend special
case, colorbar, mean/std/IQR stats strip, title/subtitle, CRS footer.
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
    "solar_resource": ("Solar Resource (PVOUT)", "Potential (normalised)", "YlOrRd", False),
    "wind_resource": ("Wind Resource (Power Density)", "Potential (normalised)", "Blues", False),
    "terrain_score": ("Terrain Suitability (Slope + TRI)", "Score (0-1)", "RdYlGn", False),
    "lc_biomass": ("Land Cover Suitability - Biomass", "Score (0-1)", "RdYlGn", False),
    "biomass_resource": ("Biomass Resource (Yield by LC)", "Potential (normalised)", "Greens", False),
    "pop_suitability": ("Population Suitability", "Score (0-1)", "RdYlGn", False),
    "road_suitability": ("Proximity to Roads", "Score (0-1)", "RdYlGn", False),
    "slope_degrees": ("Slope", "Degrees", "YlOrRd", False),
    "protected_areas": ("Protected Areas Constraint", "Score (0-1)", "RdYlGn", False),
    "lakes_exclusion": ("Lakes Exclusion (HydroLAKES)", "Binary (0=lake, 1=ok)", "RdYlGn", False),
    "river_solar": ("River Buffer - Solar/Wind", "Score (0-1)", "RdYlGn", False),
    "river_wind": ("River Buffer - Wind", "Score (0-1)", "RdYlGn", False),
    "river_biomass": ("River Access - Biomass", "Score (0-1)", "Blues", False),
    "seismic_suitability": ("Seismic Hazard Suitability", "Score (0-1)", "RdYlGn", False),
    "grid_suitability": ("Power Grid Proximity (OSM)", "Score (0-1)", "RdYlGn", False),
}

_COUNTRY_BORDER = "#1A1A1A"
_OCEAN_BG = "#D6EAF8"
_FIG_BG = "#F8F9FA"
_CTX_FILL = "#E8E8E8"
_CTX_EDGE = "#B0B0B0"
_RESTRICTED_COLOR = "#C0392B"  # legacy's CONTOUR_P90_COLOR, reused for the protected overlay
_FREE_TERRITORY_COLOR = "#E8E8E8"

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
    cbar.set_label(unit_label, fontsize=14, labelpad=12, fontweight="bold")
    cbar.ax.tick_params(labelsize=12.5)


def _add_title(fig: plt.Figure, title_main: str, title_sub: str) -> None:
    top_margin_frac = _TOP_IN / fig.get_figheight()
    ax_top = 1.0 - top_margin_frac
    y_main = ax_top + top_margin_frac * (0.60 if title_sub else 0.45)
    fig.text(
        0.5, y_main, title_main, ha="center", va="center",
        fontsize=22, fontweight="bold", color="#1A1A1A", transform=fig.transFigure,
    )
    if title_sub:
        y_sub = y_main - top_margin_frac * 0.35
        fig.text(
            0.5, y_sub, title_sub, ha="center", va="center",
            fontsize=17, fontweight="bold", color="#444444", transform=fig.transFigure,
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
    fig.text(ax_cx, 0.025, text, ha="center", fontsize=18, color="#222222", transform=fig.transFigure)


def _apply_decorations(ax: plt.Axes, minx: float, maxx: float, miny: float, maxy: float) -> None:
    is_geographic = abs(minx) <= 180 and abs(maxy) <= 90
    mid_lat = (miny + maxy) / 2.0
    cos_mid_lat = math.cos(math.radians(mid_lat)) if is_geographic else 1.0
    ax.set_aspect(1.0 / cos_mid_lat if is_geographic else 1.0, adjustable="box")
    ax.set_xlabel("Longitude", fontsize=16, labelpad=8, color="#333333")
    ax.set_ylabel("Latitude", fontsize=16, labelpad=8, color="#333333")
    ax.tick_params(labelsize=14, colors="#333333", width=1.2, length=4)
    ax.grid(False)


def _make_cmap(name: str, reverse: bool) -> mcolors.Colormap:
    full_name = name + "_r" if reverse else name
    return plt.get_cmap(full_name).with_extremes(under="none", bad="none")


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
    vmax (it is not normalised to [0,1]), and the footer carries a
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
            loc="lower right", bbox_to_anchor=(0.98, 0.03), fontsize=14,
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
    _add_footer(fig, f"CRS: {crs or 'EPSG:4326'}")
    _add_title(fig, title, country_name)

    valid_data = plot_data[np.isfinite(plot_data)]
    if len(valid_data) > 0:
        _add_stats_strip(fig, valid_data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), bbox_inches="tight", pad_inches=0.10, dpi=_DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
