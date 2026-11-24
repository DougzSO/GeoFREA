"""T-X1 to T-X4: the exploratory outputs of DEC-098, read from the artifacts of the support phase `exploratory_analysis` (M-F8-01; COMMAND 210).

EXPLORATORY. Every title, caption and legend says so, and the provenance carries `"exploratory": true`. Only this module reads the exploratory artifacts: no
module of the pre-registered outputs T-R1 to T-R12 imports `exploratory_analysis` (a test checks it), so those tables cannot change with them.

- T-X1 (table): H5c, the cost of reaching the target and the energy levels, per technology and window.
- T-X2 (figure): LCOE at f0 against VUL_clim per cell, the nominal top-k highlighted.
- T-X3 (map): VUL_clim per cell.
- T-X4 (table): VUL, the distributions, the Spearman correlations, the capacity per quadrant and the climate-fragile cells.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from geofrea.exploratory_analysis.table_schemas import EXPLORATORY_TABLE_SCHEMA_VERSION
from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.maps import draw_grid, map_aspect, table_grid
from geofrea.results_synthesis.output import BuildContext, write_figure, write_table

T_X1, T_X2, T_X3, T_X4 = "T-X1", "T-X2", "T-X3", "T-X4"
_VERSIONS = {EXPLORATORY_TABLE_SCHEMA_VERSION}
_EXTRA = {"exploratory": True, "decision": "DEC-098"}
LABEL = "Exploratory (DEC-098; the pre-registered results are unchanged). "


def t_x1(ctx: BuildContext) -> None:
    """T-X1, per technology: H5c for the core window, the nominal curves and the per-cell P90 envelope."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            table = ctx.reader.table(f"h5c_summary_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_X1, technology, str(exc))
            continue
        columns = [
            "basis", "level", "g_twh", "g_share_of_total_m0", "mc_m0", "ac_m0", "n_unreachable_members",
            "delta_mc_max", "delta_mc_member", "delta_mc_ssp", "delta_mc_median", "delta_mc_by_ssp",
            "delta_ac_max", "delta_ac_member", "delta_ac_ssp", "delta_ac_median", "label",
        ]  # fmt: skip
        write_table(
            ctx,
            T_X1,
            "h5c_cost_to_target",
            table[columns],
            LABEL
            + f"H5c, cost-to-target of {technology} in the core window. MC and AC (USD/MWh) at the reference member for the target and for 5, 10 and 25 per cent of the energy of the F7 set; "
            "Delta_MC and Delta_AC are the largest relative increase over the core members, with the member and the SSP that attain it, the median over members and the value per SSP. "
            "Basis nominal: LCOE at the nominal parameters; basis p90_envelope: the per-cell P90 over the draws of each member (an upper envelope, not a joint draw). No tau is used.",
            technology=technology,
            extra=_EXTRA,
        )


def t_x2(ctx: BuildContext) -> None:
    """T-X2, per technology: LCOE at f0 against VUL_clim, the nominal top-k highlighted."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            table = ctx.reader.table(f"vulnerability_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_X2, technology, str(exc))
            continue
        ranked = table[table["vul_clim"].notna() & table["lcoe_f0"].notna()]
        if ranked.empty:
            ctx.skip(T_X2, technology, "no ranked cell has a VUL_clim")
            continue
        top = ranked["topk_nominal"].fillna(False).astype(bool)

        def draw(ranked=ranked, top=top, technology=technology):
            with style.thesis_style():
                fig, ax = style.new_figure(0.6, 0.8)
                ax.scatter(ranked.loc[~top, "lcoe_f0"], ranked.loc[~top, "vul_clim"], s=4, alpha=0.4, linewidths=0, rasterized=True,
                           color=style.technology_color(ctx.technologies, technology), label="ranked cells")  # fmt: skip
                ax.scatter(ranked.loc[top, "lcoe_f0"], ranked.loc[top, "vul_clim"], s=7, linewidths=0, rasterized=True, color="#b2182b", label="nominal top-k")
                ax.set_xlabel("LCOE at f0 (USD/MWh)")
                ax.set_ylabel("VUL_clim (largest relative LCOE increase over the core members)")
                ax.set_title("Exploratory: own vulnerability against cost")
                ax.legend(frameon=False, loc="upper right")
                return fig

        write_figure(
            ctx,
            T_X2,
            "lcoe_vs_vul_clim",
            draw,
            LABEL + f"LCOE at the reference future against the climate vulnerability VUL_clim of each ranked cell of {technology}, core window; the cells of the nominal top-k are highlighted.",
            technology=technology,
            extra=_EXTRA,
        )


def t_x3(ctx: BuildContext) -> None:
    """T-X3, per technology: the map of VUL_clim of the core window."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            table = ctx.reader.table(f"vulnerability_{technology}__core", _VERSIONS, columns=["cell_id", "vul_clim"])
        except MissingArtifactError as exc:
            ctx.skip(T_X3, technology, str(exc))
            continue
        ranked = table[table["vul_clim"].notna()]
        if ranked.empty:
            ctx.skip(T_X3, technology, "no ranked cell has a VUL_clim")
            continue
        grid, extent = table_grid(ranked["cell_id"].to_numpy(), ranked["vul_clim"].to_numpy())
        if not np.isfinite(grid).any():
            ctx.skip(T_X3, technology, "no cell on the lattice")
            continue

        def draw(grid=grid, extent=extent):
            with style.thesis_style():
                fig, ax = style.new_figure(0.8, map_aspect(grid))
                draw_grid(fig, ax, grid, extent, cmap="magma_r", label="VUL_clim (relative)")
                ax.set_title("Exploratory: own climate vulnerability VUL_clim")
                return fig

        write_figure(
            ctx,
            T_X3,
            "vul_clim_map",
            draw,
            LABEL + f"Climate vulnerability VUL_clim of each ranked cell of {technology}, core window: the largest relative increase of the LCOE over the core members at the nominal parameters.",
            technology=technology,
            extra=_EXTRA,
        )


def t_x4(ctx: BuildContext) -> None:
    """T-X4, per technology: the summary of VUL (distributions, Spearman, top-k share, capacity per quadrant, climate-fragile cells)."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            table = ctx.reader.table(f"vulnerability_summary_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_X4, technology, str(exc))
            continue
        table = table.assign(value=pd.to_numeric(table["value"], errors="coerce"))
        write_table(
            ctx,
            T_X4,
            "vul_summary",
            table,
            LABEL + f"Own vulnerability of {technology} in the core window: distribution of VUL_clim, VUL_tec and VUL over the ranked cells, Spearman correlation with the LCOE at f0 and with MR, "
            "the share of the nominal top-k in the upper quartile of VUL_clim, the capacity (MW) in each quadrant of LCOE at f0 and VUL_clim against their medians, and the climate-fragile cells reported apart. "
            "VUL_tec is mostly common to the country and varies little between cells.",
            technology=technology,
            extra=_EXTRA,
        )
