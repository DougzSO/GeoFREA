"""What every thesis script shares: the build context, the writers and the provenance file (M-F8-01, M-F8-02; D-F8-004, D-F8-005).

A table is written as CSV and LaTeX (booktabs), a figure as PNG and PDF, and each output gets `<stem>.provenance.json` with the manifest
keys and SHA-256 of the artifacts it read, the hashes of the configuration files, the METHODOLOGY version, the scale and the caption. The
provenance holds no time and no machine path, so the same inputs give the same files (A-02). A build with test values stamps
"TEST VALUES" on the caption and in the provenance (D9).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.schemas import CountryParams
from geofrea.results_synthesis import names
from geofrea.results_synthesis.inputs import ArtifactReader, sha256_of
from geofrea.results_synthesis.style import save_figure

TEST_VALUES_STAMP = "TEST VALUES (synthetic fixture, not a result). "
_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


class NotBuilt(Exception):
    """An output cannot be built for this country, with the reason (D7: reported, never hidden)."""


@dataclass
class BuildContext:
    """Everything a script needs.

    Attributes:
        iso: Country code.
        technologies: The technologies of the run.
        reader: Artifacts of the active scale.
        other_scale: Reader of the other scale (the 0.1 degree check of V-07), or None when no such manifest exists.
        cross_country: Readers of the manifests of the support phase `cross_country_h4` (one per scale that has one), empty when it has not run.
        out_dir: `outputs/thesis`.
        config_files: Name -> path of the configuration files read (hashed into the provenance).
        methodology_version: Version of `docs/METHODOLOGY.md`.
        registry: `technologies.yaml`.
        experiments: `experiments.yaml`.
        country_params: The country's block of `parameters.json`, or None when it has none.
        test_values: The country is a synthetic fixture: its values are test values (D9).
        written: Files written so far, by T-ID.
        not_built: `(T-ID, item, reason)` of what could not be built.
    """

    iso: str
    technologies: tuple[str, ...]
    reader: ArtifactReader
    other_scale: ArtifactReader | None
    out_dir: Path
    config_files: dict[str, Path]
    methodology_version: str
    registry: TechnologiesFile
    experiments: ExperimentsFile
    country_params: CountryParams | None
    test_values: bool
    written: dict[str, list[Path]] = field(default_factory=dict)
    not_built: list[tuple[str, str, str]] = field(default_factory=list)
    cross_country: tuple[ArtifactReader, ...] = ()

    def begin(self) -> None:
        """Start a group of outputs: from here on, the provenance lists only the artifacts read after this call."""
        self.reader.used.clear()
        if self.other_scale is not None:
            self.other_scale.used.clear()
        for reader in self.cross_country:
            reader.used.clear()

    def skip(self, t_id: str, item: str, reason: str) -> None:
        """Record that `item` of `t_id` was not built and why."""
        self.not_built.append((t_id, item, reason))

    def caption(self, text: str) -> str:
        return (TEST_VALUES_STAMP if self.test_values else "") + text


def latex_escape(text: str) -> str:
    return "".join(_LATEX_SPECIAL.get(c, c) for c in str(text))


def _latex_cell(value: object) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    return latex_escape(value)


def latex_table(frame: pd.DataFrame, caption: str, label: str) -> str:
    """A booktabs table: columns left-aligned for text and right-aligned for numbers, missing values as `--`."""
    align = "".join(
        "r" if pd.api.types.is_numeric_dtype(frame[c]) and frame[c].dtype != bool else "l"
        for c in frame.columns
    )
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        rf"\caption{{{latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{align or 'l'}}}",
        r"\toprule",
        " & ".join(latex_escape(c) for c in frame.columns) + r" \\",
        r"\midrule",
    ]
    lines += [
        " & ".join(_latex_cell(v) for v in row) + r" \\"
        for row in frame.astype(object).itertuples(index=False, name=None)
    ]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def _provenance(
    ctx: BuildContext, t_id: str, files: list[Path], caption: str, extra: dict | None
) -> dict:
    payload = {
        "output": t_id,
        "files": sorted(p.name for p in files),
        "caption": caption,
        "country": ctx.iso,
        "scale": ctx.reader.scale_id,
        "methodology_version": ctx.methodology_version,
        "test_values": ctx.test_values,
        "artifacts_read": dict(sorted(ctx.reader.used.items())),
        "config_files_read": {n: sha256_of(p) for n, p in sorted(ctx.config_files.items())},
    }
    if ctx.other_scale is not None and ctx.other_scale.used:
        payload["artifacts_read_other_scale"] = {
            "scale": ctx.other_scale.scale_id,
            **dict(sorted(ctx.other_scale.used.items())),
        }
    used_cross = {
        reader.scale_id: dict(sorted(reader.used.items()))
        for reader in ctx.cross_country
        if reader.used
    }
    if used_cross:
        payload["artifacts_read_cross_country"] = used_cross
    if extra:
        payload.update(extra)
    return payload


def _write_provenance(ctx: BuildContext, stem: str, payload: dict) -> Path:
    path = ctx.out_dir / f"{stem}.provenance.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_table(
    ctx: BuildContext,
    t_id: str,
    what: str,
    frame: pd.DataFrame,
    caption: str,
    *,
    technology: str | None = None,
    per_country: bool = True,
    latex: bool = True,
    extra: dict | None = None,
) -> list[Path]:
    """Write `frame` as `<stem>.csv` and `<stem>.tex` with a provenance file; an empty frame is written with its header (D7)."""
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    stem = names.stem(t_id, what, ctx.iso if per_country else None, technology)
    text = ctx.caption(caption)
    csv = ctx.out_dir / f"{stem}.csv"
    frame.to_csv(csv, index=False, lineterminator="\n", float_format="%.10g")
    files = [csv]
    if latex:
        tex = ctx.out_dir / f"{stem}.tex"
        tex.write_text(latex_table(frame, text, f"tab:{stem}"), encoding="utf-8", newline="\n")
        files.append(tex)
    files.append(_write_provenance(ctx, stem, _provenance(ctx, t_id, files, text, extra)))
    ctx.written.setdefault(t_id, []).extend(files)
    return files


def write_figure(
    ctx: BuildContext,
    t_id: str,
    what: str,
    draw: Callable[[], object],
    caption: str,
    *,
    technology: str | None = None,
    per_country: bool = True,
    extra: dict | None = None,
) -> list[Path]:
    """Save the figure that `draw()` returns as `<stem>.png` and `<stem>.pdf` with a provenance file."""
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    stem = names.stem(t_id, what, ctx.iso if per_country else None, technology)
    text = ctx.caption(caption)
    files = save_figure(draw(), ctx.out_dir / stem)
    files.append(_write_provenance(ctx, stem, _provenance(ctx, t_id, files, text, extra)))
    ctx.written.setdefault(t_id, []).extend(files)
    return files


_VERSION = re.compile(r"^\| Version \| (\d+\.\d+\.\d+) \|", re.MULTILINE)


def methodology_version(methodology_md: Path) -> str:
    """The version in the header table of METHODOLOGY."""
    match = _VERSION.search(Path(methodology_md).read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{methodology_md} has no version row")
    return match.group(1)
