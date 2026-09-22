"""Unit tests for geofrea.data_acquisition.phase.

As of 2026-09-11 (2026-08-25 "real fetchers for power_plants/wind/
lakes/rivers" + 2026-08-26 "real fetcher for borders/admin1" +
2026-09-11 "protected_planet API activation", all docs/DECISIONS.md),
run_acquisition_phase() calls real fetcher functions for 7 layers —
every test in this file must NOT hit the real network. The
`_no_network_fetchers` autouse fixture below monkeypatches all 7
fetcher names in the `phase` module to return None by default
(matching these functions' own documented behavior when a real fetch
fails — see fetchers/*.py), so every existing structural test keeps
working unchanged: "no real fetch happens in this test" looks identical
to "the fetch failed" from run_acquisition_phase()'s point of view.
Tests that specifically exercise the wiring itself override individual
fetchers to return a real value. `fetch_protected_areas` differs from
the other 6 in that it can also *raise*
(ProtectedPlanetTokenMissingError when no API token is configured) —
see test_run_acquisition_phase_protected_token_missing_propagates below.

2026-09-08 (see docs/DECISIONS.md same date, "wire das 5 camadas
restantes a partir do banco local, Fase 1"): run_acquisition_phase()
also resolves elevation/population/grid/land_cover from the local
database (local_layers.py) unconditionally on every call. The
`_no_raw_data_dir` autouse fixture below clears GEOFREA_RAW_DATA_DIR so
every existing structural test keeps passing unchanged, exactly like
`_no_network_fetchers` above — an unset env var makes those 4 resolvers
gracefully return None/[] (see local_layers.py's module docstring, "two
different failure modes"), the same as a fetcher returning None. Tests
that specifically exercise this new wiring monkeypatch the resolver
functions themselves, same pattern as the fetcher tests below.
"""

from pathlib import Path

import pytest

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import Orchestrator, PhaseContext, PhaseSpec
from geofrea.data_acquisition import phase as phase_module
from geofrea.data_acquisition.local_layers import RAW_DATA_DIR_ENV_VAR
from geofrea.data_acquisition.phase import _LAYER_REGISTRY, run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"

_FETCHER_NAMES = (
    "fetch_power_plants",
    "fetch_wind",
    "fetch_lakes",
    "fetch_rivers",
    "fetch_borders",
    "fetch_admin1",
    "fetch_protected_areas",
)

