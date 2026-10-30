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

Used in `docs/PROGRESS.json` only (phase records carry no status line):

- `not_started`
- `in_progress`
- `built_pending_conformance`: code exists but has not been audited against the current methodology
- `conformant`: audited, all conformance rows pass
- `rework_required`: code exists and conflicts with the methodology

Country run status per phase: `not_run`, `ran_with_issues`, `ran_clean`, and, while a check of the content is open, `awaiting_content_check_post_77` (the phase ran, but its artifacts have not been compared with the state before the performance work of COMMANDS 75 to 79; `pending_verifications` of `docs/PROGRESS.json` says what is missing and where it is done, and the status returns to `ran_clean` when the check settles). They describe the execution only: `ran_with_issues` when the last run of the phase logged a warning, an error or an alert from that phase, `ran_clean` when it did not. The quality of the sources and open research questions are recorded in `docs/LIMITATIONS.md` and `docs/OPEN_QUESTIONS.md`, never in the run status.

## Where status lives

The status of a phase, of a country run and of a milestone lives only in `docs/PROGRESS.json`.

- METHODOLOGY Section 12 holds milestones, content and gates, with no state column and no sentence about the state. A milestone is described by what it contains and what closes it.
- Comments in `config/*.yaml` and docstrings in `src/` do not assert state: no "not built yet", "pending", "in progress" or a date of state. They say what a key or function does and which question (OQ) sets a value.
- Phase records (`docs/phases/`) record decisions, their reasons and their tests, not the current status of the phase.
- `test_status_lives_only_in_progress` enforces this for METHODOLOGY Section 12 and the config files.

## Decision records

A decision is recorded once, in the record of its phase (`docs/phases/<phase>.md`), as one bullet that starts `- **D-<phase>-<number> — Title (date, command).**`, or as a table row that starts `| D-<phase>-<number> |`. A later paragraph about the same decision is a continuation of that bullet or cites the ID without starting with it. IDs rise in the order of the file. `scripts/find_decision.py D-<phase>-<number>` prints the defining lines of an ID.

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
- Map file names: `{ISO3}_{phase}_{variable}_{technology}_{scenario}_{climate}.png` (`mapstyle.figure_filename`): fields that do not apply are left out, never written as `na`; the ISO3 code is always there. Files written before COMMAND 66 keep the old pattern (`<map>__ref__na__na.png`) until their phase runs again.
- One map per file. Figures respect `settings.yaml` `figures`. The metadata of a figure is in the text chunks of its PNG; a folder has one `figures_index.json`, no sidecar per figure.
- Map style: new maps are drawn with `src/geofrea/viz/mapstyle.py` (`docs/figures/style_guide.md`); the figures that exist today are listed in `docs/figures/inventory.md` and move to it one at a time.
- Thesis outputs are produced only by F8 into `GEOFREA_DATA_DIR/outputs/thesis/`, named by their T-ID (`T-R4_max_regret_BRA_solar.png`).

## Thesis text

- `docs/thesis/` holds the LaTeX text of the thesis, in US English, one file per section; hypothesis sections go under `docs/thesis/hypotheses/`.
- File names: `<ID>_<snake_case_topic>.tex` (for example `H1_climate_rank_robustness.tex`).
- The METHODOLOGY stays the single source of the method. Thesis figures and tables stay in `GEOFREA_DATA_DIR/outputs/thesis/` (F8).

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

## Memory before a cold round

A cold audit or a cold F2a of a large country peaks near 2 to 4 GB. `main.py` does not start a run whose target phases include a cold `data_quality_audit` or `grid_alignment` (no current manifest entry or cache for the country) when `core/memory_guard.py` finds less than **2 GB available** (`MIN_AVAILABLE_GB`): it logs the shortfall and exits with code 75 before any phase of any country runs. Close the browser and the editors first. A script that runs a country unattended (`scripts/run_unattended.ps1`) also samples the available memory and stops the country cleanly under 400 MB, so the manifest keeps the phases that finished (it is replaced atomically, never truncated).

## Keeping the computer awake

`settings.yaml` `keep_awake` (schema default `false`; the shipped file sets `true`) tells `main.py` to ask Windows not to suspend the computer while a run goes on. A phase suspended by the system logs hours of wall time that its CPU time does not show: report a duration as **awake time** (`wall - slept`, the sleeps read from the Kernel-Power 42 and Power-Troubleshooter 1 events, `scripts/profiling/export_power_events.ps1`), never as wall time alone.

## Changes that must not change a result

A change made for speed or memory is accepted only with the canonical content hash (`core/content_hash.py`, the hash of the manifest) of what it writes equal to that of the code before it, on the same input; a clip is compared with `equals_exact` at tolerance 0, a figure by pixels. The proof runs on a sample country and, for a transformation that depends on the data (a clip of a layer with lines that touch themselves), on the whole layer of the countries it touches. One change per commit, with tests; a change that cannot be proved equal is not applied and its evidence stays in `docs/_audit`. Where a country cannot be run in the proof (hours of compute), the proof is deferred to the pipeline itself: `config/deferred_checks.yaml` names a reference manifest and the first execution of each phase is compared with it (D-core-050). A new cache key or a changed fingerprint rebuilds the internal caches once; adopting the caches of an earlier revision is allowed only under D-core-044.

