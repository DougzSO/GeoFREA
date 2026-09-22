"""Tests for main.py's startup .env loading (load_dotenv(..., override=False)).

Exercises the mechanism directly against a synthetic .env file rather
than the real repository-root .env, so these tests don't depend on
Douglas's local machine layout.
"""

import os
from unittest import mock

import pytest
from dotenv import load_dotenv


@pytest.mark.unit
@mock.patch.dict(os.environ, {}, clear=True)
def test_no_environment_run_resolves_paths_from_env_file(tmp_path):
    """With nothing in the process environment, every value comes from .env."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEOFREA_SHARED_RAW_DIR=/fake/shared_raw\n"
        "GEOFREA_DATA_DIR=/fake/data\n",
        encoding="utf-8",
    )

    load_dotenv(env_file, override=False)

    assert os.environ["GEOFREA_SHARED_RAW_DIR"] == "/fake/shared_raw"
    assert os.environ["GEOFREA_DATA_DIR"] == "/fake/data"


@pytest.mark.unit
@mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": "/real/data"}, clear=True)
def test_variable_already_set_in_environment_wins_over_env_file(tmp_path):
    """A variable already set in the process environment is not overridden by .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("GEOFREA_DATA_DIR=/fake/data\n", encoding="utf-8")

    load_dotenv(env_file, override=False)

    assert os.environ["GEOFREA_DATA_DIR"] == "/real/data"
