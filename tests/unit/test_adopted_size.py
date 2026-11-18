"""The sample size F6 and F7 run at is `sampler.adopted_size`, not `sampler.initial_size` (COMMAND 182; U-04, V182, D-F6-032)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from geofrea.core.config_loader import load_experiments
from geofrea.core.config_schemas import SamplerConfig

REPO = Path(__file__).resolve().parents[2]
EXPERIMENTS = REPO / "config" / "experiments.yaml"


@pytest.mark.unit
def test_the_adopted_size_is_the_largest_size_tested_and_the_doubling_still_starts_at_500():
    sampler = load_experiments(EXPERIMENTS).sampler
    assert sampler.adopted_size == 4000
    assert sampler.initial_size == 500
    assert sampler.initial_size <= sampler.adopted_size <= sampler.max_size_for_convergence


@pytest.mark.unit
def test_the_sampler_refuses_a_missing_or_non_positive_adopted_size():
    base = load_experiments(EXPERIMENTS).sampler.model_dump()
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            SamplerConfig.model_validate({**base, "adopted_size": bad})
    del base["adopted_size"]
    with pytest.raises(ValidationError):
        SamplerConfig.model_validate(base)


@pytest.mark.unit
def test_f6_and_f7_read_the_adopted_size_and_only_the_convergence_reads_the_initial_size():
    """No phase other than the convergence may size its draws from `initial_size`."""
    allowed = {"robustness_analysis/convergence.py"}
    for path in (REPO / "src" / "geofrea").rglob("*.py"):
        rel = path.relative_to(REPO / "src" / "geofrea").as_posix()
        if rel in allowed or rel == "core/config_schemas.py":
            continue
        assert not re.search(r"sampler\.initial_size", path.read_text(encoding="utf-8")), rel
    assert "sampler.initial_size" not in (REPO / "main.py").read_text(encoding="utf-8").replace("sampler=experiments.sampler", "")
