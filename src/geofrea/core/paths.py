r"""Central path resolution module for GeoFREA pipeline.

All path construction outside this module should use helpers from this module.
Environment variables define the data layout:
  - GEOFREA_DATA_DIR: external data directory (e.g. D:\Douglas\DOUTORADO\GeoFREA_data); the pipeline reads and writes nothing outside it
  - GEOWORLD_BASELINE_DIR: legacy geoworld framework (logic reference only)
  - CRAEI_BASELINE_DIR: CRAEI climate-risk framework (primary reference, copy and adapt)

Paths stored in manifests and Pydantic models use StoredPath (root + relative path)
to remain portable across environments. Absolute paths are resolved at read time only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from geofrea.core.scale import manifest_file_name, phase_directory_name


class MissingPathEnvironmentError(RuntimeError):
    """A required environment variable for path resolution is not set."""

    def __init__(self, var_name: str) -> None:
        super().__init__(
            f"Required environment variable '{var_name}' is not set. "
            f"Set it in the process environment or in a repository-root .env "
            f"file (see .env.example)."
        )
        self.var_name = var_name


class StoredPath(BaseModel):
    """A filesystem path for storage in manifests and Pydantic models.

    Uses a root identifier + relative path (posix-style) for portability
    across environments and installations. Resolved to absolute paths at
    read time only via StoredPath.resolve().

    Args:
        root: "data" (GEOFREA_DATA_DIR), the only root.
        rel: Relative path (posix-style, forward slashes only).
    """

    root: Literal["data"]
    rel: str

    def resolve(self) -> Path:
        """Resolve to an absolute filesystem path.

        Returns:
            Absolute Path using the environment variable for this root.

        Raises:
            MissingPathEnvironmentError: If the required env var is not set.
        """
        if self.root == "data":
            base = _ensure_env("GEOFREA_DATA_DIR")
        else:
            raise ValueError(f"Unknown root: {self.root}")
        return (Path(base) / self.rel).resolve()

    def __str__(self) -> str:
        """Return as a normalized string for display."""
        return f"{self.root}:{self.rel}"


def _ensure_env(var_name: str) -> str:
    """Read an environment variable, raising if not set.

    Args:
        var_name: Environment variable name.

    Returns:
        The environment variable value.

    Raises:
        MissingPathEnvironmentError: If var_name is not set.
    """
    value = os.environ.get(var_name)
    if value is None:
        raise MissingPathEnvironmentError(var_name)
    return value


def _ensure_data_env() -> Path:
    """Ensure GEOFREA_DATA_DIR is set and return it as a Path."""
    return Path(_ensure_env("GEOFREA_DATA_DIR"))


def data_root() -> Path:
    """Get GEOFREA_DATA_DIR itself (not one of its conventional subdirectories).

    Used by data_acquisition/local_layers.py to resolve a synthetic
    country's fixture root (`countries.yaml`'s `synthetic_fixture_root`,
    A-06/D-core-017) under the writable data directory, distinct from
    every other helper here which returns a fixed subdirectory
    (`outputs/`, `interim/`, ...) of it.

    Returns:
        GEOFREA_DATA_DIR as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env()


def fetched_raw(source: str, scope: str) -> Path:
    """Get the directory for a fetcher's raw data.

    Args:
        source: Fetcher name (e.g. "gadm", "hydrosheds", "wri_gppd", "wdpa", "gwa").
        scope: ISO3 country code or "_global" for global data.

    Returns:
        GEOFREA_DATA_DIR / raw / <source> / <scope> as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "raw" / source / scope


def interim(iso3: str, layer: str) -> Path:
    """Get the interim (processed cache) directory for a layer.

    Args:
        iso3: ISO-3166-alpha-3 country code.
        layer: Layer name (e.g. "grid_alignment", "audit").

    Returns:
        GEOFREA_DATA_DIR / interim / <iso3> / <layer> as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "interim" / iso3 / layer


def phase_dir(iso3: str, phase: str, kind: str) -> Path:
    """Get the output directory for a phase's outputs of a given kind.

    Args:
        iso3: ISO-3166-alpha-3 country code.
        phase: Phase name (e.g. "data_quality_audit", "grid_alignment",
            "siting_layers").
        kind: Output kind (e.g. "artifacts", "figures", "reports").

    Returns:
        GEOFREA_DATA_DIR / outputs / <iso3> / <phase> / <kind> as an absolute Path. At a scale other than the default one
        (`core.scale`), a phase that depends on the cell size is `<phase>__<scale id>` (A-08).

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "outputs" / iso3 / phase_directory_name(phase) / kind


def manifest_path(iso3: str) -> Path:
    """Get the manifest file for a country's run results.

    Args:
        iso3: ISO-3166-alpha-3 country code.

    Returns:
        GEOFREA_DATA_DIR / outputs / <iso3> / manifest.json as an absolute Path (`manifest__<scale id>.json` at another
        scale, A-08).

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "outputs" / iso3 / manifest_file_name()


def thesis_dir() -> Path:
    """Get the thesis outputs directory.

    Returns:
        GEOFREA_DATA_DIR / outputs / thesis as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "outputs" / "thesis"


def cross_country_dir() -> Path:
    """Get the directory of the outputs that depend on several countries (the support phase `cross_country_h4`).

    Returns:
        GEOFREA_DATA_DIR / outputs / cross_country as an absolute Path. The manifest of those outputs is
        `manifest.json` in it (`manifest__<scale id>.json` at another scale, A-08).

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "outputs" / "cross_country"


def cross_country_manifest_path() -> Path:
    """Get the manifest of the support phase `cross_country_h4` at the active scale.

    Returns:
        GEOFREA_DATA_DIR / outputs / cross_country / manifest.json (`manifest__<scale id>.json` at another scale, A-08).

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return cross_country_dir() / manifest_file_name()


def log_path(iso3: str, run_id: str) -> Path:
    """Get the run log file for a country and run.

    Args:
        iso3: ISO-3166-alpha-3 country code.
        run_id: Run identifier (e.g. from orchestrator.compute_run_id).

    Returns:
        GEOFREA_DATA_DIR / logs / <iso3> / <run_id>.log as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "logs" / iso3 / f"{run_id}.log"


def outputs_dir() -> Path:
    """Get the root outputs directory.

    Returns:
        GEOFREA_DATA_DIR / outputs as an absolute Path.

    Raises:
        MissingPathEnvironmentError: If GEOFREA_DATA_DIR is not set.
    """
    return _ensure_data_env() / "outputs"


def to_stored_path(path: Path) -> StoredPath:
    """Convert an absolute filesystem path to a StoredPath.

    The only root is GEOFREA_DATA_DIR.

    Args:
        path: An absolute Path to convert.

    Returns:
        A StoredPath with the appropriate root and relative path.

    Raises:
        ValueError: If the path is not under any known root.
        MissingPathEnvironmentError: If the required env var for the path's root is not set.
    """
    path = path.resolve()
    path_str = str(path)

    # Check in order of specificity (most specific first)
    try:
        data_base = _ensure_data_env().resolve()
        data_base_str = str(data_base)
        if path_str.startswith(data_base_str):
            rel = path.relative_to(data_base)
            return StoredPath(root="data", rel=rel.as_posix())
    except (MissingPathEnvironmentError, ValueError):
        pass

    raise ValueError(f"Path {path} is not under any known root (GEOFREA_DATA_DIR)")
