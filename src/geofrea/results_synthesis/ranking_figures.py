"""T-R4 (max-regret map with the distribution within the regions) and T-R5 (nominal against robust rank, stability across SSPs) from F7.

Reads the F7 tables and the max-regret raster that F7 registered; no quantity is computed beyond what a plot draws (M-F8-01).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.maps import draw_grid, map_aspect, read_grid
from geofrea.results_synthesis.output import BuildContext, write_figure
from geofrea.robustness_analysis.table_schemas import ROBUSTNESS_TABLE_SCHEMA_VERSION

T_R4, T_R5 = "T-R4", "T-R5"
MAX_REGIONS = 20  # the regions drawn in the distribution panel: the largest by capacity
_VERSIONS = {ROBUSTNESS_TABLE_SCHEMA_VERSION}


def _statistic(hypothesis: pd.DataFrame, name: str) -> float | None:
    rows = hypothesis[hypothesis["statistic"] == name]["value"].dropna()
    return float(rows.iloc[0]) if len(rows) else None


def t_r4(ctx: BuildContext) -> None:
    """T-R4, per technology: the map of the max regret MR of the core window and, beside it, the distribution of MR within each Admin1 region
    against the national capacity-weighted value (the aggregate that hides the within-region spread, H2)."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            grid, extent = read_grid(ctx.reader.path(f"max_regret_{technology}__core"))
            table = ctx.reader.table(f"robustness_{technology}__core", _VERSIONS)
            hypothesis = ctx.reader.table(f"hypothesis_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_R4, technology, str(exc))
            continue
        ranked = table[table["mr"].notna()]
        if ranked.empty or not np.isfinite(grid).any():
            ctx.skip(T_R4, technology, "no cell has a max regret (the F7 set has no ranked cell)")
            continue
        national = _statistic(hypothesis, "h2_mr_capacity_weighted_national")
        capacity = ranked.groupby("admin1_id")["p_mw"].sum().sort_values(ascending=False)
        shown = list(capacity.index[:MAX_REGIONS])
        order = (
            ranked[ranked["admin1_id"].isin(shown)]
            .groupby("admin1_id")["mr"]
            .median()
            .sort_values()
        )
        data = [
            ranked.loc[ranked["admin1_id"] == region, "mr"].to_numpy() for region in order.index
        ]
        text = (
            f"Max regret MR of {technology} in the core window. Left: MR of each candidate cell of the ranked set. Right: the distribution of MR of the cells within "
            f"each Admin1 region (box: quartiles; whiskers: 1.5 interquartile ranges; at most the {MAX_REGIONS} regions with the most capacity, ordered by median), "
            "against the capacity-weighted national value (dashed line), which is a single number for the country."
        )

        def draw(grid=grid, extent=extent, data=data, labels=tuple(order.index), national=national):
            with style.thesis_style():
                fig, (ax_map, ax_box) = style.plt.subplots(
                    1,
                    2,
                    figsize=(
                        style.PAGE_WIDTH_IN,
                        style.PAGE_WIDTH_IN * max(0.5, map_aspect(grid) * 0.6),
                    ),
                    gridspec_kw={"width_ratios": [1.15, 1.0]},
                    layout="constrained",
                )
                draw_grid(
                    fig, ax_map, grid, extent, cmap="magma_r", label="max regret MR (relative)"
                )
                ax_box.boxplot(
                    data,
                    orientation="horizontal",
                    tick_labels=labels,
                    showfliers=False,
                    patch_artist=True,
                    boxprops={"facecolor": "#bdd7e7", "linewidth": 0.6},
                    medianprops={"color": style.REFERENCE_COLOR, "linewidth": 1.0},
                    whiskerprops={"linewidth": 0.6},
                    capprops={"linewidth": 0.6},
                )
                if national is not None:
                    ax_box.axvline(
                        national,
                        color="#b2182b",
                        linestyle="--",
                        linewidth=1.0,
                        label="national (capacity-weighted)",
                    )
                    ax_box.legend(loc="lower right")
                ax_box.set_xlabel("max regret MR (relative)")
                ax_box.set_ylabel("Admin1 region")
                ax_box.invert_yaxis()
                return fig

        write_figure(ctx, T_R4, "max_regret", draw, text, technology=technology)


def t_r5(ctx: BuildContext) -> None:
    """T-R5, per technology: the nominal rank against the robust rank of the ranked cells (the nominal and robust top-k marked) and the stability of
    the top-k across the SSPs, drawn from the Jaccard of every pair of SSP shortlists and the core share C_k that F7 stored (H1)."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            table = ctx.reader.table(f"robustness_{technology}__core", _VERSIONS)
            hypothesis = ctx.reader.table(f"hypothesis_{technology}__core", _VERSIONS)
            summary = ctx.reader.table(f"h1_summary_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_R5, technology, str(exc))
            continue
        ranked = table[table["nominal_rank"].notna() & table["robust_rank"].notna()]
        if ranked.empty:
            ctx.skip(T_R5, technology, "no cell has both a nominal and a robust rank")
            continue
        pairs = hypothesis[hypothesis["statistic"].str.startswith("h1_ssp_jaccard__")]
        pairs = pairs.assign(
            pair=pairs["statistic"].str.replace("h1_ssp_jaccard__", "", regex=False)
        )
        primary = summary[summary["primary"]]
        core_share = float(primary["c_k"].iloc[0]) if len(primary) else None
        k = int(primary["k"].iloc[0]) if len(primary) else None
        bars = [
            (str(r.pair).replace("_vs_", " vs "), float(r.value))
            for r in pairs.itertuples()
            if pd.notna(r.value)
        ]
        if core_share is not None:
            bars.append(("core share C_k", core_share))
        text = (
            f"Rank robustness of {technology} in the core window. Left: nominal rank (by LCOE at the reference climate) against robust rank (by max regret) of the cells of the ranked set; "
            "colour shows membership of the nominal top-k, the robust top-k, both or neither. Right: stability of the top-k across the SSPs, as the Jaccard index of the "
            "top-k sets of each pair of SSPs and the core share C_k (the share of the sites robust under one SSP that are robust under all three)."
        )

        def draw(ranked=ranked, bars=bars):
            with style.thesis_style():
                fig, (ax_rank, ax_bar) = style.plt.subplots(
                    1,
                    2,
                    figsize=(style.PAGE_WIDTH_IN, style.PAGE_WIDTH_IN * 0.45),
                    gridspec_kw={"width_ratios": [1.2, 1.0]},
                    layout="constrained",
                )
                nominal = ranked["topk_nominal"].fillna(False).astype(bool)
                robust = ranked["topk_robust"].fillna(False).astype(bool)
                for mask, color, label in (
                    (~nominal & ~robust, "#cccccc", "neither"),
                    (nominal & ~robust, style.AXIS_COLORS["techno_economic"], "nominal top-k only"),
                    (~nominal & robust, style.AXIS_COLORS["climate"], "robust top-k only"),
                    (nominal & robust, "#33a02c", "both"),
                ):
                    ax_rank.scatter(
                        ranked.loc[mask, "nominal_rank"],
                        ranked.loc[mask, "robust_rank"],
                        s=6,
                        color=color,
                        label=f"{label} ({int(mask.sum())})",
                        linewidths=0,
                    )
                top = float(max(ranked["nominal_rank"].max(), ranked["robust_rank"].max()))
                ax_rank.plot([1, top], [1, top], color=style.REFERENCE_COLOR, linewidth=0.6)
                ax_rank.set_xlabel("nominal rank")
                ax_rank.set_ylabel("robust rank")
                ax_rank.legend(loc="lower right")
                if bars:
                    ax_bar.barh(range(len(bars)), [v for _, v in bars], color="#6a51a3")
                    ax_bar.set_yticks(range(len(bars)), [n for n, _ in bars])
                    ax_bar.invert_yaxis()
                ax_bar.set_xlim(0, 1)
                ax_bar.set_xlabel("Jaccard index or share")
                return fig

        write_figure(
            ctx,
            T_R5,
            "rank_stability",
            draw,
            text,
            technology=technology,
            extra={"k": k},
        )
