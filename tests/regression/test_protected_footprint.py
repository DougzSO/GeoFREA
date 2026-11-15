"""Frozen protected-area footprint of PRT and BRA (the regression that left with the legacy baseline, 2026-10-06).

The counts of pixels (share above 0 and at least one half) are compared exactly with
`tests/fixtures/protected_footprint/footprint.json`, the area with a relative tolerance of 1e-9. The test reads the WDPA
file and the aligned grid of the real data directory (the key `GEOFREA_DATA_DIR` of `.env`) and is skipped when either
is absent, as in CI. If the data file changed (its sha256 differs from the fixture) the test fails on that first, because
the counts then say nothing about the code. Refreeze only with Douglas's authorization, with the commands of the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.regression.protected_footprint import footprint, grid_file, sha256, wdpa_file

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "protected_footprint" / "footprint.json"


def _real_data_dir() -> Path | None:
    """The real data directory, read from the key `GEOFREA_DATA_DIR` of `.env` (conftest points the variable at a temporary directory)."""
    env = REPO / ".env"
    if not env.is_file():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            value = line.split("=", 1)[1].strip().strip('"')
            return Path(value) if value else None
    return None


def _needs(iso: str) -> bool:
    root = _real_data_dir()
    return root is not None and wdpa_file(root, iso).is_file() and grid_file(root, iso).is_file()


@pytest.mark.regression
@pytest.mark.requires_data
@pytest.mark.parametrize("iso", ["PRT", "BRA"])
def test_the_protected_area_footprint_matches_the_frozen_counts(iso):
    if not _needs(iso):
        pytest.skip(f"the WDPA file or the aligned grid of {iso} is not in the real data directory")
    root = _real_data_dir()
    frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))["countries"][iso]
    assert sha256(wdpa_file(root, iso)) == frozen["wdpa_sha256"], "the WDPA file is not the one that was frozen"
    assert sha256(grid_file(root, iso)) == frozen["grid_sha256"], "the aligned grid is not the one that was frozen"
    got = footprint(root, iso)
    for level, want in frozen["footprint"].items():
        assert got[level]["pixels_above_0"] == want["pixels_above_0"], level
        assert got[level]["pixels_at_least_half"] == want["pixels_at_least_half"], level
        assert got[level]["area_km2"] == pytest.approx(want["area_km2"], rel=1e-9), level
