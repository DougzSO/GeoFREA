"""One layer of F2a or F2b in its own child process, one at a time (COMMAND 88, item 1).

The parent only coordinates: before a layer it waits for the memory that layer needs (`memory_guard.wait_for_memory`), it starts the child
(`python -m geofrea.core.layer_process`), watches the commit charge of the system while the child runs, and records what happened in the
ledger of the phase. The child imports the function named by `target` (`"package.module:function"`), calls it with the pickled keyword
arguments and pickles the return value to a result file. Whatever the child allocated returns to the system when it exits, so the peak of
a run is the peak of its heaviest layer, not the sum of the layers.

A layer that fails does not touch the files of the layers already written: the ledger row says `failed` and the caller decides whether to
go on with the layers that do not depend on it. A commit charge over the limit (`CommitLimitExceeded`) or a wait that times out
(`MemoryWaitTimeout`) ends the run at once: the next layers would meet the same machine.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import psutil

from geofrea.core import memory_guard
from geofrea.core.atomic_io import replace_durable
from geofrea.core.memory_guard import COMMIT_STOP_FRACTION, CommitLimitExceeded

logger = logging.getLogger(__name__)

IN_PROCESS_ENV = "GEOFREA_LAYERS_IN_PROCESS"  # "1" runs the layers in the calling process (tests only)
POLL_S = 0.5
GDAL_CACHEMAX_MB = 256  # when the environment has none; main.py sets GDAL_CACHEMAX from settings.yaml `geospatial.gdal_cachemax_mb`
_LOG_TAIL_LINES = 12


class LayerFailedError(RuntimeError):
    """A layer's child process ended with an error; the layers written before it are intact."""

    def __init__(self, layer: str, returncode: int, tail: str) -> None:
        super().__init__(f"layer {layer}: the child process ended with exit code {returncode}:\n{tail}")
        self.layer = layer
        self.returncode = returncode
        self.record: LayerRecord | None = None


@dataclass
class LayerRecord:
    """One row of the ledger of a phase: what a layer did, how long it took and the highest memory its child held."""

    layer: str
    status: str  # "ok" | "failed" | "stopped"
    wall_s: float = 0.0
    peak_rss_mb: float = 0.0
    peak_commit_mb: float = 0.0
    waited_s: float = 0.0
    waits: list[str] = field(default_factory=list)
    detail: str = ""


def _peaks(root: psutil.Process) -> tuple[int, int]:
    """(highest working set, highest commit) among a process and its children, bytes: the venv launcher is a stub, the work is in its child."""
    ws = commit = 0
    try:
        processes = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0, 0
    for process in processes:
        try:
            info = process.memory_info()
        except psutil.Error:
            continue
        ws = max(ws, int(getattr(info, "peak_wset", info.rss)))
        commit = max(commit, int(getattr(info, "peak_pagefile", 0)))
    return ws, commit


def kill_tree(process: psutil.Process) -> None:
    """End a process and every process below it: the venv launcher is a stub, so ending it alone leaves the Python child running."""
    try:
        victims = [*process.children(recursive=True), process]
    except psutil.Error:
        return
    for victim in victims:
        try:
            victim.kill()
        except psutil.Error:
            pass


