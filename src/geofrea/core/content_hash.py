"""Canonical content hash of an artifact (A-02): the data, without the metadata that a writer puts in the file.

The manifest marks a consumer stale only when the content hash of an artifact it requires changed. The hash of the bytes is not that: the
parquet writer stores provenance in the file metadata, a GeoTIFF carries tags, a JSON file can differ in white space and key order, and a
rewrite of the same table gives other bytes. This module hashes what a reader sees:

- parquet: column names, Arrow types and the values of every row, in row order (the file-level key-value metadata, the row-group layout and
  the compression are ignored). Two kinds coexist (COMMAND 131, OQ-084): `parquet2:` (the default) writes the LOGICAL type of each column, so
  `large_string` is `string`, `large_binary` is `binary` and `large_list<T>` is `list<T>`; `parquet:` is the first kind, which writes the Arrow type
  as it is, so a pandas 3 / pyarrow 25 file (`large_string`) and the official file (`string`) hold the same data and have different hashes. The first
  kind is kept to read the hashes already recorded: `content_hash_like(path, recorded)` hashes a file in the kind of a recorded value;
- GeoTIFF: data of band by band (as read, block by block), dtype, shape, CRS, transform and nodata (tags and creation options are ignored);
- JSON and YAML: the parsed document in a canonical dump (key order and white space are ignored, values are not);
- PNG: the decoded pixels and the mode (text chunks are ignored);
- anything else: the bytes.

The hash starts with the kind (`parquet2:`, `parquet:`, `tif:`, `json:`, `yaml:`, `png:`, `bytes:`), so a file that cannot be read as its kind and falls
back to bytes never equals a content hash of another kind.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_BATCH_ROWS = 500_000
_CHUNK = 1 << 22


def _bytes_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_hash(path: Path, logical: bool = False) -> str:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    digest = hashlib.sha256()
    digest.update(
        json.dumps([(f.name, _logical_type(f.type) if logical else str(f.type)) for f in pf.schema_arrow], sort_keys=True).encode()
    )
    for batch in pf.iter_batches(batch_size=_BATCH_ROWS):
        try:
            frame = batch.to_pandas()
            digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
        except (
            TypeError
        ):  # a column of lists or structs: hash the Arrow stream of the batch instead
            if logical:  # the stream carries the schema: write it with the logical types, or a large_list would not equal a list
                batch = batch.cast(pa.schema([pa.field(f.name, _logical_arrow_type(f.type), f.nullable) for f in batch.schema]))
            sink = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink, batch.schema) as writer:
                writer.write_batch(batch)
            digest.update(sink.getvalue().to_pybytes())
    return digest.hexdigest()


def _logical_arrow_type(arrow_type: Any) -> Any:
    """The Arrow type with the physical width of strings, binaries and lists removed (`large_string` -> `string`, `large_list<T>` -> `list<T>`).

    Nested types are walked (a list of large strings, a struct with a large string field); a dictionary-encoded column is not decoded and keeps its type.
    """
    import pyarrow as pa

    types = pa.types
    if types.is_large_string(arrow_type):
        return pa.string()
    if types.is_large_binary(arrow_type):
        return pa.binary()
    if types.is_large_list(arrow_type) or types.is_list(arrow_type):
        item = arrow_type.value_field
        return pa.list_(pa.field(item.name, _logical_arrow_type(item.type), item.nullable))
    if types.is_struct(arrow_type):
        return pa.struct([pa.field(f.name, _logical_arrow_type(f.type), f.nullable) for f in arrow_type])
    if types.is_map(arrow_type):
        return pa.map_(_logical_arrow_type(arrow_type.key_type), _logical_arrow_type(arrow_type.item_type))
    return arrow_type


def _logical_type(arrow_type: Any) -> str:
    """`_logical_arrow_type` as text."""
    return str(_logical_arrow_type(arrow_type))


def _parquet2_hash(path: Path) -> str:
    """`_parquet_hash` with the logical type of each column in place of the Arrow type: the same data hashes the same whatever the writer's string width."""
    return _parquet_hash(path, logical=True)


def _tif_hash(path: Path) -> str:
    import rasterio

    digest = hashlib.sha256()
    with rasterio.open(path) as src:
        digest.update(
            repr(
                (
                    src.count,
                    src.width,
                    src.height,
                    str(src.crs),
                    tuple(src.transform),
                    src.nodatavals,
                    src.dtypes,
                )
            ).encode()
        )
        for band in range(1, src.count + 1):
            for _, window in src.block_windows(band):
                digest.update(np.ascontiguousarray(src.read(band, window=window)).tobytes())
    return digest.hexdigest()


def _canonical(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)


def _json_hash(path: Path) -> str:
    return hashlib.sha256(
        _canonical(json.loads(path.read_text(encoding="utf-8"))).encode()
    ).hexdigest()


def _yaml_hash(path: Path) -> str:
    import yaml

    return hashlib.sha256(
        _canonical(yaml.safe_load(path.read_text(encoding="utf-8"))).encode()
    ).hexdigest()


def _png_hash(path: Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        digest = hashlib.sha256()
        digest.update(repr((image.mode, image.size)).encode())
        digest.update(image.tobytes())
    return digest.hexdigest()


_KINDS = {
    ".parquet": ("parquet2", _parquet2_hash),
    ".tif": ("tif", _tif_hash),
    ".tiff": ("tif", _tif_hash),
    ".json": ("json", _json_hash),
    ".yaml": ("yaml", _yaml_hash),
    ".yml": ("yaml", _yaml_hash),
    ".png": ("png", _png_hash),
}


_HASHERS = {"parquet2": _parquet2_hash, "parquet": _parquet_hash, "tif": _tif_hash, "json": _json_hash, "yaml": _yaml_hash, "png": _png_hash}


def kind_of(recorded: str) -> str:
    """The kind a recorded hash was made in (`parquet2`, `parquet`, `tif`, ..., `bytes`); an unprefixed value is a hash of the bytes."""
    kind, sep, _ = recorded.partition(":")
    return kind if sep else "bytes"


def content_hash(path: Path, kind: str | None = None) -> str:
    """The canonical content hash of the file at `path`, `<kind>:<sha256>`.

    Args:
        path: The file.
        kind: Hash the file in this kind (`parquet`, the first kind of a Parquet file, for instance) instead of the default of its extension.
            An unknown kind, or one that is not made for this file, falls back to the bytes.

    A file that cannot be read as its kind (a truncated parquet, a JSON with a comment) falls back to `bytes:<sha256 of the bytes>`.
    """
    path = Path(path)
    default = _KINDS.get(path.suffix.lower())
    name, hasher = (kind, _HASHERS[kind]) if kind in _HASHERS and default is not None and _same_family(kind, default[0]) else (default or (None, None))
    if hasher is not None:
        try:
            return f"{name}:{hasher(path)}"
        except Exception as exc:  # noqa: BLE001 - any reader failure means: hash the bytes
            logger.debug("%s: not read as %s (%s), hashing its bytes", path, name, exc)
    return f"bytes:{_bytes_hash(path)}"


def _same_family(kind: str, default: str) -> bool:
    return kind.rstrip("2") == default.rstrip("2")


def content_hash_like(path: Path, recorded: str) -> str:
    """The content hash of `path` in the kind of `recorded`, so a value written under the first Parquet kind is compared with a hash of that kind."""
    return content_hash(path, kind_of(recorded))
