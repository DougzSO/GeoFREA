"""Content-addressed cache keys (OQ-026).

The key of a cache is the SHA-256 of three things: the sorted list of the input files with the SHA-256 of each, the config values that
change the output, and an algorithm-version constant defined in the module that computes the cached result and bumped by hand when
its logic changes, and, since COMMAND 61, the fingerprint of the code that computes the result (`core.cache_code`), so a changed line of calculation
gives another key whether or not anyone bumped the constant. A change in any of them gives another key, so a stale cache is recomputed, never reused. File names enter the
key by base name, not by directory, so a data directory that moves keeps its caches.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KEY_SUFFIX = ".cachekey"
_CHUNK_BYTES = 1 << 20


def file_sha256(path: Path | str) -> str:
    """SHA-256 of the bytes of `path`, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileHashMemo:
    """File hashes persisted in a JSON file and reused while path, size and mtime are unchanged.

    The reuse is the one the orchestrator applies to its artifacts (`_hash_with_reuse`): a file edited in place with the same size and
    mtime is not detected. The memo is never the key itself; the key holds the hash.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._entries: dict[str, str] = {}
        if path is not None and path.exists():
            try:
                self._entries = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                logger.warning("Input hash memo %s is unreadable; hashing again.", path)

    def sha256(self, path: Path | str) -> str:
        path = Path(path)
        stat = path.stat()
        memo_key = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
        if memo_key not in self._entries:
            self._entries[memo_key] = file_sha256(path)
            self._save()
        return self._entries[memo_key]

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._entries, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not write the input hash memo %s: %s", self._path, exc)


def cache_key(
    algorithm_version: str | int,
    input_files: Iterable[Path | str | None],
    config: Mapping[str, Any] | None = None,
    memo: FileHashMemo | None = None,
    *,
    code: str,
) -> str:
    """Key of one cached result: algorithm version, sorted (name, SHA-256) of the input files, the config values and the code.

    Args:
        algorithm_version: The module's constant, bumped by hand when the logic changes.
        input_files: Every file the result is computed from; `None` entries are skipped.
        config: The config values that affect the output (JSON-serializable, e.g. a resolution, a cap, a polygon hash).
        memo: Optional hash memo; without it every file is hashed.
        code: Fingerprint of the code that computes the result (`core.cache_code.cache_code(name)`); required, a key without it is the
            defect of COMMAND 58.
    """
    sha = memo.sha256 if memo is not None else file_sha256
    files = sorted((Path(p).name, sha(p)) for p in input_files if p is not None)
    payload = {
        "algorithm_version": algorithm_version,
        "input_files": files,
        "config": dict(config or {}),
        "code": code,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def key_path(output: Path | str) -> Path:
    """Sidecar that holds the key of `output`."""
    output = Path(output)
    return output.with_name(output.name + KEY_SUFFIX)


def cache_is_current(output: Path | str, key: str) -> bool:
    """True when `output` exists and its sidecar holds exactly `key`; an output with no sidecar is stale."""
    sidecar = key_path(output)
    return (
        Path(output).exists()
        and sidecar.exists()
        and sidecar.read_text(encoding="utf-8").strip() == key
    )


def write_cache_key(output: Path | str, key: str) -> None:
    key_path(output).write_text(key, encoding="utf-8")
