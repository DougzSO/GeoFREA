"""Durable, atomic file writes (COMMAND 98).

A file that must never be seen half written is written beside its destination, flushed to the disk, and moved into place with one
`os.replace`. `os.replace` alone survives a killed process; the flush (`fsync`) is what survives a power loss, where NTFS can keep a
renamed file whose data never reached the disk.

This module decides how bytes reach the disk, never what they are: it is listed in `code_fingerprint.FINGERPRINT_EXEMPT_MODULES`, so a change
here does not change the code fingerprint of any result or cache (CONVENTIONS, "Write mechanics outside the fingerprints").
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Windows holds a file that a search indexer or an antivirus is reading; the lock clears by itself, so a bounded wait and retry is enough
WRITE_RETRY_WAITS_S = (2.0, 5.0, 10.0, 20.0)


def is_lock_error(exc: BaseException) -> bool:
    """True when `exc` is Windows refusing to touch a file another process holds ("Permission denied")."""
    return isinstance(exc, PermissionError) or "ermission" in str(exc)


def retry_while_locked(
    operation: Callable[[], T], label: str, errors: tuple[type[BaseException], ...] = (OSError,)
) -> T:
    """Run `operation`, retrying after each wait of `WRITE_RETRY_WAITS_S` while it fails because the file is locked.

    Any other error, and the last lock error, is raised as it came.
    """
    for wait in (*WRITE_RETRY_WAITS_S, None):
        try:
            return operation()
        except errors as exc:
            if wait is None or not is_lock_error(exc):
                raise
            logger.warning("%s is locked (%s); retrying in %.0fs", label, exc, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover


def fsync_file(path: Path | str) -> None:
    """Flush the data of the file at `path` to the disk."""
    with open(path, "r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def fsync_directory(path: Path | str) -> None:
    """Flush the directory entry of a rename to the disk. Windows cannot open a directory for this; there NTFS journals the rename."""
    if sys.platform == "win32":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def replace_durable(temporary: Path | str, final: Path | str) -> Path:
    """Move `temporary` onto `final` so that `final` is always the old file or the whole new one, also after a power loss.

    The temporary file must be in the same directory (the same volume) as `final`.
    """
    temporary, final = Path(temporary), Path(final)
    fsync_file(temporary)
    retry_while_locked(lambda: temporary.replace(final), final.name)
    fsync_directory(final.parent)
    return final


def write_bytes_atomic(path: Path | str, data: bytes) -> Path:
    """Write `data` to `path` atomically and durably (beside it as `<name>.<pid>.tmp`, flushed, moved into place)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return replace_durable(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path | str, text: str, encoding: str = "utf-8") -> Path:
    """`write_bytes_atomic` for text."""
    return write_bytes_atomic(path, text.encode(encoding))
