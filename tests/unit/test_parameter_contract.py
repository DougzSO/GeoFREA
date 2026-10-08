"""Parameter contract (U-05, V6, V7): value within range, proxy, uncertain parameters, registry consistency, loaders."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

import main
from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.core.production import (
    ConfigConsistencyError,
    ProductionRunError,
    audit_parameters,
    enforce_production,
    validate_registry,
    validate_run_technologies,
)
from geofrea.core.schemas import ParameterRange, VerifiedValue

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = REPO_ROOT / "config" / "parameters.json"
TECHNOLOGIES = REPO_ROOT / "config" / "technologies.yaml"
EXPERIMENTS = REPO_ROOT / "config" / "experiments.yaml"
_LEGACY_NAME = "opex_fixed_" + "pct_of_capex"  # built from parts so this file does not contain the retired name


def _vv(value, **extra):
    base = {"value": value, "unit": "x", "verified": False, "verification_method": "unverified"}
    return VerifiedValue[float].model_validate({**base, **extra})


def _range(lo, hi):
    return {"min": lo, "max": hi, "distribution": "uniform", "source": "test"}


@pytest.mark.unit
def test_parameter_value_within_range():
    """U-05: min <= value <= max."""
    assert _vv(5.0, range=_range(1.0, 10.0)).value == 5.0
    assert _vv(1.0, range=_range(1.0, 10.0)).value == 1.0
    assert _vv(10.0, range=_range(1.0, 10.0)).value == 10.0
    with pytest.raises(ValidationError, match="must be within range"):
        _vv(0.5, range=_range(1.0, 10.0))
    with pytest.raises(ValidationError, match="must be within range"):
        _vv(10.5, range=_range(1.0, 10.0))
    with pytest.raises(ValidationError, match="must be <= max"):
        ParameterRange.model_validate(_range(3.0, 2.0))


@pytest.mark.unit
def test_every_value_of_the_real_parameters_file_is_within_its_range():
    parameters = load_parameters(PARAMETERS)
    for iso, country in parameters.countries.items():
        for tech in ("solar", "wind"):
            for key, vv in getattr(country.technologies, tech).__dict__.items():
                if vv.range is not None and vv.value is not None:
                    assert vv.range.min <= vv.value <= vv.range.max, (iso, tech, key)


@pytest.mark.unit
def test_proxy_flag_is_true_only_for_bra_and_ind_wind_fixed_om_and_defaults_to_false():
    parameters = load_parameters(PARAMETERS)
    proxies = {
        (iso, tech, key)
        for iso, country in parameters.countries.items()
        for tech in ("solar", "wind")
        for key, vv in getattr(country.technologies, tech).__dict__.items()
        if vv.proxy
    }
    assert proxies == {("BRA", "wind", "opex_fixed_frac"), ("IND", "wind", "opex_fixed_frac")}
    assert _vv(1.0).proxy is False


@pytest.mark.unit
def test_proxy_blocks_production_run():
    """V6: a production run fails when a consumed parameter is a proxy; a development run only warns."""
    parameters, technologies = load_parameters(PARAMETERS), load_technologies(TECHNOLOGIES)
    audit = audit_parameters(parameters, technologies, ["BRA"], ["wind"])
    assert any("BRA wind opex_fixed_frac: proxy value consumed" in e for e in audit.errors)
    with pytest.raises(ProductionRunError, match="proxy value consumed"):
        enforce_production(audit)
    # PRT wind O&M is a Tier 2 transfer of the same quantity and technology: not a proxy
    prt = audit_parameters(parameters, technologies, ["PRT"], ["wind"])
    assert not any("proxy" in e for e in prt.errors)
    # a run that does not consume wind does not consume the proxy
    assert not any("proxy" in e for e in audit_parameters(parameters, technologies, ["BRA"], ["solar"]).errors)


@pytest.mark.unit
def test_uncertain_parameter_requires_range_in_production():
    """U-05: every uncertain parameter needs a value and a range, enforced only in a production run (MS-6 is not finished)."""
    parameters, technologies = load_parameters(PARAMETERS), load_technologies(TECHNOLOGIES)
    audit = audit_parameters(parameters, technologies, ["PRT"], ["solar"])
    assert any("PRT solar capex_usd_per_kw: uncertain parameter has no range" in e for e in audit.errors)
    assert any("PRT solar gamma: uncertain parameter has no entry" in e for e in audit.errors)
    with pytest.raises(ProductionRunError, match="no range"):
        enforce_production(audit)
    # a parameter with a range passes: give capex a range and its finding disappears
    data = parameters.model_dump(mode="json")
    capex = data["countries"]["PRT"]["technologies"]["solar"]["capex_usd_per_kw"]
    capex["range"] = {"min": capex["value"] * 0.5, "max": capex["value"] * 2, "distribution": "uniform", "source": "test"}
    patched = type(parameters).model_validate(data)
    assert not any("PRT solar capex_usd_per_kw" in e for e in audit_parameters(patched, technologies, ["PRT"], ["solar"]).errors)


@pytest.mark.unit
def test_main_refuses_a_production_run_before_any_phase_starts(monkeypatch):
    called = []
    monkeypatch.setattr(main, "run_geofrea", lambda *a, **k: called.append(a) or (True, None, {}))
    assert main.main(["PRT", "--production"]) == 1
    assert called == []


@pytest.mark.unit
def test_no_legacy_opex_names():
    """V7: the fixed O&M is `opex_fixed_frac` everywhere except the archive and dated audit records."""
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules", "geofrea.egg-info", "_archive"}
    hits = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        rel = Path(dirpath).relative_to(REPO_ROOT).as_posix()
        for name in filenames:
            if name.endswith((".pyc", ".tif", ".parquet", ".npz", ".png", ".gpkg")):
                continue
            if rel == "docs/_audit" and name[:4].isdigit() and name[4] == "-":
                continue  # dated audit records are historical
            try:
                text = (Path(dirpath) / name).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _LEGACY_NAME in text:
                hits.append(f"{rel}/{name}")
    assert hits == []


@pytest.mark.unit
def test_loaders_validate_the_real_registry_and_experiments():
    technologies, experiments = load_technologies(TECHNOLOGIES), load_experiments(EXPERIMENTS)
    assert set(technologies.technologies) == {"solar", "wind"}
    assert experiments.sampler.method == "latin_hypercube" and experiments.sampler.seed == 42
    assert "opex_fixed_frac" in experiments.uncertain_parameters
    validate_registry(technologies, experiments)
    validate_run_technologies(["solar", "wind"], technologies)


@pytest.mark.unit
def test_run_technologies_must_be_declared_in_the_registry():
    technologies = load_technologies(TECHNOLOGIES)
    with pytest.raises(ConfigConsistencyError, match="geothermal"):
        validate_run_technologies(["solar", "geothermal"], technologies)


@pytest.mark.unit
def test_a_technology_listing_an_undeclared_uncertain_parameter_is_rejected():
    technologies, experiments = load_technologies(TECHNOLOGIES), load_experiments(EXPERIMENTS)
    broken = copy.deepcopy(technologies)
    broken.technologies["solar"].uncertain_parameters.append("not_declared")
    with pytest.raises(ConfigConsistencyError, match="not_declared"):
        validate_registry(broken, experiments)


@pytest.mark.unit
def test_experiments_and_technologies_forbid_unknown_keys(tmp_path):
    import yaml

    raw = yaml.safe_load(EXPERIMENTS.read_text(encoding="utf-8"))
    raw["unexpected_block"] = {}
    bad = tmp_path / "experiments.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError, match="unexpected_block"):
        load_experiments(bad)
    tech = yaml.safe_load(TECHNOLOGIES.read_text(encoding="utf-8"))
    tech["solar"]["capacity_factor"] = 1
    bad_t = tmp_path / "technologies.yaml"
    bad_t.write_text(yaml.safe_dump(tech), encoding="utf-8")
    with pytest.raises(ValidationError, match="capacity_factor"):
        load_technologies(bad_t)
