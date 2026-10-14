"""T-R3: the change of the capacity factor by SSP in the core window, with the marking of the cells where the GCMs agree on its sign.

Reads the potential tables of F5 (`CF` per cell and member) and the members of F4; no raw data and no kernel (M-F8-01). The change of a member is
`CF` of the member minus `CF` of the reference member; the map of an SSP shows the median of that change over the members of the SSP (one per GCM).
A cell is marked when at least `thesis_figures.gcm_agreement.min_share` of them (two thirds, the convention of the IPCC AR6 WGI Atlas; D2 of the
F8 design report, D-F8-018) agree on the sign of the change. A member without a value in the cell (masked by M-F4-07) and a change of exactly zero
agree with no sign, so they count against the agreement.
"""

from __future__ import annotations

import warnings
from fractions import Fraction

import numpy as np
import pandas as pd

from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.maps import Extent, draw_grid, map_aspect, table_grid
from geofrea.results_synthesis.members import REFERENCE, members_table
from geofrea.results_synthesis.output import BuildContext, NotBuilt, write_figure, write_table
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION

T_R3 = "T-R3"
STIPPLE_TARGET = 40  # about this many marks along the longer side of a map


def agreement_mask(changes: np.ndarray, min_share: Fraction) -> np.ndarray:
    """True where at least `min_share` of the rows of `changes` (members by cells) have the same sign; NaN and 0 have none."""
    n = changes.shape[0]
    positive = (changes > 0).sum(axis=0)
    negative = (changes < 0).sum(axis=0)
    return np.maximum(positive, negative) * min_share.denominator >= min_share.numerator * n


def median_change(changes: np.ndarray) -> np.ndarray:
    """Median over the members, NaN where no member has a value."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(changes, axis=0)


def changes_by_ssp(
    potential: pd.DataFrame, members: pd.DataFrame, core_window: str
) -> tuple[np.ndarray, dict[str, tuple[list[str], np.ndarray]]]:
    """`(cell ids, {ssp: (members, changes of shape (members, cells))})` for the members of the core window.

    Raises:
        NotBuilt: no reference member or no member of the core window.
    """
    reference = members.loc[members["window"] == REFERENCE, "member"].tolist()
    if not reference:
        raise NotBuilt("members has no reference member")
    wide = potential.assign(member=potential["member"].astype(str)).pivot(
        index="cell_id", columns="member", values="CF"
    )
    base = wide[reference[0]]
    core = members[(members["window"] == core_window) & members["ssp"].notna()]
    out = {
        str(ssp): (
            part["member"].tolist(),
            wide.reindex(columns=part["member"].tolist()).sub(base, axis=0).to_numpy().T,
        )
        for ssp, part in core.groupby("ssp", sort=True)
    }
    if not out:
        raise NotBuilt(f"members has no member of the core window {core_window}")
    return wide.index.to_numpy(), out


def stipple_points(marked: np.ndarray, extent: Extent) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude of the marks: the marked cells on a lattice thinned to about `STIPPLE_TARGET` marks along the longer side."""
    rows, cols = marked.shape
    stride = max(1, round(max(rows, cols) / STIPPLE_TARGET))
    r, c = np.nonzero(marked[::stride, ::stride])
    west, east, south, north = extent
    x = west + (c * stride + 0.5) * (east - west) / cols
    y = north - (r * stride + 0.5) * (north - south) / rows
    return x, y


def t_r3(ctx: BuildContext) -> None:
    """T-R3, per technology: the change of the capacity factor of the core window by SSP, one panel per SSP, marked where the GCMs agree on the sign,
    and the table of the share of cells in agreement."""
    rule = ctx.experiments.thesis_figures.gcm_agreement
    window = ctx.experiments.windows["core"]
    core_window = f"{window['start_year']}-{window['end_year']}"
    for technology in ctx.technologies:
        ctx.begin()
        try:
            members = members_table(ctx.reader)
            potential = ctx.reader.table(
                f"potential_{technology}__central", {POTENTIAL_TABLE_SCHEMA_VERSION}
            )
            cell_ids, by_ssp = changes_by_ssp(potential, members, core_window)
        except (MissingArtifactError, NotBuilt) as exc:
            ctx.skip(T_R3, technology, str(exc))
            continue
        panels = []
        rows = []
        for ssp, (ssp_members, changes) in by_ssp.items():
            median = median_change(changes)
            marked = agreement_mask(changes, rule.share)
            panels.append((ssp, table_grid(cell_ids, median), table_grid(cell_ids, marked)))
            valid = np.isfinite(median)
            rows.append(
                {
                    "ssp": ssp,
                    "n_gcms": len(ssp_members),
                    "n_cells": int(valid.sum()),
                    "n_cells_in_agreement": int(marked[valid].sum()),
                    "share_in_agreement": float(marked[valid].mean()) if valid.any() else None,
                    "min_share": rule.min_share,
                }
            )
        limit = max(
            (
                float(np.nanmax(np.abs(grid)))
                for _, (grid, _), _ in panels
                if np.isfinite(grid).any()
            ),
            default=0.0,
        )
        if limit == 0.0:
            ctx.skip(T_R3, technology, "the capacity factor does not change in any member")
            continue
        text = (
            f"Change of the capacity factor of {technology} in the core window ({core_window}) against the reference climate, by SSP: the median over the GCMs of the SSP, "
            f"central land scenario. Dots mark the cells where at least {rule.min_share} of the GCMs agree on the sign of the change "
            "(the convention of the IPCC AR6 WGI Atlas); a member without a value in a cell, and a change of zero, agree with no sign."
        )

        def draw(panels=panels, limit=limit, technology=technology):
            with style.thesis_style():
                grid0 = panels[0][1][0]
                fig, axes = style.plt.subplots(
                    1,
                    len(panels),
                    figsize=(style.PAGE_WIDTH_IN, style.PAGE_WIDTH_IN * map_aspect(grid0) * 0.45),
                    sharey=True,
                    layout="constrained",
                    squeeze=False,
                )
                image = None
                for ax, (ssp, (grid, extent), (mark_grid, _)) in zip(axes[0], panels, strict=True):
                    image = draw_grid(
                        fig,
                        ax,
                        grid,
                        extent,
                        cmap="RdBu",
                        label="",
                        vmin=-limit,
                        vmax=limit,
                        colorbar=False,
                    )
                    x, y = stipple_points(mark_grid > 0.5, extent)
                    ax.scatter(x, y, s=1.2, c="black", linewidths=0, rasterized=True)
                    ax.set_title(ssp)
                for ax in axes[0][1:]:
                    ax.set_ylabel("")
                fig.colorbar(
                    image,
                    ax=list(axes[0]),
                    label="change of the capacity factor (median over the GCMs)",
                    shrink=0.85,
                )
                return fig

        write_figure(ctx, T_R3, "cf_change", draw, text, technology=technology)
        write_table(
            ctx,
            T_R3,
            "cf_agreement",
            pd.DataFrame(rows),
            f"Share of the cells of {technology} where at least {rule.min_share} of the GCMs of the SSP agree on the sign of the change of the capacity factor in the core window.",
            technology=technology,
        )
