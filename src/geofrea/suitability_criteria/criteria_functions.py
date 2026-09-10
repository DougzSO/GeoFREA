"""Per-criterion computation functions for suitability_criteria (Fase 2b).

Ported from legacy geoworld_framework's src/processors/criteria_builder.py
module-level `compute_*` functions. Each is a pure transform: aligned
raster path in, (score_array, transform, crs) out, scores in [0, 1] with
NODATA_FLOAT elsewhere. No I/O side effects beyond reading the input
raster.

This module is built incrementally, one criterion package at a time
(see docs/architecture/suitability_criteria_audit.md sec 8 and the
DECISIONS.md 2026-09-10 entries). Package 1: road_suitability,
river_biomass, solar_resource, wind_resource — the four with the lowest
regression risk (road/river distances were already confirmed pixel-exact
against the PRT baseline on 2026-09-10; solar/wind share the same
normalize_percentile path).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy.ndimage import gaussian_filter
from shapely.geometry import mapping

from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.geo_utils import read_clipped_to_country
from geofrea.core.raster_io import safe_raster_open
from geofrea.core.schemas import CriteriaParams
from geofrea.suitability_criteria.normalization import normalize_percentile, valid_finite_mask

logger = logging.getLogger(__name__)

ComputeResult = tuple[np.ndarray, Affine, str]

# compute_protected_areas also reports which branch it took (audit sec 5).
ProtectedResult = tuple[np.ndarray, Affine, str, Literal["wdpa", "assumed_free"]]

# The only value the binary protected-areas mask emits for unrestricted
# land (legacy IUCN_FREE_SCORE, constants.py L196).
_IUCN_FREE_SCORE = 1.0


def _read_band(path: str) -> tuple[np.ndarray, Affine, str, float | None]:
    """Read band 1 of a raster as float32, plus its transform/crs/nodata."""
    with safe_raster_open(path) as src:
        data = src.read(1).astype(np.float32)
        return data, src.transform, str(src.crs), src.nodata


def compute_solar_resource(solar_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Solar-resource suitability: percentile-normalised PVOUT irradiance.

    Legacy: compute_solar_resource (criteria_builder.py L125-145). Valid
    pixels are finite, non-nodata, and strictly positive.

    solar_pvout_weight defaults to 1.0 (a no-op). The legacy's `!= 1.0`
    branch multiplied every FINITE cell, including the NODATA_FLOAT
    sentinel (np.isfinite(-9999.0) is True), which would corrupt invalid
    pixels to -4999.5 etc. for any weight != 1.0. GeoFREA guards the
    NODATA sentinel out of the multiplication (METHODOLOGY_REVISION,
    2026-09-10 — see DECISIONS.md same date). No effect at the default
    weight, so the frozen-baseline regression is unchanged.
    """
    data, transform, crs, nodata = _read_band(solar_path)
    valid = valid_finite_mask(data, nodata) & (data > 0)
    score = normalize_percentile(
        data,
        valid,
        criteria.normalization_min_percentile.value,
        criteria.normalization_max_percentile.value,
    )
    weight = criteria.solar_pvout_weight.value
    if weight != 1.0:
        scored = np.isfinite(score) & (score != NODATA_FLOAT)
        score = np.where(scored, score * weight, score).astype(np.float32)
    return score, transform, crs


