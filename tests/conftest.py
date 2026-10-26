"""Pytest configuration and fixtures for GeoFREA tests."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up environment variables for testing (session scope).

    Ensures test data directories exist and are properly configured.
    """
    test_tmp_base = Path(tempfile.gettempdir()) / "geofrea_test_data"
    test_tmp_base.mkdir(exist_ok=True)

    # Create required directories if they don't exist
    for subdir in ["data", "geoworld", "craei"]:
        (test_tmp_base / subdir).mkdir(exist_ok=True)

    # Set defaults if not already set
    os.environ.setdefault("GEOFREA_DATA_DIR", str(test_tmp_base / "data"))
    os.environ.setdefault("GEOWORLD_BASELINE_DIR", str(test_tmp_base / "geoworld"))
    os.environ.setdefault("CRAEI_BASELINE_DIR", str(test_tmp_base / "craei"))

    yield


@pytest.fixture(autouse=True)
def mock_geofrea_data_dir(tmp_path):
    """Mock GEOFREA_DATA_DIR to tmp_path for each test.

    This ensures test artifacts are created under a known root for the
    StoredPath resolution to work correctly.
    """
    with mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": str(tmp_path)}):
        yield tmp_path


@pytest.fixture(autouse=True, scope="session")
def synthetic_country_names():
    """The invented countries of the map tests (ISO codes that are not countries) get a name, as a title needs one."""
    from geofrea.viz import mapstyle

    added = {"XXX": "Examplia", "ZZZ": "Examplia"}
    for names in mapstyle.COUNTRY_NAMES.values():
        names.update(added)
    yield
    for names in mapstyle.COUNTRY_NAMES.values():
        for code in added:
            names.pop(code, None)
