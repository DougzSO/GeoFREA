"""The definition of `rx5day_mm` in `hazard_indicators` (COMMAND 177, item 1d; DEC-093, M-F4-05).

The key carries the Rx5day index of the ETCCDI: the annual maximum of the precipitation accumulated in 5 consecutive days, in mm (Zhang et al., 2011).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from geofrea.core.config_loader import load_experiments
from geofrea.core.config_schemas import HazardIndicators

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"


@pytest.mark.unit
def test_the_experiments_file_defines_rx5day_mm_as_the_etccdi_index():
    indicator = load_experiments(EXPERIMENTS).hazard_indicators.rx5day_mm
    assert indicator.window_days == 5
    assert indicator.unit == "mm"
    assert indicator.tier == 1
    assert "Zhang" in indicator.source and "DEC-093" in indicator.source


@pytest.mark.unit
def test_the_model_refuses_a_window_that_is_not_a_positive_number_of_days():
    base = load_experiments(EXPERIMENTS).hazard_indicators.model_dump()
    for bad in (0, -5):
        base["rx5day_mm"]["window_days"] = bad
        with pytest.raises(ValidationError):
            HazardIndicators.model_validate(base)


@pytest.mark.unit
def test_the_model_refuses_a_definition_without_rx5day_mm():
    base = load_experiments(EXPERIMENTS).hazard_indicators.model_dump()
    del base["rx5day_mm"]
    with pytest.raises(ValidationError):
        HazardIndicators.model_validate(base)
