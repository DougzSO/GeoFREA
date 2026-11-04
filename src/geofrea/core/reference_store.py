"""The reference store: copies of the outputs of the rounds that were accepted (COMMAND 91; D-core-051).

`config/deferred_checks.yaml` compares a run with a reference by the content hash of each artifact. A hash says that two files differ, not by how much:
for a raster that differs in the last bit of a float the check needs the reference *file*. The store keeps those files, apart from any backup directory
made by hand, and keeps them for every accepted round so that the reference moves forward.

Layout under `<data root>/references/`:

    objects/<aa>/<sha256>          the bytes of a file, once (the name is the SHA-256 of the bytes: a file never changes)
    <run_id>/index.json            country, run_id, when accepted, the phases of the run with their verdict, and every file kept
    <run_id>/manifest.json         the manifest of the country as it was when the round was accepted (the hashes of every artifact)
    <run_id>/files/<path>          the files, at the path they have under the data root (`outputs/BRA/artifacts/land_eligibility.json`); a hard link
                                   to the object, so a file that did not change between two rounds takes no new space (a copy where the volume cannot link)
    latest.json                    {"BRA": "<run_id>", ...}: the last accepted round of each country

What is kept (`StoreConfig`): the JSON artifacts, that is the summaries of the phases (not only their hashes), and the rasters of the phases listed in
`raster_phases` (the aligned and the F2b layers, which are the ones compared by tolerance). The tables are not kept: they are large and the check compares
them by hash.

A round is accepted (`accepts`) when it executed at least one phase, every phase of its results ended `success` and, for a country with a deferred check,
no phase of the check has the verdict DIFERENTE. `publish` is called by the orchestrator at the end of a run and does nothing for a round that is not
accepted. A file is copied only if its SHA-256 is the one the manifest recorded for it: a reference never holds a file that is not the one of the run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


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

    def resolve(self, iso: str, run: str | None) -> str | None:
        """`run` as a run_id: `latest` (or None) is the last accepted round of `iso`; anything else must exist."""
        if run is None or run == "latest":
            return self.latest(iso)
        return run if (self.root / run / INDEX_NAME).is_file() else None

    def index(self, run_id: str) -> dict:
        return json.loads((self.root / run_id / INDEX_NAME).read_text(encoding="utf-8"))

    def find(self, iso: str, run: str | None, name: str) -> Path | None:
        """The kept file called `name` (a file name) in round `run` of `iso`, or None; the first one by path if the name is not unique."""
        run_id = self.resolve(iso, run)
        if run_id is None:
            return None
        for rel in sorted(self.index(run_id)["files"]):
            if Path(rel).name == name:
                path = self.root / run_id / "files" / rel
                return path if path.is_file() else None
        return None

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
            os.replace(tmp, target)
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
        run_dir = self.root / run_id
        for rel, (source, sha) in staged.items():
            self._place(self._keep_bytes(source, sha), run_dir / "files" / rel)
        if manifest_path is not None and manifest_path.is_file():
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
        return self.publish_files(iso, run_id, files, extra={"imported_from": [str(d) for d in directories], "note": note}, make_latest=False)

    # --- the acceptance of a round -------------------------------------------------------------------------------------------------------

    @staticmethod
    def accepts(results: dict[str, Any], deferred_check: Any = None) -> tuple[bool, str]:
        """(accepted, why not): the round executed a phase, every result is `success`, and the deferred check has no phase DIFERENTE."""
        if not results:
            return False, "no phase in the results"
        bad = sorted(name for name, r in results.items() if r.status != "success")
        if bad:
            return False, f"phases that did not end success: {', '.join(bad)}"
        if not any(r.wall_s is not None for r in results.values()):
            return False, "every phase was resumed, nothing was executed"
        if deferred_check is not None:
            blocked = deferred_check.blocked_phases()
            if blocked:
                return False, f"the deferred check has phases DIFERENTE: {', '.join(blocked)}"
        return True, ""

    def publish(self, manifest: Any, manifest_path: Path, results: dict[str, Any], deferred_check: Any = None) -> Path | None:
        """Keep the round that has just ended if it is accepted; returns the directory, or None. An error here never stops the pipeline."""
        accepted, why = self.accepts(results, deferred_check)
        if not accepted:
            logger.info("reference store: the round %s of %s is not kept (%s)", manifest.run_id, manifest.country_code, why)
            return None
        try:
            files: dict[str, tuple[Path, str | None, dict]] = {}
            for key, entry in sorted(manifest.artifacts.items()):
                path = Path(entry.path.resolve())
                if path.is_file() and self.config.keeps(entry.phase, path):
                    files[entry.path.rel] = (path, entry.sha256, {"key": key, "phase": entry.phase})
            check_phases = deferred_check.verdicts() if deferred_check is not None else {}
            phases = {
                name: {
                    "executed_in_this_round": results[name].wall_s is not None if name in results else False,
                    "code_fingerprint": getattr(entry, "code_fingerprint", None),
                    "config_fingerprint": getattr(entry, "config_fingerprint", None),
                    "finished_at": getattr(entry, "finished_at", None),
                    "deferred_check": check_phases.get(name),
                }
                for name, entry in manifest.phases.items()
            }
            return self.publish_files(
                manifest.country_code,
                manifest.run_id,
                files,
                manifest_path=manifest_path,
                phases=phases,
                extra={"methodology_version": getattr(next(iter(manifest.phases.values()), None), "methodology_version", None)},
            )
        except (OSError, ValueError) as exc:
            logger.error("reference store: the round %s of %s could not be kept: %s", manifest.run_id, manifest.country_code, exc)
            return None
