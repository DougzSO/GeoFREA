"""Unit tests for geofrea.data_acquisition.adapter.

acquisition_result_to_audit_inputs() is real local-file glue (no HTTP,
no SDK — see adapter.py's module docstring), so these tests exercise it
with actual small CSV/GeoJSON fixtures on disk, not just empty inputs.

The "malformed" tests below are CHARACTERIZATION tests: they document
current (non-defensive) behavior — _load_power_plants()/
_load_mainland_boundary() have no try/except, per adapter.py's module
docstring, third known gap — not a spec for how failures *should* be
handled. If that gap is ever fixed (pending Douglas's authorization),
these specific assertions are expected to change.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from pydantic import ValidationError
from pyogrio.errors import DataSourceError
from shapely.geometry import Polygon

from geofrea.data_acquisition.adapter import acquisition_result_to_audit_inputs
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult, AcquisitionSummary
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
    assert audit_inputs.plants_df is None
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
def test_adapter_loads_power_plants_csv(tmp_path):
    csv_path = tmp_path / "plants.csv"
    csv_path.write_text("capacity_mw,primary_fuel\n10.0,Hydro\n5.0,Solar\n", encoding="utf-8")

    result = _result(
        [
            AcquiredLayer(
                layer_name="power_plants",
                provenance="local_only",
                auth_required=False,
                path=csv_path,
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.plants_df is not None
    assert len(audit_inputs.plants_df) == 2
    assert list(audit_inputs.plants_df["primary_fuel"]) == ["Hydro", "Solar"]


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
def test_adapter_empty_power_plants_csv_raises(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")
    result = _result(
        [
            AcquiredLayer(
                layer_name="power_plants",
                provenance="local_only",
                auth_required=False,
                path=csv_path,
            )
        ]
    )

    with pytest.raises(pd.errors.EmptyDataError):
        acquisition_result_to_audit_inputs(result)


@pytest.mark.unit
def test_adapter_garbage_power_plants_csv_does_not_raise_but_parses_garbage(tmp_path):
    # Not every malformed CSV raises: pandas happily parses binary
    # garbage into a nonsense 1-row DataFrame instead of erroring. This
    # is the scarier failure mode of the two — a silent data-quality
    # problem, not a loud one — documented here rather than assumed.
    csv_path = tmp_path / "garbage.csv"
    csv_path.write_bytes(b"\x00\x01\x02not,a,real\ncsv\x00\x00")
    result = _result(
        [
            AcquiredLayer(
                layer_name="power_plants",
                provenance="local_only",
                auth_required=False,
                path=csv_path,
            )
        ]
    )

    audit_inputs = acquisition_result_to_audit_inputs(result)

    assert audit_inputs.plants_df is not None
    assert "capacity_mw" not in [c.lower() for c in audit_inputs.plants_df.columns]


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
