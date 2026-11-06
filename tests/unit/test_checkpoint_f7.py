"""COMMAND 98, F7: an interruption in the evaluation, the sample-major pass or the PRIM bootstrap gives, after the restart, the continuous result.

The bootstrap draws every replicate from one generator, so each stored batch carries the state of the generator after it (Douglas, 2026-11-05: never a
seed per replicate, which would be another sample).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_robustness_evaluator import _samples, _world
from test_scenario_discovery import SETTINGS, _synthetic

from geofrea.core.checkpoint import digest_inputs
from geofrea.robustness_analysis import evaluator, futures, scenario_discovery
from geofrea.robustness_analysis.evaluator import evaluate
from geofrea.robustness_analysis.futures import MemberLabel, futures_pass
from geofrea.robustness_analysis.scenario_discovery import bootstrap, derive_seed

LABELS = [
    MemberLabel("m1", "GCM-A", "SSP1-2.6"),
    MemberLabel("m2", "GCM-A", "SSP3-7.0"),
    MemberLabel("m3", "GCM-B", "SSP1-2.6"),
]


class _PowerLoss(BaseException):  # like a Ctrl+C or a kill: not an Exception
    pass


def _fail_on_call(
    monkeypatch: pytest.MonkeyPatch, module, name: str, at_call: int | None
) -> list[int]:
    real = getattr(module, name)
    calls: list[int] = []

    def spy(*args, **kwargs):
        calls.append(len(calls) + 1)
        if at_call is not None and len(calls) == at_call:
            raise _PowerLoss
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, spy)
    return calls


# --- evaluate: the running totals are kept after each member ---------------------------------------------------------------------------------


def _world_and_samples():
    rng = np.random.default_rng(98)
    reference, worlds = _world(rng, n_cells=60, n_core=3)
    return reference, worlds, _samples(rng, 40)


def test_evaluate_resumes_after_an_interruption_to_the_identical_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, worlds, samples = _world_and_samples()
    continuous = evaluate(reference, worlds, samples, tau=500.0, block_cells=20)
    ck = tmp_path / "evaluate_ckpt"
    _fail_on_call(
        monkeypatch, evaluator, "_member_pass_two", 3
    )  # the reference and the first member are done
    with pytest.raises(_PowerLoss):
        evaluate(reference, worlds, samples, tau=500.0, block_cells=20, checkpoint_dir=ck)
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, evaluator, "_member_pass_two", None)
    resumed = evaluate(reference, worlds, samples, tau=500.0, block_cells=20, checkpoint_dir=ck)
    assert (
        len(calls) == 2
    )  # members 2 and 3 only (4 passes in all: the reference and three members)
    assert digest_inputs(resumed) == digest_inputs(continuous)


def test_evaluate_with_two_interruptions_in_a_row_gives_the_identical_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, worlds, samples = _world_and_samples()
    continuous = evaluate(reference, worlds, samples, tau=None, block_cells=20)
    ck = tmp_path / "evaluate_ckpt"
    for at in (2, 2):
        _fail_on_call(monkeypatch, evaluator, "_member_pass_two", at)
        with pytest.raises(_PowerLoss):
            evaluate(reference, worlds, samples, tau=None, block_cells=20, checkpoint_dir=ck)
        monkeypatch.undo()
    resumed = evaluate(reference, worlds, samples, tau=None, block_cells=20, checkpoint_dir=ck)
    assert digest_inputs(resumed) == digest_inputs(continuous)


def test_evaluate_does_not_take_totals_of_other_draws(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    reference, worlds, samples = _world_and_samples()
    ck = tmp_path / "evaluate_ckpt"
    _fail_on_call(monkeypatch, evaluator, "_member_pass_two", 3)
    with pytest.raises(_PowerLoss):
        evaluate(reference, worlds, samples, tau=None, block_cells=20, checkpoint_dir=ck)
    monkeypatch.undo()
    other = _samples(
        np.random.default_rng(1), 40
    )  # other draws: the stored totals are not this computation's
    calls = _fail_on_call(monkeypatch, evaluator, "_member_pass_two", None)
    with caplog.at_level(logging.WARNING):
        evaluate(reference, worlds, other, tau=None, block_cells=20, checkpoint_dir=ck)
    assert len(calls) == 4 and "another computation" in caplog.text


# --- futures_pass: a batch of draws is the unit ---------------------------------------------------------------------------------------------


def _futures_inputs():
    from geofrea.lcoe_modeling.kernel import lcoe_block

    rng = np.random.default_rng(5)
    reference, worlds = _world(rng, n_cells=40, n_core=3)
    samples = _samples(rng, 30)
    nominal = lcoe_block(reference.cells, samples.take(slice(0, 1)))[:, 0]
    top = np.zeros(40, dtype=bool)
    top[np.argsort(nominal, kind="stable")[:8]] = True
    return worlds, samples, top, 8


def test_the_sample_major_pass_resumes_after_an_interruption_to_the_identical_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worlds, samples, top, k = _futures_inputs()
    kwargs = {"max_batch_gb": 1e-7}  # one draw a batch: thirty-one batches
    continuous = futures_pass(worlds, LABELS, samples, top, k, **kwargs)
    ck = tmp_path / "futures_ckpt"
    _fail_on_call(
        monkeypatch, futures, "lcoe_block", 3 * 12 + 1
    )  # twelve batches are done; the thirteenth is stopped on its first member
    with pytest.raises(_PowerLoss):
        futures_pass(worlds, LABELS, samples, top, k, checkpoint_dir=ck, **kwargs)
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, futures, "lcoe_block", None)
    resumed = futures_pass(worlds, LABELS, samples, top, k, checkpoint_dir=ck, **kwargs)
    assert len(calls) == 3 * (31 - 12)  # the batches that were stored are not evaluated again
    assert digest_inputs(resumed) == digest_inputs(continuous)


# --- the bootstrap: the state of the generator is stored with each batch ------------------------------------------------------------------------


def _bootstrap(checkpoint_dir=None, replicates=30):
    x, shares = _synthetic(600)
    return bootstrap(
        x,
        shares,
        SETTINGS,
        replicates=replicates,
        seed=derive_seed(42),
        percentiles=(5.0, 95.0),
        checkpoint_dir=checkpoint_dir,
    )


def test_the_bootstrap_resumes_in_the_middle_to_the_identical_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    continuous = _bootstrap()
    ck = tmp_path / "bootstrap_ckpt"
    _fail_on_call(
        monkeypatch, scenario_discovery, "discover", 25
    )  # two batches of ten replicates are stored, the third is cut at its fifth
    with pytest.raises(_PowerLoss):
        _bootstrap(ck)
    monkeypatch.undo()
    assert len(list(ck.glob("batch_*.npz"))) == 2
    calls = _fail_on_call(monkeypatch, scenario_discovery, "discover", None)
    resumed = _bootstrap(ck)
    assert len(calls) == 10  # only the replicates of the third batch are searched again
    pd.testing.assert_frame_equal(resumed, continuous)


def test_the_bootstrap_with_two_interruptions_in_a_row_gives_the_identical_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    continuous = _bootstrap()
    ck = tmp_path / "bootstrap_ckpt"
    for at in (13, 8):  # the first run stores one batch, the second two more
        _fail_on_call(monkeypatch, scenario_discovery, "discover", at)
        with pytest.raises(_PowerLoss):
            _bootstrap(ck)
        monkeypatch.undo()
    pd.testing.assert_frame_equal(_bootstrap(ck), continuous)


def test_the_stored_state_of_the_generator_is_what_makes_the_resumed_table_equal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the restored state the later replicates would be another sample: the table would differ (the check of the check)."""
    continuous = _bootstrap()
    ck = tmp_path / "bootstrap_ckpt"
    _fail_on_call(monkeypatch, scenario_discovery, "discover", 25)
    with pytest.raises(_PowerLoss):
        _bootstrap(ck)
    monkeypatch.undo()

    real = np.random.default_rng

    def fresh_generator(seed):
        generator = real(seed)
        original = type(generator.bit_generator).state

        class Ignoring:  # a generator whose state cannot be restored
            def __getattr__(self, name):
                return getattr(generator, name)

        wrapper = Ignoring()
        wrapper.bit_generator = type(
            "B", (), {"state": property(lambda s: generator.bit_generator.state, lambda s, v: None)}
        )()
        del original
        return wrapper

    monkeypatch.setattr(scenario_discovery.np.random, "default_rng", fresh_generator)
    broken = _bootstrap(ck)
    assert not broken.equals(continuous)


def test_a_bootstrap_checkpoint_of_another_seed_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ck = tmp_path / "bootstrap_ckpt"
    _fail_on_call(monkeypatch, scenario_discovery, "discover", 15)
    with pytest.raises(_PowerLoss):
        _bootstrap(ck)
    monkeypatch.undo()
    x, shares = _synthetic(600)
    calls = _fail_on_call(monkeypatch, scenario_discovery, "discover", None)
    with caplog.at_level(logging.WARNING):
        bootstrap(
            x,
            shares,
            SETTINGS,
            replicates=30,
            seed=derive_seed(43),
            percentiles=(5.0, 95.0),
            checkpoint_dir=ck,
        )
    assert len(calls) == 30 and "another computation" in caplog.text
