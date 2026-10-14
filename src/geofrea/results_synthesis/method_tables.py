"""T-M2 (exclusions, cost drivers, resource models, parameters with sources and tiers) and T-M3 (the futures design) from configuration.

Both read configuration and the `members` artifact of F4; no number is computed. A thesis build refuses a value that is a proxy or a test
value (D9, D-F8-006), and an uncertain parameter without a value or a range; a synthetic fixture is built as a test build, which stamps its
outputs "TEST VALUES".
"""

from __future__ import annotations

import pandas as pd

from geofrea.config_models.land_availability import Levels, Ranged
from geofrea.core.schemas import VerifiedValue
from geofrea.results_synthesis.members import members_table
from geofrea.results_synthesis.output import BuildContext, NotBuilt, write_table

T_M2, T_M3 = "T-M2", "T-M3"


class ThesisValueError(RuntimeError):
    """A value a thesis table would show is a proxy, a test value, or missing (D9; A-09)."""


def _verified(ctx: BuildContext, technology: str) -> dict[str, VerifiedValue]:
    if ctx.country_params is None:
        raise NotBuilt(f"{ctx.iso} has no block in parameters.json")
    params = getattr(ctx.country_params.technologies, technology)
    return {
        name: value
        for name in type(params).model_fields
        if isinstance(value := getattr(params, name), VerifiedValue)
    }


def check_values(ctx: BuildContext, technology: str) -> None:
    """Refuse proxy and test values (unless the build is a test build), and an uncertain parameter without a value or a range.

    Raises:
        ThesisValueError: listing every offending parameter.
    """
    values = _verified(ctx, technology)
    uncertain = set(ctx.registry.technologies[technology].uncertain_parameters)
    problems = []
    for name, v in sorted(values.items()):
        if v.proxy:
            problems.append(f"{name}: proxy value")
        if v.synthetic and not ctx.test_values:
            problems.append(f"{name}: test value in a thesis build")
        if name in uncertain and (v.value is None or v.range is None):
            problems.append(f"{name}: uncertain parameter without a value or a range")
    if problems:
        raise ThesisValueError(f"{ctx.iso} {technology}: " + "; ".join(problems))


def _flag(v: VerifiedValue) -> str:
    return "test value" if v.synthetic else ("proxy" if v.proxy else "")


def _land_rows(ctx: BuildContext, technology: str) -> list[dict]:
    land = ctx.experiments.land_availability.technologies.get(technology)
    if land is None:
        return []
    rows = []
    for name in type(land).model_fields:
        item = getattr(land, name)
        if isinstance(item, Ranged):
            rows.append(
                {
                    "category": "exclusion",
                    "name": name,
                    "nominal": item.nominal,
                    "low": item.low,
                    "high": item.high,
                    "unit": item.unit,
                    "source": item.source,
                    "tier": None,
                    "status": item.status,
                    "flag": "",
                }
            )
        elif isinstance(item, Levels):
            rows.append(
                {
                    "category": "exclusion",
                    "name": name,
                    "nominal": item.nominal,
                    "low": None,
                    "high": None,
                    "unit": "level",
                    "source": item.source,
                    "tier": None,
                    "status": item.status,
                    "flag": "",
                }
            )
    return rows


def t_m2(ctx: BuildContext) -> None:
    """T-M2, one table per technology: the land-availability parameters (E1 to E6 and the candidate filter), the structural choices of the
    registry (resource layers, capacity-factor model, exclusion and cost-driver lists) and every parameter with its source and tier.

    Implements: T-M2.
    """
    for technology in ctx.technologies:
        ctx.begin()
        try:
            check_values(ctx, technology)
            registry = ctx.registry.technologies[technology]
            values = _verified(ctx, technology)
        except NotBuilt as exc:
            ctx.skip(T_M2, technology, str(exc))
            continue
        rows = _land_rows(ctx, technology)
        for category, listing in (
            ("resource model", [registry.cf_model, *registry.resource_layers]),
            ("exclusion constraint", registry.exclusions),
            ("cost driver", registry.cost_drivers),
        ):
            rows += [
                {
                    "category": category,
                    "name": item,
                    "nominal": None,
                    "low": None,
                    "high": None,
                    "unit": None,
                    "source": None,
                    "tier": None,
                    "status": None,
                    "flag": "",
                }
                for item in listing
            ]
        for name, v in sorted(values.items()):
            rows.append(
                {
                    "category": "parameter",
                    "name": name,
                    "nominal": v.value,
                    "low": v.range.min if v.range else None,
                    "high": v.range.max if v.range else None,
                    "unit": v.unit,
                    "source": v.source,
                    "tier": v.tier,
                    "status": v.status,
                    "flag": _flag(v),
                }
            )
        frame = pd.DataFrame(rows).astype({"nominal": "object"})
        write_table(
            ctx,
            T_M2,
            "methods",
            frame,
            f"Method inputs for {technology}: land-availability parameters, resource and cost-driver choices, and parameters with sources and evidence tiers.",
            technology=technology,
        )


def t_m3(ctx: BuildContext) -> None:
    """T-M3: the uncertain parameters per technology with nominal value, range, distribution, source and tier, and the members of the futures design.

    Implements: T-M3.
    """
    for technology in ctx.technologies:
        ctx.begin()
        try:
            check_values(ctx, technology)
            values = _verified(ctx, technology)
        except NotBuilt as exc:
            ctx.skip(T_M3, technology, str(exc))
            continue
        rows = []
        for name in ctx.registry.technologies[technology].uncertain_parameters:
            v = values[name]
            assert v.range is not None  # checked above
            rows.append(
                {
                    "parameter": name,
                    "description": ctx.experiments.uncertain_parameters[name].description,
                    "unit": v.unit,
                    "nominal": v.value,
                    "min": v.range.min,
                    "max": v.range.max,
                    "distribution": v.range.distribution,
                    "range_source": v.range.source,
                    "range_tier": v.range.tier,
                    "nominal_source": v.source,
                    "nominal_tier": v.tier,
                    "flag": _flag(v),
                }
            )
        sampler = ctx.experiments.sampler
        write_table(
            ctx,
            T_M3,
            "uncertain_parameters",
            pd.DataFrame(rows),
            f"Futures design for {technology}: uncertain parameters, sampled by {sampler.method} (N = {sampler.initial_size}, seed {sampler.seed}); draws are independent (U-03).",
            technology=technology,
            extra={"sampler": sampler.model_dump(mode="json")},
        )
    ctx.begin()
    if not ctx.reader.has("members"):
        ctx.skip(T_M3, "members", "the F4 `members` artifact is not registered")
        return
    members = members_table(ctx.reader)
    write_table(
        ctx,
        T_M3,
        "members",
        members,
        "Climate members of the futures design: the reference member and the GCM, SSP and window of every projection member.",
    )
