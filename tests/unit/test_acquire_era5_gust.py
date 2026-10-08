"""Unit tests for scripts/acquire_era5_gust.py's retry/timeout policy (OQ-038, COMMAND F4-5).

No real CDS request anywhere in this file -- every CDS interaction is a
mock/fake object. Timeout constants are monkeypatched to small values
so tests run in well under a second while exercising the same
timeout/retry *logic* the real (90 min / 30 min / 2 attempts) policy
uses; the literal minute values are not what these tests check.

`scripts/` is not an importable package (no `src/` entry), so the
module under test is loaded directly from its file path.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "acquire_era5_gust.py"
_spec = importlib.util.spec_from_file_location("acquire_era5_gust", _SCRIPT_PATH)
acquire_era5_gust = importlib.util.module_from_spec(_spec)
sys.modules["acquire_era5_gust"] = acquire_era5_gust
_spec.loader.exec_module(acquire_era5_gust)


# --- (a) a request near the new timeout is not interrupted prematurely ---


@pytest.mark.unit
def test_run_with_timeout_does_not_interrupt_a_call_that_finishes_just_under_the_limit():
    """Scaled-down equivalent of "a 55-minute request is not killed": a call
    that takes 90% of the allotted timeout must still return normally."""

    def slow_but_within_budget():
        time.sleep(0.05)
        return "done"

    result = acquire_era5_gust._run_with_timeout(
        slow_but_within_budget, timeout_s=0.2, stall_message="should not fire"
    )
    assert result == "done"


@pytest.mark.unit
def test_run_with_timeout_raises_timeout_error_when_genuinely_stalled():
    def never_returns_in_time():
        time.sleep(1.0)
        return "too late"

    with pytest.raises(TimeoutError, match="genuinely stalled"):
        acquire_era5_gust._run_with_timeout(
            never_returns_in_time, timeout_s=0.05, stall_message="genuinely stalled"
        )


# --- (b) a download that reaches 100% is not killed by queue-phase timeout ---


@pytest.mark.unit
def test_queue_and_download_timeouts_are_independent(tmp_path, monkeypatch):
    """The exact F4-2 false-positive (D-F1-018): a slow queue phase must not
    steal time from the download phase's own budget.

    Queue phase takes 90% of QUEUE_TIMEOUT_S; download phase then takes
    90% of DOWNLOAD_TIMEOUT_S. Combined, this exceeds either timeout
    alone (the old, single shared timeout would have killed this), but
    under the separated policy both phases fit their own budget.
    """
    monkeypatch.setattr(acquire_era5_gust, "QUEUE_TIMEOUT_S", 0.1)
    monkeypatch.setattr(acquire_era5_gust, "DOWNLOAD_TIMEOUT_S", 0.1)

    downloaded_to = {}

    class FakeResult:
        def download(self, target):
            time.sleep(0.09)  # 90% of DOWNLOAD_TIMEOUT_S
            Path(target).write_bytes(b"fake netcdf bytes")
            downloaded_to["path"] = target
            return target

    class FakeClient:
        def retrieve(self, name, request, target):
            assert target is None  # poll-only phase, no download here
            time.sleep(0.09)  # 90% of QUEUE_TIMEOUT_S
            return FakeResult()

    request = {"variable": "fg10"}
    result = acquire_era5_gust._run_with_timeout(
        lambda: acquire_era5_gust._submit_and_wait(FakeClient(), request),
        acquire_era5_gust.QUEUE_TIMEOUT_S,
        "queue timeout fired -- should not have",
    )
    tmp_download = tmp_path / "year.part.download"
    acquire_era5_gust._run_with_timeout(
        lambda: result.download(str(tmp_download)),
        acquire_era5_gust.DOWNLOAD_TIMEOUT_S,
        "download timeout fired -- should not have",
    )

    assert downloaded_to["path"] == str(tmp_download)
    assert tmp_download.read_bytes() == b"fake netcdf bytes"


@pytest.mark.unit
def test_download_year_once_completes_when_queue_is_slow_but_download_is_fast(
    tmp_path, monkeypatch
):
    """Full `_download_year_once()` path: a queue phase that alone would have
    exhausted a combined old-style timeout must not prevent a fast,
    complete download afterward."""
    monkeypatch.setattr(acquire_era5_gust, "QUEUE_TIMEOUT_S", 1.0)
    monkeypatch.setattr(acquire_era5_gust, "DOWNLOAD_TIMEOUT_S", 5.0)

    class FakeResult:
        def download(self, target):
            _write_valid_netcdf(Path(target))  # real NetCDF I/O, not instant
            return target

    class FakeClient:
        def retrieve(self, name, request, target):
            time.sleep(0.5)  # well under QUEUE_TIMEOUT_S alone
            return FakeResult()

    job = acquire_era5_gust.era5.Era5Job(country="PRT")
    path = acquire_era5_gust._download_year_once(
        FakeClient(), job, 2010, bbox=[43.0, -9.6, 36.8, -6.0], out_dir=tmp_path
    )
    assert path.exists()
    assert path.name == "PRT_fg10_hourly_bbox_2010.nc"


def _write_valid_netcdf(path: Path) -> None:
    """Write a minimal real NetCDF file `validate_downloaded_netcdf()` accepts."""
    import numpy as np
    import xarray as xr

    ds = xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), np.zeros((1, 2, 2)))},
        coords={
            "valid_time": np.array(["2010-01-01"], dtype="datetime64[ns]"),
            "latitude": [0.0, 1.0],
            "longitude": [0.0, 1.0],
        },
    )
    ds.to_netcdf(path)


# --- (c) retry after real failure follows the defined policy, no hang ---


@pytest.mark.unit
def test_download_year_with_retries_succeeds_on_second_attempt(monkeypatch):
    monkeypatch.setattr(acquire_era5_gust, "RETRY_BACKOFF_S", 0)  # no real wait in tests
    calls = {"n": 0}

    def flaky_then_ok(client, job, year, bbox, out_dir):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("stalled in CDS queue/processing: no result after 90s")
        return Path("fake_success.nc")

    monkeypatch.setattr(acquire_era5_gust, "_download_year_once", flaky_then_ok)

    result = acquire_era5_gust._download_year_with_retries(
        client=object(),
        job=acquire_era5_gust.era5.Era5Job(country="XXX"),
        year=2010,
        bbox=[0, 0, 0, 0],
        out_dir=Path("."),
    )
    assert result == Path("fake_success.nc")
    assert calls["n"] == acquire_era5_gust.MAX_ATTEMPTS_PER_YEAR


@pytest.mark.unit
def test_download_year_with_retries_gives_up_after_max_attempts_without_hanging(monkeypatch):
    monkeypatch.setattr(acquire_era5_gust, "RETRY_BACKOFF_S", 0)
    calls = {"n": 0}

    def always_stalls(client, job, year, bbox, out_dir):
        calls["n"] += 1
        raise TimeoutError("stalled in CDS queue/processing: no result after 90s")

    monkeypatch.setattr(acquire_era5_gust, "_download_year_once", always_stalls)

    with pytest.raises(TimeoutError):
        acquire_era5_gust._download_year_with_retries(
            client=object(),
            job=acquire_era5_gust.era5.Era5Job(country="XXX"),
            year=1996,
            bbox=[0, 0, 0, 0],
            out_dir=Path("."),
        )
    # Exactly MAX_ATTEMPTS_PER_YEAR attempts -- proves it gives up rather
    # than retrying indefinitely and hanging the sequential run.
    assert calls["n"] == acquire_era5_gust.MAX_ATTEMPTS_PER_YEAR


@pytest.mark.unit
def test_one_failed_year_does_not_abort_the_rest_of_the_country(monkeypatch):
    """The OQ-038 loop-continuation fix: a year that exhausts retries must
    not stop the remaining years of the same country from being
    attempted in the same run (the old code's `break` did)."""
    monkeypatch.setattr(acquire_era5_gust, "RETRY_BACKOFF_S", 0)
    attempted_years = []

    def fail_only_1996(client, job, year, bbox, out_dir):
        attempted_years.append(year)
        if year == 1996:
            raise TimeoutError("stalled in CDS queue/processing: no result after 90s")
        return Path(f"fake_{year}.nc")

    monkeypatch.setattr(acquire_era5_gust, "_download_year_once", fail_only_1996)

    results = {}
    for year in (1995, 1996, 1997):
        try:
            results[year] = acquire_era5_gust._download_year_with_retries(
                client=object(),
                job=acquire_era5_gust.era5.Era5Job(country="XXX"),
                year=year,
                bbox=[0, 0, 0, 0],
                out_dir=Path("."),
            )
        except TimeoutError:
            results[year] = None

    assert results[1995] == Path("fake_1995.nc")
    assert results[1996] is None
    assert results[1997] == Path("fake_1997.nc")  # reached despite 1996's failure
    # 1996 was retried MAX_ATTEMPTS_PER_YEAR times, 1995/1997 succeeded first try
    assert attempted_years.count(1996) == acquire_era5_gust.MAX_ATTEMPTS_PER_YEAR
    assert attempted_years.count(1995) == 1
    assert attempted_years.count(1997) == 1


# --- 502 Bad Gateway: confirm no extra handling is silently required ---


@pytest.mark.unit
def test_submit_and_wait_is_a_thin_passthrough_relying_on_client_own_retry():
    """`_submit_and_wait()` must not add its own HTTP-retry logic -- the
    502 self-recovery observed in F4-2 is the *client's* own retry
    (`Client.robust()` / `multiurl.robust()`), confirmed sufficient in
    that real run. This test only pins down that `_submit_and_wait()`
    stays a direct passthrough to `client.retrieve(..., target=None)`,
    so it does not accidentally suppress or duplicate that behavior."""
    calls = []

    class FakeClient:
        def retrieve(self, name, request, target):
            calls.append((name, request, target))
            return "the-result"

    out = acquire_era5_gust._submit_and_wait(FakeClient(), {"variable": "fg10"})
    assert out == "the-result"
    assert calls == [(acquire_era5_gust.era5.ERA5_DATASET, {"variable": "fg10"}, None)]


# --- COMMAND F4-6: request stuck in "accepted" forever, never returns ---


@pytest.mark.unit
def test_queue_phase_stuck_in_accepted_forever_is_interrupted_by_watchdog(monkeypatch):
    """Distinct from "demora mas eventualmente sai" (the existing slow-
    but-under-timeout tests): here the poll call never returns at all
    within the process's lifetime (simulating a request that never
    leaves "accepted"). QUEUE_TIMEOUT_S must still interrupt it -- the
    thread is abandoned (Python cannot kill a thread), not joined -- and
    control must return to the caller, not hang the process."""
    monkeypatch.setattr(acquire_era5_gust, "QUEUE_TIMEOUT_S", 0.1)

    class NeverRespondingClient:
        def retrieve(self, name, request, target):
            assert target is None
            # Simulates "accepted" with no state change for far longer
            # than QUEUE_TIMEOUT_S. Bounded (not a true infinite block):
            # concurrent.futures.ThreadPoolExecutor registers an atexit
            # hook that joins every worker thread at interpreter exit
            # regardless of `pool.shutdown(wait=False)` -- a genuinely
            # unbounded block here would hang the test process at
            # teardown even though `_run_with_timeout()` itself already
            # returned control correctly.
            time.sleep(2.0)
            return "unreachable"  # pragma: no cover -- watchdog fires first

    t_start = time.time()
    with pytest.raises(TimeoutError, match="no result after 0.1s"):
        acquire_era5_gust._run_with_timeout(
            lambda: acquire_era5_gust._submit_and_wait(NeverRespondingClient(), {}),
            acquire_era5_gust.QUEUE_TIMEOUT_S,
            f"stalled in CDS queue/processing: no result after {acquire_era5_gust.QUEUE_TIMEOUT_S}s",
        )
    elapsed = time.time() - t_start
    # The watchdog fired at ~QUEUE_TIMEOUT_S, not after waiting for the
    # (permanently blocked) thread to finish -- the call returns
    # promptly, proving the process is not hung by the stuck thread.
    assert elapsed < 2.0


@pytest.mark.unit
def test_download_year_with_retries_recovers_from_a_request_stuck_forever_in_accepted(
    monkeypatch, tmp_path
):
    """Same stuck-forever scenario, through the full retry path: attempt
    1 stalls in "accepted" past QUEUE_TIMEOUT_S, attempt 2 succeeds --
    the retry policy must engage exactly as it does for an ordinary
    (eventually-returning) stall, not treat "never returns" specially
    or hang."""
    monkeypatch.setattr(acquire_era5_gust, "QUEUE_TIMEOUT_S", 0.1)
    monkeypatch.setattr(acquire_era5_gust, "DOWNLOAD_TIMEOUT_S", 5.0)
    monkeypatch.setattr(acquire_era5_gust, "RETRY_BACKOFF_S", 0)

    attempts = {"n": 0}

    class FlakyThenOkClient:
        def retrieve(self, name, request, target):
            attempts["n"] += 1
            if attempts["n"] == 1:
                time.sleep(2.0)  # bounded stand-in for "never returns", see note above
                return "unreachable"  # pragma: no cover -- watchdog fires first
            time.sleep(0.01)
            return _FakeResultForStuckTest()

    class _FakeResultForStuckTest:
        def download(self, target):
            _write_valid_netcdf(Path(target))
            return target

    job = acquire_era5_gust.era5.Era5Job(country="PRT")
    path = acquire_era5_gust._download_year_with_retries(
        FlakyThenOkClient(), job, 2011, bbox=[43.0, -9.6, 36.8, -6.0], out_dir=tmp_path
    )
    assert path.exists()
    assert attempts["n"] == 2


# --- Registry: permanent-failure status is explicit and distinct ---


@pytest.mark.unit
def test_registry_permanently_failed_years_is_distinct_from_success_and_not_attempted():
    from geofrea.data_acquisition.era5_registry import Era5RegistryEntry

    entry = Era5RegistryEntry(
        country_code="BRA",
        status="missing",
        missing_reason="1 year(s) permanently failed after retries: ['1996']",
        year_sha256={"1995": "a" * 64},
        permanently_failed_years={"1996": "TimeoutError: stalled in CDS queue/processing"},
    )
    # 1995: success. 1996: permanent failure. 1997: not attempted (absent from both).
    assert "1995" in entry.year_sha256 and "1995" not in entry.permanently_failed_years
    assert "1996" in entry.permanently_failed_years and "1996" not in entry.year_sha256
    assert "1997" not in entry.year_sha256 and "1997" not in entry.permanently_failed_years


@pytest.mark.unit
def test_registry_round_trips_permanently_failed_years_through_json(tmp_path):
    from geofrea.data_acquisition.era5_registry import Era5Registry, Era5RegistryEntry

    registry = Era5Registry(
        entries={
            "era5/BRA/fg10": Era5RegistryEntry(
                country_code="BRA",
                status="missing",
                missing_reason="1 year(s) permanently failed after retries: ['1996']",
                year_sha256={"1995": "a" * 64},
                permanently_failed_years={"1996": "TimeoutError: stalled"},
            )
        }
    )
    path = tmp_path / "era5_registry.json"
    registry.save(path)
    reloaded = Era5Registry.load(path)
    assert reloaded.entries["era5/BRA/fg10"].permanently_failed_years == {
        "1996": "TimeoutError: stalled"
    }


@pytest.mark.unit
def test_registry_loads_old_shape_without_permanently_failed_years_field(tmp_path):
    """Forward-compatibility: a registry written before this field existed
    (no `permanently_failed_years` key at all) must still load, per the
    same pattern D-core-016 already uses for other additive fields."""
    import json

    from geofrea.data_acquisition.era5_registry import Era5Registry

    path = tmp_path / "era5_registry.json"
    path.write_text(
        json.dumps(
            {
                "entries": {
                    "era5/PRT/fg10": {
                        "country_code": "PRT",
                        "variable": "fg10",
                        "status": "missing",
                        "missing_reason": "in progress: 17/20 years downloaded",
                        "year_sha256": {"1995": "a" * 64},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    reloaded = Era5Registry.load(path)
    assert reloaded.entries["era5/PRT/fg10"].permanently_failed_years == {}
