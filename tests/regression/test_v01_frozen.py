"""V-01 frozen regression: F1 + F2a aligned rasters and exclusions E1-E3 on the synthetic ZZZ country.

A fresh run (fixture regenerated, pipeline executed in a temp data dir) is compared with
tests/fixtures/v01/zzz.npz. Binary and integer-valued layers must match exactly; float layers use
rtol = 1e-6 (METHODOLOGY V-01). Refreeze only with Douglas's authorization: scripts/freeze_v01_fixtures.py.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.regression.v01_run import REPO_ROOT, run_zzz

FROZEN = REPO_ROOT / "tests" / "fixtures" / "v01" / "zzz.npz"


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    return run_zzz(tmp_path_factory.mktemp("v01"))


@pytest.mark.regression
def test_the_same_layers_are_produced(fresh):
    frozen = np.load(FROZEN)
    assert {k.replace("__", "/") for k in frozen.files} == set(fresh)


@pytest.mark.regression
def test_every_layer_matches_the_frozen_fixture(fresh):
    frozen = np.load(FROZEN)
    for key in frozen.files:
        name = key.replace("__", "/")
        want, got = frozen[key], fresh[name]
        assert got.shape == want.shape, name
        if np.array_equal(
            want, want.astype(np.uint8)
        ):  # binary / integer-valued (classes, flags, masks)
            np.testing.assert_array_equal(got, want, err_msg=name)
        else:
            np.testing.assert_allclose(got, want, rtol=1e-6, atol=0.0, err_msg=name)
