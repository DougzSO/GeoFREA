"""F7b on hand-made cases: pixels of the units, excluded shares, deciles, enrichment, published estimates and the inventory guards (M-F7b-01 to M-F7b-04)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from rasterio.transform import from_origin

from geofrea.external_validation.enrichment import enrichment_rows, weighted_deciles
from geofrea.external_validation.exclusion import exclusion_rows
from geofrea.external_validation.inventory import (
    InventoryError,
    load_inventory,
    pixel_of_units,
    row_sets,
)
from geofrea.external_validation.published import (
    PublishedEntry,
    comparison_rows,
    load_published,
)

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "geofrea"
CONSTRAINTS = ("E1", "E2", "E3", "E4", "E5", "E6", "combined")


def _units(rows):
    return pd.DataFrame(rows, columns=["capacity_mw", "row", "col", "in_grid"]).astype(
        {"capacity_mw": "float64", "in_grid": bool}
    )


# -- pixels -----------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_a_unit_is_assigned_to_the_pixel_that_contains_it_and_outside_the_mask_it_is_off_the_grid():
    transform = from_origin(20.0, -4.8, 0.01, 0.01)  # north-west corner, 4 rows by 5 columns
    mask = np.ones((4, 5), dtype=bool)
    mask[3, 4] = False
    lat = np.array([-4.805, -4.835, -4.835, -4.795, -4.805, -4.805])
    lon = np.array([20.005, 20.015, 20.045, 20.005, 19.995, 20.055])
    row, col, in_grid = pixel_of_units(lat, lon, transform, mask)
    assert list(row[:3]) == [0, 3, 3] and list(col[:3]) == [0, 1, 4]
    assert list(in_grid) == [
        True,
        True,
        False,
        False,
        False,
        False,
    ]  # masked pixel, north, west, east


@pytest.mark.unit
def test_the_unit_sets_are_the_operating_units_and_the_configured_sensitivity_filters():
    frame = pd.DataFrame(
        {
            "status": ["operating", "operating", "operating", "Operating", "retired"],
            "start_year": [2010.0, 2020.0, np.nan, 2021.0, 2005.0],
            "location_accuracy": ["exact", "approximate", None, "exact", "exact"],
        }
    )
    assert list(row_sets(frame, None, None)) == ["operating"]
    sets = row_sets(frame, 2015, ["approximate"])
    assert set(sets) == {"operating", "vintage", "accuracy"}
    assert len(sets["operating"]) == 4
    assert list(sets["vintage"]["start_year"]) == [2020.0, 2021.0]  # no start year: not in the set
    assert len(sets["accuracy"]) == 3  # the unit with no accuracy stays


# -- exclusion shares -------------------------------------------------------------------------------------


@pytest.mark.unit
def test_the_excluded_share_is_the_capacity_weighted_mean_and_counts_units_off_the_grid_and_in_invalid_pixels():
    excluded = {name: np.zeros((2, 3), dtype="float32") for name in CONSTRAINTS}
    excluded["E1"][0, 0], excluded["E1"][0, 1], excluded["E1"][0, 2] = 1.0, 0.5, 0.25
    valid = np.ones((2, 3), dtype=bool)
    valid[0, 2] = False
    units = _units(
        [
            (10.0, 0, 0, True),  # E1 = 1
            (30.0, 0, 1, True),  # E1 = 0.5
            (5.0, 0, 2, True),  # an invalid pixel: counted, not averaged
            (20.0, 1, 1, True),  # E1 = 0
            (7.0, 0, 0, False),  # off the grid
        ]
    )
    rows = {r["constraint"]: r for r in exclusion_rows("t", "operating", units, excluded, valid)}
    e1 = rows["E1"]
    assert e1["mean_excluded_share"] == pytest.approx((10 * 1 + 30 * 0.5 + 20 * 0) / 60)
    assert e1["share_above_0"] == pytest.approx(40 / 60)
    assert e1["share_at_least_half"] == pytest.approx(40 / 60)
    assert e1["share_equal_1"] == pytest.approx(10 / 60)
    assert (e1["n_outside_grid"], e1["capacity_outside_grid_mw"]) == (1, 7.0)
    assert (e1["n_invalid_pixel"], e1["capacity_invalid_pixel_mw"]) == (1, 5.0)
    assert (e1["n_evaluated"], e1["capacity_evaluated_mw"]) == (3, 60.0)
    assert rows["E2"]["mean_excluded_share"] == 0.0


@pytest.mark.unit
def test_with_no_unit_in_a_valid_pixel_the_shares_are_null():
    excluded = {n: np.zeros((1, 1), dtype="float32") for n in CONSTRAINTS}
    rows = exclusion_rows(
        "t", "operating", _units([(5.0, 0, 0, False)]), excluded, np.ones((1, 1), bool)
    )
    assert all(r["mean_excluded_share"] is None for r in rows)


# -- deciles and enrichment -------------------------------------------------------------------------------


@pytest.mark.unit
def test_deciles_cut_the_eligible_area_in_tenths_in_lcoe_order_with_ties_by_cell_id():
    lcoe = np.array([50.0, 10.0, 30.0, 20.0, 40.0, 10.0, 60.0, 70.0, 80.0, 90.0])
    decile = weighted_deciles(lcoe, np.ones(10), np.arange(10))
    # ordered by (lcoe, cell id): 1, 5, 3, 2, 4, 0, ...: the tie at 10 goes to the smaller id first
    assert decile[1] == 1 and decile[5] == 2 and decile[3] == 3 and decile[9] == 10
    assert sorted(decile) == list(range(1, 11))


@pytest.mark.unit
def test_a_large_cell_goes_to_the_decile_of_its_area_midpoint():
    # areas 6 and 4 in LCOE order: the first cell spans 0 to 60% of the area, midpoint 30% -> decile 4; the second, midpoint 80% -> decile 9
    decile = weighted_deciles(np.array([1.0, 2.0]), np.array([6.0, 4.0]), np.array([0, 1]))
    assert list(decile) == [4, 9]


@pytest.mark.unit
def test_deciles_refuse_a_non_positive_area_or_a_non_finite_lcoe():
    with pytest.raises(ValueError):
        weighted_deciles(np.array([1.0, np.inf]), np.ones(2), np.arange(2))
    with pytest.raises(ValueError):
        weighted_deciles(np.array([1.0, 2.0]), np.array([1.0, 0.0]), np.arange(2))


@pytest.mark.unit
def test_the_enrichment_ratio_is_the_capacity_share_over_the_area_share_of_the_lowest_deciles():
    candidates = pd.DataFrame(
        {"cell_id": np.arange(10), "eligible_area_km2": np.ones(10), "decile": np.arange(1, 11)}
    )
    units = pd.DataFrame(
        {
            "capacity_mw": [30.0, 10.0, 60.0, 20.0],
            "cell_id": pd.array(
                [0, 1, 7, 99], dtype="Int64"
            ),  # deciles 1, 2, 8; cell 99 is no candidate
            "in_grid": [True, True, True, True],
        }
    )
    rows = enrichment_rows("t", "operating", candidates, units, [1, 2, 3])
    lowest = {r["decile"]: r for r in rows if r["kind"] == "lowest"}
    # the capacity in candidate cells is 100 MW; deciles 1 and 2 hold 30 and 10 MW of it
    assert lowest[1]["capacity_share"] == pytest.approx(0.3)
    assert lowest[1]["eligible_area_share"] == pytest.approx(0.1)
    assert lowest[1]["enrichment_ratio"] == pytest.approx(3.0)
    assert lowest[2]["enrichment_ratio"] == pytest.approx(0.4 / 0.2)
    assert lowest[3]["capacity_share"] == pytest.approx(0.4)
    assert lowest[1]["capacity_share_non_candidate"] == pytest.approx(20 / 120)
    by_decile = {r["decile"]: r for r in rows if r["kind"] == "decile"}
    assert by_decile[8]["capacity_share"] == pytest.approx(0.6)
    assert sum(r["eligible_area_share"] for r in by_decile.values()) == pytest.approx(1.0)


@pytest.mark.unit
def test_with_no_capacity_in_candidates_the_capacity_shares_and_ratios_are_null():
    candidates = pd.DataFrame(
        {"cell_id": [1, 2], "eligible_area_km2": [1.0, 1.0], "decile": [1, 10]}
    )
    units = pd.DataFrame(
        {"capacity_mw": [5.0], "cell_id": pd.array([9], dtype="Int64"), "in_grid": [True]}
    )
    rows = enrichment_rows("t", "operating", candidates, units, [1])
    assert all(r["capacity_share"] is None and r["enrichment_ratio"] is None for r in rows)
    assert rows[0]["capacity_share_non_candidate"] == 1.0


# -- inventory --------------------------------------------------------------------------------------------


def _write_inventory(root: Path, synthetic: bool, drop: str | None = None) -> None:
    folder = root / "raw" / "gem" / "ZZZ"
    folder.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "gem_unit_id": ["a"],
            "tech": ["wind"],
            "status": ["operating"],
            "capacity_mw": [10.0],
            "start_year": [2020.0],
            "location_accuracy": ["exact"],
            "lat": [-4.9],
            "lon": [20.1],
        }
    )
    if drop:
        frame = frame.drop(columns=drop)
    frame.to_parquet(folder / "gem_solar_wind_ZZZ.parquet")
    (folder / "gem_snapshot.json").write_text(
        json.dumps({"synthetic": synthetic}), encoding="utf-8"
    )


@pytest.mark.unit
def test_a_synthetic_inventory_is_refused_in_a_production_run_and_accepted_otherwise(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _write_inventory(tmp_path, synthetic=True)
    assert load_inventory("ZZZ", production=False).synthetic is True
    with pytest.raises(InventoryError, match="synthetic"):
        load_inventory("ZZZ", production=True)


@pytest.mark.unit
def test_a_missing_inventory_or_column_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    with pytest.raises(InventoryError, match="absent"):
        load_inventory("ZZZ", production=False)
    _write_inventory(tmp_path, synthetic=False, drop="capacity_mw")
    with pytest.raises(InventoryError, match="columns missing"):
        load_inventory("ZZZ", production=False)


# -- published estimates ----------------------------------------------------------------------------------


@pytest.mark.unit
def test_the_shipped_published_file_is_empty_and_only_f7b_reads_it():
    assert load_published() == []
    readers = [
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if "published_potential" in p.read_text(encoding="utf-8")
    ]
    assert readers and all(r.startswith("external_validation/") for r in readers)


def _entry(**changes) -> PublishedEntry:
    base = {
        "country": "ZZZ",
        "technology": "wind",
        "value": 3.5,
        "unit": "GW",
        "source": "s",
        "year": 2020,
        "definition": "technical",
        "tier": "1",
    }
    return PublishedEntry(**(base | changes))


@pytest.mark.unit
def test_the_comparison_puts_the_estimate_beside_f5_at_the_reference_member_and_computes_nothing_from_it():
    def table(scale: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "member": ["m0", "m0", "m1"],
                "P_MW": [1000.0 * scale, 2000.0 * scale, 9000.0],
                "E_MWh": [1.0e6 * scale, 3.0e6 * scale, 9.0e6],
            }
        )

    potentials = {
        "wind": {"central": table(1.0), "restrictive": table(0.5), "permissive": table(2.0)}
    }
    entries = [
        _entry(),
        _entry(value=7.0, unit="TWh_per_year", source="t", year=2021, definition="economic"),
        _entry(country="OTH", source="u"),
        _entry(technology="other", source="v"),
    ]
    rows = comparison_rows(entries, "ZZZ", potentials, "m0")
    assert [r["source"] for r in rows] == ["s", "t"]
    gw, twh = rows
    assert (gw["f5_central_m0"], gw["f5_restrictive_m0"], gw["f5_permissive_m0"]) == (3.0, 1.5, 6.0)
    assert gw["definition_matches"] is True and twh["definition_matches"] is False
    assert twh["f5_central_m0"] == pytest.approx(4.0) and gw["published_value"] == 3.5


@pytest.mark.unit
def test_a_published_entry_with_an_unknown_unit_or_definition_is_refused():
    with pytest.raises(ValueError):
        _entry(unit="MW")
    with pytest.raises(ValueError):
        _entry(definition="guess")
