"""The reference store: copies of the outputs of the rounds that were accepted (COMMAND 91; D-core-051).

`config/deferred_checks.yaml` compares a run with a reference by the content hash of each artifact. A hash says that two files differ, not by how much:
for a raster that differs in the last bit of a float the check needs the reference *file*. The store keeps those files, apart from any backup directory
made by hand, and keeps them for every accepted round so that the reference moves forward.

Layout under `<data root>/references/`:

    objects/<aa>/<sha256>          the bytes of a file, once (the name is the SHA-256 of the bytes: a file never changes)
    <run_id>/<ISO>/index.json      country, run_id, when accepted, the phases of the run with their verdict, and every file kept
    <run_id>/<ISO>/manifest.json   the manifest of the country as it was when the round was accepted, with the phases that ended `success` only (a phase
                                   that is `stale_upstream` is waiting for a rerun: the next run must not be compared with its old artifacts)
    <run_id>/<ISO>/files/<path>    the files, at the path they have under the data root (`outputs/BRA/artifacts/land_eligibility.json`); a hard link
                                   to the object, so a file that did not change between two rounds takes no new space (a copy where the volume cannot link)
    latest.json                    {"BRA": "<run_id>", ...}: the last accepted round of each country

The `run_id` of the manifest says which code and configuration the run had, not which country: the countries of one unattended round share it, and two
runs of one country on the same code share it too. So a round is the pair (`run_id`, country); a round that is kept again under the same pair replaces the
earlier one, which is moved to `<run_id>/<ISO>.superseded_<time>/` and not deleted.

What is kept (`StoreConfig`): the JSON artifacts, that is the summaries of the phases (not only their hashes), and the rasters of the phases listed in
`raster_phases` (the aligned and the F2b layers, which are the ones compared by tolerance). The tables are not kept: they are large and the check compares
them by hash.

The reference moves only by an explicit act (OQ-080, COMMAND 137): `core.deferred_check.publish_with_gate`, called by `scripts/publish_reference.py` or by
`main.py --publish-reference`, runs the gate over every phase of the round and keeps it (`publish_state`) only if no phase is DIFERENTE and every phase has a
comparison. The pipeline does not publish by itself any more: a run that passes its own gate is not thereby the reference.
A file is copied only if its SHA-256 is the one the manifest recorded for it: a reference never holds a file that is not the one of the run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geofrea.core.atomic_io import replace_durable

logger = logging.getLogger(__name__)

LATEST_NAME = "latest.json"
INDEX_NAME = "index.json"
SEED_PREFIX = "seed_"


@dataclass(frozen=True)
class StoreConfig:
    """What the store keeps of a run."""

    suffixes: tuple[str, ...] = (".json",)  # artifacts of any phase with one of these suffixes (the summaries)
    raster_phases: tuple[str, ...] = ("grid_alignment", "siting_layers")  # phases whose .tif artifacts are kept
    raster_suffixes: tuple[str, ...] = (".tif", ".tiff")

    def keeps(self, phase: str, path: Path) -> bool:
        suffix = path.suffix.lower()
        return suffix in self.suffixes or (suffix in self.raster_suffixes and phase in self.raster_phases)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    replace_durable(tmp, path)


@dataclass
class ReferenceStore:
    """The store under `root` (`<data root>/references`)."""

    root: Path
    config: StoreConfig = field(default_factory=StoreConfig)

    # --- reading -------------------------------------------------------------------------------------------------------------------------

    def latest(self, iso: str) -> str | None:
        """The run_id of the last accepted round of `iso`, or None."""
        path = self.root / LATEST_NAME
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get(iso.upper())

    def round_dir(self, iso: str, run_id: str) -> Path:
        """The directory of round `run_id` of `iso`."""
        return self.root / run_id / iso.upper()

    def resolve(self, iso: str, run: str | None) -> str | None:
        """`run` as a run_id: `latest` (or None) is the last accepted round of `iso`; anything else must exist for `iso`."""
        if run is None or run == "latest":
            return self.latest(iso)
        return run if (self.round_dir(iso, run) / INDEX_NAME).is_file() else None

    def index(self, iso: str, run_id: str) -> dict:
        return json.loads((self.round_dir(iso, run_id) / INDEX_NAME).read_text(encoding="utf-8"))

    def find(self, iso: str, run: str | None, name: str) -> Path | None:
        """The kept file called `name` (a file name) in round `run` of `iso`, or None; the first one by path if the name is not unique."""
        run_id = self.resolve(iso, run)
        if run_id is None:
            return None
        for rel in sorted(self.index(iso, run_id)["files"]):
            if Path(rel).name == name:
                path = self.round_dir(iso, run_id) / "files" / rel
                return path if path.is_file() else None
        return None

    def manifest_path(self, iso: str, run: str | None) -> Path | None:
        """The manifest of the country as it was when round `run` was accepted, or None."""
        run_id = self.resolve(iso, run)
        path = None if run_id is None else self.round_dir(iso, run_id) / "manifest.json"
        return path if path is not None and path.is_file() else None

    def status(self, iso: str, run_id: str) -> str:
        """`accepted` (kept by the pipeline), `state` (the state of a country published by hand with its evidence), `imported` (a backup) or `historical`."""
        return self.index(iso, run_id).get("status", "accepted")

    def mark_historical(self, iso: str, run_id: str, note: str) -> None:
        """Mark a round as historical: kept, still readable and still pinnable, but no longer a reference to move forward from. Nothing is deleted."""
        index = self.index(iso, run_id)
        index["status_before"] = index.get("status", "accepted")
        index["status"] = "historical"
        index["historical_note"] = note
        index["marked_historical_at"] = _now()
        _write_json(self.round_dir(iso, run_id) / INDEX_NAME, index)

    def json_summary(self, iso: str, run: str | None, name: str) -> dict | None:
        """A kept JSON summary (`land_eligibility.json`) as a dictionary, or None."""
        path = self.find(iso, run, name)
        return None if path is None else json.loads(path.read_text(encoding="utf-8"))

    # --- writing -------------------------------------------------------------------------------------------------------------------------

    def _object(self, sha: str) -> Path:
        return self.root / "objects" / sha[:2] / sha

    def _keep_bytes(self, source: Path, sha: str) -> Path:
        target = self._object(sha)
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp")
            shutil.copyfile(source, tmp)
            replace_durable(tmp, target)
        return target

    def _place(self, obj: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        try:
            os.link(obj, destination)
        except OSError:
            shutil.copyfile(obj, destination)

    def publish_files(
        self,
        iso: str,
        run_id: str,
        files: dict[str, tuple[Path, str | None, dict]],
        *,
        manifest_path: Path | None = None,
        manifest_data: dict | None = None,
        phases: dict[str, dict] | None = None,
        extra: dict | None = None,
        make_latest: bool = True,
    ) -> Path:
        """Keep `files` as round `run_id` of `iso`: {path under the data root: (file, expected SHA-256 or None, extra fields of its index entry)}.

        A file whose SHA-256 is not the expected one is not kept and the whole round is refused (`ValueError`): nothing is written for it.
        """
        entries: dict[str, dict] = {}
        staged: dict[str, tuple[Path, str]] = {}
        for rel, (source, expected, info) in sorted(files.items()):
            sha = _sha256(source)
            if expected is not None and sha != expected:
                raise ValueError(f"{rel}: the file on disk ({sha[:12]}) is not the one the manifest recorded ({expected[:12]}); the round is not kept")
            staged[rel] = (source, sha)
            entries[rel] = {"sha256": sha, "size_bytes": source.stat().st_size, **info}
        run_dir = self.round_dir(iso, run_id)
        if run_dir.exists():  # the same pair (run_id, country) kept again: the earlier round is set aside, not deleted
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            run_dir.rename(run_dir.with_name(f"{run_dir.name}.superseded_{stamp}"))
        for rel, (source, sha) in staged.items():
            self._place(self._keep_bytes(source, sha), run_dir / "files" / rel)
        if manifest_data is not None:
            _write_json(run_dir / "manifest.json", manifest_data)
        elif manifest_path is not None and manifest_path.is_file():
            shutil.copyfile(manifest_path, run_dir / "manifest.json")
        _write_json(
            run_dir / INDEX_NAME,
            {"country": iso.upper(), "run_id": run_id, "accepted_at": _now(), "phases": phases or {}, "files": entries, **(extra or {})},
        )
        if make_latest:
            latest_path = self.root / LATEST_NAME
            latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.is_file() else {}
            latest[iso.upper()] = run_id
            _write_json(latest_path, latest)
        logger.info("reference store: round %s of %s kept (%d files)", run_id, iso.upper(), len(entries))
        return run_dir

    def import_directories(self, iso: str, run_id: str, directories: list[Path], *, note: str) -> Path:
        """Keep the rasters and the JSON files found in `directories` (a backup made by hand) as round `run_id` of `iso`.

        They are placed at `outputs/<ISO>/imported/<directory name>/<file name>`; the round is marked `imported` and is not `latest` (it is the
        reference a country pins with `reference_run`, not an accepted round of the pipeline).
        """
        files: dict[str, tuple[Path, str | None, dict]] = {}
        for directory in directories:
            for path in sorted(Path(directory).iterdir()):
                if path.is_file() and path.suffix.lower() in (*self.config.suffixes, *self.config.raster_suffixes):
                    files[f"outputs/{iso.upper()}/imported/{Path(directory).name}/{path.name}"] = (path, None, {"phase": None, "key": None})
        return self.publish_files(
            iso, run_id, files, extra={"status": "imported", "imported_from": [str(d) for d in directories], "note": note}, make_latest=False
        )

    def publish_state(self, manifest: Any, manifest_path: Path, deferred_check: Any = None, *, evidence: dict) -> Path | None:
        """Keep the state a country has on disk as an accepted round, by hand (COMMAND 91): the state of the manifest, with the evidence that it is clean.

        Only the phases that ended `success` are kept (a `stale_upstream` phase is waiting for a rerun, its artifacts are not the reference of anything);
        the others are listed in the index as `not_kept_phases`. Refused when a phase `failed`, when none is `success` or when the deferred check has a
        phase DIFERENTE. `evidence` is stored in the index.
        """
        failed = sorted(name for name, e in manifest.phases.items() if e.status == "failed")
        if failed:
            raise ValueError(f"phases of the manifest that failed: {', '.join(failed)}")
        if not any(e.status == "success" for e in manifest.phases.values()):
            raise ValueError("no phase of the manifest ended success")
        if deferred_check is not None and deferred_check.blocked_phases():
            raise ValueError(f"the deferred check has phases DIFERENTE: {', '.join(deferred_check.blocked_phases())}")
        executed = {name: False for name in manifest.phases}
        run_dir = self._publish_manifest(manifest, manifest_path, executed, deferred_check, {"status": "state", "evidence": evidence}, raise_errors=True)
        return run_dir

    def _publish_manifest(
        self, manifest: Any, manifest_path: Path, executed: dict[str, bool], deferred_check: Any, extra: dict, *, raise_errors: bool = False
    ) -> Path | None:
        try:
            kept = {name for name, entry in manifest.phases.items() if entry.status == "success"}
            not_kept = {name: entry.status for name, entry in manifest.phases.items() if name not in kept}
            files: dict[str, tuple[Path, str | None, dict]] = {}
            for key, entry in sorted(manifest.artifacts.items()):
                path = Path(entry.path.resolve())
                if entry.phase in kept and path.is_file() and self.config.keeps(entry.phase, path):
                    files[entry.path.rel] = (path, entry.sha256, {"key": key, "phase": entry.phase})
            check_phases = deferred_check.verdicts() if deferred_check is not None else {}
            phases = {
                name: {
                    "executed_in_this_round": executed.get(name, False),
                    "code_fingerprint": getattr(entry, "code_fingerprint", None),
                    "config_fingerprint": getattr(entry, "config_fingerprint", None),
                    "finished_at": getattr(entry, "finished_at", None),
                    "deferred_check": check_phases.get(name),
                }
                for name, entry in manifest.phases.items()
                if name in kept
            }
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["phases"] = {k: v for k, v in data["phases"].items() if k in kept}
            data["artifacts"] = {k: v for k, v in data["artifacts"].items() if v["phase"] in kept}
            return self.publish_files(
                manifest.country_code,
                manifest.run_id,
                files,
                manifest_data=data,
                phases=phases,
                extra={
                    "methodology_version": getattr(next(iter(manifest.phases.values()), None), "methodology_version", None),
                    "not_kept_phases": not_kept,
                    **extra,
                },
            )
        except (OSError, ValueError) as exc:
            if raise_errors:
                raise
            logger.error("reference store: the round %s of %s could not be kept: %s", manifest.run_id, manifest.country_code, exc)
            return None
