"""H5, climate pressure on the economic potential relative to the national target (M-F7-07; D-F7-050 to D-F7-053).

The rule is that of the thesis text `docs/thesis/hypotheses/H5_climate_threat_to_targets.tex` (METHODOLOGY 12.0.0). For one country, technology and
window, the economic domain `Omega_econ` is the set of cells of the F7 set (the like-for-like candidates of the central land scenario; climate-fragile
cells are kept) with `LCOE_i,f0 <= tau`, fixed across members. `E_0` is its annual energy at the reference member and `E_m` at member `m`, in
TWh/year; `G` is the national target in TWh/year (a target in GW is converted by `G = 8.76 * G_cap * CFbar`, `CFbar` the capacity-weighted reference
capacity factor of the cheapest cells of `Omega_econ` that reach `G_cap`); `H_0 = E_0 - G` is the slack.

  - H5a, resource: `Delta E = max(0, E_0 - min_m E_m)` and `R_loss = Delta E / H_0`.
  - H5b, exposure: a cell is exposed under member `m` when at least one hazard channel reaches its threshold (a union, so a cell with several
    channels above their thresholds counts once); `E_exp` is the largest, over the members that carry the hazard channel, of the energy of the
    exposed cells of `Omega_econ`, and `R_exp = E_exp / H_0`. The same statistic with the reference values of the indicators and the difference are
    reported.

With `lambda = 0.20` H5a holds when `R_loss >= lambda` and H5b when `R_exp >= lambda`; the verdict is supported, partially supported (resource),
partially supported (exposure) or not supported. Without a target the status is not testable; with `H_0 <= 0` it is target not met at reference and
the ratios are reported on `G` without a verdict. H5b is not available when no hazard member remains or a channel has no threshold, and then the
hypothesis has no verdict. The functions work on arrays: the pipeline builds the inputs from the F7 set and the tables of a land scenario.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from geofrea.robustness_analysis.thesis_tables import (
    REFERENCE_COLUMNS,
    ThesisTableError,
    exposed_flags,
    like_for_like_cells,
    merge_nominal_lcoe,
)

TWH_PER_GW_AT_FULL_LOAD = 8.76  # 8760 h / 1000: TWh/year of 1 GW at a capacity factor of 1
TOLERANCE = 1e-12  # a ratio within this of lambda is at lambda (the decision is `>=`)

PRIMARY = "primary"

TESTED = "tested"
NOT_TESTABLE = "not_testable"
TARGET_NOT_MET = "target_not_met_at_reference"

SUPPORTED = "supported"
PARTIAL_RESOURCE = "partially_supported_resource"
PARTIAL_EXPOSURE = "partially_supported_exposure"
NOT_SUPPORTED = "not_supported"

CHEAPEST_FIRST = "cheapest_cells_first"
WHOLE_DOMAIN = "whole_domain"
ENERGY_TARGET = "none (target in TWh/year)"

Conversion = Literal["cheapest_cells_first", "whole_domain"]


class H5Error(ValueError):
    """H5 cannot be computed from the inputs (A-09)."""


@dataclass(frozen=True)
class Exposure:
    """The exposed flags of the hazard members, by channel.

    Attributes:
        slots: Position, among the core members, of each hazard member (0-based, so the energy column of member `j` is `j + 1`).
        channels: The hazard channels, in the order of the flag arrays.
        absolute: `(hazard members, channels, cells)` True where the absolute indicator reaches the threshold of the channel.
        reference: Same shape, for the reference values of the indicators; False where the channel has no reference.
        has_reference: Per channel, whether it has a reference value of the same quantity.
        reason: Why H5b is not available, or None when it is.
        excluded: The hazard channels left out because their threshold is null (OQ-051); the others are the `channels` used.
    """

    slots: tuple[int, ...]
    channels: tuple[str, ...]
    absolute: np.ndarray
    reference: np.ndarray
    has_reference: tuple[bool, ...]
    reason: str | None = None
    excluded: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return self.reason is None and len(self.slots) > 0


def unavailable(reason: str, excluded: Sequence[str] = ()) -> Exposure:
    """An exposure that H5b cannot use, with the reason and the channels left out for want of a threshold."""
    empty = np.zeros((0, 0, 0), dtype=bool)
    return Exposure((), (), empty, empty, (), reason, tuple(excluded))


@dataclass(frozen=True)
class H5Inputs:
    """What H5 reads for one country, technology, window and land scenario; cells are the F7 set and members are the core members.

    Attributes:
        cell_id: Cell identifiers, sorted.
        capacity_mw: Capacity of each cell in the land scenario.
        cf: Reference capacity factor of each cell (member `m0`).
        energy_twh: `(cells, 1 + M)` annual energy in TWh/year; column 0 is the reference member, then the core members.
        lcoe: `(cells, 1 + M)` nominal LCOE at `s0` in USD/MWh (`inf` where the cell is infeasible in the member); column 0 is `f0`.
        members: The core members, in the order of the columns after the first.
        gcms: GCM of each core member.
        exposure: The exposed flags of the hazard members.
    """

    cell_id: np.ndarray
    capacity_mw: np.ndarray
    cf: np.ndarray
    energy_twh: np.ndarray
    lcoe: np.ndarray
    members: tuple[str, ...]
    gcms: tuple[str, ...]
    exposure: Exposure

    def __post_init__(self) -> None:
        n = self.cell_id.size
        m = len(self.members)
        if self.energy_twh.shape != (n, m + 1) or self.lcoe.shape != (n, m + 1):
            raise H5Error(
                "energy_twh and lcoe need one column for the reference and one per core member"
            )
        if self.capacity_mw.shape != (n,) or self.cf.shape != (n,) or len(self.gcms) != m:
            raise H5Error("the cell and member arrays disagree in length")
        if self.exposure.available and self.exposure.absolute.shape[2] != n:
            raise H5Error("the exposure flags do not cover the cells")


@dataclass(frozen=True)
class Target:
    """A national target: the value in its original unit, the unit (`GW` or `TWh/year`), the horizon year and the source (OQ-010)."""

    value: float | None
    unit: str | None = None
    horizon: int | None = None
    source: str | None = None


@dataclass(frozen=True)
class H5Variant:
    """The result of H5 for one setting; `variant` `primary` carries the verdict (D-F7-051)."""

    variant: str
    lam: float
    tau: float
    domain: str
    conversion: str
    excluded_gcms: tuple[str, ...]
    channels: tuple[str, ...]
    excluded_channels: tuple[str, ...]
    status: str
    verdict: str | None
    verdict_reason: str | None
    n_domain_cells: int
    domain_capacity_gw: float
    e0_twh: float
    target_value: float | None
    target_unit: str | None
    target_horizon: int | None
    target_source: str | None
    g_twh: float | None
    cf_bar: float | None
    target_exceeds_domain: bool
    h0_twh: float | None
    member_energy_twh: tuple[float, ...]
    delta_e_twh: float
    member_min: str
    r_loss: float | None
    h5a_holds: bool | None
    max_gain_twh: float
    median_change_twh: float
    exposure_available: bool
    exposure_reason: str | None
    e_exp_twh: float | None
    member_exp_max: str | None
    r_exp: float | None
    h5b_holds: bool | None
    e_exp_comparable_twh: float | None
    e_exp_reference_twh: float | None
    exposure_increment_twh: float | None
    reference_channels: tuple[str, ...]
    delta_e_over_g: float | None
    e_exp_over_g: float | None
    members: tuple[str, ...]
    exposed_by_member_twh: tuple[float, ...]
    exposed_reference_by_member_twh: tuple[float, ...]
    hazard_members: tuple[str, ...]


def economic_domain(lcoe: np.ndarray, tau: float) -> np.ndarray:
    """Cells with a finite nominal LCOE at most `tau` (the T-R12 criterion)."""
    return np.isfinite(lcoe) & (lcoe <= tau)


def convert_target(
    capacity_mw: np.ndarray,
    cf: np.ndarray,
    lcoe: np.ndarray,
    cell_id: np.ndarray,
    domain: np.ndarray,
    target_gw: float,
    conversion: Conversion = CHEAPEST_FIRST,
) -> tuple[float | None, float | None, bool]:
    """A target in GW as TWh/year, `G = 8.76 * G_cap * CFbar`, with `CFbar` and whether the target exceeds the capacity of the domain.

    Implements: M-F7-07 (H5, the conversion of a capacity target).

    `CFbar` is the capacity-weighted reference capacity factor of the cells of the domain taken in ascending order of `LCOE_i,f0` (ties by
    ascending `cell_id`, A-12) until their capacity reaches `target_gw`, the last cell with a fraction; a target above the capacity of the domain
    takes all of it. With `whole_domain` it is the capacity-weighted factor of the whole domain (the alternative of the sensitivity).

    Returns:
        `G` (None when the domain is empty and the target positive), `CFbar` (None when no capacity is taken) and the exceeds flag.
    """
    if target_gw < 0:
        raise H5Error("a national target cannot be negative")
    if target_gw == 0:
        return 0.0, None, False
    index = np.flatnonzero(domain)
    if index.size == 0:
        return None, None, True
    order = index[np.lexsort((cell_id[index], lcoe[index]))]
    capacity_gw = capacity_mw[order] / 1000.0
    total_gw = float(capacity_gw.sum())
    exceeds = target_gw > total_gw * (1.0 + TOLERANCE)
    if conversion == WHOLE_DOMAIN or exceeds:
        weights = capacity_gw
    else:
        before = np.concatenate([[0.0], np.cumsum(capacity_gw)[:-1]])
        weights = np.clip(target_gw - before, 0.0, capacity_gw)
    if weights.sum() <= 0:
        return None, None, exceeds
    cf_bar = float((weights * cf[order]).sum() / weights.sum())
    return TWH_PER_GW_AT_FULL_LOAD * target_gw * cf_bar, cf_bar, exceeds


def _exposed_energy(
    inputs: H5Inputs,
    domain: np.ndarray,
    keep: Sequence[int],
    channels: Sequence[int],
    *,
    reference: bool,
) -> np.ndarray:
    """Energy of the exposed cells of the domain for each kept hazard member, by union of the chosen channels."""
    exposure = inputs.exposure
    flags = exposure.reference if reference else exposure.absolute
    out = np.zeros(len(keep))
    for at, h in enumerate(keep):
        member_column = exposure.slots[h] + 1
        exposed = (
            flags[h][list(channels)].any(axis=0)
            if len(channels)
            else np.zeros(inputs.cell_id.size, dtype=bool)
        )
        out[at] = float(inputs.energy_twh[exposed & domain[:, member_column], member_column].sum())
    return out


def evaluate_h5(
    inputs: H5Inputs,
    target: Target,
    *,
    lam: float,
    tau: float,
    variant: str = PRIMARY,
    domain: Literal["fixed", "dynamic"] = "fixed",
    conversion: Conversion = CHEAPEST_FIRST,
    excluded_gcms: Sequence[str] = (),
    channels: Sequence[str] | None = None,
) -> H5Variant:
    """H5 for one setting.

    Implements: M-F7-07 (H5).

    Args:
        inputs: The arrays of one country, technology, window and land scenario.
        target: The national target of the technology.
        lam: The materiality threshold `lambda`.
        tau: The cost threshold of the economic domain, USD/MWh.
        variant: Name of the setting.
        domain: `fixed` (the cells with `LCOE_i,f0 <= tau`, for every member) or `dynamic` (the cells with `LCOE_i,(m,s0) <= tau`, per member).
        conversion: How a target in GW becomes TWh/year.
        excluded_gcms: GCMs left out of the members (the TCR-exception sensitivity).
        channels: The hazard channels used (default all), for the one-by-one sensitivity.

    Raises:
        H5Error: no member remains, a channel is unknown or the target is negative.
    """
    keep_members = [j for j, g in enumerate(inputs.gcms) if g not in set(excluded_gcms)]
    if not keep_members:
        raise H5Error("no core member remains")
    n_cells = inputs.cell_id.size
    f0 = economic_domain(inputs.lcoe[:, 0], tau)
    by_member = np.empty((n_cells, inputs.lcoe.shape[1]), dtype=bool)
    by_member[:, 0] = f0
    for column in range(1, inputs.lcoe.shape[1]):
        by_member[:, column] = (
            f0 if domain == "fixed" else economic_domain(inputs.lcoe[:, column], tau)
        )
    e0 = float(inputs.energy_twh[by_member[:, 0], 0].sum())
    energies = np.array(
        [
            float(inputs.energy_twh[by_member[:, j + 1], j + 1].sum())
            for j in range(len(inputs.members))
        ]
    )
    kept_energy = energies[keep_members]
    change = kept_energy - e0
    at_min = int(np.argmin(kept_energy))
    delta_e = max(0.0, e0 - float(kept_energy[at_min]))

    # the target and the slack
    g_twh: float | None
    cf_bar: float | None = None
    exceeds = False
    if target.value is None:
        g_twh = None
    elif target.unit == "TWh/year":
        g_twh = float(target.value)
    elif target.unit == "GW":
        g_twh, cf_bar, exceeds = convert_target(
            inputs.capacity_mw,
            inputs.cf,
            inputs.lcoe[:, 0],
            inputs.cell_id,
            f0,
            target.value,
            conversion,
        )
    else:
        raise H5Error(f"the unit of the target is {target.unit!r}; it must be GW or TWh/year")
    empty_domain_with_target = target.value is not None and target.unit == "GW" and g_twh is None

    # exposure
    exposure = inputs.exposure
    all_channels = exposure.channels
    chosen = list(range(len(all_channels)))
    if channels is not None:
        unknown = [c for c in channels if c not in all_channels]
        if unknown and exposure.available:
            raise H5Error(f"unknown hazard channels {unknown}")
        chosen = [all_channels.index(c) for c in channels if c in all_channels]
    keep_hazard = [h for h, s in enumerate(exposure.slots) if s in set(keep_members)]
    exposure_reason = exposure.reason
    if exposure.reason is None and not keep_hazard:
        exposure_reason = "no member that carries the hazard channel remains"
    available = exposure.reason is None and bool(keep_hazard)
    e_exp = e_cmp = e_ref = increment = None
    member_exp_max = None
    exposed_by_member: tuple[float, ...] = ()
    exposed_ref_by_member: tuple[float, ...] = ()
    reference_channels: tuple[str, ...] = ()
    if available:
        absolute = _exposed_energy(inputs, by_member, keep_hazard, chosen, reference=False)
        e_exp = float(absolute.max())
        member_exp_max = inputs.members[exposure.slots[keep_hazard[int(np.argmax(absolute))]]]
        exposed_by_member = tuple(float(x) for x in absolute)
        with_reference = [c for c in chosen if exposure.has_reference[c]]
        reference_channels = tuple(all_channels[c] for c in with_reference)
        if with_reference:
            comparable = _exposed_energy(
                inputs, by_member, keep_hazard, with_reference, reference=False
            )
            referenced = _exposed_energy(
                inputs, by_member, keep_hazard, with_reference, reference=True
            )
            e_cmp, e_ref = float(comparable.max()), float(referenced.max())
            increment = e_cmp - e_ref
            exposed_ref_by_member = tuple(float(x) for x in referenced)

    # the status and the verdict
    h0 = None if g_twh is None else e0 - g_twh
    r_loss = r_exp = None
    h5a = h5b = None
    d_over_g = x_over_g = None
    verdict = None
    reason: str | None = None
    if target.value is None:
        status = NOT_TESTABLE
        reason = "not testable: no national target (OQ-010)"
    elif empty_domain_with_target or (h0 is not None and h0 <= 0):
        status = TARGET_NOT_MET
        reason = (
            "target not met at reference: the economic domain is empty"
            if empty_domain_with_target
            else f"target not met at reference: E_0 {e0:.6g} does not exceed G {g_twh:.6g} TWh/year"
        )
        if g_twh is not None and g_twh > 0:
            d_over_g = delta_e / g_twh
            x_over_g = None if e_exp is None else e_exp / g_twh
    else:
        assert h0 is not None
        status = TESTED
        r_loss = delta_e / h0
        h5a = bool(r_loss >= lam - TOLERANCE)
        if e_exp is not None:
            r_exp = e_exp / h0
            h5b = bool(r_exp >= lam - TOLERANCE)
        if h5b is None:
            reason = f"H5b is not available: {exposure_reason}"
        else:
            verdict = (
                SUPPORTED
                if h5a and h5b
                else PARTIAL_RESOURCE
                if h5a
                else PARTIAL_EXPOSURE
                if h5b
                else NOT_SUPPORTED
            )
    return H5Variant(
        variant=variant,
        lam=lam,
        tau=tau,
        domain=domain,
        conversion=ENERGY_TARGET if target.unit != "GW" else conversion,
        excluded_gcms=tuple(excluded_gcms),
        channels=tuple(all_channels[c] for c in chosen) if available else (),
        excluded_channels=exposure.excluded,
        status=status,
        verdict=verdict,
        verdict_reason=reason,
        n_domain_cells=int(f0.sum()),
        domain_capacity_gw=float(inputs.capacity_mw[f0].sum() / 1000.0),
        e0_twh=e0,
        target_value=target.value,
        target_unit=target.unit,
        target_horizon=target.horizon,
        target_source=target.source,
        g_twh=g_twh,
        cf_bar=cf_bar,
        target_exceeds_domain=exceeds,
        h0_twh=h0,
        member_energy_twh=tuple(float(x) for x in energies),
        delta_e_twh=delta_e,
        member_min=inputs.members[keep_members[at_min]],
        r_loss=r_loss,
        h5a_holds=h5a,
        max_gain_twh=float(max(0.0, change.max())),
        median_change_twh=float(np.median(change)),
        exposure_available=available,
        exposure_reason=None if available else exposure_reason,
        e_exp_twh=e_exp,
        member_exp_max=member_exp_max,
        r_exp=r_exp,
        h5b_holds=h5b,
        e_exp_comparable_twh=e_cmp,
        e_exp_reference_twh=e_ref,
        exposure_increment_twh=increment,
        reference_channels=reference_channels,
        delta_e_over_g=d_over_g,
        e_exp_over_g=x_over_g,
        members=inputs.members,
        exposed_by_member_twh=exposed_by_member,
        exposed_reference_by_member_twh=exposed_ref_by_member,
        hazard_members=tuple(inputs.members[exposure.slots[h]] for h in keep_hazard)
        if available
        else (),
    )


def sensitivity_variants(
    inputs: H5Inputs,
    target: Target,
    primary: H5Variant,
    *,
    lam_sensitivity: float,
    tau_range: tuple[float, float] | None,
    tcr_exception_gcms: Sequence[str],
    alternative_targets: Sequence[Target] = (),
) -> list[H5Variant]:
    """The sensitivities of H5 beside the primary result (M-F7-07); none of them revises the verdict.

    The settings: `lambda` 0.10, `tau` at the ends of its sourced range, the dynamic economic domain, without the GCM that carries the TCR
    exception, the hazard channels one by one, the whole-domain conversion of a capacity target and the alternative official targets.
    """
    common = {"lam": primary.lam, "tau": primary.tau}
    out = [
        evaluate_h5(
            inputs,
            target,
            **{**common, "lam": lam_sensitivity},
            variant=f"lambda_{lam_sensitivity:.2f}",
        )
    ]
    if tau_range is not None:
        for name, value in (("tau_min", tau_range[0]), ("tau_max", tau_range[1])):
            out.append(evaluate_h5(inputs, target, lam=primary.lam, tau=float(value), variant=name))
    out.append(evaluate_h5(inputs, target, **common, domain="dynamic", variant="dynamic_domain"))
    if tcr_exception_gcms and any(g in set(tcr_exception_gcms) for g in inputs.gcms):
        out.append(
            evaluate_h5(
                inputs,
                target,
                **common,
                excluded_gcms=tuple(tcr_exception_gcms),
                variant="without_" + "_".join(tcr_exception_gcms),
            )
        )
    if inputs.exposure.available:
        for channel in inputs.exposure.channels:
            out.append(
                evaluate_h5(
                    inputs, target, **common, channels=(channel,), variant=f"channel_{channel}"
                )
            )
    if target.unit == "GW":
        out.append(
            evaluate_h5(
                inputs, target, **common, conversion=WHOLE_DOMAIN, variant="conversion_whole_domain"
            )
        )
    for at, alternative in enumerate(alternative_targets, start=1):
        out.append(evaluate_h5(inputs, alternative, **common, variant=f"target_alternative_{at}"))
    return out


def build_exposure(
    hazard,
    hazard_members: Sequence[tuple[int, str]],
    thresholds: Mapping[str, float | None],
    cell_ids: np.ndarray,
) -> Exposure:
    """The exposure of the hazard members over `cell_ids` from the rows of `hazard_context` and the thresholds of OQ-051.

    Implements: M-F7-07 (H5b), T-R10. A cell is exposed in a channel when the indicator is at least the threshold (`exposed_flags`, the
    calculation T-R10 uses). A channel with a null threshold is excluded and listed in `Exposure.excluded`; the others are used. H5b is not
    available when no channel has a threshold or there is no hazard member.

    Args:
        hazard: `hazard_context` rows (`cell_id`, `member`, the indicators and their `*_ref` values).
        hazard_members: `(position among the core members, member identifier)` of each member that carries the hazard channel.
        thresholds: Threshold per hazard channel; None is not yet sourced.
        cell_ids: The cells, in the order of the arrays of the inputs.

    Raises:
        ThesisTableError: a hazard member lacks hazard rows for cells of `cell_ids`.
    """
    nulls = tuple(name for name, value in thresholds.items() if value is None)
    if not hazard_members:
        return unavailable("no member of the window carries the hazard channel (L-021)", nulls)
    channels = tuple(name for name, value in thresholds.items() if value is not None)
    if not channels:
        return unavailable(
            f"no hazard channel has a threshold: {list(nulls)} are null (OQ-051)", nulls
        )
    has_reference = tuple(c in REFERENCE_COLUMNS for c in channels)
    haz = hazard.assign(member=hazard["member"].astype(str))
    absolute = np.zeros((len(hazard_members), len(channels), cell_ids.size), dtype=bool)
    reference = np.zeros_like(absolute)
    for h, (_, member) in enumerate(hazard_members):
        rows = haz[haz["member"] == member].set_index("cell_id")
        for c, channel in enumerate(channels):
            threshold = float(thresholds[channel])  # type: ignore[arg-type]
            absolute[h, c] = exposed_flags(rows, cell_ids, channel, threshold, "absolute", member)
            if has_reference[c]:
                reference[h, c] = exposed_flags(
                    rows, cell_ids, channel, threshold, "reference", member
                )
    return Exposure(
        tuple(s for s, _ in hazard_members),
        channels,
        absolute,
        reference,
        has_reference,
        excluded=nulls,
    )


def inputs_from_tables(
    potential: pd.DataFrame,
    lcoe_nominal: pd.DataFrame,
    members: Sequence[str],
    gcms: Sequence[str],
    reference: str,
    cf_min: float,
    scenario: str,
    *,
    hazard: pd.DataFrame | None = None,
    hazard_members: Sequence[tuple[int, str]] = (),
    thresholds: Mapping[str, float | None] | None = None,
) -> H5Inputs:
    """The inputs of H5 for one land scenario from the F5 rows and the F6 nominal LCOE, over the like-for-like cells of T-R12.

    Implements: M-F7-07 (H5, `Omega`), T-R12. The cells are those of `like_for_like_cells` (the F7 set of the scenario), so H5 and T-R12 share the
    domain, and the exposure is `build_exposure` (the exposed flags of T-R10). The exposure is not available when `hazard` is None, no member carries the
    hazard channel, a threshold is null or the hazard rows do not cover the cells of the scenario.

    Args:
        potential: F5 rows `cell_id, member, P_MW, CF, E_MWh` of the scenario.
        lcoe_nominal: `cell_id, member, lcoe_nominal` of the scenario (F6).
        members: The members of the window.
        gcms: The GCM of each member.
        reference: The reference member.
        cf_min: Minimum capacity factor.
        scenario: Name of the land scenario.
        hazard: `hazard_context` rows, or None.
        hazard_members: `(position among members, member identifier)` of the members that carry the hazard channel.
        thresholds: Exposure threshold per hazard channel (OQ-051).

    Raises:
        ThesisTableError: an F5 row has no F6 nominal LCOE.
    """
    table = merge_nominal_lcoe(potential, lcoe_nominal, scenario)
    wanted = [reference, *members]
    table = table[table["member"].isin(wanted)]
    cells = like_for_like_cells(table, members, reference, cf_min)
    table = table[table["cell_id"].isin(cells)]

    def wide(column: str) -> np.ndarray:
        frame = table.pivot(index="cell_id", columns="member", values=column)
        return frame.reindex(index=cells, columns=wanted).to_numpy(dtype="float64")

    at_reference = table[table["member"] == reference].set_index("cell_id").loc[cells]
    lcoe = wide("lcoe_nominal")
    # a cell-member below CF_min is infeasible, as in the evaluation (D-F7-007): it has no finite LCOE and is outside a dynamic domain
    lcoe = np.where(np.isfinite(lcoe) & (wide("CF") >= cf_min), lcoe, np.inf)
    if hazard is None or thresholds is None:
        exposure = unavailable("no hazard_context table")
    else:
        try:
            exposure = build_exposure(hazard, hazard_members, thresholds, cells)
        except ThesisTableError as exc:
            exposure = unavailable(str(exc))
    return H5Inputs(
        cell_id=cells,
        capacity_mw=at_reference["P_MW"].to_numpy(dtype="float64"),
        cf=at_reference["CF"].to_numpy(dtype="float64"),
        energy_twh=wide("E_MWh") / 1.0e6,
        lcoe=lcoe,
        members=tuple(members),
        gcms=tuple(gcms),
        exposure=exposure,
    )
