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

from geofrea.data_acquisition.cmip6_registry import Cmip6Registry

SSP_EXPERIMENT = {"SSP1-2.6": "ssp126", "SSP3-7.0": "ssp370", "SSP5-8.5": "ssp585"}
VARIABLES = ("rsds", "sfcWind", "tas")
REFERENCE_MEMBER_ID = "m0"
REFERENCE_WINDOW = (1995, 2014)


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


def _parse_window(text: str) -> tuple[int, int]:
    start, end = text.split("-")
    return int(start), int(end)


def load_ensemble(experiments_yaml: Path) -> Ensemble:
    """Read `gcm_ensemble` from experiments.yaml; fail loud if it is absent or names an unknown SSP."""
    cfg = yaml.safe_load(Path(experiments_yaml).read_text(encoding="utf-8")).get("gcm_ensemble")
    if not cfg:
        raise MemberResolutionError(f"{experiments_yaml}: no `gcm_ensemble` block (OQ-009 verdict missing)")
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
        )
        for g in cfg["gcms"]
    )
    return Ensemble(
        gcms=gcms,
        ssps=tuple(cfg["ssps"]),
        windows=tuple(_parse_window(w) for w in cfg["windows"]),
        wind_ratio_neighbourhood_cells=cfg.get("wind_ratio_neighbourhood_cells"),
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
        raise MemberResolutionError(f"{gcm.name}: {experiment}/{variable} is not registered in the CMIP6 registry")
    return entry


def members_manifest(members: list[Member], registry: Cmip6Registry) -> dict:
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
                    "window": "1995-2014",
                    "channels": {"resource": True, "hazard": True},
                }
            )
            continue
        sources: dict[str, dict] = {}
        realizations: set[str] = set()
        for variable in VARIABLES:
            for experiment in ("historical", m.experiment):
                e = _entry(registry, m.gcm, experiment, variable)
                realizations.add(e.realization)
                sources[f"{experiment}/{variable}"] = {"path": e.global_path, "sha256": e.source_sha256}
        if len(realizations) != 1:
            raise MemberResolutionError(f"{m.gcm.name}/{m.ssp}: realizations differ across files: {sorted(realizations)}")
        grid = _entry(registry, m.gcm, "historical", "tas").native_grid
        entry: dict = {
            "member": m.member_id,
            "gcm": m.gcm.name,
            "ssp": m.ssp,
            "window": f"{m.window[0]}-{m.window[1]}",
            "channels": {"resource": True, "hazard": m.gcm.hazard_channel},
            "realization": next(iter(realizations)),
            "native_grid": grid.model_dump() if grid else None,
            "tcr_ar6_k": m.gcm.tcr_ar6_k,
            "sources": sources,
        }
        if m.gcm.tcr_exception:
            entry["tcr_exception"] = True
        out.append(entry)
    return {"reference_period": "1995-2014", "n_members": len(out), "members": out}
