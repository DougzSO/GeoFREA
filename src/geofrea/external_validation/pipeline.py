"""F7b external_validation end to end for one country: existing plants against the exclusion set, the LCOE deciles and published estimates (M-F7b-01 to M-F7b-04).

Reads the plant inventory (validation-only, V-06), the aligned layers through F3's `prepare_shared_layers`, F3's candidate tables (central
scenario), F6's nominal LCOE at `m0` and F5's potential, and writes under `outputs/<ISO3>/external_validation/artifacts/`:

  - `exclusion_shares.parquet`: per technology, set of units and constraint, the capacity-weighted excluded share at the plant pixels (M-F7b-01);
  - `enrichment.parquet`: per technology and set of units, the capacity and area by decile of the nominal LCOE and the enrichment ratio (M-F7b-02);
  - `published_comparison.parquet`: the entries of `config/published_potential.yaml` beside F5's potential at `m0` (M-F7b-03), empty while there are none;
  - `validation_units.parquet`: every operating unit, where it falls and what the engine says about its pixel.

Nothing here feeds a parameter, a threshold or another phase (V-06); the results are plausibility evidence, not accuracy (M-F7b-04).
See docs/phases/F7b_external_validation.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_experiments
from geofrea.core.config_schemas import TechnologiesFile
from geofrea.core.scale import active_scale
from geofrea.core.tables import write_table
from geofrea.external_validation.enrichment import enrichment_rows, weighted_deciles
from geofrea.external_validation.exclusion import exclusion_rows
from geofrea.external_validation.inventory import (
    inventory_path,
    load_inventory,
    pixel_of_units,
    row_sets,
)
from geofrea.external_validation.published import comparison_rows, load_published
from geofrea.external_validation.table_schemas import (
    VALIDATION_TABLE_SCHEMA_VERSION,
    EnrichmentRow,
    ExclusionRow,
    PublishedComparisonRow,
    ValidationUnitRow,
)
from geofrea.grid_alignment.schemas import GridAlignmentResult
from geofrea.land_eligibility.cells import cell_id as make_cell_id
from geofrea.land_eligibility.cells import cell_row_col
from geofrea.land_eligibility.eligibility import eligible_fraction, valid_pixels
from geofrea.land_eligibility.parameters import load_land_availability
from geofrea.land_eligibility.pipeline import prepare_shared_layers, technology_layers
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS, scenario_sets
from geofrea.siting_layers.physical_layers import SitingLayersResult

logger = logging.getLogger("geofrea.external_validation.pipeline")

PROVENANCE_KEY = "geofrea_validation_provenance"
SKIPPED_KEY = "geofrea_validation_skipped"
TABLES = ("exclusion_shares", "enrichment", "published_comparison", "validation_units")
ROW_MODELS: dict[str, type[BaseModel]] = {
    "exclusion_shares": ExclusionRow,
    "enrichment": EnrichmentRow,
    "published_comparison": PublishedComparisonRow,
    "validation_units": ValidationUnitRow,
}
INTERPRETATION = (
    "Existing plants reflect past auctions, policy and grid access; the results are plausibility evidence, not accuracy (M-F7b-04). "
    "Nothing here is a calibration (V-06)."
)
OPERATING_SET = "operating"


class ValidationInputError(RuntimeError):
    """An input table of F7b breaks its contract (A-09)."""


class ValidationMissingInputError(FileNotFoundError):
    """Inputs F7b needs are absent; the message lists every one of them before anything is read (A-09)."""

    def __init__(self, iso: str, missing: Sequence[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            f"external_validation cannot run for {iso}: {len(self.missing)} missing input(s) "
            "(F3, F5 and F6 must have run, and the plant inventory must be acquired): "
            + "; ".join(self.missing)
        )


class TechValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    n_units: int
    capacity_mw: float
    n_outside_grid: int
    n_invalid_pixel: int
    mean_combined_excluded_share: float | None
    enrichment_ratio_lowest: dict[int, float | None]
    capacity_share_non_candidate: float | None


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    synthetic_inventory: bool
    technologies: dict[str, TechValidation]
    tables: dict[str, Path]
    skipped: list[str]


def validation_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "external_validation", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _units_frame(
    set_units: pd.DataFrame, technology: str, transform, country_mask: np.ndarray
) -> pd.DataFrame:
    """The units of one technology with their pixel, whether they fall on the grid, and their cell."""
    units = set_units[set_units["tech"] == technology].copy().reset_index(drop=True)
    lat = units["lat"].to_numpy(dtype="float64")
    lon = units["lon"].to_numpy(dtype="float64")
    row, col, in_grid = pixel_of_units(lat, lon, transform, country_mask)
    units["row"], units["col"], units["in_grid"] = row, col, in_grid
    cell = pd.Series(pd.array([pd.NA] * len(units), dtype="Int64"))
    if in_grid.any():
        cell_row, cell_col = cell_row_col(lat[in_grid], lon[in_grid])
        cell[in_grid] = make_cell_id(cell_row, cell_col)
    units["cell_id"] = cell
    return units


def build_external_validation(
    iso: str,
    technologies: TechnologiesFile,
    run_technologies: Sequence[str],
    experiments_yaml: Path,
    grid_result: GridAlignmentResult,
    siting_result: SitingLayersResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    *,
    production: bool = False,
    published_path: Path | None = None,
    potential_dir: Path | None = None,
    candidates_dir: Path | None = None,
    lcoe_dir: Path | None = None,
    out_dir: Path | None = None,
) -> ValidationSummary:
    """F7b for `iso` and the technologies of the run.

    Implements: M-F7b-01 to M-F7b-04.

    Raises:
        InventoryError: the plant inventory is incomplete or synthetic in a production run.
        ValidationMissingInputError: the inventory, or an F3, F5 or F6 input, is absent; every missing item is listed.
        ValidationInputError: a candidate has no nominal LCOE row at `m0`.
    """
    unknown = sorted(set(run_technologies) - set(technologies.technologies))
    if unknown:
        raise ValidationInputError(f"technologies not in the registry: {unknown}")
    config = load_experiments(experiments_yaml).external_validation
    potential_dir = Path(
        potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    )
    candidates_dir = Path(
        candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    )
    lcoe_dir = Path(lcoe_dir or core_paths.phase_dir(iso, "lcoe_modeling", "artifacts"))
    needed = [inventory_path(iso)]
    for tech in run_technologies:
        needed.append(candidates_dir / f"candidates_{tech}__central.parquet")
        needed.append(lcoe_dir / f"lcoe_summary_{tech}.parquet")
        needed += [potential_dir / f"potential_{tech}__{s}.parquet" for s in LAND_SCENARIOS]
    absent = [str(p) for p in needed if not p.is_file()]
    if absent:
        raise ValidationMissingInputError(iso, absent)
    out_dir = Path(out_dir or validation_dir(iso))  # created only once every input is there
    inventory = load_inventory(iso, production=production)

    la = load_land_availability(experiments_yaml)
    interim = core_paths.interim(iso, "land_eligibility")
    interim.mkdir(parents=True, exist_ok=True)
    shared = prepare_shared_layers(
        la,
        list(run_technologies),
        grid_result,
        country_gdf,
        protected_path,
        lakes_path,
        rivers_path,
        interim,
    )
    sets = row_sets(
        inventory.frame, config.vintage_min_start_year, config.excluded_location_accuracy
    )

    exclusion, enrichment, unit_rows = [], [], []
    per_tech: dict[str, TechValidation] = {}
    for tech in run_technologies:
        layers, _ = technology_layers(shared, tech, siting_result)
        eligible, excl = eligible_fraction(layers, scenario_sets(la.technologies[tech])["central"])
        excluded = {**excl, "combined": (1.0 - eligible).astype("float32")}
        valid = valid_pixels(layers)
        candidates = pd.read_parquet(
            candidates_dir / f"candidates_{tech}__central.parquet",
            columns=["cell_id", "eligible_area_km2"],
        )
        lcoe = pd.read_parquet(
            lcoe_dir / f"lcoe_summary_{tech}.parquet", columns=["cell_id", "member", "lcoe_nominal"]
        )
        lcoe = lcoe[lcoe["member"].astype(str) == REFERENCE_MEMBER_ID]
        candidates = candidates.merge(
            lcoe[["cell_id", "lcoe_nominal"]], on="cell_id", how="left", validate="one_to_one"
        )
        if candidates["lcoe_nominal"].isna().any():
            raise ValidationInputError(
                f"{tech}: {int(candidates['lcoe_nominal'].isna().sum())} candidates have no nominal LCOE at {REFERENCE_MEMBER_ID}"
            )
        ranked = candidates[np.isfinite(candidates["lcoe_nominal"])].reset_index(drop=True)
        ranked["decile"] = weighted_deciles(
            ranked["lcoe_nominal"].to_numpy(),
            ranked["eligible_area_km2"].to_numpy(),
            ranked["cell_id"].to_numpy(),
        )
        for name, frame in sets.items():
            units = _units_frame(frame, tech, shared.transform, shared.country_mask)
            if units.empty:
                logger.warning("%s %s [%s]: no operating units in the inventory", iso, tech, name)
            exclusion += exclusion_rows(tech, name, units, excluded, valid)
            enrichment += enrichment_rows(
                tech, name, ranked, units, config.enrichment_lowest_deciles
            )
            if name == OPERATING_SET:
                unit_rows.append(
                    _unit_table(tech, units, excluded, valid, ranked, candidates["cell_id"])
                )
                per_tech[tech] = _tech_summary(tech, exclusion, enrichment, units, config)

    potentials = {
        tech: {
            s: pd.read_parquet(potential_dir / f"potential_{tech}__{s}.parquet")
            for s in LAND_SCENARIOS
        }
        for tech in run_technologies
    }
    published = comparison_rows(
        load_published(published_path), iso, potentials, REFERENCE_MEMBER_ID
    )
    skips = {}
    if not published:
        skips["published_comparison"] = {
            "output": "comparison with published estimates (M-F7b-03)",
            "reason": "config/published_potential.yaml has no entry for this country and these technologies",
            "open_question": "OQ-057",
        }

    provenance = json.dumps(
        {
            "country": iso,
            "scale": active_scale().scale_id,
            "inventory": inventory.path.name,
            "inventory_sha256": _sha256(inventory.path),
            "synthetic_inventory": inventory.synthetic,
            "row_sets": sorted(sets),
            "vintage_min_start_year": config.vintage_min_start_year,
            "vintage_reason": config.vintage_reason,
            "excluded_location_accuracy": config.excluded_location_accuracy,
            "enrichment_lowest_deciles": config.enrichment_lowest_deciles,
            "reference_member": REFERENCE_MEMBER_ID,
            "interpretation": INTERPRETATION,
            "production": production,
        },
        sort_keys=True,
    )
    frames = {
        "exclusion_shares": pd.DataFrame(exclusion),
        "enrichment": pd.DataFrame(enrichment),
        "published_comparison": pd.DataFrame(published),
        "validation_units": pd.concat(unit_rows, ignore_index=True)
        if unit_rows
        else pd.DataFrame(),
    }
    tables: dict[str, Path] = {}
    for kind in TABLES:
        frame = frames[kind]
        meta = {PROVENANCE_KEY: provenance}
        if kind in skips:
            frame = pd.DataFrame(
                {name: pd.Series(dtype="object") for name in ROW_MODELS[kind].model_fields}
            )
            meta[SKIPPED_KEY] = json.dumps(skips[kind])
            logger.warning("%s: skipped %s (%s)", iso, skips[kind]["output"], skips[kind]["reason"])
        tables[kind] = write_table(
            frame,
            out_dir / f"{kind}.parquet",
            schema_version=VALIDATION_TABLE_SCHEMA_VERSION,
            row_model=ROW_MODELS[kind],
            compression="zstd",
            extra_metadata=meta,
        )
    return ValidationSummary(
        country_code=iso,
        synthetic_inventory=inventory.synthetic,
        technologies=per_tech,
        tables=tables,
        skipped=[s["output"] for s in skips.values()],
    )


def _unit_table(
    tech: str,
    units: pd.DataFrame,
    excluded: dict[str, np.ndarray],
    valid: np.ndarray,
    ranked: pd.DataFrame,
    candidate_ids: pd.Series,
) -> pd.DataFrame:
    """One row per operating unit of a technology; `decile` is null in a cell that is not a ranked candidate."""
    n = len(units)
    in_grid = units["in_grid"].to_numpy(dtype=bool)
    row, col = units["row"].to_numpy(), units["col"].to_numpy()
    valid_pixel = np.zeros(n, dtype=bool)
    valid_pixel[in_grid] = valid[row[in_grid], col[in_grid]]
    out = pd.DataFrame(
        {
            "technology": tech,
            "gem_unit_id": units["gem_unit_id"],
            "capacity_mw": units["capacity_mw"].astype("float64"),
            "start_year": units["start_year"].astype("float64"),
            "location_accuracy": units["location_accuracy"],
            "lat": units["lat"].astype("float64"),
            "lon": units["lon"].astype("float64"),
            "in_grid": in_grid,
            "valid_pixel": valid_pixel,
            "cell_id": units["cell_id"],
        }
    )
    evaluated = in_grid & valid_pixel
    for key in ("E1", "E2", "E3", "E4", "E5", "E6", "combined"):
        values = np.full(n, np.nan)
        values[evaluated] = excluded[key][row[evaluated], col[evaluated]]
        out[f"excluded_{key}"] = values
    decile_of = ranked.set_index("cell_id")["decile"]
    out["decile"] = units["cell_id"].map(decile_of)
    out["candidate"] = units["cell_id"].isin(candidate_ids).where(in_grid, other=pd.NA)
    return out


def _tech_summary(tech, exclusion, enrichment, units, config) -> TechValidation:
    combined = next(
        r
        for r in exclusion
        if r["technology"] == tech
        and r["row_set"] == OPERATING_SET
        and r["constraint"] == "combined"
    )
    lowest = {
        r["decile"]: r["enrichment_ratio"]
        for r in enrichment
        if r["technology"] == tech and r["row_set"] == OPERATING_SET and r["kind"] == "lowest"
    }
    first = next(
        r
        for r in enrichment
        if r["technology"] == tech and r["row_set"] == OPERATING_SET and r["kind"] == "decile"
    )
    return TechValidation(
        technology=tech,
        n_units=combined["n_units"],
        capacity_mw=combined["capacity_mw"],
        n_outside_grid=combined["n_outside_grid"],
        n_invalid_pixel=combined["n_invalid_pixel"],
        mean_combined_excluded_share=combined["mean_excluded_share"],
        enrichment_ratio_lowest=lowest,
        capacity_share_non_candidate=first["capacity_share_non_candidate"],
    )
