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
    """
    root = _legacy_baseline_root()
    if root is None:
        pytest.skip(
            "GEOWORLD_BASELINE_DIR not set and no sibling geoworld_framework/ found — "
            "cannot locate the legacy aligned rasters."
        )
    processed = root / "data" / "processed"
    if not processed.is_dir():
        pytest.skip(f"legacy aligned rasters not found at {processed}")
    return processed
