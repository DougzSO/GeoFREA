"""The resumable ERA5 downloader (COMMAND 63): on start it reconciles the state file with the CDS and the disk and sends only the years that have
neither a live job nor a file; a job still accepted or running is never sent again."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def queue():
    spec = importlib.util.spec_from_file_location(
        "era5_ext_queue", REPO_ROOT / "scripts" / "era5_ext_queue.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


YEARS = list(range(1996, 2015))

# the state file as the first run left it: two jobs queued, nothing else
SYNTHETIC = {
    "cancelled": {"old-job": {"status_before": "accepted", "at": "2026-10-21 02:33:49"}},
    "rects": {
        "box": {
            "part": [73.0, 20.9, 98.1, 36.2],
            "area": [36.5, 72.8, 20.6, 98.4],
            "jobs": {
                "aff31dcf": {
                    "years": [1996, 1997],
                    "status": "accepted",
                    "submitted": "2026-10-21T02:33:50+00:00",
                    "started": None,
                    "finished": None,
                },
                "1ce0a738": {
                    "years": [1998, 1999],
                    "status": "accepted",
                    "submitted": "2026-10-21T02:34:01+00:00",
                    "started": None,
                    "finished": None,
                },
            },
        }
    },
}


def _state(tmp_path):
    path = tmp_path / "IND_box_jobs.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def _chunks(queue, state, on_disk=(), per_request=2):
    return queue.pending_chunks(
        state["rects"]["box"], YEARS, lambda y: y in set(on_disk), per_request
    )


def test_only_the_years_without_a_job_or_a_file_are_sent(queue, tmp_path):
    state = _state(tmp_path)
    chunks = _chunks(queue, state)
    assert chunks[0] == [2000, 2001] and chunks[-1] == [2014]
    assert [y for c in chunks for y in c] == list(
        range(2000, 2015)
    )  # 1996-1999 are held by the two queued jobs
    assert all(len(c) <= 2 for c in chunks)


def test_a_year_on_disk_is_not_asked_again_and_a_gap_splits_a_request(queue, tmp_path):
    state = _state(tmp_path)
    chunks = _chunks(queue, state, on_disk={2001, 2005})
    flat = [y for c in chunks for y in c]
    assert 2001 not in flat and 2005 not in flat
    assert [2000] in chunks and [2004] in chunks and [2006, 2007] in chunks


def test_a_job_that_is_accepted_or_running_is_never_sent_again(queue, tmp_path):
    state = _state(tmp_path)
    state["rects"]["box"]["jobs"]["1ce0a738"]["status"] = "running"
    flat = [y for c in _chunks(queue, state) for y in c]
    assert not set(flat) & {1996, 1997, 1998, 1999}


def test_a_rejected_or_lost_job_gives_its_years_back(queue, tmp_path):
    state = _state(tmp_path)
    state["rects"]["box"]["jobs"]["aff31dcf"]["status"] = "rejected"
    state["rects"]["box"]["jobs"]["1ce0a738"]["status"] = "lost"
    flat = [y for c in _chunks(queue, state) for y in c]
    assert flat[:4] == [1996, 1997, 1998, 1999]


def test_a_collected_job_holds_its_years_only_while_the_files_exist(queue, tmp_path):
    state = _state(tmp_path)
    state["rects"]["box"]["jobs"]["aff31dcf"]["status"] = "collected"
    with_files = [y for c in _chunks(queue, state, on_disk={1996, 1997}) for y in c]
    assert 1996 not in with_files and 1997 not in with_files
    without_files = [y for c in _chunks(queue, state) for y in c]
    assert without_files[:2] == [1996, 1997]  # the files were deleted: asked again


def test_reconcile_reads_the_status_and_times_from_the_cds(queue, tmp_path):
    state = _state(tmp_path)
    answers = {
        "aff31dcf": SimpleNamespace(
            status="successful",
            started_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
            finished_at=datetime(2026, 10, 21, 9, 20, tzinfo=UTC),
        ),
        "1ce0a738": SimpleNamespace(status="accepted", started_at=None, finished_at=None),
    }
    changed = queue.reconcile(state, answers.__getitem__)
    jobs = state["rects"]["box"]["jobs"]
    assert changed["successful"] == [("box", "aff31dcf")]
    assert jobs["aff31dcf"]["started"].startswith("2026-10-21T09:00")
    assert jobs["aff31dcf"]["finished"].startswith("2026-10-21T09:20")
    assert jobs["1ce0a738"]["status"] == "accepted" and jobs["1ce0a738"]["started"] is None


def test_reconcile_marks_a_job_the_cds_does_not_know_as_lost_and_skips_finished_ones(
    queue, tmp_path
):
    state = _state(tmp_path)
    state["rects"]["box"]["jobs"]["1ce0a738"]["status"] = "collected"

    def get_remote(jid):
        raise KeyError(jid)

    changed = queue.reconcile(state, get_remote)
    jobs = state["rects"]["box"]["jobs"]
    assert changed["lost"] == [("box", "aff31dcf")] and jobs["aff31dcf"]["status"] == "lost"
    assert jobs["1ce0a738"]["status"] == "collected"  # not asked about


def test_a_rejected_job_is_reported(queue, tmp_path):
    state = _state(tmp_path)
    answers = {
        "aff31dcf": SimpleNamespace(status="rejected", started_at=None, finished_at=None),
        "1ce0a738": SimpleNamespace(status="accepted", started_at=None, finished_at=None),
    }
    changed = queue.reconcile(state, answers.__getitem__)
    assert changed["rejected"] == [("box", "aff31dcf")]
