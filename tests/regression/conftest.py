"""Shared fixtures and collection hooks for the regression test suite.

Regression tests compare GeoFREA outputs against the frozen legacy
baseline in outputs_baseline_fc7b43d/ (see docs/architecture/
baseline-manifest.md). That directory is gitignored and only present on
machines where it has been regenerated locally, so a clean clone or CI
checkout will not have it. Tests marked "regression" are skipped with an
informative message in that case, rather than failing with
FileNotFoundError.
"""

import os
from pathlib import Path

import pytest

BASELINE_DIRNAME = "outputs_baseline_fc7b43d"


def _baseline_root() -> Path:
    """Return the expected path of the local regression baseline.

    Returns:
        Path to <repo_root>/outputs_baseline_fc7b43d, whether or not it
        actually exists on disk.
    """
    return Path(__file__).resolve().parents[2] / BASELINE_DIRNAME


def _baseline_available() -> bool:
    """Check whether the local baseline has both PRT and BRA outputs.

    Returns:
        True if outputs_baseline_fc7b43d/PRT and .../BRA both exist.
    """
    root = _baseline_root()
    return (root / "PRT").is_dir() and (root / "BRA").is_dir()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip all "regression"-marked tests when the local baseline is absent.

    This is the single enforcement point for the skip behavior so
    individual regression tests don't need to check for the baseline
    themselves.
    """
    if _baseline_available():
        return
    skip_marker = pytest.mark.skip(
        reason=(
            f"{BASELINE_DIRNAME}/ not found at {_baseline_root()} — "
            "regression baseline is a local, gitignored artifact "
            "(see docs/architecture/baseline-manifest.md to regenerate it)."
        )
    )
    for item in items:
        if "regression" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture
def baseline_dir() -> Path:
    """Provide the local regression baseline root directory.

    Returns:
        Path to outputs_baseline_fc7b43d/, guaranteed to exist when this
        fixture is used, since pytest_collection_modifyitems already
        skips regression tests otherwise.
    """
    root = _baseline_root()
    if not _baseline_available():
        pytest.skip(f"{BASELINE_DIRNAME}/ not found at {root}")
    return root


def _in_ci() -> bool:
    """True when running under GitHub Actions (or any CI setting CI=true).

    GitHub Actions sets CI=true by default on every hosted/self-hosted
    runner; other CI providers commonly follow the same convention. Added
    2026-09-14 (see docs/DECISIONS.md same date, "regression fixtures
    storage") alongside the CI workflow that now provisions
    GEOWORLD_BASELINE_DIR from a packaged fixture: a skip is the right
    call for a developer who has not fetched the local baseline, but the
    exact same skip in CI silently hides a real misconfiguration (a
    missing/broken fixture download) behind a green build.
    """
    return os.environ.get("CI", "").strip().lower() == "true"


def _legacy_baseline_root() -> Path | None:
    """Locate the read-only legacy geoworld_framework checkout.

    GEOWORLD_BASELINE_DIR (from the developer's .env) is the canonical
    pointer; fall back to a sibling `geoworld_framework/` next to this
    repo. Returns None if neither resolves to a real directory.
    """
    env = os.environ.get("GEOWORLD_BASELINE_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[3] / "geoworld_framework")
    for c in candidates:
        if c.is_dir():
            return c
    return None


@pytest.fixture
def raw_data_root() -> Path:
    """The local raw-data database (GEOFREA_RAW_DATA_DIR from .env).

    Holds the GADM country boundaries (countries_borders/<Country>/) and
    the WDPA protected-areas shapefiles (protected_areas/<Country>/shp_*/)
    that the legacy compute_protected_areas consumed. Read-only; skips
    when the env var is unset or the directory is absent.
    """
    env = os.environ.get("GEOFREA_RAW_DATA_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[3] / "database" / "raw")
    for root in candidates:
        if root.is_dir():
            return root
    pytest.skip(
        "GEOFREA_RAW_DATA_DIR not set and no sibling database/raw/ found — "
        "cannot locate GADM/WDPA raw inputs."
    )
    raise AssertionError  # unreachable, for type-checkers


@pytest.fixture
def legacy_processed_root() -> Path:
    """The legacy `data/processed/` directory (frozen Fase 2a outputs).

    Per-country subdirs (PRT/, BRA/) hold the `<ISO>_<layer>_aligned.tif`
    rasters the frozen criteria_builder baseline was computed from —
    matching outputs_baseline_fc7b43d/<ISO> exactly. Used to
    regression-test suitability_criteria in isolation from GeoFREA's own
    grid_alignment (Bloqueio 3 decision (a), 2026-09-10). Read-only.

    Local dev: missing/unset is a pytest.skip() — an unfetched local
    fixture is not a reason to fail the whole suite, same convention as
    every other local-only fixture in this file (baseline_dir,
    raw_data_root). In CI (CI=true, see _in_ci()), the exact same
    condition is a pytest.fail() instead (added 2026-09-14, see
    docs/DECISIONS.md same date): CI's copy of this fixture comes from a
    packaged GitHub Release asset the workflow downloads itself, so
    "missing" there means the download/extraction was broken or
    misconfigured — a real red-build-worthy problem, not a developer's
    unfetched local state, and a bare skip would hide it behind green.
    """
    root = _legacy_baseline_root()
    if root is None:
        msg = (
            "GEOWORLD_BASELINE_DIR not set and no sibling geoworld_framework/ found — "
            "cannot locate the legacy aligned rasters."
        )
        if _in_ci():
            pytest.fail(msg)
        pytest.skip(msg)
    processed = root / "data" / "processed"
    if not processed.is_dir():
        msg = f"legacy aligned rasters not found at {processed}"
        if _in_ci():
            pytest.fail(msg)
        pytest.skip(msg)
    return processed
