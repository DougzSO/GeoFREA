"""Climate members and `members.yaml` (M-F4-01, M-F4-06, D-F4-004).

A member is `m = (gcm, ssp, window)`, plus the reference member `m0` with no change. The ensemble itself
(GCMs, SSPs, windows) is configuration: `config/experiments.yaml` `gcm_ensemble` (OQ-009, option C). Every member
carries a declaration of which channels it has (resource always; hazard only for ISIMIP3b models, D-F4-003/004)
and the provenance of the files its change factors come from (path, sha256, realization, native grid).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from geofrea.core.constants import REFERENCE_PERIOD
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry

SSP_EXPERIMENT = {"SSP1-2.6": "ssp126", "SSP3-7.0": "ssp370", "SSP5-8.5": "ssp585"}
VARIABLES = ("rsds", "sfcWind", "tas")
# The channels a member declares (M-F4-06). A technology needs the resource channels of its capacity-factor model: solar reads
# rsds and tas, wind reads the wind ratio. The hazard channel is context only and is not a requirement of any technology.
CHANNEL_NAMES = ("resource_rsds", "resource_tas", "resource_wind", "hazard")
CHANNELS_BY_CF_MODEL: dict[str, tuple[str, ...]] = {
    "pvout_with_temperature": ("resource_rsds", "resource_tas"),
    "weibull_with_air_density": ("resource_wind",),
}


def required_channels(cf_model: str) -> tuple[str, ...]:
    """The resource channels a member must carry for a technology whose capacity-factor model is `cf_model`."""
    try:
        return CHANNELS_BY_CF_MODEL[cf_model]
    except KeyError:
        raise MemberResolutionError(
            f"no channel requirement is declared for cf_model {cf_model!r}"
        ) from None


REFERENCE_MEMBER_ID = "m0"


class MemberResolutionError(ValueError):
    """A member cannot be resolved against the configuration or the CMIP6 registry (A-09: fail loud)."""


@dataclass(frozen=True)
class Gcm:
    name: str
    cds_name: str
    hazard_channel: bool
    tcr_ar6_k: float | None = None
    tcr_exception: bool = False
    note: str | None = None
    wind_channel: bool = (
        True  # False: the wind ratio of this GCM is not used (M-F4-02 item 6); rsds and tas are
    )


@dataclass(frozen=True)
class Member:
    member_id: str
    gcm: Gcm | None  # None for the reference member
    ssp: str | None
    window: tuple[int, int] | None

    @property
    def experiment(self) -> str | None:
        return SSP_EXPERIMENT[self.ssp] if self.ssp else None


@dataclass(frozen=True)
class Ensemble:
    gcms: tuple[Gcm, ...]
    ssps: tuple[str, ...]
    windows: tuple[tuple[int, int], ...]
    wind_ratio_neighbourhood_cells: int | None = None  # OQ-042, option A
    wind_factor_valid_range: tuple[float, float] | None = None  # OQ-042, option C
    hazard_windows_available: tuple[
        tuple[int, int], ...
    ] = ()  # windows with ISIMIP3b daily data on disk
    dt_isolated_native_cell_threshold_k: float | None = (
        None  # V-82: flag threshold for isolated native dT cells
    )


def _parse_window(text: str) -> tuple[int, int]:
    start, end = text.split("-")
    return int(start), int(end)


def load_ensemble(experiments_yaml: Path) -> Ensemble:
    """Read `gcm_ensemble` from experiments.yaml; fail loud if it is absent or names an unknown SSP."""
    cfg = yaml.safe_load(Path(experiments_yaml).read_text(encoding="utf-8")).get("gcm_ensemble")
    if not cfg:
        raise MemberResolutionError(
            f"{experiments_yaml}: no `gcm_ensemble` block (OQ-009 verdict missing)"
        )
    unknown = [s for s in cfg["ssps"] if s not in SSP_EXPERIMENT]
    if unknown:
        raise MemberResolutionError(f"unknown SSP(s) {unknown}; known: {sorted(SSP_EXPERIMENT)}")
    gcms = tuple(
        Gcm(
            name=g["name"],
            cds_name=g["cds_name"],
            hazard_channel=bool(g["hazard_channel"]),
            tcr_ar6_k=g.get("tcr_ar6_k"),
            tcr_exception=bool(g.get("tcr_exception", False)),
            note=g.get("note"),
            wind_channel=bool(g.get("wind_channel", True)),
        )
        for g in cfg["gcms"]
    )
    return Ensemble(
        gcms=gcms,
        ssps=tuple(cfg["ssps"]),
        windows=tuple(_parse_window(w) for w in cfg["windows"]),
        wind_ratio_neighbourhood_cells=cfg.get("wind_ratio_neighbourhood_cells"),
        wind_factor_valid_range=tuple(cfg["wind_factor_valid_range"])
        if cfg.get("wind_factor_valid_range")
        else None,
        hazard_windows_available=tuple(
            _parse_window(w) for w in cfg.get("hazard_windows_available", [])
        ),
        dt_isolated_native_cell_threshold_k=cfg.get("dt_isolated_native_cell_threshold_k"),
    )


def member_id(cds_name: str, ssp: str, window: tuple[int, int]) -> str:
    return f"m_{cds_name}_{SSP_EXPERIMENT[ssp]}_{window[0]}_{window[1]}"


def resolve_members(ensemble: Ensemble) -> list[Member]:
    """The reference member first, then the full factorial gcm x ssp x window."""
    members = [Member(REFERENCE_MEMBER_ID, None, None, None)]
    for gcm in ensemble.gcms:
        for ssp in ensemble.ssps:
            for window in ensemble.windows:
                members.append(Member(member_id(gcm.cds_name, ssp, window), gcm, ssp, window))
    ids = [m.member_id for m in members]
    if len(set(ids)) != len(ids):
        raise MemberResolutionError("duplicate member ids in the resolved ensemble")
    return members


def _entry(registry: Cmip6Registry, gcm: Gcm, experiment: str, variable: str):
    entry = registry.entries.get(f"cmip6/{gcm.cds_name}/{experiment}/{variable}")
    if entry is None or entry.status != "registered":
        raise MemberResolutionError(
            f"{gcm.name}: {experiment}/{variable} is not registered in the CMIP6 registry"
        )
    return entry


def has_hazard_channel(member: Member, hazard_windows: tuple[tuple[int, int], ...]) -> bool:
    """True if the member has hazard data: an ISIMIP3b model whose daily data cover the member's window (D-F4-004)."""
    return member.gcm is not None and member.gcm.hazard_channel and member.window in hazard_windows


