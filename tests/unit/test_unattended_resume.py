"""COMMAND 98: `run_unattended.ps1` with no flags continues the round that an interruption left unfinished."""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "unattended_resume", REPO / "scripts" / "unattended_resume.py"
)
resume = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resume)

HEADER = "2026-11-05 16:12:06 round 20261105_161201: countries IND, BRA; worktree D:\\x (main @ 9dd49df5ec)\n"
STARTED = "2026-11-05 16:12:08 IND: start; available memory 2455 MB; manifest saved in D:\\x\n"
RUNNING = "2026-11-05 16:12:08 IND: running grid_alignment\n"


def _log(directory: Path, stamp: str, text: str, age_hours: float = 1.0) -> Path:
    path = directory / f"unattended_round_{stamp}.log"
    path.write_text(text, encoding="utf-8")
    when = (datetime.now().astimezone() - timedelta(hours=age_hours)).timestamp()
    os.utime(path, (when, when))
    return path


def test_an_unfinished_round_is_found_with_its_stamp_countries_and_phases(tmp_path: Path) -> None:
    _log(tmp_path, "20261105_161201", HEADER + STARTED + RUNNING)
    found = resume.find_incomplete_round(tmp_path)
    assert found["stamp"] == "20261105_161201"
    assert found["countries"] == ["IND", "BRA"]
    assert found["phases"] == "grid_alignment"


def test_a_round_with_its_summary_file_is_finished(tmp_path: Path) -> None:
    _log(tmp_path, "20261105_161201", HEADER + STARTED + RUNNING)
    (tmp_path / "unattended_round_20261105_161201.json").write_text("{}", encoding="utf-8")
    assert resume.find_incomplete_round(tmp_path) is None


def test_a_round_that_printed_round_finished_is_finished(tmp_path: Path) -> None:
    _log(
        tmp_path, "20261105_161201", HEADER + STARTED + RUNNING + "x ROUND FINISHED: IND IDENTICO\n"
    )
    assert resume.find_incomplete_round(tmp_path) is None


def test_a_round_that_never_started_a_country_is_not_continued(tmp_path: Path) -> None:
    _log(tmp_path, "20261105_161201", HEADER + "x available memory at the start: 2000 MB\n")
    assert resume.find_incomplete_round(tmp_path) is None


def test_only_the_newest_round_counts(tmp_path: Path) -> None:
    _log(
        tmp_path,
        "20261104_100000",
        HEADER.replace("20261105_161201", "20261104_100000") + STARTED,
        age_hours=30,
    )
    _log(tmp_path, "20261105_161201", HEADER + STARTED, age_hours=1)
    (tmp_path / "unattended_round_20261105_161201.json").write_text("{}", encoding="utf-8")
    assert (
        resume.find_incomplete_round(tmp_path) is None
    )  # the newest one finished; the older unfinished one is not resurrected


def test_a_round_left_for_days_is_not_continued_silently(tmp_path: Path) -> None:
    _log(
        tmp_path,
        "20261101_090000",
        HEADER.replace("20261105_161201", "20261101_090000") + STARTED,
        age_hours=24 * 5,
    )
    assert resume.find_incomplete_round(tmp_path, max_age_days=3) is None
    assert resume.find_incomplete_round(tmp_path, max_age_days=10) is not None


def test_a_round_without_a_running_line_has_no_phases_and_an_empty_directory_gives_nothing(
    tmp_path: Path,
) -> None:
    assert resume.find_incomplete_round(tmp_path) is None
    _log(tmp_path, "20261105_161201", HEADER + STARTED)
    assert resume.find_incomplete_round(tmp_path)["phases"] is None


def test_a_later_try_that_never_started_a_country_does_not_hide_the_interrupted_round(tmp_path: Path) -> None:
    _log(tmp_path, "20261105_161201", HEADER + STARTED + RUNNING, age_hours=3)
    failed_try = "x round 20261105_190000: countries IND; worktree here\nx another GeoFREA process is active\n"
    _log(tmp_path, "20261105_190000", failed_try, age_hours=1)
    assert resume.find_incomplete_round(tmp_path)["stamp"] == "20261105_161201"
