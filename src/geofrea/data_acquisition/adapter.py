"""Converts data_acquisition's output into data_quality_audit's input.

This is local-file glue (pandas.read_csv, geopandas.read_file), not
fetch/download logic — no HTTP call, no external SDK, no .env read
happens here. It only interprets paths that run_acquisition_phase()
already resolved (currently always None in the skeleton — see phase.py
— so every branch below that reads a file is present but unexercised
until real fetch logic exists).

KNOWN GAP, flagged rather than improvised (per this stage's
instructions): AuditInputs (geofrea/data_quality_audit/schemas.py) has
no field to record provenance ("fetched" vs "local_only") for any of
its paths — it is a flat bag of already-resolved Path/DataFrame/
GeoDataFrame values with no per-field metadata at all. This adapter is
therefore necessarily LOSSY: AcquiredLayer.provenance/auth_required/
source_name/crs_metadata are all dropped during conversion, because
AuditInputs has nowhere to put them. Not fixed here — changing
AuditInputs to carry provenance was explicitly out of scope for this
stage ("NÃO improvise — pare e reporte a divergência antes de alterar
AuditInputs"). If audit-phase reporting ever needs to say "this raster
came from Terrascope" vs "this was a bundled local file", AuditInputs
itself needs a schema change first, authorized as its own stage.

wind vs. land_cover (RESOLVED 2026-08-24, see DECISIONS.md same date
and schemas.py's module docstring): wind maps from AcquiredLayer.path,
wrapped into a one-element list — AuditInputs' own docstring confirms
only the first wind file is ever inspected, so a single resolved path
is not lossy for wind. land_cover maps from AcquiredLayer.paths (the
dedicated multi-file field) directly, since every ESA tile is actually
consumed downstream. These are NOT symmetric by oversight — wind
staying single-path and land_cover getting a list field were each a
deliberate call, not the same fix applied twice.

THIRD KNOWN GAP, NOT defensive by design (flagged, not fixed — see
DECISIONS.md 2026-08-24): load_power_plants_df()/_load_mainland_boundary()
below have no try/except. A malformed CSV either silently parses into
garbage (pandas does not always raise) or raises pandas.errors.
EmptyDataError; a corrupted/non-geospatial file at the boundary path
raises pyogrio's DataSourceError. Both propagate straight out of this
adapter today — unlike data_quality_audit's inspect_raster() and (as of
2026-08-24) inspect_vector_layer(), both of which catch broadly and
report {"error": str(exc)} instead of raising. Left as-is pending
authorization — see tests/unit/test_data_acquisition_adapter.py's
characterization tests for the exact exceptions each failure mode
raises. Note this gap is specific to load_power_plants_df()/
_load_mainland_boundary() — the plain pass-through Path fields added
2026-08-24 (protected_path, admin1_path, grid_path, roads_path,
borders_path) never open the file here at all, so there is nothing to
catch in this module for them; the file is only ever opened later,
inside data_quality_audit/vector_inspection.py.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from geofrea.core.geo_utils import load_mainland_boundary
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult
from geofrea.data_quality_audit.schemas import AuditInputs

# layer_name -> AuditInputs single-Path field. power_plants needs
# special handling below (loaded, not just passed through); wind is
# wrapped into a list; land_cover uses .paths — see module docstring
# "wind vs. land_cover".
#
# protected/admin1/grid/roads were added 2026-08-24 (see DECISIONS.md
# same date, "vector layer audit depth") once data_quality_audit grew
# an inspect_vector_layer() that opens these files itself (mirroring
# inspect_raster()'s lazy pattern) — before that, AuditInputs had no
# equivalent field for them at all. `borders` is passed through
# unchanged AS WELL AS consumed by _load_mainland_boundary() below —
# the same AcquiredLayer feeds two different AuditInputs fields
# (borders_path: raw, unopened here; country_gdf: opened + mainland-
# filtered here), not a conflict.
_SINGLE_PATH_FIELDS: dict[str, str] = {
    "solar": "solar_path",
    "elevation": "elevation_path",
    "population": "population_path",
    "lakes": "lakes_path",
    "rivers": "rivers_path",
    "protected": "protected_path",
    "admin1": "admin1_path",
    "grid": "grid_path",
    "roads": "roads_path",
    "borders": "borders_path",
}


def _layers_by_name(result: AcquisitionResult) -> dict[str, AcquiredLayer]:
    return {layer.layer_name: layer for layer in result.layers}


def acquisition_result_to_audit_inputs(
    result: AcquisitionResult, *, skip_land_cover: bool = False
) -> AuditInputs:
    """Build AuditInputs from an AcquisitionResult.

    Args:
        result: The data_acquisition phase's output for one country.
        skip_land_cover: Passed straight through to AuditInputs — not
            derived from acquisition data, it's a separate run-time
            toggle for whether the (slow) ESA tile analysis should run.

    Returns:
        An AuditInputs instance. Every path is None / every list is
        empty while run_acquisition_phase() remains a skeleton (see
        phase.py) — this function is correct-but-inert until then,
        except for the gaps flagged in the module docstring (provenance
        loss; no defensive handling on the two loaders), which stay
        gapped regardless of whether paths are populated.
    """
    layers = _layers_by_name(result)

    single_paths = {
        field_name: layers[layer_name].path
        for layer_name, field_name in _SINGLE_PATH_FIELDS.items()
        if layer_name in layers
    }

    wind_layer = layers.get("wind")
    wind_paths = [wind_layer.path] if wind_layer and wind_layer.path else []

    land_cover_layer = layers.get("land_cover")
    land_cover_tiles = land_cover_layer.paths if land_cover_layer else []

    plants_df = load_power_plants_df(layers.get("power_plants"))
    country_gdf = _load_mainland_boundary(layers.get("borders"))

    return AuditInputs(
        **single_paths,
        wind_paths=wind_paths,
        land_cover_tiles=land_cover_tiles,
        plants_df=plants_df,
        country_gdf=country_gdf,
        skip_land_cover=skip_land_cover,
    )


def load_power_plants_df(layer: AcquiredLayer | None) -> pd.DataFrame | None:
    """Load the power-plants CSV, if a path was resolved for it.

    Public (not `_`-prefixed, unlike the rest of this module's small
    per-field loaders): grid_alignment/adapter.py needs the identical
    logic for its own plants_df field and imports this directly rather
    than duplicating it — see docs/DECISIONS.md 2026-09-08,
    grid_alignment orchestrator wiring, for why (same "don't
    mechanically duplicate" care already applied to the mainland-
    boundary derivation below).
    """
    if layer is None or layer.path is None:
        return None
    return pd.read_csv(layer.path)


def _load_mainland_boundary(layer: AcquiredLayer | None) -> gpd.GeoDataFrame | None:
    """Load the country boundary and reduce it to its mainland polygon.

    The None-handling (falls back to None, not an error) is specific to
    this adapter: data_quality_audit has a degraded-but-useful mode
    when country_gdf is missing (AuditInputs.country_gdf is Optional —
    see that field's docstring). The mechanical read+mainland-filter
    itself is shared via core.geo_utils.load_mainland_boundary() (
    extracted 2026-09-08, see docs/DECISIONS.md same date) —
    grid_alignment/adapter.py calls the SAME shared function but
    raises instead of returning None when borders is missing, since it
    has no equivalent degraded mode.
    """
    if layer is None or layer.path is None:
        return None
    return load_mainland_boundary(layer.path)
