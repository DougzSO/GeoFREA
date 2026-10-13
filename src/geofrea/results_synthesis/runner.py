"""The F8 runner: builds the thesis outputs of one country and records what was and was not built (M-F8-01, M-F8-02; D-F8-007).

One script per T-ID (`SCRIPTS`); `only` runs a subset. Each script reads artifacts through `ArtifactReader` and configuration, never raw
data and never a kernel. A script that cannot build an item says why (`BuildContext.skip`); the runner lists it in
`outputs/thesis/thesis_manifest.json` and fails only when an Essential T-ID has no output at all for the country.

Outputs not built yet and the open decision that blocks each: T-R3 (D2, the GCM-agreement convention), T-R8 (D6, the combination rule of
the cross-country synthesis); T-M1, T-R1, T-R4, T-R5, T-R7, T-R11 and T-O1 follow in later commits.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.core.scale import active_scale, other_scales
from geofrea.core.schemas import CountryParams, VerifiedValue
from geofrea.results_synthesis import names
from geofrea.results_synthesis.inputs import ArtifactReader
from geofrea.results_synthesis.method_tables import ThesisValueError, t_m2, t_m3
from geofrea.results_synthesis.output import BuildContext, NotBuilt, methodology_version
from geofrea.results_synthesis.potential_and_cost import t_o3, t_r2
from geofrea.results_synthesis.robustness_tables import t_o2, t_r6, t_r9, t_r10, t_r12

SCRIPTS: dict[str, Callable[[BuildContext], None]] = {
    "T-M2": t_m2,
    "T-M3": t_m3,
    "T-R2": t_r2,
    "T-R6": t_r6,
    "T-R9": t_r9,
    "T-R10": t_r10,
    "T-R12": t_r12,
    "T-O2": t_o2,
    "T-O3": t_o3,
}
MANIFEST_NAME = "thesis_manifest.json"


class ThesisBuildError(RuntimeError):
    """An Essential output has nothing built for the country (D7)."""


class NotBuiltItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_id: str
    item: str
    reason: str


class ThesisSummary(BaseModel):
    """What one F8 run built for a country: the files by T-ID (names only) and what was not built."""

    model_config = ConfigDict(extra="forbid")

    country_code: str
    scale: str
    test_values: bool
    methodology_version: str
    built: dict[str, list[str]]
    not_built: list[NotBuiltItem]


def is_test_build(country: CountryParams | None, technologies: Sequence[str]) -> bool:
    """True when every parameter value of the country is a test value: the country is a synthetic fixture (D9)."""
    if country is None:
        return False
    flags = [
        value.synthetic
        for technology in technologies
        for name in type(getattr(country.technologies, technology)).model_fields
        if isinstance(
            value := getattr(getattr(country.technologies, technology), name), VerifiedValue
        )
    ]
    return bool(flags) and all(flags)


def thesis_output_dir() -> Path:
    """`outputs/thesis`; a run at another scale writes `outputs/thesis__<scale id>` so it never overwrites the thesis outputs (A-08)."""
    scale = active_scale()
    base = core_paths.thesis_dir()
    return base if scale.is_default else base.with_name(f"{base.name}__{scale.scale_id}")


def _other_scale(iso: str) -> ArtifactReader | None:
    for scale in other_scales():
        reader = ArtifactReader(iso, scale.scale_id)
        if reader.available:
            return reader
    return None


def _update_manifest(out_dir: Path, summary: ThesisSummary) -> None:
    path = out_dir / MANIFEST_NAME
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"countries": {}}
    current["countries"][summary.country_code] = summary.model_dump(mode="json")
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_thesis(
    iso: str,
    technologies: Sequence[str],
    *,
    technologies_yaml: Path,
    experiments_yaml: Path,
    parameters_json: Path,
    methodology_md: Path,
    only: Sequence[str] | None = None,
    out_dir: Path | None = None,
) -> ThesisSummary:
    """Build the implemented thesis outputs of `iso`.

    Implements: M-F8-01, M-F8-02.

    Args:
        only: T-IDs to build (default: all implemented).
        out_dir: Default `outputs/thesis`.

    Raises:
        ThesisBuildError: an Essential T-ID has no output for the country.
        OutputNameError: `only` names something that is not a thesis output.
        KeyError: `only` names a thesis output without a script.
    """
    chosen = list(only) if only else list(SCRIPTS)
    for t_id in chosen:
        names.stem(t_id, "x")  # validates the ID
    unknown = [t for t in chosen if t not in SCRIPTS]
    if unknown:
        raise KeyError(f"no script for {unknown}; implemented: {sorted(SCRIPTS)}")
    parameters = load_parameters(parameters_json).countries.get(iso)
    technologies = tuple(technologies)
    ctx = BuildContext(
        iso=iso,
        technologies=technologies,
        reader=ArtifactReader(iso),
        other_scale=_other_scale(iso),
        out_dir=Path(out_dir) if out_dir else thesis_output_dir(),
        config_files={
            "technologies.yaml": technologies_yaml,
            "experiments.yaml": experiments_yaml,
            "parameters.json": parameters_json,
        },
        methodology_version=methodology_version(methodology_md),
        registry=load_technologies(technologies_yaml),
        experiments=load_experiments(experiments_yaml),
        country_params=parameters,
        test_values=is_test_build(parameters, technologies),
    )
    for t_id in chosen:
        try:
            SCRIPTS[t_id](ctx)
        except (ThesisValueError, NotBuilt) as exc:
            ctx.skip(t_id, "all", str(exc))
    summary = ThesisSummary(
        country_code=iso,
        scale=ctx.reader.scale_id,
        test_values=ctx.test_values,
        methodology_version=ctx.methodology_version,
        built={
            t: sorted({p.name for p in ctx.written.get(t, [])}) for t in chosen if t in ctx.written
        },
        not_built=[NotBuiltItem(t_id=t, item=i, reason=r) for t, i, r in ctx.not_built],
    )
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    _update_manifest(ctx.out_dir, summary)
    empty = [t for t in chosen if t not in names.OPTIONAL and t not in ctx.written]
    if empty:
        reasons = "; ".join(f"{t}: {i}: {r}" for t, i, r in ctx.not_built if t in empty)
        raise ThesisBuildError(f"{iso}: Essential outputs with nothing built: {empty}. {reasons}")
    return summary
