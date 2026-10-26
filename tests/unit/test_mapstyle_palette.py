"""The semantics of colour and of scale of the common map style (COMMAND 66): one colormap and one scale per variable, the colours of a
figure never have two meanings (also under colour-blind simulation), the scales are fixed, percentile or shared, a clip is declared in
the subtitle and the colour bar extends exactly where the data go beyond the limits. Synthetic data only."""

from __future__ import annotations

import math

import numpy as np
import pytest
from matplotlib.colors import Normalize

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------------------------------------------------------------ palette


def test_each_technology_has_its_own_warm_or_cool_family_truncated_from_the_white():
    solar = ms.colormap_for("capacity_factor", "solar")
    wind = ms.colormap_for("capacity_factor", "wind")
    assert solar.name.startswith("YlOrBr") and wind.name.startswith("GnBu")
    for cmap in (solar, wind):
        low = cmap(0.0)[:3]
        assert min(low) < 0.97, "the lowest colour is not white, the colour of the sea"
    assert (
        ms.colormap_for("density", "solar").name == solar.name
    )  # the same family for every variable of the technology
    assert ms.colormap_for("eligible_share", "wind").name == wind.name


def test_diagnostic_and_climate_colormaps():
    assert ms.colormap_for("excluded_share").name == "Reds"
    assert ms.colormap_for("delta").name == "RdBu"
    assert ms.colormap_for("delta_alt").name == "BrBG"
    assert ms.colormap_for("temperature").name == "YlOrRd"
    for name in ("viridis", "magma"):
        for kind in ms.TECH_KINDS:
            for tech in ("solar", "wind"):
                assert not ms.colormap_for(kind, tech).name.startswith(name)


def test_a_kind_that_takes_the_technology_needs_it():
    with pytest.raises(ValueError):
        ms.colormap_for("potential")
    with pytest.raises(ValueError):
        ms.colormap_for("potential", "fusion")
    with pytest.raises(ValueError):
        ms.colormap_for("nonsense")


FIGURES = {  # the colormaps that appear together in one figure
    "technologies side by side": [("capacity_factor", "solar"), ("capacity_factor", "wind")],
    "climate forcing": [("delta", None), ("delta_alt", None), ("temperature", None)],
    "diagnostic exclusion": [("excluded_share", None)],
}


def test_the_colormaps_of_one_figure_are_different_and_stay_apart_for_every_vision():
    for figure, members in FIGURES.items():
        cmaps = [ms.colormap_for(kind, tech) for kind, tech in members]
        assert len({c.name for c in cmaps}) == len(cmaps), figure
        for i, a in enumerate(cmaps):
            for b in cmaps[i + 1 :]:
                for vision in ms.VISIONS:
                    gaps = [ms.delta_e(a(v), b(v), vision) for v in np.linspace(0.3, 0.9, 4)]
                    assert max(gaps) > 12.0, f"{a.name} and {b.name} look alike for {vision}"


def test_no_technology_colormap_is_used_for_exclusion_or_for_a_change():
    tech = {ms.colormap_for(k, t).name for k in ms.TECH_KINDS for t in ("solar", "wind")}
    other = {
        ms.colormap_for(k).name for k in ("excluded_share", "delta", "delta_alt", "temperature")
    }
    assert not tech & other


def test_class_colours_have_no_green_and_stay_apart_for_every_vision():
    colours = ms.class_colours(6)
    assert len(set(colours)) == 6
    for c in (*colours, ms.CLASS_NONE_COLOUR):
        r, g, b = (float(x) for x in ms.to_rgb(c))
        assert not (g > r and g > b), f"{c} is green"
    meanings = {c: f"E{i + 1}" for i, c in enumerate(colours)}
    meanings[ms.CLASS_NONE_COLOUR] = "none"
    meanings[ms.NO_DATA_COLOUR] = "no potential"
    meanings[ms.NEIGHBOUR_COLOUR] = "neighbouring countries"
    meanings[ms.SEA_COLOUR] = "sea"
    assert ms.colour_conflicts(meanings) == []
    with pytest.raises(ValueError):
        ms.class_colours(7)


def test_the_grey_of_no_potential_is_not_the_grey_of_the_neighbours():
    assert ms.delta_e(ms.NO_DATA_COLOUR, ms.NEIGHBOUR_COLOUR) > 12.0
    assert ms.delta_e(ms.NO_DATA_COLOUR, ms.SEA_COLOUR) > 2 * ms.MIN_DELTA_E


