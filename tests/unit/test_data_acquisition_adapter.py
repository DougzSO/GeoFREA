"""Unit tests for geofrea.data_acquisition.adapter.

acquisition_result_to_audit_inputs() is real local-file glue (no HTTP,
no SDK — see adapter.py's module docstring), so these tests exercise it
with actual small CSV/GeoJSON fixtures on disk, not just empty inputs.

The "malformed" tests below are CHARACTERIZATION tests: they document
current (non-defensive) behavior — _load_mainland_boundary()
has no try/except, per adapter.py's module
docstring, third known gap — not a spec for how failures *should* be
handled. If that gap is ever fixed (pending Douglas's authorization),
these specific assertions are expected to change.
"""

from pathlib import Path

import geopandas as gpd
import pytest
from pydantic import ValidationError
from pyogrio.errors import DataSourceError
from shapely.geometry import Polygon

from geofrea.data_acquisition.adapter import acquisition_result_to_audit_inputs
from geofrea.data_acquisition.schemas import (
    AcquiredLayer,
    AcquisitionResult,
    AcquisitionSummary,
    LayerAcquisitionFailedError,
)
from geofrea.data_quality_audit.schemas import AuditInputs


def _empty_summary(n: int = 0) -> AcquisitionSummary:
    return AcquisitionSummary(
        layers_total=n,
        layers_fetched_provenance=0,
        layers_local_only_provenance=n,
        layers_requiring_auth=0,
        layers_resolved=0,
    )


def _result(layers: list[AcquiredLayer]) -> AcquisitionResult:
    return AcquisitionResult(
        country_code="PRT",
        timestamp="2026-08-24T00:00:00+00:00",
        layers=layers,
        summary=_empty_summary(len(layers)),
    )


@pytest.mark.unit
def test_adapter_with_no_resolved_layers_returns_empty_audit_inputs():
    result = _result([])

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert isinstance(audit_inputs, AuditInputs)
    assert audit_inputs.solar_path is None
    assert audit_inputs.elevation_path is None
    assert audit_inputs.country_gdf is None
    assert audit_inputs.wind_paths == []
    assert audit_inputs.land_cover_tiles == []


