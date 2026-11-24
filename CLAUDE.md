# CLAUDE.md: GeoFREA

## Project

GeoFREA is a spatially explicit framework for the climate adaptation of power supply planning (fleet risk, supply gap and adaptive solar and wind expansion), built for Douglas's PhD thesis (UFMG). This is v2; v1 is summarised in `docs/v1/record.md` and lives in the tags `v1.0`, `v1.1` and `v1-final`. Its scientific method, scope, phase contracts, and thesis outputs are defined in `docs/METHODOLOGY.md`, which is the single source of truth. Anything in code or in other documents that conflicts with `docs/METHODOLOGY.md` is a defect or an open question, never an alternative authority.

All documentation, code, comments, docstrings, and commit messages are in US English.

## Session start

Read, in this order, before proposing or doing anything:

1. `docs/README.md` (index) and `docs/PROGRESS.json`
2. The sections of `docs/METHODOLOGY.md` referenced by the task (at least the phase specification and the related A-, U-, V- items)
3. `docs/phases/<phase>.md` for the phase being touched
4. `docs/OPEN_QUESTIONS.md` entries that block the phase

The documents describe the current state only; the history is in git and in the tags. Reports that the documents cite are in `docs/evidence/`.

## Authority and change rules

- `docs/METHODOLOGY.md` is edited only with explicit authorization from Douglas, following its Section 0 change protocol.
- If implementation requires deviating from, reinterpreting, or extending a methodology item, open an entry in `docs/OPEN_QUESTIONS.md`, stop work on that item, and report. Never implement a deviation first.
- A methodological value without a documented primary source is never assumed. Register it as an open question awaiting Douglas's verdict.
- If a value depends on data that does not exist yet, register the approved protocol, not a value. The value enters only after the data exists.
- When delegating to a subagent, pass the command verbatim. A subagent or the main session must not replace, narrow, or defer an instructed action; if an action seems wrong or too large, stop before executing and report the objection for Douglas's verdict.

## Record keeping

Where things are recorded:

| Record | Content | Mode |
|---|---|---|
| `docs/METHODOLOGY.md` | Method, architecture, outputs | Static, versioned |
| `docs/phases/<phase>.md` | Phase contract, conformance table, active implementation decisions | Current state, rewritten in place |
| `docs/DECISIONS.md` | Decisions of v2, from DEC-001 | Append-only |
| `docs/OPEN_QUESTIONS.md` | Unresolved items only | Items leave when resolved |
| `docs/LIMITATIONS.md` | Declared limitations and every Tier 3 value | Append and maintain |
| `docs/PROGRESS.json` | Status per phase and country | Rewritten in place |
| `docs/CONVENTIONS.md` | Coding conventions | Maintained |

What triggers a record in `docs/phases/<phase>.md`:

- A change to a scientific result, a data contract, or the interpretation of a methodology item: record it as an implementation decision (`D-<phase>-nnn`), at most about eight lines.
- A bug fix that changes results: one line under the decision it affects, or a new decision if none applies.
- Refactoring or performance work without result changes: commit message only.
- A superseded decision leaves the active section; the history is in git.

Code, docstrings, phase contracts, documents and thesis text describe the current state only; the reason for a change goes in `docs/DECISIONS.md` and the commit message.

When an open question is resolved: move the resolution into the relevant phase record (decision or conformance row), update `docs/METHODOLOGY.md` only if the resolution changes a methodology item and Douglas authorized it, then delete the entry from `docs/OPEN_QUESTIONS.md`.

## Session end

At the end of every session that changed code or documents:

1. Update the conformance table and decisions of the touched phase record.
2. Update `docs/PROGRESS.json` (`last_updated`, phase status, country status, `summary` of at most 200 characters).
3. Add any new Tier 3 value or limitation to `docs/LIMITATIONS.md`.

## Commits

- Pre-registration: the decision phases (F7, M1, M2, M3) run on real data only after the annotated tag `prereg-v2` exists, and the digest of the pre-registered subset must match the live configuration (METHODOLOGY M-F7-13). From the creation of the tag, a change to a selector of the digest is a deviation that needs Douglas's verdict.
- A phase F1 to F3 must not become stale because of a change in a document or in code that does not change its result: prove it with `python main.py <ISO> --phases <phase> --plan` before the commit.

