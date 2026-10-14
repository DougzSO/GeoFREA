"""T-R6, T-R10, T-R12 and T-O2 from the F7 tables, and T-R9 from the F7b tables: reads of persisted artifacts (M-F8-01).

A table F7 or F7b wrote empty because a decision parameter is null is written empty here too, with the reason in the caption: "not
available" is never shown as zero (D7, D-F8-007).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from geofrea.core.config_schemas import H4Rule
from geofrea.external_validation.table_schemas import VALIDATION_TABLE_SCHEMA_VERSION
from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import ArtifactReader, MissingArtifactError
from geofrea.results_synthesis.members import members_table
from geofrea.results_synthesis.output import BuildContext, NotBuilt, write_figure, write_table
from geofrea.robustness_analysis.table_schemas import ROBUSTNESS_TABLE_SCHEMA_VERSION

T_O1 = "T-O1"
T_R6, T_R7, T_R9, T_R10, T_R12, T_O2 = "T-R6", "T-R7", "T-R9", "T-R10", "T-R12", "T-O2"
ROLES = ("core", "sensitivity")
_VERSIONS = {ROBUSTNESS_TABLE_SCHEMA_VERSION}


def _reason(reader: ArtifactReader, key: str) -> str:
    note = reader.skip_note(key)
    if not note:
        return "the table has no row"
    return (
        f"{note.get('reason', 'skipped')} ({note.get('open_question', 'no open question named')})"
    )


def _readers(ctx: BuildContext) -> list[ArtifactReader]:
    return [r for r in (ctx.reader, ctx.other_scale) if r is not None]


# What T-R6 shows of each hypothesis: the F7 summary table, the columns of its primary statistic, its reference value and its threshold, and
# the rule as F7 applies it (M-F7-07). H1 and H5 have two primary statistics (H1a and H1b; the resource and the exposure ratio of H5), the
# second one in the `*_2` columns.
VERDICT_COLUMNS = [
    "scale",
    "role",
    "window",
    "hypothesis",
    "statistic",
    "value",
    "reference",
    "threshold",
    "verdict",
    "rule",
    "statistic_2",
    "value_2",
    "reference_2",
    "threshold_2",
]
_SUMMARIES = ("h1", "h2", "h3", "h5")


def _window_of(ctx: BuildContext, role: str) -> str:
    """The years of the window of a role, as `2041-2070`."""
    window = ctx.experiments.windows[role]
    return f"{window['start_year']}-{window['end_year']}"


def _h4_verdict_tables(ctx: BuildContext, technology: str) -> list[pd.DataFrame]:
    """The `h4_verdict` tables of the support phase `cross_country_h4` (one per scale and window role that exist), with `scale` and `role`."""
    tables = []
    for reader in ctx.cross_country:
        for role in ROLES:
            key = f"h4_verdict_{technology}__{role}"
            if reader.has(key):
                tables.append(
                    reader.table(key, _VERSIONS).assign(
                        scale=reader.scale_id, role=role, window=_window_of(ctx, role)
                    )
                )
    return tables


def _h4_verdict_row(total: pd.Series) -> dict:
    """The one row of H4 in the verdict table, from the `technology` row of the cross-country table (one row per technology, not per country)."""
    return {
        "scale": total["scale"],
        "role": total["role"],
        "window": total["window"],
        "hypothesis": "H4",
        "statistic": "h4_strict_pair_count",
        "value": float(total["n_climate_dominated"] * total["n_techno_economic_dominated"]),
        "reference": None,
        "threshold": 1.0,
        "verdict": total["verdict"],
        "rule": "supported if a country is Climate-Dominated (rho > 0.60) and another Techno-Economic-Dominated (rho < 0.40); not testable if fewer than two countries have a profile",
        "statistic_2": "countries_with_profile",
        "value_2": float(total["n_available"]),
        "reference_2": None,
        "threshold_2": 2.0,
    }


def _h5_verdict(row: pd.Series) -> str:
    """The verdict of H5, or why there is none: its status (not testable, target not met at reference) or the unavailable exposure."""
    if pd.notna(row["verdict"]):
        return row["verdict"]
    return row["status"] if row["status"] != "tested" else "exposure_not_available"


def _verdict_row(hypothesis: str, row: pd.Series) -> dict:
    """The one row of a hypothesis in the verdict table, from the primary row of its F7 summary."""
    common = {
        "scale": row["scale"],
        "role": row["role"],
        "window": row["window"],
        "hypothesis": hypothesis,
        "verdict": row["verdict"],
        "statistic_2": None,
        "value_2": None,
        "reference_2": None,
        "threshold_2": None,
    }
    if hypothesis == "H1":
        return common | {
            "statistic": "h1a_core_share",
            "value": row["c_k"],
            "reference": row["reference"],
            "threshold": row["alpha"],
            "rule": "supported if C_k >= alpha and V_k >= beta; partially supported if exactly one holds",
            "statistic_2": "h1b_vulnerable_share",
            "value_2": row["v_k"],
            "threshold_2": row["beta"],
        }
    if hypothesis == "H2":
        return common | {
            "statistic": "h2_overlap_index",
            "value": row["overlap"],
            "reference": row["overlap_ref"],
            "threshold": row["gamma"],
            "rule": "supported if O < gamma; not testable if O_ref >= gamma",
        }
    if hypothesis == "H5":
        return common | {
            "verdict": _h5_verdict(row),
            "statistic": "h5a_resource_loss_ratio",
            "value": row["r_loss"],
            "reference": None,
            "threshold": row["lam"],
            "rule": "supported if R_loss >= lambda and R_exp >= lambda; partially supported (resource) or (exposure) if only one holds; not testable without a target; target not met at reference if H_0 <= 0",
            "statistic_2": "h5b_exposure_ratio",
            "value_2": row["r_exp"],
            "threshold_2": row["lam"],
        }
    return common | {
        "statistic": "h3_beyond_reach_share",
        "value": row["d"],
        "reference": row["d_ref"],
        "threshold": row["delta"],
        "rule": "supported if D >= delta; not testable if D_ref < delta",
    }


def t_r6(ctx: BuildContext) -> None:
    """T-R6, per technology: the H1 to H5 statistics for the core window, the 2071-2100 window and the other cell scale, each with its
    pre-registered rule and verdict; the verdict table (one row per hypothesis: primary statistic, reference, threshold, verdict); and the
    F7 summaries of H1 (C_k, V_k), H2 (O), H3 (D, the price and the benefit of robustness) and H5 (R_loss, R_exp, the target and the slack)
    with their sensitivities."""
    for technology in ctx.technologies:
        ctx.begin()
        statistics: list[pd.DataFrame] = []
        summaries: dict[str, list[pd.DataFrame]] = {name: [] for name in _SUMMARIES}
        h4_country: list[pd.DataFrame] = []
        for reader in _readers(ctx):
            for role in ROLES:
                try:
                    hypothesis = reader.table(f"hypothesis_{technology}__{role}", _VERSIONS)
                except MissingArtifactError as exc:
                    ctx.skip(T_R6, f"{technology} {reader.scale_id} {role}", str(exc))
                    continue
                part = hypothesis[hypothesis["hypothesis"].isin(["H1", "H2", "H3", "H4", "H5"])]
                statistics.append(part.assign(scale=reader.scale_id, role=role))
                for name in _SUMMARIES:
                    key = f"{name}_summary_{technology}__{role}"
                    if not reader.has(key):
                        continue
                    summary = reader.table(key, _VERSIONS)
                    if len(summary):
                        summaries[name].append(summary.assign(scale=reader.scale_id, role=role))
                    else:
                        ctx.skip(
                            T_R6,
                            f"{technology} {reader.scale_id} {role} {name.upper()} summary",
                            _reason(reader, key),
                        )
                key = f"h4_country_{technology}__{role}"
                if reader.has(key):
                    table = reader.table(key, _VERSIONS)
                    if len(table):
                        h4_country.append(table.assign(scale=reader.scale_id, role=role))
                    else:
                        ctx.skip(
                            T_R6,
                            f"{technology} {reader.scale_id} {role} H4 country table",
                            _reason(reader, key),
                        )
        if statistics:
            frame = pd.concat(statistics, ignore_index=True)
            frame = frame[
                [
                    "scale",
                    "role",
                    "window",
                    "hypothesis",
                    "statistic",
                    "value",
                    "p10",
                    "p50",
                    "p90",
                    "range_axis",
                    "n_cells",
                    "k",
                    "rule",
                    "verdict",
                    "verdict_reason",
                ]
            ]
            write_table(
                ctx,
                T_R6,
                "hypothesis_statistics",
                frame,
                f"H1 to H5 statistics for {technology}: core window, 2071-2100 window and the other cell scale. A value with p10 and p90 is the central value at the nominal parameters and the range over the draws; a null verdict means no rule is pre-registered or the hypothesis is not testable, not that it fails.",
                technology=technology,
            )
        else:
            ctx.skip(T_R6, technology, "no hypothesis table is registered")
        verdicts = [
            _verdict_row(name.upper(), row)
            for name in _SUMMARIES
            for table in summaries[name]
            for _, row in table[table["primary"]].iterrows()
        ]
        h4_verdict = _h4_verdict_tables(ctx, technology)
        verdicts += [
            _h4_verdict_row(total)
            for table in h4_verdict
            for _, total in table[table["kind"] == "technology"].iterrows()
        ]
        if not h4_verdict:
            ctx.skip(
                T_R6,
                f"{technology} H4 verdict",
                "the support phase cross_country_h4 has not run (no manifest in outputs/cross_country)",
            )
        if verdicts:
            frame = pd.DataFrame(verdicts, columns=VERDICT_COLUMNS)
            frame["_order"] = frame["hypothesis"].map({"H1": 1, "H2": 2, "H3": 3, "H4": 4, "H5": 5})
            frame["_role"] = frame["role"].map({role: at for at, role in enumerate(ROLES)})
            frame = (
                frame.sort_values(["scale", "_role", "_order"])
                .drop(columns=["_order", "_role"])
                .reset_index(drop=True)
            )
            write_table(
                ctx,
                T_R6,
                "hypothesis_verdicts",
                frame,
                f"Verdict of H1 to H5 for {technology}, one row per hypothesis, window and scale: the primary statistic, its reference value (the value expected by chance), the pre-registered threshold and the verdict, read from the F7 summary tables. H1 has two primary statistics (H1a and H1b, the second in the columns ending in 2) and so has H5 (the resource ratio R_loss and the exposure ratio R_exp, both compared with lambda; a status such as not_testable, target_not_met_at_reference or exposure_not_available stands for a verdict that does not exist). H4 is a statement about the countries together: its row counts the pairs of a Climate-Dominated and a Techno-Economic-Dominated country (threshold 1) and the countries with a profile (at least 2), and is read from the support phase cross_country_h4. A sensitivity never revises a verdict.",
                technology=technology,
            )
        captions = {
            "h1": f"H1 for {technology}: core share C_k (H1a), vulnerable share V_k (H1b), the chance-level reference (k/n)^2 and the verdict, with the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
            "h2": f"H2 for {technology}: the Capacity Overlap Index O of the cell and the Admin1 selections, the reference T/Q_max, the verdict, the robustness penalty and the total variation distance, with the decision profile over gamma and the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
            "h5": f"H5 for {technology}: the baseline economic potential E_0 of the fixed domain, the national target G in TWh/year with its original unit, horizon and conversion, the slack H_0, the largest loss of energy over the members (R_loss, H5a) and the largest exposed energy over the hazard members (R_exp, H5b) as shares of the slack, the same exposure with the reference indicators, the status and the verdict, with the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
            "h3": f"H3 for {technology}: the share D of the robust capacity beyond the reach of the nominal plan, the reference 1 - (k + m)/|I|, the verdict, the price of robustness (relative increase of the present LCOE) and the benefit of robustness (reduction of the capacity-weighted maximum regret, no verdict), with the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
        }
        for name in _SUMMARIES:
            if summaries[name]:
                write_table(
                    ctx,
                    T_R6,
                    f"{name}_summary",
                    pd.concat(summaries[name], ignore_index=True),
                    captions[name],
                    technology=technology,
                )
        if h4_country:
            write_table(
                ctx,
                T_R6,
                "h4_country",
                pd.concat(h4_country, ignore_index=True),
                f"H4 for {technology} in this country: the displacements D_clim and D_tec of the climate-only and the techno-economic-only shortlists, the dominance ratio rho, the profile (boundaries 0.40 and 0.60), the displacement D of the joint shortlist, the climate axis by SSP and the sensitivities (variant column) beside the primary result. The verdict needs the other countries (h4_verdict). A sensitivity never revises the profile.",
                technology=technology,
            )
        if h4_verdict:
            write_table(
                ctx,
                T_R6,
                "h4_verdict",
                pd.concat(h4_verdict, ignore_index=True),
                f"H4 for {technology} across countries: the profile of each country (or why it is unavailable), the count of countries by profile and the verdict of the strict rule (supported with one Climate-Dominated and one Techno-Economic-Dominated country; not testable with fewer than two countries that have a profile).",
                technology=technology,
                per_country=False,
            )


def t_r7(ctx: BuildContext) -> None:
    """T-R7, per technology: the climate and techno-economic displacement (D_clim, D_tec) and the dominance ratio rho by country, with the
    profile boundaries marked. The countries are those of the support phase cross_country_h4; without it the country alone is shown from its
    own h4_country table, and the caption says so."""
    rule = ctx.experiments.hypothesis_rules.get("H4")
    if not isinstance(rule, H4Rule):
        raise NotBuilt("hypothesis_rules.H4 is null (OQ-050)")
    for technology in ctx.technologies:
        ctx.begin()
        frames = [
            table[table["kind"] == "country"]
            for table in _h4_verdict_tables(ctx, technology)
            if (table["kind"] == "country").any()
        ]
        scope = "the countries of the support phase cross_country_h4"
        if not frames:
            scope = f"{ctx.iso} alone (the support phase cross_country_h4 has not run)"
            for reader in _readers(ctx):
                for role in ROLES:
                    key = f"h4_country_{technology}__{role}"
                    if not reader.has(key):
                        continue
                    table = reader.table(key, _VERSIONS)
                    primary = table[table["primary"]]
                    if primary.empty:
                        ctx.skip(
                            T_R7, f"{technology} {reader.scale_id} {role}", _reason(reader, key)
                        )
                        continue
                    frames.append(
                        pd.DataFrame(
                            {
                                "kind": "country",
                                "country": ctx.iso,
                                "window": _window_of(ctx, role),
                                "available": True,
                                "profile": primary["profile"],
                                "d_clim": primary["d_clim"],
                                "d_tec": primary["d_tec"],
                                "d_sum": primary["d_sum"],
                                "rho": primary["rho"],
                                "reason": None,
                                "scale": reader.scale_id,
                                "role": role,
                            }
                        )
                    )
        if not frames:
            ctx.skip(T_R7, technology, "no h4_country or h4_verdict table is registered")
            continue
        frame = pd.concat(frames, ignore_index=True)[
            [
                "scale",
                "role",
                "window",
                "country",
                "available",
                "profile",
                "d_clim",
                "d_tec",
                "d_sum",
                "rho",
                "reason",
            ]
        ]
        scale_shown = (
            ctx.reader.scale_id
            if (frame["scale"] == ctx.reader.scale_id).any()
            else frame["scale"].iloc[0]
        )
        shown = frame[(frame["scale"] == scale_shown) & (frame["role"] == "core")].reset_index(
            drop=True
        )
        text = (
            f"Displacement of the site ranking by each uncertainty axis for {technology} ({scope}). Left: D_clim (climate alone) and D_tec "
            f"(techno-economic parameters alone), the share of the capacity of the axis shortlist beyond the nominal top k + m. Right: the dominance "
            f"ratio rho = D_clim / (D_clim + D_tec) with the boundaries {rule.lower:.2f} and {rule.upper:.2f}; between them the profile is Mixed. "
            "The ratio is relative: read it with the displacements."
        )

        def draw(shown=shown, technology=technology, rule=rule):
            with style.thesis_style():
                fig, (ax_d, ax_r) = style.new_figure(1.0, 0.45, ncols=2)
                x = np.arange(len(shown))
                labels = []
                for at, row in shown.iterrows():
                    labels.append(
                        str(row["country"]) + ("" if row["available"] else "\n(unavailable)")
                    )
                    if not row["available"]:
                        continue
                    ax_d.bar(at - 0.2, row["d_clim"], 0.38, color=style.AXIS_COLORS["climate"])
                    ax_d.bar(
                        at + 0.2, row["d_tec"], 0.38, color=style.AXIS_COLORS["techno_economic"]
                    )
                ax_d.set_xticks(x, labels)
                ax_d.set_ylim(0.0, 1.0)
                ax_d.set_ylabel("Displacement D")
                ax_d.legend(
                    handles=[
                        Patch(color=style.AXIS_COLORS["climate"], label="D_clim (climate)"),
                        Patch(
                            color=style.AXIS_COLORS["techno_economic"],
                            label="D_tec (techno-economic)",
                        ),
                    ],
                    loc="upper right",
                    frameon=False,
                )
                ax_r.axhspan(rule.lower, rule.upper, color="0.88", zorder=0)
                for level in (rule.lower, rule.upper):
                    ax_r.axhline(level, color=style.REFERENCE_COLOR, linestyle="--", linewidth=0.8)
                colors = {
                    "climate_dominated": style.AXIS_COLORS["climate"],
                    "techno_economic_dominated": style.AXIS_COLORS["techno_economic"],
                    "mixed": style.REFERENCE_COLOR,
                }
                for at, row in shown.iterrows():
                    if row["available"] and pd.notna(row["rho"]):
                        ax_r.scatter(
                            at, row["rho"], s=36, color=colors.get(row["profile"], "0.5"), zorder=3
                        )
                    elif row["available"]:
                        ax_r.annotate(
                            "no\ndisplacement",
                            (at, 0.5),
                            ha="center",
                            va="center",
                            fontsize=style.FONT_SIZE - 1,
                        )
                ax_r.set_xticks(x, labels)
                ax_r.set_xlim(-0.6, len(shown) - 0.4)
                ax_r.set_ylim(0.0, 1.0)
                ax_r.set_ylabel("Dominance ratio rho")
                right = len(shown) - 0.45
                ax_r.text(
                    right,
                    rule.upper + 0.02,
                    "Climate-Dominated",
                    ha="right",
                    va="bottom",
                    fontsize=style.FONT_SIZE - 1,
                )
                ax_r.text(
                    right,
                    (rule.lower + rule.upper) / 2,
                    "Mixed",
                    ha="right",
                    va="center",
                    fontsize=style.FONT_SIZE - 1,
                )
                ax_r.text(
                    right,
                    rule.lower - 0.02,
                    "Techno-Economic-Dominated",
                    ha="right",
                    va="top",
                    fontsize=style.FONT_SIZE - 1,
                )
                return fig

        write_table(
            ctx, T_R7, "axis_displacement", frame, text, technology=technology, per_country=False
        )
        write_figure(
            ctx, T_R7, "axis_displacement", draw, text, technology=technology, per_country=False
        )


def t_r10(ctx: BuildContext) -> None:
    """T-R10, per technology: potential (GW, TWh) in cells above the hazard exposure thresholds by member, group and basis."""
    for technology in ctx.technologies:
        ctx.begin()
        members = members_table(ctx.reader).set_index("member")
        key = f"hazard_exposure_{technology}__core"
        try:
            table = ctx.reader.table(key, _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_R10, technology, str(exc))
            continue
        note = ""
        if table.empty:
            note = f" The table is empty: {_reason(ctx.reader, key)}."
        else:
            table = table.assign(window=table["member"].map(members["window"])).sort_values(
                ["hazard", "group", "basis", "ssp", "gcm", "member"], ignore_index=True
            )
        write_table(
            ctx,
            T_R10,
            "hazard_exposure",
            table,
            f"Potential of {technology} in cells above the hazard exposure thresholds, by SSP and window, for the cells of the F7 set and the nominal and robust top-k. "
            "Cells are called exposed, not lost: no loss function has been admitted. A member without the hazard channel has no row (not zero). "
            "The rows of hazard any_channel over the group economic_domain are the exposed energy of H5b (a cell counted once over the channels)."
            + note,
            technology=technology,
        )


def t_r12(ctx: BuildContext) -> None:
    """T-R12, per technology: potential below the cost threshold tau per member and land scenario, with the gap to the national target."""
    for technology in ctx.technologies:
        ctx.begin()
        members = members_table(ctx.reader).set_index("member")
        key = f"potential_below_tau_{technology}__core"
        try:
            table = ctx.reader.table(key, _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_R12, technology, str(exc))
            continue
        note = ""
        if table.empty:
            note = f" The table is empty: {_reason(ctx.reader, key)}."
        else:
            table = table.assign(
                gcm=table["member"].map(members["gcm"]),
                ssp=table["member"].map(members["ssp"]),
                window=table["member"].map(members["window"]),
            ).sort_values(
                ["land_scenario", "series", "basis", "ssp", "gcm", "member"], ignore_index=True
            )
        write_table(
            ctx,
            T_R12,
            "potential_below_tau",
            table,
            f"Potential of {technology} (GW, TWh/yr) below the cost threshold tau per member, against the national target. The central land set carries the draws (basis p10, p50, p90); "
            "the restrictive and permissive scenarios give the land range beside it at the nominal parameters (U-08). "
            "The series fixed_domain is the energy of the economic domain of H5 in each member."
            + note,
            technology=technology,
        )


def t_o2(ctx: BuildContext) -> None:
    """T-O2, per technology: MR against SR for the ranked cells, with the Kendall tau-b F7 wrote (agreement of the two rankings)."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            robustness = ctx.reader.table(
                f"robustness_{technology}__core", _VERSIONS, columns=["cell_class", "mr", "sr"]
            )
            hypothesis = ctx.reader.table(f"hypothesis_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_O2, technology, str(exc))
            continue
        ranked = robustness[(robustness["cell_class"] == "ranked")].dropna(subset=["mr", "sr"])
        tau = hypothesis[hypothesis["statistic"] == "mr_sr_kendall_tau_b"]["value"]
        if ranked.empty or tau.empty or pd.isna(tau.iloc[0]):
            ctx.skip(T_O2, technology, "no SR (tau is null, OQ-008) or no ranked cell")
            continue
        tau_value = float(tau.iloc[0])

        def draw(ranked=ranked, tau_value=tau_value, technology=technology):
            with style.thesis_style():
                fig, ax = style.new_figure(0.6, 0.8)
                ax.scatter(
                    ranked["mr"],
                    ranked["sr"],
                    s=4,
                    alpha=0.5,
                    color=style.technology_color(ctx.technologies, technology),
                    linewidths=0,
                    rasterized=True,
                )
                ax.set_xlabel("Max regret MR (relative)")
                ax.set_ylabel("Satisficing robustness SR (share of futures)")
                ax.annotate(
                    f"Kendall tau-b (MR, -SR) = {tau_value:.3f}",
                    xy=(0.03, 0.04),
                    xycoords="axes fraction",
                    fontsize=style.FONT_SIZE - 1,
                )
                return fig

        write_figure(
            ctx,
            T_O2,
            "mr_sr_agreement",
            draw,
            f"Agreement between the max-regret and satisficing criteria for {technology}: each point is a ranked cell. Kendall tau-b is taken between MR and -SR, so a positive value means the two criteria order the cells alike.",
            technology=technology,
        )


def t_r9(ctx: BuildContext) -> None:
    """T-R9: external validation (F7b): excluded share under existing plants, enrichment in the lowest-LCOE deciles, comparison with published
    potentials and the units behind them."""
    caption_tail = " Existing plants reflect past auctions, policy and grid access: the table is plausibility evidence, not accuracy (M-F7b-04)."
    tables = {
        "exclusion_shares": (
            "exclusion_shares",
            "Excluded share of the pixels under existing plants, by constraint (E1 to E6 and combined).",
        ),
        "enrichment": (
            "enrichment",
            "Capacity of existing plants against the deciles of eligible area ordered by the nominal LCOE at the reference member.",
        ),
        "published_comparison": (
            "published_comparison",
            "National technical potential at the reference member beside published estimates, with the land-scenario interval.",
        ),
        "validation_units": ("units", "Existing units with their pixel and decile."),
    }
    for key, (what, text) in tables.items():
        ctx.begin()
        try:
            table = ctx.reader.table(key, {VALIDATION_TABLE_SCHEMA_VERSION})
        except MissingArtifactError as exc:
            ctx.skip(T_R9, key, str(exc))
            continue
        note = ""
        if table.empty:
            note = f" The table is empty: {_reason(ctx.reader, key)}."
        write_table(
            ctx,
            T_R9,
            what,
            table,
            text + caption_tail + note,
            latex=key != "validation_units",
        )


def t_o1(ctx: BuildContext) -> None:
    """T-O1, per technology: the PRIM box chosen for the core window (M-F7-08), its limits on the share of the range of each restricted descriptor, the
    5th to 95th percentile of each bound over the bootstrap replicates and the share of replicates that restrict the descriptor."""
    for technology in ctx.technologies:
        ctx.begin()
        try:
            box = ctx.reader.table(f"prim_box_{technology}__core", _VERSIONS)
            boot = ctx.reader.table(f"prim_bootstrap_{technology}__core", _VERSIONS)
            trajectory = ctx.reader.table(f"prim_boxes_{technology}__core", _VERSIONS)
        except MissingArtifactError as exc:
            ctx.skip(T_O1, technology, str(exc))
            continue
        if box.empty:
            ctx.skip(T_O1, technology, _reason(ctx.reader, f"prim_box_{technology}__core"))
            continue
        primary = box[box["primary"]].iloc[0]
        if primary["status"] != "box_found":
            ctx.skip(
                T_O1, technology, f"no box to draw: the primary search ended as {primary['status']}"
            )
            continue
        restricted = [d for d in str(primary["restricted"]).split("|") if d]
        first = trajectory[trajectory["step"] == 0].iloc[0]
        real = [d for d in restricted if f"{d}__min" in box.columns]
        categorical = [d for d in restricted if d not in real]

        def share(value: float, name: str, first=first) -> float:
            low, high = float(first[f"{name}__min"]), float(first[f"{name}__max"])
            return 0.0 if high == low else (float(value) - low) / (high - low)

        def bounds(kind: str, name: str, boot=boot) -> tuple[float, float, float] | None:
            row = boot[(boot["kind"] == kind) & (boot["name"] == name)]
            if row.empty or pd.isna(row.iloc[0]["p50"]):
                return None
            r = row.iloc[0]
            return float(r["p_low"]), float(r["p50"]), float(r["p_high"])

        frequency = boot[boot["kind"] == "restriction"].set_index("name")["frequency"]
        density = boot[boot["kind"] == "density"].iloc[0]
        coverage = boot[boot["kind"] == "coverage"].iloc[0]
        rows = []
        for name in real:
            rows.append(
                {
                    "descriptor": name,
                    "lower": primary[f"{name}__min"],
                    "upper": primary[f"{name}__max"],
                    "lower_p_low": (bounds("lower", name) or (None,) * 3)[0],
                    "lower_p_high": (bounds("lower", name) or (None,) * 3)[2],
                    "upper_p_low": (bounds("upper", name) or (None,) * 3)[0],
                    "upper_p_high": (bounds("upper", name) or (None,) * 3)[2],
                    "restricted_in_share_of_replicates": frequency.get(name),
                }
            )
        for name in categorical:
            rows.append(
                {
                    "descriptor": name,
                    "lower": primary[f"{name}__in"],
                    "upper": None,
                    "restricted_in_share_of_replicates": frequency.get(name),
                }
            )
        write_table(
            ctx,
            T_O1,
            "prim_box",
            pd.DataFrame(rows),
            f"PRIM box chosen for {technology}: the limits of the restricted descriptors with the 5th to 95th percentile of each bound over the bootstrap replicates and the share of replicates that restrict the descriptor.",
            technology=technology,
        )

        def draw(
            technology=technology,
            real=real,
            categorical=categorical,
            primary=primary,
            frequency=frequency,
            density=density,
            coverage=coverage,
            share=share,
            bounds=bounds,
        ):
            with style.thesis_style():
                n = max(len(real) + len(categorical), 1)
                fig, ax = style.new_figure(0.8, 0.25 + 0.12 * n)
                color = style.technology_color(ctx.technologies, technology)
                labels = []
                for at, name in enumerate(real):
                    low, high = (
                        share(primary[f"{name}__min"], name),
                        share(primary[f"{name}__max"], name),
                    )
                    ax.barh(at, high - low, left=low, height=0.45, color=color, alpha=0.8)
                    for kind, edge in (("lower", low), ("upper", high)):
                        spread = bounds(kind, name)
                        if spread is not None:
                            ax.plot(
                                [share(spread[0], name), share(spread[2], name)],
                                [at, at],
                                color="black",
                                linewidth=1.0,
                            )
                    labels.append(f"{name}\n({_pct(frequency.get(name))} of replicates)")
                for offset, name in enumerate(categorical):
                    at = len(real) + offset
                    ax.text(
                        0.5,
                        at,
                        f"keeps: {primary[f'{name}__in'].replace('|', ', ')}",
                        ha="center",
                        va="center",
                    )
                    labels.append(f"{name}\n({_pct(frequency.get(name))} of replicates)")
                ax.set_yticks(range(len(labels)), labels)
                ax.set_xlim(-0.02, 1.02)
                ax.invert_yaxis()
                ax.set_xlabel(
                    "Position within the range of the descriptor (0 = lowest, 1 = highest value)"
                )
                ax.set_title(
                    f"density {primary['density']:.2f} (P5 to P95 {density['p_low']:.2f} to {density['p_high']:.2f}), "
                    f"coverage {primary['coverage']:.2f} (P5 to P95 {coverage['p_low']:.2f} to {coverage['p_high']:.2f})",
                    fontsize=style.FONT_SIZE - 1,
                )
                return fig

        write_figure(
            ctx,
            T_O1,
            "prim_box",
            draw,
            f"PRIM box under which the present-optimal shortlist of {technology} stops being a good choice: bars are the limits of the box chosen, lines the 5th to 95th percentile of each bound over the bootstrap replicates.",
            technology=technology,
        )


def _pct(value: object) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{100 * float(value):.0f}%"
