"""Checkpoints of a long piece of work, so that an interruption loses minutes and not hours (COMMAND 98).

A phase splits its work into units that are independent of each other (a group of rows of a raster, a member of the ensemble, a batch of
bootstrap replicates). When a unit is done, its result is stored in `interim/<ISO>/<phase>/<item>_ckpt/` and the unit is not computed again
if the run is interrupted and started again. A unit is stored with `atomic_io` (written beside, flushed, moved into place), so after a power
loss a unit is either whole or absent; one that cannot be read is computed again, never trusted.

The directory holds a `manifest.json` with the validity key: a SHA-256 of everything the stored results depend on (the code fingerprint of
the function that computes them, the inputs, the grid, the parameters, the size of a unit). When the key of a run differs from the key in the
directory, every stored unit is dropped with a warning: a result is never taken from a computation that was not this one. The caller clears
the directory when the work it belongs to is finished and recorded (`clear`), not before, so a stop between the last unit and the record of the
result does not lose the work.

The size of all checkpoints is bounded (`checkpoint_max_gb` in settings.yaml, `GEOFREA_CHECKPOINT_MAX_GB` in the environment of the child
processes): when the bound would be passed a unit is not stored, one warning is logged, and the work goes on without protection for that unit.

This module decides how finished work is kept, never what it is: it is listed in `code_fingerprint.FINGERPRINT_EXEMPT_MODULES`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
import shutil
import time
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from geofrea.core.atomic_io import replace_durable, write_text_atomic

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
ENV_MAX_GB = "GEOFREA_CHECKPOINT_MAX_GB"
DEFAULT_MAX_GB = 20.0
_UNIT_SUFFIXES = (".npz", ".json", ".parquet")
_KEY_ITEM = "__checkpoint_key__"
_META_ITEM = "__meta__"


def make_key(**parts: Any) -> str:
    """SHA-256 of the parts a stored result depends on (JSON-serialisable; anything else enters by `str`)."""
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def max_bytes_from_environment() -> int:
    """The disk bound of all checkpoints in bytes: `GEOFREA_CHECKPOINT_MAX_GB` (set by main.py from settings.yaml), else the default."""
    raw = os.environ.get(ENV_MAX_GB)
    try:
        gigabytes = float(raw) if raw else DEFAULT_MAX_GB
    except ValueError:
        logger.warning("%s=%r is not a number; using %.0f GB", ENV_MAX_GB, raw, DEFAULT_MAX_GB)
        gigabytes = DEFAULT_MAX_GB
    return int(gigabytes * 2**30)


def _safe_name(unit: int | str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{unit:08d}" if isinstance(unit, int) else str(unit))


class CheckpointStore:
    """The stored units of one piece of work. Create it at the start of the work; call `clear` when the work is finished and recorded.

    Args:
        directory: Where the units go, `interim/<ISO>/<phase>/<item>_ckpt`.
        key: The validity key (`make_key(...)`): a directory made under another key is dropped.
        label: Name of the work, for the log.
        max_bytes: Bound of the size of this directory (default: `max_bytes_from_environment()`).

    Attributes:
        resumed_from: Number of units found valid in the directory when it was opened (0 on a first run or after a drop).
    """

    def __init__(
        self, directory: Path | str, key: str, *, label: str, max_bytes: int | None = None
    ) -> None:
        self.directory = Path(directory)
        self.key = key
        self.label = label
        self.max_bytes = max_bytes if max_bytes is not None else max_bytes_from_environment()
        self._full_logged = False
        self.resumed_from = 0
        self._open()

    # --- the directory ---------------------------------------------------------------------------------------------------------------------

    def _unit_files(self) -> list[Path]:
        if not self.directory.is_dir():
            return []
        return sorted(
            p
            for p in self.directory.iterdir()
            if p.is_file() and p.suffix in _UNIT_SUFFIXES and p.name != MANIFEST_NAME
        )

    def _manifest_matches(self) -> bool:
        try:
            manifest = json.loads((self.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return manifest.get("schema") == SCHEMA_VERSION and manifest.get("key") == self.key

    def _open(self) -> None:
        if self.directory.is_dir() and not self._manifest_matches():
            stored = self._unit_files()
            if stored:
                logger.warning(
                    "%s: the checkpoint in %s was made for another computation (or its manifest is unreadable): %d stored units dropped.",
                    self.label,
                    self.directory,
                    len(stored),
                )
            self._remove_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        if not (self.directory / MANIFEST_NAME).is_file():
            manifest = {
                "schema": SCHEMA_VERSION,
                "key": self.key,
                "label": self.label,
                "created": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            write_text_atomic(self.directory / MANIFEST_NAME, json.dumps(manifest, indent=1))
        self.resumed_from = len(self._unit_files())
        if self.resumed_from:
            logger.info(
                "%s: %d stored units found in %s; they are not computed again.",
                self.label,
                self.resumed_from,
                self.directory,
            )

    def _remove_directory(self) -> None:
        clear_checkpoint(self.directory)

    def size_bytes(self) -> int:
        return (
            sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())
            if self.directory.is_dir()
            else 0
        )

    def clear(self) -> None:
        """Remove every stored unit and the directory: the work is finished and its result is recorded."""
        self._remove_directory()

    def done_units(self) -> list[str]:
        """Names of the stored units, as written (the file name without its suffix)."""
        return [p.stem for p in self._unit_files()]

    def _room_for(self, nbytes: int) -> bool:
        if self.size_bytes() + nbytes <= self.max_bytes:
            return True
        if not self._full_logged:
            self._full_logged = True
            logger.warning(
                "%s: the checkpoints would pass %.1f GB (checkpoint_max_gb); the units from here on are not stored.",
                self.label,
                self.max_bytes / 2**30,
            )
        return False

    def _path(self, unit: int | str, suffix: str) -> Path:
        return self.directory / f"{_safe_name(unit)}{suffix}"

    def exists(self, unit: int | str, suffix: str = ".npz") -> bool:
        """Whether a file of the unit is there (not whether it can be read: `load_*` decides that)."""
        return self._path(unit, suffix).is_file()

    def _discard(self, path: Path, reason: str) -> None:
        logger.warning(
            "%s: the stored unit %s cannot be read (%s); it is computed again.",
            self.label,
            path.name,
            reason,
        )
        path.unlink(missing_ok=True)

    # --- arrays ----------------------------------------------------------------------------------------------------------------------------

    def save_arrays(
        self,
        unit: int | str,
        arrays: Mapping[str, np.ndarray],
        meta: Mapping[str, Any] | None = None,
        *,
        compress: bool = True,
    ) -> bool:
        """Store the arrays (and a small JSON-serialisable `meta`) of a finished unit. Returns False when the disk bound stopped it.

        A unit that is stored again under the same name replaces the earlier one whole (the state of a running total, kept after each step).
        `compress=False` skips the compression for large arrays that are rewritten often.
        """
        final = self._path(unit, ".npz")
        replaced = final.stat().st_size if final.is_file() else 0
        if not self._room_for(sum(int(np.asarray(a).nbytes) for a in arrays.values()) - replaced):
            return False
        temporary = final.with_name(f"{final.name}.{os.getpid()}.tmp")
        payload = {name: np.asarray(a) for name, a in arrays.items()}
        payload[_KEY_ITEM] = np.array(self.key)
        payload[_META_ITEM] = np.array(json.dumps(dict(meta or {}), sort_keys=True))
        try:
            with open(temporary, "wb") as handle:
                (np.savez_compressed if compress else np.savez)(handle, **payload)
            replace_durable(temporary, final)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return True

    def load_arrays(self, unit: int | str) -> tuple[dict[str, np.ndarray], dict[str, Any]] | None:
        """The arrays and meta of a stored unit, or None when there is none or it cannot be read (an unreadable unit is removed)."""
        path = self._path(unit, ".npz")
        if not path.is_file():
            return None
        reason = None
        try:
            # the file is opened here so that the handle is closed before a bad unit is removed (Windows cannot delete an open file, and numpy
            # leaves the handle open when it fails to read the archive)
            with open(path, "rb") as handle, np.load(handle, allow_pickle=False) as stored:
                if str(stored[_KEY_ITEM]) != self.key:
                    reason = "made under another key"
                else:
                    meta = json.loads(str(stored[_META_ITEM]))
                    arrays = {
                        name: stored[name]
                        for name in stored.files
                        if name not in (_KEY_ITEM, _META_ITEM)
                    }
        except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
            reason = f"{type(exc).__name__}: {exc}"
        if reason is not None:
            self._discard(path, reason)
            return None
        return arrays, meta

    def group(self, prefix: str) -> UnitGroup:
        """The units of one named sequence (the strips of one share, for example), numbered from 0."""
        return UnitGroup(self, prefix)

    # --- small JSON state (for example the state of a random generator) ----------------------------------------------------------------------

    def save_json(self, unit: int | str, state: Mapping[str, Any]) -> bool:
        """Store a small JSON-serialisable state as a unit."""
        document = json.dumps({"key": self.key, "state": dict(state)}, sort_keys=True)
        if not self._room_for(len(document)):
            return False
        write_text_atomic(self._path(unit, ".json"), document)
        return True

    def load_json(self, unit: int | str) -> dict[str, Any] | None:
        path = self._path(unit, ".json")
        if not path.is_file():
            return None
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document["key"] != self.key:
                self._discard(path, "made under another key")
                return None
            return document["state"]
        except (OSError, ValueError, KeyError) as exc:
            self._discard(path, f"{type(exc).__name__}: {exc}")
            return None

    # --- tables ----------------------------------------------------------------------------------------------------------------------------

    def save_frame(self, unit: int | str, frame) -> bool:
        """Store a pandas DataFrame as a unit (Parquet, the key in its metadata)."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pandas(frame, preserve_index=True)
        table = table.replace_schema_metadata(
            {**(table.schema.metadata or {}), b"checkpoint_key": self.key.encode()}
        )
        if not self._room_for(int(table.nbytes)):
            return False
        final = self._path(unit, ".parquet")
        temporary = final.with_name(f"{final.name}.{os.getpid()}.tmp")
        try:
            pq.write_table(table, temporary, compression="zstd")
            replace_durable(temporary, final)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return True

    def load_frame(self, unit: int | str):
        """The DataFrame of a stored unit, or None when there is none or it cannot be read (an unreadable unit is removed)."""
        import pyarrow.parquet as pq

        path = self._path(unit, ".parquet")
        if not path.is_file():
            return None
        try:
            table = pq.read_table(path)
            if (table.schema.metadata or {}).get(b"checkpoint_key") != self.key.encode():
                self._discard(path, "made under another key")
                return None
            return table.to_pandas()
        except (OSError, ValueError, KeyError) as exc:
            self._discard(path, f"{type(exc).__name__}: {exc}")
            return None


