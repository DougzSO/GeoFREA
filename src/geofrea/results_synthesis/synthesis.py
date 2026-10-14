"""T-R8, the cross-country synthesis of the hypotheses: the structured profiles, the summary by hypothesis and the readable summary of a country
(M-F8-03; D-F8-014 to D-F8-016).

The synthesis reports what was observed and issues no aggregate verdict. It reads the persisted F7 tables (M-F8-01), never recomputes a quantity, and
builds, in this order:

  1. `hypothesis_profiles`: one structured record per country and technology (JSON with a `schema_version`) with the verdict of each hypothesis, the
     numbers it rests on, the range of every number across the sensitivity variants and the count of variants whose verdict differs from the primary
     one. It is the unit from which the thesis and, later, a per-country page of a platform are built;
  2. the summary by hypothesis and technology: the number of countries in each verdict class and the label `consistent`, `context-dependent` or
     `not assessable`, from the profiles of every country that has been built;
  3. a readable summary per country (Markdown and LaTeX).

A case without a verdict (no target, target not met at reference, no exposure, no tables) is not testable and never a disagreement.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from geofrea.core.config_schemas import SynthesisConfig
from geofrea.results_synthesis import names
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.output import (
    BuildContext,
    NotBuilt,
    latex_escape,
    write_table,
    write_text_output,
)
from geofrea.robustness_analysis.table_schemas import ROBUSTNESS_TABLE_SCHEMA_VERSION

T_R8 = "T-R8"
PROFILES_SCHEMA_VERSION = "1.0"
PROFILES_STEM = "hypothesis_profiles"
_VERSIONS = {ROBUSTNESS_TABLE_SCHEMA_VERSION}
HYPOTHESES = ("H1", "H2", "H3", "H4", "H5")
TESTABLE_VERDICTS = frozenset(
    {
        "supported",
        "partially_supported_core_stable",  # H1: only H1a holds
        "partially_supported_vulnerable",  # H1: only H1b holds
        "partially_supported_resource",  # H5: only H5a holds
        "partially_supported_exposure",  # H5: only H5b holds
        "partially_supported",  # H1 when the classes are not kept apart
        "not_supported",
    }
)
NO_VERDICT_CLASSES = (
    "not_testable",
    "target_not_met_at_reference",
    "exposure_not_available",
    "unavailable",
)
PROFILE_CLASSES = (
    "climate_dominated",
    "techno_economic_dominated",
    "mixed",
    "no_displacement",
)
VERDICT_COLUMNS = (
    "supported",
    "partially_supported_core_stable",
    "partially_supported_vulnerable",
    "partially_supported_resource",
    "partially_supported_exposure",
    "not_supported",
    *NO_VERDICT_CLASSES,
)

# What a profile holds for each hypothesis: the F7 summary table, the primary statistics (column, reference column, threshold column) and the
# descriptive numbers. H4 is read from `h4_country` (the country) and `h4_verdict` (the technology).
_SPECS: dict[str, dict] = {
    "H1": {
        "table": "h1_summary",
        "statistics": {
            "c_k": ("c_k", "reference", "alpha"),
            "v_k": ("v_k", None, "beta"),
        },
        "descriptive": ("k", "n_cells", "n_ranked", "core_size", "n_vulnerable"),
    },
    "H2": {
        "table": "h2_summary",
        "statistics": {
            "overlap": ("overlap", "overlap_ref", "gamma"),
            "robustness_penalty": ("robustness_penalty", None, None),
        },
        "descriptive": ("k", "n_ranked", "n_regions", "target_mw", "q_max_mw", "tv_distance"),
    },
    "H3": {
        "table": "h3_summary",
        "statistics": {
            "d": ("d", "d_ref", "delta"),
            "price_of_robustness": ("price_of_robustness", None, None),
            "benefit_of_robustness": ("benefit_of_robustness", None, None),
        },
        "descriptive": ("k", "m", "n_ranked", "robust_capacity_mw", "nominal_capacity_mw"),
    },
    "H5": {
        "table": "h5_summary",
        "statistics": {
            "r_loss": ("r_loss", None, "lam"),
            "r_exp": ("r_exp", None, "lam"),
            "e0_twh": ("e0_twh", None, None),
            "g_twh": ("g_twh", None, None),
            "h0_twh": ("h0_twh", None, None),
        },
        "descriptive": (
            "status",
            "target_value",
            "target_unit",
            "target_horizon",
            "conversion",
            "delta_e_twh",
            "e_exp_twh",
            "e_exp_reference_twh",
            "exposure_increment_twh",
            "n_domain_cells",
        ),
    },
}


def _clean(value: object) -> object:
    """A JSON-safe value: numpy scalars as Python ones, a missing value as null."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def verdict_class(hypothesis: str, row: pd.Series, separate: Sequence[str]) -> str:
    """The class of a case: the verdict, with the partial class of H1 split by the sub-hypothesis that holds when the configuration keeps them apart,
    or the reason there is no verdict (`not_testable`, `target_not_met_at_reference`, `exposure_not_available`)."""
    verdict = row.get("verdict")
    if hypothesis == "H5" and (verdict is None or pd.isna(verdict)):
        return "exposure_not_available" if row.get("status") == "tested" else str(row["status"])
    if verdict is None or pd.isna(verdict):
        return "not_testable"
    verdict = str(verdict)
    if verdict == "not_testable":
        return "not_testable"
    if hypothesis == "H1" and verdict == "partially_supported" and "H1" in separate:
        return (
            "partially_supported_core_stable"
            if bool(row["h1a_holds"])
            else "partially_supported_vulnerable"
        )
    return verdict


