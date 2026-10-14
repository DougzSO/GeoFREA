"""T-M1: the framework DAG, drawn from the graph of the orchestrator and not by hand (D-F8-019).

The graph is `phase_graph(phase specs)` of `geofrea.core.orchestrator`: an edge from phase A to phase B when B requires an artifact that A produces.
The member and sample axes are marked on the phases that `thesis_figures.dag_axes` lists; a name in that list that is not a phase of the graph
is an error, so the marking cannot drift from the code. The figure holds no data: the number of members and the size of the sample are read
from the `members` artifact and the sampler of `experiments.yaml`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from geofrea.results_synthesis import style
from geofrea.results_synthesis.inputs import MissingArtifactError
from geofrea.results_synthesis.members import members_table
from geofrea.results_synthesis.output import BuildContext, NotBuilt, write_figure

T_M1 = "T-M1"
BOX_W, BOX_H = 0.78, 0.34
MEMBER_COLOR, SAMPLE_COLOR = "#1f78b4", "#e6550d"


def layers(graph: Mapping[str, Sequence[str]]) -> dict[str, int]:
    """The layer of each phase: the length of the longest chain of dependencies below it.

    Raises:
        ValueError: a dependency names a phase that is not in the graph, or the graph has a cycle.
    """
    for phase, needs in graph.items():
        missing = [n for n in needs if n not in graph]
        if missing:
            raise ValueError(f"{phase} depends on {missing}, which are not phases of the graph")
    level: dict[str, int] = {}
    pending = dict(graph)
    while pending:
        ready = [p for p, needs in pending.items() if all(n in level for n in needs)]
        if not ready:
            raise ValueError(f"the phase graph has a cycle among {sorted(pending)}")
        for phase in ready:
            level[phase] = 1 + max((level[n] for n in pending[phase]), default=-1)
            del pending[phase]
    return level


def positions(graph: Mapping[str, Sequence[str]]) -> dict[str, tuple[float, float]]:
    """`(x, y)` of each phase: x is the layer, y spreads the phases of a layer in the order of their names, centred on 0."""
    level = layers(graph)
    by_level: dict[int, list[str]] = {}
    for phase in sorted(graph):
        by_level.setdefault(level[phase], []).append(phase)
    out = {}
    for lvl, phases in by_level.items():
        for i, phase in enumerate(phases):
            out[phase] = (float(lvl), (len(phases) - 1) / 2.0 - i)
    return out


def edges(graph: Mapping[str, Sequence[str]]) -> list[tuple[str, str]]:
    """`(from, to)` for every dependency, sorted."""
    return sorted((n, phase) for phase, needs in graph.items() for n in needs)


def t_m1(ctx: BuildContext) -> None:
    """T-M1: the phases of the pipeline as a DAG with the member and sample axes."""
    graph = ctx.phase_graph
    if not graph:
        raise NotBuilt(
            "no phase graph was given (the thesis build of main.py gives the graph of the orchestrator)"
        )
    axes = ctx.experiments.thesis_figures.dag_axes
    unknown = sorted((set(axes.member) | set(axes.sample)) - set(graph))
    if unknown:
        raise NotBuilt(
            f"thesis_figures.dag_axes names {unknown}, which are not phases of the graph"
        )
    ctx.begin()
    n_members = None
    try:
        members = members_table(ctx.reader)
        n_members = len(members)
    except MissingArtifactError:
        pass
    sample = ctx.experiments.sampler.initial_size
    where = positions(graph)
    member_text = f"{n_members} members" if n_members is not None else "members"
    text = (
        "Framework of GeoFREA as the directed acyclic graph of its phases, drawn from the requires and produces of the phase specifications "
        "(an arrow from A to B when B reads an artifact that A produces). "
        f"Blue marks the phases that run along the member axis ({member_text}: the reference and the GCM by SSP by window projections); "
        f"orange marks those that run along the sample axis (draws of the uncertain parameters, {sample} in the first batch)."
    )

    def draw():
        with style.thesis_style():
            width = max(x for x, _ in where.values()) + 1
            height = max(max(abs(y) for _, y in where.values()) * 2 + 1, 1)
            fig, ax = style.plt.subplots(
                figsize=(style.PAGE_WIDTH_IN * 1.6, max(3.0, 0.5 * height + 0.8)),
                layout="constrained",
            )
            ax.set_xlim(-0.6, width - 0.4)
            ax.set_ylim(-height / 2 - 0.4, height / 2 + 0.4)
            ax.axis("off")
            for src, dst in edges(graph):
                (x0, y0), (x1, y1) = where[src], where[dst]
                ax.add_patch(
                    FancyArrowPatch(
                        (x0 + BOX_W / 2, y0),
                        (x1 - BOX_W / 2, y1),
                        arrowstyle="-|>",
                        mutation_scale=6,
                        linewidth=0.4,
                        color="#888888",
                        connectionstyle="arc3,rad=0.0",
                        zorder=1,
                    )
                )
            for phase, (x, y) in where.items():
                on_member, on_sample = phase in axes.member, phase in axes.sample
                edge = MEMBER_COLOR if on_member else SAMPLE_COLOR if on_sample else "#444444"
                ax.add_patch(
                    FancyBboxPatch(
                        (x - BOX_W / 2, y - BOX_H / 2),
                        BOX_W,
                        BOX_H,
                        boxstyle="round,pad=0.0,rounding_size=0.05",
                        facecolor="white",
                        edgecolor=edge,
                        linewidth=1.4 if (on_member or on_sample) else 0.6,
                        zorder=2,
                    )
                )
                ax.text(
                    x,
                    y,
                    phase.replace("_", "\n", 1),
                    ha="center",
                    va="center",
                    fontsize=5.5,
                    zorder=3,
                )
                if on_member and on_sample:
                    ax.plot(
                        [x - BOX_W / 2, x + BOX_W / 2],
                        [y - BOX_H / 2] * 2,
                        color=SAMPLE_COLOR,
                        linewidth=2.2,
                        zorder=3,
                    )
            return fig

    write_figure(
        ctx,
        T_M1,
        "framework_dag",
        draw,
        text,
        per_country=False,
        extra={
            "edges": [list(e) for e in edges(graph)],
            "member_axis": sorted(axes.member),
            "sample_axis": sorted(axes.sample),
        },
    )