def test_conflict_finder_catches_one_colour_with_two_meanings_and_look_alikes():
    assert ms.colour_conflicts({"#2ca02c": "eligible", "#2CA02C": "excluded E1"})  # the old figure
    reds = {"#d62728": "excluded", "#2ca02c": "eligible"}
    assert ms.colour_conflicts(reds), "red and green look alike for deuteranopia and protanopia"
    assert ms.colour_conflicts({"#E69F00": "a", "#56B4E9": "b"}) == []
    same_map = ms.colour_conflicts({}, {"YlOrBr": "solar"})
    assert same_map == []


def test_a_figure_refuses_a_colour_with_two_meanings():
    country = synthetic_country("wide")
    canvas = ms.raster_map(
        country.grid,
        country.grid_extent,
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Capacity",
        label="MW per cell",
        tech="solar",
        neighbours=country.neighbours,
    )
    assert canvas.colour_problems() == []
    with pytest.raises(ValueError):
        canvas.use_colour(ms.NEIGHBOUR_COLOUR, "no potential")
    with pytest.raises(ValueError):
        canvas.use_cmap(ms.colormap_for("capacity_factor", "solar"), "something else")


@pytest.mark.parametrize("name", ["tall", "wide", "small"])
def test_a_classed_figure_with_the_class_palette_has_no_conflict(name):
    country = synthetic_country(name)
    spec = ms.qualitative_legend(
        "Dominant exclusion",
        ["E1 protected", "E2 water", "E3 riparian", "E4 slope", "E5 land cover"],
        "none",
    )
    side, below = ms.legend_space(spec)
    canvas = ms.new_map(
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Dominant exclusion",
        neighbours=country.neighbours,
        legend_side_mm=side,
        legend_below_mm=below,
    )
    ms.draw_classed_legend(canvas, spec)
    assert canvas.colour_problems() == []
    assert len(canvas.colours) == 5 + 1 + 2  # five classes, none, neighbours, sea


# ------------------------------------------------------------------------------------------------------------------------ scales


def test_fixed_scale_keeps_the_physical_limits_and_extends_where_the_data_go_beyond():
    cf = np.array([0.05, 0.12, 0.2, 0.31])
    info = ms.resolve_scale(cf, ms.default_scale("capacity_factor", "solar"))
    assert (info.vmin, info.vmax) == (0.10, 0.25) and info.mode == "fixed"
    assert info.scope == "shared_across_countries" and info.extend == "both"
    inside = ms.resolve_scale(np.array([0.12, 0.2]), ms.default_scale("capacity_factor", "solar"))
    assert inside.extend == "neither"
    wind = ms.resolve_scale(np.array([0.0, 0.7]), ms.default_scale("capacity_factor", "wind"))
    assert (wind.vmin, wind.vmax, wind.extend) == (0.0, 0.60, "max")


def test_capacity_factor_scale_is_the_same_in_every_country():
    a = ms.resolve_scale(
        np.random.default_rng(1).uniform(0.1, 0.4, 500), ms.default_scale("capacity_factor", "wind")
    )
    b = ms.resolve_scale(
        np.random.default_rng(2).uniform(0.02, 0.3, 500),
        ms.default_scale("capacity_factor", "wind"),
    )
    assert (a.vmin, a.vmax) == (b.vmin, b.vmax)


def test_percentile_scale_is_the_robust_norm_of_each_country():
    values = np.linspace(0.0, 100.0, 1001)
    info = ms.resolve_scale(values, ms.default_scale("density", "solar"))
    assert info.mode == "percentile" and info.scope == "per_country"
    assert (info.vmin, info.vmax) == pytest.approx((2.0, 98.0)) and info.extend == "both"


def test_shared_scale_gives_the_same_limits_to_every_map_that_is_compared():
    rng = np.random.default_rng(3)
    maps = [rng.uniform(0, 10, 400), rng.uniform(0, 4, 400), rng.uniform(0, 7, 400)]
    spec = ms.default_scale("density", "solar")
    limits = ms.shared_limits(maps, spec)
    infos = [ms.resolve_scale(m, replace_scope(spec), limits) for m in maps]
    assert {(i.vmin, i.vmax) for i in infos} == {limits}
    assert {i.mode for i in infos} == {"shared"}
    assert infos[1].extend in {"min", "neither"}  # the smallest map stays inside the big limits
    with pytest.raises(ValueError):
        ms.resolve_scale(maps[0], ms.ScaleSpec("shared"))


