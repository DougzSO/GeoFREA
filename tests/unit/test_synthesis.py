"""The cross-country synthesis of T-R8 on constructed cases: the labels, the partial classes, a missing target and the profile files (M-F8-03)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from geofrea.core.config_schemas import SynthesisConfig
from geofrea.results_synthesis.output import NotBuilt
from geofrea.results_synthesis.profile_registry import register_profile, registered_profiles
from geofrea.results_synthesis.synthesis import (
    PROFILES_SCHEMA_VERSION,
    label_of,
    profiles_frame,
    read_profiles,
    summary_frame,
    verdict_class,
)

REPO = Path(__file__).resolve().parents[2]
SYNTHESIS = SynthesisConfig.model_validate(
    yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))["synthesis"]
)
LABELS = SYNTHESIS.labels


def _hypothesis(cls, statistics=None):
    return {
        "available": cls != "unavailable",
        "class": cls,
        "statistics": statistics or {},
        "n_variants": 4,
        "n_variants_changing_verdict": 1,
    }


def _profile(country, technology="solar", **classes):
    """A country's profile with a class for each of H1, H2, H3 and H5 (supported unless given) and an H4 profile."""
    hypotheses = {h: _hypothesis(classes.get(h, "supported")) for h in ("H1", "H2", "H3", "H5")}
    h4_profile = classes.get("H4", "climate_dominated")
    hypotheses["H4"] = {
        **_hypothesis(h4_profile),
        "technology_verdict": {
            "available": True,
            "verdict": classes.get("H4_verdict", "supported"),
        },
    }
    return {
        "country": country,
        "records": [
            {
                "country": country,
                "technology": technology,
                "hypotheses": {h: hypotheses[h] for h in ("H1", "H2", "H3", "H4", "H5")},
            }
        ],
    }


def _row(frame, hypothesis, technology="solar"):
    return frame[(frame["hypothesis"] == hypothesis) & (frame["technology"] == technology)].iloc[0]


@pytest.mark.unit
def test_every_testable_case_with_the_same_verdict_is_consistent():
    assert label_of(["supported", "supported", "supported"], SYNTHESIS) == LABELS.consistent
    assert label_of(["not_supported", "not_supported"], SYNTHESIS) == LABELS.consistent


@pytest.mark.unit
def test_testable_cases_that_differ_are_context_dependent():
    assert label_of(["supported", "not_supported", "supported"], SYNTHESIS) == "context-dependent"
    assert (
        label_of(["supported", "partially_supported_resource"], SYNTHESIS)
        == LABELS.context_dependent
    )


@pytest.mark.unit
def test_fewer_than_two_testable_cases_are_not_assessable():
    assert label_of(["supported", "not_testable", "not_testable"], SYNTHESIS) == "not assessable"
    assert label_of(["not_testable", "unavailable"], SYNTHESIS) == LABELS.not_assessable
    assert label_of([], SYNTHESIS) == LABELS.not_assessable


@pytest.mark.unit
def test_a_case_without_a_verdict_is_no_disagreement():
    classes = ["supported", "supported", "target_not_met_at_reference", "exposure_not_available"]
    assert label_of(classes, SYNTHESIS) == LABELS.consistent
    assert label_of([*classes, "not_testable"], SYNTHESIS) == LABELS.consistent


@pytest.mark.unit
def test_the_partial_classes_of_h5_are_kept_apart_and_so_are_those_of_h1():
    assert label_of(
        ["partially_supported_resource", "partially_supported_exposure"], SYNTHESIS
    ) == (LABELS.context_dependent)  # two partial classes are two classes
    assert label_of(["partially_supported_resource"] * 2, SYNTHESIS) == LABELS.consistent
    base = {"verdict": "partially_supported", "status": None}
    core_only = pd.Series({**base, "h1a_holds": True, "h1b_holds": False})
    vulnerable_only = pd.Series({**base, "h1a_holds": False, "h1b_holds": True})
    separate = list(SYNTHESIS.partial_classes_separate)
    assert verdict_class("H1", core_only, separate) == "partially_supported_core_stable"
    assert verdict_class("H1", vulnerable_only, separate) == "partially_supported_vulnerable"
    assert (
        verdict_class("H1", core_only, []) == "partially_supported"
    )  # unless the configuration keeps them together


@pytest.mark.unit
def test_the_class_of_a_case_without_a_verdict_is_the_reason_it_has_none():
    separate = list(SYNTHESIS.partial_classes_separate)
    no_target = pd.Series({"verdict": None, "status": "not_testable"})
    not_met = pd.Series({"verdict": None, "status": "target_not_met_at_reference"})
    no_exposure = pd.Series({"verdict": None, "status": "tested"})
    assert verdict_class("H5", no_target, separate) == "not_testable"
    assert verdict_class("H5", not_met, separate) == "target_not_met_at_reference"
    assert verdict_class("H5", no_exposure, separate) == "exposure_not_available"
    assert verdict_class("H2", pd.Series({"verdict": "not_testable"}), separate) == "not_testable"
    assert verdict_class("H3", pd.Series({"verdict": "supported"}), separate) == "supported"