@pytest.fixture(autouse=True)
def _no_network_fetchers(monkeypatch):
    for name in _FETCHER_NAMES:
        monkeypatch.setattr(phase_module, name, lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _no_raw_data_dir(monkeypatch):
    monkeypatch.delenv(RAW_DATA_DIR_ENV_VAR, raising=False)


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
def test_run_acquisition_phase_only_protected_requires_auth_2026_09_11(tmp_path):
    # Until 2026-09-08, land_cover was the one layer with
    # auth_required=True (Terrascope). It reverted to local_only that
    # stage (see docs/DECISIONS.md 2026-09-08, "wire das 5 camadas
    # restantes a partir do banco local, Fase 1") — the local ESA
    # WorldCover tiles need no credentials, so no layer required auth
    # for a few days. 2026-09-11 (see DECISIONS.md same date,
    # "protected_planet API activation") gave `protected` a real,
    # credentialed fetcher (Protected Planet API token) — it is now the
    # one layer that requires auth.
    result = run_acquisition_phase(_context(tmp_path))

    auth_required_names = {
        layer.layer_name for layer in result.layers if layer.auth_required
    }
    assert auth_required_names == {"protected"}


@pytest.mark.unit
def test_run_acquisition_phase_global_layers_have_no_country_code(tmp_path):
    result = run_acquisition_phase(_context(tmp_path))
    layers_by_name = {layer.layer_name: layer for layer in result.layers}

    # protected moved into this list 2026-08-24 (was incorrectly
    # country_specific=True — see phase.py's _LAYER_REGISTRY comment
    # and DECISIONS.md 2026-08-24 "vector layer audit depth"). roads
    # moved into this list 2026-09-08 for the same reason — its source
    # is now a single GRIP4 regional file shared across countries, not
    # a per-country download (see DECISIONS.md same date, Fase 2).
    for name in (
        "solar",
        "lakes",
        "rivers",
        "seismic",
        "power_plants",
        "protected",
        "roads",
    ):
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
def test_run_acquisition_phase_provenance_split_2026_09_11(tmp_path):
    # Updated 2026-08-25 (real fetchers for power_plants/wind/lakes/
    # rivers) then 2026-09-08 (see DECISIONS.md same date, "wire das 5
    # camadas restantes a partir do banco local", Fase 1 for
    # land_cover/elevation/population/grid, Fase 2 for roads):
    # land_cover/elevation/population/grid/roads all REVERTED from
    # fetched to local_only — not a bug fix, an explicit scope reversal
    # now that they resolve from the local database instead. Then
    # 2026-09-11 (see DECISIONS.md same date, "protected_planet API
    # activation") protected moved local_only -> fetched, once a real
    # API token was placed in .env. solar/seismic stay local_only, no
    # confirmed automatable source (solar gained a local-path resolver
    # 2026-09-11 too, provenance unchanged — resolving a bundled path
    # is not fetching).
    result = run_acquisition_phase(_context(tmp_path))

    fetched = {layer.layer_name for layer in result.layers if layer.provenance == "fetched"}
    local_only = {
        layer.layer_name for layer in result.layers if layer.provenance == "local_only"
    }

    assert fetched == {
        "borders",
        "admin1",
        "wind",
        "lakes",
        "rivers",
        "power_plants",
        "protected",
    }
    assert local_only == {
        "land_cover",
        "elevation",
        "population",
        "grid",
        "roads",
        "solar",
        "seismic",
    }


@pytest.mark.unit
def test_run_acquisition_phase_fetch_status_split_2026_09_11(tmp_path):
    # fetch_status (AcquiredLayer, schemas.py — a computed field, not
    # stored) answers "is there real fetch code wired in today", which
    # provenance deliberately does not (see the test above and
    # docs/DECISIONS.md 2026-08-26, "fetch_status computed field").
    # implemented: the 7 layers with a real handler in
    # _FETCHED_LAYER_HANDLERS (borders/admin1 added 2026-08-26, protected
    # added 2026-09-11 — see DECISIONS.md same dates).
    # implemented_not_activated: none today (empty — protected was the
    # only member and it activated 2026-09-11). not_implemented: the
    # other 7 — the 5 remaining skeleton layers (still no fetch code at
    # all) plus solar/seismic (no confirmed automatable source, decided
    # not to pursue).
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
        "protected",
    }
    assert by_status["implemented_not_activated"] == set()
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
    "layer_name",
    ["power_plants", "wind", "lakes", "rivers", "borders", "admin1", "protected"],
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
        "protected": "fetch_protected_areas",
    }[layer_name]
    monkeypatch.setattr(phase_module, handler_name, lambda *args, **kwargs: fake_path)

    result = run_acquisition_phase(_context(tmp_path))

    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    assert layers_by_name[layer_name].path == fake_path
    assert result.summary.layers_resolved == 1


@pytest.mark.unit
def test_run_acquisition_phase_does_not_call_fetchers_for_unrelated_layers(tmp_path, monkeypatch):
    # Only the 7 layers in _FETCHED_LAYER_HANDLERS should ever invoke a
    # fetcher — every other layer_name must never trigger a call.
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


@pytest.mark.unit
def test_run_acquisition_phase_protected_token_missing_propagates(tmp_path, monkeypatch):
    # Mirrors test_run_acquisition_phase_rivers_unmapped_country_
    # propagates_keyerror above: fetch_protected_areas() deliberately
    # raises ProtectedPlanetTokenMissingError when no API token is
    # configured (a configuration gap, not a transient network failure
    # — see fetchers/protected_planet.py's _require_token) — this phase
    # must NOT swallow it either, unlike a real network error (which
    # that fetcher already catches internally and returns None for).
    from geofrea.data_acquisition.fetchers.protected_planet import (
        ProtectedPlanetTokenMissingError,
    )

    def _raise_missing_token(*args, **kwargs):
        raise ProtectedPlanetTokenMissingError("no token")

    monkeypatch.setattr(phase_module, "fetch_protected_areas", _raise_missing_token)

    with pytest.raises(ProtectedPlanetTokenMissingError):
        run_acquisition_phase(_context(tmp_path))


