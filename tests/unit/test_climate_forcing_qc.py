"""The QC summaries of forcing.parquet read the member ids once each, not as ten million strings, and give what they gave (COMMAND 75)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from geofrea.climate_forcing import pipeline

pytestmark = pytest.mark.unit


def _reference_ratio_qc(forcing_path):
    """`_ratio_qc` as it was: the member column as strings, grouped by the GCM extracted from the id."""
    df = pd.read_parquet(forcing_path, columns=["member", "delta_rsds", "delta_wind"])
    df["member"] = df["member"].astype(str)
    df = df[df["member"] != "m0"]
    df["gcm"] = df["member"].str.extract(r"^m_(.+)_ssp")[0]
    return {
        gcm: {col: {"min": float(g[col].min()), "max": float(g[col].max())} for col in ("delta_rsds", "delta_wind")}
        for gcm, g in df.groupby("gcm")
    }


def _reference_isolated_counts(forcing_path):
    df = pd.read_parquet(forcing_path, columns=["member", "dT_isolated_native_cell"])
    df["member"] = df["member"].astype(str)
    return {k: int(v) for k, v in df.groupby("member")["dT_isolated_native_cell"].sum().items() if v}


def _forcing(tmp_path, categorical):
    rng = np.random.default_rng(75)
    members = ["m0", "m_gfdl_esm4_ssp126_2041_2070", "m_gfdl_esm4_ssp370_2041_2070", "m_ipsl_cm6a_lr_ssp126_2071_2100", "m_cnrm_cm6_1_ssp370_2041_2070"]
    n = 4_000
    df = pd.DataFrame(
        {
            "cell_id": np.tile(np.arange(n // len(members)), len(members)).astype("int64"),
            "member": np.repeat(members, n // len(members)),
            "delta_rsds": rng.uniform(0.9, 1.1, n).astype("float32"),
            "delta_wind": rng.uniform(0.7, 1.3, n).astype("float32"),
            "dT_isolated_native_cell": rng.uniform(size=n) < 0.05,
        }
    )
    df.loc[df["member"] == "m_cnrm_cm6_1_ssp370_2041_2070", "dT_isolated_native_cell"] = False  # a member with none is left out
    df.loc[5, "delta_wind"] = np.nan
    if categorical:
        df["member"] = df["member"].astype("category")
    path = tmp_path / ("cat.parquet" if categorical else "obj.parquet")
    df.to_parquet(path)
    return path


@pytest.mark.parametrize("categorical", [True, False])
def test_the_ratio_and_isolated_summaries_equal_the_string_versions(tmp_path, categorical):
    path = _forcing(tmp_path, categorical)
    assert pipeline._ratio_qc(path) == _reference_ratio_qc(path)
    assert list(pipeline._ratio_qc(path)) == list(_reference_ratio_qc(path))  # the order of the GCMs, written to members.yaml
    got = pipeline._isolated_counts(path)
    assert got == _reference_isolated_counts(path) and list(got) == list(_reference_isolated_counts(path))
    assert "m_cnrm_cm6_1_ssp370_2041_2070" not in got and "m0" in pipeline._member_codes(pd.read_parquet(path)["member"])[1]
