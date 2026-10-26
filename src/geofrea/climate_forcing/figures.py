"""Figures of the climate forcing in the common map style (COMMAND 68; spec v2 T-09; M-F4-06, A-08).

What the figures of F4 show is the ensemble, not a model:

  - one sheet per SSP and window (`ensemble_sheet`): the multi-model mean of the change of the solar radiation (%), of the wind speed (%) and of
    the temperature (K) against 1995-2014, with dots where fewer than two thirds of the models agree on the sign of the change. Solar and
    temperature use the 6 GCMs of the ensemble, wind the 5 that have a wind channel (M-F4-02 item 6);
  - one sheet per variable with the SSPs in the rows and the windows in the columns (`grid_sheet`), on one scale shared by all its maps;
  - one sheet per member (`member_sheet`), supplementary material under `figures/members/`: the same three panels for one GCM, SSP and window.

A ratio is drawn as a percentage change (`(ratio - 1) x 100`), the temperature in K. The colour limits of a variable are shared by every sheet of
the country (the percentiles of all the ensemble means, symmetric about zero for a change of a ratio), so the same colour means the same change in
every SSP and window. The GCM fields are coarse (about 100 km) and are interpolated to the 0.05 degree cells, so the maps are smoothed for display
(`display_smoothing`, `auto` | `off`) and say so with the native resolution in the subtitle. Nothing here changes a forcing value.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from geofrea.core.scale import active_scale
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import Lattice, MapContext, lattice_of, to_grid
from geofrea.viz.panels import PanelFigure, add_panel_colorbar, new_panels, stipple_note

AGREEMENT = 2.0 / 3.0  # the dots: fewer than this share of the models agree on the sign
REFERENCE_PERIOD = "1995–2014"
KM_PER_DEG = 111.32
FIGURE_PHASE = "F4"


@dataclass(frozen=True)
class Variable:
    """One panel of the figures: the column of `forcing.parquet`, how it becomes the drawn quantity, its colours and its words."""

    key: str  # file name piece
    column: str
    kind: str  # the colormap kind of `mapstyle.colormap_for`
    caption: str
    label: str  # colour bar label
    ratio: bool  # a ratio drawn as a percentage change
    diverging: bool


VARIABLES = (
    Variable("solar", "delta_rsds", "delta", "Solar radiation change", "Change (%)", True, True),
    Variable("wind", "delta_wind", "delta_alt", "Wind speed change", "Change (%)", True, True),
    Variable(
        "temperature",
        "dT",
        "temperature",
        "Temperature change",
        "Change (K)",
        False,
        False,
    ),
)
BY_KEY = {v.key: v for v in VARIABLES}


# ------------------------------------------------------------------------------------------------------------------------------ the grids


def drawn_quantity(variable: Variable, raw: np.ndarray) -> np.ndarray:
    """What is drawn: the percentage change of a ratio, the change of a temperature as it is."""
    values = np.asarray(raw, dtype="float32")
    return (values - 1.0) * 100.0 if variable.ratio else values


@dataclass(frozen=True)
class MemberInfo:
    member: str
    gcm: str
    ssp: str
    window: str  # `2041-2070`
    lat_res_deg: float
    lon_res_deg: float


def read_members(members_yaml: Path) -> list[MemberInfo]:
    """The members with a GCM (the reference member `m0` has none) from `members.yaml`, with the native grid of their GCM."""
    import yaml

    document = yaml.safe_load(Path(members_yaml).read_text(encoding="utf-8"))
    out = []
    for entry in document["members"]:
        if "gcm" not in entry:
            continue
        grid = entry.get("native_grid") or {}
        out.append(
            MemberInfo(
                str(entry["member"]),
                str(entry["gcm"]),
                str(entry["ssp"]),
                str(entry["window"]),
                float(grid.get("lat_resolution_deg", math.nan)),
                float(grid.get("lon_resolution_deg", math.nan)),
            )
        )
    return out


def member_grids(
    forcing: pd.DataFrame, members: Sequence[MemberInfo], lattice: Lattice
) -> dict[str, dict[str, np.ndarray]]:
    """For each member, the drawn quantity of each variable on the lattice (NaN where the member has no valid value: a wind factor that
    was masked, or a GCM with no wind channel)."""
    codes = forcing["member"].astype(str)
    out: dict[str, dict[str, np.ndarray]] = {}
    for info in members:
        rows = forcing[codes == info.member]
        out[info.member] = {
            v.key: drawn_quantity(
                v, to_grid(rows["cell_id"].to_numpy(), rows[v.column].to_numpy(), lattice)
            )
            for v in VARIABLES
        }
    return out


# -------------------------------------------------------------------------------------------------------------------------- the ensemble


@dataclass(frozen=True)
class EnsembleField:
    """The multi-model mean of one variable for one SSP and window, with where the models disagree on the sign."""

    variable: str
    ssp: str
    window: str
    mean: np.ndarray  # NaN where no model has a value
    disagree: (
        np.ndarray
    )  # True where fewer than `AGREEMENT` of the models with a value agree on the sign
    n_models: int  # how many models contributed anywhere
    gcms: tuple[str, ...]


def ensemble_field(
    variable: str, ssp: str, window: str, members: Sequence[MemberInfo], grids: dict
) -> EnsembleField:
    """Mean over the GCMs of `(ssp, window)` of `grids[member][variable]`, and the sign agreement of the models that have a value.

    A cell where no GCM has a value is NaN. The agreement of a cell is the larger of the shares of the models with a positive and with a
    negative change; a change of exactly zero counts for neither. A cell where fewer than `AGREEMENT` agree is marked.
    """
    chosen = [m for m in members if m.ssp == ssp and m.window == window]
    stack = np.stack([grids[m.member][variable] for m in chosen])
    valid = np.isfinite(stack)
    count = valid.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, np.nansum(stack, axis=0) / np.maximum(count, 1), np.nan).astype(
            "float32"
        )
        positive = (np.where(valid, stack, 0.0) > 0).sum(axis=0)
        negative = (np.where(valid, stack, 0.0) < 0).sum(axis=0)
        agreement = np.maximum(positive, negative) / np.maximum(count, 1)
    disagree = (count > 0) & (agreement < AGREEMENT - 1e-9)
    contributing = tuple(m.gcm for m, ok in zip(chosen, valid.any(axis=(1, 2)), strict=True) if ok)
    return EnsembleField(variable, ssp, window, mean, disagree, len(contributing), contributing)


def ensemble_fields(
    members: Sequence[MemberInfo], grids: dict
) -> dict[tuple[str, str], dict[str, EnsembleField]]:
    """The ensemble field of every variable for every (SSP, window) of `members`."""
    scenarios = sorted({(m.ssp, m.window) for m in members})
    return {
        (ssp, window): {
            v.key: ensemble_field(v.key, ssp, window, members, grids) for v in VARIABLES
        }
        for ssp, window in scenarios
    }


def shared_scale(fields: dict, variable: str) -> tuple[float, float]:
    """The colour limits of a variable, shared by every SSP and window of the country: the percentiles of all the ensemble means together,
    symmetric about zero for a change of a ratio."""
    spec = ms.ScaleSpec("shared", diverging=BY_KEY[variable].diverging)
    return ms.shared_limits(
        [f[variable].mean[np.isfinite(f[variable].mean)] for f in fields.values()], spec
    )


def native_note(members: Sequence[MemberInfo], lat_mid: float) -> str:
    """The native size of the GCM cells of `members` at the latitude of the country, for the subtitle: `~110–280 km`."""
    sides = []
    for m in members:
        if math.isfinite(m.lat_res_deg) and math.isfinite(m.lon_res_deg):
            lat_km = m.lat_res_deg * KM_PER_DEG
            lon_km = m.lon_res_deg * KM_PER_DEG * math.cos(math.radians(lat_mid))
            sides.append(math.sqrt(lat_km * lon_km))
    if not sides:
        return "native resolution of the GCMs"
    lo, hi = 5 * round(min(sides) / 5), 5 * round(max(sides) / 5)
    return f"~{lo:g} km" if lo == hi else f"~{lo:g}–{hi:g} km"


# ---------------------------------------------------------------------------------------------------------------------------- the sheets


def _window_label(window: str) -> str:
    return window.replace("-", "–")


def _resolution_text(members: Sequence[MemberInfo], ctx: MapContext) -> str:
    lat = (ctx.extent[2] + ctx.extent[3]) / 2.0
    return f"GCM fields {native_note(members, lat)}, interpolated to {active_scale().cell_deg:g}°"


def _plan(sheet: PanelFigure, grid, extent, resolution: str, mode: str) -> ms.DisplayPlan:
    """Whether the maps of the sheet are smoothed for display (they come from a GCM, so `auto` smooths them) and what the subtitle says."""
    return ms.plan_display(
        sheet.panels[0], grid, extent, resolution, None, mode, coarse_source=True
    )


def _norm(variable: str, values: np.ndarray, limits: tuple[float, float]) -> ms.NormInfo:
    finite = values[np.isfinite(values)]
    if not finite.size:
        finite = np.array([0.0])
    return ms.resolve_scale(finite, ms.ScaleSpec("shared", limits=limits), limits)


def _scale_note(infos: Sequence[ms.NormInfo]) -> str:
    return "Scale: shared" if any(i.extend != "neither" for i in infos) else ""


def _meta(sheet: PanelFigure, limits: dict[str, tuple[float, float]], plan, mode: str, **extra):
    sheet.meta.update(ms.display_meta(plan, mode))
    for key, (lo, hi) in limits.items():
        sheet.meta[f"scale_limits_{key}"] = f"{lo:.6g},{hi:.6g}"
    sheet.meta["scale_mode"] = "shared"
    sheet.meta["scale_scope"] = "per_country"
    sheet.meta["agreement_threshold"] = f"{AGREEMENT:.3f}"
    sheet.meta.update({k: str(v) for k, v in extra.items()})


def _draw(panel, grid, extent, cmap, norm, plan: ms.DisplayPlan):
    panel.fill_country()  # the part of the country with no value stays grey (and the note says so)
    return panel.draw_raster(
        np.ma.masked_invalid(grid), extent, cmap=cmap, norm=norm, smooth=plan.factor
    )


def ensemble_sheet(
    ctx: MapContext,
    iso: str,
    ssp: str,
    window: str,
    fields: dict[str, EnsembleField],
    limits: dict[str, tuple[float, float]],
    members: Sequence[MemberInfo],
    lattice: Lattice,
    *,
    display_smoothing: str = "auto",
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """One sheet: the three variables as maps of the ensemble mean for one SSP and window, with dots where the models disagree on the sign."""
    extent = lattice.extent
    chosen = [m for m in members if m.ssp == ssp and m.window == window]
    n_solar, n_wind = fields["solar"].n_models, fields["wind"].n_models
    resolution = _resolution_text(chosen, ctx)
    infos = {v.key: _norm(v.key, fields[v.key].mean, limits[v.key]) for v in VARIABLES}
    captions = [v.caption for v in VARIABLES]
    scale = _scale_note(list(infos.values()))
    notes = [stipple_note(), gap_note({k: f.mean for k, f in fields.items()})]

    def build(shown: str | None):
        return new_panels(
            ctx.polygon,
            iso=iso,
            variable=f"Climate forcing · {ssp} · {_window_label(window)} vs {REFERENCE_PERIOD}",
            captions=captions,
            n_rows=1,
            n_cols=3,
            subtitle=ms.format_subtitle(
                f"Ensemble mean of {n_solar} GCMs ({n_wind} for wind)", shown, scale
            ),
            total_text="\n".join(n for n in notes if n),
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            country=country,
            preset=preset,
            bar="each",
        )

    sheet = build(resolution)
    plan = _plan(sheet, fields["solar"].mean, extent, resolution, display_smoothing)
    if plan.shown != resolution:
        ms.plt.close(sheet.fig)
        sheet = build(plan.shown)
    for i, v in enumerate(VARIABLES):
        field = fields[v.key]
        panel = sheet.panels[i]
        image = _draw(
            panel,
            field.mean,
            extent,
            ms.colormap_for(v.kind),
            infos[v.key].norm,
            plan,
        )
        panel.stipple(field.disagree, extent)
        add_panel_colorbar(sheet, image, v.label, infos[v.key].extend, i)
    _meta(sheet, limits, plan, display_smoothing, n_gcms_solar=n_solar, n_gcms_wind=n_wind)
    sheet.meta.update({"ssp": ssp, "window": window, "data_source": "F4 forcing, ensemble mean"})
    return sheet


def gap_note(means: dict[str, np.ndarray]) -> str | None:
    """The note on the grey part of a map: cells of the country where the solar radiation has a value and another variable has none (a GCM with
    no wind channel, or a wind factor that was masked), by variable; None when there are none."""
    have = np.isfinite(means["solar"])
    names = [
        BY_KEY[k].caption.lower().replace(" change", "")
        for k, m in means.items()
        if (have & ~np.isfinite(m)).any()
    ]
    return f"Grey: no value ({', '.join(names)})" if names else None


def grid_sheet(
    ctx: MapContext,
    iso: str,
    variable: str,
    fields: dict[tuple[str, str], dict[str, EnsembleField]],
    limits: tuple[float, float],
    members: Sequence[MemberInfo],
    lattice: Lattice,
    *,
    display_smoothing: str = "auto",
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """The summary sheet of one variable: the SSPs in the rows, the windows in the columns, one scale and one colour bar for all."""
    v = BY_KEY[variable]
    extent = lattice.extent
    ssps = sorted({s for s, _ in fields})
    windows = sorted({w for _, w in fields})
    scenarios = [(s, w) for s in ssps for w in windows]
    captions = [f"{s} · {_window_label(w)}" for s, w in scenarios]
    resolution = _resolution_text(members, ctx)
    values = np.concatenate(
        [fields[sw][variable].mean[np.isfinite(fields[sw][variable].mean)] for sw in scenarios]
    )
    info = _norm(variable, values, limits)
    scale = _scale_note([info])

    def build(shown: str | None):
        return new_panels(
            ctx.polygon,
            iso=iso,
            variable=f"{v.caption} by SSP and window vs {REFERENCE_PERIOD}",
            captions=captions,
            n_rows=len(ssps),
            n_cols=len(windows),
            subtitle=ms.format_subtitle("Ensemble mean of the GCMs", shown, scale),
            total_text=stipple_note(),
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            country=country,
            preset=preset,
            bar="shared",
        )

    sheet = build(resolution)
    plan = _plan(sheet, fields[scenarios[0]][variable].mean, extent, resolution, display_smoothing)
    if plan.shown != resolution:
        ms.plt.close(sheet.fig)
        sheet = build(plan.shown)
    image = None
    for panel, sw in zip(sheet.panels, scenarios, strict=True):
        field = fields[sw][variable]
        image = _draw(panel, field.mean, extent, ms.colormap_for(v.kind), info.norm, plan)
        panel.stipple(field.disagree, extent)
    add_panel_colorbar(sheet, image, v.label, info.extend)
    _meta(sheet, {variable: limits}, plan, display_smoothing, variable=variable)
    sheet.meta["data_source"] = "F4 forcing, ensemble mean"
    return sheet


def member_sheet(
    ctx: MapContext,
    iso: str,
    info: MemberInfo,
    grids: dict[str, np.ndarray],
    limits: dict[str, tuple[float, float]],
    lattice: Lattice,
    *,
    display_smoothing: str = "auto",
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """Supplementary sheet: the three variables of one member (a GCM, an SSP, a window). A variable the GCM has no value for is grey and
    the note says why (a GCM with no wind channel, or a wind factor that was masked)."""
    extent = lattice.extent
    resolution = _resolution_text([info], ctx)
    norms = {v.key: _norm(v.key, grids[v.key], limits[v.key]) for v in VARIABLES}
    notes = [gap_note(grids)]
    scale = _scale_note(list(norms.values()))

    def build(shown: str | None):
        return new_panels(
            ctx.polygon,
            iso=iso,
            variable=f"Climate forcing · {info.gcm} · {info.ssp} · {_window_label(info.window)} vs {REFERENCE_PERIOD}",
            captions=[v.caption for v in VARIABLES],
            n_rows=1,
            n_cols=3,
            subtitle=ms.format_subtitle("One GCM, supplementary", shown, scale),
            total_text="\n".join(n for n in notes if n) or None,
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            country=country,
            preset=preset,
            bar="each",
        )

    sheet = build(resolution)
    plan = _plan(
        sheet,
        next(g for g in grids.values() if np.isfinite(g).any()),
        extent,
        resolution,
        display_smoothing,
    )
    if plan.shown != resolution:
        ms.plt.close(sheet.fig)
        sheet = build(plan.shown)
    for i, v in enumerate(VARIABLES):
        panel = sheet.panels[i]
        panel.fill_country()
        image = panel.draw_raster(
            np.ma.masked_invalid(grids[v.key]),
            extent,
            cmap=ms.colormap_for(v.kind),
            norm=norms[v.key].norm,
            smooth=plan.factor if np.isfinite(grids[v.key]).any() else None,
        )
        add_panel_colorbar(sheet, image, v.label, norms[v.key].extend, i)
    _meta(sheet, limits, plan, display_smoothing, gcm=info.gcm, ssp=info.ssp, window=info.window)
    sheet.meta["data_source"] = "F4 forcing, one member"
    return sheet


# ---------------------------------------------------------------------------------------------------------------------- the whole country


def ensemble_name(iso: str, ssp: str, window: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "climate-forcing", None, ssp, window)


def grid_name(iso: str, variable: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "climate-forcing-grid", variable)


def member_name(iso: str, info: MemberInfo) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "forcing", info.gcm, info.ssp, info.window)


def draw_country(
    iso: str,
    forcing: pd.DataFrame,
    members: Sequence[MemberInfo],
    ctx: MapContext,
    out_dir: Path,
    *,
    display_smoothing: str = "auto",
    with_members: bool = True,
    country: str | None = None,
    preset: str = "thesis",
) -> list[Path]:
    """Every figure of F4 of one country: the ensemble sheets (one per SSP and window), the three summary grids and, under `members/`, the
    supplementary sheets of the members. Returns the files written, the index of each folder included."""
    lattice = lattice_of(forcing["cell_id"].to_numpy())
    grids = member_grids(forcing, members, lattice)
    fields = ensemble_fields(members, grids)
    limits = {v.key: shared_scale(fields, v.key) for v in VARIABLES}
    out_dir = Path(out_dir)
    written: list[Path] = []
    kw = {"display_smoothing": display_smoothing, "preset": preset, "country": country}
    for (ssp, window), by_variable in fields.items():
        sheet = ensemble_sheet(ctx, iso, ssp, window, by_variable, limits, members, lattice, **kw)
        written.append(ms.save_png(sheet, out_dir / ensemble_name(iso, ssp, window)))
    for v in VARIABLES:
        sheet = grid_sheet(ctx, iso, v.key, fields, limits[v.key], members, lattice, **kw)
        written.append(ms.save_png(sheet, out_dir / grid_name(iso, v.key)))
    ms.write_figures_index(out_dir)
    if with_members:
        member_dir = out_dir / "members"
        for info in members:
            sheet = member_sheet(ctx, iso, info, grids[info.member], limits, lattice, **kw)
            written.append(ms.save_png(sheet, member_dir / member_name(iso, info)))
        ms.write_figures_index(member_dir)
    return written