def child_environment(src_root: Path | None = None) -> dict[str, str]:
    """The environment of a layer child: the same `geofrea` source as the parent and a fixed GDAL block cache."""
    root = Path(src_root) if src_root is not None else Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])])
    env["GDAL_CACHEMAX"] = env.get("GDAL_CACHEMAX") or str(GDAL_CACHEMAX_MB)  # main.py sets it from settings.yaml
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_layer(
    layer: str,
    target: str,
    kwargs: dict[str, Any],
    *,
    peak_mb: float | None = None,
    work_dir: Path | None = None,
    wait_timeout_s: float = memory_guard.WAIT_TIMEOUT_S,
    margin_mb: float = memory_guard.MARGIN_MB,
) -> tuple[Any, LayerRecord]:
    """Run `target(**kwargs)` in a child process and return (its return value, the ledger row).

    Args:
        layer: Name of the layer (log and ledger).
        target: `"package.module:function"`, importable in the child.
        kwargs: Keyword arguments, pickled to the child.
        peak_mb: Peak resident memory measured for this layer; the child starts when that much plus `margin_mb` is free. None skips the wait.
        work_dir: Where the payload and result files go (default: a temporary directory).

    Raises:
        MemoryWaitTimeout: the memory did not become free in time; the layer was not started.
        CommitLimitExceeded: the commit charge passed 95 % while the child ran (the child was ended) or before it started.
        LayerFailedError: the child ended with an error.
    """
    record = LayerRecord(layer=layer, status="stopped")
    if os.environ.get(IN_PROCESS_ENV) == "1":  # the unit tests patch module attributes, which a child process would not see
        started = time.perf_counter()
        module_name, _, function_name = target.partition(":")
        value = getattr(importlib.import_module(module_name), function_name)(**kwargs)
        record.status, record.wall_s = "ok", round(time.perf_counter() - started, 1)
        return value, record
    if peak_mb is not None:
        wait = memory_guard.wait_for_memory(layer, peak_mb, margin_mb=margin_mb, timeout_s=wait_timeout_s)
        record.waits, record.waited_s = wait.waits, round(wait.waited_s, 1)
    remove_stale_work_dirs(layer, work_dir)
    with tempfile.TemporaryDirectory(prefix=f"layer_{layer}_", dir=work_dir) as tmp:
        payload, result, log = Path(tmp) / "payload.pkl", Path(tmp) / "result.pkl", Path(tmp) / "child.log"
        payload.write_bytes(pickle.dumps({"target": target, "kwargs": kwargs}, protocol=pickle.HIGHEST_PROTOCOL))
        started = time.perf_counter()
        with log.open("wb") as log_file:
            child = subprocess.Popen(
                [sys.executable, "-m", "geofrea.core.layer_process", str(payload), str(result)],
                env=child_environment(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            process = psutil.Process(child.pid)
            peak_ws = peak_commit = 0
            while child.poll() is None:
                ws, commit = _peaks(process)
                peak_ws, peak_commit = max(peak_ws, ws), max(peak_commit, commit)
                used = memory_guard.commit_fraction()
                if used > COMMIT_STOP_FRACTION:
                    kill_tree(process)
                    child.wait()
                    record.detail = f"the commit charge reached {used:.0%} (stop above {COMMIT_STOP_FRACTION:.0%})"
                    _fill(record, started, peak_ws, peak_commit)
                    raise CommitLimitExceeded(f"{layer}: {record.detail}; the child was ended, the layers written before it are intact")
                time.sleep(POLL_S)
            ws, commit = _peaks(process)
            peak_ws, peak_commit = max(peak_ws, ws), max(peak_commit, commit)
        _fill(record, started, peak_ws, peak_commit)
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-_LOG_TAIL_LINES:])
        if child.returncode != 0 or not result.exists():
            record.status, record.detail = "failed", tail
            error = LayerFailedError(layer, child.returncode, tail)
            error.record = record  # the peak the child reached is still wanted when it was stopped from outside
            raise error
        record.status = "ok"
        return pickle.loads(result.read_bytes()), record  # noqa: S301 — written by our own child a moment ago


def remove_stale_work_dirs(layer: str, work_dir: Path | None) -> int:
    """Remove the work folders (`layer_<name>_*`, with their `payload.pkl`) that an earlier run left when it was killed (COMMAND 98).

    Layers run one at a time, so a folder of this kind that exists when a layer starts belongs to a process that no longer runs.

    Returns:
        The number of folders removed.
    """
    if work_dir is None or not Path(work_dir).is_dir():
        return 0
    removed = 0
    for stale in Path(work_dir).glob(f"layer_{layer}_*"):
        if stale.is_dir() and (stale / "payload.pkl").exists():
            shutil.rmtree(stale, ignore_errors=True)
            removed += 1
    if removed:
        logger.info("%s: %d work folder(s) of an interrupted run removed.", layer, removed)
    return removed


def _fill(record: LayerRecord, started: float, peak_ws: int, peak_commit: int) -> None:
    record.wall_s = round(time.perf_counter() - started, 1)
    record.peak_rss_mb = round(peak_ws / 2**20, 1)
    record.peak_commit_mb = round(peak_commit / 2**20, 1)


def append_ledger(path: Path, records: list[LayerRecord]) -> None:
    """Write the ledger of the phase (`layers.json`, replaced atomically after every layer so an interrupted run keeps what finished)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps([asdict(r) for r in records], indent=2), encoding="utf-8")
    replace_durable(tmp, path)


def _child_main(payload_file: str, result_file: str) -> int:
    request = pickle.loads(Path(payload_file).read_bytes())  # noqa: S301 — written by the parent of this very call
    module_name, _, function_name = request["target"].partition(":")
    function = getattr(importlib.import_module(module_name), function_name)
    try:
        value = function(**request["kwargs"])
    except BaseException:  # noqa: BLE001 — the parent reads the traceback from the log
        traceback.print_exc()
        return 1
    Path(result_file).write_bytes(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
    return 0


def selftest_echo(value: Any = None, megabytes: int = 0) -> Any:
    """A target for the tests: returns `value` after holding `megabytes` MB for a moment."""
    held = bytearray(megabytes * 2**20)
    for offset in range(0, len(held), 4096):  # touch every page so it is resident
        held[offset] = 1
    time.sleep(1.5 if megabytes else 0.2)  # long enough for the parent's poll to see it
    del held
    return value


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    raise SystemExit(_child_main(sys.argv[1], sys.argv[2]))
