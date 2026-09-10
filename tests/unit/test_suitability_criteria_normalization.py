"""Unit tests for geofrea.suitability_criteria.normalization."""

import numpy as np
import pytest

from geofrea.core.constants import NODATA_FLOAT
from geofrea.suitability_criteria.normalization import normalize_percentile, valid_finite_mask


@pytest.mark.unit
def test_valid_finite_mask_excludes_nan_and_nodata():
    data = np.array([1.0, np.nan, -9999.0, 3.0], dtype=np.float32)
    mask = valid_finite_mask(data, nodata=-9999.0)
    assert mask.tolist() == [True, False, False, True]


@pytest.mark.unit
def test_valid_finite_mask_without_nodata_only_checks_finite():
    data = np.array([1.0, np.inf, 2.0], dtype=np.float32)
    assert valid_finite_mask(data, nodata=None).tolist() == [True, False, True]


@pytest.mark.unit
def test_normalize_percentile_linear_between_clips():
    data = np.arange(0, 101, dtype=np.float64)
    valid = np.ones_like(data, dtype=bool)
    score = normalize_percentile(data, valid, 0.0, 100.0)
    assert score[0] == pytest.approx(0.0)
    assert score[50] == pytest.approx(0.5, abs=1e-6)
    assert score[100] == pytest.approx(1.0)


@pytest.mark.unit
def test_normalize_percentile_clips_outliers_to_bounds():
    data = np.array([0.0, 10.0, 20.0, 30.0, 1000.0], dtype=np.float64)
    valid = np.ones_like(data, dtype=bool)
    score = normalize_percentile(data, valid, 10.0, 90.0)
    assert score.min() == pytest.approx(0.0)
    assert score.max() == pytest.approx(1.0)


@pytest.mark.unit
def test_normalize_percentile_invalid_pixels_stay_nodata():
    data = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    valid = np.array([True, True, False, False])
    score = normalize_percentile(data, valid, 0.0, 100.0)
    assert score[2] == NODATA_FLOAT
    assert score[3] == NODATA_FLOAT


@pytest.mark.unit
def test_normalize_percentile_all_invalid_returns_all_nodata():
    data = np.zeros(5, dtype=np.float64)
    score = normalize_percentile(data, np.zeros(5, dtype=bool), 5.0, 95.0)
    assert np.all(score == NODATA_FLOAT)


@pytest.mark.unit
def test_normalize_percentile_flat_distribution_returns_half():
    data = np.full(10, 7.0, dtype=np.float64)
    valid = np.ones(10, dtype=bool)
    score = normalize_percentile(data, valid, 5.0, 95.0)
    assert np.all(score[valid] == 0.5)