def _statistic(rows: pd.DataFrame, primary: pd.Series, column: str, reference, threshold) -> dict:
    values = pd.to_numeric(rows[column], errors="coerce").dropna()
    return {
        "value": _clean(primary[column]),
        "reference": None if reference is None else _clean(primary[reference]),
        "threshold": None if threshold is None else _clean(primary[threshold]),
        "range": {
            "min": _clean(values.min()) if len(values) else None,
            "max": _clean(values.max()) if len(values) else None,
        },
    }


def _variant_rows(
    ctx: BuildContext, hypothesis: str, technology: str, spec: dict
) -> tuple[pd.DataFrame, pd.Series] | None:
    """The rows over which a hypothesis is reported (the variants of the core window, the 2071-2100 window and the other cell scale) and the primary row.

    Returns None when the F7 table was not written or is empty (a null rule or parameter).
    """
    key = f"{spec['table']}_{technology}__core"
    if not ctx.reader.has(key):
        return None
    core = ctx.reader.table(key, _VERSIONS)
    if core.empty:
        return None
    core = core.assign(variant=core["variant"].astype(str))
    extra = []
    late_key = f"{spec['table']}_{technology}__sensitivity"
    if ctx.reader.has(late_key):
        late = ctx.reader.table(late_key, _VERSIONS)
        extra.append(late[late["primary"]].assign(variant="window_2071-2100", primary=False))
    if ctx.other_scale is not None and ctx.other_scale.has(key):
        other = ctx.other_scale.table(key, _VERSIONS)
        extra.append(
            other[other["primary"]].assign(
                variant=f"scale_{ctx.other_scale.scale_id}", primary=False
            )
        )
    rows = pd.concat([core, *[e for e in extra if not e.empty]], ignore_index=True)
    return rows, core[core["primary"]].iloc[0]


