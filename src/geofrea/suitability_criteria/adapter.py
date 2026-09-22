"""Builds suitability_criteria's input from the two phases it depends on.

suitability_criteria (Fase 2b) consumes TWO prior phases (audit sec 8c):
  - grid_alignment  -> the 12 aligned rasters + GridMetadata
  - data_acquisition -> the optional WDPA path, the power-plants
    DataFrame, and the mainland boundary (via `borders`)

Same local-file glue style as grid_alignment/adapter.py — no HTTP, no
SDK. Mirrors that module's GridAlignmentRequiresBordersError with its own
fail-loud guard: without a country boundary there is no mainland mask
for protected_areas and no basemap for the criterion maps.
"""

from __future__ import annotations

from geofrea.core.geo_utils import load_mainland_boundary
from geofrea.core.schemas import CountryCriteriaParams, CriteriaParams
from geofrea.data_acquisition.adapter import load_power_plants_df
from geofrea.data_acquisition.schemas import AcquisitionResult
from geofrea.grid_alignment.schemas import GridAlignmentResult
from geofrea.suitability_criteria.schemas import SuitabilityCriteriaInputs

# GridAlignmentResult field -> SuitabilityCriteriaInputs field. Same
# names on both sides (the inputs schema mirrors GridAlignmentResult
# field-for-field), listed explicitly rather than via __dict__ so an
# added/removed layer is a visible edit here.
_ALIGNED_RASTER_FIELDS: tuple[str, ...] = (
    "elevation",
    "slope",
    "solar",
    "wind",
    "land_cover",
    "population",
    "roads",
    "grid",
    "lakes",
    "rivers",
    "plants",
)


class SuitabilityCriteriaRequiresBordersError(ValueError):
    """Raised when the AcquisitionResult has no usable `borders` layer.

    Same class of gap as grid_alignment's
    GridAlignmentRequiresBordersError: a wiring/configuration problem,
    not a per-file data problem, so it fails loudly at adapter
    construction time rather than surfacing deep inside the phase.
    """


def build_suitability_criteria_inputs(
    grid_result: GridAlignmentResult,
    acquisition_result: AcquisitionResult,
    criteria: CriteriaParams,
    country_criteria: CountryCriteriaParams,
) -> SuitabilityCriteriaInputs:
    """Assemble SuitabilityCriteriaInputs from the two upstream phase outputs.

    Args:
        grid_result: grid_alignment's output for this country.
        acquisition_result: data_acquisition's output for this country
            (used for the WDPA path, the power-plants DataFrame, and the
            mainland boundary).
        criteria: The global CriteriaParams block from parameters.json.
        country_criteria: This country's CountryParams.criteria — the
            adapter unwraps its VerifiedValue fields into the plain
            values the compute functions take.

    Returns:
        A SuitabilityCriteriaInputs instance.

    Raises:
        SuitabilityCriteriaRequiresBordersError: If `acquisition_result`
            has no `borders` layer, or that layer's path is None.
    """
    layers = {layer.layer_name: layer for layer in acquisition_result.layers}

    aligned = {field: getattr(grid_result, field) for field in _ALIGNED_RASTER_FIELDS}

    protected_layer = layers.get("protected")
    wdpa_path = protected_layer.path if protected_layer else None

    plants_df = load_power_plants_df(layers.get("power_plants"))

    borders_layer = layers.get("borders")
    if borders_layer is None or borders_layer.path is None:
        raise SuitabilityCriteriaRequiresBordersError(
            f"suitability_criteria requires a resolved 'borders' layer for "
            f"{acquisition_result.country_code!r} to build the mainland mask — "
            f"AcquisitionResult has none (path=None or layer missing)."
        )
    mainland_gdf = load_mainland_boundary(borders_layer.path)

    return SuitabilityCriteriaInputs(
        **aligned,
        grid_metadata=grid_result.grid_metadata,
        criteria=criteria,
        yield_by_land_cover=country_criteria.yield_by_land_cover.value,
        terrain_slope_threshold_deg=country_criteria.terrain_slope_threshold_deg.value,
        wdpa_path=wdpa_path,
        mainland_gdf=mainland_gdf,
        context_gdf=None,
        plants_df=plants_df,
    )