def replace_scope(spec: ms.ScaleSpec) -> ms.ScaleSpec:
    return ms.ScaleSpec(spec.mode, spec.limits, spec.percentiles, "shared_across_countries")


def test_shared_limits_of_a_diverging_variable_are_symmetric_about_the_centre():
    spec = ms.default_scale("delta")
    limits = ms.shared_limits([np.array([-1.0, 3.0, 0.5]), np.array([2.0, -4.0, 1.0])], spec)
    assert limits[0] == pytest.approx(-limits[1])


def test_scale_spec_validates_its_mode_scope_and_limits():
    with pytest.raises(ValueError):
        ms.ScaleSpec("median")
    with pytest.raises(ValueError):
        ms.ScaleSpec("percentile", scope="everywhere")
    with pytest.raises(ValueError):
        ms.ScaleSpec("fixed")
    with pytest.raises(ValueError):
        ms.ScaleSpec("fixed", (1.0, 1.0))


def test_extend_follows_the_data_not_the_percentiles():
    info = ms.resolve_scale(np.array([1.0, 2.0, 3.0]), ms.ScaleSpec("fixed", (0.0, 10.0)))
    assert info.extend == "neither"
    assert (
        ms.resolve_scale(np.array([-1.0, 2.0]), ms.ScaleSpec("fixed", (0.0, 10.0))).extend == "min"
    )
    assert (
        ms.resolve_scale(np.array([1.0, 12.0]), ms.ScaleSpec("fixed", (0.0, 10.0))).extend == "max"
    )
    assert isinstance(info.norm, Normalize)


def test_a_clip_is_declared_in_the_subtitle_with_its_limit_mode_and_scope():
    info = ms.resolve_scale(np.array([1.0, 2.0, 30.0]), ms.ScaleSpec("fixed", (0.0, 10.0)))
    note = ms.clip_note(info, "MW/km²")
    assert (
        note == "Scale: fixed"
    )  # the limit, the scope and the norm are in the metadata of the PNG (COMMAND 67b)
    cf = ms.resolve_scale(np.array([0.05, 0.3]), ms.default_scale("capacity_factor", "solar"))
    assert ms.clip_note(cf) == "Scale: fixed" and cf.scope == "shared_across_countries"
    none = ms.resolve_scale(np.array([1.0, 2.0]), ms.ScaleSpec("fixed", (0.0, 10.0)))
    assert ms.clip_note(none, "x") == ""
    assert (
        ms.format_subtitle("Central", None, "Reference climate", "")
        == "Central · Reference climate"
    )


def test_a_raster_map_declares_its_clip_and_its_scale_in_subtitle_and_metadata():
    country = synthetic_country("wide")
    canvas = ms.raster_map(
        country.grid,
        country.grid_extent,
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Capacity factor",
        label="Capacity factor",
        kind="capacity_factor",
        tech="solar",
        scenario="Central",
        climate="Reference climate",
        neighbours=country.neighbours,
    )
    text = canvas.texts["subtitle"].get_text().replace("\n", " ")
    assert text.startswith("Central · Reference climate")
    assert text.endswith("Scale: fixed") and "0.1" not in text  # the limits are in the metadata
    assert (
        canvas.meta["scale_mode"] == "fixed"
        and canvas.meta["scale_scope"] == "shared_across_countries"
    )
    assert canvas.meta["scale_limits"] == "0.1,0.25" and canvas.meta["scale_extend"] in {
        "min",
        "max",
        "both",
    }


def test_the_scale_of_a_change_is_centred_and_drawn_with_the_diverging_map():
    country = synthetic_country("tall")
    grid = (country.grid - np.nanmedian(country.grid)) * 3.0
    canvas = ms.raster_map(
        country.grid * 0 + grid,
        country.grid_extent,
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Change of resource",
        label="Change (%)",
        kind="delta",
        tech="solar",
        scenario="SSP3-7.0",
        climate="2071-2100",
    )
    assert float(canvas.meta["scale_limits"].split(",")[0]) == pytest.approx(
        -float(canvas.meta["scale_limits"].split(",")[1])
    )
    assert math.isfinite(float(canvas.meta["scale_limits"].split(",")[1]))
