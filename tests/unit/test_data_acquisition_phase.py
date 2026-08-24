"""Unit tests for geofrea.data_acquisition.phase (structure-only skeleton).

No fetch/download logic exists yet (see phase.py's module docstring),
so these tests only confirm the structural contract: a valid
AcquisitionResult with the expected layer registry, all paths None.
"""

from pathlib import Path

import pytest

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import PhaseContext
from geofrea.data_acquisition.phase import _LAYER_REGISTRY, run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquisitionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"


def _context(tmp_path: Path, country_code: str = "PRT") -> PhaseContext:
    country_params = load_parameters(PARAMETERS_JSON).countries[country_code]
    return PhaseContext(
        country_code=country_code,
        country_params=country_params,
        outputs_dir=tmp_path,
        prior_results={},
    )


@pytest.mark.unit
def test_run_acquisition_phase_returns_valid_result(tmp_path):
    result = run_acquisition_phase(_context(tmp_path))

    assert isinstance(result, AcquisitionResult)
    assert result.country_code == "PRT"
    assert len(result.layers) == len(_LAYER_REGISTRY)


@pytest.mark.unit
def test_run_acquisition_phase_every_layer_path_is_none(tmp_path):
    result = run_acquisition_phase(_context(tmp_path))

    assert all(layer.path is None for layer in result.layers)
    assert result.summary.layers_resolved == 0


@pytest.mark.unit
def test_run_acquisition_phase_slope_is_not_in_the_registry(tmp_path):
    # Deliberately excluded: slope is derived from elevation in legacy,
    # not fetched or bundled — see schemas.py's module docstring.
    result = run_acquisition_phase(_context(tmp_path))
    layer_names = {layer.layer_name for layer in result.layers}

    assert "slope" not in layer_names
    assert "elevation" in layer_names


@pytest.mark.unit
def test_run_acquisition_phase_only_land_cover_requires_auth(tmp_path):
    result = run_acquisition_phase(_context(tmp_path))
    layers_by_name = {layer.layer_name: layer for layer in result.layers}

    assert layers_by_name["land_cover"].auth_required is True
    auth_required_names = {
        layer.layer_name for layer in result.layers if layer.auth_required
    }
    assert auth_required_names == {"land_cover"}


@pytest.mark.unit
def test_run_acquisition_phase_global_layers_have_no_country_code(tmp_path):
    result = run_acquisition_phase(_context(tmp_path))
    layers_by_name = {layer.layer_name: layer for layer in result.layers}

    # protected moved into this list 2026-08-24 (was incorrectly
    # country_specific=True — see phase.py's _LAYER_REGISTRY comment
    # and DECISIONS.md 2026-08-24 "vector layer audit depth").
    for name in ("solar", "lakes", "rivers", "seismic", "power_plants", "protected"):
        assert layers_by_name[name].country_code is None

    for name in ("borders", "elevation", "wind", "land_cover"):
        assert layers_by_name[name].country_code == "PRT"


@pytest.mark.unit
def test_run_acquisition_phase_reads_country_code_from_context(tmp_path):
    result = run_acquisition_phase(_context(tmp_path, country_code="BRA"))
    assert result.country_code == "BRA"
    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    assert layers_by_name["elevation"].country_code == "BRA"


@pytest.mark.unit
def test_run_acquisition_phase_provenance_split_matches_legacy_download_methods(tmp_path):
    # geoworld_framework's DataFetcher has exactly 6 download_* methods
    # (gadm, land_cover, elevation, worldpop, osm_grid, osm_roads) —
    # borders/admin1 share the GADM download, so that's 6 distinct
    # fetched layers here (admin1 reuses the same download as borders,
    # not a 7th method) plus 8 local_only layers with no fetch method.
    result = run_acquisition_phase(_context(tmp_path))

    fetched = {layer.layer_name for layer in result.layers if layer.provenance == "fetched"}
    local_only = {
        layer.layer_name for layer in result.layers if layer.provenance == "local_only"
    }

    assert fetched == {"borders", "admin1", "land_cover", "elevation", "population", "grid", "roads"}
    assert local_only == {
        "wind",
        "protected",
        "solar",
        "lakes",
        "rivers",
        "seismic",
        "power_plants",
    }