def _hypothesis_record(
    ctx: BuildContext, hypothesis: str, technology: str, separate: Sequence[str]
) -> dict:
    spec = _SPECS[hypothesis]
    found = _variant_rows(ctx, hypothesis, technology, spec)
    if found is None:
        return {
            "available": False,
            "class": "unavailable",
            "verdict": None,
            "reason": "the F7 table is absent or empty (a null rule or parameter)",
        }
    rows, primary = found
    classes = [verdict_class(hypothesis, r, separate) for _, r in rows.iterrows()]
    primary_class = verdict_class(hypothesis, primary, separate)
    changing = [
        str(v)
        for v, c, is_primary in zip(rows["variant"], classes, rows["primary"], strict=True)
        if not is_primary
        and primary_class in TESTABLE_VERDICTS
        and c in TESTABLE_VERDICTS
        and c != primary_class
    ]
    record = {
        "available": True,
        "class": primary_class,
        "verdict": primary_class if primary_class in TESTABLE_VERDICTS else None,
        "status": _clean(primary["status"]) if "status" in rows.columns else None,
        "reason": _clean(primary["verdict_reason"]) if "verdict_reason" in rows.columns else None,
        "statistics": {
            name: _statistic(rows, primary, column, reference, threshold)
            for name, (column, reference, threshold) in spec["statistics"].items()
        },
        "details": {c: _clean(primary[c]) for c in spec["descriptive"] if c in rows.columns},
        "n_variants": int(len(rows) - 1),
        "n_variants_changing_verdict": len(changing),
        "variants_changing_verdict": changing,
        "variant_classes": {str(v): c for v, c in zip(rows["variant"], classes, strict=True)},
    }
    return record


def _h4_record(ctx: BuildContext, technology: str) -> dict:
    key = f"h4_country_{technology}__core"
    if not ctx.reader.has(key):
        return {
            "available": False,
            "class": "unavailable",
            "verdict": None,
            "reason": "no h4_country table",
        }
    table = ctx.reader.table(key, _VERSIONS)
    if table.empty:
        return {
            "available": False,
            "class": "unavailable",
            "verdict": None,
            "reason": "the h4_country table is empty (a null rule or parameter)",
        }
    table = table.assign(variant=table["variant"].astype(str))
    primary = table[table["primary"]].iloc[0]
    variants = table[~table["primary"]]
    changing = [
        str(r["variant"]) for _, r in variants.iterrows() if r["profile"] != primary["profile"]
    ]
    return {
        "available": True,
        "profile": _clean(primary["profile"]),
        "class": _clean(primary["profile"]),
        "statistics": {
            name: {
                "value": _clean(primary[name]),
                "range": {
                    "min": _clean(pd.to_numeric(table[name], errors="coerce").min()),
                    "max": _clean(pd.to_numeric(table[name], errors="coerce").max()),
                },
            }
            for name in ("d_clim", "d_tec", "rho")
        },
        "boundaries": {"lower": _clean(primary["lower"]), "upper": _clean(primary["upper"])},
        "n_variants": len(variants),
        "n_variants_changing_verdict": len(changing),
        "variants_changing_verdict": changing,
        "variant_classes": {str(r["variant"]): _clean(r["profile"]) for _, r in table.iterrows()},
    }


def _h4_technology_verdict(ctx: BuildContext, technology: str) -> dict:
    """The verdict of H4 for the technology and the profile of every country, from the support phase `cross_country_h4`."""
    for reader in ctx.cross_country:
        key = f"h4_verdict_{technology}__core"
        if not reader.has(key):
            continue
        table = reader.table(key, _VERSIONS)
        total = table[table["kind"] == "technology"]
        if total.empty:
            continue
        countries = table[table["kind"] == "country"]
        return {
            "available": True,
            "verdict": _clean(total.iloc[0]["verdict"]),
            "countries_with_profile": _clean(total.iloc[0]["n_available"]),
            "profiles": {
                str(r["country"]): _clean(r["profile"]) if bool(r["available"]) else "unavailable"
                for _, r in countries.iterrows()
            },
        }
    return {
        "available": False,
        "verdict": None,
        "reason": "the support phase cross_country_h4 has not run",
        "profiles": {},
    }


