"""`core/run_logging.py` (COMMAND ADJ-7): the console and file handlers on the shared logger, the periodic progress lines and the run table."""

from __future__ import annotations

import logging

import pytest

from geofrea.core import run_logging
from geofrea.core.run_logging import PeriodicProgress, configure_logging, render_run_table

pytestmark = pytest.mark.unit


@pytest.fixture
def geofrea_logger():
    logger = logging.getLogger("geofrea")
    before = (list(logger.handlers), logger.level)
    yield logger
    for handler in list(logger.handlers):
        if handler not in before[0]:
            logger.removeHandler(handler)
            handler.close()
    logger.setLevel(before[1])


def _managed(logger: logging.Logger) -> list[logging.Handler]:
    return [h for h in logger.handlers if getattr(h, run_logging._MANAGED_ATTR, False)]


def test_the_file_gets_every_level_with_the_logger_name_and_the_console_only_info(
    tmp_path, geofrea_logger
):
    handler = configure_logging(tmp_path / "logs" / "run.log")
    child = logging.getLogger("geofrea.grid_alignment.alignment")
    child.debug("a detail")
    child.info("a phase line")
    handler.flush()
    text = (tmp_path / "logs" / "run.log").read_text(encoding="utf-8")
    assert "DEBUG geofrea.grid_alignment.alignment a detail" in text
    assert "INFO geofrea.grid_alignment.alignment a phase line" in text
    console = [h for h in _managed(geofrea_logger) if not isinstance(h, logging.FileHandler)]
    assert len(console) == 1 and console[0].level == logging.INFO
    assert handler.level == logging.DEBUG


def test_calling_it_again_replaces_its_handlers_and_leaves_the_others(tmp_path, geofrea_logger):
    foreign = logging.NullHandler()
    geofrea_logger.addHandler(foreign)
    first = configure_logging(tmp_path / "a.log")
    second = configure_logging(tmp_path / "b.log")
    managed = _managed(geofrea_logger)
    assert len(managed) == 2  # one console and one file, not four
    assert first not in geofrea_logger.handlers and second in geofrea_logger.handlers
    assert foreign in geofrea_logger.handlers
    geofrea_logger.removeHandler(foreign)


def test_the_logger_level_is_the_lowest_of_the_two_handlers(tmp_path, geofrea_logger):
    configure_logging(tmp_path / "run.log", console_level=logging.WARNING, file_level=logging.INFO)
    assert geofrea_logger.level == logging.INFO


def _counts(caplog) -> list[str]:
    """The `done/total` of every progress line."""
    return [
        r.getMessage().split(":")[1].split("done")[0].strip()
        for r in caplog.records
        if r.name == "test.progress"
    ]


def test_progress_logs_the_first_and_the_last_item_and_every_nth(caplog):
    caplog.set_level(logging.INFO, logger="test.progress")
    progress = PeriodicProgress(logging.getLogger("test.progress"), 25, "tiles", every=10)
    for _ in range(25):
        progress.step()
    assert _counts(caplog) == ["1/25", "10/25", "20/25", "25/25"]


def test_progress_logs_a_slow_item_by_time_and_an_empty_loop_logs_nothing(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="test.progress")
    # the clock: start, first item, second item, third item (35 s after the last line), fourth item
    clock = iter([0.0, 0.0, 5.0, 40.0, 41.0])
    monkeypatch.setattr(run_logging.time, "monotonic", lambda: next(clock, 99.0))
    progress = PeriodicProgress(
        logging.getLogger("test.progress"), 100, "slow", every=50, min_interval_s=30.0
    )
    for _ in range(4):
        progress.step()
    assert _counts(caplog) == ["1/100", "3/100"]
    caplog.clear()
    PeriodicProgress(logging.getLogger("test.progress"), 0, "none")
    assert _counts(caplog) == []


def test_every_below_one_is_taken_as_one(caplog):
    caplog.set_level(logging.INFO, logger="test.progress")
    progress = PeriodicProgress(logging.getLogger("test.progress"), 3, "x", every=0)
    for _ in range(3):
        progress.step()
    assert len(_counts(caplog)) == 3


def test_the_run_table_has_the_columns_the_peak_memory_or_a_dash_and_the_run_id():
    rows = [
        {
            "country": "PRT",
            "phase": "technical_potential",
            "status": "success",
            "elapsed_s": 14.04,
            "peak_rss_mb": 1523.6,
            "artifact_count": 9,
        },
        {
            "country": "PRT",
            "phase": "siting_layers",
            "status": "success",
            "elapsed_s": 3.0,
            "peak_rss_mb": None,
            "artifact_count": 13,
        },
        {  # a row built before the column existed
            "country": "IND",
            "phase": "overview",
            "status": "success",
            "elapsed_s": 1.0,
            "artifact_count": 1,
        },
    ]
    lines = render_run_table(rows, "abc123").splitlines()
    assert lines[0].split() == [
        "country",
        "phase",
        "status",
        "elapsed_s",
        "peak_rss_mb",
        "artifacts",
    ]
    assert set(lines[1].replace(" ", "")) == {"-"}
    assert lines[2].split() == ["PRT", "technical_potential", "success", "14.0", "1524", "9"]
    assert lines[3].split() == ["PRT", "siting_layers", "success", "3.0", "-", "13"]
    assert lines[4].split() == ["IND", "overview", "success", "1.0", "-", "1"]
    assert lines[-1] == "run_id: abc123"
    # the columns are aligned: every data line is padded to the same width except the last cell
    assert lines[2].index("success") == lines[3].index("success") == lines[4].index("success")


def test_an_empty_run_table_is_only_the_header_and_the_run_id():
    lines = render_run_table([], "r").splitlines()
    assert len(lines) == 3 and lines[-1] == "run_id: r"
