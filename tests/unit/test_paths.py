"""Tests for geofrea.core.paths module.

Tests path resolution, read-only guard, and StoredPath serialization.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from geofrea.core.paths import (
    MissingPathEnvironmentError,
    StoredPath,
    to_stored_path,
)


class TestStoredPath:
    """StoredPath serialization and resolution."""

    def test_resolve_data_root(self):
        """StoredPath with root='data' resolves to GEOFREA_DATA_DIR."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": tmpdir}),
        ):
            sp = StoredPath(root="data", rel="outputs/BRA/manifest.json")
            resolved = sp.resolve()
            assert resolved == Path(tmpdir) / "outputs" / "BRA" / "manifest.json"

    def test_the_shared_raw_root_no_longer_exists(self):
        """COMMAND 37: nothing is read outside GEOFREA_DATA_DIR, so a stored path cannot name the shared raw directory."""
        with pytest.raises(ValueError):
            StoredPath(root="shared_raw", rel="gadm/BRA/gadm41_BRA_0.shp")

    def test_the_legacy_baseline_root_no_longer_exists(self):
        """COMMAND 37: the legacy baseline moved to the archive and is not a root."""
        with pytest.raises(ValueError):
            StoredPath(root="legacy_baseline", rel="BRA/results/abatement.tif")

    def test_resolve_missing_env_raises(self):
        """StoredPath.resolve() raises if required env var is not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            sp = StoredPath(root="data", rel="test.txt")
            with pytest.raises(MissingPathEnvironmentError, match="GEOFREA_DATA_DIR"):
                sp.resolve()

    def test_resolve_missing_env_error_points_at_env_example(self):
        """The missing-variable error names the variable and points at .env.example."""
        with mock.patch.dict(os.environ, {}, clear=True):
            sp = StoredPath(root="data", rel="test.txt")
            with pytest.raises(
                MissingPathEnvironmentError, match=r"GEOFREA_DATA_DIR.*\.env\.example"
            ):
                sp.resolve()

    def test_str_representation(self):
        """StoredPath.__str__() returns root:rel format."""
        sp = StoredPath(root="data", rel="outputs/BRA/test.json")
        assert str(sp) == "data:outputs/BRA/test.json"


class TestToStoredPath:
    """Conversion from absolute paths to StoredPath."""

    def test_convert_path_under_data_dir(self):
        """to_stored_path() detects paths under GEOFREA_DATA_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            test_file = data_dir / "outputs" / "BRA" / "test.json"
            test_file.parent.mkdir(parents=True)
            test_file.touch()

            with mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": str(data_dir)}):
                sp = to_stored_path(test_file)
                assert sp.root == "data"
                assert sp.rel == "outputs/BRA/test.json"

    def test_a_path_under_the_former_shared_raw_dir_is_not_convertible(self):
        """to_stored_path() has no root for GEOFREA_SHARED_RAW_DIR any more, even when the variable is still set."""
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as other:
            test_file = Path(other) / "gadm" / "BRA" / "file.shp"
            test_file.parent.mkdir(parents=True)
            test_file.touch()
            with (
                mock.patch.dict(
                    os.environ,
                    {"GEOFREA_DATA_DIR": str(Path(tmpdir)), "GEOFREA_SHARED_RAW_DIR": other},
                ),
                pytest.raises(ValueError, match="not under any known root"),
            ):
                to_stored_path(test_file)

    def test_convert_path_not_under_any_root_raises(self):
        """to_stored_path() raises if path is not under any known root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "orphan" / "file.txt"
            test_file.parent.mkdir(parents=True)
            test_file.touch()

            with (
                mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": str(Path(tmpdir) / "data")}),
                pytest.raises(ValueError, match="not under any known root"),
            ):
                to_stored_path(test_file)
