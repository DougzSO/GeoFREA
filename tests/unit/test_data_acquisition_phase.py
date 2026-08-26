"""Unit tests for geofrea.data_acquisition.phase.

As of 2026-08-26 (2026-08-25 "real fetchers for power_plants/wind/
lakes/rivers" + 2026-08-26 "real fetcher for borders/admin1", both
docs/DECISIONS.md), run_acquisition_phase() calls real fetcher
functions for 6 layers — every test in this file must NOT hit the real
network. The `_no_network_fetchers` autouse fixture below monkeypatches
all 6 fetcher names in the `phase` module to return None by default
(matching these functions' own documented behavior when a real fetch
fails — see fetchers/*.py), so every existing structural test keeps
working unchanged: "no real fetch happens in this test" looks identical
to "the fetch failed" from run_acquisition_phase()'s point of view.
Tests that specifically exercise the wiring itself override individual
fetchers to return a real value.
"""

from pathlib import Path

import pytest

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import PhaseContext
from geofrea.data_acquisition import phase as phase_module
from geofrea.data_acquisition.phase import _LAYER_REGISTRY, run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquisitionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"

_FETCHER_NAMES = (
    "fetch_power_plants",
    "fetch_wind",
    "fetch_lakes",
    "fetch_rivers",
    "fetch_borders",
    "fetch_admin1",
)


@pytest.fixture(autouse=True)
def _no_network_fetchers(monkeypatch):
    for name in _FETCHER_NAMES:
        monkeypatch.setattr(phase_module, name, lambda *args, **kwargs: None)


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
def test_run_acquisition_phase_every_layer_path_is_none_when_fetchers_fail(tmp_path):
    # With every real fetcher mocked to return None (the
    # _no_network_fetchers default — matches how these functions
    # actually behave on a real network failure, see fetchers/*.py),
    # every AcquiredLayer.path stays None regardless of provenance.
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
def test_run_acquisition_phase_provenance_split_2026_08_25(tmp_path):
    # Updated 2026-08-25 (see DECISIONS.md same date, "real fetchers
    # for power_plants/wind/lakes/rivers"): power_plants/wind/lakes/
    # rivers moved from local_only to fetched — real, live-verified
    # fetchers now exist for them. protected keeps a real fetcher too
    # (fetchers/protected_planet.py) but its provenance stays
    # local_only, gated behind a manual API token — not activated.
    # solar/seismic stay local_only, no confirmed automatable source.
    result = run_acquisition_phase(_context(tmp_path))

    fetched = {layer.layer_name for layer in result.layers if layer.provenance == "fetched"}
    local_only = {
        layer.layer_name for layer in result.layers if layer.provenance == "local_only"
    }

    assert fetched == {
        "borders",
        "admin1",
        "land_cover",
        "elevation",
        "population",
        "grid",
        "roads",
        "wind",
        "lakes",
        "rivers",
        "power_plants",
    }
    assert local_only == {"protected", "solar", "seismic"}


@pytest.mark.unit
def test_run_acquisition_phase_fetch_status_split_2026_08_26(tmp_path):
    # fetch_status (AcquiredLayer, schemas.py — a computed field, not
    # stored) answers "is there real fetch code wired in today", which
    # provenance deliberately does not (see the test above and
    # docs/DECISIONS.md 2026-08-26, "fetch_status computed field").
    # implemented: the 6 layers with a real handler in
    # _FETCHED_LAYER_HANDLERS (borders/admin1 added 2026-08-26, see
    # DECISIONS.md same date "real fetcher for borders/admin1").
    # implemented_not_activated: protected only — fetcher complete and
    # tested (fetchers/protected_planet.py) but gated behind a manual
    # API token. not_implemented: the other 7 — the 5 remaining skeleton
    # layers (still no fetch code at all) plus solar/seismic (no
    # confirmed automatable source, decided not to pursue).
    result = run_acquisition_phase(_context(tmp_path))

    by_status: dict[str, set[str]] = {
        "implemented": set(),
        "implemented_not_activated": set(),
        "not_implemented": set(),
    }
    for layer in result.layers:
        by_status[layer.fetch_status].add(layer.layer_name)

    assert by_status["implemented"] == {
        "power_plants",
        "wind",
        "lakes",
        "rivers",
        "borders",
        "admin1",
    }
    assert by_status["implemented_not_activated"] == {"protected"}
    assert by_status["not_implemented"] == {
        "land_cover",
        "elevation",
        "population",
        "grid",
        "roads",
        "solar",
        "seismic",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "layer_name", ["power_plants", "wind", "lakes", "rivers", "borders", "admin1"]
)
def test_run_acquisition_phase_populates_path_when_fetcher_succeeds(
    tmp_path, monkeypatch, layer_name
):
    fake_path = tmp_path / f"{layer_name}.fake"
    handler_name = {
        "power_plants": "fetch_power_plants",
        "wind": "fetch_wind",
        "lakes": "fetch_lakes",
        "rivers": "fetch_rivers",
        "borders": "fetch_borders",
        "admin1": "fetch_admin1",
    }[layer_name]
    monkeypatch.setattr(phase_module, handler_name, lambda *args, **kwargs: fake_path)

    result = run_acquisition_phase(_context(tmp_path))

    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    assert layers_by_name[layer_name].path == fake_path
    assert result.summary.layers_resolved == 1


@pytest.mark.unit
def test_run_acquisition_phase_does_not_call_fetchers_for_unrelated_layers(tmp_path, monkeypatch):
    # Only the 6 layers in _FETCHED_LAYER_HANDLERS should ever invoke a
    # fetcher — every other layer_name, including protected (fetcher
    # exists, not wired in), must never trigger a call.
    called = []
    monkeypatch.setattr(
        phase_module, "fetch_power_plants", lambda *a, **k: called.append("power_plants") or None
    )

    run_acquisition_phase(_context(tmp_path))

    assert called == ["power_plants"]


@pytest.mark.unit
def test_run_acquisition_phase_rivers_unmapped_country_propagates_keyerror(tmp_path, monkeypatch):
    # hydrosheds.fetch_rivers() deliberately raises KeyError for a
    # country outside _COUNTRY_TO_REGION (a configuration gap, not a
    # transient failure — see phase.py's _FETCHED_LAYER_HANDLERS
    # comment) — this phase must NOT swallow it.
    def _raise_unmapped(*args, **kwargs):
        raise KeyError("XXX")

    monkeypatch.setattr(phase_module, "fetch_rivers", _raise_unmapped)

    with pytest.raises(KeyError):
        run_acquisition_phase(_context(tmp_path))
