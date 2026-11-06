"""The mechanics of writing a raster: open with a retry, convert to a Cloud Optimized GeoTIFF, put it in place atomically (COMMAND 98).

`raster_io` decides what is written (the profile, the windows, the tags); this module decides how the finished file reaches its name. The
conversion goes to a temporary name beside the destination and is moved onto it with one `os.replace` after a flush, so a stop during the
conversion leaves the previous file untouched or no file, never a cut one (the earlier code deleted the destination first and converted in
place, so a power loss left a truncated raster that a still-current cache key would have accepted).

The COG written is the one `rasterio.shutil.copy(..., driver="COG")` wrote before (same options, same bytes): the name it is created under
is not part of the file. Listed in `code_fingerprint.FINGERPRINT_EXEMPT_MODULES`: a change here does not change any code fingerprint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rasterio
import rasterio.shutil
from rasterio._err import CPLE_BaseError

from geofrea.core.atomic_io import replace_durable, retry_while_locked

CONVERTING_SUFFIX = ".converting.tif"
_LOCK_ERRORS = (rasterio.errors.RasterioIOError, CPLE_BaseError, PermissionError)


def open_for_write(file_path: Path, kwargs: dict[str, Any]):
    """rasterio.open(..., "w") that retries when Windows holds the file it must overwrite.

    GDAL deletes an existing file before creating it; a search indexer or antivirus scanning a file written moments earlier makes that
    delete fail with "Permission denied" (observed 2026-10-06 on the BRA wind layers). The lock clears by itself, so wait and retry a
    bounded number of times, then raise the original error.
    """

    def _open():
        # A scratch file left by an interrupted run (a power loss cuts it mid-write) has an unreadable header: GDAL opens an existing file to
        # delete it before creating the new one and fails on it (IND, 2026-11-05). The name is ours and holds nothing worth keeping.
        file_path.unlink(missing_ok=True)
        return rasterio.open(str(file_path), "w", **kwargs)

    return retry_while_locked(_open, file_path.name, _LOCK_ERRORS)


def cog_options(kwargs: dict[str, Any]) -> dict[str, str]:
    """GDAL COG creation options equivalent to the writer's profile (same compression, same predictor, 256 pixel blocks)."""
    options = {
        "COMPRESS": str(kwargs.get("compress", "lzw")).upper(),
        "BLOCKSIZE": str(kwargs.get("blockxsize", 256)),
        "OVERVIEW_RESAMPLING": "NEAREST",  # overviews never invent values: classes and counts stay valid
    }
    if kwargs.get("predictor") is not None:
        options["PREDICTOR"] = str(kwargs["predictor"])
    return options


def write_cog(tmp_path: Path, final_path: Path, kwargs: dict[str, Any]) -> None:
    """Convert the finished GeoTIFF at `tmp_path` into a Cloud Optimized GeoTIFF at `final_path` (lossless), then drop `tmp_path`.

    `final_path` is replaced only when the conversion is complete and flushed: an error or a stop before that leaves what was there.

    Implements: A-07.
    """
    options = cog_options(kwargs)
    converting = final_path.with_name(final_path.stem + CONVERTING_SUFFIX)
    try:

        def _convert() -> None:
            converting.unlink(missing_ok=True)  # a cut conversion of an interrupted run, same reason as in `open_for_write`
            rasterio.shutil.copy(str(tmp_path), str(converting), driver="COG", **options)

        retry_while_locked(_convert, final_path.name, _LOCK_ERRORS)
        replace_durable(converting, final_path)
    except BaseException:
        converting.unlink(missing_ok=True)
        raise
    tmp_path.unlink(missing_ok=True)