def clear_checkpoint(directory: Path | str) -> None:
    """Remove the checkpoint directory of a piece of work that is finished and recorded (nothing happens when there is none)."""
    directory = Path(directory)
    for attempt in range(4):  # a search indexer can hold a file for a moment
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 3:
                raise
            time.sleep(1.0 + attempt)


class UnitGroup:
    """A numbered sequence of units of one store (`store.group("c3")`): what a loop over strips, blocks or members stores and takes back.

    A function that works in independent pieces takes an optional group and does, per piece `i`: `arrays = group.load(i)`; when it is None, compute the
    piece and `group.save(i, {...})`. With no group nothing is stored and the function behaves as before.
    """

    def __init__(self, store: CheckpointStore, prefix: str) -> None:
        self.store = store
        self.prefix = prefix

    def _unit(self, index: int) -> str:
        return f"{self.prefix}_{index:06d}"

    def load(self, index: int) -> dict[str, np.ndarray] | None:
        """The arrays stored for piece `index`, or None (absent or unreadable)."""
        stored = self.store.load_arrays(self._unit(index))
        return None if stored is None else stored[0]

    def save(self, index: int, arrays: Mapping[str, np.ndarray]) -> bool:
        """Store the arrays of piece `index` (False when the disk bound stopped it)."""
        return self.store.save_arrays(self._unit(index), arrays)


