"""The figures of the climate forcing (`climate_forcing/figures.py`, COMMAND 68; spec v2 T-09): the ensemble mean, the agreement of the sign,
the percentage change, the shared scales, the files and what the subtitle says. Built from small synthetic forcing tables."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from geofrea.climate_forcing import figures as F
from geofrea.land_eligibility.cells import cell_id
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import MapContext, country_geometry

pytestmark = pytest.mark.unit

ISO = "ZZZ"


def _ids(n_rows=6, n_cols=8):
    rows, cols = np.meshgrid(np.arange(n_rows) + 1000, np.arange(n_cols) + 2000, indexing="ij")
    return cell_id(rows.ravel(), cols.ravel())


def _members(
    gcms=("GCM-A", "GCM-B", "GCM-C"),
    ssps=("SSP1-2.6", "SSP3-7.0"),
    windows=("2041-2070", "2071-2100"),
):
    return [
        F.MemberInfo(f"m_{g}_{s}_{w}", g, s, w, 1.0, 1.25)
        for g in gcms
        for s in ssps
        for w in windows
    ]


def _forcing(members, rsds=None, wind=None, dt=None, ids=None, no_wind=("GCM-C",)):
    ids = _ids() if ids is None else ids
    rng = np.random.default_rng(5)
    frames = []
    for m in members:
        k = len(ids)
        r = 1.0 + 0.03 * rng.standard_normal(k) if rsds is None else rsds(m, k)
        if m.gcm in no_wind:
            w = np.full(k, np.nan)
        else:
            w = 1.0 + 0.02 * rng.standard_normal(k) if wind is None else wind(m, k)
        d = 2.0 + rng.random(k) if dt is None else dt(m, k)
        frames.append(
            pd.DataFrame(
                {"cell_id": ids, "member": m.member, "delta_rsds": r, "delta_wind": w, "dT": d}
            )
        )
    return pd.concat(frames, ignore_index=True)


def _context(ids):
    polygon = country_geometry(None, ids)
    return MapContext(polygon, ms.country_extent(polygon, contiguous=False), None)


# ------------------------------------------------------------------------------------------------------------------------------ the maths


def test_a_ratio_is_drawn_as_a_percentage_change_and_a_temperature_as_it_is():
    assert F.drawn_quantity(F.BY_KEY["solar"], np.array([1.05, 0.9]))[0] == pytest.approx(5.0)
    assert F.drawn_quantity(F.BY_KEY["wind"], np.array([1.05, 0.9]))[1] == pytest.approx(-10.0)
    assert F.drawn_quantity(F.BY_KEY["temperature"], np.array([2.5]))[0] == pytest.approx(2.5)


def test_the_ensemble_mean_and_the_agreement_of_the_sign_follow_two_thirds():
    members = _members(ssps=("SSP1-2.6",), windows=("2041-2070",))
    # four cells, three GCMs: all up | two up, one down (agree exactly 2/3: not marked) | up, down, zero | two have a value, up and down
    values = {
        "GCM-A": [1.0, 1.0, 1.0, 1.0],
        "GCM-B": [2.0, 3.0, -1.0, -1.0],
        "GCM-C": [3.0, -1.0, 0.0, np.nan],
    }
    grids = {m.member: {"solar": np.array([values[m.gcm]], dtype="float32")} for m in members}
    field = F.ensemble_field("solar", "SSP1-2.6", "2041-2070", members, grids)
    assert field.mean[0] == pytest.approx([2.0, 1.0, 0.0, 0.0])
    assert field.disagree[0].tolist() == [False, False, True, True]
    assert field.n_models == 3 and field.gcms == ("GCM-A", "GCM-B", "GCM-C")


def test_wind_is_the_mean_of_the_gcms_that_have_a_wind_channel():
    members = _members(ssps=("SSP1-2.6",), windows=("2041-2070",))
    forcing = _forcing(members, wind=lambda m, k: np.full(k, 1.10 if m.gcm == "GCM-A" else 1.20))
    lattice = F.lattice_of(forcing["cell_id"].to_numpy())
    grids = F.member_grids(forcing, members, lattice)
    fields = F.ensemble_fields(members, grids)[("SSP1-2.6", "2041-2070")]
    assert fields["wind"].n_models == 2 and fields["solar"].n_models == 3
    assert np.nanmean(fields["wind"].mean) == pytest.approx(15.0, abs=1e-4)  # (10 % + 20 %) / 2
    assert not fields["wind"].disagree.any()  # both models agree on the sign


def test_the_scale_of_a_variable_is_shared_by_every_ssp_and_window_and_symmetric_for_a_change():
    members = _members()
    forcing = _forcing(members)
    lattice = F.lattice_of(forcing["cell_id"].to_numpy())
    fields = F.ensemble_fields(members, F.member_grids(forcing, members, lattice))
    solar = F.shared_scale(fields, "solar")
    assert solar[0] == pytest.approx(-solar[1]) and solar[1] > 0
    temperature = F.shared_scale(fields, "temperature")
    assert 1.0 < temperature[0] < temperature[1] < 4.0


def test_the_native_resolution_is_the_size_of_the_gcm_cells_at_the_latitude_of_the_country():
    members = [F.MemberInfo("m", "G", "SSP1-2.6", "2041-2070", 1.0, 1.25)]
    assert F.native_note(members, 0.0) == "~125 km"
    assert F.native_note(members, 60.0).startswith("~")
    mixed = [*members, F.MemberInfo("n", "H", "SSP1-2.6", "2041-2070", 2.5, 2.5)]
    assert "–" in F.native_note(mixed, 0.0)
    unknown = F.MemberInfo("m", "G", "S", "w", float("nan"), float("nan"))
    assert F.native_note([unknown], 0.0) == "native resolution of the GCMs"


def test_the_dots_mark_only_the_cells_where_the_models_disagree():
    members = _members(ssps=("SSP1-2.6",), windows=("2041-2070",))
    ids = _ids()
    half = len(ids) // 2

    def rsds(
        m, k
    ):  # the left half of the cells: every model up; the right half: two models up, one down
        sign = {"GCM-A": 1.0, "GCM-B": -1.0, "GCM-C": 1.0}[m.gcm]
        out = np.full(k, 1.04)
        out[half:] = 1.0 + 0.04 * sign
        return out

    forcing = _forcing(members, rsds=rsds)
    fields = F.ensemble_fields(members, F.member_grids(forcing, members, F.lattice_of(ids)))[
        ("SSP1-2.6", "2041-2070")
    ]
    assert not fields["solar"].disagree.any()  # exactly 2/3 agree: not "fewer than 2/3"

    def split(m, k):  # one model up, one down, one zero on the right half
        value = {"GCM-A": 1.04, "GCM-B": 0.96, "GCM-C": 1.0}[m.gcm]
        out = np.full(k, 1.04)
        out[half:] = value
        return out

    forcing = _forcing(members, rsds=split)
    fields = F.ensemble_fields(members, F.member_grids(forcing, members, F.lattice_of(ids)))[
        ("SSP1-2.6", "2041-2070")
    ]
    marked = fields["solar"].disagree.ravel()
    assert not marked[:half].any() and marked[half:].all()


# ----------------------------------------------------------------------------------------------------------------------------- the files


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    out = tmp_path_factory.mktemp("f4")
    members = _members()
    forcing = _forcing(members)
    ctx = _context(forcing["cell_id"].unique())
    files = F.draw_country(ISO, forcing, members, ctx, out)
    return out, files, members


def test_the_ensemble_sheets_the_grids_and_the_members_are_written_with_standard_names(drawn):
    out, files, members = drawn
    names = sorted(p.name for p in files)
    ensemble = sorted(n for n in names if "climate-forcing_" in n)
    assert ensemble == sorted(
        f"ZZZ_F4_climate-forcing_{s}_{w}.png"
        for s in ("SSP1-2.6", "SSP3-7.0")
        for w in ("2041-2070", "2071-2100")
    )
    assert sorted(n for n in names if "climate-forcing-grid" in n) == [
        f"ZZZ_F4_climate-forcing-grid_{v}.png" for v in ("solar", "temperature", "wind")
    ]
    member_files = sorted((out / "members").glob("*.png"))
    assert len(member_files) == len(members) == 12
    assert all(ms.validate_filename(p.name) for p in files)
    assert (out / "figures_index.json").exists() and (
        out / "members" / "figures_index.json"
    ).exists()
    # the folder holds the ensemble and the grids; the members are supplementary and live under members/
    assert len(list(out.glob("*.png"))) == 4 + 3


def test_a_sheet_says_what_it_shows_in_its_title_subtitle_and_metadata(drawn):
    out, *_ = drawn
    meta = ms.read_png_metadata(out / "ZZZ_F4_climate-forcing_SSP3-7.0_2071-2100.png")
    assert meta["Title"].endswith("Climate forcing · SSP3-7.0 · 2071–2100 vs 1995–2014")
    text = meta["Description"]
    assert "Ensemble mean of 3 GCMs (2 for wind)" in text and "GCM fields ~" in text
    assert "display smoothing" in text and "interpolated to 0.05°" in text
    assert meta["geofrea_n_gcms_wind"] == "2" and meta["geofrea_agreement_threshold"] == "0.667"
    assert meta["geofrea_display_smoothing"] == "applied"
    for variable in ("solar", "wind", "temperature"):
        assert meta[f"geofrea_scale_limits_{variable}"].count(",") == 1


def test_every_sheet_of_a_country_shares_the_limits_of_each_variable(drawn):
    _, files, _ = drawn
    for variable in ("solar", "wind", "temperature"):
        seen = {
            ms.read_png_metadata(p)[f"geofrea_scale_limits_{variable}"]
            for p in files
            if f"geofrea_scale_limits_{variable}" in ms.read_png_metadata(p)
        }
        assert len(seen) == 1, (variable, seen)


def test_a_gcm_without_a_wind_channel_says_why_its_wind_panel_is_grey(drawn):
    out, *_ = drawn
    path = out / "members" / "ZZZ_F4_forcing_GCM-C_SSP1-2.6_2041-2070.png"
    meta = ms.read_png_metadata(path)
    assert "Climate forcing · GCM-C · SSP1-2.6" in meta["Title"]
    assert "supplementary" in meta["Description"]
    ok = ms.read_png_metadata(out / "members" / "ZZZ_F4_forcing_GCM-A_SSP1-2.6_2041-2070.png")
    assert ok["geofrea_gcm"] == "GCM-A" and ok["geofrea_ssp"] == "SSP1-2.6"


def test_the_option_off_draws_the_gcm_fields_as_they_are_and_summary_leaves_the_members_out(
    tmp_path,
):
    members = _members(gcms=("GCM-A", "GCM-B"), ssps=("SSP1-2.6",), windows=("2041-2070",))
    forcing = _forcing(members, no_wind=())
    ctx = _context(forcing["cell_id"].unique())
    files = F.draw_country(
        ISO, forcing, members, ctx, tmp_path, display_smoothing="off", with_members=False
    )
    assert len(files) == 1 + 3 and not (tmp_path / "members").exists()
    meta = ms.read_png_metadata(files[0])
    assert meta["geofrea_display_smoothing"] == "off"
    assert "display smoothing" not in meta["Description"]
    assert "interpolated to 0.05°" in meta["Description"]
