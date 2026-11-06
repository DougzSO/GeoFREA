"""A download that continues where it stopped and is never taken for complete before it is (COMMAND 98).

The bytes go to `<file>.part` beside the destination. A `.part` file left by an interrupted run is continued with an HTTP `Range` request; a server
that answers the whole file again (it ignored the range) starts the file over. When the size received is the size the server declared, the file is
flushed to the disk and moved onto its name with one rename, so the destination is the whole file or does not exist: a file cut by a stop is never
named as a tile.

`existing_entry` is for a file that is already at its name (a previous run's tile): it must have the size and the SHA-256 recorded for it, and, when the
run has no record (the manifest is written when a country is finished), a GeoTIFF must open and give its last block.

This module decides how bytes reach the disk, never what they are: it is listed in `code_fingerprint.FINGERPRINT_EXEMPT_MODULES`.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import requests

from geofrea.core.atomic_io import replace_durable

logger = logging.getLogger(__name__)

_CHUNK = 1 << 20  # hashing
_NET_CHUNK = 1 << 16  # a connection that breaks loses the block it was reading: small blocks keep what arrived before it
_RANGE_TOTAL = re.compile(r"bytes\s+(?:\d+-\d+|\*)/(\d+)")


class DownloadError(RuntimeError):
    """The download did not end with the whole file (the `.part` is kept for the next run unless it was longer than the file)."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _declared_size(response: requests.Response, offset: int) -> int:
    """The size of the whole file as the server declares it: `Content-Range` of a 206, else `Content-Length` of a 200."""
    if response.status_code == 206:
        match = _RANGE_TOTAL.match(response.headers.get("Content-Range", ""))
        if match is None:
            raise DownloadError("the server answered 206 with no usable Content-Range")
        return int(match.group(1))
    return int(response.headers["Content-Length"])


def download_resumable(
    url: str,
    target: Path,
    *,
    timeout: float = 120.0,
    absent_statuses: Iterable[int] = (404,),
    attempts: int = 3,
    verify: Callable[[Path], None] | None = None,
) -> dict | None:
    """Download `url` to `target`, continuing a `.part` file of an earlier run.

    Args:
        target: The destination. Its `.part` is `target` with the suffix `.part` (the name the earlier fetchers used).
        absent_statuses: HTTP statuses that mean "this file does not exist" (open sea): the result is None and no file is left.
        attempts: Times the transfer is continued within one call when the connection ends before the declared size.
        verify: Called on the complete `.part` before it is named; raises to refuse it.

    Returns:
        `{"bytes": size, "sha256": hex}` of the file, or None when the server says it does not exist.

    Raises:
        DownloadError: the size received is not the size declared after every attempt (a short `.part` stays for the next run; a longer one is
            removed), the server answers an error status, or `verify` refuses the file.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".part")
    absent = set(absent_statuses)
    total: int | None = None
    for attempt in range(1, attempts + 1):
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=headers) as response:
                if response.status_code in absent:
                    part.unlink(missing_ok=True)
                    return None
                if response.status_code == 416:  # the part is as long as the file, or longer
                    match = _RANGE_TOTAL.match(response.headers.get("Content-Range", ""))
                    total = int(match.group(1)) if match else None
                    if total == offset:
                        break
                    part.unlink(missing_ok=True)
                    continue
                response.raise_for_status()
                total = _declared_size(response, offset)
                mode = "ab" if response.status_code == 206 else "wb"  # a 200 gives the whole file again: start it over
                with open(part, mode) as handle:
                    handle.writelines(response.iter_content(_NET_CHUNK))
                    handle.flush()
        except requests.RequestException as exc:
            logger.warning("%s: the transfer ended early (%s: %s); %d of %d attempts", target.name, type(exc).__name__, exc, attempt, attempts)
            if attempt == attempts:
                raise DownloadError(f"{target.name}: {exc}") from exc
            continue
        if total is not None and part.stat().st_size == total:
            break
    size = part.stat().st_size if part.exists() else 0
    if total is None or size != total:
        if total is not None and size > total:
            part.unlink(missing_ok=True)
        raise DownloadError(f"{target.name}: got {size} bytes, expected {total}")
    if verify is not None:
        try:
            verify(part)
        except Exception as exc:
            part.unlink(missing_ok=True)
            raise DownloadError(f"{target.name}: the file received was refused ({exc})") from exc
    replace_durable(part, target)
    return {"bytes": total, "sha256": sha256_of(target)}


def looks_whole_geotiff(path: Path) -> bool:
    """A GeoTIFF that opens and gives its last block (a file cut by a stop fails one of the two)."""
    import rasterio

    try:
        with rasterio.open(path) as src:
            windows = list(src.block_windows(1))
            src.read(1, window=windows[-1][1])
    except Exception:  # noqa: BLE001 - any failure to open or read means the file is not whole
        return False
    return True


def existing_entry(path: Path, recorded: dict | None, *, geotiff: bool = True) -> dict | None:
    """The manifest entry `{"bytes", "sha256"}` of a file that is already at its name, or None when it is not the whole file.

    With a record (`recorded`: the entry of an earlier run) the size and the SHA-256 must be the recorded ones; with none, a GeoTIFF must open and give
    its last block. The hash is computed once: it is the one the manifest keeps.
    """
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    entry = {"bytes": path.stat().st_size, "sha256": sha256_of(path)}
    if recorded is not None:
        return entry if entry["bytes"] == recorded.get("bytes") and entry["sha256"] == recorded.get("sha256") else None
    return entry if (not geotiff or looks_whole_geotiff(path)) else None
