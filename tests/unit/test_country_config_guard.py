"""Schema of countries.yaml and country_names.yaml and the antimeridian refusal (COMMAND 126, defect 2 of the generality audit)."""

from __future__ import annotations

import ast
import copy
import os
from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from shapely.geometry import Polygon, box

from geofrea.core.country_guard import (
    AntimeridianCountryError,
    CountryConfigError,
    polygon_crosses_antimeridian,
    refuse_antimeridian_countries,
    validate_countries_config,
    validate_country_names,
)

REPO = Path(__file__).resolve().parents[2]
COUNTRIES = yaml.safe_load((REPO / "config" / "countries.yaml").read_text(encoding="utf-8"))
NAMES = yaml.safe_load((REPO / "config" / "country_names.yaml").read_text(encoding="utf-8"))


def _gdf(*geoms):
    return gpd.GeoDataFrame({"id": range(len(geoms))}, geometry=list(geoms), crs="EPSG:4326")


# --- the schema -------------------------------------------------------------------------------------------------------------------


def test_the_three_thesis_countries_and_the_others_in_the_file_pass():
    entries = validate_countries_config(COUNTRIES)
    assert {"BRA", "PRT", "IND", "ZZZ"} <= set(entries)
    assert entries["PRT"].mainland_only is True
    assert entries["IND"].gwa_neighbours == ["PAK", "CHN"]


def test_country_names_of_the_repository_pass():
    assert "BRA" in validate_country_names(NAMES).en


def test_a_misspelled_key_fails_and_is_named():
    raw = copy.deepcopy(COUNTRIES)
    raw["PRT"]["mainland_onlly"] = True
    with pytest.raises(CountryConfigError, match=r"PRT\.mainland_onlly"):
        validate_countries_config(raw)


@pytest.mark.parametrize("key", ["hydrosheds_region", "grip4_region_dir", "grip4_region_file"])
def test_a_required_key_that_is_absent_fails_and_is_named(key):
    raw = copy.deepcopy(COUNTRIES)
    del raw["BRA"][key]
    with pytest.raises(CountryConfigError, match=rf"BRA\.{key}"):
        validate_countries_config(raw)


def test_a_null_value_is_still_allowed_for_a_required_key():
    raw = copy.deepcopy(COUNTRIES)
    raw["CHN"]["hydrosheds_region"] = None
    validate_countries_config(raw)


def test_mainland_only_must_be_a_real_boolean():
    raw = copy.deepcopy(COUNTRIES)
    raw["PRT"]["mainland_only"] = "yes"
    with pytest.raises(CountryConfigError, match=r"PRT\.mainland_only"):
        validate_countries_config(raw)


def test_a_country_code_that_is_not_three_capitals_fails():
    raw = copy.deepcopy(COUNTRIES)
    raw["Prt"] = raw.pop("PRT")
    with pytest.raises(CountryConfigError, match="three capital letters"):
        validate_countries_config(raw)


def test_an_empty_file_fails():
    with pytest.raises(CountryConfigError):
        validate_countries_config(None)


def test_country_names_with_an_unknown_language_or_a_bad_code_fail():
    bad = copy.deepcopy(NAMES)
    bad["fr"] = {"BRA": "Brésil"}
    with pytest.raises(CountryConfigError, match="country_names.yaml"):
        validate_country_names(bad)
    bad = copy.deepcopy(NAMES)
    bad["en"]["bra"] = "Brazil"
    with pytest.raises(CountryConfigError):
        validate_country_names(bad)
    bad = copy.deepcopy(NAMES)
    del bad["pt"]
    with pytest.raises(CountryConfigError):
        validate_country_names(bad)


# --- the antimeridian ---------------------------------------------------------------------------------------------------------------


def test_a_polygon_cut_at_the_seam_is_a_crossing():
    fiji_like = _gdf(box(177.0, -19.0, 180.0, -16.0), box(-180.0, -19.0, -178.0, -16.0))
    assert "both +180 and -180" in polygon_crosses_antimeridian(fiji_like)


def test_a_polygon_in_0_360_or_drawn_the_long_way_is_a_crossing():
    assert "outside -180..180" in polygon_crosses_antimeridian(_gdf(box(170.0, 60.0, 190.0, 70.0)))
    long_way = _gdf(Polygon([(-170.0, 0.0), (170.0, 0.0), (170.0, 10.0), (-170.0, 10.0)]))
    assert "wider than 180" in polygon_crosses_antimeridian(long_way)


