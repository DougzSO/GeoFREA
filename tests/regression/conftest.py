"""Shared fixtures and collection hooks for the regression test suite.

Regression tests compare GeoFREA outputs against the frozen legacy
baseline in outputs_baseline_fc7b43d/ (see docs/architecture/
baseline-manifest.md). That directory is gitignored and only present on
machines where it has been regenerated locally, so a clean clone or CI
checkout will not have it. Tests marked "regression" are skipped with an
informative message in that case, rather than failing with
FileNotFoundError.
"""

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
