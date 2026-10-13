"""T-R6, T-R10, T-R12 and T-O2 from the F7 tables, and T-R9 from the F7b tables: reads of persisted artifacts (M-F8-01).

A table F7 or F7b wrote empty because a decision parameter is null is written empty here too, with the reason in the caption: "not
available" is never shown as zero (D7, D-F8-007).
"""

from __future__ import annotations

import pandas as pd

from geofrea.external_validation.table_schemas import VALIDATION_TABLE_SCHEMA_VERSION
from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import ArtifactReader, MissingArtifactError
from geofrea.results_synthesis.members import members_table
from geofrea.results_synthesis.output import BuildContext, write_figure, write_table
from geofrea.robustness_analysis.table_schemas import ROBUSTNESS_TABLE_SCHEMA_VERSION

T_R6, T_R9, T_R10, T_R12, T_O2 = "T-R6", "T-R9", "T-R10", "T-R12", "T-O2"
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
# the rule as F7 applies it (M-F7-07). H1 has two primary statistics (H1a and H1b), the second one in the `*_2` columns.
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
_SUMMARIES = ("h1", "h2", "h3")


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
    return common | {
        "statistic": "h3_beyond_reach_share",
        "value": row["d"],
        "reference": row["d_ref"],
        "threshold": row["delta"],
        "rule": "supported if D >= delta; not testable if D_ref < delta",
    }


def t_r6(ctx: BuildContext) -> None:
    """T-R6, per technology: the H1, H2 and H3 statistics for the core window, the 2071-2100 window and the other cell scale, each with its
    pre-registered rule and verdict; the verdict table (one row per hypothesis: primary statistic, reference, threshold, verdict); and the
    F7 summaries of H1 (C_k, V_k), H2 (O) and H3 (D, the price and the benefit of robustness) with their sensitivities."""
    for technology in ctx.technologies:
        ctx.begin()
        statistics: list[pd.DataFrame] = []
        summaries: dict[str, list[pd.DataFrame]] = {name: [] for name in _SUMMARIES}
        for reader in _readers(ctx):
            for role in ROLES:
                try:
                    hypothesis = reader.table(f"hypothesis_{technology}__{role}", _VERSIONS)
                except MissingArtifactError as exc:
                    ctx.skip(T_R6, f"{technology} {reader.scale_id} {role}", str(exc))
                    continue
                part = hypothesis[hypothesis["hypothesis"].isin(["H1", "H2", "H3"])]
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
                f"H1, H2 and H3 statistics for {technology}: core window, 2071-2100 window and the other cell scale. A value with p10 and p90 is the central value at the nominal parameters and the range over the draws; a null verdict means no rule is pre-registered or the hypothesis is not testable, not that it fails.",
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
        if verdicts:
            frame = pd.DataFrame(verdicts, columns=VERDICT_COLUMNS)
            frame["_order"] = frame["hypothesis"].map({"H1": 1, "H2": 2, "H3": 3})
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
                f"Verdict of H1, H2 and H3 for {technology}, one row per hypothesis, window and scale: the primary statistic, its reference value (the value expected by chance), the pre-registered threshold and the verdict, read from the F7 summary tables. H1 has two primary statistics (H1a and H1b, the second in the columns ending in 2). A sensitivity never revises a verdict.",
                technology=technology,
            )
        captions = {
            "h1": f"H1 for {technology}: core share C_k (H1a), vulnerable share V_k (H1b), the chance-level reference (k/n)^2 and the verdict, with the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
            "h2": f"H2 for {technology}: the Capacity Overlap Index O of the cell and the Admin1 selections, the reference T/Q_max, the verdict, the robustness penalty and the total variation distance, with the decision profile over gamma and the sensitivities (variant column) beside the primary result. A sensitivity never revises the verdict.",
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
            "Cells are called exposed, not lost: no loss function has been admitted. A member without the hazard channel has no row (not zero)."
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
            "the restrictive and permissive scenarios give the land range beside it at the nominal parameters (U-08)."
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
