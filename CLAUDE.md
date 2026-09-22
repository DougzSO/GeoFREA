# CLAUDE.md: GeoFREA

## Project

GeoFREA is a spatially explicit framework for solar and wind expansion planning under climate and techno-economic uncertainty, built for Douglas's PhD thesis (UFMG). Its scientific method, scope, phase contracts, and thesis outputs are defined in `docs/METHODOLOGY.md`, which is the single source of truth. Anything in code or in other documents that conflicts with `docs/METHODOLOGY.md` is a defect or an open question, never an alternative authority.

All documentation, code, comments, docstrings, and commit messages are in US English.

## Session start

Read, in this order, before proposing or doing anything:

1. `docs/PROGRESS.json`
2. The sections of `docs/METHODOLOGY.md` referenced by the task (at least the phase specification and the related A-, U-, V- items)
3. `docs/phases/<phase>.md` for the phase being touched
4. `docs/OPEN_QUESTIONS.md` entries that block the phase

Do not load archived records (`docs/_archive/`) unless the task explicitly asks for historical rationale.

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
| `docs/phases/<phase>.md` | Phase contract, conformance table, active implementation decisions, known issues, history | Current state, rewritten in place |
| `docs/OPEN_QUESTIONS.md` | Unresolved items only | Items leave when resolved |
| `docs/LIMITATIONS.md` | Declared limitations and every Tier 3 value | Append and maintain |
| `docs/PROGRESS.json` | Status per phase and country | Rewritten in place |
| `docs/CONVENTIONS.md` | Coding conventions | Maintained |

What triggers a record in `docs/phases/<phase>.md`:

- A change to a scientific result, a data contract, or the interpretation of a methodology item: record it as an implementation decision (`D-<phase>-nnn`), at most about eight lines.
- A bug fix that changes results: one line under the decision it affects, or a new decision if none applies.
- Refactoring or performance work without result changes: commit message only.
- A superseded decision leaves the active section and becomes one line under History, pointing to the decision that replaced it.
- When a phase record exceeds about 400 lines, compact History.

Changelog language ("was changed because", "previously") appears only in History sections and in the METHODOLOGY changelog. Code, docstrings, phase contracts, and thesis text describe the current state only.

When an open question is resolved: move the resolution into the relevant phase record (decision or conformance row), update `docs/METHODOLOGY.md` only if the resolution changes a methodology item and Douglas authorized it, then delete the entry from `docs/OPEN_QUESTIONS.md`.

## Session end

At the end of every session that changed code or documents:

1. Update the conformance table and decisions of the touched phase record.
2. Update `docs/PROGRESS.json` (`last_updated`, phase status, country status, `summary` of at most 200 characters).
3. Add any new Tier 3 value or limitation to `docs/LIMITATIONS.md`.

## Commits

- Never commit or push without explicit authorization from Douglas for that specific commit, after presenting the diff.
- Review and approval of a change and the commit itself happen in separate steps.
- Temporary CI infrastructure or debug scripts (even gated to `workflow_dispatch` and planned for removal) need approval before each commit or push, and their creation and removal (with commit SHAs) are recorded in the related phase record.

## Read-only locations

- `GEOFREA_SHARED_RAW_DIR`: shared raw data (environment variable, never under repository root). Read-only. Never modified by the pipeline.
- `GEOFREA_LEGACY_BASELINE_DIR`: frozen legacy baseline outputs. Read-only reference for regression tests.
- `GEOWORLD_BASELINE_DIR`: legacy geoworld framework. Read-only. Used only to consult logic (never ported line by line) when a task explicitly requires it.
- `CRAEI_BASELINE_DIR`: CRAEI climate-risk framework. Read-only. Primary reference repository for climate data acquisition, hazard processing, and risk logic. Code may be copied into GeoFREA and adapted under METHODOLOGY A-11, with a provenance header. Never import from it and never edit it.

Note: All pipeline data lives in GEOFREA_DATA_DIR (external directory). No data is stored under the repository root (`outputs/`, `outputs_baseline_fc7b43d/`, logs, etc.).

## Regression and testing

- Frozen regression (METHODOLOGY V-01): binary layers require exact parity; float rasters `rtol = 1e-6` unless a documented platform difference justifies a larger bound in the phase record.
- Fixtures are refrozen only with Douglas's authorization, recorded in the phase record with the reason.
- Phases F3 onward are tested by analytical cases, invariants, and sanity ranges (V-02 to V-04), not by legacy parity.
- Every new method item needs at least one test that fails if the item is violated.

## Concurrency

Before writing shared documents (`docs/METHODOLOGY.md`, `docs/phases/`, `docs/PROGRESS.json`, `docs/OPEN_QUESTIONS.md`, `docs/LIMITATIONS.md`), check for `.session-lock` at the repository root. If present, treat it as a concurrent session and do not write without coordination.

## Delegation policy

- Audit, inventory, provenance, and conformance work is executed in the main session. It is never delegated to a subagent.
- A subagent may only be used for a task whose completion criterion is a count or a file list, and only when the main session re-verifies that count or list afterward.
- Reporting an action as done when it was narrowed or skipped is a stop-and-report condition, not a deferral. Report it to Douglas immediately instead of continuing.

## Geometry over bounding box

Any tile, extent, or coverage claim about a country is decided by intersection with the GADM country polygon, never by bounding box. A bounding box overstates coverage in every non-rectangular country. Precedent: the BRA S36W057 tile and the IND 28-tile case were both wrongly included/counted under bounding-box logic and corrected only after GADM polygon intersection was applied.

## Scope reminders

In scope: BRA, PRT, IND; solar PV and onshore wind; SSP1-2.6, SSP3-7.0, SSP5-8.5; windows 2041-2070 and 2071-2100. Out of scope: GHG abatement, biomass, seismic, transport decarbonisation, sea-level rise, wildfire. Do not add code for out-of-scope items.
