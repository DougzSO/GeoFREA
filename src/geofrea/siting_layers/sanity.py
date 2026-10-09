"""Sanity ranges of the F2b layers that follow from physics and geometry, not from research (V-04, H-6).

Two ranges are derived, so nothing is looked up or judged:

- **Air density** at hub height. A pixel at ground elevation `z` and a layer at height `h` above ground cannot be less dense than the
  International Standard Atmosphere at `z + h` nor denser than it at the lowest ground elevation of the country plus the lowest layer
  height. The envelope of a country is `[rho_ISA(z_max + h), rho_ISA(z_min + h)]`, with `z_min` and `z_max` the lowest and highest in-country
  elevation of the DEM (F2a aligned layer) and `rho_ISA` the ISO 2533 troposphere formulas. `h` is the layer height, a physical
  quantity, not a margin. Real temperature and pressure anomalies are covered by a relative quality-control tolerance declared in
  `audit.yaml` (`tolerance_rel`, +-5%, about +-15 K): the check exists to catch gross errors (unit, swapped layer, corrupt tile), not to
  predict the density. A pixel outside the widened envelope is reported, never corrected.
- **Distances** to the grid and to the road network. A distance between two in-country points cannot exceed the diagonal of the
  country's bounding box, and cannot be negative. The bound is loose by construction (a country's bounding box is larger than the
  country) and sound: the layer, which is uncapped (OQ-040), cannot break it unless the layer is wrong.

Weibull A and k have no derivation of this kind; their ranges need a sourced reading of the Global Wind Atlas documentation (OQ-053).
PVOUT keeps the range of `config/audit.yaml`, read from the product's own statistics.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

from geofrea.core import paths as core_paths
from geofrea.core.constants import (
    ISA_G_M_S2,
    ISA_LAPSE_K_PER_M,
    ISA_P0_PA,
    ISA_R_J_KG_K,
    ISA_T0_K,
)
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.data_quality_audit.schemas import AuditConfig, AuditLayerConfig

logger = logging.getLogger("geofrea.siting_layers.sanity")

ISA_TROPOSPHERE_TOP_M = 11000.0
ISA_LOWEST_M = -5000.0  # ISO 2533 tabulates the troposphere formulas down to -5 km


class SanityError(ValueError):
    """An input of a sanity range is outside the domain of its derivation (A-09)."""


def isa_density_kg_m3(altitude_m: np.ndarray | float) -> np.ndarray | float:
    """Air density of the ISO 2533 standard atmosphere in the troposphere.

    `T = T0 - L z`, `p = p0 (T / T0)^(g / (R L))`, `rho = p / (R T)`.

    Implements: V-04.

    Args:
        altitude_m: Geopotential altitude above mean sea level, m, between -5000 and 11000.

    Returns:
        Density, kg/m3, same shape as the input.

    Raises:
        SanityError: an altitude outside the tabulated troposphere.
    """
    z = np.asarray(altitude_m, dtype="float64")
    if (z < ISA_LOWEST_M).any() or (z > ISA_TROPOSPHERE_TOP_M).any():
        raise SanityError(
            f"altitude outside the ISO 2533 troposphere [{ISA_LOWEST_M}, {ISA_TROPOSPHERE_TOP_M}] m"
        )
    t = ISA_T0_K - ISA_LAPSE_K_PER_M * z
    p = ISA_P0_PA * (t / ISA_T0_K) ** (ISA_G_M_S2 / (ISA_R_J_KG_K * ISA_LAPSE_K_PER_M))
    rho = p / (ISA_R_J_KG_K * t)
    return float(rho) if np.ndim(altitude_m) == 0 else rho


def air_density_envelope(z_min_m: float, z_max_m: float, height_m: float) -> tuple[float, float]:
    """`(lower, upper)` density bound of a layer `height_m` above ground in a country spanning `z_min_m` to `z_max_m`.

    Implements: V-04.
    """
    if z_max_m < z_min_m:
        raise SanityError("z_max is below z_min")
    return float(isa_density_kg_m3(z_max_m + height_m)), float(
        isa_density_kg_m3(z_min_m + height_m)
    )


def bbox_diagonal_km(west: float, south: float, east: float, north: float) -> float:
    """Upper bound of the distance between two points of a bounding box, km (planar diagonal at the widest latitude).

    The east-west extent uses the longitude scale at the latitude closest to the equator inside the box, which is the
    largest one, so the result is never below the true geodesic distance across the box.

    Implements: V-04.
    """
    if east <= west or north <= south:
        raise SanityError("empty bounding box")
    lat_closest_to_equator = 0.0 if south <= 0.0 <= north else min(abs(south), abs(north))
    lat_km, _ = wgs84_km_per_degree(np.array([south, north]))
    _, lon_km = wgs84_km_per_degree(lat_closest_to_equator)
    return float(math.hypot((north - south) * float(np.max(lat_km)), (east - west) * float(lon_km)))


@dataclass(frozen=True)
class CountryGeometry:
    """What the derived ranges need to know about a country: the DEM elevation span and the bounding box (degrees)."""

    z_min_m: float
    z_max_m: float
    west: float
    south: float
    east: float
    north: float


def dem30_extremes(tile_dir: Path, cache: Path | None = None) -> tuple[float, float]:
    """Lowest and highest elevation of the 30 m DEM tiles of a country, m (the finest terrain the pipeline holds).

    The 0.005 degree DEM that F2a aligns averages the terrain, so its highest pixel is lower than the highest peak that the wind-atlas
    density was computed on. The 30 m tiles (the ones F2a derives the slope from) bound the terrain from above and below. Tiles
    cover the country plus the border margin of their 1 degree squares, which only widens the envelope. The result is cached in
    `cache` (JSON, keyed by the tile names) because BRA has hundreds of tiles.

    Raises:
        SanityError: no tile, or no valid pixel.
    """
    tiles = sorted(Path(tile_dir).glob("*.tif"))
    if not tiles:
        raise SanityError(f"no 30 m DEM tile in {tile_dir}")
    key = [t.name for t in tiles]
    if cache is not None and cache.is_file():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("tiles") == key:
            return float(cached["z_min_m"]), float(cached["z_max_m"])
    z_min, z_max = math.inf, -math.inf
    for i, tile in enumerate(tiles, start=1):
        with rasterio.open(tile) as src:
            data = src.read(1, masked=True)
        if data.count():
            z_min, z_max = min(z_min, float(data.min())), max(z_max, float(data.max()))
        if i % 50 == 0 or i == len(tiles):
            logger.info("30 m DEM extremes: %d/%d tiles", i, len(tiles))
    if not math.isfinite(z_min):
        raise SanityError(f"the 30 m tiles in {tile_dir} hold no valid pixel")
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps({"tiles": key, "z_min_m": z_min, "z_max_m": z_max}), encoding="utf-8"
        )
    return z_min, z_max


def country_geometry(
    elevation_aligned: Path, dem30_tile_dir: Path | None = None, cache: Path | None = None
) -> CountryGeometry:
    """Elevation span and bounding box of a country: the F2a aligned DEM, widened by the 30 m tiles when given.

    Raises:
        SanityError: the raster has no valid pixel.
    """
    with rasterio.open(elevation_aligned) as src:
        data = src.read(1, masked=True)
        b = src.bounds
    if data.count() == 0:
        raise SanityError(f"{elevation_aligned} has no valid pixel")
    z_min, z_max = float(data.min()), float(data.max())
    if dem30_tile_dir is not None:
        low, high = dem30_extremes(dem30_tile_dir, cache)
        z_min, z_max = min(z_min, low), max(z_max, high)
    return CountryGeometry(
        z_min_m=z_min,
        z_max_m=z_max,
        west=b.left,
        south=b.bottom,
        east=b.right,
        north=b.top,
    )


def derived_range(
    layer: str,
    geometry: CountryGeometry,
    height_m: float | None = None,
    tolerance_rel: float = 0.0,
) -> tuple[float, float] | None:
    """The derived `(low, high)` of a layer, or `None` when the layer has no derivation (Weibull A and k, OQ-053).

    Args:
        layer: `air_density`, `dist_grid_km` or `dist_road_km`.
        geometry: The country's geometry.
        height_m: Height above ground of an `air_density` layer.
        tolerance_rel: Relative quality-control tolerance on each side of an `air_density` envelope (`audit.yaml`); ignored by
            the distances, which are exact bounds.
    """
    if layer == "air_density":
        if height_m is None:
            raise SanityError("air_density needs the layer height")
        low, high = air_density_envelope(geometry.z_min_m, geometry.z_max_m, height_m)
        return low * (1.0 - tolerance_rel), high * (1.0 + tolerance_rel)
    if layer in ("dist_grid_km", "dist_road_km"):
        return 0.0, bbox_diagonal_km(geometry.west, geometry.south, geometry.east, geometry.north)
    return None


def load_country_geometry(iso: str) -> CountryGeometry:
    """`CountryGeometry` of a country from the pipeline's own files: the F2a aligned DEM widened by the 30 m tiles (cached).

    Raises:
        SanityError: no aligned DEM, no 30 m tile, or no valid pixel (a derived range cannot be built without them).
    """
    elevation = (
        core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_elevation_aligned.tif"
    )
    if not elevation.is_file():
        raise SanityError(f"the F2a aligned DEM is missing: {elevation} (F2a must have run)")
    return country_geometry(
        elevation,
        core_paths.fetched_raw("copernicus_dem30", iso),
        core_paths.interim(iso, "sanity") / "dem30_extremes.json",
    )


def pvout_range(audit: AuditConfig, iso: str) -> tuple[tuple[float, float], str]:
    """`((low, high), source)` of PVOUT in kWh/kWp/day: the country override of `audit.yaml` when there is one, else the product's range.

    Raises:
        SanityError: `audit.yaml` declares no PVOUT range.
    """
    override = audit.country_overrides.get(iso, {}).get("solar")
    if override is not None and override.sanity_range is not None:
        return override.sanity_range, f"audit.yaml country_overrides.{iso}.solar.sanity_range"
    product = audit.layers.get("solar")
    if isinstance(product, AuditLayerConfig) and product.sanity_range is not None:
        return product.sanity_range, "audit.yaml layers.solar.sanity_range"
    raise SanityError("audit.yaml has no sanity_range for the PVOUT layer")
