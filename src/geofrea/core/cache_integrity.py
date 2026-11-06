"""Integrity check of the cached artifacts of a country, to run after any interruption (COMMAND 98).

A power loss or a killed process can leave a file that exists but is not whole: a raster cut in the middle of its conversion, a table
that was renamed before its data reached the disk, a manifest hash that no longer matches. The cache key of such a file may still say
"current", so the next run would read it. This module opens every cached file, reads it to the end, compares it with the hashes the
manifest recorded, and invalidates the cache key of what fails, so the next run computes it again. It deletes no data file.

What is checked, per country (`data_root` is GEOFREA_DATA_DIR):

1. every artifact of `outputs/<ISO>/manifest.json`: it exists, its size and its byte SHA-256 are the recorded ones, it reads to the end, and
   its canonical content hash (`content_hash.py`) is the recorded one;
2. every file that has a cache-key sidecar (`<file>.cachekey` under `outputs/<ISO>`, `<stem>.key` under `interim/<ISO>`): it exists, is not
   empty and reads to the end; a sidecar without its file is reported;
3. the ledgers and state files (`layers.json`, `manifest.json`, `deferred_check.json`, the reference store) parse;
4. residue of an interrupted write (`*.writing.tif`, `*.partial`, `*.part`, `*.tmp`, `layer_*` work folders) is listed, not removed;
5. with `include_raw`: every file under `raw/<source>/<ISO>` reads to the end, and the tiles that a source manifest hashes match it.

This module is not imported by any phase, so it is outside the code fingerprint of every result and cache.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from geofrea.core.cache_key import KEY_SUFFIX, file_sha256
from geofrea.core.content_hash import content_hash

OK = "ok"
PROBLEM_STATUSES = frozenset(
    {
        "missing",
        "empty",
        "unreadable",
        "size_mismatch",
        "hash_mismatch",
        "content_mismatch",
        "bad_state_file",
    }
)
INFO_STATUSES = frozenset({"orphan_sidecar", "residue", "ledger_not_ok"})
_RESIDUE_SUFFIXES = (".writing.tif", ".partial", ".part")
_CHUNK = 1 << 22
_NC_SLICE = 64


@dataclass
class Finding:
    """One checked file: what was found and what was done about it."""

    country: str
    scope: str  # manifest | sidecar | state | residue | raw
    path: str  # relative to the data directory, posix style
    status: str
    detail: str = ""
    phase: str = ""
    invalidated: bool = False  # the cache-key sidecar was removed (never the data file)

    @property
    def is_problem(self) -> bool:
        return self.status in PROBLEM_STATUSES


class UnreadableError(Exception):
    """The file is there but cannot be read to its end."""


def _read_bytes(path: Path) -> None:
    with path.open("rb") as handle:
        while handle.read(_CHUNK):
            pass


def _read_raster(path: Path) -> None:
    import rasterio

    with rasterio.open(path) as src:
        for band in src.indexes:
            for _, window in src.block_windows(band):
                src.read(band, window=window)


def _read_parquet(path: Path) -> None:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    rows = 0
    for batch in parquet.iter_batches(batch_size=500_000):
        rows += batch.num_rows
    if rows != parquet.metadata.num_rows:
        raise UnreadableError(f"{rows} rows read, {parquet.metadata.num_rows} declared")


def _read_json(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"))


def _read_gpkg(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
    finally:
        connection.close()
    if not result or result[0] != "ok":
        raise UnreadableError(f"sqlite quick_check: {result}")


def _read_npy(path: Path) -> None:
    import numpy as np

    value = np.load(path, allow_pickle=False)
    if hasattr(value, "files"):  # .npz
        with value:
            for name in value.files:
                value[name]
    del value


def _read_png(path: Path) -> None:
    from PIL import Image

    with Image.open(path) as image:
        image.load()


def _read_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
    if bad is not None:
        raise UnreadableError(f"zip member {bad} is damaged")


def _read_netcdf(path: Path) -> None:
    import xarray as xr

    with xr.open_dataset(path, decode_times=False) as dataset:
        for variable in dataset.data_vars.values():
            if variable.ndim == 0:
                variable.values  # noqa: B018
                continue
            first = variable.dims[0]
            for start in range(0, variable.sizes[first], _NC_SLICE):
                variable.isel({first: slice(start, start + _NC_SLICE)}).values  # noqa: B018


_READERS: dict[str, Callable[[Path], None]] = {
    ".tif": _read_raster,
    ".tiff": _read_raster,
    ".parquet": _read_parquet,
    ".json": _read_json,
    ".geojson": _read_json,
    ".gpkg": _read_gpkg,
    ".npy": _read_npy,
    ".npz": _read_npy,
    ".png": _read_png,
    ".zip": _read_zip,
    ".nc": _read_netcdf,
    ".nc4": _read_netcdf,
}


def read_fully(path: Path) -> None:
    """Open `path` and read it to its end with the reader of its type (any other type: every byte).

    Raises:
        UnreadableError: the file is empty, cut, or cannot be decoded.
        OSError: the file cannot be opened (missing, locked).
    """
    path = Path(path)
    if path.stat().st_size == 0:
        raise UnreadableError("the file is empty")
    reader = _READERS.get(path.suffix.lower(), _read_bytes)
    try:
        reader(path)
    except UnreadableError:
        raise
    except Exception as exc:
        raise UnreadableError(f"{type(exc).__name__}: {str(exc)[:300]}") from exc


def sidecar_for(output: Path) -> Path | None:
    """The cache-key sidecar that belongs to `output`, or None: `<name>.cachekey`, or `<stem>.key` (the clip caches)."""
    for candidate in (output.with_name(output.name + KEY_SUFFIX), output.with_suffix(".key")):
        if candidate.is_file():
            return candidate
    return None


def invalidate_cache_key(output: Path) -> bool:
    """Remove the cache-key sidecar of `output`, so no key matches it and the next run computes it again. The data file is not touched.

    Returns:
        True when a sidecar was removed.
    """
    sidecar = sidecar_for(Path(output))
    if sidecar is None:
        return False
    sidecar.unlink()
    return True


def _rel(data_root: Path, path: Path) -> str:
    try:
        return path.relative_to(data_root).as_posix()
    except ValueError:
        return path.as_posix()


def _check_file(
    country: str,
    scope: str,
    data_root: Path,
    path: Path,
    *,
    phase: str = "",
    size: int | None = None,
    sha256: str | None = None,
    content_sha256: str | None = None,
) -> Finding:
    """Read one file to the end and compare it with the recorded size and hashes (those that are given)."""
    rel = _rel(data_root, path)

    def found(status: str, detail: str = "") -> Finding:
        return Finding(country, scope, rel, status, detail, phase)

    if not path.is_file():
        return found("missing", "the file is not there")
    try:
        read_fully(path)
    except UnreadableError as exc:
        return found("empty" if "empty" in str(exc) else "unreadable", str(exc))
    except OSError as exc:
        return found("unreadable", f"{type(exc).__name__}: {exc}")
    actual_size = path.stat().st_size
    if size is not None and actual_size != size:
        return found("size_mismatch", f"{actual_size} bytes, the manifest has {size}")
    if sha256 is not None and file_sha256(path) != sha256:
        return found("hash_mismatch", "the SHA-256 of the bytes is not the recorded one")
    if content_sha256 is not None:
        actual = content_hash(path)
        if actual != content_sha256:
            return found(
                "content_mismatch",
                f"content hash {actual[:24]}..., the manifest has {content_sha256[:24]}...",
            )
    return found(OK)


def _manifest_findings(country: str, data_root: Path, pool: ThreadPoolExecutor) -> list[Finding]:
    manifest_path = data_root / "outputs" / country / "manifest.json"
    if not manifest_path.is_file():
        return [
            Finding(
                country,
                "state",
                _rel(data_root, manifest_path),
                "missing",
                "no manifest for this country",
            )
        ]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [
            Finding(
                country,
                "state",
                _rel(data_root, manifest_path),
                "bad_state_file",
                f"manifest does not parse: {exc}",
            )
        ]
    jobs = []
    for key, entry in sorted(manifest.get("artifacts", {}).items()):
        stored = entry.get("path") or {}
        path = data_root / stored.get("rel", "")
        jobs.append(
            pool.submit(
                _check_file,
                country,
                "manifest",
                data_root,
                path,
                phase=entry.get("phase", ""),
                size=entry.get("size_bytes"),
                sha256=entry.get("sha256"),
                content_sha256=entry.get("content_sha256"),
            )
        )
    return [job.result() for job in jobs]


def _sidecar_outputs(country: str, data_root: Path) -> Iterator[tuple[Path, Path | None]]:
    """(sidecar, output) pairs: `<file>.cachekey` under outputs, `<stem>.key` under interim (output None when it is not there)."""
    for sidecar in sorted((data_root / "outputs" / country).rglob(f"*{KEY_SUFFIX}")):
        output = sidecar.with_name(sidecar.name[: -len(KEY_SUFFIX)])
        yield sidecar, (output if output.is_file() else None)
    for sidecar in sorted((data_root / "interim" / country).rglob("*.key")):
        siblings = [
            p
            for p in sidecar.parent.glob(sidecar.stem + ".*")
            if p.suffix != ".key" and p.is_file()
        ]
        siblings = [
            p for p in siblings if p.name == sidecar.stem + p.suffix
        ]  # not `<stem>.stats.json` and the like
        yield sidecar, (siblings[0] if len(siblings) == 1 else None)


def _sidecar_findings(
    country: str, data_root: Path, pool: ThreadPoolExecutor, seen: set[str]
) -> list[Finding]:
    results: list[Finding] = []
    jobs = []
    for sidecar, output in _sidecar_outputs(country, data_root):
        if output is None:
            results.append(
                Finding(
                    country,
                    "sidecar",
                    _rel(data_root, sidecar),
                    "orphan_sidecar",
                    "the file this key belongs to is not there",
                )
            )
            continue
        if _rel(data_root, output) in seen:
            continue  # already read as a manifest artifact
        jobs.append(pool.submit(_check_file, country, "sidecar", data_root, output))
    return results + [job.result() for job in jobs]


def _state_files(country: str, data_root: Path) -> Iterable[Path]:
    yield from sorted((data_root / "outputs" / country).rglob("layers.json"))
    yield from sorted((data_root / "interim" / country).rglob("layers.json"))
    yield data_root / "outputs" / country / "deferred_check.json"
    yield from sorted((data_root / "references").glob(f"**/{country}*.json"))


def _state_findings(country: str, data_root: Path) -> list[Finding]:
    results = []
    for path in _state_files(country, data_root):
        if not path.is_file():
            continue
        rel = _rel(data_root, path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            results.append(
                Finding(country, "state", rel, "bad_state_file", f"does not parse: {exc}")
            )
            continue
        if path.name == "layers.json" and isinstance(document, list):
            bad = [
                row.get("layer", "?")
                for row in document
                if isinstance(row, dict) and row.get("status") not in {"ok", "cached"}
            ]
            if bad:
                results.append(
                    Finding(
                        country, "state", rel, "ledger_not_ok", "layers not ok: " + ", ".join(bad)
                    )
                )
                continue
        results.append(Finding(country, "state", rel, OK))
    return results


def _residue_findings(country: str, data_root: Path) -> list[Finding]:
    results = []
    for tree in (data_root / "outputs" / country, data_root / "interim" / country):
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            name = path.name
            leftover = path.is_file() and (
                name.endswith(_RESIDUE_SUFFIXES) or name.endswith(".tmp") or ".tmp." in name
            )
            work_dir = (
                path.is_dir() and name.startswith("layer_") and (path / "payload.pkl").exists()
            )
            if leftover or work_dir:
                kind = (
                    "work folder of an interrupted layer"
                    if work_dir
                    else f"{path.stat().st_size} bytes"
                )
                results.append(Finding(country, "residue", _rel(data_root, path), "residue", kind))
    return results


def _raw_findings(country: str, data_root: Path, pool: ThreadPoolExecutor) -> list[Finding]:
    jobs = []
    for source in (
        sorted(p for p in (data_root / "raw").iterdir() if p.is_dir())
        if (data_root / "raw").is_dir()
        else []
    ):
        tree = source / country
        if not tree.is_dir():
            continue
        recorded: dict[str, str] = {}
        for manifest in tree.glob("*.json"):
            try:
                tiles = json.loads(manifest.read_text(encoding="utf-8")).get("tiles")
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(tiles, list):
                recorded.update(
                    {
                        f"{t['name']}.tif": t["sha256"]
                        for t in tiles
                        if isinstance(t, dict) and "name" in t and "sha256" in t
                    }
                )
        for path in sorted(
            p for p in tree.rglob("*") if p.is_file() and not p.name.endswith(".part")
        ):
            jobs.append(
                pool.submit(
                    _check_file, country, "raw", data_root, path, sha256=recorded.get(path.name)
                )
            )
    return [job.result() for job in jobs]


def check_country(
    country: str,
    data_root: Path,
    *,
    include_raw: bool = False,
    invalidate: bool = True,
    workers: int = 4,
) -> list[Finding]:
    """Check the cached artifacts of `country` and, unless `invalidate` is False, remove the cache key of every file that fails.

    Returns:
        One `Finding` per checked file, problems first within each scope.
    """
    data_root = Path(data_root)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        findings = _manifest_findings(country, data_root, pool)
        seen = {f.path for f in findings}
        findings += _sidecar_findings(country, data_root, pool, seen)
        findings += _state_findings(country, data_root)
        findings += _residue_findings(country, data_root)
        if include_raw:
            findings += _raw_findings(country, data_root, pool)
    if invalidate:
        for finding in findings:
            if finding.is_problem and finding.scope in {"manifest", "sidecar"}:
                finding.invalidated = invalidate_cache_key(data_root / finding.path)
    return findings


def summarize(findings: list[Finding]) -> dict:
    """Counts by status and the phases whose artifacts failed (what to rerun)."""
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1
    phases = sorted({f.phase for f in findings if f.is_problem and f.phase})
    return {
        "counts": counts,
        "problems": sum(1 for f in findings if f.is_problem),
        "invalidated": sum(1 for f in findings if f.invalidated),
        "phases_to_rerun": phases,
    }


def to_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