@pytest.mark.unit
@pytest.mark.parametrize("layer_name", ["elevation", "population", "grid", "roads", "solar"])
def test_run_acquisition_phase_populates_path_from_local_resolver(
    tmp_path, monkeypatch, layer_name
):
    fake_path = tmp_path / f"{layer_name}.fake"
    handler_name = {
        "elevation": "resolve_elevation_path",
        "population": "resolve_population_path",
        "grid": "resolve_grid_path",
        "roads": "resolve_roads_path",
        "solar": "resolve_solar_path",
    }[layer_name]
    monkeypatch.setattr(phase_module, handler_name, lambda country_code: fake_path)

    result = run_acquisition_phase(_context(tmp_path))

    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    assert layers_by_name[layer_name].path == fake_path
    assert result.summary.layers_resolved == 1


@pytest.mark.unit
def test_run_acquisition_phase_populates_paths_from_land_cover_resolver(tmp_path, monkeypatch):
    fake_tiles = [tmp_path / "tile_a.tif", tmp_path / "tile_b.tif"]
    monkeypatch.setattr(
        phase_module, "resolve_land_cover_tiles", lambda country_code, country_gdf: fake_tiles
    )

    result = run_acquisition_phase(_context(tmp_path))

    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    assert layers_by_name["land_cover"].paths == fake_tiles
    assert layers_by_name["land_cover"].path is None
    assert result.summary.layers_resolved == 1


@pytest.mark.unit
def test_run_acquisition_phase_local_resolvers_receive_country_code(tmp_path, monkeypatch):
    received = []
    monkeypatch.setattr(
        phase_module,
        "resolve_elevation_path",
        lambda country_code: received.append(country_code) or None,
    )

    run_acquisition_phase(_context(tmp_path, country_code="BRA"))

    assert received == ["BRA"]


@pytest.mark.unit
def test_run_acquisition_phase_does_not_call_local_resolvers_for_unrelated_layers(
    tmp_path, monkeypatch
):
    called = []
    monkeypatch.setattr(
        phase_module,
        "resolve_elevation_path",
        lambda country_code: called.append("elevation") or None,
    )

    run_acquisition_phase(_context(tmp_path))

    assert called == ["elevation"]


@pytest.mark.unit
def test_run_acquisition_phase_elevation_unmapped_country_propagates_keyerror(
    tmp_path, monkeypatch
):
    # Mirrors test_run_acquisition_phase_rivers_unmapped_country_propagates_keyerror
    # above: local_layers.py's resolve_elevation_path()/
    # resolve_land_cover_tiles() deliberately raise KeyError for a
    # country outside their lookup tables (a configuration gap, not a
    # transient failure — see local_layers.py's module docstring) —
    # this phase must NOT swallow it either.
    def _raise_unmapped(country_code):
        raise KeyError(country_code)

    monkeypatch.setattr(phase_module, "resolve_elevation_path", _raise_unmapped)

    with pytest.raises(KeyError):
        run_acquisition_phase(_context(tmp_path))


@pytest.mark.unit
def test_run_acquisition_phase_roads_unmapped_country_propagates_keyerror(tmp_path, monkeypatch):
    # local_layers.py's resolve_roads_path() has its own independent
    # lookup table (_ROADS_COUNTRY_REGION_DIRS, deliberately BRA/PRT
    # only — see that module's docstring) — same KeyError-on-unmapped-
    # country contract as resolve_elevation_path()/
    # resolve_land_cover_tiles(), verified separately since it is a
    # separate table that could independently regress.
    def _raise_unmapped(country_code):
        raise KeyError(country_code)

    monkeypatch.setattr(phase_module, "resolve_roads_path", _raise_unmapped)

    with pytest.raises(KeyError):
        run_acquisition_phase(_context(tmp_path))


@pytest.mark.unit
def test_run_acquisition_phase_local_layers_resolve_to_none_without_raw_data_dir(tmp_path):
    # With GEOFREA_RAW_DATA_DIR unset (the _no_raw_data_dir autouse
    # fixture's default) and no monkeypatched resolver, elevation/
    # population/grid/roads/land_cover fall back to the real
    # local_layers.py resolvers, which gracefully return None/[] rather
    # than raising — same contract as a real fetcher failing.
    result = run_acquisition_phase(_context(tmp_path))

    layers_by_name = {layer.layer_name: layer for layer in result.layers}
    for name in ("elevation", "population", "grid", "roads"):
        assert layers_by_name[name].path is None


