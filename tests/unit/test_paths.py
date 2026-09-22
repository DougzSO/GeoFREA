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
    ReadOnlyLocationError,
    StoredPath,
    ensure_writable,
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

    def test_resolve_shared_raw_root(self):
        """StoredPath with root='shared_raw' resolves to GEOFREA_SHARED_RAW_DIR."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.dict(os.environ, {"GEOFREA_SHARED_RAW_DIR": tmpdir}),
        ):
            sp = StoredPath(root="shared_raw", rel="gadm/BRA/gadm41_BRA_0.shp")
            resolved = sp.resolve()
            assert resolved == Path(tmpdir) / "gadm" / "BRA" / "gadm41_BRA_0.shp"

    def test_resolve_legacy_baseline_root(self):
        """StoredPath with root='legacy_baseline' resolves to GEOFREA_LEGACY_BASELINE_DIR."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.dict(os.environ, {"GEOFREA_LEGACY_BASELINE_DIR": tmpdir}),
        ):
            sp = StoredPath(root="legacy_baseline", rel="BRA/results/abatement.tif")
            resolved = sp.resolve()
            assert resolved == Path(tmpdir) / "BRA" / "results" / "abatement.tif"

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
            with pytest.raises(MissingPathEnvironmentError, match=r"GEOFREA_DATA_DIR.*\.env\.example"):
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

    def test_convert_path_under_shared_raw_dir(self):
        """to_stored_path() detects paths under GEOFREA_SHARED_RAW_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shared_raw = Path(tmpdir) / "shared_raw"
            shared_raw.mkdir()
            test_file = shared_raw / "gadm" / "BRA" / "file.shp"
            test_file.parent.mkdir(parents=True)
            test_file.touch()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": str(Path(tmpdir)), "GEOFREA_SHARED_RAW_DIR": str(shared_raw)},
            ):
                sp = to_stored_path(test_file)
                assert sp.root == "shared_raw"
                assert sp.rel == "gadm/BRA/file.shp"

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


class TestEnsureWritable:
    """ReadOnlyLocationError guard for writes."""

    def test_write_to_data_dir_is_allowed(self):
        """ensure_writable() allows writes under GEOFREA_DATA_DIR."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.dict(os.environ, {"GEOFREA_DATA_DIR": tmpdir}),
        ):
            path = Path(tmpdir) / "outputs" / "BRA" / "test.json"
            # Should not raise
            ensure_writable(path)

    def test_write_to_shared_raw_raises(self):
        """ensure_writable() raises for writes under GEOFREA_SHARED_RAW_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shared_raw = Path(tmpdir) / "shared_raw"
            shared_raw.mkdir()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": tmpdir, "GEOFREA_SHARED_RAW_DIR": str(shared_raw)},
            ):
                path = shared_raw / "gadm" / "file.shp"
                with pytest.raises(ReadOnlyLocationError, match="GEOFREA_SHARED_RAW_DIR"):
                    ensure_writable(path)

    def test_write_to_legacy_baseline_raises(self):
        """ensure_writable() raises for writes under GEOFREA_LEGACY_BASELINE_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy = Path(tmpdir) / "legacy"
            legacy.mkdir()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": tmpdir, "GEOFREA_LEGACY_BASELINE_DIR": str(legacy)},
            ):
                path = legacy / "BRA" / "results.tif"
                with pytest.raises(ReadOnlyLocationError, match="GEOFREA_LEGACY_BASELINE_DIR"):
                    ensure_writable(path)

    def test_write_to_craei_raises(self):
        """ensure_writable() raises for writes under CRAEI_BASELINE_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            craei = Path(tmpdir) / "craei"
            craei.mkdir()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": tmpdir, "CRAEI_BASELINE_DIR": str(craei)},
            ):
                path = craei / "climate_data.nc"
                with pytest.raises(ReadOnlyLocationError, match="CRAEI_BASELINE_DIR"):
                    ensure_writable(path)

    def test_write_to_gear_raises(self):
        """ensure_writable() raises for writes under GEAR_BASELINE_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gear = Path(tmpdir) / "gear"
            gear.mkdir()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": tmpdir, "GEAR_BASELINE_DIR": str(gear)},
            ):
                path = gear / "legacy_code.py"
                with pytest.raises(ReadOnlyLocationError, match="GEAR_BASELINE_DIR"):
                    ensure_writable(path)

    def test_write_to_geoworld_raises(self):
        """ensure_writable() raises for writes under GEOWORLD_BASELINE_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            geoworld = Path(tmpdir) / "geoworld"
            geoworld.mkdir()

            with mock.patch.dict(
                os.environ,
                {"GEOFREA_DATA_DIR": tmpdir, "GEOWORLD_BASELINE_DIR": str(geoworld)},
            ):
                path = geoworld / "framework.py"
                with pytest.raises(ReadOnlyLocationError, match="GEOWORLD_BASELINE_DIR"):
                    ensure_writable(path)
