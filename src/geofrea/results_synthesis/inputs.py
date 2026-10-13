"""The only door F8 reads through: the artifacts a country's manifest registers (M-F8-01; D-F8-001).

F8 recomputes no scientific quantity. Every table or figure is a function of artifacts that F4 to F7b registered in the manifest of the run
(and of configuration files for the method tables). `ArtifactReader` finds an artifact by its manifest key, checks that the file still has
the hash recorded at registration, refuses a table whose schema version it does not know, and remembers what was read so the output can
cite it. A path is never built by hand.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from geofrea.core import paths as core_paths
from geofrea.core.scale import active_scale, use_scale
from geofrea.core.tables import SCHEMA_VERSION_KEY

_CHUNK = 1 << 20


class ThesisInputError(RuntimeError):
    """An artifact F8 needs is absent, changed since it was registered, or has a schema version F8 does not know (A-09)."""


class MissingArtifactError(ThesisInputError):
    """The manifest does not register the artifact."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


class ArtifactReader:
    """Reads the registered artifacts of one country at one scale and records what it read.

    Args:
        iso: Country code.
        scale_id: The scale whose manifest is read (default: the active scale). The manifest of another scale is
            `manifest__<scale id>.json` (A-08).
    """

    def __init__(self, iso: str, scale_id: str | None = None) -> None:
        self.iso = iso
        self.scale_id = scale_id or active_scale().scale_id
        with use_scale(self.scale_id):
            self.manifest_file = core_paths.manifest_path(iso)
        self._artifacts: dict[str, dict] = {}
        if self.manifest_file.is_file():
            self._artifacts = json.loads(self.manifest_file.read_text(encoding="utf-8")).get(
                "artifacts", {}
            )
        self._hashes: dict[str, str] = {}
        self.used: dict[str, str] = {}

    @property
    def available(self) -> bool:
        """The manifest exists and registers at least one artifact."""
        return bool(self._artifacts)

    def has(self, key: str) -> bool:
        return key in self._artifacts

    def path(self, key: str) -> Path:
        """The file of the artifact `key`, after checking it against the hash registered with it.

        Raises:
            MissingArtifactError: `key` is not registered, or its file is gone.
            ThesisInputError: the file's content differs from the registered hash.
        """
        entry = self._artifacts.get(key)
        if entry is None:
            raise MissingArtifactError(
                f"{self.iso} ({self.scale_id}): the manifest registers no artifact {key!r}"
            )
        stored = core_paths.StoredPath(**entry["path"])
        path = stored.resolve()
        if not path.is_file():
            raise MissingArtifactError(
                f"{self.iso}: artifact {key!r} is registered but {stored} is absent"
            )
        if key not in self._hashes:
            self._hashes[key] = sha256_of(path)
        if self._hashes[key] != entry["sha256"]:
            raise ThesisInputError(
                f"{self.iso}: artifact {key!r} changed since it was registered ({stored}); rerun its phase"
            )
        self.used[key] = entry["sha256"]
        return path

    def table(
        self,
        key: str,
        schema_versions: set[str] | tuple[str, ...],
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """A Parquet artifact, refused when its schema version is not one of `schema_versions` (A-07)."""
        path = self.path(key)
        meta = pq.read_schema(path).metadata or {}
        found = meta.get(SCHEMA_VERSION_KEY, b"").decode()
        if found not in set(schema_versions):
            raise ThesisInputError(
                f"{key}: schema version {found!r}, F8 reads {sorted(schema_versions)}"
            )
        return pd.read_parquet(path, columns=columns)

    def skip_note(self, key: str) -> dict | None:
        """The reason a table was written empty (the `*_skipped` entry of its metadata), or None."""
        meta = pq.read_schema(self.path(key)).metadata or {}
        for name, value in meta.items():
            if name.decode().endswith("_skipped"):
                return json.loads(value.decode())
        return None
