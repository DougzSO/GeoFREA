"""The scale of a run: the size of the decision cell (M-F3-06, M-F4-04, V-07; D-F3-013, D-F4-020).

The cell size is a parameter of the run. The default is the 0.05 degree cell of S-06 (`constants.CELL_DEG`, 5 x 5 pixels of the 0.01
degree analysis grid); the scale check of V-07 runs the same code on 0.1 degree cells (10 x 10 pixels). Nothing branches on the scale:
the functions that need the cell size read the active scale, and the only other consequence is where the files go (A-08): the phases
that depend on the cell size write under `<phase>__<scale id>` and the manifest is `manifest__<scale id>.json`, so a 0.1 degree run
never overwrites a 0.05 degree result. The pixel-level phases (F1 to F2b) and `external_inputs` do not depend on the cell size and
keep their directories.

The active scale is process-wide state set once by the entry point (`use_scale`), the same way the data directory is read from the
environment (`core/paths.py`); it is not a hidden input of a computation, because every cell table carries the lattice it was built
on in its `row`, `col` and `cell_id`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from geofrea.core.constants import CELL_DEG, CELL_NESTING_PIXELS


class UnknownScaleError(ValueError):
    """The requested scale is not one of the registered ones (A-09)."""


@dataclass(frozen=True)
class CellScale:
    """One scale: the cell side as a multiple of the default cell.

    Args:
        scale_id: Name used in directory and file names, for example `0p1deg`.
        factor: Cell side in units of the default cell (1 for 0.05 degree, 2 for 0.1 degree).
    """

    scale_id: str
    factor: int

    @property
    def cell_deg(self) -> float:
        """Cell side, degrees (EPSG:4326)."""
        return CELL_DEG * self.factor

    @property
    def nesting_pixels(self) -> int:
        """Pixels of the analysis grid along one cell side."""
        return CELL_NESTING_PIXELS * self.factor

    @property
    def n_cols(self) -> int:
        """Columns of the global cell lattice."""
        return round(360.0 / self.cell_deg)

    @property
    def n_rows(self) -> int:
        """Rows of the global cell lattice."""
        return round(180.0 / self.cell_deg)

    @property
    def is_default(self) -> bool:
        return self is DEFAULT_SCALE or self == DEFAULT_SCALE


DEFAULT_SCALE = CellScale("0p05deg", 1)
SCALES: dict[str, CellScale] = {s.scale_id: s for s in (DEFAULT_SCALE, CellScale("0p1deg", 2))}

# Phases whose output depends on the cell size: F3 onward, their maps and the overview (A-08).
SCALE_DEPENDENT_PHASES = frozenset(
    {
        "land_eligibility",
        "climate_forcing",
        "hazard_context",
        "climate_maps",
        "overview",
        "technical_potential",
        "potential_maps",
        "lcoe_modeling",
        "sample_size_convergence",
        "lcoe_maps",
        "robustness_analysis",
        "robustness_maps",
        "external_validation",
    }
)

_active: CellScale = DEFAULT_SCALE


def get_scale(scale_id: str) -> CellScale:
    """The registered scale called `scale_id`.

    Raises:
        UnknownScaleError: not registered.
    """
    try:
        return SCALES[scale_id]
    except KeyError:
        raise UnknownScaleError(f"unknown scale {scale_id!r}; known: {sorted(SCALES)}") from None


def active_scale() -> CellScale:
    """The scale of the run in progress (the default one outside `use_scale`)."""
    return _active


@contextmanager
def use_scale(scale: str | CellScale) -> Iterator[CellScale]:
    """Run the body at `scale`; the previous scale is restored on exit."""
    global _active
    chosen = get_scale(scale) if isinstance(scale, str) else scale
    previous, _active = _active, chosen
    try:
        yield chosen
    finally:
        _active = previous


def phase_directory_name(phase: str) -> str:
    """The directory name of a phase under `outputs/<ISO3>/`: suffixed with the scale id for a scale-dependent phase at a non-default scale."""
    scale = _active
    if scale.is_default or phase not in SCALE_DEPENDENT_PHASES:
        return phase
    return f"{phase}__{scale.scale_id}"


def manifest_file_name() -> str:
    """`manifest.json` at the default scale, `manifest__<scale id>.json` otherwise."""
    scale = _active
    return "manifest.json" if scale.is_default else f"manifest__{scale.scale_id}.json"
