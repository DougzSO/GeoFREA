"""Unit tests for scripts/gcm_selection_spread.py (the pure selection step; no data on disk)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gcm_selection_spread.py"
_spec = importlib.util.spec_from_file_location("gcm_selection_spread", _SCRIPT)
spread = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spread)


@pytest.mark.unit
def test_farthest_point_selection_keeps_seeds_and_spans_the_extremes():
    names = ["gfdl_esm4", "miroc6", "low", "mid", "high"]
    # one standardized axis is enough: the seeds sit in the middle, the extremes are far away
    matrix = np.array([[5.0], [5.2], [0.0], [5.1], [10.0]])

    chosen = spread.farthest_point_selection(matrix, names, ["gfdl_esm4", "miroc6"], k=4)

    assert chosen[:2] == ["gfdl_esm4", "miroc6"]
    assert set(chosen[2:]) == {"low", "high"}  # the two extremes beat the redundant "mid"


@pytest.mark.unit
def test_farthest_point_selection_never_returns_more_than_the_candidates():
    names = ["a", "b"]
    chosen = spread.farthest_point_selection(np.array([[0.0], [1.0]]), names, [], k=6)

    assert sorted(chosen) == ["a", "b"]