@pytest.mark.unit
def test_acquired_layer_round_trips_through_dumped_fetch_status():
    # Regression test for the bug fixed 2026-09-11 (see docs/DECISIONS.md
    # same date, "fetch_status manifest resume bug"): fetch_status is a
    # @computed_field, so model_dump(mode="json") — exactly what
    # Orchestrator._write_manifest() calls — includes it. Feeding that
    # dict back into AcquiredLayer.model_validate() (what resuming from
    # manifest.json does) used to raise `extra_forbidden`, because a
    # computed field cannot be accepted as a constructor input under
    # extra="forbid". schemas.py's _drop_computed_fetch_status before-
    # validator strips it; this asserts the round trip now succeeds and
    # is lossless.
    layer = AcquiredLayer(layer_name="power_plants", provenance="fetched", auth_required=False)
    dumped = layer.model_dump(mode="json")

    assert "fetch_status" in dumped  # sanity: the bug requires this key to be present

    reloaded = AcquiredLayer.model_validate(dumped)

    assert reloaded == layer
    assert reloaded.fetch_status == "implemented"


@pytest.mark.unit
def test_acquired_layer_still_rejects_unrelated_extra_fields():
    # The fix above only special-cases the known `fetch_status` key —
    # it must not turn into a blanket extra="ignore" that would hide a
    # genuinely corrupted/mistyped manifest entry.
    dumped = AcquiredLayer(
        layer_name="power_plants", provenance="fetched", auth_required=False
    ).model_dump(mode="json")
    dumped["typo_field_that_should_not_exist"] = "oops"

    with pytest.raises(Exception, match="typo_field_that_should_not_exist|extra_forbidden"):
        AcquiredLayer.model_validate(dumped)


@pytest.mark.unit
def test_orchestrator_resumes_data_acquisition_phase_from_saved_manifest(tmp_path, monkeypatch):
    # End-to-end reproduction of the bug via the real save -> load ->
    # resume path: run the data_acquisition phase through Orchestrator
    # (which persists AcquisitionResult.model_dump(mode="json") — with
    # every layer's computed fetch_status included — to manifest.json),
    # then build a second Orchestrator pointed at the same outputs_dir
    # to simulate a fresh process resuming. Before the fix, the second
    # Orchestrator's __post_init__ -> _load_manifest() ->
    # RunManifest.model_validate_json() raised extra_forbidden on the
    # first layer's fetch_status; the phase then had to be re-run from
    # scratch instead of resuming.
    #
    # fetch_protected_areas is mocked here (not via the module-level
    # _no_network_fetchers fixture, which predates "protected"'s
    # 2026-09-11 activation and is unrelated to this bug) purely so this
    # test doesn't require a real PROTECTED_PLANET_API_KEY / network
    # access — it plays no part in the fetch_status bug being tested.
    monkeypatch.setattr(phase_module, "fetch_protected_areas", lambda *a, **kw: None)

    country_code = "PRT"
    country_params = load_parameters(PARAMETERS_JSON).countries[country_code]
    phase_specs = [
        PhaseSpec(
            name="data_acquisition",
            output_model=AcquisitionResult,
            run=run_acquisition_phase,
        )
    ]

    first_run = Orchestrator(
        outputs_dir=tmp_path,
        country_code=country_code,
        country_params=country_params,
        target_phases=["data_acquisition"],
        force_rerun=False,
        run_id="test-run-id",
        dirty=False,
    )
    first_results = first_run.run(phase_specs)
    assert first_results["data_acquisition"].status == "success"
    assert first_run.manifest_path.exists()

    # Simulates the next process/invocation for the same country: a
    # fresh Orchestrator that loads the manifest.json just written.
    resumed_run = Orchestrator(
        outputs_dir=tmp_path,
        country_code=country_code,
        country_params=country_params,
        target_phases=["data_acquisition"],
        force_rerun=False,
        run_id="test-run-id",
        dirty=False,
    )
    resumed_results = resumed_run.run(phase_specs)

    resumed_result = resumed_results["data_acquisition"]
    assert resumed_result.status == "success"
    assert isinstance(resumed_result.output, AcquisitionResult)
    assert resumed_result.output == first_results["data_acquisition"].output
