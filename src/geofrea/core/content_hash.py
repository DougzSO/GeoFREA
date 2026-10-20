"""Canonical content hash of an artifact (A-02): the data, without the metadata that a writer puts in the file.

The manifest marks a consumer stale only when the content hash of an artifact it requires changed. The hash of the bytes is not that: the
parquet writer stores provenance in the file metadata, a GeoTIFF carries tags, a JSON file can differ in white space and key order, and a
rewrite of the same table gives other bytes. This module hashes what a reader sees:

- parquet: column names, Arrow types and the values of every row, in row order (the file-level key-value metadata, the row-group layout and
  the compression are ignored);
- GeoTIFF: data of band by band (as read, block by block), dtype, shape, CRS, transform and nodata (tags and creation options are ignored);
- JSON and YAML: the parsed document in a canonical dump (key order and white space are ignored, values are not);
- PNG: the decoded pixels and the mode (text chunks are ignored);
- anything else: the bytes.

The hash starts with the kind (`parquet:`, `tif:`, `json:`, `yaml:`, `png:`, `bytes:`), so a file that cannot be read as its kind and falls
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


def _parquet_hash(path: Path) -> str:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    digest = hashlib.sha256()
    digest.update(
        json.dumps([(f.name, str(f.type)) for f in pf.schema_arrow], sort_keys=True).encode()
    )
    for batch in pf.iter_batches(batch_size=_BATCH_ROWS):
        try:
            frame = batch.to_pandas()
            digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
        except (
            TypeError
        ):  # a column of lists or structs: hash the Arrow stream of the batch instead
            sink = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink, batch.schema) as writer:
                writer.write_batch(batch)
            digest.update(sink.getvalue().to_pybytes())
    return digest.hexdigest()


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
    ".parquet": ("parquet", _parquet_hash),
    ".tif": ("tif", _tif_hash),
    ".tiff": ("tif", _tif_hash),
    ".json": ("json", _json_hash),
    ".yaml": ("yaml", _yaml_hash),
    ".yml": ("yaml", _yaml_hash),
    ".png": ("png", _png_hash),
}


def content_hash(path: Path) -> str:
    """The canonical content hash of the file at `path`, `<kind>:<sha256>`.

    A file that cannot be read as its kind (a truncated parquet, a JSON with a comment) falls back to `bytes:<sha256 of the bytes>`.
    """
    path = Path(path)
    kind = _KINDS.get(path.suffix.lower())
    if kind is not None:
        name, hasher = kind
        try:
            return f"{name}:{hasher(path)}"
        except Exception as exc:  # noqa: BLE001 - any reader failure means: hash the bytes
            logger.debug("%s: not read as %s (%s), hashing its bytes", path, name, exc)
    return f"bytes:{_bytes_hash(path)}"