@pytest.mark.parametrize(
    "geom",
    [
        box(-9.5, 36.9, -6.2, 42.2),  # PRT-like
        box(68.0, 8.0, 97.5, 37.0),  # IND-like
        box(-74.0, -33.8, -34.8, 5.3),  # BRA-like
        box(-3.0, 50.0, 2.0, 53.0),  # crosses Greenwich: not the antimeridian
        box(170.0, -45.0, 180.0, -35.0),  # touches +180 only
    ],
)
def test_ordinary_polygons_are_not_a_crossing(geom):
    assert polygon_crosses_antimeridian(_gdf(geom)) is None


def _place(raw: Path, iso: str, *geoms):
    folder = raw / iso / f"gadm41_{iso}_shp"
    folder.mkdir(parents=True)
    _gdf(*geoms).to_file(folder / f"gadm41_{iso}_0.shp")


def _entries(**per_country):
    raw = {
        iso: {"hydrosheds_region": None, "grip4_region_dir": None, "grip4_region_file": None, "gadm_dir": iso, **extra}
        for iso, extra in per_country.items()
    }
    return validate_countries_config(raw)


def test_a_country_that_crosses_180_is_refused_by_name(tmp_path):
    _place(tmp_path, "FJI", box(177.0, -19.0, 180.0, -16.0), box(-180.0, -19.0, -178.0, -16.0))
    with pytest.raises(AntimeridianCountryError, match="FJI"):
        refuse_antimeridian_countries(["FJI"], _entries(FJI={}), tmp_path)


def test_a_country_that_does_not_cross_passes_and_one_without_a_polygon_is_reported(tmp_path):
    _place(tmp_path, "PRT", box(-9.5, 36.9, -6.2, 42.2))
    unchecked = refuse_antimeridian_countries(["PRT", "XXX"], _entries(PRT={}, XXX={}), tmp_path)
    assert unchecked == ["XXX"]


def test_with_mainland_only_the_far_islands_do_not_count(tmp_path):
    # the mainland is far from the seam; two islands on either side of it lie farther than the contiguity gap from the mainland
    _place(tmp_path, "AAA", box(-100.0, 30.0, -90.0, 40.0), box(179.0, 0.0, 180.0, 1.0), box(-180.0, 0.0, -179.0, 1.0))
    assert refuse_antimeridian_countries(["AAA"], _entries(AAA={"mainland_only": True}), tmp_path) == []
    with pytest.raises(AntimeridianCountryError):
        refuse_antimeridian_countries(["AAA"], _entries(AAA={"mainland_only": False}), tmp_path)


def test_the_real_polygons_of_the_three_countries_pass_when_they_are_placed():
    root = os.environ.get("GEOFREA_DATA_DIR")
    gadm = Path(root) / "raw" / "gadm" if root else None
    if gadm is None or not all((gadm / i / f"gadm41_{i}_shp" / f"gadm41_{i}_0.shp").exists() for i in ("PRT", "IND", "BRA")):
        pytest.skip("the GADM level-0 polygons of the three countries are not placed in GEOFREA_DATA_DIR")
    assert refuse_antimeridian_countries(["PRT", "IND", "BRA"], validate_countries_config(COUNTRIES), gadm) == []


# --- main.py ------------------------------------------------------------------------------------------------------------------------


def test_main_stops_before_any_phase_on_a_misspelled_key(tmp_path, monkeypatch, caplog):
    import main  # repo-root script

    raw = copy.deepcopy(COUNTRIES)
    raw["PRT"]["mainland_onlly"] = True
    bad = tmp_path / "countries.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setattr(main, "COUNTRIES_YAML", bad)
    called = []
    monkeypatch.setattr(main, "run_acquisition_phase", lambda *a, **k: called.append(1))
    with caplog.at_level("ERROR"):
        assert main.main(["PRT"]) == 1
    assert "mainland_onlly" in caplog.text and not called


def test_main_stops_before_any_phase_on_an_antimeridian_country(tmp_path, monkeypatch, caplog):
    import main  # repo-root script

    _place(tmp_path / "raw" / "gadm", "PRT", box(177.0, -19.0, 180.0, -16.0), box(-180.0, -19.0, -178.0, -16.0))
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    called = []
    monkeypatch.setattr(main, "run_acquisition_phase", lambda *a, **k: called.append(1))
    with caplog.at_level("ERROR"):
        assert main.main(["PRT"]) == 1
    assert "PRT" in caplog.text and "180" in caplog.text and not called


def test_no_module_of_src_imports_the_guard():
    for path in (REPO / "src" / "geofrea").rglob("*.py"):
        if path.name == "country_guard.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            assert not any("country_guard" in n for n in names), path
