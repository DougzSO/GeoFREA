"""The F7 set and the classes of the candidate cells (M-F7-01; D-F7-006, D-F7-007, D-F7-011).

The candidates `C` are the cells of the central land scenario. A candidate is

  - `climate_data_invalid` when it is missing from `m0` or from some member of the window (a cell-member masked by M-F4-07 has no F5 row,
    D-F5-006); it is counted and mapped, never ranked, and has no regret;
  - `infeasible_at_f0` when it is present everywhere but `CF(m0, s0) < CF_min` or its nominal energy is zero;
  - in the F7 set `S7` otherwise. Inside `S7`, a cell with `CF(m, s0) < CF_min` in at least one member of the window is `climate_fragile` (it
    is reported with the members in which it fails and is not ranked by `MR`); the others are `ranked`.

Feasibility is evaluated on the capacity factor F5 stores for the member at the nominal parameters, not on the draws (D-F7-007).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.lcoe_modeling.inputs import MemberCells
from geofrea.robustness_analysis.evaluator import MemberWorld

RANKED = "ranked"
CLIMATE_FRAGILE = "climate_fragile"
CLIMATE_DATA_INVALID = "climate_data_invalid"
INFEASIBLE_AT_F0 = "infeasible_at_f0"
CLASSES = (RANKED, CLIMATE_FRAGILE, CLIMATE_DATA_INVALID, INFEASIBLE_AT_F0)


class CellSetError(ValueError):
    """The member tables cannot be turned into an F7 set (A-09)."""


@dataclass(frozen=True)
class CellSet:
    """The classes of the candidates and the member inputs restricted to the F7 set.

    Attributes:
        candidate_ids: Every candidate cell, sorted.
        classes: The class of each candidate (see `CLASSES`).
        f7_ids: The F7 set, sorted; the order of every per-cell array of the evaluation.
        f7_position: For each candidate, its index in `f7_ids` or -1.
        fails: `(n_f7, n_core)` True where `CF(m, s0) < CF_min` in a core member.
        reference: The reference member over the F7 set.
        core: The core members over the F7 set, in the order given.
    """

    candidate_ids: np.ndarray
    classes: np.ndarray
    f7_ids: np.ndarray
    f7_position: np.ndarray
    fails: np.ndarray
    reference: MemberWorld
    core: tuple[MemberWorld, ...]
    p_mw: np.ndarray

    @property
    def n_f7(self) -> int:
        return int(self.f7_ids.size)

    @property
    def fragile(self) -> np.ndarray:
        """Over the F7 set: cells that fail `CF_min` in at least one core member."""
        return self.fails.any(axis=1)

    @property
    def ranked(self) -> np.ndarray:
        """Over the F7 set: cells that are not climate-fragile."""
        return ~self.fragile

    def failing_members(self) -> list[list[str]]:
        """Over the F7 set: the core members in which each cell fails `CF_min`."""
        names = [w.member for w in self.core]
        return [[names[j] for j in np.flatnonzero(row)] for row in self.fails]

    def counts(self) -> dict[str, int]:
        return {name: int((self.classes == name).sum()) for name in CLASSES}


def build_cell_set(
    candidate_ids: np.ndarray,
    members: Mapping[str, MemberCells],
    reference: str,
    core: Sequence[str],
    cf_min: float,
) -> CellSet:
    """Classify the candidates and restrict every member to the F7 set.

    Implements: M-F7-01, D-F5-006.

    Args:
        candidate_ids: Cell identifiers of the candidates of the central scenario.
        members: The cells of each member that has an F5 row (`read_member_inputs`), including `reference` and the core members.
        reference: Identifier of `m0`.
        core: Identifiers of the members of the window, in the order the results use.
        cf_min: The minimum capacity factor of a feasible cell-member.

    Raises:
        CellSetError: the reference member has no rows, a member is repeated, or a member has a cell the candidates lack.
    """
    candidate_ids = np.unique(np.asarray(candidate_ids, dtype="int64"))
    if reference not in members:
        raise CellSetError(f"the reference member {reference} has no F5 rows")
    if len(set(core)) != len(core):
        raise CellSetError("a core member is listed twice")
    wanted = [reference, *core]
    for name in wanted:
        if name in members and not np.isin(members[name].cell_id, candidate_ids).all():
            raise CellSetError(f"member {name} has cells that are not candidates")
    present = np.isin(candidate_ids, members[reference].cell_id)
    for name in core:
        present &= np.isin(candidate_ids, members[name].cell_id) if name in members else False
    ref = members[reference]
    at_ref = np.searchsorted(ref.cell_id, candidate_ids[present])
    ok_ref = (ref.cf[at_ref] >= cf_min) & (ref.cells.energy_mwh[at_ref] > 0)
    in_f7 = np.zeros(candidate_ids.size, dtype=bool)
    in_f7[np.flatnonzero(present)[ok_ref]] = True
    classes = np.full(candidate_ids.size, CLIMATE_DATA_INVALID, dtype=object)
    classes[present] = INFEASIBLE_AT_F0
    f7_ids = candidate_ids[in_f7]
    position = np.full(candidate_ids.size, -1, dtype="int64")
    position[in_f7] = np.arange(f7_ids.size)
    fails = np.zeros((f7_ids.size, len(core)), dtype=bool)
    worlds: list[MemberWorld] = []
    for j, name in enumerate(core):
        item = members.get(name)
        if (
            item is None
        ):  # a member with no rows at all: no candidate is present everywhere, the F7 set is empty
            worlds.append(
                MemberWorld(member=name, cells=ref.cells.take(slice(0, 0)), floor=np.zeros(0))
            )
            continue
        index = np.searchsorted(item.cell_id, f7_ids)
        fails[:, j] = item.cf[index] < cf_min
        worlds.append(
            MemberWorld(
                member=name,
                cells=item.cells.take(index),
                floor=np.where(fails[:, j], np.inf, 0.0),
            )
        )
    index_ref = np.searchsorted(ref.cell_id, f7_ids)
    reference_world = MemberWorld(
        member=reference, cells=ref.cells.take(index_ref), floor=np.zeros(f7_ids.size)
    )
    classes[in_f7] = RANKED
    fragile_ids = f7_ids[fails.any(axis=1)]
    classes[np.isin(candidate_ids, fragile_ids)] = CLIMATE_FRAGILE
    return CellSet(
        candidate_ids=candidate_ids,
        classes=classes,
        f7_ids=f7_ids,
        f7_position=position,
        fails=fails,
        reference=reference_world,
        core=tuple(worlds),
        p_mw=reference_world.cells.p_mw,
    )