def digest_inputs(*objects: Any) -> str:
    """SHA-256 of what a stored result is computed from: the numbers of arrays, of dataclasses made of them, of pandas objects and of containers.

    For a checkpoint whose inputs are objects in memory (the members of the ensemble, the draws) and not files. An array enters by its dtype, its shape
    and its bytes, an array of Python objects by its list, a dataclass by its fields in order, a mapping by its sorted keys; anything else by `repr`.
    """
    import pandas as pd

    digest = hashlib.sha256()

    def feed(value: Any) -> None:
        if isinstance(value, np.ndarray):
            digest.update(f"nd:{value.dtype}:{value.shape}".encode())
            if value.dtype == object:
                digest.update(repr(value.tolist()).encode())
            else:
                digest.update(np.ascontiguousarray(value).tobytes())
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            digest.update(f"dc:{type(value).__name__}".encode())
            for field in dataclasses.fields(value):
                digest.update(field.name.encode())
                feed(getattr(value, field.name))
        elif isinstance(value, pd.DataFrame):
            digest.update(("df:" + ",".join(map(str, value.columns)) + f":{value.shape}").encode())
            digest.update(pd.util.hash_pandas_object(value, index=True).to_numpy().tobytes())
        elif isinstance(value, pd.Series):
            digest.update(f"sr:{value.name}:{value.dtype}:{value.shape}".encode())
            digest.update(pd.util.hash_pandas_object(value, index=True).to_numpy().tobytes())
        elif isinstance(value, Mapping):
            digest.update(f"map:{len(value)}".encode())
            for key in sorted(value, key=str):
                feed(key)
                feed(value[key])
        elif isinstance(value, list | tuple):
            digest.update(f"seq:{len(value)}".encode())
            for item in value:
                feed(item)
        else:
            digest.update(f"v:{value!r}".encode())

    for obj in objects:
        feed(obj)
    return digest.hexdigest()
