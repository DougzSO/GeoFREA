"""Converts data_acquisition's output into grid_alignment's input.

Mirrors data_acquisition/adapter.py::acquisition_result_to_audit_inputs()
— same shape, same source type (AcquisitionResult), same local-file glue
(no HTTP, no SDK). See docs/DECISIONS.md 2026-09-08, grid_alignment
orchestrator wiring.

Deliberately depends ONLY on AcquisitionResult, never on AuditResult —
this was checked explicitly before writing this module (AuditResult has
no country_gdf field; get_mainland_gdf() is called by
data_acquisition/adapter.py, not by data_quality_audit). Matches Passo 1's
already-closed design principle (grid_alignment must not depend on
data_quality_audit's PhaseResult) — depending on AuditResult here would
have silently reintroduced that same coupling one phase down.

country_gdf: REQUIRED, unlike AuditInputs.country_gdf (Optional there —
audit degrades gracefully to "areas cover the whole file" without one).
grid_alignment has no equivalent degraded mode (see GridAlignmentInputs'
own docstring, schemas.py) — build_reference_grid() IS country_gdf's
bounds, so a missing boundary is a configuration gap, not a per-file
data problem. Same class of guard as vector_inspection.py's
ClipRequiresCountryGdfError (added 2026-08-26 after a real RAM incident
from country_gdf silently being None) — fails loud at adapter
construction time, not lazily inside run_grid_alignment_phase().

Layer-name -> field-name map deliberately differs from
data_acquisition/adapter.py's _SINGLE_PATH_FIELDS for two entries:
roads -> roads_source, grid -> grid_source (not roads_path/grid_path),
matching GridAlignmentInputs' own deliberate rename (see schemas.py's
module docstring — visibly marks these as raw AcquiredLayer.path,
never a data_quality_audit artifact). protected/admin1/borders are NOT
mapped here at all: grid_alignment (like legacy's GridAligner.run())
never consumes protected or admin1, and borders feeds country_gdf only,
not a passthrough field (GridAlignmentInputs has no borders_path).

wind: known gap, not fixed here. AcquisitionResult only ever holds ONE
wind AcquiredLayer.path (wind is not in MULTI_FILE_LAYER_NAMES — see
data_acquisition/schemas.py), so this adapter can only ever produce a
one-element (or empty) wind_paths list, even though
GridAlignmentInputs.wind_paths / combine_wind_layers() were ported to
support up to 3 height variants (legacy's real capability).
combine_wind_layers() handles a single file correctly (uniform weight
= 1.0, AHP never triggers since len(present) != 3) — not broken, just
unable to exercise the AHP branch until data_acquisition's layer
registry can hold multiple wind heights per country, which is out of
scope here (would require changing AcquiredLayer/MULTI_FILE_LAYER_NAMES,
a data_acquisition-schema change, not an adapter concern).
"""

from __future__ import annotations

from geofrea.core.geo_utils import load_mainland_boundary
from geofrea.core.schemas import ResolutionsConfig
from geofrea.data_acquisition.adapter import load_power_plants_df
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult
from geofrea.grid_alignment.schemas import GridAlignmentInputs

# layer_name -> GridAlignmentInputs single-Path field. wind/land_cover/
# plants_df/country_gdf need special handling below — see module
# docstring.
_SOURCE_PATH_FIELDS: dict[str, str] = {
    "elevation": "elevation_path",
    "solar": "solar_path",
    "population": "population_path",
    "seismic": "seismic_path",
    "lakes": "lakes_path",
    "rivers": "rivers_path",
    "roads": "roads_source",
    "grid": "grid_source",
}


class GridAlignmentRequiresBordersError(ValueError):
    """Raised when AcquisitionResult has no usable `borders` layer.

    grid_alignment cannot build a reference grid without a country
    boundary — there is no degraded mode to fall back to (see module
    docstring). Same class of gap as ClipRequiresCountryGdfError
    (vector_inspection.py, added 2026-08-26 after a real incident where
    a silently-None country_gdf let an unclipped global file be read in
    full): a configuration/wiring problem, not a per-file data problem,
    so it must fail loudly at adapter construction time rather than
    surface later as a confusing failure inside run_grid_alignment_phase().
    """


def _layers_by_name(result: AcquisitionResult) -> dict[str, AcquiredLayer]:
    return {layer.layer_name: layer for layer in result.layers}


def acquisition_result_to_grid_alignment_inputs(
    result: AcquisitionResult, resolutions: ResolutionsConfig | None = None
) -> GridAlignmentInputs:
    """Build GridAlignmentInputs from an AcquisitionResult.

    Args:
        result: The data_acquisition phase's output for one country.
        resolutions: settings.yaml's `geospatial.resolutions` (see
            docs/DECISIONS.md 2026-09-09, grid_alignment Passo 4 item 3).
            None (default) falls back to ResolutionsConfig()'s own
            defaults — 0.01 fixed, matching the frozen baseline.

    Returns:
        A GridAlignmentInputs instance.

    Raises:
        GridAlignmentRequiresBordersError: If `result` has no `borders`
            layer, or that layer's `path` is None — see module docstring.
    """
    resolutions = resolutions or ResolutionsConfig()
    layers = _layers_by_name(result)

    source_paths = {
        field_name: layers[layer_name].path
        for layer_name, field_name in _SOURCE_PATH_FIELDS.items()
        if layer_name in layers
    }

    wind_layer = layers.get("wind")
    wind_paths = [wind_layer.path] if wind_layer and wind_layer.path else []

    land_cover_layer = layers.get("land_cover")
    land_cover_tiles = land_cover_layer.paths if land_cover_layer else []

    plants_df = load_power_plants_df(layers.get("power_plants"))

    borders_layer = layers.get("borders")
    if borders_layer is None or borders_layer.path is None:
        raise GridAlignmentRequiresBordersError(
            f"grid_alignment requires a resolved 'borders' layer for "
            f"{result.country_code!r} to build country_gdf — "
            f"AcquisitionResult has none (path=None or layer missing)."
        )
    country_gdf = load_mainland_boundary(borders_layer.path)

    return GridAlignmentInputs(
        **source_paths,
        wind_paths=wind_paths,
        land_cover_tiles=land_cover_tiles,
        plants_df=plants_df,
        country_gdf=country_gdf,
        resolution_deg=resolutions.suitability,
        adaptive_target_pixels=resolutions.adaptive.target_pixels,
        adaptive_min_deg=resolutions.adaptive.min_deg,
        adaptive_max_deg=resolutions.adaptive.max_deg,
    )
