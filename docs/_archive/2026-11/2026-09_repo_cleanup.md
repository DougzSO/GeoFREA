# 2026-09 repository cleanup audit (COMMAND ADJ-3)

Executed in the main session, read-only except for this document and the two ADJ-2b record
lines (core.md D-core-018, action 7 — already present from ADJ-3's own prior pass; verified,
not re-written here since they already state the required content verbatim).

Every row below is **awaiting verdict**. Proposed actions are limited to: keep, delete,
rename, or owned by `<task>`.

---

## 1. Module inventory

`src/geofrea/<module>/` mapped to METHODOLOGY §4.2's phase table.

| Phase | Module | Line count (excl. `__init__.py`) | Status (PROGRESS.json) | Note | Proposed action |
|---|---|---|---|---|---|
| core | `core` | 3,610 (8 files: geodesy, raster_io, config_loader, http_retry, constants, paths, schemas, orchestrator) | in_progress | — | keep |
| F1 | `data_acquisition` | 2,072 (schemas, adapter, local_layers, phase, fetchers/*) | built_pending_conformance | — | keep |
| F1b | `data_quality_audit` | 1,825 (schemas, audit, vector_inspection, raster_inspection) | built_pending_conformance | — | keep |
| F2a | `grid_alignment` | 1,626 (schemas, adapter, alignment, raster_alignment, vector_alignment, reference_grid) | built_pending_conformance | — | keep |
| F2b | `siting_layers` | 0 (no `siting_layers/` directory exists) | rework_required | Module name mismatch: CONVENTIONS.md and METHODOLOGY §4.2 both name the F2b module `siting_layers`; the actual code lives in `src/geofrea/suitability_criteria/` (1,782 lines: normalization, raster_output, report, adapter, schemas, phase, cartography, criteria_functions). Already tracked as the pending Stage H rebuild in `docs/phases/F2b_siting_layers.md`, not a new finding. | owned by Stage H (F2b rebuild) |
| F3 | `land_eligibility` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F4 | `climate_forcing` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F5 | `technical_potential` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F6 | `lcoe_modeling` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F7 | `robustness_analysis` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F7b | `external_validation` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| F8 | `results_synthesis` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |
| E1 | `explorer` | 0 (only `__init__.py`) | not_started | Empty module, matches not_started status | keep (placeholder) |

**Module with no phase:** `suitability_criteria/` (1,782 lines) — the legacy 14-criteria code implementing what will become F2b `siting_layers`. Not a stray module; explicitly tracked in `docs/phases/F2b_siting_layers.md`'s conformance table as the pre-rebuild state. No action beyond what Stage H already owns.

**Phase with no module:** F2b `siting_layers` has no directory of that name yet (code lives under the legacy name `suitability_criteria`) — same finding as above, one row.

**Empty modules (only `__init__.py` or imports):** 8 — `climate_forcing`, `explorer`, `external_validation`, `land_eligibility`, `lcoe_modeling`, `results_synthesis`, `robustness_analysis`, `technical_potential`. All correspond to `not_started` phases per `docs/PROGRESS.json` — expected, not a defect.

Also present: `docs/phases/E5b.md` — a phase-shaped record for a one-off infrastructure task (GEOFREA_DATA_DIR migration), not a METHODOLOGY §4.2 phase. No corresponding `src/` module, and none expected (E5b was a data-layout migration, not a pipeline phase). Not a defect, just outside the phase table by design.

---

## 2. Dead code

Method: AST-parsed every public (non-`_`-prefixed) top-level function, class, and
`UPPER_CASE` constant in `src/` (262 symbols), then regex-searched `src/`, `main.py`, and
`tests/` for each name, excluding its own definition line.

**Reachable only from tests (tests of code nothing uses in `src/`/`main.py`):**

| Symbol | file:line | Test callers |
|---|---|---|
| `ensure_writable` | `src/geofrea/core/paths.py:302` | `tests/unit/test_paths.py` (5 call sites) |

`ensure_writable()` guards writes to read-only data roots (GEOFREA_SHARED_RAW_DIR,
GEOFREA_LEGACY_BASELINE_DIR, CRAEI_BASELINE_DIR, GEOWORLD_BASELINE_DIR) per CLAUDE.md's
read-only-locations list, but no phase's write path calls it yet — every phase built so far
(F1/F1b/F2a/F2b) writes only under `outputs/`/`interim/`, never attempting a write to a
read-only root, so there has been no real call site to guard. Not dead in the sense of
"nobody needs this"; it is pre-built defensive code with no live caller yet.

**Reachable from nowhere (no caller in `src/`, `main.py`, or `tests/`):**

| Symbol | file:line | Kind |
|---|---|---|
| `phase_dir` | `src/geofrea/core/paths.py:176` | function |
| `thesis_dir` | `src/geofrea/core/paths.py:209` | function |

Both are `paths.py` helpers for output layout (A-08: `outputs/<ISO3>/<phase>/<kind>/` and
`outputs/thesis/`) with no caller and no test. `thesis_dir()` is F8-shaped (F8 is
`not_started`); `phase_dir()` is generic but likewise unused by any of the four phases wired
into `main.py::_build_phase_specs()` today (each of F1/F1b/F2a/F2b uses
`context.outputs_dir`/`register_artifact()` directly, not `phase_dir()`).

Proposed action for all three: owned by the phase whose wiring would first call them (F8 for
`thesis_dir`, whichever future phase for `phase_dir`/`ensure_writable`) — not delete, since
each is a direct implementation of an already-approved architecture requirement (A-08,
CLAUDE.md read-only locations) awaiting its first real caller, not orphaned legacy code.

No `vulture` or equivalent installed in `.venv`; this pass is a custom AST+regex script, not
a call-graph tool — it can miss dynamic dispatch (`getattr`, string-keyed registries) but the
codebase's own convention (`_FETCHED_LAYER_HANDLERS`-style dict-of-lambdas, confirmed by
grep) keeps every dynamic call site textually present as a dict value, which the regex pass
does catch.

---

## 3. Retired concepts

Grepped `src/`, `tests/`, `config/`, `docs/` (excluding `_archive/`, `_audit/`) for: `mcda`,
`ahp`, `owa`, `weight`, `score`, `normaliz`, `suitability`, `criteria`, `biomass`,
`abatement`, `sensitivity`, `potential_analysis`, `ghg`, `tri`, `terrain_score`. Most hits are
inside `suitability_criteria/` itself (the legacy module already fully tracked in
`docs/phases/F2b_siting_layers.md`'s per-criterion rebuild table) or are false positives from
substring matching common English words ("triangle", "trigger", "normalize [a string]",
"distribution"). The table below reports only hits **outside** `suitability_criteria/` that
implement a retired concept, judged by behavior, not by the word appearing.

| Term | file:line | What it does | Owned? |
|---|---|---|---|
| AHP (retired MCDA method) | `src/geofrea/core/constants.py:83` `AHP_RANDOM_INDEX`; `src/geofrea/grid_alignment/raster_alignment.py:262-284` `compute_ahp_weights()`, `_combine_wind_layers()` | Active production code: combines the 3 wind-height rasters (100/150/200 m) into a single aligned wind layer using AHP (Saaty eigenvector) pairwise-comparison weights, falling back to uniform 1/3 weighting when the consistency ratio exceeds 0.10. This is a genuine MCDA technique executing in `grid_alignment` (F2a), not a name collision — it runs today for every real country and is covered by `tests/unit/test_grid_alignment_raster_alignment.py`. | **Yes** — `docs/PROGRESS.json`'s F2a summary explicitly lists "wind AHP removal" as outstanding, under milestone MS-3 (F2a conformance). Not a new finding, but confirms it is still live code as of this audit, not yet removed. |
| `BiomassParams` class (retired technology, METHODOLOGY S-02) | `src/geofrea/core/schemas.py:255` `class BiomassParams` | A full Pydantic schema for biomass CAPEX/OPEX/lifetime/discount-rate/slope parameters. Biomass itself is out of scope (S-02, CLAUDE.md "Scope reminders"): `parameters.json` has no `biomass` key under `technologies` for any country, and `TechnologyParams`/config loading never reference `BiomassParams`. Kept per `tests/unit/test_config_loader.py:102-105`'s comment "for backward compatibility (`criteria.biomass` still exists)". | **Partially.** The `criteria.biomass`-adjacent fields it names (`biomass_smooth_sigma`, `land_suitability`'s per-class `biomass` weights) are on `docs/phases/F2b_siting_layers.md`'s explicit H-2 retirement list. The `BiomassParams` class itself is not named on that list — no task currently owns deleting it. |
| `criteria.biomass`-family config values | `config/parameters.json` — `criteria.biomass_smooth_sigma` (:996), `criteria.land_suitability.*.biomass` (11 land-cover classes, :1060-1120), `criteria.renewable_fuel_labels` including `"biomass"` (:1020), per-country `criteria.yield_by_land_cover` for BRA/PRT/IND (biomass yield tables) | Legacy biomass-siting parameters, still present in `parameters.json` and still validated by `ParametersFile`/`CriteriaParams` schemas since nothing has removed the fields. | **Yes** — all on the H-2 retirement list in `docs/phases/F2b_siting_layers.md` (`criteria.biomass_smooth_sigma`, `criteria.land_suitability`, `countries.{BRA,PRT}.criteria.yield_by_land_cover` are named verbatim; `criteria.renewable_fuel_labels` is also named). |
| `terrain_score` / TRI weight 0.4 | `src/geofrea/core/schemas.py:335,350,467` (docstrings only, no active TRI computation found outside `suitability_criteria/`) | See action 7 below — the live TRI contamination is inside `suitability_criteria/criteria_functions.py`, already recorded. | **Yes** — H-2, per action 7 below. |
| `mcda`, `owa`, `abatement`, `ghg`, `potential_analysis` | — | No hits outside `suitability_criteria/`, `_archive/`, or `_audit/` implementing any of these; the `_archive/architecture/ghg_abatement.md` and `potential_analysis.md` files are the retired legacy design docs themselves, correctly excluded by the grep scope. | n/a — nothing found to own |

Proposed action: `BiomassParams` class — **owned by H-2** (extend that task's scope to cover
the class itself, not only its config fields), since leaving a schema class for an
out-of-scope technology with no config data to validate against is the same category of
residue H-2 already exists to clear.

---

## 4. Configuration reachability

**Every config file, whether any loader reads it** (`src/geofrea/core/config_loader.py` is
the only place that opens a `config/*` file):

| File | Loader | Status |
|---|---|---|
| `config/parameters.json` | `load_parameters()` → `ParametersFile` | reachable |
| `config/settings.yaml` | `load_settings()` → `SettingsFile` | reachable |
| `config/audit.yaml` | `load_audit_config()` → `AuditConfig` | reachable |
| `config/countries.yaml` | `load_countries()` → `dict` (not schema-validated, unlike the other three) | reachable |
| `config/experiments.yaml` | **none** | **unreachable — no loader exists at all** |
| `config/technologies.yaml` | **none** | **unreachable — no loader exists at all** |

`config_loader.py` defines exactly four load functions (`load_parameters`, `load_settings`,
`load_audit_config`, `load_countries`); grepping `src/` and `main.py` for
`experiments.yaml`/`technologies.yaml`/`load_experiments`/`load_technologies`/
`ExperimentsFile`/`TechnologyRegistry` finds only two docstring mentions in
`core/schemas.py` (referring forward to the files, not reading them). Every key in both
files is therefore unread by any code path today.

Proposed action: **owned by whichever milestone first needs each file** —
`config/technologies.yaml` by A-04's consumer (first technology-registry-reading phase,
likely F5/F6, MS-8/MS-9) and `config/experiments.yaml` by U-01/U-03's consumer (F4/F6,
MS-7/MS-9). Not a defect today: both files' own docstrings already say "skeleton... values
that depend on [later phases]" — this is expected pre-implementation state, not drift.

**Reverse — every configuration value code expects that no file provides:**

None found. `SettingsFile`, `ParametersFile`, `AuditConfig` are all Pydantic models with
required fields; `load_settings()`/`load_parameters()`/`load_audit_config()` would raise
`pydantic.ValidationError` at startup if a required key were missing from the corresponding
YAML/JSON, and `main.py::main()` calls all three unconditionally before any phase runs — a
missing required key is therefore a fail-loud startup error, not a silent gap, and none is
currently present (the test suite's `test_config_loader.py`/`test_schemas.py` load the real
`config/` files in fixtures and pass).

---

## 5. Country scope

**How the default country list is determined today** (`main.py:502-521`):

```
countries_config = load_countries(COUNTRIES_YAML)                       # main.py:502
default_countries = [
    c for c in parameters.countries
    if not countries_config.get(c, {}).get("synthetic_fixture_root")    # main.py:511-513
]
countries = settings.run.countries or default_countries                 # main.py:514
unknown = [c for c in countries if c not in countries_config]           # main.py:515
```

`default_countries` iterates `parameters.countries` (i.e. `config/parameters.json`'s keys),
not `countries_config` (`config/countries.yaml`'s keys) — so the default (empty
`run.countries`) run set is entirely keyed off which countries have a `parameters.json`
entry. The `synthetic_fixture_root` filter (added by ADJ-2b, `git log -L` confirms it is the
only change to this block since D-core-017) only removes ZZZ from that already-`parameters.
countries`-scoped list; it does not itself decide which countries enter the base list.

**Does a country present in `config/countries.yaml` and absent from `config/parameters.json`
still run phases that read no parameters? — Answer: only if explicitly named in
`settings.yaml`'s `run.countries`; no via the default expansion.**

- `main.py:511-513` (`default_countries`) can never include such a country — it is built by
  iterating `parameters.countries`, so a country absent from `parameters.json` is absent from
  the default list regardless of the synthetic filter.
- If `settings.run.countries` explicitly names such a country, `main.py:515`'s `unknown`
  check only requires membership in `countries_config` (`countries.yaml`), not
  `parameters.countries` — so it passes. `run_geofrea()` (`main.py:463`) then does
  `country_params = parameters.countries.get(country_code)` → `None` is accepted
  (`main.py:458-462`'s comment: "a country present in countries.yaml but not yet in
  parameters.json can still run phases that read no CountryParams field"). This path is live
  and matches F2-3's original intent for an *explicitly targeted* country.

**Was this reintroduced through the synthetic filter?** No.
`git log -L 505,515:main.py` shows the base line
`countries = settings.run.countries or list(parameters.countries.keys())` (functionally
identical `parameters.countries`-driven default) has existed unchanged since the very first
orchestrator commit (`c4c4c75`, "Implement orchestrator + data_quality_audit phase") — long
before F2-3 and long before ADJ-2b. ADJ-2b's only edit to this block
(commit `0012415`) was adding the `synthetic_fixture_root` exclusion on top of the
pre-existing `parameters.countries` base, and a separate earlier commit (`7379ce2`) relaxed
the `unknown` check from `parameters.countries` to `countries_config` — which is what makes
the explicit-listing path above work at all. The default-expansion gap (a country absent
from `parameters.json` never enters the default run set) is a pre-existing condition of
`main.py`'s original design, not something ADJ-2b's synthetic-country change touched or
reintroduced.

Proposed action: **owned by whichever milestone reconciles this with F2-3's intent** — no
task currently owns making the *default* expansion also honor "parameters-optional
per-phase" the way the explicit-listing path already does. Flag only; not fixed here per the
command's instruction.

---

## 6. Synthetic reach

Every place production code branches on the synthetic country (ZZZ), with what a real
country's path does when the branch is absent:

| Branch | file:line | What a real country does without this branch |
|---|---|---|
| `resolve_synthetic_fetched_layer()` | `src/geofrea/data_acquisition/local_layers.py:329-352`, called from `src/geofrea/data_acquisition/phase.py:522-524` | Falls through to `fetch_handler`/`local_handler` (the real GADM/GWA/HydroSHEDS/WDPA/local-database resolution path) — the synthetic check returns `None` for every real country (`config.get(country_code, {}).get("synthetic_fixture_root")` is `None`/absent), so the branch is a pure no-op for BRA/PRT/IND. |
| `_country_raw_root()` | `src/geofrea/data_acquisition/local_layers.py:275-296`, consumed by 6 call sites (`local_layers.py:376,401,438,467,531,595`) resolving elevation/population/grid/roads/land_cover/solar | Returns `GEOFREA_SHARED_RAW_DIR/<source>/<country's real elevation_dir/land_cover_dir/...>` unchanged — this function IS the real-country path (it looks up `synthetic_fixture_root` first, falls through to the normal `GEOFREA_SHARED_RAW_DIR` construction when absent), so there is no separate "without this branch" behavior to compare; it is one function serving both cases via an if/else, not an added-on synthetic-only branch. |
| `VerifiedValue.synthetic` field | `src/geofrea/core/schemas.py:150` (`synthetic: bool = False`), validated at `:162-172` (`_synthetic_never_carries_a_real_tier`) | Defaults `False` for every real value; the validator only fires when `synthetic=True`, so a real country's `VerifiedValue` entries are entirely unaffected — the field and its validator are additive, not a fork in real-country logic. |
| `AuditConfig.country_overrides` | `src/geofrea/data_quality_audit/schemas.py:59,78`; consumed at `src/geofrea/data_quality_audit/audit.py:274-282` (`audit_config.country_overrides.get(context.country_code, {})`) | `.get(context.country_code, {})` returns `{}` for every real country (`config/audit.yaml`'s `country_overrides` map has only a `ZZZ` key) — the audit falls back entirely to the flat, source-driven `layers` config (native resolution/range/source per layer), which is what every real country audit run against today. |
| `main.py` default-country synthetic filter | `main.py:511-513` | Without the filter, `default_countries` would include ZZZ whenever it has a `parameters.json` entry (it does, as test fixture values) — a real country's own inclusion/exclusion is entirely governed by its own presence in `parameters.countries`, unaffected by this filter existing or not. |
| `config/countries.yaml`'s `synthetic_fixture_root` key itself | `config/countries.yaml:182` (ZZZ only) | Every real country's entry has no such key, so `.get(c, {}).get("synthetic_fixture_root")` is `None` for all of them — same no-op characterization as row 1. |

Cost assessment: every branch above degrades gracefully to the real-country path when the
synthetic key is absent (`.get(..., {})`/`.get(...)` chains, never a required field or an
`if country == "ZZZ": raise` shape) — the fixture's production-code footprint is six small,
additive `.get()`-guarded lookups, not a structural fork that real countries pay a
maintenance cost for. No branch found that a real country's path executes differently
*because* the synthetic branch exists (as opposed to simply not matching it).

---

## 7. ADJ-2b findings, recorded (not reinvestigated)

Both required findings are **already recorded** in `docs/phases/core.md` D-core-018
(2026-09-24, same COMMAND ADJ-3 authorization) — verified present, not re-written:

- **F2a grid-offset mechanism** (core.md D-core-018, "Finding 1"): the WGS84↔UTM round trip
  in `get_mainland_gdf()` (`src/geofrea/core/geo_utils.py:285-295`) combined with the
  untoleranced `np.floor`/`np.ceil` in `build_reference_grid()`
  (`src/geofrea/grid_alignment/reference_grid.py:58-61`) — owned by **G-3**. Also duplicated
  as a "Known issues" bullet in the same file.
- **F2b TRI contamination** (core.md's "Known issues" section, `terrain_score` entry): the
  TRI term at `terrain_tri_weight = 0.4` (`config/parameters.json:946-955`) is active in
  `suitability_criteria/criteria_functions.py` today, so no current F2b `terrain_score` output
  is a methodology-conformant baseline — owned by **H-2**, matching
  `docs/phases/F2b_siting_layers.md`'s conformance table row ("`terrain_score` → E4 slope (TRI
  term removed) → rework").

No new record lines written per the command's read-only instruction for this action beyond
verification — both already exist with the exact ownership (G-3, H-2) the command specifies.

---

## 8. Tests

**Test files mapped to what they cover** (37 files, `tests/unit/` + `tests/regression/`):

| Test file | Covers |
|---|---|
| `test_env_loading.py` | `.env` loading precedence (`main.py`'s `load_dotenv`) |
| `test_core_geodesy.py` | `core/geodesy.py` (geodesic distance/area) |
| `test_core_raster_io.py` | `core/raster_io.py` |
| `test_config_loader.py` | `core/config_loader.py` |
| `test_http_retry.py` | `core/http_retry.py` |
| `test_paths.py` | `core/paths.py` (`StoredPath`, `ensure_writable`, env-var roots) |
| `test_schemas.py` | `core/schemas.py` (`ParametersFile`, `TechnologyParams`, `BiomassParams`, etc.) |
| `test_iso3_literals.py` | A-05 enforcement (no ISO3 literals in `src/`) |
| `test_orchestrator.py` | `core/orchestrator.py` (DAG, manifest, resume, staleness) |
| `test_main.py` | `main.py` wiring (`_build_phase_specs`, country resolution) |
| `test_synthetic_value_separation.py` | OQ-032 test/sourced-value separation (`VerifiedValue.synthetic`) |
| `test_data_acquisition_schemas.py` | `data_acquisition/schemas.py` |
| `test_data_acquisition_adapter.py` | `data_acquisition/adapter.py` |
| `test_data_acquisition_local_layers.py` | `data_acquisition/local_layers.py` (incl. synthetic resolution) |
| `test_data_acquisition_phase.py` | `data_acquisition/phase.py` (`run_acquisition_phase`) |
| `test_fetchers_gadm.py`, `test_fetchers_hydrosheds.py`, `test_fetchers_power_plants.py`, `test_fetchers_protected_planet.py`, `test_fetchers_wind.py` | each corresponding `fetchers/*.py` module |
| `test_audit.py` | `data_quality_audit/audit.py` |
| `test_vector_inspection.py` | `data_quality_audit/vector_inspection.py` |
| `test_raster_inspection.py` | `data_quality_audit/raster_inspection.py` (largest file, 1,014 lines) |
| `test_grid_alignment_schemas.py`, `test_grid_alignment_adapter.py`, `test_grid_alignment_alignment.py`, `test_grid_alignment_raster_alignment.py`, `test_grid_alignment_vector_alignment.py`, `test_grid_alignment_reference_grid.py`, `test_grid_alignment_slope_derivation.py` | each corresponding `grid_alignment/*.py` module |
| `test_geo_utils.py` | `core/geo_utils.py` |
| `test_suitability_criteria_normalization.py`, `test_suitability_criteria_adapter.py`, `test_suitability_criteria_schemas.py`, `test_suitability_criteria_phase.py`, `test_suitability_criteria_functions.py` | each corresponding `suitability_criteria/*.py` module |
| `regression/test_suitability_criteria_regression.py` | V-01 frozen-fixture parity for the 14 legacy criteria |

**Tests that exercise removed behavior:** the entire `regression/test_suitability_criteria_
regression.py` parametrization over `lc_biomass`, `biomass_resource` (both technologies
removed, S-02) and `grid_suitability`, `river_solar`, `river_wind`, `pop_suitability`,
`terrain_score` (all marked "rework" or to-be-replaced in `docs/phases/F2b_siting_layers.md`'s
conformance table). Already flagged as a known issue in that phase record ("Regression
fixtures `regression-fixtures-v1` cover the 14 legacy criteria; only E1-E3 layers remain
under V-01") — owned by MS-3/MS-4's refreeze, not a new finding.

**Suite runtime:** `pytest tests/unit` — 634 passed, 137.03s wall time (2m17s), 271 warnings
(mostly geographic-CRS-area `UserWarning`s and rasterio `PendingDeprecationWarning`s, no
failures). `tests/regression/` was not executed (24 tests collected; needs
`GEOFREA_LEGACY_BASELINE_DIR` populated with the real frozen baseline, not present in this
session's environment) — collection succeeded, run skipped, not a gap in this audit's
read-only scope.

**Ten slowest (`--durations=12`, unit suite):**

| Test | Duration |
|---|---|
| `test_suitability_criteria_phase.py::test_phase_produces_all_implemented_criteria` | 10.88s |
| `test_suitability_criteria_phase.py::test_phase_result_round_trips_through_output_model` | 9.62s |
| `test_suitability_criteria_phase.py::test_phase_buckets_partition_canonical_criteria` | 9.32s |
| `test_suitability_criteria_phase.py::test_phase_writes_report` | 9.30s |
| `test_suitability_criteria_phase.py::test_phase_protected_areas_assumed_free_without_wdpa` | 9.22s |
| `test_suitability_criteria_phase.py::test_phase_writes_one_tif_per_criterion` | 9.20s |
| `test_suitability_criteria_phase.py::test_phase_writes_slope_degrees_outside_criteria` | 9.17s |
| `test_suitability_criteria_phase.py::test_corrupted_wdpa_error_message_survives_to_orchestrator_output` | 8.86s |
| `test_suitability_criteria_phase.py::test_phase_separates_input_absent_from_not_implemented` | 8.37s |
| `test_audit.py::test_run_audit_phase_summary_footer_text_for_raster_and_vector_layer` | 4.15s |

All 9 slowest are in `test_suitability_criteria_phase.py` (the legacy F2b phase's full
raster-writing integration tests) — consistent with that module producing 14 real COG/report
outputs per test run, not a per-test anomaly.

**Tests that write outside a temporary directory:** none found.
`tests/conftest.py:34-42`'s `mock_geofrea_data_dir` fixture is `autouse=True` at function
scope and `mock.patch.dict`-overrides `GEOFREA_DATA_DIR` to `tmp_path` for every single test
unconditionally (not `setdefault` — it always wins, even over a real exported env var), so
every test that writes through `paths.py`'s `StoredPath` resolution writes under pytest's own
`tmp_path`. The one file referencing a bare `Path("outputs/PRT/...")` string
(`tests/unit/test_suitability_criteria_schemas.py:76-78`) is a schema-field value used for an
equality assertion, never passed to a write call — confirmed by reading the surrounding test,
which constructs a `SuitabilityCriteriaResult` object and asserts its fields, doing no I/O.

**The ZZZ leftovers (`outputs/ZZZ`, `interim/ZZZ`, `logs/ZZZ` inside `GEOFREA_DATA_DIR`):**
came from the **manual verification run** recorded in `docs/phases/core.md` D-core-018 (the
"Run result... F1+F1b in 0.93s, +F2a in 0.46s, +F2b in 10.15s" hand-check), not from the
pytest suite. That run is described as exercising the real `main.py`/orchestrator path against
the real `GEOFREA_DATA_DIR` with "no monkeypatch, no network call" to produce timing numbers —
which requires running outside pytest's `mock_geofrea_data_dir` override, since that fixture
only exists inside pytest's test collection. No test in the suite would reproduce this: every
test's `GEOFREA_DATA_DIR` is forced to an isolated `tmp_path` regardless of the ambient
environment, so no unit test can write to the real `GEOFREA_DATA_DIR/outputs/ZZZ` short of
explicitly bypassing that fixture (grepped for — no test does).

---

## 9. Scripts and stray files

Repository-root files that are neither configuration nor documentation, plus `scripts/`:

| File | What it is | Proposed action |
|---|---|---|
| `regression-fixtures.tar.gz` (380 MB, root) | Packaged V-01 regression fixture, staged for the `regression-fixtures-v1` GitHub Release (per `PROGRESS.json`'s `regression.fixtures_release` and `.gitignore:10-12`'s own comment). Confirmed **not tracked by git** (`.gitignore` excludes it explicitly) — it is local build output, not a committed stray file. | keep (local artifact, correctly gitignored; not a repository-cleanliness issue) |
| `scripts/generate_zzz_fixture.py` | Actively used: regenerates the ZZZ fixture fresh on every CI run (`.github/workflows/synthetic_fixture.yml`, per D-core-018) and was run manually for this session's ZZZ leftovers. Has a docstring naming its owning command (ADJ-2). | keep (live, CI-invoked) |
| `scripts/migrate_manifest_2_0_to_2_1.py` | Single-use migration script, explicitly labeled as such in its own docstring ("Single-use migration script... COMMAND E5b action 11"). Its job (manifest schema 2.0→2.1 StoredPath conversion) is complete — `RunManifest.schema_version` is now pinned `"2.0"`... actually per `docs/phases/core.md` D-core-003, pinned to `"2.0"` with `LegacyManifestError`, and separately the 2.1 migration is E5b-specific; task is closed per `docs/phases/E5b.md`. | owned by whoever confirms E5b is fully closed (delete candidate — single-use, task done — but not deleted here per the read-only scope) |
| `scripts/move_geofrea_data_e5b.py` | Single-use migration script, explicitly labeled "Single-use migration script" for COMMAND E5b Part B (repo-to-external data move). Same closure status as above. | owned by whoever confirms E5b is fully closed (delete candidate) |
| `docs/phases/E5b.md` | Phase-shaped record for the one-off E5b migration (see action 1) | keep (historical decision record, D-E5b-001) |

No other file at the repository root is outside configuration (`config/`, `.env*`,
`pyproject.toml`) or documentation (`CLAUDE.md`, `README.md`) — `main.py` is the entry point
(expected), `.github/`, `.git/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
are tooling directories, not repository content.

---

## Summary counts

| Category | Count |
|---|---|
| Modules inventoried | 14 (13 phase modules + core); 8 empty placeholders (all `not_started`, expected); 1 name mismatch (`suitability_criteria` vs. `siting_layers`, already tracked) |
| Dead code (no caller anywhere) | 2 (`phase_dir`, `thesis_dir`) |
| Test-only reachable | 1 (`ensure_writable`) |
| Retired-concept hits outside `suitability_criteria/` that implement (not just name-share) a retired concept | 3 groups: AHP wind-combination (owned MS-3), `BiomassParams` class + biomass config fields (owned H-2, class itself unowned), `terrain_score`/TRI (owned H-2, per action 7) |
| Config keys unreachable by any loader | 2 files entirely (`experiments.yaml`, `technologies.yaml`) |
| Config values code expects with no provider | 0 |
| Country-scope question (action 5) | Answered: No, not reintroduced by the synthetic filter — pre-existing gap since the first orchestrator commit |
| Synthetic-reach branches in production code | 6 |
| ADJ-2b findings to record | 2 — both already present in `docs/phases/core.md` D-core-018 |
| Test files | 37 (36 unit + 1 regression module) |
| Tests exercising removed behavior | entire `test_suitability_criteria_regression.py` (7 of 8 parametrized criteria; already known issue) |
| Unit suite runtime | 137.03s, 634 passed |
| Tests writing outside a temp directory | 0 |
| Stray files/scripts | 5 rows (1 keep as-is gitignored artifact, 1 keep as live CI script, 2 delete candidates pending E5b closure confirmation, 1 keep as historical record) |
