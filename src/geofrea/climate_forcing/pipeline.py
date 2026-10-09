"""F4 climate_forcing end to end for one country: forcing, members.yaml, hazard context, maps (J-3, J-4, J-5).

Library functions used by the orchestrator phases in main.py and by the thin scripts in `scripts/`. Everything
reads the global CMIP6 files (registry), the ISIMIP3b crops, the ERA5 annual maxima and the F2a aligned grid of the
country, and writes under `outputs/<ISO3>/climate_forcing/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.forcing import country_cells, forcing_frames, write_forcing
from geofrea.climate_forcing.hazards import (
    HazardDataError,
    era5_gust_mean_annual_max,
    hazard_fields,
    hazard_frame,
)
from geofrea.climate_forcing.maps import plot_all_members
from geofrea.climate_forcing.members import (
    has_hazard_channel,
    load_ensemble,
    members_manifest,
    resolve_members,
)
from geofrea.climate_forcing.table_schemas import (
    CLIMATE_TABLE_SCHEMA_VERSION,
    ForcingMaskedRow,
    HazardContextRow,
)
from geofrea.core import paths as core_paths
from geofrea.core.tables import write_table
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry

ISIMIP_MAX_DISTANCE_DEG = 0.4  # half the 0.5 degree diagonal (0.354) plus a margin


class ForcingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    n_cells: int
    n_members: int
    n_rows: int
    n_masked_cell_members: int
    forcing: Path
    forcing_masked: Path
    members: Path
    wind_ratio_neighbourhood_cells: int | None
    wind_factor_valid_range: tuple[float, float] | None


class HazardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    n_cells: int
    n_hazard_members: int
    n_rows: int
    hazard_context: Path


class MapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    n_figures: int
    figures: list[Path]


def aligned_mask_path(iso: str) -> Path:
    """The F2a raster whose valid pixels are the in-country pixels (grid_alignment must have run)."""
    return core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_grid_aligned.tif"


def artifacts_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ratio_qc(forcing_path: Path) -> dict:
    df = pd.read_parquet(forcing_path, columns=["member", "delta_rsds", "delta_wind"])
    df["member"] = df["member"].astype(str)
    df = df[df["member"] != "m0"]
    df["gcm"] = df["member"].str.extract(r"^m_(.+)_ssp")[0]
    return {
        gcm: {
            col: {"min": float(g[col].min()), "max": float(g[col].max())}
            for col in ("delta_rsds", "delta_wind")
        }
        for gcm, g in df.groupby("gcm")
    }


def build_forcing(
    iso: str, experiments_yaml: Path, registry_path: Path | None = None
) -> ForcingSummary:
    """J-3: forcing.parquet, forcing_masked.parquet and members.yaml for `iso`."""
    registry = Cmip6Registry.load(
        registry_path or core_paths.fetched_raw("cmip6", "_global") / "cmip6_registry.json"
    )
    ensemble = load_ensemble(experiments_yaml)
    members = resolve_members(ensemble)
    manifest = members_manifest(
        members, registry, ensemble.hazard_windows_available
    )  # fails loud first

    cells = country_cells(aligned_mask_path(iso))
    out_dir = artifacts_dir(iso)
    masked: list[pd.DataFrame] = []
    n_rows = write_forcing(
        forcing_frames(
            cells,
            members,
            registry,
            ensemble.wind_ratio_neighbourhood_cells,
            ensemble.wind_factor_valid_range,
            masked,
        ),
        out_dir / "forcing.parquet",
    )
    masked_df = (
        pd.concat(masked, ignore_index=True)
        if masked
        else pd.DataFrame(
            {
                "cell_id": pd.Series(dtype="int64"),
                "member": pd.Series(dtype="object"),
                "delta_wind": pd.Series(dtype="float32"),
            }
        )
    )
    masked_df["reason"] = "delta_wind outside wind_factor_valid_range (OQ-042 option C)"
    masked_df["member"] = masked_df["member"].astype(str)
    masked_df["delta_wind"] = masked_df["delta_wind"].astype("float32")
    write_table(
        masked_df,
        out_dir / "forcing_masked.parquet",
        schema_version=CLIMATE_TABLE_SCHEMA_VERSION,
        row_model=ForcingMaskedRow,
    )

    manifest.update(
        {
            "country": iso,
            "n_cells": len(cells),
            "n_rows": n_rows,
            "wind_ratio_neighbourhood_cells": ensemble.wind_ratio_neighbourhood_cells,
            "wind_factor_valid_range": list(ensemble.wind_factor_valid_range)
            if ensemble.wind_factor_valid_range
            else None,
            "masked_cell_members": {
                k: int(v) for k, v in masked_df.groupby("member").size().items()
            },
            "qc_factor_ranges_after_masking": _ratio_qc(out_dir / "forcing.parquet"),
        }
    )
    members_path = out_dir / "members.yaml"
    members_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return ForcingSummary(
        country_code=iso,
        n_cells=len(cells),
        n_members=len(members),
        n_rows=n_rows,
        n_masked_cell_members=len(masked_df),
        forcing=out_dir / "forcing.parquet",
        forcing_masked=out_dir / "forcing_masked.parquet",
        members=members_path,
        wind_ratio_neighbourhood_cells=ensemble.wind_ratio_neighbourhood_cells,
        wind_factor_valid_range=ensemble.wind_factor_valid_range,
    )


def _isimip(iso: str, gcm: str, experiment: str, variable: str) -> Path:
    path = (
        core_paths.fetched_raw("isimip3b", iso)
        / f"{gcm.replace('_', '-')}_{experiment}_{variable}_{iso}.nc"
    )
    if not path.exists():
        raise HazardDataError(f"missing ISIMIP3b file {path}")
    return path


def build_hazard_context(iso: str, experiments_yaml: Path) -> HazardSummary:
    """J-4: hazard_context.parquet for the members that carry the hazard channel."""
    ensemble = load_ensemble(experiments_yaml)
    members = [
        m
        for m in resolve_members(ensemble)
        if has_hazard_channel(m, ensemble.hazard_windows_available)
    ]
    if not members:
        raise HazardDataError(
            "no member carries the hazard channel (check hazard_windows_available)"
        )
    cells = country_cells(aligned_mask_path(iso))
    gust = era5_gust_mean_annual_max(
        core_paths.fetched_raw("era5", iso) / f"{iso}_fg10_annual_max.nc",
        cells["lat_c"].to_numpy(),
        cells["lon_c"].to_numpy(),
    )
    frames: list[pd.DataFrame] = []
    for m in members:
        fields = hazard_fields(
            _isimip(iso, m.gcm.cds_name, "historical", "tasmax"),
            _isimip(iso, m.gcm.cds_name, m.experiment, "tasmax"),
            _isimip(iso, m.gcm.cds_name, "historical", "pr"),
            _isimip(iso, m.gcm.cds_name, m.experiment, "pr"),
            m.window,
        )
        frames.append(hazard_frame(cells, m.member_id, fields, gust, ISIMIP_MAX_DISTANCE_DEG))
    out = pd.concat(frames, ignore_index=True)
    out["member"] = out["member"].astype("category")
    path = artifacts_dir(iso) / "hazard_context.parquet"
    write_table(
        out,
        path,
        schema_version=CLIMATE_TABLE_SCHEMA_VERSION,
        row_model=HazardContextRow,
        compression="zstd",
    )
    return HazardSummary(
        country_code=iso,
        n_cells=len(cells),
        n_hazard_members=len(members),
        n_rows=len(out),
        hazard_context=path,
    )


def build_maps(iso: str, figures_mode: str) -> MapsSummary:
    """J-5: one PNG per member under `figures/`, from forcing.parquet and forcing_masked.parquet.

    Args:
        iso: Country code.
        figures_mode: `settings.yaml` `figures` (A-08). Member-level maps are drawn only with `all`; `summary` and `none`
            draw none (F4 has no summary-level map).
    """
    if figures_mode not in ("all", "summary", "none"):
        raise ValueError(f"figures must be all, summary or none, got {figures_mode!r}")
    if figures_mode != "all":
        return MapsSummary(country_code=iso, n_figures=0, figures=[])
    art = artifacts_dir(iso)
    forcing = pd.read_parquet(art / "forcing.parquet")
    masked = pd.read_parquet(art / "forcing_masked.parquet")
    notes = {
        m: "OQ-042: grey cells have no valid wind factor for this member (masked, not zero change)"
        for m in masked["member"].astype(str).unique()
    }
    figures = plot_all_members(
        forcing, masked, core_paths.phase_dir(iso, "climate_forcing", "figures"), iso, notes
    )
    return MapsSummary(country_code=iso, n_figures=len(figures), figures=figures)
