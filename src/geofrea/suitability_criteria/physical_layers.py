"""Cost-driver and resource layers in physical units (H-4; M-F2b-02, M-F2b-03, M-F2b-04).

Each layer is the aligned raster copied as float32 with invalid pixels set to NODATA_FLOAT. Values are never
rescaled, clipped, normalized or weighted (M-F2b-04): distances stay in km, PVOUT in kWh/kWp/day, Weibull A in m/s,
Weibull k dimensionless, air density in kg/m3. Distances are the uncapped geodesic values of F2a (OQ-040).

No CRAEI counterpart exists (checked 2026-10-06: no weibull/pvout/distance-to-grid code), so this is written fresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
from geofrea.grid_alignment.schemas import GridAlignmentResult

WIND_HEIGHTS_M = (100, 150, 200)


@dataclass(frozen=True)
class PhysicalLayerSpec:
    """One output layer: its name, the unit it keeps, and where it comes from in GridAlignmentResult."""

    name: str
    unit: str
    kind: str  # "cost_driver" | "resource"


LAYER_SPECS: tuple[PhysicalLayerSpec, ...] = (
    PhysicalLayerSpec("dist_grid_km", "km", "cost_driver"),
    PhysicalLayerSpec("dist_road_km", "km", "cost_driver"),
    PhysicalLayerSpec("pvout_kwh_kwp_day", "kWh/kWp/day", "resource"),
    *(PhysicalLayerSpec(f"weibull_a_{h}m", "m/s", "resource") for h in WIND_HEIGHTS_M),
    *(PhysicalLayerSpec(f"weibull_k_{h}m", "1", "resource") for h in WIND_HEIGHTS_M),
    *(PhysicalLayerSpec(f"air_density_{h}m", "kg/m3", "resource") for h in WIND_HEIGHTS_M),
)


class MissingPhysicalLayerError(ValueError):
    """Required aligned layers are absent from the grid_alignment result (named, never silently skipped)."""


def _sources(grid_result: GridAlignmentResult) -> dict[str, Path | None]:
    wind = grid_result.wind_layers
    sources: dict[str, Path | None] = {
        "dist_grid_km": grid_result.grid,
        "dist_road_km": grid_result.roads,
        "pvout_kwh_kwp_day": grid_result.solar,
    }
    for h in WIND_HEIGHTS_M:
        for product in ("weibull_a", "weibull_k", "air_density"):
            sources[f"{product}_{h}m"] = wind.get(f"{product}_{h}m")
    return sources


def write_physical_layer(src_path: Path, out_path: Path, spec: PhysicalLayerSpec) -> Path:
    """Copy `src_path` band 1 to `out_path` unchanged except that invalid pixels become NODATA_FLOAT.

    Implements: M-F2b-04 (no normalization; physical units kept, recorded in the `units` tag).
    """
    with safe_raster_open(src_path) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": src.width,
            "height": src.height,
            "count": 1,
            "crs": src.crs,
            "transform": src.transform,
            "nodata": NODATA_FLOAT,
            "blockxsize": 256,
            "blockysize": 256,
        }
    invalid = ~np.isfinite(data)
    if nodata is not None:
        invalid |= data == np.float32(nodata)
    data[invalid] = NODATA_FLOAT
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(layer=spec.name, units=spec.unit, kind=spec.kind, normalized="false")
    return out_path


def build_physical_layers(grid_result: GridAlignmentResult, out_dir: Path) -> dict[str, Path]:
    """Write every cost-driver and resource layer of M-F2b-02/03 under `out_dir`; return name -> path.

    Implements: M-F2b-02, M-F2b-03.

    Raises:
        MissingPhysicalLayerError: listing every required layer that is absent or whose file is missing.
    """
    sources = _sources(grid_result)
    missing = [name for name, p in sources.items() if p is None or not Path(p).exists()]
    if missing:
        raise MissingPhysicalLayerError(f"required aligned layers missing: {', '.join(missing)}")
    return {
        spec.name: write_physical_layer(Path(sources[spec.name]), out_dir / f"{spec.name}.tif", spec)
        for spec in LAYER_SPECS
    }
