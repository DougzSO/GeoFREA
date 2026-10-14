"""H4, context-dependent dominance of the climate and the techno-economic axis: the axis displacements, the dominance ratio, the profile of a
country and technology and the verdict across countries (M-F7-06, M-F7-07; D-F7-046 to D-F7-049).

For one country and technology, each axis is introduced alone and the displacement it produces in the site ranking is the statistic of H3 on
the shortlist of that axis:

  - the climate axis keeps the parameters at their nominal values: `Z_clim_i = max over the core members of r_i,(m,s0)`;
  - the techno-economic axis keeps the climate at the reference member: `Z_tec_i = P90 over s >= 1 of r_i,(m0,s)`;
  - `S^a_k` is the `k` cells of the ranked set `I` with the lowest `Z^a_i` (ties by `cell_id`, D-F7-012) and
    `D_a = (sum of q_i over S^a_k with r^nom_i > k + m) / (sum of q_i over S^a_k)`, `r^nom_i` the rank within `I` by `LCOE_i,f0`.

`rho = D_clim / (D_clim + D_tec)` and the profile follow from the boundaries `lower` and `upper` (OQ-050, H4): No Displacement when
`D_clim + D_tec = 0`, Climate-Dominated above `upper`, Techno-Economic-Dominated below `lower`, Mixed between them, both boundaries
inclusive. The verdict of a technology needs the profiles of all the countries (`technology_verdict`): supported when one country is
Climate-Dominated and another Techno-Economic-Dominated, not supported when at least two countries have a profile and no such pair exists, not
testable when fewer than two do. Everything is a pure function of arrays over the F7 set in `cell_id` order.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.core.constants import H4_SENSITIVITY_BOUNDARIES, SENSITIVITY_TOP_K_PERCENT
from geofrea.robustness_analysis.h1_rank_robustness import tolerance_size
from geofrea.robustness_analysis.h3_robust_vs_nominal import capacity_share_beyond
from geofrea.robustness_analysis.rankings import order_by, ranks_from_order, take_top_k, top_k_size

PRIMARY = "primary"
CLIMATE_DOMINATED = "climate_dominated"
TECHNO_ECONOMIC_DOMINATED = "techno_economic_dominated"
MIXED = "mixed"
NO_DISPLACEMENT = "no_displacement"
PROFILES = (CLIMATE_DOMINATED, TECHNO_ECONOMIC_DOMINATED, MIXED, NO_DISPLACEMENT)
SUPPORTED = "supported"
NOT_SUPPORTED = "not_supported"
NOT_TESTABLE = "not_testable"
SENSITIVITY_TOLERANCE_MULTIPLES = (0.5, 2.0)  # m in {k/2, 2k}
_TOLERANCE = 1.0e-12  # a ratio within this of a boundary is at the boundary, which is Mixed


class H4Error(ValueError):
    """H4 cannot be computed from its inputs (A-09)."""


@dataclass(frozen=True)
class H4Inputs:
    """What H4 reads, over the F7 set in `cell_id` order and the `M` core members.

    Attributes:
        r_clim: `(n, M)` relative regret of each cell at `s0` in each core member (`h1_rank_robustness.climate_only_regret`).
        z_tec: `(n,)` the techno-economic score `P90 over s >= 1 of r at m0` (`evaluation.mr_tech`).
        z_joint: `(n,)` the primary robustness score `MR_i` (the joint shortlist of H3).
        lcoe: `(n,)` the levelised cost `LCOE_i,f0`.
        q: `(n,)` installable capacity of the central land scenario, MW.
        ranked: Boolean over the F7 set: the cell is not climate-fragile (the set `I`).
        sr: `(n,)` satisficing robustness for the tie-break of the joint order, or None.
        ssps: SSP of each member.
        gcms: GCM of each member.
    """

    r_clim: np.ndarray
    z_tec: np.ndarray
    z_joint: np.ndarray
    lcoe: np.ndarray
    q: np.ndarray
    ranked: np.ndarray
    sr: np.ndarray | None
    ssps: tuple[str, ...]
    gcms: tuple[str, ...]

    @property
    def n_cells(self) -> int:
        return int(self.ranked.size)


def profile_of(d_clim: float, d_tec: float, lower: float, upper: float) -> tuple[float | None, str]:
    """`(rho, profile)`: `rho = D_clim / (D_clim + D_tec)` (None when both are 0) and the profile, boundaries inclusive for Mixed."""
    d_sum = d_clim + d_tec
    if d_sum <= 0.0:
        return None, NO_DISPLACEMENT
    rho = d_clim / d_sum
    if rho > upper + _TOLERANCE:
        return rho, CLIMATE_DOMINATED
    if rho < lower - _TOLERANCE:
        return rho, TECHNO_ECONOMIC_DOMINATED
    return rho, MIXED


@dataclass(frozen=True)
class H4Variant:
    """The result of H4 for one country, technology and setting (the primary one, a sensitivity or a complementary reading)."""

    variant: str
    top_k_percent: float
    k: int
    m: int
    tolerance_multiple: float
    excluded_gcms: tuple[str, ...]
    ssp: str | None
    lower: float
    upper: float
    n_cells: int
    n_ranked: int
    top_k_truncated: bool
    clim_capacity_mw: float
    tec_capacity_mw: float
    d_clim: float
    d_tec: float
    d_sum: float
    rho: float | None
    profile: str
    d_joint: float
    distance_to_lower: float | None
    distance_to_upper: float | None


def evaluate_variant(
    inputs: H4Inputs,
    *,
    variant: str,
    lower: float,
    upper: float,
    tolerance_multiple: float,
    top_k_percent: float,
    exclude_gcms: Sequence[str] = (),
    only_ssp: str | None = None,
) -> H4Variant:
    """`D_clim`, `D_tec`, `rho` and the profile for one setting.

    Implements: M-F7-06, M-F7-07 (H4).

    Args:
        exclude_gcms: GCMs left out of the climate axis (the techno-economic axis and the joint shortlist do not use them).
        only_ssp: Keep only the members of this SSP in the climate axis (the reading by scenario).

    Raises:
        H4Error: the ranked set is empty, or the climate axis has no member left.
    """
    n = inputs.n_cells
    n_ranked = int(inputs.ranked.sum())
    if n_ranked == 0:
        raise H4Error("the ranked set is empty (every cell of the F7 set is climate-fragile)")
    keep = [
        j
        for j in range(len(inputs.gcms))
        if inputs.gcms[j] not in set(exclude_gcms)
        and (only_ssp is None or inputs.ssps[j] == only_ssp)
    ]
    if not keep:
        raise H4Error("no climate member is left for the climate axis")
    z_clim = np.where(inputs.ranked, inputs.r_clim[:, keep].max(axis=1), np.nan)
    z_tec = np.where(inputs.ranked, inputs.z_tec, np.nan)
    k = top_k_size(top_k_percent, n)
    m = tolerance_size(tolerance_multiple, k)
    nominal_rank = ranks_from_order(order_by(inputs.lcoe, candidates=inputs.ranked), n)
    clim_top = take_top_k(order_by(z_clim, candidates=inputs.ranked), k, n)
    tec_top = take_top_k(order_by(z_tec, candidates=inputs.ranked), k, n)
    joint_order = order_by(inputs.z_joint, candidates=inputs.ranked, descending_tiebreak=inputs.sr)
    joint_top = take_top_k(joint_order, k, n)
    d_clim = capacity_share_beyond(inputs.q, clim_top.mask, nominal_rank, k + m)
    d_tec = capacity_share_beyond(inputs.q, tec_top.mask, nominal_rank, k + m)
    d_joint = capacity_share_beyond(inputs.q, joint_top.mask, nominal_rank, k + m)
    rho, profile = profile_of(d_clim, d_tec, lower, upper)
    return H4Variant(
        variant=variant,
        top_k_percent=top_k_percent,
        k=k,
        m=m,
        tolerance_multiple=tolerance_multiple,
        excluded_gcms=tuple(sorted(exclude_gcms)),
        ssp=only_ssp,
        lower=lower,
        upper=upper,
        n_cells=n,
        n_ranked=n_ranked,
        top_k_truncated=clim_top.truncated or tec_top.truncated,
        clim_capacity_mw=float(inputs.q[clim_top.mask].sum()),
        tec_capacity_mw=float(inputs.q[tec_top.mask].sum()),
        d_clim=d_clim,
        d_tec=d_tec,
        d_sum=d_clim + d_tec,
        rho=rho,
        profile=profile,
        d_joint=d_joint,
        distance_to_lower=None if rho is None else abs(rho - lower),
        distance_to_upper=None if rho is None else abs(rho - upper),
    )


def sensitivity_variants(
    inputs: H4Inputs, primary: H4Variant, *, tcr_exception_gcms: Sequence[str]
) -> list[H4Variant]:
    """The complementary readings and mandatory sensitivities that one run can give, after the primary result.

    The climate axis by SSP, without the TCR-exception GCM (omitted when no core member carries it), `p_k` in {5, 10, 20} percent, `m` in
    {k/2, 2k}, and the boundaries {0.30, 0.70} and {0.45, 0.55} as descriptive variants. The 2071-2100 window and the 0.1 degree scale are
    separate runs of F7, each with its own primary row. A sensitivity never revises the verdict.
    """
    common = {
        "lower": primary.lower,
        "upper": primary.upper,
        "tolerance_multiple": primary.tolerance_multiple,
        "top_k_percent": primary.top_k_percent,
    }
    out: list[H4Variant] = []
    for ssp in sorted(set(inputs.ssps)):
        out.append(evaluate_variant(inputs, variant=f"climate_ssp_{ssp}", only_ssp=ssp, **common))
    present = sorted(set(tcr_exception_gcms) & set(inputs.gcms))
    if present:
        out.append(
            evaluate_variant(
                inputs, variant="without_" + "_".join(present), exclude_gcms=present, **common
            )
        )
    for percent in SENSITIVITY_TOP_K_PERCENT:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"top_k_percent_{percent:g}",
                **{**common, "top_k_percent": percent},
            )
        )
    for multiple in SENSITIVITY_TOLERANCE_MULTIPLES:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"tolerance_{multiple:g}k",
                **{**common, "tolerance_multiple": multiple},
            )
        )
    for lower, upper in H4_SENSITIVITY_BOUNDARIES:
        rho, profile = profile_of(primary.d_clim, primary.d_tec, lower, upper)
        out.append(
            dataclasses.replace(
                primary,
                variant=f"boundaries_{lower:.2f}_{upper:.2f}",
                lower=lower,
                upper=upper,
                profile=profile,
                distance_to_lower=None if rho is None else abs(rho - lower),
                distance_to_upper=None if rho is None else abs(rho - upper),
            )
        )
    return out


@dataclass(frozen=True)
class CountryProfile:
    """What the verdict reads of one country and technology: its profile and statistics, or why there is none (`unavailable`)."""

    country: str
    available: bool
    profile: str | None = None
    d_clim: float | None = None
    d_tec: float | None = None
    d_sum: float | None = None
    rho: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TechnologyVerdict:
    """The verdict of H4 for one technology and the count of countries by profile (unavailable ones counted apart)."""

    verdict: str
    reason: str | None
    n_countries: int
    n_available: int
    counts: Mapping[str, int]


def technology_verdict(profiles: Sequence[CountryProfile]) -> TechnologyVerdict:
    """The strict rule: supported with one Climate-Dominated and one Techno-Economic-Dominated country, not supported with at least two
    countries that have a profile and no such pair, not testable with fewer than two.

    Implements: M-F7-07 (H4).
    """
    seen = Counter(p.profile for p in profiles if p.available and p.profile is not None)
    counts = {name: seen.get(name, 0) for name in PROFILES}
    n_available = sum(counts.values())
    if counts[CLIMATE_DOMINATED] >= 1 and counts[TECHNO_ECONOMIC_DOMINATED] >= 1:
        verdict, reason = SUPPORTED, None
    elif n_available < 2:
        verdict = NOT_TESTABLE
        reason = (
            f"{n_available} of {len(profiles)} countries have a profile, at least two are needed"
        )
    else:
        verdict, reason = NOT_SUPPORTED, None
    return TechnologyVerdict(
        verdict=verdict,
        reason=reason,
        n_countries=len(profiles),
        n_available=n_available,
        counts=counts,
    )