def build_profiles(ctx: BuildContext) -> dict:
    """The structured profiles of the country: one record per technology (M-F8-03).

    Raises:
        NotBuilt: `experiments.yaml` has no `synthesis` block.
    """
    synthesis = ctx.experiments.synthesis
    separate = list(synthesis.partial_classes_separate)
    records = []
    for technology in ctx.technologies:
        try:
            robustness = ctx.reader.table(
                f"robustness_{technology}__core", _VERSIONS, columns=["cell_class"]
            )
        except MissingArtifactError as exc:
            ctx.skip(T_R8, f"{technology} profile", str(exc))
            continue
        hypotheses = {
            h: _hypothesis_record(ctx, h, technology, separate) for h in ("H1", "H2", "H3", "H5")
        }
        hypotheses["H4"] = _h4_record(ctx, technology)
        hypotheses["H4"]["technology_verdict"] = _h4_technology_verdict(ctx, technology)
        window = ctx.experiments.windows["core"]
        records.append(
            {
                "country": ctx.iso,
                "technology": technology,
                "window": f"{window['start_year']}-{window['end_year']}",
                "n_candidates": len(robustness),
                "n_f7_set": int(robustness["cell_class"].isin(["ranked", "climate_fragile"]).sum()),
                "k": hypotheses["H1"].get("details", {}).get("k")
                if hypotheses["H1"]["available"]
                else None,
                "hypotheses": {h: hypotheses[h] for h in HYPOTHESES},
            }
        )
    return {
        "schema_version": PROFILES_SCHEMA_VERSION,
        "country": ctx.iso,
        "scale": ctx.reader.scale_id,
        "methodology_version": ctx.methodology_version,
        "test_values": ctx.test_values,
        "records": records,
    }


