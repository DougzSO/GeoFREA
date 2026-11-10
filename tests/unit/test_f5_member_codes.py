"""F5 reads the members of the forcing from the codes of the categorical column, not from a string per row (COMMAND 127, item c).

The old path (`forcing["member"].astype(str)`, `groupby`, `assert_forcing_usable` on the whole forcing) is kept in the module for any other
column, and is the oracle here. `climate_forcing/forcing.py` is not changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from geofrea.climate_forcing.forcing import ForcingContractError, assert_forcing_usable
from geofrea.technical_potential import pipeline as P
from tests.unit.test_technical_potential_pipeline import (  # noqa: F401  (fixtures)
    _run,
    registry,
    synthetic_params,
)

pytestmark = pytest.mark.unit

WIND_RANGE = (0.5, 1.5)
CHANNELS = ("resource_wind", "resource_tas", "resource_rsds")


def _forcing(members, n_cells=6, *, categories=None, seed=1):
    """Rows in the order the members appear (member-major), the way F4 writes them; `categories` fixes the order of the dictionary."""
    rng = np.random.default_rng(seed)
    frames = []
    for m in members:
        frames.append(
            pd.DataFrame(
                {
                    "cell_id": np.arange(n_cells, dtype="int64") * 3 + 100,
                    "member": m,
                    "delta_rsds": rng.uniform(0.9, 1.1, n_cells),
                    "dT": rng.uniform(0.0, 3.0, n_cells),
                    "delta_wind": rng.uniform(0.8, 1.2, n_cells),
                }
            )
        )
    frame = pd.concat(frames, ignore_index=True)
    frame["member"] = pd.Categorical(frame["member"], categories=categories or list(dict.fromkeys(members)))
    return frame


def _masked(rows=()):
    return pd.DataFrame(
        {"cell_id": np.array([r[0] for r in rows], dtype="int64"), "member": pd.Series([r[1] for r in rows], dtype="object")}
    )


CELLS = np.arange(6, dtype="int64") * 3 + 100
MEMBERS = ["m_ref", "m_b", "m_c", "m_d"]
# the dictionary in another order than the rows, with a member that has no row
CATEGORIES = ["m_d", "unused", "m_c", "m_ref", "m_b"]


def _old_by_member(forcing):
    s = forcing.assign(member=forcing["member"].astype(str))
    return {str(m): g.set_index("cell_id") for m, g in s.groupby("member", sort=False)}


def test_the_factor_tables_are_those_of_the_string_path_in_the_same_order():
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    assert P._has_string_member_codes(forcing, MEMBERS)
    new = P._forcing_by_member(forcing, True)
    old = _old_by_member(forcing)
    assert list(new) == list(old) == MEMBERS
    for m in MEMBERS:
        assert list(new[m].columns) == ["delta_rsds", "dT", "delta_wind"]
        pd.testing.assert_frame_equal(new[m], old[m].drop(columns="member"), check_exact=True)
        for c in new[m].columns:
            assert new[m][c].to_numpy().tobytes() == old[m][c].to_numpy().tobytes()


def test_a_member_that_appears_late_keeps_its_place_by_first_appearance():
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    shuffled = pd.concat([forcing[forcing["member"] == "m_c"], forcing[forcing["member"] != "m_c"]], ignore_index=True)
    assert list(P._forcing_by_member(shuffled, True)) == list(_old_by_member(shuffled)) == ["m_c", "m_ref", "m_b", "m_d"]


def test_the_members_in_use_ignore_the_unused_categories():
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    assert sorted(P._members_in_use(forcing)) == sorted(MEMBERS)
    assert "unused" not in P._members_in_use(forcing)


@pytest.mark.parametrize(
    "column",
    [
        pd.Series(["a", "b"], dtype="object"),  # strings
        pd.Series(pd.Categorical(["a", None])),  # a missing member
        pd.Series(pd.Categorical([1, 2])),  # categories that are not strings
    ],
)
def test_any_other_column_takes_the_old_path(column):
    assert not P._has_string_member_codes(pd.DataFrame({"member": column}), ["a", "b"])


def test_a_repeated_member_name_takes_the_old_path():
    assert not P._has_string_member_codes(_forcing(MEMBERS), ["m_ref", "m_ref", "m_b"])


def test_the_guard_passes_by_member_when_it_passes_on_the_whole_forcing():
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    whole = forcing.assign(member=forcing["member"].astype(str))
    assert_forcing_usable(whole, _masked(), CELLS, MEMBERS, WIND_RANGE, CHANNELS)
    P._assert_usable_by_member(forcing, _masked(), CELLS, MEMBERS, WIND_RANGE, CHANNELS)


def _message_of(call) -> str:
    with pytest.raises(ForcingContractError) as caught:
        call()
    return str(caught.value)


@pytest.mark.parametrize(
    "damage",
    ["drop_row", "nan_dT", "nan_wind", "wind_out_of_range", "missing_member", "several_members_fail"],
)
def test_the_guard_raises_the_same_error_as_on_the_whole_forcing(damage):
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    members = list(MEMBERS)
    if damage == "drop_row":
        forcing = forcing.drop(index=3)
    elif damage == "nan_dT":
        forcing.loc[(forcing["member"] == "m_c") & (forcing["cell_id"] == 103), "dT"] = np.nan
    elif damage == "nan_wind":
        forcing.loc[(forcing["member"] == "m_b") & (forcing["cell_id"] == 106), "delta_wind"] = np.nan
    elif damage == "wind_out_of_range":
        forcing.loc[(forcing["member"] == "m_d") & (forcing["cell_id"] == 109), "delta_wind"] = 9.0
    elif damage == "missing_member":
        members = [*MEMBERS, "m_not_in_forcing"]
    else:  # a failure of a different kind in two members: the first check of the whole forcing is the one raised
        forcing.loc[(forcing["member"] == "m_d") & (forcing["cell_id"] == 109), "delta_wind"] = 9.0
        forcing = forcing.drop(index=8)
    whole = forcing.assign(member=forcing["member"].astype(str))
    old = _message_of(lambda: assert_forcing_usable(whole, _masked(), CELLS, members, WIND_RANGE, CHANNELS))
    new = _message_of(lambda: P._assert_usable_by_member(forcing, _masked(), CELLS, members, WIND_RANGE, CHANNELS))
    assert new == old


def test_a_declared_wind_mask_passes_by_member_too():
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    forcing.loc[(forcing["member"] == "m_b") & (forcing["cell_id"] == 106), "delta_wind"] = np.nan
    masked = _masked([(106, "m_b")])
    assert_forcing_usable(forcing.assign(member=forcing["member"].astype(str)), masked, CELLS, MEMBERS, WIND_RANGE, CHANNELS)
    P._assert_usable_by_member(forcing, masked, CELLS, MEMBERS, WIND_RANGE, CHANNELS)


def test_the_guard_never_makes_a_string_column_of_the_whole_forcing(monkeypatch):
    forcing = _forcing(MEMBERS, categories=CATEGORIES)
    sizes = []
    real = assert_forcing_usable

    def spy(frame, *a, **k):
        sizes.append(len(frame))
        return real(frame, *a, **k)

    monkeypatch.setattr(P, "assert_forcing_usable", spy)
    P._assert_usable_by_member(forcing, _masked(), CELLS, MEMBERS, WIND_RANGE, CHANNELS)
    assert sizes == [len(CELLS)] * len(MEMBERS)  # one member's rows each time, never the whole forcing


# --- the whole of F5 ----------------------------------------------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_f4_writes_it(monkeypatch, categories_reversed: bool):
    """The F5 tests write `member` as strings; F4 writes a categorical (dictionary): read it back that way."""
    real = pd.read_parquet

    def read(path, *a, **k):
        frame = real(path, *a, **k)
        if Path(path).name == "forcing.parquet":
            names = list(dict.fromkeys(frame["member"].astype(str)))
            categories = names[::-1] if categories_reversed else names
            frame["member"] = pd.Categorical(frame["member"].astype(str), categories=[*categories, "unused_member"])
        return frame

    monkeypatch.setattr(pd, "read_parquet", read)


def test_every_artifact_of_f5_is_byte_identical_with_a_categorical_forcing(tmp_path_factory, registry, synthetic_params, monkeypatch):  # noqa: F811
    _, string_out = _run(tmp_path_factory.mktemp("string"), registry, synthetic_params)  # the forcing of the test, member as strings
    taken = {"coded": 0}
    real = P._assert_usable_by_member

    def spy(*a, **k):
        taken["coded"] += 1
        return real(*a, **k)

    monkeypatch.setattr(P, "_assert_usable_by_member", spy)
    _as_f4_writes_it(monkeypatch, categories_reversed=True)
    _, coded_out = _run(tmp_path_factory.mktemp("coded"), registry, synthetic_params)
    assert taken["coded"] > 0  # the new path ran
    names = sorted(p.name for p in string_out.rglob("*") if p.is_file())
    assert names == sorted(p.name for p in coded_out.rglob("*") if p.is_file())
    assert any(n.startswith("potential_wind__") for n in names)
    for name in names:
        assert _sha(string_out / name) == _sha(coded_out / name), name


def test_the_categorical_forcing_on_the_old_path_is_the_same_too(tmp_path_factory, registry, synthetic_params, monkeypatch):  # noqa: F811
    _as_f4_writes_it(monkeypatch, categories_reversed=False)
    _, coded_out = _run(tmp_path_factory.mktemp("coded"), registry, synthetic_params)
    monkeypatch.setattr(P, "_has_string_member_codes", lambda *a, **k: False)
    _, old_out = _run(tmp_path_factory.mktemp("old"), registry, synthetic_params)
    for name in sorted(p.name for p in coded_out.rglob("*") if p.is_file()):
        assert _sha(coded_out / name) == _sha(old_out / name), name


def test_a_member_not_in_members_yaml_is_still_refused_with_the_same_message(tmp_path_factory, registry, synthetic_params, monkeypatch):  # noqa: F811
    real = pd.read_parquet

    def read(path, *a, **k):
        frame = real(path, *a, **k)
        if Path(path).name == "forcing.parquet":
            frame["member"] = pd.Categorical(frame["member"].astype(str).where(frame["member"].astype(str) != "m_gcmA_ssp245_2041-2070", "m_stranger"))
        return frame

    monkeypatch.setattr(pd, "read_parquet", read)
    with pytest.raises(P.CfModelError, match="not listed in members.yaml: \\['m_stranger'\\]"):
        _run(tmp_path_factory.mktemp("stranger"), registry, synthetic_params)
