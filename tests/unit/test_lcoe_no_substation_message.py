"""The message of F6 when the candidates table has no `dist_sub_km` names a country with no eligible substation as the cause when it is (COMMAND 134, OQ-086, L-069)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from geofrea.lcoe_modeling import inputs
from geofrea.lcoe_modeling.inputs import LcoeInputError, read_member_inputs


def _tables(tmp_path):
    root = tmp_path / "outputs" / "ZZA"
    (root / "grid_alignment" / "artifacts").mkdir(parents=True)
    (root / "land_eligibility" / "artifacts").mkdir(parents=True)
    potential = root / "potential.parquet"
    pd.DataFrame({"cell_id": [1], "member": ["m"], "P_MW": [1.0], "CF": [0.2], "E_MWh": [1.0]}).to_parquet(potential)
    candidates = root / "land_eligibility" / "artifacts" / "candidates.parquet"
    pd.DataFrame({"cell_id": [1]}).to_parquet(candidates)
    return root, potential, candidates


def _call(potential, candidates):
    gen = read_member_inputs(None, potential_path=potential, candidates_path=candidates, forcing_path=potential, members=["m"], x_range=(0.0, 1.0))
    next(gen)


@pytest.mark.unit
def test_a_country_with_no_eligible_substation_is_named_as_the_cause(tmp_path, monkeypatch):
    monkeypatch.setattr(inputs, "_assert_potential_matches", lambda *a, **k: None)
    root, potential, candidates = _tables(tmp_path)
    (root / "grid_alignment" / "artifacts" / "poi_counts.json").write_text(json.dumps({"total": 1, "excluded_no_voltage": 1, "eligible": 0}), encoding="utf-8")
    with pytest.raises(LcoeInputError, match="no eligible substation") as err:
        _call(potential, candidates)
    assert "not a stale table" in str(err.value) and "dist_sub_km" in str(err.value)


@pytest.mark.unit
def test_without_that_cause_the_message_is_the_one_about_a_table_to_run_again(tmp_path, monkeypatch):
    monkeypatch.setattr(inputs, "_assert_potential_matches", lambda *a, **k: None)
    root, potential, candidates = _tables(tmp_path)
    with pytest.raises(LcoeInputError, match="must run again with the Group 3 layers"):
        _call(potential, candidates)
    (root / "grid_alignment" / "artifacts" / "poi_counts.json").write_text(json.dumps({"total": 9, "eligible": 4}), encoding="utf-8")
    with pytest.raises(LcoeInputError, match="must run again with the Group 3 layers"):
        _call(potential, candidates)