def read_profiles(directory: Path) -> list[dict]:
    """The profile files of every country in `directory`, sorted by country; a file with another schema version is refused.

    Raises:
        NotBuilt: a profile file has an unknown schema version.
    """
    out = []
    for path in sorted(directory.glob(f"{names.stem(T_R8, PROFILES_STEM)}_*.json")):
        if path.name.endswith(".provenance.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != PROFILES_SCHEMA_VERSION:
            raise NotBuilt(
                f"{path.name}: schema version {payload.get('schema_version')!r}, expected {PROFILES_SCHEMA_VERSION}"
            )
        out.append(payload)
    return out


def label_of(classes: Sequence[str], synthesis: SynthesisConfig) -> str:
    """`consistent` when every testable case has the same class, `context-dependent` when they differ, `not assessable` with fewer than two.

    Implements: M-F8-03. A class without a verdict is not testable and never counts as a disagreement.
    """
    testable = [c for c in classes if c in TESTABLE_VERDICTS]
    labels = synthesis.labels
    if len(testable) < synthesis.min_testable_cases:
        return labels.not_assessable
    return labels.consistent if len(set(testable)) == 1 else labels.context_dependent


def summary_frame(
    profiles: Sequence[dict], technologies: Sequence[str], synthesis: SynthesisConfig
) -> pd.DataFrame:
    """The count of countries by class and the label, per technology and hypothesis; H4 shows its verdict and the profile counts."""
    rows = []
    for technology in technologies:
        cases = [
            (p["country"], r)
            for p in profiles
            for r in p["records"]
            if r["technology"] == technology
        ]
        for hypothesis in HYPOTHESES:
            classes = [r["hypotheses"][hypothesis]["class"] for _, r in cases]
            row: dict[str, object] = {
                "technology": technology,
                "hypothesis": hypothesis,
                "n_countries": len(cases),
                "n_testable": sum(c in TESTABLE_VERDICTS for c in classes),
            }
            if hypothesis == "H4":
                tech_verdict = next(
                    (
                        r["hypotheses"]["H4"]["technology_verdict"]
                        for _, r in cases
                        if r["hypotheses"]["H4"]["technology_verdict"].get("available")
                    ),
                    None,
                )
                row["n_testable"] = sum(c in PROFILE_CLASSES for c in classes)
                row["label"] = "comparative (verdict per technology)"
                row["verdict"] = None if tech_verdict is None else tech_verdict["verdict"]
                for c in PROFILE_CLASSES:
                    row[c] = classes.count(c)
                row["unavailable"] = classes.count("unavailable")
            else:
                row["label"] = label_of(classes, synthesis)
                row["verdict"] = None
                for c in VERDICT_COLUMNS:
                    row[c] = classes.count(c)
            rows.append(row)
    columns = [
        "technology", "hypothesis", "label", "verdict", "n_countries", "n_testable",
        *VERDICT_COLUMNS, *PROFILE_CLASSES,
    ]  # fmt: skip
    frame = pd.DataFrame(rows)
    for c in columns:
        if c not in frame:
            frame[c] = 0
    return frame[columns].fillna({c: 0 for c in (*VERDICT_COLUMNS, *PROFILE_CLASSES)})


_KEY_STATISTICS = {
    "H1": ("c_k", "v_k"),
    "H2": ("overlap", "robustness_penalty"),
    "H3": ("d", "price_of_robustness"),
    "H4": ("d_clim", "rho"),
    "H5": ("r_loss", "r_exp"),
}


def profiles_frame(profiles: Sequence[dict]) -> pd.DataFrame:
    """One row per country, technology and hypothesis: the class, the two key statistics with their range, and the variants that change the verdict."""
    rows = []
    for payload in profiles:
        for record in payload["records"]:
            for hypothesis in HYPOTHESES:
                h = record["hypotheses"][hypothesis]
                first, second = _KEY_STATISTICS[hypothesis]
                stats = h.get("statistics", {})

                def pick(name: str, stats=stats) -> dict:
                    return stats.get(name, {"value": None, "range": {"min": None, "max": None}})

                a, b = pick(first), pick(second)
                rows.append(
                    {
                        "country": record["country"],
                        "technology": record["technology"],
                        "hypothesis": hypothesis,
                        "class": h["class"],
                        "statistic_1": first,
                        "value_1": a["value"],
                        "min_1": a["range"]["min"],
                        "max_1": a["range"]["max"],
                        "statistic_2": second,
                        "value_2": b["value"],
                        "min_2": b["range"]["min"],
                        "max_2": b["range"]["max"],
                        "n_variants": h.get("n_variants"),
                        "n_variants_changing_verdict": h.get("n_variants_changing_verdict"),
                    }
                )
    frame = pd.DataFrame(rows)
    return frame.astype(
        {
            "value_1": "float64", "min_1": "float64", "max_1": "float64",
            "value_2": "float64", "min_2": "float64", "max_2": "float64",
            "n_variants": "Int64", "n_variants_changing_verdict": "Int64",
        }
    )  # fmt: skip


def _fmt(value: object, digits: int = 3) -> str:
    return (
        "n/a"
        if value is None
        else f"{value:.{digits}g}"
        if isinstance(value, float)
        else str(value)
    )


def _range_text(statistic: dict) -> str:
    low, high = statistic["range"]["min"], statistic["range"]["max"]
    if low is None or high is None:
        return ""
    return f" (range {_fmt(low)} to {_fmt(high)})"


def country_markdown(payload: dict) -> str:
    """The readable summary of a country: for each technology, the verdict of each hypothesis with its numbers and ranges."""
    lines = [f"# Hypothesis profiles: {payload['country']}", ""]
    if payload["test_values"]:
        lines += ["**TEST VALUES (synthetic fixture, not a result).**", ""]
    lines += [
        (
            f"METHODOLOGY {payload['methodology_version']}, scale {payload['scale']}. The verdicts are those of the primary setting; the ranges are over the "
            "sensitivity variants of each hypothesis. No verdict is combined with another."
        ),
        "",
    ]
    for record in payload["records"]:
        lines += [
            f"## {record['technology']}",
            "",
            f"Window {record['window']}: {record['n_candidates']} candidate cells, {record['n_f7_set']} in the F7 set, shortlist k = {_fmt(record['k'])}.",
            "",
        ]
        for hypothesis in HYPOTHESES:
            h = record["hypotheses"][hypothesis]
            if not h["available"]:
                lines.append(f"- **{hypothesis}**: not available ({h.get('reason')}).")
                continue
            stats = h["statistics"]
            numbers = "; ".join(
                f"{name} = {_fmt(s['value'])}{_range_text(s)}"
                for name, s in stats.items()
                if s["value"] is not None
            )
            extra = ""
            if hypothesis == "H4":
                verdict = h["technology_verdict"]
                extra = f" Technology verdict: {verdict.get('verdict') or 'not available'}."
            lines.append(
                f"- **{hypothesis}**: {h['class']}. {numbers}. "
                f"{h['n_variants_changing_verdict']} of {h['n_variants']} sensitivity variants change the verdict.{extra}"
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def country_latex(payload: dict) -> str:
    """The same summary as LaTeX itemised lists, one subsection per technology."""
    out = [
        f"\\section*{{Hypothesis profiles: {latex_escape(payload['country'])}}}",
        "",
    ]
    if payload["test_values"]:
        out += [r"\textbf{TEST VALUES (synthetic fixture, not a result).}", ""]
    for record in payload["records"]:
        out += [
            f"\\subsection*{{{latex_escape(record['technology'])}}}",
            (
                f"Window {latex_escape(record['window'])}: {record['n_candidates']} candidate cells, {record['n_f7_set']} in the F7 set, "
                f"shortlist $k={latex_escape(_fmt(record['k']))}$."
            ),
            r"\begin{itemize}",
        ]
        for hypothesis in HYPOTHESES:
            h = record["hypotheses"][hypothesis]
            if not h["available"]:
                out.append(
                    f"  \\item \\textbf{{{hypothesis}}}: not available ({latex_escape(h.get('reason'))})."
                )
                continue
            numbers = "; ".join(
                f"{latex_escape(name)} = {_fmt(s['value'])}{_range_text(s)}"
                for name, s in h["statistics"].items()
                if s["value"] is not None
            )
            out.append(
                f"  \\item \\textbf{{{hypothesis}}}: {latex_escape(h['class'])}. {numbers}. "
                f"{h['n_variants_changing_verdict']} of {h['n_variants']} variants change the verdict."
            )
        out += [r"\end{itemize}", ""]
    return "\n".join(out)


def t_r8(ctx: BuildContext) -> None:
    """T-R8: the structured profiles of the country, the profiles and the summary of all the countries built so far, and the readable summary.

    The profiles of the other countries are read from the thesis directory (`hypothesis_profiles_<ISO3>.json`): the directory is shared by the
    countries, so a build run after every country has been built shows all of them.
    """
    synthesis = ctx.experiments.synthesis
    ctx.begin()
    payload = build_profiles(ctx)
    if not payload["records"]:
        raise NotBuilt("no technology has the tables a profile needs")
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    write_text_output(
        ctx,
        T_R8,
        PROFILES_STEM,
        {"json": json.dumps(payload, indent=2, sort_keys=True) + "\n"},
        "Structured hypothesis profiles of the country, one record per technology: verdict and numbers of H1 to H5, their range over the sensitivity variants and the variants that change the verdict. No aggregate verdict.",
        per_country=True,
    )
    write_text_output(
        ctx,
        T_R8,
        "country_summary",
        {"md": country_markdown(payload), "tex": country_latex(payload)},
        "Readable summary of the hypothesis profiles of the country: the numbers of H1 to H5 and their ranges over the sensitivity variants.",
        per_country=True,
    )
    profiles = read_profiles(ctx.out_dir)
    countries = ", ".join(p["country"] for p in profiles)
    write_table(
        ctx,
        T_R8,
        "country_profiles",
        profiles_frame(profiles),
        f"Profile of each country and technology ({countries}): the class of each hypothesis, its two key statistics with the range over the sensitivity variants, and the number of variants that change the verdict. No score and no aggregate verdict.",
        per_country=False,
    )
    write_table(
        ctx,
        T_R8,
        "hypothesis_summary",
        summary_frame(profiles, ctx.technologies, synthesis),
        f"Cross-country summary by hypothesis and technology ({countries}): the number of countries in each verdict class and the pattern, labelled {synthesis.labels.consistent} (every testable case has the same verdict), {synthesis.labels.context_dependent} (the testable cases differ) or {synthesis.labels.not_assessable} (fewer than {synthesis.min_testable_cases} testable cases). The partial classes of H1 and of H5 are kept apart, a case without a verdict is not testable and is no disagreement, and H4 shows the verdict of the technology with the profiles of the countries.",
        per_country=False,
    )
