"""The support phase cross_country_h4: the verdict of H4 from the h4_country tables of several countries (M-F7-07; D-F7-049)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from geofrea.core.artifact_reader import (
    ArtifactReader,
    ThesisInputError,
    stale_cross_country_inputs,
)
from geofrea.core.scale import active_scale
from geofrea.core.tables import write_table
from geofrea.robustness_analysis.assemble import h4_country_frame
from geofrea.robustness_analysis.cross_country import ROLES, build_h4_verdict, manifest_file
from geofrea.robustness_analysis.h4_axis_dominance import H4Variant, profile_of
from geofrea.robustness_analysis.table_schemas import (
    ROBUSTNESS_TABLE_SCHEMA_VERSION,
    H4CountryRow,
)


def _variant(name: str, d_clim: float, d_tec: float) -> H4Variant:
    rho, profile = profile_of(d_clim, d_tec, 0.40, 0.60)
    return H4Variant(
        variant=name,
        top_k_percent=10.0,
        k=5,
        m=5,
        tolerance_multiple=1.0,
        excluded_gcms=(),
        ssp=None,
        lower=0.40,
        upper=0.60,
        n_cells=100,
        n_ranked=100,
        top_k_truncated=False,
        clim_capacity_mw=50.0,
        tec_capacity_mw=50.0,
        d_clim=d_clim,
        d_tec=d_tec,
        d_sum=d_clim + d_tec,
        rho=rho,
        profile=profile,
        d_joint=0.1,
        distance_to_lower=None if rho is None else abs(rho - 0.40),
        distance_to_upper=None if rho is None else abs(rho - 0.60),
    )


def _country(
    data: Path,
    iso: str,
    tech: str,
    role: str,
    d: tuple[float, float] | None,
    *,
    empty_reason: str | None = None,
) -> Path:
    """Register `h4_country_<tech>__<role>` in the manifest of `iso`: a primary row from `d`, or an empty table that says why."""
    rel = f"outputs/{iso}/robustness_analysis/artifacts/h4_country_{tech}__{role}.parquet"
    path = data / rel
    if d is None:
        frame = h4_country_frame([_variant("primary", 0.0, 0.0)], "2041-2070").iloc[0:0]
        meta = {
            "h4_country_skipped": json.dumps(
                {"output": "H4", "reason": empty_reason, "open_question": "OQ-050"}
            )
        }
    else:
        frame = h4_country_frame(
            [_variant("primary", *d), _variant("top_k_percent_5", 0.0, 0.0)], "2041-2070"
        )
        meta = {}
    write_table(
        frame,
        path,
        schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
        row_model=H4CountryRow,
        extra_metadata=meta,
    )
    manifest = data / "outputs" / iso / "manifest.json"
    current = (
        json.loads(manifest.read_text(encoding="utf-8"))
        if manifest.is_file()
        else {"artifacts": {}}
    )
    current["artifacts"][f"h4_country_{tech}__{role}"] = {
        "path": {"root": "data", "rel": rel},
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(current), encoding="utf-8")
    return path


def _all_roles(data, iso, d, **kwargs):
    for role in ("core", "sensitivity"):
        _country(data, iso, "solar", role, d, **kwargs)


def _verdict(table: pd.DataFrame) -> pd.Series:
    return table[table["kind"] == "technology"].iloc[0]


@pytest.mark.unit
def test_three_countries_with_a_climate_and_a_techno_economic_profile_support_h4(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _all_roles(tmp_path, "AAA", (0.12, 0.38))
    _all_roles(tmp_path, "BBB", (0.42, 0.08))
    _all_roles(tmp_path, "CCC", (0.25, 0.25))
    summary = build_h4_verdict(["AAA", "BBB", "CCC"], ("solar",))
    assert [(v.technology, v.role, v.verdict) for v in summary.verdicts] == [
        ("solar", "core", "supported"),
        ("solar", "sensitivity", "supported"),
    ]
    # the table is a registered artifact of the phase, readable through the reader with its hash checked
    reader = ArtifactReader("cross_country", manifest_file=manifest_file())
    table = reader.table("h4_verdict_solar__core", {ROBUSTNESS_TABLE_SCHEMA_VERSION})
    countries = table[table["kind"] == "country"].set_index("country")
    assert list(countries.index) == ["AAA", "BBB", "CCC"]
    assert list(countries["profile"]) == [
        "techno_economic_dominated",
        "climate_dominated",
        "mixed",
    ]
    assert countries.loc["BBB", "rho"] == pytest.approx(0.84)
    assert countries.loc["AAA", "d_sum"] == pytest.approx(0.50)
    total = _verdict(table)
    assert (total["verdict"], total["n_countries"], total["n_available"]) == ("supported", 3, 3)
    assert (
        total["n_climate_dominated"],
        total["n_techno_economic_dominated"],
        total["n_mixed"],
    ) == (
        1,
        1,
        1,
    )
    meta = pq.read_schema(reader.path("h4_verdict_solar__core")).metadata
    assert json.loads(meta[b"artifacts_read"].decode()).keys() == {
        "AAA:h4_country_solar__core",
        "BBB:h4_country_solar__core",
        "CCC:h4_country_solar__core",
    }


@pytest.mark.unit
def test_a_country_without_inputs_is_unavailable_with_its_reason_and_one_country_is_not_testable(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _all_roles(tmp_path, "AAA", (0.12, 0.38))
    _all_roles(tmp_path, "EEE", None, empty_reason="top_k_percent is null")
    summary = build_h4_verdict(["AAA", "EEE", "NOP"], ("solar",))  # NOP has no manifest at all
    core = next(v for v in summary.verdicts if v.role == "core")
    assert core.verdict == "not_testable" and (core.n_countries, core.n_available) == (3, 1)
    reader = ArtifactReader("cross_country", manifest_file=manifest_file())
    table = reader.table("h4_verdict_solar__core", {ROBUSTNESS_TABLE_SCHEMA_VERSION})
    countries = table[table["kind"] == "country"].set_index("country")
    assert list(countries["available"]) == [True, False, False]
    assert "top_k_percent is null" in countries.loc["EEE", "reason"]
    assert "OQ-050" in countries.loc["EEE", "reason"]
    assert "no manifest" in countries.loc["NOP", "reason"]
    assert countries.loc["EEE", "profile"] is None or pd.isna(countries.loc["EEE", "profile"])
    assert "1 of 3" in _verdict(table)["reason"]


@pytest.mark.unit
def test_two_mixed_countries_do_not_support_h4_and_a_third_with_a_profile_can(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _all_roles(tmp_path, "AAA", (0.25, 0.25))
    _all_roles(tmp_path, "BBB", (0.0, 0.0))
    summary = build_h4_verdict(["AAA", "BBB"], ("solar",))
    assert {v.verdict for v in summary.verdicts} == {"not_supported"}
    assert summary.verdicts[0].counts["no_displacement"] == 1


@pytest.mark.unit
def test_a_changed_country_table_is_refused_and_the_phase_writes_apart_for_another_scale(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    path = _country(tmp_path, "AAA", "solar", "core", (0.1, 0.3))
    _country(tmp_path, "AAA", "solar", "sensitivity", (0.1, 0.3))
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(ThesisInputError, match="changed since it was registered"):
        build_h4_verdict(["AAA"], ("solar",))
    from geofrea.core.scale import SCALES, use_scale

    other = next(s for s in SCALES.values() if not s.is_default)
    with use_scale(other.scale_id):
        assert manifest_file().name == f"manifest__{other.scale_id}.json"
        assert manifest_file().parent == tmp_path / "outputs" / "cross_country"


@pytest.mark.unit
def test_the_manifest_records_the_hash_of_every_h4_country_table_it_read(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _all_roles(tmp_path, "AAA", (0.12, 0.38))
    build_h4_verdict(["AAA", "NOP"], ("solar",))
    recorded = json.loads(manifest_file().read_text(encoding="utf-8"))["inputs"]
    assert set(recorded) == {f"{c}:h4_country_solar__{r}" for c in ("AAA", "NOP") for r in ROLES}
    assert (
        recorded["NOP:h4_country_solar__core"] is None
    )  # a country without a manifest registers none
    manifest = json.loads((tmp_path / "outputs" / "AAA" / "manifest.json").read_text("utf-8"))
    assert (
        recorded["AAA:h4_country_solar__core"]
        == manifest["artifacts"]["h4_country_solar__core"]["sha256"]
    )
    assert stale_cross_country_inputs(manifest_file(), active_scale().scale_id) == []


@pytest.mark.unit
def test_a_rerun_of_the_f7_of_one_country_makes_the_h4_verdict_stale_until_it_runs_again(
    tmp_path, monkeypatch
):
    """B-5: the verdict names the tables it read; a country whose table was replaced, added or lost makes it stale."""
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _all_roles(tmp_path, "AAA", (0.12, 0.38))
    _all_roles(tmp_path, "BBB", (0.42, 0.08))
    build_h4_verdict(["AAA", "BBB", "CCC"], ("solar",))  # CCC has no F7 yet
    scale = active_scale().scale_id
    assert stale_cross_country_inputs(manifest_file(), scale) == []
    _country(tmp_path, "BBB", "solar", "core", (0.10, 0.30))  # the F7 of BBB runs again
    stale = stale_cross_country_inputs(manifest_file(), scale)
    assert len(stale) == 1 and stale[0].startswith("BBB:h4_country_solar__core")
    _country(tmp_path, "CCC", "solar", "sensitivity", (0.25, 0.25))  # CCC registers a table
    assert {s.split(":")[0] for s in stale_cross_country_inputs(manifest_file(), scale)} == {
        "BBB",
        "CCC",
    }
    build_h4_verdict(["AAA", "BBB", "CCC"], ("solar",))
    assert stale_cross_country_inputs(manifest_file(), scale) == []
    manifest = json.loads(manifest_file().read_text(encoding="utf-8"))
    del manifest["inputs"]  # a manifest written before the inputs were recorded
    manifest_file().write_text(json.dumps(manifest), encoding="utf-8")
    assert "records no inputs" in stale_cross_country_inputs(manifest_file(), scale)[0]
