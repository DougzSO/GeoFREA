"""Console/file logging split and phase-lifecycle/progress logging (COMMAND ADJ-7).

Before this module, `main.py` called `logging.basicConfig()` (attaching a
handler to the plain root logger) and separately attached a `FileHandler`
only to the `"geofrea.main"` logger. Since Python's logging hierarchy only
delivers a record to the handlers on its own logger's ancestors, every other
module's logger (`"geofrea.core.orchestrator"`, `"geofrea.grid_alignment.*"`,
`"geofrea.data_quality_audit.*"`, ...) propagated to the console (via root's
basicConfig handler) but never reached the run's log file — the file was, in
practice, the least complete record of a run, backwards from what a log file
is for. `configure_logging()` fixes this by attaching both handlers to the shared
`"geofrea"` ancestor logger instead — every `geofrea.*` module's logger is
a descendant of it, so both handlers see every record any of them emits.

Console vs. file split:
    - Console: `logging.INFO` and above, compact format
      (`"%(asctime)s %(levelname)s %(message)s"`). Carries phase start/
      completion/failure lines and periodic progress — what a person
      watching a terminal needs to see, nothing else.
    - File: `logging.DEBUG` and above, format includes the logger name
      (`"%(asctime)s %(levelname)s %(name)s %(message)s"`) so a line's
      origin module is traceable after the fact. Carries everything any
      `geofrea.*` module logs, at any level, for post-hoc diagnosis.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TypeVar

_CONSOLE_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_FILE_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_GEOFREA_LOGGER_NAME = "geofrea"
_MANAGED_ATTR = "_geofrea_run_logging_managed"

T = TypeVar("T")


def configure_logging(
    log_file_path: Path,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.FileHandler:
    """Attach a console and a file handler to the shared `"geofrea"` logger.

    Idempotent and safe to call once per country in a multi-country run:
    any handler this function previously attached (marked via
    `_MANAGED_ATTR`) is removed first, so repeated calls neither duplicate
    console lines nor leave stale file handlers pointed at a prior
    country's log file open.

    Args:
        log_file_path: Where this run's complete log is written. Parent
            directories are created if missing.
        console_level: Minimum level shown on the console (default INFO).
        file_level: Minimum level written to the file (default DEBUG —
            the full detail, regardless of what the console shows).

    Returns:
        The attached `FileHandler`, so a caller can `.close()` it when a
        country's run ends, before opening the next country's log file.
    """
    geofrea_logger = logging.getLogger(_GEOFREA_LOGGER_NAME)
    geofrea_logger.setLevel(min(console_level, file_level))
    # propagate left at its default (True): nothing here should require
    # the plain root logger to stay handler-less. In production, root has
    # no handlers of its own, so nothing is emitted twice; in tests,
    # pytest's `caplog` fixture attaches its capture handler to root and
    # still needs to see these records.

    for handler in list(geofrea_logger.handlers):
        if getattr(handler, _MANAGED_ATTR, False):
            geofrea_logger.removeHandler(handler)
            handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    setattr(console_handler, _MANAGED_ATTR, True)
    geofrea_logger.addHandler(console_handler)

    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    setattr(file_handler, _MANAGED_ATTR, True)
    geofrea_logger.addHandler(file_handler)

    return file_handler


class PeriodicProgress:
    """Logs "`done`/`total` done, elapsed `Xs`" every `every` items or `min_interval_s` seconds.

    Deliberately not a progress bar (CONVENTIONS.md "Long-running scripts"):
    a bar's carriage-return redraw is unreadable once a console is
    redirected to a log file, whereas a plain INFO line every N items reads
    the same in a terminal and in a file. Always logs on the first and last
    item regardless of `every`/`min_interval_s`, so a short loop still
    brackets its own progress.

    Args:
        logger: Logger to emit progress lines on (INFO level).
        total: Total item count, for the "`done`/`total`" line. 0 is valid
            (an empty loop logs nothing, since there is no first/last item).
        label: Short description prefixed to each line (e.g. "land_cover
            mosaic", "land_cover tile audit").
        every: Log a line every this many completed items (default 10).
        min_interval_s: Additionally log a line if at least this many
            seconds have passed since the last one, even if `every` hasn't
            been reached — keeps a slow-per-item loop legible too.
    """

    def __init__(
        self,
        logger: logging.Logger,
        total: int,
        label: str,
        every: int = 10,
        min_interval_s: float = 30.0,
    ) -> None:
        self._logger = logger
        self._total = total
        self._label = label
        self._every = max(1, every)
        self._min_interval_s = min_interval_s
        self._done = 0
        self._start = time.monotonic()
        self._last_logged_at = self._start

    def step(self) -> None:
        """Record one completed item, logging a line if a threshold was reached."""
        self._done += 1
        now = time.monotonic()
        is_first = self._done == 1
        is_last = self._done == self._total
        due_by_count = self._done % self._every == 0
        due_by_time = (now - self._last_logged_at) >= self._min_interval_s
        if is_first or is_last or due_by_count or due_by_time:
            elapsed = now - self._start
            self._logger.info(
                "%s: %d/%d done, elapsed %.1fs", self._label, self._done, self._total, elapsed
            )
            self._last_logged_at = now

    def track(self, iterable: Iterable[T]) -> Iterator[T]:
        """Yield each item of `iterable`, calling `step()` after it is produced."""
        for item in iterable:
            yield item
            self.step()


def periodic_progress(
    logger: logging.Logger,
    iterable: Sequence[T] | Iterable[T],
    label: str,
    total: int | None = None,
    every: int = 10,
    min_interval_s: float = 30.0,
) -> Iterator[T]:
    """Wrap `iterable`, logging periodic "`done`/`total`" progress lines.

    Convenience wrapper over `PeriodicProgress.track()` for the common case
    (a `for tile in periodic_progress(logger, tiles, "land_cover mosaic"):`
    loop) — see `PeriodicProgress` for the logging behavior.

    Args:
        total: Item count, if not derivable from `len(iterable)` (e.g.
            `iterable` is a generator). Required in that case.
    """
    if total is None:
        total = len(iterable)  # type: ignore[arg-type]
    return PeriodicProgress(logger, total, label, every=every, min_interval_s=min_interval_s).track(
        iterable
    )


def render_run_table(rows: Sequence[dict], run_id: str) -> str:
    """Render the end-of-run table: phase, status, elapsed time, artifact count, per country.

    Args:
        rows: One dict per (country, phase) attempted, each with keys
            "country", "phase", "status", "elapsed_s", "artifact_count".
        run_id: This run's identifier, printed once below the table.

    Returns:
        A plain-text table, ready to log or print — fixed-width columns,
        no external table-formatting dependency.
    """
    headers = ("country", "phase", "status", "elapsed_s", "artifacts")
    str_rows = [
        (
            row["country"],
            row["phase"],
            row["status"],
            f"{row['elapsed_s']:.1f}",
            str(row["artifact_count"]),
        )
        for row in rows
    ]
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in str_rows)) if str_rows else len(headers[i])
        for i in range(len(headers))
    ]

    def _fmt_row(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))

    lines = [_fmt_row(headers), _fmt_row(["-" * w for w in widths])]
    lines.extend(_fmt_row(r) for r in str_rows)
    lines.append(f"run_id: {run_id}")
    return "\n".join(lines)
