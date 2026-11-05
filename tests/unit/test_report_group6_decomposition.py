"""`scripts/report_group6_decomposition.py`: the decomposition of the change of the eligible area, by criterion, from numbers computed by hand."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_group6_decomposition.py"
spec = importlib.util.spec_from_file_location("report_group6_decomposition", SCRIPT)
g6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g6)


def sums(eligible, **excluded):
    out = {"cell_area_km2": 100.0, "eligible_area_km2": eligible}
    for c in "123456":
        out[f"excluded_E{c}_km2"] = float(excluded.get(f"E{c}", 0.0))
    return out


def test_one_criterion_replaced_by_another_is_split_exactly_and_without_interaction():
    # Only E6 changes: the density rule excluded 20 of 100 km2, the settlements exclude 10. A_old = 80, A_new = 90.
    row = g6.decompose(sums(80.0, E6=20.0), sums(90.0, E6=10.0), None)
    assert row["change_km2"] == pytest.approx(10.0)
    assert row["interaction_km2"] == pytest.approx(0.0, abs=1e-9)
    assert row["settlements_km2"] == pytest.approx(10.0 * math.log(0.9) / math.log(1.125))  # -8.9456
    assert row["density_removed_km2"] == pytest.approx(10.0 * (-math.log(0.8)) / math.log(1.125))  # 18.9456
    for name in ("slope", "rivers", "other", "min_area"):
        assert row[f"{name}_km2"] == pytest.approx(0.0, abs=1e-9)


def test_slope_and_rivers_take_their_own_terms_and_an_unchanged_criterion_takes_none():
    # E4 (slope) 30 -> 20 km2 and E3 (rivers) 10 -> 15 km2, E1 unchanged at 5, on 100 km2. Independent exclusions: A = 100 (1-e1)(1-e3)(1-e4).
    a_old = 100 * 0.95 * 0.90 * 0.70
    a_new = 100 * 0.95 * 0.85 * 0.80
    row = g6.decompose(sums(a_old, E1=5, E3=10, E4=30), sums(a_new, E1=5, E3=15, E4=20), None)
    assert row["other_km2"] == pytest.approx(0.0, abs=1e-9)
    assert row["interaction_km2"] == pytest.approx(0.0, abs=1e-9)  # independent exclusions: the product explains the whole change
    assert row["slope_km2"] > 0 > row["rivers_km2"]
    assert row["slope_km2"] + row["rivers_km2"] == pytest.approx(a_new - a_old)
    ratio = row["slope_km2"] / row["rivers_km2"]
    assert ratio == pytest.approx(math.log(0.8 / 0.7) / math.log(0.85 / 0.90))


def test_overlapping_exclusions_leave_an_interaction_term_that_is_named_and_the_total_still_adds_up():
    row = g6.decompose(sums(60.0, E3=20, E4=30), sums(70.0, E3=20, E4=20), None)  # independent would give 100 * 0.8 * 0.7 = 56 and 100 * 0.8 * 0.8 = 64
    assert row["interaction_km2"] != pytest.approx(0.0)
    total = sum(row[f"{n}_km2"] for n in g6.CRITERIA) + row["interaction_km2"] + row["min_area_km2"]
    assert total == pytest.approx(row["change_km2"])


def test_the_minimum_area_term_is_the_exact_removal_of_the_summary():
    area = {"area_before_km2": 90.0, "area_removed_by_pixel_floor_km2": 1.0, "area_removed_by_cluster_floor_km2": 2.0}
    row = g6.decompose(sums(80.0, E6=20.0), sums(87.0, E6=10.0), area)
    assert row["min_area_km2"] == pytest.approx(-3.0)
    assert row["min_area_pixel_floor_km2"] == pytest.approx(-1.0) and row["min_area_cluster_floor_km2"] == pytest.approx(-2.0)
    assert row["change_km2"] == pytest.approx(7.0)
    assert row["settlements_km2"] + row["density_removed_km2"] == pytest.approx(10.0)  # the change before the rule
    with pytest.raises(g6.DecompositionError, match="minimum-area record"):
        g6.decompose(sums(80.0, E6=20.0), sums(87.5, E6=10.0), area)


def test_tables_of_another_grid_are_refused():
    other = sums(80.0, E6=20.0) | {"cell_area_km2": 200.0}
    with pytest.raises(g6.DecompositionError, match="same cell area"):
        g6.decompose(sums(80.0, E6=20.0), other, None)


def _table(path, eligible):
    frame = pd.DataFrame({"cell_area_km2": [50.0, 50.0], "eligible_area_km2": eligible, **{f"excluded_area_km2_E{c}": [1.0, 2.0] for c in "123456"}})
    frame.to_parquet(path)


def test_a_snapshot_is_refused_when_the_tables_are_not_those_of_the_reference_summary(tmp_path):
    summary = {"technologies": {"solar": {"scenarios": {"central": {"cells": "data:outputs/X/land_eligibility/artifacts/cells_solar__central.parquet", "eligible_area_km2": 10.0}}}}}
    summary_path = tmp_path / "land_eligibility.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    _table(tmp_path / "cells_solar__central.parquet", [4.0, 6.0])
    snap = g6.snapshot(summary_path, tmp_path, "XXX", "ref")
    assert snap["technologies"]["solar"]["central"]["eligible_area_km2"] == 10.0
    assert snap["technologies"]["solar"]["central"]["excluded_E3_km2"] == 3.0
    _table(tmp_path / "cells_solar__central.parquet", [4.0, 7.0])
    with pytest.raises(g6.DecompositionError, match="not the one of the reference round"):
        g6.snapshot(summary_path, tmp_path, "XXX", "ref")


def test_the_reference_summary_is_found_through_latest_json(tmp_path):
    run = "abc"
    target = tmp_path / "references" / run / "PRT" / "files" / "outputs" / "PRT" / "artifacts" / "land_eligibility.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    (tmp_path / "references" / "latest.json").write_text(json.dumps({"PRT": run}), encoding="utf-8")
    assert g6.reference_summary(tmp_path, "PRT", None) == target
    assert target.parents[5].name == run  # `main` records the run id from this position
    with pytest.raises(g6.DecompositionError, match="no accepted round"):
        g6.reference_summary(tmp_path, "IND", None)
