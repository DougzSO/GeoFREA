"""T-R3 (the GCM agreement), T-M1 (the DAG of the orchestrator) and the settings of the thesis figures, on constructed cases (D-F8-018, D-F8-019)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from geofrea.core.config_schemas import ExperimentsFile, GcmAgreementConfig
from geofrea.core.orchestrator import (
    DependencyCycleError,
    MissingProducerError,
    PhaseSpec,
    phase_graph,
)
from geofrea.results_synthesis.climate_change import (
    agreement_mask,
    changes_by_ssp,
    median_change,
    stipple_points,
)
from geofrea.results_synthesis.dag import edges, layers, positions
from geofrea.results_synthesis.output import NotBuilt

REPO = Path(__file__).resolve().parents[2]
TWO_THIRDS = Fraction(2, 3)


def _experiments() -> ExperimentsFile:
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    return ExperimentsFile.model_validate(raw)


@pytest.mark.unit
def test_two_thirds_of_the_gcms_on_the_same_sign_mark_a_cell_and_a_zero_or_a_missing_value_agrees_with_no_sign():
    nan = np.nan
    # members by cells: [+,+,-] marked; [+,-,0] not; [+,+,+] marked; [-,-,nan] marked (2 of 3); [+,nan,nan] not; [0,0,0] not
    changes = np.array(
        [
            [1.0, 1.0, 1.0, -1.0, 1.0, 0.0],
            [2.0, -1.0, 1.0, -2.0, nan, 0.0],
            [-3.0, 0.0, 1.0, nan, nan, 0.0],
        ]
    )
    assert agreement_mask(changes, TWO_THIRDS).tolist() == [True, False, True, True, False, False]
    # exactly two of three is enough with a fraction, which a rounded 0.6667 would have refused
    assert agreement_mask(changes[:, :1], TWO_THIRDS).tolist() == [True]
    assert agreement_mask(changes, Fraction(1, 1)).tolist() == [
        False,
        False,
        True,
        False,
        False,
        False,
    ]


@pytest.mark.unit
def test_the_map_shows_the_median_over_the_gcms_and_nan_where_none_has_a_value():
    changes = np.array([[1.0, np.nan], [3.0, np.nan], [2.0, np.nan]])
    out = median_change(changes)
    assert out[0] == 2.0 and np.isnan(out[1])


@pytest.mark.unit
def test_the_changes_are_the_member_capacity_factor_minus_the_reference_by_ssp_of_the_core_window():
    members = pd.DataFrame(
        {
            "member": ["m0", "a", "b", "c", "late"],
            "ssp": [None, "SSP1-2.6", "SSP1-2.6", "SSP5-8.5", "SSP5-8.5"],
            "window": ["reference", "2041-2070", "2041-2070", "2041-2070", "2071-2100"],
        }
    )
    potential = pd.DataFrame(
        {
            "cell_id": [1, 1, 1, 1, 1, 2, 2, 2],
            "member": ["m0", "a", "b", "c", "late", "m0", "a", "b"],
            "CF": [0.30, 0.33, 0.27, 0.40, 0.99, 0.20, 0.25, 0.20],
        }
    )
    cell_ids, by_ssp = changes_by_ssp(potential, members, "2041-2070")
    assert cell_ids.tolist() == [1, 2] and sorted(by_ssp) == ["SSP1-2.6", "SSP5-8.5"]
    names, changes = by_ssp["SSP1-2.6"]
    assert names == ["a", "b"]
    assert changes == pytest.approx(np.array([[0.03, 0.05], [-0.03, 0.0]]))
    names_c, _ = by_ssp["SSP5-8.5"]
    assert names_c == ["c"]  # the 2071-2100 member is not in the core window
    with pytest.raises(NotBuilt, match="no member of the core window"):
        changes_by_ssp(potential, members, "1999-2000")
    with pytest.raises(NotBuilt, match="no reference member"):
        changes_by_ssp(potential, members[members["member"] != "m0"], "2041-2070")


@pytest.mark.unit
def test_the_dots_lie_on_marked_cells_and_are_thinned_on_a_large_map():
    marked = np.zeros((200, 100), dtype=bool)
    marked[::2, ::2] = True
    x, y = stipple_points(marked, (10.0, 20.0, 30.0, 50.0))
    assert 0 < len(x) < 400 and len(x) == len(y)
    assert (x > 10).all() and (x < 20).all() and (y > 30).all() and (y < 50).all()
    none_marked = stipple_points(np.zeros((3, 3), dtype=bool), (0, 1, 0, 1))
    assert len(none_marked[0]) == 0


@pytest.mark.unit
def test_the_agreement_setting_is_a_fraction_above_one_half_and_the_shipped_value_is_two_thirds():
    rule = _experiments().thesis_figures.gcm_agreement
    assert rule.share == Fraction(2, 3) and rule.rule == "sign_of_change"
    base = rule.model_dump()
    for bad in ("0.6667", "1/2", "3/2", "2/0", ""):
        with pytest.raises(ValidationError):
            GcmAgreementConfig.model_validate({**base, "min_share": bad})


def _spec(name, requires=(), produces=()):
    return PhaseSpec(
        name=name,
        output_model=dict,
        run=lambda context: {},
        requires=frozenset(requires),
        produces=frozenset(produces),
    )


@pytest.mark.unit
def test_the_graph_comes_from_the_requires_and_produces_of_the_specs_and_is_validated_like_a_run():
    specs = [
        _spec("a", produces={"x"}),
        _spec("b", requires={"x"}, produces={"y", "z"}),
        _spec("c", requires={"x", "y"}),
        _spec("d", requires={"z", "y"}),
    ]
    graph = phase_graph(specs)
    assert graph == {"a": (), "b": ("a",), "c": ("a", "b"), "d": ("b",)}
    assert edges(graph) == [("a", "b"), ("a", "c"), ("b", "c"), ("b", "d")]
    assert layers(graph) == {"a": 0, "b": 1, "c": 2, "d": 2}
    where = positions(graph)
    assert where["c"][0] == where["d"][0] == 2.0 and where["c"][1] != where["d"][1]
    with pytest.raises(MissingProducerError):
        phase_graph([_spec("a", requires={"nobody"})])
    with pytest.raises(DependencyCycleError):
        phase_graph(
            [_spec("a", requires={"y"}, produces={"x"}), _spec("b", requires={"x"}, produces={"y"})]
        )
    with pytest.raises(ValueError, match="cycle"):
        layers({"a": ("b",), "b": ("a",)})
    with pytest.raises(ValueError, match="not phases"):
        layers({"a": ("ghost",)})


@pytest.mark.unit
def test_the_axes_of_the_shipped_configuration_name_phases_of_the_real_graph():
    import main
    from geofrea.core.config_loader import load_audit_config
    from geofrea.core.schemas import ResolutionsConfig

    graph = phase_graph(
        main._build_phase_specs(
            ResolutionsConfig(suitability=0.01),
            100.0,
            load_audit_config(main.AUDIT_YAML),
            technologies=("solar", "wind"),
        )
    )
    axes = _experiments().thesis_figures.dag_axes
    assert set(axes.member) | set(axes.sample) <= set(graph)
    assert graph.get("results_synthesis")