def compute_wind_resource(wind_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Wind-resource suitability: percentile-normalised wind speed / power density.

    Legacy: compute_wind_resource (criteria_builder.py L148-164).
    """
    data, transform, crs, nodata = _read_band(wind_path)
    valid = valid_finite_mask(data, nodata) & (data > 0)
    score = normalize_percentile(
        data,
        valid,
        criteria.normalization_min_percentile.value,
        criteria.normalization_max_percentile.value,
    )
    return score, transform, crs


def compute_linear_proximity_suitability(
    dist_path: str, max_dist_km: float, p_low: float, p_high: float
) -> ComputeResult:
    """Linear-decay proximity score, then percentile-normalised.

    S(d) = clip(1 - d / d_max, 0, 1), then normalize_percentile(p_low, p_high).
    Legacy: compute_linear_proximity_suitability (criteria_builder.py
    L234-260). Used for roads and grid distance rasters.
    """
    dist_data, transform, crs, nodata = _read_band(dist_path)
    nd = float(nodata if nodata is not None else NODATA_FLOAT)
    valid = (dist_data != nd) & np.isfinite(dist_data)
    dist_data[~valid] = NODATA_FLOAT

    raw = np.full(dist_data.shape, NODATA_FLOAT, dtype=np.float32)
    raw[valid] = np.clip(1.0 - dist_data[valid] / max_dist_km, 0.0, 1.0).astype(np.float32)

    score = normalize_percentile(raw, valid, p_low, p_high)
    score[~valid] = NODATA_FLOAT
    return score, transform, crs


def compute_road_suitability(roads_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Road-network proximity suitability.

    Legacy: compute_road_suitability (criteria_builder.py L263-269).
    road_max_dist_km = 15.0 and the 5/95 percentile bounds were confirmed
    pixel-exact against outputs_baseline_fc7b43d/PRT on 2026-09-10 (see
    DECISIONS.md same date, and suitability_criteria_audit.md sec 6a).
    """
    return compute_linear_proximity_suitability(
        roads_path,
        criteria.road_max_dist_km.value,
        criteria.linear_proximity_percentile_low.value,
        criteria.linear_proximity_percentile_high.value,
    )


def compute_grid_suitability(grid_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Power-grid proximity suitability.

    Legacy: compute_grid_suitability (criteria_builder.py L272-278) —
    the same linear-decay-then-percentile-normalise as roads, with
    grid_max_dist_km (20.0) and the shared 5/95 percentile bounds.
    """
    return compute_linear_proximity_suitability(
        grid_path,
        criteria.grid_max_dist_km.value,
        criteria.linear_proximity_percentile_low.value,
        criteria.linear_proximity_percentile_high.value,
    )


def compute_lakes_exclusion(lakes_path: str) -> ComputeResult:
    """Binary lake exclusion mask: lake pixels -> 0, land pixels -> 1.

    Legacy: compute_lakes_exclusion (criteria_builder.py L536-547). The
    aligned lakes raster is uint8 with {0 = land, 1 = lake, 255 = outside
    country}; 255 pixels stay NODATA_FLOAT. Only ever emits {0.0, 1.0}
    for in-country pixels — so the Fase 3 threshold on it is
    mathematically inert (audit sec 3a E1), which is why CriteriaParams
    has no parameter for it.
    """
    with safe_raster_open(lakes_path) as src:
        lake_mask = src.read(1).astype(np.uint8)
        transform, crs = src.transform, str(src.crs)

    in_country = lake_mask != 255
    score = np.full(lake_mask.shape, NODATA_FLOAT, dtype=np.float32)
    score[in_country & (lake_mask == 0)] = 1.0
    score[in_country & (lake_mask == 1)] = 0.0
    return score, transform, crs


def compute_river_suitability(
    rivers_path: str, criteria: CriteriaParams, tech: str
) -> ComputeResult:
    """Technology-specific river-proximity suitability.

    Legacy: compute_river_suitability (criteria_builder.py L550-577).
      - tech == "biomass": linear access score, closer is better, out to
        river_max_dist_biomass_km (= 30.0, confirmed pixel-exact vs the
        PRT baseline on 2026-09-10).
      - tech in {"solar", "wind"}: a riparian safety SETBACK — 0 within
        river_safety_buffer_km of a river, 1 beyond it. This function
        produces the {0, 1} raster; promoting it to a Fase 3 hard
        exclusion is suitability_builder's job (audit sec 8d), not done
        here.

    Args:
        rivers_path: Aligned distance-to-river raster (km).
        criteria: The global CriteriaParams block.
        tech: "biomass", "solar", or "wind".

    Raises:
        ValueError: If `tech` is not one of the three expected values.
    """
    if tech not in ("biomass", "solar", "wind"):
        raise ValueError(f"tech must be 'biomass', 'solar', or 'wind', got {tech!r}.")

    dist_km, transform, crs, nodata = _read_band(rivers_path)
    nd = float(nodata if nodata is not None else NODATA_FLOAT)
    valid = (dist_km != nd) & np.isfinite(dist_km)
    score = np.full(dist_km.shape, NODATA_FLOAT, dtype=np.float32)

    if tech == "biomass":
        max_dist = criteria.river_max_dist_biomass_km.value
        score[valid] = np.clip(1.0 - dist_km[valid] / max_dist, 0.0, 1.0).astype(np.float32)
    else:
        buffer_km = criteria.river_safety_buffer_km.value
        score[valid & (dist_km < buffer_km)] = 0.0
        score[valid & (dist_km >= buffer_km)] = 1.0

    return score, transform, crs


def compute_slope_degrees(slope_path: str) -> ComputeResult:
    """Pass-through: absolute slope in degrees, NODATA_FLOAT for invalid pixels.

    Legacy: compute_slope_degrees (criteria_builder.py L223-231). Written
    to disk for cartography only (slope_degrees.tif) — it is NOT a
    canonical criterion and never enters the MCDA (audit sec 2b). No
    parameters.
    """
    data, transform, crs, nodata = _read_band(slope_path)
    valid = valid_finite_mask(data, nodata) & (data >= 0)
    out = np.full(data.shape, NODATA_FLOAT, dtype=np.float32)
    out[valid] = data[valid]
    return out, transform, crs


def compute_terrain_score(
    slope_path: str,
    elev_path: str | None,
    criteria: CriteriaParams,
    slope_threshold_deg: float,
) -> ComputeResult:
    """Compound terrain suitability: w_slope * slope_score + w_tri * TRI_score.

    Legacy: compute_terrain_score (criteria_builder.py L167-220).
      - slope_score = clip(1 - slope / slope_threshold_deg, 0, 1)
      - TRI = sqrt(sum over the 8 neighbours of (E_centre - E_i)^2), with
        edge-padded elevation; TRI_score = clip(1 - TRI / tri_threshold_m, 0, 1)
      - combined where both are valid: w_slope * slope_score + w_tri * TRI_score
        (weights from CriteriaParams, must sum to 1); slope-only where the
        TRI sub-score is NoData; slope-only entirely if elevation is
        absent or the TRI computation raises.

    `slope_threshold_deg` is the PER-COUNTRY denominator
    (CountryParams.criteria.terrain_slope_threshold_deg — PRT 10, BRA 12),
    NOT the fixed cross-country exclusion gate (see docs/DECISIONS.md
    2026-09-10 - terrain_score denominator is per-country). The legacy's
    7.0 signature fallback is dead code and not ported — the value always
    comes from config.
    """
    slope, transform, crs, slope_nodata = _read_band(slope_path)
    valid_s = valid_finite_mask(slope, slope_nodata) & (slope >= 0)

    score_s = np.full(slope.shape, NODATA_FLOAT, dtype=np.float32)
    score_s[valid_s] = np.clip(
        1.0 - slope[valid_s] / slope_threshold_deg, 0.0, 1.0
    ).astype(np.float32)

    score_tri: np.ndarray | None = None
    if elev_path is not None:
        try:
            elev, _t, _c, elev_nodata = _read_band(elev_path)
            valid_e = valid_finite_mask(elev, elev_nodata)
            pad = np.pad(elev, 1, mode="edge")
            tri = np.zeros_like(elev, dtype=np.float32)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    neighbour = pad[
                        1 + di : 1 + di + elev.shape[0], 1 + dj : 1 + dj + elev.shape[1]
                    ]
                    tri += (neighbour - elev) ** 2
            tri = np.sqrt(tri)
            st = np.full(elev.shape, NODATA_FLOAT, dtype=np.float32)
            st[valid_e] = np.clip(
                1.0 - tri[valid_e] / criteria.tri_threshold_m.value, 0.0, 1.0
            ).astype(np.float32)
            score_tri = st
        except Exception as exc:  # noqa: BLE001 — legacy degrades to slope-only here
            logger.warning("  TRI computation failed, using slope only: %s", exc)

    if score_tri is None:
        return score_s, transform, crs

    w_slope = criteria.terrain_slope_weight.value
    w_tri = criteria.terrain_tri_weight.value
    combined = np.full(slope.shape, NODATA_FLOAT, dtype=np.float32)
    both = (score_s != NODATA_FLOAT) & (score_tri != NODATA_FLOAT)
    only_s = (score_s != NODATA_FLOAT) & (score_tri == NODATA_FLOAT)
    combined[both] = (w_slope * score_s[both] + w_tri * score_tri[both]).astype(np.float32)
    combined[only_s] = score_s[only_s]
    return combined, transform, crs


def _read_land_cover(lc_path: str) -> tuple[np.ndarray, Affine, str, int]:
    """Read the aligned land-cover raster as int16, with its nodata as int."""
    with safe_raster_open(lc_path) as src:
        lc_data = src.read(1).astype(np.int16)
        nodata = int(src.nodata) if src.nodata is not None else 0
        return lc_data, src.transform, str(src.crs), nodata


def compute_lc_biomass(
    lc_path: str, land_suitability: dict[int, object]
) -> ComputeResult:
    """Direct ESA-class -> biomass-suitability lookup (the `lc_biomass` criterion).

    Legacy: compute_land_cover_scores (criteria_builder.py L355-385), the
    "biomass" entry of its returned dict. Each valid land-cover pixel
    takes the `biomass` score of its ESA class from the global
    land_suitability table; a class not in the table scores 0.0.

    Args:
        lc_path: Aligned land-cover raster (ESA WorldCover class codes).
        land_suitability: CriteriaParams.land_suitability.value —
            {esa_class_code: LandCoverSuitability}. Only `.biomass` is read.
    """
    lc_data, transform, crs, nodata = _read_land_cover(lc_path)
    lookup = {int(code): float(row.biomass) for code, row in land_suitability.items()}

    score = np.full(lc_data.shape, NODATA_FLOAT, dtype=np.float32)
    valid = (lc_data != nodata) & (lc_data > 0) & (lc_data != 255)
    for cls in np.unique(lc_data[valid]):
        score[(lc_data == cls) & valid] = lookup.get(int(cls), 0.0)
    return score, transform, crs


def compute_biomass_resource(
    lc_path: str, yield_by_land_cover: dict[int, float], criteria: CriteriaParams
) -> ComputeResult:
    """Biomass resource potential from land-cover-specific yields.

    Legacy: compute_biomass_resource (criteria_builder.py L388-432).
    Each valid land-cover pixel takes its class's yield (classes without
    a listed yield score 0.0), optionally Gaussian-smoothed
    (biomass_smooth_sigma), then percentile-normalised.

    The valid mask is `(lc != nodata) & (lc > 0) & (lc != 255)`, mirroring
    compute_lc_biomass. The legacy omitted the explicit `!= 255`, which was
    harmless only because grid_alignment always writes the land-cover raster
    with nodata == 255 (NODATA_UINT8) — so `lc != nodata` already dropped
    those pixels. GeoFREA makes the exclusion explicit to close that implicit
    dependency on the nodata convention (guard fix, 2026-09-10 — see
    DECISIONS.md same date). Bit-exact against the frozen PRT/BRA baselines
    (both have nodata == 255).
    """
    lc_data, transform, crs, nodata = _read_land_cover(lc_path)
    yields_int = {int(k): float(v) for k, v in yield_by_land_cover.items()}

    raw = np.full(lc_data.shape, NODATA_FLOAT, dtype=np.float32)
    valid_base = (lc_data != nodata) & (lc_data > 0) & (lc_data != 255)
    for cls, y in yields_int.items():
        raw[(lc_data == cls) & valid_base] = y
    raw[(raw == NODATA_FLOAT) & valid_base] = 0.0

    sigma = criteria.biomass_smooth_sigma.value
    if sigma > 0:
        tmp = raw.copy()
        tmp[~valid_base] = 0.0
        tmp = gaussian_filter(tmp, sigma=sigma).astype(np.float32)
        tmp[~valid_base] = NODATA_FLOAT
        raw = tmp

    score = normalize_percentile(
        raw,
        valid_base,
        criteria.normalization_min_percentile.value,
        criteria.normalization_max_percentile.value,
    )
    return score, transform, crs


def compute_population_suitability(pop_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Logarithmic penalty for high population density.

    Legacy: compute_population_suitability (criteria_builder.py L518-533).
      S = clip(1 - log1p(clip(pop, 0, thr)) / log1p(thr), 0, 1)
    where thr = criteria.pop_density_threshold. NODATA where pop equals
    the raster's nodata value or is negative.

    Note: production config sets pop_density_threshold = 200.0
    (docs/DECISIONS.md 2026-09-10 "suitability_criteria parameter
    calibration" — lowered from the legacy's 300.0). The frozen baseline
    was built with 300.0, so this criterion is intentionally NOT
    bit-exact against outputs_baseline_fc7b43d under the production
    config; the regression test overrides the threshold back to 300.0 to
    check port fidelity of the formula itself.
    """
    with safe_raster_open(pop_path) as src:
        pop = src.read(1)  # native dtype, matching legacy (no .astype)
        transform, crs, nodata = src.transform, str(src.crs), src.nodata

    threshold = criteria.pop_density_threshold.value
    score = np.clip(
        1.0 - np.log1p(np.clip(pop, 0, threshold)) / np.log1p(threshold),
        0.0,
        1.0,
    ).astype(np.float32)
    if nodata is not None:
        score[pop == float(nodata)] = NODATA_FLOAT
    score[pop < 0] = NODATA_FLOAT
    return score, transform, crs


def compute_seismic_suitability(seismic_path: str, criteria: CriteriaParams) -> ComputeResult:
    """Seismic-risk inversion: low hazard -> high suitability.

    Legacy: compute_seismic_suitability (criteria_builder.py L580-593).
    normalize_percentile over the 2/98 percentile band (parametrised as
    criteria.seismic_percentile_low/high, values inherited unchanged from
    the legacy — audit M8), then score = clip(1 - normalized, 0, 1).
    """
    data, transform, crs, nodata = _read_band(seismic_path)
    valid = valid_finite_mask(data, nodata) & (data >= 0)
    normalized = normalize_percentile(
        data,
        valid,
        criteria.seismic_percentile_low.value,
        criteria.seismic_percentile_high.value,
    )
    score = np.full(data.shape, NODATA_FLOAT, dtype=np.float32)
    valid_norm = valid & (normalized != NODATA_FLOAT)
    score[valid_norm] = np.clip(1.0 - normalized[valid_norm], 0.0, 1.0).astype(np.float32)
    return score, transform, crs


def _resolve_wdpa_shapefile(wdpa_path: str | Path | None) -> str | None:
    """Resolve a WDPA input (file or directory) to a single polygon shapefile.

    Mirrors the legacy's directory probe (criteria_builder.py L463-472):
    prefer a ``*polygon*.shp``, then a ``*_0.shp``, then any non-point
    ``.shp``; take the first match in sorted order. Returns None when the
    path is missing or holds no usable shapefile.
    """
    if wdpa_path is None:
        return None
    p = Path(wdpa_path)
    if not p.exists():
        return None
    if p.is_file():
        return str(p)
    candidates = (
        sorted(p.rglob("*polygon*.shp"))
        or sorted(p.rglob("*_0.shp"))
        or [q for q in sorted(p.rglob("*.shp")) if "point" not in q.name.lower()]
    )
    return str(candidates[0]) if candidates else None


def compute_protected_areas(
    wdpa_path: str | Path | None,
    mainland_gdf: gpd.GeoDataFrame,
    transform: Affine,
    width: int,
    height: int,
    crs: str,
    strict_categories: list[str],
) -> ProtectedResult:
    """Binary WDPA protected-areas mask on the mainland footprint.

    Legacy: compute_protected_areas (criteria_builder.py L435-515), with
    the graded IUCN_SCORES table dropped per the approved contract
    (docs/architecture/suitability_criteria_audit.md sec 5 / M9-M10,
    DECISIONS.md 2026-09-10). The Fase 3 hard-exclusion threshold (0.99)
    already made every fractional IUCN score dead code, so GeoFREA emits
    only:
      - 0.0  where a WDPA polygon's IUCN category (lowercased, stripped)
             is in `strict_categories` (default {ia, ib, ii});
      - 1.0  everywhere else on the mainland (other WDPA polygons AND
             unprotected land — they are indistinguishable to Fase 3).
    Pixels outside the mainland polygon stay NODATA_FLOAT.

    No WDPA file (the layer is gated behind a manual Protected Planet
    token and is often absent): the whole mainland scores 1.0 and the
    returned source is "assumed_free" — the legacy's L458-459 behaviour,
    so a missing token never silently changes the science.

    This criterion has NO bit-exact parity with outputs_baseline_fc7b43d
    (the frozen baseline is graded; this is binary — a deliberate
    post-baseline contract decision). Its regression checks the mainland
    footprint against the frozen valid-pixel mask and the binary
    structure, not cell values.

    Args:
        wdpa_path: WDPA polygon shapefile, a directory containing one, or
            None.
        mainland_gdf: Mainland country polygon(s) (any CRS).
        transform: Reference-grid affine transform (from GridMetadata).
        width/height: Reference-grid shape (from GridMetadata).
        crs: Reference-grid CRS string.
        strict_categories: IUCN category codes scored 0.0
            (criteria.iucn_strict_categories.value).

    Returns:
        (score, transform, crs, source) where source is "wdpa" if a WDPA
        file drove the mask, else "assumed_free".
    """
    strict = {c.lower().strip() for c in strict_categories}

    mainland_union = mainland_gdf.to_crs(crs).union_all()
    mainland_mask = rasterize(
        [(mapping(mainland_union), 1)],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    score = np.full((height, width), NODATA_FLOAT, dtype=np.float32)

    shapefile = _resolve_wdpa_shapefile(wdpa_path)
    if shapefile is None:
        score[mainland_mask > 0] = _IUCN_FREE_SCORE
        return score, transform, crs, "assumed_free"

    try:
        gdf = read_clipped_to_country(shapefile, mainland_gdf)
        if gdf.crs is not None and str(gdf.crs) != crs:
            gdf = gdf.to_crs(crs)
        gdf = gdf[~gdf.geometry.is_empty]
        if gdf.empty:
            score[mainland_mask > 0] = _IUCN_FREE_SCORE
            return score, transform, crs, "assumed_free"

        iucn_col = next(
            (c for c in ("IUCN_CAT", "iucn_cat", "IUCN", "DESIGNATION") if c in gdf.columns),
            None,
        )
        if iucn_col is not None:
            cats = gdf[iucn_col].astype("string").str.lower().str.strip()
            feature_scores = np.where(cats.isin(strict), 0.0, _IUCN_FREE_SCORE)
        else:
            feature_scores = np.full(len(gdf), _IUCN_FREE_SCORE)

        # Rasterize free (1.0) first, strict (0.0) last so exclusions win.
        order = np.argsort(-feature_scores, kind="stable")
        shapes = [
            (mapping(geom), float(sv))
            for geom, sv in zip(gdf.geometry.to_numpy()[order], feature_scores[order])
        ]
        temp = np.full((height, width), _IUCN_FREE_SCORE, dtype=np.float32)
        rasterize(shapes, out_shape=(height, width), transform=transform, out=temp)
        score[mainland_mask > 0] = temp[mainland_mask > 0]
        return score, transform, crs, "wdpa"

    except Exception as exc:  # noqa: BLE001 — legacy degrades to "all free" here (L511-513)
        logger.warning("  Protected-areas rasterization failed, assuming free: %s", exc)
        score[mainland_mask > 0] = _IUCN_FREE_SCORE
        return score, transform, crs, "assumed_free"
