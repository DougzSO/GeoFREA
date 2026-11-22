"""F7b on hand-made cases: pixels of the units, excluded shares, deciles, enrichment, published estimates and the inventory guards (M-F7b-01 to M-F7b-04)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from rasterio.transform import from_origin

from geofrea.core.tables import write_table
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
from geofrea.external_validation.table_schemas import (
    VALIDATION_TABLE_SCHEMA_VERSION,
    PublishedComparisonRow,
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
def test_the_shipped_published_file_registers_only_verified_values_and_only_f7b_reads_it():
    entries = load_published()
    registered = [e for e in entries if e.status == "registered"]
    pending = [e for e in entries if e.status == "pending"]
    assert registered and pending
    assert all(e.value is not None and e.year is not None and e.source for e in registered)
    assert all(e.value is None for e in pending)  # no value without a verified source
    assert {e.country for e in entries} == {"BRA", "IND", "PRT"}
    assert {e.technology for e in entries if e.country == "PRT"} == {"solar", "wind"}
    assert all(e.status == "pending" for e in entries if e.country == "PRT")
    readers = [
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if "published_potential" in p.read_text(encoding="utf-8")
    ]
    # core/config_fingerprint.py only hashes the file (the manifest resumes F7b while it is unchanged); it reads no value
    assert readers and all(
        r.startswith("external_validation/") or r == "core/config_fingerprint.py" for r in readers
    )


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
def test_a_pending_entry_has_no_value_and_a_registered_entry_needs_a_value_and_a_year():
    pending = _entry(value=None, status="pending", year=None)
    assert pending.value is None and pending.status == "pending"
    with pytest.raises(ValueError):
        _entry(value=None)  # registered without a value
    with pytest.raises(ValueError):
        _entry(year=None)  # registered without a year
    with pytest.raises(ValueError):
        _entry(status="pending")  # pending with a value


@pytest.mark.unit
def test_a_pending_entry_comes_out_as_pending_beside_f5_with_no_error_and_no_number_from_it(
    tmp_path,
):
    table = pd.DataFrame({"member": ["m0"], "P_MW": [2000.0], "E_MWh": [3.0e6]})
    potentials = {"solar": {"central": table, "restrictive": table, "permissive": table}}
    entries = [
        _entry(
            country="PRT",
            technology="solar",
            value=None,
            status="pending",
            year=2023,
            note="no total found",
        )
    ]
    (row,) = comparison_rows(entries, "PRT", potentials, "m0")
    assert row["status"] == "pending" and row["published_value"] is None
    assert row["f5_central_m0"] == pytest.approx(
        2.0
    )  # F5's number stays; nothing is derived from the null
    assert set(row) == set(PublishedComparisonRow.model_fields)
    write_table(
        pd.DataFrame([row]),
        tmp_path / "published_comparison.parquet",
        schema_version=VALIDATION_TABLE_SCHEMA_VERSION,
        row_model=PublishedComparisonRow,
        compression="zstd",
        extra_metadata={},
    )
    assert (tmp_path / "published_comparison.parquet").is_file()


@pytest.mark.unit
def test_a_published_entry_with_an_unknown_unit_or_definition_is_refused():
    with pytest.raises(ValueError):
        _entry(unit="MW")
    with pytest.raises(ValueError):
        _entry(definition="guess")


# -- the real countries -----------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_the_real_countries_fail_loud_listing_every_missing_input_and_write_nothing(
    iso, tmp_path, monkeypatch
):
    from geofrea.core.config_loader import load_technologies
    from geofrea.external_validation.pipeline import (
        ValidationMissingInputError,
        build_external_validation,
    )

    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    with pytest.raises(ValidationMissingInputError) as info:
        build_external_validation(
            iso,
            load_technologies(REPO / "config" / "technologies.yaml"),
            ["solar", "wind"],
            REPO / "config" / "experiments.yaml",
            None,
            None,
            None,
            None,
            None,
            None,
        )
    listed = info.value.missing
    assert len(listed) == 1 + 2 * (
        1 + 1 + 3
    )  # the inventory, then per technology the candidates, the LCOE and three potentials
    assert any(f"gem_solar_wind_{iso}.parquet" in item for item in listed)
    for tech in ("solar", "wind"):
        assert any(f"candidates_{tech}__central" in item for item in listed)
        assert any(f"lcoe_summary_{tech}" in item for item in listed)
        assert sum(f"potential_{tech}__" in item for item in listed) == 3
    assert not (tmp_path / "outputs").exists()


def _lcoe(rows):
    return pd.DataFrame(rows, columns=["cell_id", "member", "lcoe_nominal"])


def test_a_candidate_cell_with_no_f6_row_in_any_member_is_left_out_and_counted():
    """L-253, D-F7b-009: F6 leaves out a cell whose PV zone or distance is missing."""
    from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
    from geofrea.external_validation.pipeline import NO_LCOE_REASON, merge_candidate_lcoe

    candidates = pd.DataFrame({"cell_id": [1, 2, 3], "eligible_area_km2": [10.0, 5.0, 2.0]})
    lcoe = _lcoe([(1, REFERENCE_MEMBER_ID, 40.0), (3, REFERENCE_MEMBER_ID, 50.0), (3, "m1", 51.0)])
    kept, left_out = merge_candidate_lcoe(candidates, lcoe, "solar")
    assert kept["cell_id"].tolist() == [1, 3]
    assert left_out == {"reason": NO_LCOE_REASON, "n_cells": 1, "eligible_area_km2": 5.0}
    assert not kept["lcoe_nominal"].isna().any()


def test_with_an_lcoe_for_every_candidate_nothing_is_left_out():
    from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
    from geofrea.external_validation.pipeline import merge_candidate_lcoe

    candidates = pd.DataFrame({"cell_id": [1, 2], "eligible_area_km2": [1.0, 2.0]})
    lcoe = _lcoe([(1, REFERENCE_MEMBER_ID, 40.0), (2, REFERENCE_MEMBER_ID, 41.0)])
    kept, left_out = merge_candidate_lcoe(candidates, lcoe, "wind")
    assert len(kept) == 2 and left_out is None


def test_a_cell_with_an_f6_row_in_another_member_but_not_at_the_reference_member_stays_an_error():
    from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
    from geofrea.external_validation.pipeline import ValidationInputError, merge_candidate_lcoe

    candidates = pd.DataFrame({"cell_id": [1, 2], "eligible_area_km2": [1.0, 2.0]})
    lcoe = _lcoe([(1, REFERENCE_MEMBER_ID, 40.0), (2, "m1", 41.0)])
    with pytest.raises(ValidationInputError, match="another member"):
        merge_candidate_lcoe(candidates, lcoe, "solar")


def test_the_exclusion_leaves_m_f7b_01_as_it_is_and_keeps_the_unit_of_a_left_out_cell_a_candidate():
    from geofrea.external_validation.pipeline import _unit_table

    units = pd.DataFrame(
        {
            "gem_unit_id": ["a", "b"],
            "capacity_mw": [10.0, 20.0],
            "start_year": [2015.0, 2016.0],
            "location_accuracy": ["exact", "exact"],
            "lat": [0.0, 0.0],
            "lon": [0.0, 0.0],
            "in_grid": [True, True],
            "row": [0, 1],
            "col": [0, 0],
            "cell_id": pd.array([1, 2], dtype="Int64"),
        }
    )
    keys = ("E1", "E2", "E3", "E4", "E5", "E6", "combined")
    excluded = {k: np.zeros((2, 1), dtype=bool) for k in keys}
    valid = np.ones((2, 1), dtype=bool)
    ranked = pd.DataFrame({"cell_id": [1], "decile": [3]})  # cell 2 was left out of the deciles
    table = _unit_table("solar", units, excluded, valid, ranked, pd.Series([1, 2]))
    assert table["candidate"].tolist() == [True, True]
    assert table["decile"].iloc[0] == 3 and pd.isna(table["decile"].iloc[1])
    assert table["excluded_combined"].tolist() == [0.0, 0.0]