## Run legibility (COMMAND ADJ-7)

A manual run must show what it is doing while it is doing it — a failure or a wrong result is visible as it happens, not only after the fact in a manifest or a report file.

- **Console vs. file.** `main.py::run_geofrea()` calls `core/run_logging.py::configure_logging()` once per country, attaching both handlers to the shared `"geofrea"` ancestor logger (not the plain root logger — every `geofrea.*` module's logger is a descendant of it, so both handlers see every record any of them emits). Console: `logging.INFO` and up, compact format. File (`GEOFREA_DATA_DIR/logs/<ISO3>/<run_id>.log`): `logging.DEBUG` and up, includes the logger name — the complete record, always a superset of the console.
- **Per phase, on start.** The orchestrator logs the phase name, the country, and one of: executing (no manifest entry, or `rerun_phases` names it — say which), or resuming (manifest status `"success"`, dates of the prior run). A resumed phase's line always says why it resumed — the manifest status that decided it — never just "skipped".
- **Per phase, on completion.** Elapsed time, every artifact registered this run (path + size in bytes), and — for a phase whose `PhaseSpec.summarize` is set — one line telling you the numbers are plausible without opening a file (F1: layer counts by `resolution_status`; F1b: audited/not_audited counts and any alert; F2a: raster dimensions, resolution, and grid origin). A phase with no `summarize` still logs elapsed time and artifacts; `summarize` is optional, the rest is not.
- **On failure.** One block: the phase name, the country, the exception type and message, its `file:line` (innermost traceback frame), and the full list of dependents that consequently will not run (computed immediately from the requires/produces graph, not discovered one line at a time as the orchestrator later reaches each of them).
- **Long loops report progress, never a progress bar.** `core/run_logging.py::PeriodicProgress` (or its `periodic_progress()` wrapper) logs a `"<label>: <done>/<total> done, elapsed <Xs>"` line every N items (default 10) or every `min_interval_s` (default 30s), always on the first and last item. A progress bar's carriage-return redraw is unreadable once a console is redirected to a log file; a periodic INFO line reads identically in both. New long loops (mosaic building, tile-by-tile audits, any per-file loop over more than a handful of files) use `PeriodicProgress`, not `tqdm` or a hand-rolled bar.
- **End of run.** `main.py::main()` logs one table (`core/run_logging.py::render_run_table()`): country, phase, status, elapsed time, artifact count — one row per phase attempted, across every country in the run — followed by the run id.

## Code reused from reference repositories

Code copied from CRAEI (see METHODOLOGY A-11) must have a provenance header with repository, commit SHA, original path, and adaptation summary, placed directly above the `def` line — outside the docstring, since it documents where the *code* came from, not what it does. A-13's `Implements: M-<item>.` line is separate: it is the first line of the docstring body, documenting what the function *does* against the method. The two lines answer different questions and never merge into one:

```python
# Adapted from CRAEI: https://github.com/<repo>
# Commit: <sha>  Original path: <path>
# Adaptation: <one-line summary>
def some_function(...) -> ...:
    """One-line summary of what the function does.

    Implements: M-<item>.

    Args:
        ...
    """
```

Filled example, approved F1-1 (2026-09-23) against a real CRAEI function — illustrates the header mechanics only, not a wind adaptation (CRAEI has no wind module to adapt; see `docs/phases/F1_data_acquisition.md`, M-F1-03 row):

```python
# Adapted from CRAEI: https://github.com/<douglas-org>/craei
# Commit: baae8816f65d3a0b3c2379461639e20a375b14d6  Original path: src/craei/acquire/auxiliary.py:57 (run_hydrobasins)
# Adaptation: per-country download-loop and manifest-registration pattern adapted for
# CMIP6/ERA5 fetch jobs; region/URL construction and payload handling are new.
def run_hydrobasins(manifest: Manifest, raw_dir: Path) -> list[dict]:
    """Download HydroBASINS level 6 zips per country region.

    Implements: M-F1-04.
    ...
    """
```

Every later adaptation follows this format: provenance comment above the `def`, `Implements:` line inside the docstring. No imports from CRAEI or other reference repositories. Reference repositories remain read-only; edits belong in GeoFREA only. Code with no CRAEI counterpart is written fresh and carries no provenance header — there is nothing to attribute.

## Tests

- `pytest`, `ruff` clean before any commit proposal.
- Test names state the property tested (`test_regret_is_non_negative`).
- Tests that need external data (raw, legacy baseline, reference repositories) are marked and skipped when required env vars are unset; the synthetic country fixture covers CI.
- Development loop (COMMAND 75): while developing, run only the tests the change can reach: `python scripts/affected_tests.py --run` selects the test files whose import closure (the one that fingerprints a phase's code) contains a changed module, plus the changed tests and the tests that name a changed non-Python file; `pytest --testmon` (pytest-testmon) is the alternative that learns the selection from coverage. Both can miss a test that reaches code through a string (a path, a registry).
- The full suite is mandatory before every merge, and it is the only gate. pytest-xdist with 2 workers (`-n 2 --dist loadgroup`) was evaluated: 15% faster than one worker (22:47 against 26:41) with a process-tree peak of 3.04 GB (decimal), at the 3 GB limit of the machine; it is not the default.
