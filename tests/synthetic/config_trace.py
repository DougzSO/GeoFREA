"""Which configuration keys each phase reads during a run (COMMAND 127, item 5b).

`PHASE_CONFIG_SCOPE` (`core/config_fingerprint.py`) is what a phase is said to read; a phase that reads a key it does not name does not run again when
that key changes (defect 1 of `docs/_audit/generality_audit.md`). The old test only checked that the scopes exist. This module records what is read.

How: while a run is on, every read of a field of a validated config model (`BaseModel.__getattribute__`), every dump of a model, and every read of the
raw `experiments.yaml` (`yaml.safe_load` called outside the config loader) is attributed to the phase that is running (`PhaseSpec.run` is wrapped) and
to its dotted path in the config file: `settings:geospatial.pvcz_csv`, `parameters:countries.ZZZ.connection.reference_project_mw.value`. A model
reached through a field (a section, an entry of a mapping) is given the path of the field it was read from, so the path survives the hops.

A read of a container (a section, a mapping of models) is a traversal and is not recorded: only the leaves are, and a whole-model dump counts as a read
of the whole section. A read of a leaf is covered when a selector of the scope of the phase is a prefix of its path (`*` matches any step, `{iso}` the
country).

Blind spots, stated: a model that is copied (`model_copy`) loses its path and is reported as unattributed; `countries.yaml` is read by the loader as a
plain dict and is not traced; a model read by iteration (`dict(model)`) is not seen.
"""

from __future__ import annotations

import contextlib
import sys
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping

import yaml
from pydantic import BaseModel

from geofrea.config_models.audit import AuditConfig
from geofrea.core import config_fingerprint as cfp
from geofrea.core import orchestrator
from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.schemas import ParametersFile, SettingsFile

ROOTS: dict[type, str] = {
    ExperimentsFile: "experiments",
    ParametersFile: "parameters",
    SettingsFile: "settings",
    AuditConfig: "audit",
    TechnologiesFile: "technologies",
}
# files that read the config to validate it or to fingerprint it, not to run a phase
_LOADER_FILES = ("config_loader.py", "config_fingerprint.py", "config_schemas.py")


_SCHEMA_SUFFIXES = ("core/config_schemas.py", "core/schemas.py", "config_models/audit.py", "config_models/land_availability.py")


def _in_schema_module(filename: str) -> bool:
    return filename.replace("\\", "/").endswith(_SCHEMA_SUFFIXES)


class ConfigTrace:
    """The reads of the config by phase: `reads[phase]` is a set of (file key, dotted path); `unattributed[phase]` the reads with no known path."""

    def __init__(self) -> None:
        self.reads: dict[str, set[tuple[str, str]]] = defaultdict(set)
        self.unattributed: dict[str, set[str]] = defaultdict(set)
        self.phase: str | None = None
        self._paths: dict[int, tuple[object, tuple[str, ...]]] = {}  # id -> (the object, kept alive so the id is not reused; its path)
        self._raw_texts: dict[str, str] = {}

    # -- recording --------------------------------------------------------------------------------------------------------------------

    def _register(self, obj: object, path: tuple[str, ...]) -> None:
        self._paths[id(obj)] = (obj, path)

    def _path_of(self, obj: object) -> tuple[str, ...] | None:
        known = self._paths.get(id(obj))
        if known is not None:
            return known[1]
        root = ROOTS.get(type(obj))
        if root is not None:
            self._register(obj, (root,))
            return (root,)
        return None

    def _leaf(self, path: tuple[str, ...]) -> None:
        if self.phase is not None:
            self.reads[self.phase].add((path[0], ".".join(path[1:])))

    def on_field(self, model: BaseModel, name: str, value: object) -> None:
        parent = self._path_of(model)
        if parent is None:
            if self.phase is not None:
                self.unattributed[self.phase].add(f"{type(model).__name__}.{name}")
            return
        path = (*parent, name)
        if isinstance(value, BaseModel):
            self._register(value, path)
        elif isinstance(value, Mapping) and value and all(isinstance(v, BaseModel) for v in value.values()):
            for key, child in value.items():
                self._register(child, (*path, str(key)))
        elif isinstance(value, list | tuple) and value and all(isinstance(v, BaseModel) for v in value):
            for child in value:
                self._register(child, (*path, "*"))
        else:
            self._leaf(path)

    def on_dump(self, model: BaseModel) -> None:
        path = self._path_of(model)
        if path is not None:
            self._leaf(path)

    # -- raw yaml (experiments.yaml is read as a dict by a few phases) -------------------------------------------------------------------

    def wrap_raw(self, key: str, doc: object, path: tuple[str, ...]) -> object:
        if isinstance(doc, dict):
            return _TracedDict(self, key, path, doc)
        return doc

    # -- installation --------------------------------------------------------------------------------------------------------------------

    @contextlib.contextmanager
    def installed(self, raw_files: Mapping[str, str]) -> Iterator[ConfigTrace]:
        """Trace the run inside the block. `raw_files` maps a file key to its text, so a `yaml.safe_load` of that text is traced."""
        self._raw_texts = {text: key for key, text in raw_files.items()}
        trace = self
        original_getattribute = BaseModel.__getattribute__
        original_dump = BaseModel.model_dump
        original_load = yaml.safe_load
        original_init = orchestrator.PhaseSpec.__init__
        fields_of: dict[type, frozenset[str]] = {}

        def getattribute(self: BaseModel, name: str):
            value = original_getattribute(self, name)
            if name[:1] != "_":
                cls = type(self)
                names = fields_of.get(cls)
                if names is None:
                    names = fields_of[cls] = frozenset(cls.model_fields)
                # a validator of the schema reads the fields of its own model while the file is validated: that is not the phase reading it
                if name in names and not _in_schema_module(sys._getframe(1).f_code.co_filename):
                    trace.on_field(self, name, value)
            return value

        def model_dump(self: BaseModel, *args, **kwargs):
            trace.on_dump(self)
            return original_dump(self, *args, **kwargs)

        def safe_load(stream, *args, **kwargs):
            doc = original_load(stream, *args, **kwargs)
            key = trace._raw_texts.get(stream) if isinstance(stream, str) else None
            if key is None or sys._getframe(1).f_code.co_filename.endswith(_LOADER_FILES):
                return doc
            return trace.wrap_raw(key, doc, (key,))

        def phase_spec_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            run: Callable = self.run

            def traced_run(context, _run=run, _name=self.name):
                previous, trace.phase = trace.phase, _name
                try:
                    return _run(context)
                finally:
                    trace.phase = previous

            object.__setattr__(self, "run", traced_run)

        BaseModel.__getattribute__ = getattribute  # type: ignore[method-assign]
        BaseModel.model_dump = model_dump  # type: ignore[method-assign]
        yaml.safe_load = safe_load
        orchestrator.PhaseSpec.__init__ = phase_spec_init  # type: ignore[method-assign]
        try:
            yield self
        finally:
            BaseModel.__getattribute__ = original_getattribute  # type: ignore[method-assign]
            BaseModel.model_dump = original_dump  # type: ignore[method-assign]
            yaml.safe_load = original_load
            orchestrator.PhaseSpec.__init__ = original_init  # type: ignore[method-assign]