@pytest.mark.unit
def test_adapter_maps_single_path_fields():
    elevation_path = Path("/fake/elevation.tif")
    result = _result(
        [
            AcquiredLayer(
                layer_name="elevation",
                provenance="fetched",
                auth_required=False,
                path=elevation_path,
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.elevation_path == elevation_path


@pytest.mark.unit
def test_adapter_fails_loud_on_a_failed_layer_never_treats_it_as_absent():
    # Per-layer isolation (2026-09-23, see docs/phases/F1_data_acquisition.md):
    # a layer with resolution_status="failed" must not be read as
    # path=None (an absent/optional layer) — the adapter has to raise
    # LayerAcquisitionFailedError naming it instead.
    result = _result(
        [
            AcquiredLayer(
                layer_name="elevation",
                provenance="local_only",
                auth_required=False,
                path=None,
                resolution_status="failed",
                error_type="KeyError",
                error_location="local_layers.py:42",
                error_message="'XXX'",
            )
        ]
    )

    with pytest.raises(LayerAcquisitionFailedError) as exc_info:
        acquisition_result_to_audit_inputs(result)

    assert exc_info.value.layer_name == "elevation"
    assert "elevation" in str(exc_info.value)
    assert "KeyError" in str(exc_info.value)


@pytest.mark.unit
def test_adapter_ignores_a_layer_name_absent_from_the_registry():
    # As of 2026-08-24 every _LAYER_REGISTRY entry has an AuditInputs
    # equivalent (see DECISIONS.md same date, "vector layer audit
    # depth") — so this now exercises an entirely unrecognized
    # layer_name instead (not something _LAYER_REGISTRY would ever
    # produce), confirming the adapter's lookups degrade safely rather
    # than KeyError.
    result = _result(
        [
            AcquiredLayer(
                layer_name="not_a_real_layer",
                provenance="local_only",
                auth_required=False,
                path=Path("/fake/whatever.shp"),
            )
        ]
    )

    # Must not raise, and must not silently invent an AuditInputs field.
    audit_inputs = acquisition_result_to_audit_inputs(result)
    assert audit_inputs.solar_path is None


@pytest.mark.unit
def test_adapter_maps_protected_admin1_grid_roads_paths():
    # Added 2026-08-24 (see DECISIONS.md same date, "vector layer audit
    # depth"): these four now map straight through to AuditInputs, same
    # as solar/elevation/etc — the file is opened later, inside
    # data_quality_audit/vector_inspection.py, not here. `borders` is
    # covered separately (test_adapter_loads_and_mainland_filters_
    # boundary below): unlike these four, its AcquiredLayer.path is
    # ALSO opened here in the adapter (by _load_mainland_boundary), so
    # it needs a real file on disk, not a fake nonexistent path.
    paths = {
        "protected": Path("/fake/wdpa.shp"),
        "admin1": Path("/fake/admin1.geojson"),
        "grid": Path("/fake/grid.geojson"),
        "roads": Path("/fake/roads.geojson"),
    }
    result = _result(
        [
            AcquiredLayer(
                layer_name=name,
                provenance="local_only",
                auth_required=False,
                path=path,
            )
            for name, path in paths.items()
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.protected_path == paths["protected"]
    assert audit_inputs.admin1_path == paths["admin1"]
    assert audit_inputs.grid_path == paths["grid"]
    assert audit_inputs.roads_path == paths["roads"]


@pytest.mark.unit
def test_adapter_maps_all_five_new_path_fields_from_one_complete_result(tmp_path):
    # Dedicated happy-path test for the 5 fields added 2026-08-24 (see
    # DECISIONS.md same date, "vector layer audit depth"): protected_path,
    # borders_path, admin1_path, grid_path, roads_path — all populated
    # together from a single simulated AcquisitionResult, not split
    # across separate tests each covering a subset. `borders` uses a
    # real file (its AcquiredLayer.path IS opened here, by
    # _load_mainland_boundary) — the other four use fake nonexistent
    # paths (never opened in this module, see module docstring).
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    boundary_path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326").to_file(
        boundary_path, driver="GeoJSON"
    )

    fake_paths = {
        "protected": Path("/fake/wdpa.shp"),
        "admin1": Path("/fake/admin1.geojson"),
        "grid": Path("/fake/grid.geojson"),
        "roads": Path("/fake/roads.geojson"),
    }
    result = _result(
        [
            AcquiredLayer(
                layer_name="borders",
                provenance="fetched",
                auth_required=False,
                path=boundary_path,
            ),
            *(
                AcquiredLayer(
                    layer_name=name,
                    provenance="local_only",
                    auth_required=False,
                    path=path,
                )
                for name, path in fake_paths.items()
            ),
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.borders_path == boundary_path
    assert audit_inputs.protected_path == fake_paths["protected"]
    assert audit_inputs.admin1_path == fake_paths["admin1"]
    assert audit_inputs.grid_path == fake_paths["grid"]
    assert audit_inputs.roads_path == fake_paths["roads"]


@pytest.mark.unit
def test_adapter_all_five_new_path_fields_are_none_when_layer_missing():
    # Confirms CURRENT behavior for a layer absent from the
    # AcquisitionResult entirely (not just path=None on a present
    # layer) — the field-comprehension in acquisition_result_to_audit_inputs
    # (`if layer_name in layers`) simply omits the kwarg, so AuditInputs'
    # own field default (None) applies. Not a new guarantee, just made
    # explicit for the 5 fields added 2026-08-24.
    result = _result([])

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.protected_path is None
    assert audit_inputs.borders_path is None
    assert audit_inputs.admin1_path is None
    assert audit_inputs.grid_path is None
    assert audit_inputs.roads_path is None


@pytest.mark.unit
def test_adapter_wind_path_is_wrapped_into_a_single_element_list():
    # Resolved 2026-08-24 (DECISIONS.md same date): wind stays on
    # AcquiredLayer.path (AuditInputs only ever inspects the first wind
    # file), wrapped into a list for AuditInputs.wind_paths.
    result = _result(
        [
            AcquiredLayer(
                layer_name="wind",
                provenance="local_only",
                auth_required=False,
                path=Path("/fake/wind_01.tif"),
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.wind_paths == [Path("/fake/wind_01.tif")]


@pytest.mark.unit
def test_adapter_wind_path_none_yields_empty_list():
    result = _result(
        [AcquiredLayer(layer_name="wind", provenance="local_only", auth_required=False)]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.wind_paths == []


@pytest.mark.unit
def test_adapter_land_cover_maps_from_the_multi_file_paths_field():
    # Resolved 2026-08-24: land_cover uses AcquiredLayer.paths (every
    # ESA tile is consumed downstream, unlike wind), not .path.
    tiles = [Path("/fake/tile_01.tif"), Path("/fake/tile_02.tif")]
    result = _result(
        [
            AcquiredLayer(
                layer_name="land_cover",
                provenance="fetched",
                auth_required=True,
                path=None,
                paths=tiles,
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.land_cover_tiles == tiles


@pytest.mark.unit
def test_land_cover_with_a_stray_single_path_is_rejected_at_construction():
    # Superseded 2026-08-24 (see DECISIONS.md same date, "path/paths
    # source-of-truth consolidation"): a land_cover AcquiredLayer with
    # `path` set used to be constructible, relying on the adapter to
    # ignore the stray value (see this module's git history). Now
    # AcquiredLayer's own validator rejects it at construction time —
    # the guarantee moved from "the adapter ignores it" to "it cannot
    # exist", which is stronger. This test lives here rather than in
    # test_data_acquisition_schemas.py because it directly replaces
    # the adapter-level test above.
    with pytest.raises(ValidationError, match="land_cover"):
        AcquiredLayer(
            layer_name="land_cover",
            provenance="fetched",
            auth_required=True,
            path=Path("/fake/should_be_ignored.tif"),
            paths=[],
        )


@pytest.mark.unit
def test_adapter_loads_and_mainland_filters_boundary(tmp_path):
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    island = Polygon([(10, 10), (10.1, 10), (10.1, 10.1), (10, 10.1)])
    boundary_path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland, island], crs="EPSG:4326").to_file(
        boundary_path, driver="GeoJSON"
    )

    result = _result(
        [
            AcquiredLayer(
                layer_name="borders",
                provenance="fetched",
                auth_required=False,
                path=boundary_path,
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.country_gdf is not None
    assert len(audit_inputs.country_gdf) == 1
    assert audit_inputs.country_gdf.geometry.iloc[0].area == pytest.approx(mainland.area)
    # borders_path (added 2026-08-24) is the same raw path passed
    # through unopened, alongside country_gdf being derived from it.
    assert audit_inputs.borders_path == boundary_path


@pytest.mark.unit
def test_adapter_passes_through_skip_land_cover_flag():
    result = _result([])

    audit_inputs = acquisition_result_to_audit_inputs(result, skip_land_cover=True)

    assert audit_inputs.skip_land_cover is True


# ─── Characterization tests: current (non-defensive) failure behavior ───


@pytest.mark.unit
def test_adapter_corrupted_boundary_file_raises(tmp_path):
    boundary_path = tmp_path / "corrupt_borders.geojson"
    boundary_path.write_text("this is not valid geojson", encoding="utf-8")
    result = _result(
        [
            AcquiredLayer(
                layer_name="borders",
                provenance="fetched",
                auth_required=False,
                path=boundary_path,
            )
        ]
    )

    with pytest.raises(DataSourceError):
        acquisition_result_to_audit_inputs(result)


@pytest.mark.unit
def test_adapter_resolves_cmip6_paths_from_none_when_registry_absent():
    """No cmip6_registry.json under GEOFREA_DATA_DIR: both model fields are None."""
    result = _result([])

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.cmip6_gfdl_esm4_path is None
    assert audit_inputs.cmip6_miroc6_path is None


@pytest.mark.unit
def test_adapter_resolves_cmip6_paths_from_the_registry_for_the_result_country(tmp_path):
    """The representative historical/tas crop is picked up per model, for PRT only."""
    from geofrea.core import paths as core_paths
    from geofrea.data_acquisition.cmip6_registry import (
        Cmip6CountryCrop,
        Cmip6NativeGrid,
        Cmip6Registry,
        Cmip6RegistryEntry,
    )

    prt_crop_path = tmp_path / "gfdl_esm4_historical_tas_PRT.nc"
    prt_crop_path.write_bytes(b"fake-crop-bytes")
    bra_crop_path = tmp_path / "gfdl_esm4_historical_tas_BRA.nc"
    bra_crop_path.write_bytes(b"fake-crop-bytes")

    grid = Cmip6NativeGrid(
        lat_resolution_deg=1.0, lon_resolution_deg=1.25,
        lat_min=-89.5, lat_max=89.5, lon_min=0.625, lon_max=359.375,
        n_lat=180, n_lon=288,
    )
    registry = Cmip6Registry()
    registry.entries["cmip6/gfdl_esm4/historical/tas"] = Cmip6RegistryEntry(
        model="gfdl_esm4",
        experiment="historical",
        variable="tas",
        status="registered",
        global_path=str(tmp_path / "global.nc"),
        source_sha256="deadbeef",
        realization="r1i1p1f1",
        native_grid=grid,
        country_crops=[
            Cmip6CountryCrop(
                country_code="PRT", path=str(prt_crop_path), cells_before=100, cells_after=10
            ),
            Cmip6CountryCrop(
                country_code="BRA", path=str(bra_crop_path), cells_before=100, cells_after=20
            ),
        ],
    )
    registry_path = core_paths.fetched_raw("cmip6", "_global") / "cmip6_registry.json"
    registry.save(registry_path)

    result = _result([])  # country_code="PRT"
    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.cmip6_gfdl_esm4_path == prt_crop_path
    assert audit_inputs.cmip6_miroc6_path is None  # no miroc6 entry registered at all