- Never commit or push without explicit authorization from Douglas for that specific commit, after presenting the diff.
- Review and approval of a change and the commit itself happen in separate steps.
- `docs/thesis/cap1_introduction.tex` is a tracked file like any other (committed in `90f2629` by the author's express authorization); no file of `docs/thesis` is excluded from commits by rule: the usual rule applies, an explicit authorization for each commit.
- Temporary CI infrastructure or debug scripts (even gated to `workflow_dispatch` and planned for removal) need approval before each commit or push, and their creation and removal (with commit SHAs) are recorded in the related phase record.
- Before every commit or push, read the state of the CI on `main` with `gh run list --branch main --limit 6` and report to the author the conclusion of each workflow for the current HEAD and the last green commit of each. A red workflow is never carried silently: say which commit turned it red. After each push, wait for the workflows of the new HEAD and report them before the next command.
- Before a commit that changes code under `src`, run locally what the local suite does not cover: the two synthetic end-to-end tests (`tests/synthetic/test_zzz_end_to_end.py::test_every_phase_from_f1_to_f6_runs_and_succeeds` and `tests/synthetic/test_zzz2_end_to_end.py::test_every_phase_from_f1_to_f8_runs_and_succeeds`, as in the `synthetic-fixture` workflow) and the hand validator of the four cases (`scripts/synthetic/validate_zzz_by_hand.py <dir> <wind|solar> <zzz|zzz2>`, as in the `hand-validation` job), and report the result with the diff.

## Read-only locations

- `GEOFREA_SHARED_RAW_DIR`: shared raw data (environment variable, never under repository root). Read-only. Never modified by the pipeline.
- `GEOFREA_LEGACY_BASELINE_DIR`: frozen legacy baseline outputs. Read-only reference for regression tests.
- `GEOWORLD_BASELINE_DIR`: legacy geoworld framework. Read-only. Used only to consult logic (never ported line by line) when a task explicitly requires it.
- `CRAEI_BASELINE_DIR`: CRAEI climate-risk framework. Read-only. Primary reference repository for climate data acquisition, hazard processing, and risk logic. Code may be copied into GeoFREA and adapted under METHODOLOGY A-11, with a provenance header. Never import from it and never edit it.

Note: All pipeline data lives in GEOFREA_DATA_DIR (external directory). No data is stored under the repository root (`outputs/`, `outputs_baseline_fc7b43d/`, logs, etc.).

## Regression and testing

- Frozen regression (METHODOLOGY V-01): integer, categorical and binary layers require exact parity; float rasters `|Δ| <= 1e-6 * |ref| + 1e-9` (`core/equivalence.py`) unless a documented platform difference justifies a larger bound in the phase record.
- Fixtures are refrozen only with Douglas's authorization, recorded in the phase record with the reason.
- Phases F3 onward are tested by analytical cases, invariants, and sanity ranges (V-02 to V-04), not by legacy parity.
- Every new method item needs at least one test that fails if the item is violated.
- The suite runs in parallel with `pytest -n 3` (pytest-xdist, in the dev extras): the whole suite takes about 24 minutes against 46 in one process on the same day (COMMAND 131: 2,541 passed and 1 skipped in the second of two runs, 2,539 passed and 1 failed in the first, the failure being a Windows race in `layer_process.kill_tree` that is now fixed). Three workers hold up to 2.7 GB between them (the BRA-sized synthetic tests and the ZZZ fixtures): on a machine with 6 GB close the browser and the editor first, or use `-n 2`; free memory fell to 8 MB in one of the two runs. The unit job of the CI uses `-n 3`. The memory caps of `core/memory_cap.py` bind the runs of `main.py` only: `tests/conftest.py` sets `GEOFREA_MEMORY_CAPS=0`.

## Concurrency

Before writing shared documents (`docs/METHODOLOGY.md`, `docs/phases/`, `docs/PROGRESS.json`, `docs/OPEN_QUESTIONS.md`, `docs/LIMITATIONS.md`), check for `.session-lock` at the repository root. If present, treat it as a concurrent session and do not write without coordination.

## Delegation policy

- Audit, inventory, provenance, and conformance work is executed in the main session. It is never delegated to a subagent.
- A subagent may only be used for a task whose completion criterion is a count or a file list, and only when the main session re-verifies that count or list afterward.
- Reporting an action as done when it was narrowed or skipped is a stop-and-report condition, not a deferral. Report it to Douglas immediately instead of continuing.

## Geometry over bounding box

Any tile, extent, or coverage claim about a country is decided by intersection with the GADM country polygon, never by bounding box. A bounding box overstates coverage in every non-rectangular country. Precedent: the BRA S36W057 tile and the IND 28-tile case were both wrongly included/counted under bounding-box logic and corrected only after GADM polygon intersection was applied.

## Memory safety

`groupby(...).transform(lambda s: s.rolling(...))` or `.groupby(...).apply(...)` over a full, ungrouped-in-advance table materializes a Series per group and concatenates them — with many thousands of groups this can exhaust machine RAM and crash the desktop (observed in a sibling framework, COMANDO 15/17; not yet hit in GeoFREA, checked 2026-09-29). Same risk for `.load()` before `.to_netcdf()`/`.to_dataframe()` on a dataset larger than a single already-cropped country-year (the real MemoryError fixed in F4-7, `fetchers/era5.py`'s `merge_yearly_files()`/`crop_to_country_polygon()`). Any new large-table or multi-year raster reduction must process per (country, model) chunk with an explicit, bounded memory footprint, not a single groupby/load over the whole table.

## Scope reminders

In scope (v2.0): BRA, PRT, IND; hydro, solar and wind fleet; solar PV and onshore wind expansion; five ISIMIP3b models; SSP1-2.6, SSP3-7.0, SSP5-8.5; window 2041-2070 (reference 1995-2014). Out of scope: GHG abatement, biomass, thermal plants (v2.1), seismic, transport decarbonisation, sea-level rise, wildfire, the window 2071-2100 (OQ-118). Do not add code for out-of-scope items.
