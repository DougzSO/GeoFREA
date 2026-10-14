"""One definition each (I-4 of the pre-research audit): the shared values of `core/constants.py` are read by the modules and agree with the configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from geofrea.climate_forcing import hazards, members
from geofrea.core import constants
from geofrea.data_acquisition.fetchers import cmip6, era5, wind
from geofrea.land_eligibility import pipeline as land_pipeline
from geofrea.lcoe_modeling import summary as lcoe_summary
from geofrea.robustness_analysis import (
    evaluator,
    h1_rank_robustness,
    h2_aggregation,
    h3_robust_vs_nominal,
    h4_axis_dominance,
)
from geofrea.siting_layers import physical_layers

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"


@pytest.mark.unit
def test_the_reference_period_of_the_configuration_is_the_one_the_modules_read():
    windows = yaml.safe_load(EXPERIMENTS.read_text(encoding="utf-8"))["windows"]
    assert (
        windows["reference"]["start_year"],
        windows["reference"]["end_year"],
    ) == constants.REFERENCE_PERIOD
    assert not hasattr(era5, "REFERENCE_PERIOD")  # read from constants
    assert cmip6.YEAR_RANGES["historical"] is constants.REFERENCE_PERIOD
    assert not hasattr(members, "REFERENCE_WINDOW") and not hasattr(hazards, "REFERENCE_YEARS")


@pytest.mark.unit
def test_the_sensitivity_grids_and_the_quantiles_have_one_definition():
    for module in (h1_rank_robustness, h2_aggregation, h3_robust_vs_nominal, h4_axis_dominance):
        assert module.SENSITIVITY_TOP_K_PERCENT is constants.SENSITIVITY_TOP_K_PERCENT
    assert h2_aggregation.GAMMA_PROFILE is constants.GAMMA_PROFILE
    assert not hasattr(h4_axis_dominance, "SENSITIVITY_BOUNDARIES")
    assert constants.H4_SENSITIVITY_BOUNDARIES == ((0.30, 0.70), (0.45, 0.55))
    assert evaluator.MR_QUANTILE is constants.MR_QUANTILE == 0.9
    assert not hasattr(lcoe_summary, "QUANTILES") and constants.LCOE_QUANTILES == (0.1, 0.5, 0.9)


@pytest.mark.unit
def test_the_wind_atlas_heights_have_one_definition():
    assert land_pipeline.WIND_HEIGHTS_M is constants.WIND_HEIGHTS_M
    assert physical_layers.WIND_HEIGHTS_M is constants.WIND_HEIGHTS_M
    assert wind.GWA_HEIGHTS_M is constants.WIND_HEIGHTS_M
