"""File names, PNG metadata and the index of a folder of figures (COMMAND 66): `{ISO3}_{phase}_{variable}_{technology}_{scenario}_{climate}.png`
with no empty field and no `na`, the text chunks of the PNG, no sidecar file per figure, one `figures_index.json` per folder."""

from __future__ import annotations

import json

import pytest

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

pytestmark = pytest.mark.unit


def _figure(**kwargs):
    country = synthetic_country("small")
    args = {
        "iso": "BRA",
        "technology": "Wind",
        "variable": "Capacity factor",
        "label": "Capacity factor",
        "kind": "capacity_factor",
        "tech": "wind",
        "scenario": "Central",
        "climate": "Reference climate",
        "width_mm": 90.0,
    }
    args.update(kwargs)
    return ms.raster_map(country.grid, country.grid_extent, country.geometry, **args)


# ------------------------------------------------------------------------------------------------------------------ names


def test_the_examples_of_the_spec_are_what_the_function_writes():
    assert (
        ms.figure_filename("BRA", "F3", ("excluded-share", "E5-land-cover"), technology="wind")
        == "BRA_F3_excluded-share_E5-land-cover_wind.png"
    )
    assert (
        ms.figure_filename("BRA", "F4", "forcing", climate=("ACCESS-CM2", "SSP3-7.0", "2041-2070"))
        == "BRA_F4_forcing_ACCESS-CM2_SSP3-7.0_2041-2070.png"
    )
    assert (
        ms.figure_filename("PRT", "F5", "capacity-factor", "wind", "central", "ref")
        == "PRT_F5_capacity-factor_wind_central_ref.png"
    )


def test_fields_that_do_not_apply_are_left_out_and_never_written_as_na():
    name = ms.figure_filename("IND", "F5", "potential density", technology="solar")
    assert name == "IND_F5_potential-density_solar.png"
    assert "na" not in name.split("_") and "__" not in name
    assert ms.figure_filename("IND", "F5", "eligible share", None, "", None).count("_") == 2
    for bad in ("na", "NA", "none", "n/a"):
        with pytest.raises(ValueError):
            ms.figure_filename("IND", "F5", "capacity-factor", bad)


def test_three_countries_never_write_the_same_name():
    names = {
        ms.figure_filename(iso, "F5", "capacity-factor", "wind", "central", "ref")
        for iso in ("BRA", "PRT", "IND")
    }
    assert len(names) == 3 and all(n[:3] in {"BRA", "PRT", "IND"} for n in names)
    with pytest.raises(ValueError):
        ms.figure_filename("br", "F5", "capacity-factor")
    with pytest.raises(ValueError):
        ms.figure_filename("BRA", "F5", "")


def test_a_name_has_a_readable_slug_not_a_hash():
    assert ms.slug("Land cover / E5") == "Land-cover-E5"
    assert ms.slug("ACCESS-CM2") == "ACCESS-CM2" and ms.slug("SSP3-7.0") == "SSP3-7.0"
    assert ms.slug("potential_energy density") == "potential-energy-density"
    with pytest.raises(ValueError):
        ms.validate_filename("BRA_F5_capacity-factor_34cc24a1.png")


@pytest.mark.parametrize(
    "name",
    [
        "capacity_factor_wind__ref__na__na.png",  # the old pattern: no ISO3, na
        "BRA_F5_capacity-factor__na.png",
        "BRA_F5_capacity-factor_na_na.png",
        "BRA_F5.png",
        "bra_F5_capacity-factor.png",
        "BRA_F5_capacity-factor.pdf",
    ],
)
def test_names_off_the_standard_are_refused(name):
    with pytest.raises(ValueError):
        ms.validate_filename(name)


# ------------------------------------------------------------------------------------------------------------------ metadata


def test_the_png_carries_commit_config_date_grid_source_and_scale(tmp_path):
    folder = tmp_path / "figures"  # the data directory is tmp_path: drawing a map may fill `interim/` (the territory cache), the folder of figures must not
    folder.mkdir()
    canvas = _figure()
    path = ms.save_png(
        canvas,
        folder / "BRA_F5_capacity-factor_wind_central_ref.png",
        {"grid": "0.05 degree analysis grid", "data_source": "F5 potential_wind central"},
    )
    meta = ms.read_png_metadata(path)
    assert meta["Title"] == "Brazil · Wind · Capacity factor"
    assert meta["geofrea_commit"] and meta["geofrea_config_hash"] and meta["geofrea_date"]
    assert len(meta["geofrea_date"]) == 10 and meta["geofrea_preset"] == "thesis"
    assert meta["geofrea_grid"] == "0.05 degree analysis grid"
    assert meta["geofrea_data_source"] == "F5 potential_wind central"
    assert meta["geofrea_scale_mode"] == "fixed"
    assert meta["geofrea_scale_scope"] == "shared_across_countries"
    assert meta["geofrea_scale_limits"] == "0,0.6"
    assert "Software" not in meta
    assert [p.name for p in folder.iterdir()] == [path.name], "no sidecar file per figure"


def test_the_commit_and_the_config_hash_are_read_from_the_repository():
    assert ms.repo_commit() == "unknown" or len(ms.repo_commit()) >= 7
    assert ms.config_hash() == "unknown" or len(ms.config_hash()) == 12


# ------------------------------------------------------------------------------------------------------------------ index


def test_the_index_lists_every_figure_of_the_folder_and_flags_the_old_names(tmp_path):
    ms.save_png(
        _figure(), tmp_path / "BRA_F5_capacity-factor_wind_central_ref.png", {"grid": "0.05 degree"}
    )
    ms.save_png(_figure(variable="Density"), tmp_path / "BRA_F5_density_wind_central_ref.png")
    ms.save_png(_figure(), tmp_path / "capacity_factor_wind__ref__na__na.png")
    index = json.loads(ms.write_figures_index(tmp_path).read_text(encoding="utf-8"))
    assert [f["file"] for f in index["figures"]] == [
        "BRA_F5_capacity-factor_wind_central_ref.png",
        "BRA_F5_density_wind_central_ref.png",
        "capacity_factor_wind__ref__na__na.png",
    ]
    assert index["nonconforming"] == ["capacity_factor_wind__ref__na__na.png"]
    first = index["figures"][0]
    assert first["title"] == "Brazil · Wind · Capacity factor"
    assert first["metadata"]["geofrea_grid"] == "0.05 degree" and len(first["sha256"]) == 64
    assert abs(first["size_px"][0] - 90 / 25.4 * 300) <= 1
    assert (tmp_path / "figures_index.json").exists()
    assert len(list(tmp_path.glob("*.json"))) == 1, "one index per folder"
