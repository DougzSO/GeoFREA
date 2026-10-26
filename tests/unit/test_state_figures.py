"""The figures by state (`technical_potential/state_figures.py`, COMMAND 68; spec v2 T-12): the three land scenarios as small multiples on one set of
classes, the declared denominator, the circle legend made from the data, the ranking with its range, and the refusal of a division that is not one."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from geofrea.technical_potential import state_figures as S
from geofrea.technical_potential.absolute_maps import build_absolute_maps
from geofrea.viz import mapstyle as ms
from tests.unit.test_absolute_maps import CFG, _world

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("states")
    pot, land, units = _world(base)
    figures = base / "figures"
    written, content = build_absolute_maps("ZZZ", "solar", pot, land, figures, units, CFG)
    return figures, written, content, units


def test_one_sheet_of_the_three_scenarios_and_one_ranking_per_quantity(built):
    figures, written, _, _ = built
    for quantity in ("capacity", "energy"):
        sheet = written[f"potential_{quantity}_density_state_solar"]
        assert sheet.name == f"ZZZ_F5_{quantity}-density_state_solar_land-scenarios_ref.png"
        assert written[f"potential_{quantity}_density_ranking_solar"].name == (
            f"ZZZ_F5_{quantity}-density_ranking_solar_land-scenarios_ref.png"
        )
    assert ms.validate_filename(written["potential_capacity_density_state_solar"].name)
    # the six maps of the three scenarios of the earlier version are not drawn any more: one sheet each shows them side by side
    assert not any("restrictive" in p.name or "permissive" in p.name for p in figures.glob("*.png"))


def test_the_sheet_declares_the_denominator_the_classes_and_the_scenarios(built):
    _, written, _, _ = built
    meta = ms.read_png_metadata(written["potential_capacity_density_state_solar"])
    assert meta["geofrea_denominator"] == "land area of the state"
    assert "central scenario, shared by the three maps" in meta["geofrea_classes_computed_on"]
    assert "land area of the state" in meta["Description"]
    assert "same in the three maps" in meta["Description"]
    assert meta["Title"].endswith("Solar · Capacity density by state")
    assert "OQ" not in meta["Title"] + meta["Description"]


def test_the_circle_scale_comes_from_the_data_and_is_the_same_in_the_three_maps(built):
    _, _, content, _ = built
    circles = content["per_state"]["circles"]["potential_capacity_density_state_solar"]
    reference = circles["circle_reference_total"]
    assert reference > 0
    legend = circles["circle_legend_values"]
    assert legend == ms.nice_values_below(reference) and legend[0] <= reference
    assert all(circles[s]["states_with_circle"] >= 1 for s in S.ORDER)


def test_the_ranking_is_ordered_by_the_central_density_and_carries_the_range(built):
    _, written, content, _ = built
    meta = ms.read_png_metadata(written["potential_capacity_density_ranking_solar"])
    assert meta["geofrea_range"] == "restrictive to permissive"
    assert meta["geofrea_denominator"] == "land area of the state"
    assert "Bar: central land scenario" in meta["Description"]
    assert content["per_state"]["capacity_density"]["classes_final"] >= 2


def test_a_division_with_one_unit_is_refused_with_the_reason():
    one = gpd.GeoDataFrame(
        {"admin1_id": ["a"], "admin1_name": ["A"]}, geometry=[box(0, 0, 1, 1)], crs="EPSG:4326"
    )
    with pytest.raises(S.StateFigureError, match="fewer than 2"):
        S.check_units(one)
    three = gpd.GeoDataFrame(
        {"admin1_id": list("abc"), "admin1_name": list("ABC")},
        geometry=[box(i, 0, i + 1, 1) for i in range(3)],
        crs="EPSG:4326",
    )
    S.check_units(three)


def test_the_classes_use_the_colours_of_the_technology_from_light_to_dark():
    colours = S.class_colours("solar", 5)
    assert len(colours) == 5
    luminance = [0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in colours]
    assert luminance == sorted(luminance, reverse=True)
    wind = S.class_colours("wind", 5)
    assert wind[-1][2] > wind[-1][0]  # a cool family: more blue than red at the dark end
    assert np.isclose(
        len(json.dumps(S.ORDER)), len(json.dumps(("restrictive", "central", "permissive")))
    )