class _TracedDict(dict):
    """A raw config mapping that records the leaves read; a nested mapping read from it is traced with its own path."""

    def __init__(self, trace: ConfigTrace, key: str, path: tuple[str, ...], data: dict) -> None:
        super().__init__(data)
        self._trace, self._key, self._path = trace, key, path

    def _child(self, step, value):
        path = (*self._path, str(step))
        if isinstance(value, dict):
            return _TracedDict(self._trace, self._key, path, value)
        self._trace._leaf(path)
        return value

    def __getitem__(self, step):
        return self._child(step, super().__getitem__(step))

    def get(self, step, default=None):
        return self._child(step, super().get(step)) if step in self else default

    def items(self):
        return [(step, self._child(step, super(_TracedDict, self).__getitem__(step))) for step in self]

    def values(self):
        return [value for _step, value in self.items()]

    def __contains__(self, step):  # a membership test is not a read of the value
        return super().__contains__(step)


# -- what the scope covers ---------------------------------------------------------------------------------------------------------------


def selectors_of(phase: str, country_code: str) -> dict[str, list[tuple[str, ...]]]:
    """The scope of `phase` as file key -> selectors split in steps, with the country in place; `technologies` is the bare mapping of its file."""
    scope: dict[str, list[tuple[str, ...]]] = {}
    for key, selectors in cfp.PHASE_CONFIG_SCOPE[phase].items():
        if key == cfp.TURBINES:
            continue
        scope[key] = [tuple(s.replace(cfp._ISO, country_code).split(".")) for s in selectors]
    return scope


def is_covered(key: str, path: str, selectors: dict[str, list[tuple[str, ...]]]) -> bool:
    """A leaf read is covered when a selector of its file is a prefix of the path (`*` matches any step; the selector `*` covers the file)."""
    steps = tuple(path.split(".")) if path else ()
    if key == "technologies":  # the model wraps the bare mapping of the file under `technologies`
        steps = steps[1:] if steps[:1] == ("technologies",) else steps
    for selector in selectors.get(key, []):
        if selector == (cfp.WHOLE,):
            return True
        if len(selector) <= len(steps) and all(s in (cfp.WHOLE, p) for s, p in zip(selector, steps, strict=False)):
            return True
    return False


def uncovered(trace: ConfigTrace, country_code: str) -> dict[str, list[str]]:
    """Phase -> the leaf reads (`file:path`) that its scope does not name."""
    out: dict[str, list[str]] = {}
    for phase, reads in sorted(trace.reads.items()):
        if phase not in cfp.PHASE_CONFIG_SCOPE:
            continue
        selectors = selectors_of(phase, country_code)
        missing = sorted(f"{key}:{path}" for key, path in reads if not is_covered(key, path, selectors))
        if missing:
            out[phase] = missing
    return out
