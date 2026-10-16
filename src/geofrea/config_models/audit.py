"""Configuration and input models of the data quality audit (F1b) that other packages read: `AuditConfig` (the sanity ranges of `config/audit.yaml`, read by `core`, F2b and F5) and `AuditInputs` (the resolved paths F1 hands to the audit).

They live here and not in `data_quality_audit` so that `core` and F1 do not import a later phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import geopandas as gpd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditLayerConfig(BaseModel):
    """One layer's diagnostic-gate expectations from config/audit.yaml (M-F1b-01).

    `expected_resolution_deg` and `source` are both null together, never
    one without the other — a value with no primary source is not
    configuration, it's a guess (see CLAUDE.md, "A methodological value
    without a documented primary source is never assumed"). A null pair
    means the layer is reported `not_audited` for the resolution check
    rather than silently skipped or defaulted.
    """

    model_config = ConfigDict(extra="forbid")

    expected_resolution_deg: float | None = None
    source: str | None = None
    unit: str | None = None
    sanity_range: tuple[float, float] | None = None


class DerivedRangeConfig(BaseModel):
    """How the sanity range of an F2b layer is derived (V-04, siting_layers/sanity.py), or that it has no derivation yet.

    `derivation` and `source` are both null together (the layer has no range: an OQ names what is missing), or both set (the
    range follows from the named derivation of the named standard or geometry; no number is stored here).

    `tolerance_rel` (with its `tolerance_justification`) widens an `iso2533_envelope` range by a relative margin on each side. It is a
    quality-control engineering tolerance, not a scientific parameter: it exists so that the check catches gross errors (a wrong unit,
    a swapped layer, a corrupt tile) and does not predict the density.
    """

    model_config = ConfigDict(extra="forbid")

    derivation: Literal["iso2533_envelope", "country_bbox_diagonal"] | None = None
    source: str | None = None
    open_question: str | None = None
    tolerance_rel: float | None = Field(default=None, gt=0.0, lt=1.0)
    tolerance_justification: str | None = None
    # A validity limit with no derivation (OQ-053 closed): the layer is valid on (low, high], that is, `low` is excluded and `high` is
    # included (a physical bound: a Weibull scale and shape are positive). A value outside is an error. It is a Tier 3 value with a source line.
    validity_range: tuple[float, float] | None = None
    validity_tier: int | None = None
    validity_source: str | None = None

    @model_validator(mode="after")
    def _derivation_with_source_or_an_open_question(self) -> DerivedRangeConfig:
        if (self.derivation is None) != (self.source is None):
            raise ValueError("derivation and source are both set or both null")
        if self.derivation is None and self.open_question is None and self.validity_range is None:
            raise ValueError(
                "a layer with no derivation names the open question that will give its range, or declares a validity range"
            )
        if (self.tolerance_rel is None) != (self.tolerance_justification is None):
            raise ValueError("tolerance_rel and tolerance_justification are both set or both null")
        if self.validity_range is not None:
            if self.validity_range[0] >= self.validity_range[1]:
                raise ValueError("validity_range is (low, high] with low below high")
            if self.validity_tier is None or self.validity_source is None:
                raise ValueError("a validity range declares its tier and its source")
            if self.derivation is not None:
                raise ValueError("a layer with a derivation does not also declare a validity range")
        if self.tolerance_rel is not None and self.derivation != "iso2533_envelope":
            raise ValueError(
                "a relative tolerance is declared only on the iso2533_envelope derivation"
            )
        return self


class AuditConfig(BaseModel):
    """Root schema for config/audit.yaml.

    `layers` is keyed by the same layer names AuditResult.rasters uses
    for simple layers (land_cover, solar, elevation) plus entries with
    no corresponding AuditInputs field yet — `wind` holds a nested dict
    of GWA product name -> AuditLayerConfig (all four products fetched,
    M-F1-03). `cmip6` holds a nested dict of model name ->
    AuditLayerConfig (task F-3, COMMAND F3-2: resource channel only, one
    entry per model since each keeps its own native grid, F3-1 action
    5) — the hazard channel is a separate acquisition (OQ-036).
    `era5_gust`/`gem_existing_plants` are flat AuditLayerConfig
    entries with no file to inspect yet at all, reported `not_audited`
    unconditionally. No `slope` key: slope is not an F1b layer at all
    (derived later, in grid_alignment) — see docs/phases/
    F1b_data_quality_audit.md D-F1b-003.

    Args:
        country_overrides: Per-country replacement of `layers`' flat
            (non-wind-nested) entries, keyed by ISO3/synthetic code then
            by raster key (the same keys `expected_resolutions` in
            `run_audit_phase()` uses: `land_cover`, `elevation`,
            `population`, `solar`, `wind`, `weibull_a`, `weibull_k`,
            `air_density`). `layers` above describes real, cross-country
            source products (WorldPop is always ~1/1200 deg regardless of
            country); a synthetic country's fixture rasters are generated
            at whatever resolution its own generator script chose (A-06/
            D-core-017/D-core-018) and need their own expectation so F1b
            audits them properly instead of reporting every one of them
            `not_audited`. Empty for every real country — only ZZZ uses
            this today.
    """

    model_config = ConfigDict(extra="forbid")

    resolution_tolerance: float
    layers: dict[str, AuditLayerConfig | dict[str, AuditLayerConfig]]
    country_overrides: dict[str, dict[str, AuditLayerConfig]] = {}
    derived_ranges: dict[str, DerivedRangeConfig] = {}


class AuditInputs(BaseModel):
    """Raw, already-resolved geodata paths/objects the audit phase inspects.

    Mirrors DataAuditor.run()'s parameter list exactly (see
    docs/architecture/data_quality_audit.md sec a). GeoFREA has no data
    acquisition layer yet (legacy's DataFetcher/DataManager/DataOrchestrator
    are not ported — out of scope for this stage), so main.py currently
    has no way to populate these with real values; every field left at
    its default produces the same "file not found" reporting the legacy
    auditor already does for missing inputs. This is not fabricated
    behavior — it is the existing defensive path, just with nothing to
    find yet.

    Args:
        solar_path: PVOUT raster path.
        elevation_path: DEM raster path.
        slope_path: Slope raster path, if one exists yet. Usually None:
            GeoFREA derives slope only later, inside grid_alignment
            (raster_alignment.derive_slope_from_dem(), 2026-09-11), so at
            audit time there is normally nothing to inspect and the
            slope checks are skipped.
        population_path: Population raster path.
        wind_paths: Wind speed/power-density raster paths (only the
            first, if any, is inspected — matches legacy's wind_files[0]).
        weibull_a_path: Global Wind Atlas combined-Weibull-A raster path
            at 100m (M-F1-03, task F1-2) — the representative height;
            config/audit.yaml's `wind.combined-Weibull-A` entry is not
            height-specific, matching the same "one file inspected"
            precedent as wind_paths above.
        weibull_k_path: Global Wind Atlas combined-Weibull-k raster path
            at 100m — same rationale as weibull_a_path.
        air_density_path: Global Wind Atlas air-density raster path at
            100m — same rationale as weibull_a_path.
        cmip6_gfdl_esm4_path: CMIP6 GFDL-ESM4 resource-channel raster
            path (M-F1-04, task F-3) — the country crop of the
            historical/tas combination, representative of this model's
            native grid; config/audit.yaml's `cmip6.gfdl_esm4` entry is
            not per-variable, same "one file inspected" precedent as
            wind_paths/weibull_a_path above.
        cmip6_miroc6_path: CMIP6 MIROC6 resource-channel raster path —
            same rationale as cmip6_gfdl_esm4_path. A separate field
            (not folded into one cmip6_path) because the two models keep
            distinct native grids (F3-1 action 5) with independent
            resolution expectations in config/audit.yaml.
        era5_gust_path: ERA5 gust resource path (M-F1-05, task F4-2) —
            the polygon-cropped daily-maximum source field (not the
            annual-maxima reduction, which has no CRS-bearing native
            grid of its own to audit beyond the source's), read from
            `era5_registry.json` the same way cmip6_gfdl_esm4_path/
            cmip6_miroc6_path are read from `cmip6_registry.json`.
        land_cover_tiles: ESA WorldCover tile paths.
        lakes_path: HydroLAKES vector path (global — clipped to
            country_gdf during inspection, see vector_inspection.py).
        rivers_path: HydroRIVERS vector path (global — clipped, same
            as lakes_path).
        protected_path: WDPA protected-areas vector path (global —
            clipped, same as lakes_path). Added 2026-08-24 — see
            DECISIONS.md same date, "vector layer audit depth". Note
            this is a NEW AuditInputs field with no AuditResult
            consumer beyond `vectors["protected"]`'s own inspection —
            it does not feed a suitability/exclusion calculation here
            (see DECISIONS.md 2026-08-24 "protected (WDPA): decisão de
            onde entra no GeoFREA fica pendente").
        borders_path: Raw country-boundary vector path (all polygons —
            mainland, islands, enclaves), inspected as-is, NOT clipped
            (already scoped to one country at the source). Distinct
            from `country_gdf` below, which is the mainland-only
            polygon DERIVED from this same file and used purely as a
            clip mask for every other layer.
        admin1_path: Admin level-1 boundaries vector path (same GADM
            download as borders_path in legacy — not clipped).
        grid_path: Power-grid (transmission lines) vector path, from
            OSM Overpass — country-scoped at the source, not clipped.
        roads_path: Road network vector path. Since 2026-09-08 (see
            DECISIONS.md same date, "wire das 5 camadas restantes a
            partir do banco local, Fase 2 - roads") this is a GRIP4
            regional shapefile spanning many countries, clipped by
            data_quality_audit at inspection time (clip=True) — no
            longer the country-scoped, unclipped OSM Overpass file the
            original skeleton assumed.
        country_gdf: Country polygon (mainland-filtered) used to mask
            every raster to the real country boundary, not a bounding box.
        skip_land_cover: If True, skip ESA tile analysis (the slowest step).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    solar_path: Path | None = None
    elevation_path: Path | None = None
    slope_path: Path | None = None
    population_path: Path | None = None
    wind_paths: list[Path] = []
    weibull_a_path: Path | None = None
    weibull_k_path: Path | None = None
    air_density_path: Path | None = None
    cmip6_gfdl_esm4_path: Path | None = None
    cmip6_miroc6_path: Path | None = None
    era5_gust_path: Path | None = None
    land_cover_tiles: list[Path] = []
    lakes_path: Path | None = None
    rivers_path: Path | None = None
    protected_path: Path | None = None
    borders_path: Path | None = None
    admin1_path: Path | None = None
    grid_path: Path | None = None
    roads_path: Path | None = None
    country_gdf: gpd.GeoDataFrame | None = None
    skip_land_cover: bool = False
