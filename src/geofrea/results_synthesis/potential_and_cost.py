"""T-R1 and T-R2 (potential map and table, from F5), T-R11 and T-O3 (LCOE map and supply curves, from F6): reads of persisted artifacts, no new quantity (M-F8-01)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from geofrea.lcoe_modeling.table_schemas import LCOE_TABLE_SCHEMA_VERSION
from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.maps import draw_grid, map_aspect, read_grid
from geofrea.results_synthesis.members import REFERENCE, members_table
from geofrea.results_synthesis.output import BuildContext, write_figure, write_table
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION

T_R1, T_R2, T_R11, T_O3 = "T-R1", "T-R2", "T-R11", "T-O3"
REFERENCE_MEMBER_ROLE = "m0"
_CORE, _SENSITIVITY = "core", "sensitivity"
# (series, quantity column, unit): the "all present cells" series and the like-for-like series of F5 (M-F5-06)
_QUANTITIES = (
    ("all_present", "eligible_area_km2", "km2"),
    ("all_present", "P_GW", "GW"),
    ("all_present", "E_TWh", "TWh/yr"),
    ("like_for_like", "P_GW_like_for_like", "GW"),
    ("like_for_like", "E_TWh_like_for_like", "TWh/yr"),
)


def _window_roles(ctx: BuildContext) -> dict[str, str]:
    """member -> `core` or `sensitivity` by the windows of `experiments.yaml`; the reference member is `reference`."""
    members = members_table(ctx.reader)
    windows = {
        role: f"{w['start_year']}-{w['end_year']}"
        for role, w in ctx.experiments.windows.items()
        if role in (_CORE, _SENSITIVITY)
    }
    by_window = {v: k for k, v in windows.items()}
    return {
        row.member: REFERENCE if row.window == REFERENCE else by_window.get(row.window, row.window)
        for row in members.itertuples()
    }


def _map_of_a_raster(
    ctx: BuildContext,
    t_id: str,
    what: str,
    key_of,
    cmap: str,
    label: str,
    caption_of,
) -> None:
    """One map per technology from the raster artifact `key_of(technology)` (a diagnostic COG of F5 or F6), in the thesis style."""
    for technology in ctx.technologies:
        ctx.begin()
        key = key_of(technology)
        try:
            grid, extent = read_grid(ctx.reader.path(key))
        except MissingArtifactError as exc:
            ctx.skip(t_id, technology, str(exc))
            continue
        if not np.isfinite(grid).any():
            ctx.skip(t_id, technology, f"{key} has no value (no candidate cell)")
            continue

        def draw(grid=grid, extent=extent):
            with style.thesis_style():
                fig, ax = style.new_figure(1.0, map_aspect(grid))
                draw_grid(fig, ax, grid, extent, cmap=cmap, label=label)
                return fig

        write_figure(ctx, t_id, what, draw, caption_of(technology), technology=technology)


def t_r1(ctx: BuildContext) -> None:
    """T-R1, per technology: the technical potential density (MW per km2 of cell) at the reference climate, central land scenario."""
    _map_of_a_raster(
        ctx,
        T_R1,
        "potential_density",
        lambda technology: f"potential_density_{technology}",
        "viridis",
        "MW per km2 of cell",
        lambda technology: (
            f"Technical potential density of {technology} at the reference climate (member m0), central land scenario, in MW per km2 of cell. Cells that are not candidates are blank."
        ),
    )


def t_r11(ctx: BuildContext) -> None:
    """T-R11, per technology: the nominal LCOE (constant 2024 USD per MWh) at the reference climate, central land scenario."""
    _map_of_a_raster(
        ctx,
        T_R11,
        "lcoe_map",
        lambda technology: f"lcoe_nominal_{technology}",
        "viridis_r",
        "nominal LCOE (2024 USD/MWh)",
        lambda technology: (
            f"Nominal levelised cost of electricity of {technology} at the reference climate (member m0), central land scenario, in constant 2024 USD per MWh. Cells that are not candidates are blank."
        ),
    )


def t_r2(ctx: BuildContext) -> None:
    """T-R2, per technology: eligible area, GW and TWh/yr at the reference member, the range across the members of each window and the
    interval across the three land-availability scenarios.

    Implements: T-R2.
    """
    for technology in ctx.technologies:
        ctx.begin()
        roles = _window_roles(ctx)
        reference = [m for m, r in roles.items() if r == REFERENCE]
        key = f"potential_aggregates_{technology}"
        try:
            aggregates = ctx.reader.table(key, {POTENTIAL_TABLE_SCHEMA_VERSION})
        except MissingArtifactError as exc:
            ctx.skip(T_R2, technology, str(exc))
            continue
        aggregates = aggregates.assign(role=aggregates["member"].map(roles))
        rows = []
        for scenario, part in aggregates.groupby("scenario", sort=True):
            base = part[part["member"].isin(reference)]
            for series, column, unit in _QUANTITIES:
                row = {
                    "scenario": scenario,
                    "series": series,
                    "quantity": column,
                    "unit": unit,
                    "reference_m0": float(base[column].iloc[0]) if len(base) else None,
                }
                for role in (_CORE, _SENSITIVITY):
                    sel = part[part["role"] == role][column]
                    row[f"{role}_min"] = float(sel.min()) if len(sel) else None
                    row[f"{role}_max"] = float(sel.max()) if len(sel) else None
                    row[f"n_{role}_members"] = len(sel)
                rows.append(row)
        write_table(
            ctx,
            T_R2,
            "potential",
            pd.DataFrame(rows),
            f"Technical potential of {technology} at the reference climate and its range across the members of the core (2041-2070) and sensitivity windows. "
            "`all_present` sums the cells present in the member; `like_for_like` sums the cells present in every member, so a member is compared with the reference over the same cells.",
            technology=technology,
        )
        central = aggregates[aggregates["member"].isin(reference)]
        interval = [
            {
                "series": series,
                "quantity": column,
                "unit": unit,
                **{
                    scenario: float(central[central["scenario"] == scenario][column].iloc[0])
                    for scenario in sorted(central["scenario"].unique())
                },
            }
            for series, column, unit in _QUANTITIES
        ]
        write_table(
            ctx,
            T_R2,
            "land_interval",
            pd.DataFrame(interval),
            f"Interval of the technical potential of {technology} at the reference climate across the land-availability scenarios (restrictive, central, permissive).",
            technology=technology,
        )


def t_o3(ctx: BuildContext) -> None:
    """T-O3, per technology: nominal supply curves (cumulative energy against LCOE) of the reference member and of each projection member,
    one panel per window, projection members coloured by SSP.

    Implements: T-O3.
    """
    for technology in ctx.technologies:
        ctx.begin()
        roles = _window_roles(ctx)
        members = members_table(ctx.reader).set_index("member")
        key = f"supply_curve_{technology}"
        try:
            curves = ctx.reader.table(key, {LCOE_TABLE_SCHEMA_VERSION})
        except MissingArtifactError as exc:
            ctx.skip(T_O3, technology, str(exc))
            continue
        if curves.empty:
            ctx.skip(T_O3, technology, f"{key} has no row")
            continue

        def draw(curves=curves, roles=roles, members=members):
            with style.thesis_style():
                fig, axes = style.plt.subplots(
                    1,
                    2,
                    figsize=(style.PAGE_WIDTH_IN, style.PAGE_WIDTH_IN * 0.42),
                    sharey=True,
                    layout="constrained",
                )
                for ax, role, title in (
                    (axes[0], _CORE, "Core window"),
                    (axes[1], _SENSITIVITY, "Sensitivity window"),
                ):
                    for member, part in curves.groupby("member", sort=True):
                        if roles.get(member) == REFERENCE:
                            ax.step(
                                part["cum_E_TWh"],
                                part["lcoe_nominal"],
                                where="post",
                                color=style.REFERENCE_COLOR,
                                lw=1.4,
                                zorder=3,
                            )
                        elif roles.get(member) == role:
                            ax.step(
                                part["cum_E_TWh"],
                                part["lcoe_nominal"],
                                where="post",
                                color=style.ssp_color(str(members.loc[member, "ssp"])),
                                lw=0.5,
                                alpha=0.6,
                            )
                    ax.set_title(title)
                    ax.set_xlabel("Cumulative energy (TWh/yr)")
                axes[0].set_ylabel("Nominal LCOE (USD/MWh)")
                handles = [
                    Line2D([], [], color=style.REFERENCE_COLOR, lw=1.4, label="Reference")
                ] + [Line2D([], [], color=c, lw=1.0, label=s) for s, c in style.SSP_COLORS.items()]
                axes[1].legend(handles=handles, loc="upper left", frameon=False)
                return fig

        write_figure(
            ctx,
            T_O3,
            "supply_curves",
            draw,
            f"Nominal supply curves of {technology}: cells in increasing nominal LCOE against cumulative energy, for the reference member (black) and every projection member, coloured by SSP, in the core and sensitivity windows. Central land-availability scenario.",
            technology=technology,
        )
