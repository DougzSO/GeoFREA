# CONVENTIONS.md: GeoFREA

Coding conventions for this repository. Scientific method and architecture requirements live in `docs/METHODOLOGY.md`; this file covers how code is written.

## Language

US English for code, identifiers, comments, docstrings, documentation, and commit messages.

## Phase and module names

| Phase | Module | Phase record |
|---|---|---|
| F1 | `data_acquisition` | `docs/phases/F1_data_acquisition.md` |
| F1b | `data_quality_audit` | `docs/phases/F1b_data_quality_audit.md` |
| F2a | `grid_alignment` | `docs/phases/F2a_grid_alignment.md` |
| F2b | `siting_layers` | `docs/phases/F2b_siting_layers.md` |
| F3 | `land_eligibility` | `docs/phases/F3_land_eligibility.md` |
| F4 | `climate_forcing` | `docs/phases/F4_climate_forcing.md` |
| F5 | `technical_potential` | `docs/phases/F5_technical_potential.md` |
| F6 | `lcoe_modeling` | `docs/phases/F6_lcoe_modeling.md` |
| F7 | `robustness_analysis` | `docs/phases/F7_robustness_analysis.md` |
| F7b | `external_validation` | `docs/phases/F7b_external_validation.md` |
| F8 | `results_synthesis` | `docs/phases/F8_results_synthesis.md` |
| E1 | `explorer` | `docs/phases/E1_explorer.md` |
| core | `core` | `docs/phases/core.md` |

Never write an unqualified `F2` or `F7`.

## Status vocabulary

Used in `docs/PROGRESS.json` and phase records:

- `not_started`
- `in_progress`
- `built_pending_conformance`: code exists but has not been audited against the current methodology
- `conformant`: audited, all conformance rows pass
- `rework_required`: code exists and conflicts with the methodology

Country run status per phase: `not_run`, `ran_with_issues`, `ran_clean`.

## Docstrings

Google style. Cover purpose, `Args`, `Returns`, `Raises` when relevant. Geospatial functions state units and CRS for every spatial input and output; a geospatial function without units and CRS is incomplete. Functions that implement a methodology item cite it:

```python
def weibull_capacity_factor(A: np.ndarray, k: np.ndarray, curve: PowerCurve) -> np.ndarray:
    """Compute capacity factor from Weibull parameters and a power curve.

    Implements: M-F5-03.

    Args:
        A: Weibull scale at hub height, m/s, shape (n_cells,).
        k: Weibull shape at hub height, dimensionless, shape (n_cells,).
        curve: Reference power curve with rated power in kW.

    Returns:
        Capacity factor in [0, 1], shape (n_cells,).
    """
```

Implementation decisions are cited as `See docs/phases/F5_technical_potential.md D-F5-003.`

## Parameters

- Scientific values go to `config/parameters.json` (schema METHODOLOGY U-05); operational values go to `config/settings.yaml`; experiment design goes to `config/experiments.yaml`; technology and country mappings go to `config/technologies.yaml` and `config/countries.yaml`.
- All configuration is validated through Pydantic schemas in `src/geofrea/core/`.
- No hardcoded scientific values in processing modules. Pydantic defaults must not duplicate configuration values; required fields have no default.
- Every parameter carries `source`, `tier`, `range`, and verification metadata. `verified: false` does not block execution but must be testable.
- No ISO3 code literals in `src/` outside comments and docstrings (enforced by test, METHODOLOGY A-05).

## Artifacts and outputs

- Rasters: Cloud Optimized GeoTIFF, EPSG:4326. Tables: parquet with a Pydantic schema and `schema_version`.
- Layout and file naming follow METHODOLOGY A-08. Paths are resolved via `src/geofrea/core/paths.py`, the only module that reads data-location environment variables.
- Map file names: `<map>__<window>__<ssp>__<gcm>.png`, using `ref` for the reference climate and `na` for non-applicable fields.
- One map per file. Figures respect `settings.yaml` `figures`.
- Thesis outputs are produced only by F8 into `GEOFREA_DATA_DIR/outputs/thesis/`, named by their T-ID (`T-R4_max_regret_BRA_solar.png`).

## Error handling

- Fail-loud. Never fall back silently to a degraded path.
- Integrity failures of present files raise. Absence of optional data is recorded explicitly in artifact metadata.
- Guards replace silent defaults: if a precondition is missing (for example, clipping without a country boundary), raise a named exception.

## Large data

- Large global vector files: bounding-box prefilter at read time, spatial index (`shapely.STRtree`) for predicates, country polygon simplification before intersection (never feature simplification), threaded intersection above 10,000 features, per-country cache of clipped results.
- Rasters above the configured memory threshold are read in windows or chunks; decide before allocating.
- F6 and F7 process in batches (METHODOLOGY A-10).

## Long-running scripts

Scripts or validations expected to run longer than 30 seconds log progress with elapsed time and estimated remaining time, using flushed output.

## Code reused from reference repositories

Code copied from CRAEI (see METHODOLOGY A-11) must have a provenance header with repository, commit SHA, original path, and adaptation summary:

```python
# Adapted from CRAEI: https://github.com/<repo>
# Commit: <sha>  Original path: <path>
# Adaptation: <one-line summary>
```

No imports from CRAEI or other reference repositories. Reference repositories remain read-only; edits belong in GeoFREA only.

## Tests

- `pytest`, `ruff` clean before any commit proposal.
- Test names state the property tested (`test_regret_is_non_negative`).
- Tests that need external data (raw, legacy baseline, reference repositories) are marked and skipped when required env vars are unset; the synthetic country fixture covers CI.
