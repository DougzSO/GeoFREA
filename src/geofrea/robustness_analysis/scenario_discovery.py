"""Scenario discovery on the futures: the outcome, the choice of the box, the special cases and the bootstrap (M-F7-08; D-F7-054 to D-F7-057).

The unit is the future `f = (m, s)` of the core window. Its outcome is the capacity share `V_f` of the nominal shortlist whose rank by relative
regret in `f` is beyond `k + m` (computed in `futures.py`); a future is a case of interest when `V_f >= theta`. `prim.run_prim` finds the peeling and
pasting trajectory; this module fixes, before the results are read, which box of the trajectory is the answer:

    box* = argmax density  among the boxes with coverage >= min_coverage and at most `max_restricted` restricted descriptors

(ties: the larger support, then the earlier box). When no future is a case of interest (`no_cases`), when every future is (`all_cases`) or when no box
meets the requirements (`no_eligible_box`) no box is chosen and the status says so. The bootstrap resamples the futures with replacement and repeats
the search with the same settings and rule; with the same seed the replicates are the same.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from geofrea.robustness_analysis.prim import PrimResult, PrimStep, run_prim

BOX_FOUND = "box_found"
NO_CASES = "no_cases"
ALL_CASES = "all_cases"
NO_ELIGIBLE_BOX = "no_eligible_box"
STATUSES = (BOX_FOUND, NO_CASES, ALL_CASES, NO_ELIGIBLE_BOX)
SEED_TAG = (
    0x5052494D  # "PRIM": separates the bootstrap stream from the other uses of the sampler seed
)
TOLERANCE = 1e-12  # a share within this of the threshold is at it (the case of interest is `>=`)


@dataclass(frozen=True)
class DiscoverySettings:
    """The settings of one search: the outcome threshold, the peeling fraction, the minimum support, the coverage requirement and the cap on descriptors."""

    outcome_threshold: float
    peel_alpha: float
    mass_min: float
    min_coverage: float
    max_restricted: int


@dataclass(frozen=True)
class Discovery:
    """The result of one search: its status, the trajectory and the box chosen (None unless the status is `box_found`)."""

    settings: DiscoverySettings
    status: str
    n_futures: int
    n_cases: int
    result: PrimResult | None
    chosen: PrimStep | None


def cases_of_interest(shares: np.ndarray, theta: float) -> np.ndarray:
    """1 where the capacity share beyond the tolerance `V_f` is at least `theta`, else 0."""
    return (np.asarray(shares, dtype="float64") >= theta - TOLERANCE).astype(int)


def select_box(result: PrimResult, min_coverage: float, max_restricted: int) -> PrimStep | None:
    """The box of the trajectory with the highest density among those with coverage of at least `min_coverage` and from one to `max_restricted` restricted descriptors.

    The box with every future restricts nothing and explains nothing, so it is never the answer. Ties go to the larger support, then to the earlier
    box. None when no box qualifies.
    """
    eligible = [
        s
        for s in result.steps
        if s.coverage >= min_coverage - TOLERANCE and 1 <= s.n_restricted <= max_restricted
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda s: (s.density, s.mass, -s.step))


def discover(x: pd.DataFrame, shares: np.ndarray, settings: DiscoverySettings) -> Discovery:
    """One search: the outcome from the shares, the PRIM trajectory and the box chosen, with the special cases.

    Implements: M-F7-08.

    Args:
        x: One row per future; float columns are real descriptors, string columns are categorical ones.
        shares: `V_f` of each future.
        settings: The thresholds and the choice rule.
    """
    y = cases_of_interest(shares, settings.outcome_threshold)
    n, cases = int(y.size), int(y.sum())
    if cases == 0:
        return Discovery(settings, NO_CASES, n, cases, None, None)
    if cases == n:
        return Discovery(settings, ALL_CASES, n, cases, None, None)
    result = run_prim(x, y, alpha=settings.peel_alpha, mass_min=settings.mass_min)
    chosen = select_box(result, settings.min_coverage, settings.max_restricted)
    status = BOX_FOUND if chosen is not None else NO_ELIGIBLE_BOX
    return Discovery(settings, status, n, cases, result, chosen)


def derive_seed(sampler_seed: int) -> int:
    """The seed of the bootstrap, derived from the seed of the sampler (recorded in the provenance of the tables)."""
    return int(np.random.SeedSequence([int(sampler_seed), SEED_TAG]).generate_state(1)[0])


def restricted_descriptors(discovery: Discovery) -> list[str]:
    """The descriptors that the chosen box restricts (its limits are inside those of the box with every future)."""
    if discovery.chosen is None or discovery.result is None:
        return []
    first, step = discovery.result.steps[0], discovery.chosen
    names = [
        c
        for c in discovery.result.real_descriptors
        if step.lower[c] > first.lower[c] or step.upper[c] < first.upper[c]
    ]
    names += [
        c
        for c in discovery.result.categorical_descriptors
        if set(step.categories[c]) != set(first.categories[c])
    ]
    return names


def bootstrap(
    x: pd.DataFrame,
    shares: np.ndarray,
    settings: DiscoverySettings,
    *,
    replicates: int,
    seed: int,
    percentiles: tuple[float, float],
) -> pd.DataFrame:
    """The stability of the box: the search repeated on `replicates` resamples of the futures with replacement.

    Implements: M-F7-08.

    Returns:
        One row per quantity: `kind` is `density`, `coverage` or `mass` (the percentiles over the replicates that found a box), `lower` or `upper`
        (the percentiles of the bound of a real descriptor over the replicates that restrict it), `category` (the share of the replicates that
        restrict the descriptor that keep the category, in `frequency`), `restriction` (the share of the replicates that found a box that restrict
        the descriptor) or `status` (the share of all replicates in each status). `p_low`, `p50` and `p_high` are the percentiles; `n_used` the number
        of replicates behind the row.
    """
    shares = np.asarray(shares, dtype="float64")
    rng = np.random.default_rng(seed)
    runs: list[Discovery] = []
    for _ in range(replicates):
        pick = rng.integers(0, len(x), len(x))
        runs.append(discover(x.iloc[pick].reset_index(drop=True), shares[pick], settings))
    low, high = percentiles
    rows: list[dict] = []

    def row(
        kind: str, name: str, level: str, values: Sequence[float], frequency=None, n_used=None
    ) -> None:
        values = np.asarray(values, dtype="float64")
        have = values.size > 0
        rows.append(
            {
                "kind": kind,
                "name": name,
                "level": level,
                "p_low": float(np.percentile(values, low)) if have else np.nan,
                "p50": float(np.percentile(values, 50)) if have else np.nan,
                "p_high": float(np.percentile(values, high)) if have else np.nan,
                "frequency": np.nan if frequency is None else float(frequency),
                "n_used": int(values.size if n_used is None else n_used),
            }
        )

    found = [d for d in runs if d.status == BOX_FOUND]
    for kind in ("density", "coverage", "mass"):
        row(kind, "", "", [getattr(d.chosen, kind) for d in found])
    for status in STATUSES:
        row(
            "status",
            status,
            "",
            [],
            sum(d.status == status for d in runs) / max(len(runs), 1),
            len(runs),
        )
    restricted = [set(restricted_descriptors(d)) for d in found]
    reals = list(x.select_dtypes(include="float").columns)
    others = [c for c in x.columns if c not in reals]
    for name in [*reals, *others]:
        used = [i for i, r in enumerate(restricted) if name in r]
        row("restriction", name, "", [], len(used) / len(found) if found else np.nan, len(found))
        if name in reals:
            row("lower", name, "", [found[i].chosen.lower[name] for i in used])
            row("upper", name, "", [found[i].chosen.upper[name] for i in used])
        else:
            for level in sorted(x[name].astype(str).unique()):
                kept = [level in found[i].chosen.categories.get(name, ()) for i in used]
                row("category", name, level, [], np.mean(kept) if kept else np.nan, len(used))
    return pd.DataFrame(rows)
