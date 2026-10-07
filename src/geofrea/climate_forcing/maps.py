"""Diagnostic maps of the change factors, one PNG per member (J-5; M-F4-06, A-08).

Each figure has three panels (`delta_rsds`, `delta_wind`, `dT`) on the 0.05 degree lattice. The colour scale of a
factor is shared by every member of the country (1st-99th percentile of all rows), so members can be compared by
eye. Cells masked for that member (OQ-042 option C) are drawn in hatched grey instead of being left blank, so an
absence is visible and never mistaken for "no change".
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON  # noqa: E402
from geofrea.land_eligibility.cells import row_col_from_id  # noqa: E402

PANELS = (
    ("delta_rsds", "Solar radiation ratio (window / reference)", "RdBu", "ratio"),
    ("delta_wind", "Wind speed ratio (window / reference)", "RdBu", "ratio"),
    ("dT", "Temperature change (K)", "YlOrRd", "sequential"),
)


def _grid(cell_ids: np.ndarray, values: np.ndarray, rows: np.ndarray, cols: np.ndarray, shape, origin) -> np.ndarray:
    out = np.full(shape, np.nan, dtype=np.float32)
    out[rows - origin[0], cols - origin[1]] = values
    return out


def color_limits(forcing: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Shared colour limits per factor: ratios symmetric about 1, dT from its own 1st to 99th percentile."""
    limits: dict[str, tuple[float, float]] = {}
    real = forcing[forcing["member"].astype(str) != "m0"]
    for column, _title, _cmap, kind in PANELS:
        lo, hi = np.nanpercentile(real[column], [1, 99])
        if kind == "ratio":
            half = max(abs(lo - 1.0), abs(hi - 1.0), 1e-3)
            limits[column] = (1.0 - half, 1.0 + half)
        else:
            limits[column] = (float(lo), float(max(hi, lo + 1e-3)))
    return limits


def lattice_bounds(cell_ids: np.ndarray) -> tuple[int, int, int, int]:
    """(row0, row1, col0, col1) spanned by the cells."""
    rows, cols = row_col_from_id(cell_ids)
    return int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())


def plot_member(
    member_id: str,
    member_rows: pd.DataFrame,
    masked_rows: pd.DataFrame,
    bounds: tuple[int, int, int, int],
    limits: dict[str, tuple[float, float]],
    out_path: Path,
    country: str,
    note: str | None = None,
) -> Path:
    """One figure: `member_rows` are this member's forcing rows, `masked_rows` its masked cells."""
    r0, r1, c0, c1 = bounds
    shape = (r1 - r0 + 1, c1 - c0 + 1)
    rows, cols = row_col_from_id(member_rows["cell_id"].to_numpy())
    mrows, mcols = row_col_from_id(masked_rows["cell_id"].to_numpy())
    mask_img = np.full(shape, np.nan, dtype=np.float32)
    if len(masked_rows):
        mask_img[mrows - r0, mcols - c0] = 0.5

    west = CELL_ORIGIN_LON + c0 * CELL_DEG
    east = CELL_ORIGIN_LON + (c1 + 1) * CELL_DEG
    north = CELL_ORIGIN_LAT - r0 * CELL_DEG
    south = CELL_ORIGIN_LAT - (r1 + 1) * CELL_DEG
    extent = (west, east, south, north)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), constrained_layout=True)
    for ax, (column, title, cmap, _kind) in zip(axes, PANELS, strict=True):
        img = _grid(member_rows["cell_id"].to_numpy(), member_rows[column].to_numpy(), rows, cols, shape, (r0, c0))
        vmin, vmax = limits[column]
        im = ax.imshow(img, extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        if len(masked_rows):
            ax.imshow(mask_img, extent=extent, origin="upper", cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        fig.colorbar(im, ax=ax, shrink=0.8)
    subtitle = f"{len(member_rows)} cells" + (f"; {len(masked_rows)} masked (grey, OQ-042)" if len(masked_rows) else "")
    title = f"{country} - {member_id}  ({subtitle})"
    fig.suptitle(title + (f"\n{note}" if note else ""), fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_all_members(
    forcing: pd.DataFrame, masked: pd.DataFrame, out_dir: Path, country: str, notes: dict[str, str] | None = None
) -> list[Path]:
    """One PNG per member (m0 excluded: it is identity by definition), named `<country>_<member>.png`."""
    limits = color_limits(forcing)
    all_ids = np.concatenate([forcing["cell_id"].to_numpy(), masked["cell_id"].to_numpy()])
    bounds = lattice_bounds(all_ids)
    by_member = {str(m): g for m, g in forcing.groupby(forcing["member"].astype(str), observed=True)}
    masked_by_member = {str(m): g for m, g in masked.groupby(masked["member"].astype(str), observed=True)}
    empty = masked.iloc[0:0]
    paths = []
    for m in sorted(k for k in by_member if k != "m0"):
        paths.append(
            plot_member(
                m, by_member[m], masked_by_member.get(m, empty), bounds, limits,
                out_dir / f"{country}_{m}.png", country, (notes or {}).get(m),
            )
        )
    return paths