@pytest.mark.unit
def test_the_summary_counts_the_countries_by_class_and_labels_each_hypothesis():
    profiles = [
        _profile(
            "AAA",
            H1="supported",
            H2="supported",
            H3="not_supported",
            H5="partially_supported_resource",
        ),
        _profile("BBB", H1="supported", H2="not_testable", H3="supported", H5="not_testable"),
        _profile(
            "CCC", H1="supported", H2="supported", H3="supported", H5="partially_supported_exposure"
        ),
    ]
    frame = summary_frame(profiles, ["solar"], SYNTHESIS)
    h1, h2, h3, h5 = (_row(frame, h) for h in ("H1", "H2", "H3", "H5"))
    assert (h1["label"], h1["supported"], h1["n_testable"]) == ("consistent", 3, 3)
    # a country that cannot test H2 is not a disagreement: the two others agree
    assert (h2["label"], h2["supported"], h2["not_testable"], h2["n_testable"]) == (
        "consistent",
        2,
        1,
        2,
    )
    assert (h3["label"], h3["supported"], h3["not_supported"]) == ("context-dependent", 2, 1)
    # H5: one country has no target (not testable), the two others have different partial classes
    assert h5["label"] == "context-dependent"
    assert (h5["partially_supported_resource"], h5["partially_supported_exposure"]) == (1, 1)
    assert h5["not_testable"] == 1 and h5["n_countries"] == 3


@pytest.mark.unit
def test_a_country_without_a_target_does_not_make_a_consistent_h5_context_dependent():
    profiles = [
        _profile("AAA", H5="supported"),
        _profile("BBB", H5="supported"),
        _profile("CCC", H5="not_testable"),
    ]
    h5 = _row(summary_frame(profiles, ["solar"], SYNTHESIS), "H5")
    assert (h5["label"], h5["n_testable"], h5["not_testable"]) == ("consistent", 2, 1)
    only_one = _row(summary_frame(profiles[:1] + profiles[2:], ["solar"], SYNTHESIS), "H5")
    assert only_one["label"] == "not assessable"  # one testable case is too few


@pytest.mark.unit
def test_h4_shows_the_verdict_of_the_technology_and_the_profiles_not_a_label():
    profiles = [
        _profile("AAA", H4="climate_dominated"),
        _profile("BBB", H4="techno_economic_dominated"),
        _profile("CCC", H4="mixed"),
    ]
    h4 = _row(summary_frame(profiles, ["solar"], SYNTHESIS), "H4")
    assert h4["label"] == "comparative (verdict per technology)" and h4["verdict"] == "supported"
    assert (h4["climate_dominated"], h4["techno_economic_dominated"], h4["mixed"]) == (1, 1, 1)
    assert h4["n_testable"] == 3 and h4["n_countries"] == 3


@pytest.mark.unit
def test_the_summary_has_one_row_per_technology_and_hypothesis_and_no_score():
    profiles = [_profile("AAA", "solar"), _profile("AAA", "wind")]
    merged = [{"country": "AAA", "records": profiles[0]["records"] + profiles[1]["records"]}]
    frame = summary_frame(merged, ["solar", "wind"], SYNTHESIS)
    assert len(frame) == 10 and set(frame["technology"]) == {"solar", "wind"}
    assert not any(
        word in " ".join(frame.columns).lower() for word in ("score", "aggregate", "majority")
    )
    long = profiles_frame(merged)
    assert len(long) == 10 and set(long["hypothesis"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert (long["n_variants_changing_verdict"] == 1).all()


@pytest.mark.unit
def test_only_registered_profiles_are_read_by_country_and_an_unknown_schema_version_is_refused(
    tmp_path,
):
    for iso in ("BBB", "AAA"):
        payload = {"schema_version": PROFILES_SCHEMA_VERSION, "country": iso, "records": []}
        path = tmp_path / f"T-R8_hypothesis_profiles_{iso}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        register_profile(tmp_path, iso, path)
        (tmp_path / f"T-R8_hypothesis_profiles_{iso}.provenance.json").write_text(
            "{}", encoding="utf-8"
        )
    stray = tmp_path / "T-R8_hypothesis_profiles_CCC.json"
    stray.write_text(
        json.dumps({"schema_version": PROFILES_SCHEMA_VERSION, "country": "CCC", "records": []}),
        encoding="utf-8",
    )
    assert [p["country"] for p in read_profiles(tmp_path)] == [
        "AAA",
        "BBB",
    ]  # CCC is not registered
    assert set(registered_profiles(tmp_path)) == {"AAA", "BBB"}
    bad = tmp_path / "T-R8_hypothesis_profiles_DDD.json"
    bad.write_text(
        json.dumps({"schema_version": "9.9", "country": "DDD", "records": []}), encoding="utf-8"
    )
    register_profile(tmp_path, "DDD", bad)
    with pytest.raises(NotBuilt, match="schema version"):
        read_profiles(tmp_path)


@pytest.mark.unit
def test_a_profile_changed_or_deleted_after_its_registration_is_refused(tmp_path):
    from geofrea.core.artifact_reader import ThesisInputError

    path = tmp_path / "T-R8_hypothesis_profiles_AAA.json"
    path.write_text(
        json.dumps({"schema_version": PROFILES_SCHEMA_VERSION, "country": "AAA", "records": []}),
        encoding="utf-8",
    )
    digest = register_profile(tmp_path, "AAA", path)
    assert registered_profiles(tmp_path)["AAA"][1] == digest
    path.write_text(
        json.dumps({"schema_version": PROFILES_SCHEMA_VERSION, "country": "AAA", "records": [1]}),
        encoding="utf-8",
    )
    with pytest.raises(ThesisInputError, match="changed since it was registered"):
        read_profiles(tmp_path)
    path.unlink()
    with pytest.raises(ThesisInputError, match="absent"):
        read_profiles(tmp_path)