def member_channels(member: Member, hazard_windows: tuple[tuple[int, int], ...]) -> dict[str, bool]:
    """The channels a member declares: `resource_rsds`, `resource_tas`, `resource_wind` and `hazard` (M-F4-06)."""
    if member.gcm is None:
        return {"resource_rsds": True, "resource_tas": True, "resource_wind": True, "hazard": False}
    return {
        "resource_rsds": True,
        "resource_tas": True,
        "resource_wind": member.gcm.wind_channel,
        "hazard": has_hazard_channel(member, hazard_windows),
    }


def members_manifest(
    members: list[Member], registry: Cmip6Registry, hazard_windows: tuple[tuple[int, int], ...] = ()
) -> dict:
    """The content of `members.yaml`: each member, its channels and the files its factors come from.

    Raises MemberResolutionError if a needed file is not registered, or if a GCM's historical and scenario files
    are different realizations (a change factor would then mix two ensemble members).
    """
    out: list[dict] = []
    for m in members:
        if m.gcm is None:
            out.append(
                {
                    "member": m.member_id,
                    "description": "reference climatology, no change (delta_rsds = delta_wind = 1, dT = 0)",
                    "window": f"{REFERENCE_PERIOD[0]}-{REFERENCE_PERIOD[1]}",
                    "channels": member_channels(m, hazard_windows),
                }
            )
            continue
        sources: dict[str, dict] = {}
        realizations: set[str] = set()
        for variable in VARIABLES:
            if variable == "sfcWind" and not m.gcm.wind_channel:
                continue  # declared by `channels.resource_wind: false`; the file is not read
            for experiment in ("historical", m.experiment):
                e = _entry(registry, m.gcm, experiment, variable)
                realizations.add(e.realization)
                sources[f"{experiment}/{variable}"] = {
                    "path": e.global_path,
                    "sha256": e.source_sha256,
                }
        if len(realizations) != 1:
            raise MemberResolutionError(
                f"{m.gcm.name}/{m.ssp}: realizations differ across files: {sorted(realizations)}"
            )
        grid = _entry(registry, m.gcm, "historical", "tas").native_grid
        entry: dict = {
            "member": m.member_id,
            "gcm": m.gcm.name,
            "ssp": m.ssp,
            "window": f"{m.window[0]}-{m.window[1]}",
            "channels": member_channels(m, hazard_windows),
            "realization": next(iter(realizations)),
            "native_grid": grid.model_dump() if grid else None,
            "tcr_ar6_k": m.gcm.tcr_ar6_k,
            "sources": sources,
        }
        if m.gcm.tcr_exception:
            entry["tcr_exception"] = True
        if not m.gcm.wind_channel:
            entry["wind_channel_exception"] = True
        out.append(entry)
    return {
        "reference_period": f"{REFERENCE_PERIOD[0]}-{REFERENCE_PERIOD[1]}",
        "n_members": len(out),
        "members": out,
    }
