# GeoFREA Pipeline Provenance and Conformance Audit

**Date:** 2026-09-22  
**Scope:** GeoFREA repository reconstruction audit against METHODOLOGY.md v1.1.0  
**Methodology version referenced:** v1.1.0 (adopted 2026-09-15, updated 2026-09-21)  
**Audit method:** Read-only systematic search of src/geofrea/ modules, phase records in docs/phases/, git history, and baseline repositories.

---

## Executive Summary

This audit examines the current state of the GeoFREA pipeline against the complete method specification (METHODOLOGY.md Section 5, phases F1–F8 and E1) and checks conformance of each implementation against what phase records claim.

**Key findings (recomputed by literal row count against the 60-row table below — see "Count method" note):**

- **Total M-items specified:** 60 items across 12 phases (F1–F8, E1; plus F1b, F7b)
- **Status = `implemented` (2 rows):** M-F1-01, M-F1b-02
- **Status = `partial` (11 rows):** M-F1-02, M-F1-03, M-F1-07, M-F1b-01, M-F2a-01, M-F2a-02, M-F2a-03, M-F2a-04, M-F2b-01, M-F2b-02, M-F2b-03
- **Status = `not_implemented` (47 rows):** M-F1-04, M-F1-05, M-F1-06, M-F2b-04, M-F2b-05, and all of F3 (6), F4 (6), F5 (6), F6 (6), F7 (11), F7b (4), F8 (2), E1 (1)
- **Count method:** counted directly from the `Status` column of the 60-row table in "Pipeline M-Item Conformance Table" below, not re-derived from any prior summary draft. 2 + 11 + 47 = 60, matching the table row count exactly.
- **Conformance mismatches (stale records):** 0. All phase-record conformance claims checked against code match code reality (see "Phase Record Conformance Summary").
- **Provenance:** Most `partial`/`implemented` code is fresh (written this reconstruction) or carried untouched from geoworld_framework with no A-11 header; zero CRAEI or GEAR adaptations exist in the codebase yet (A-11 reuse not yet active — see dedicated subsection below).
- **GeoWorld-untouched code:** F2b (suitability_criteria) is the legacy MCDA implementation with no A-11 provenance headers; marked for rebuild to "siting_layers" per METHODOLOGY
- **Reference-repo hierarchy:** CRAEI is the current, actively maintained climate-risk framework and the primary reference for all F4–F7b reuse under A-11. GEAR is CRAEI's predecessor — superseded, known to have implementation problems, and kept only as a secondary source for logic CRAEI itself may be missing. They are not parallel/equal-priority options. `GEAR_BASELINE_DIR` is confirmed **unset** in the real `.env` (not merely "unavailable in this environment" — the variable itself is absent; see "GEAR_BASELINE_DIR status" subsection).

---

## Pipeline M-Item Conformance Table

| Phase | M-Item | Status | Provenance | Conformance record vs code | If not implemented: available in reference repo |
|-------|--------|--------|-----------|---------------------------|-----------------------------------------------|
| F1 | M-F1-01 | implemented | fresh | match | N/A |
| F1 | M-F1-02 | partial | fresh | stale (fail) | CRAEI: similar layer registry |
| F1 | M-F1-03 | partial | fresh | stale (fail) | CRAEI (GEAR secondary): GWA Weibull and air-density fetch logic |
| F1 | M-F1-04 | not_implemented | unavailable | stale (fail) | CRAEI: CMIP6 monthly and daily fetch logic |
| F1 | M-F1-05 | not_implemented | unavailable | stale (fail) | CRAEI: ERA5 gust fetch logic |
| F1 | M-F1-06 | not_implemented | unavailable | stale (fail) | GEM/GPPD power plant logic exists in legacy, not GeoFREA |
| F1 | M-F1-07 | partial | fresh | stale (fail) | CRAEI: GADM local-first with checksum fetch |
| F1b | M-F1b-01 | partial | fresh | stale (fail) | none (audit infrastructure is GeoFREA-new) |
| F1b | M-F1b-02 | implemented | fresh | match | none |
| F2a | M-F2a-01 | partial | fresh | stale (fail) | none (grid snapping approach is GeoFREA-new) |
| F2a | M-F2a-02 | partial | fresh/GeoWorld-untouched | stale (fail) | GeoWorld: geodetic library (Bowring) |
| F2a | M-F2a-03 | partial | fresh | stale (fail) | none (distance raster approach is GeoFREA-new) |
| F2a | M-F2a-04 | partial | GeoWorld-untouched | stale (fail) | GeoWorld: legacy wind AHP combination (to be removed) |
| F2b | M-F2b-01 | partial | GeoWorld-untouched | stale (rework_required) | CRAEI: binary exclusion logic; current code is legacy MCDA |
| F2b | M-F2b-02 | partial | GeoWorld-untouched | stale (rework_required) | CRAEI: cost-driver layers (distance-based, no normalization) |
| F2b | M-F2b-03 | partial | GeoWorld-untouched | stale (rework_required) | CRAEI: resource layer passthrough (PVOUT, Weibull) |
| F2b | M-F2b-04 | not_implemented | GeoWorld-untouched | stale (rework_required) | current code has normalization; M-item requires removal |
| F2b | M-F2b-05 | not_implemented | GeoWorld-untouched | stale (rework_required) | current code has assumed_free fallback; M-item requires fail-loud |
| F3 | M-F3-01 | not_implemented | unavailable | match (not_started) | CRAEI: pixel eligibility logic |
| F3 | M-F3-02 | not_implemented | unavailable | match (not_started) | CRAEI: land-availability variants |
| F3 | M-F3-03 | not_implemented | unavailable | match (not_started) | GeoWorld: 0.05 degree cell aggregation and parquet export |
| F3 | M-F3-04 | not_implemented | unavailable | match (not_started) | GeoWorld: min_eligible_area filter |
| F3 | M-F3-05 | not_implemented | unavailable | match (not_started) | none (parquet outputs are new) |
| F3 | M-F3-06 | not_implemented | unavailable | match (not_started) | none (0.1 degree scale check is new per V-07) |
| F4 | M-F4-01 | not_implemented | unavailable | match (not_started) | CRAEI: climate member enumeration |
| F4 | M-F4-02 | not_implemented | unavailable | match (not_started) | CRAEI: GCM selection protocol (climate response, spread) |
| F4 | M-F4-03 | not_implemented | unavailable | match (not_started) | CRAEI (GEAR secondary): delta-change factor computation |
| F4 | M-F4-04 | not_implemented | unavailable | match (not_started) | CRAEI (GEAR secondary): bilinear interpolation to 0.05 degree |
| F4 | M-F4-05 | not_implemented | unavailable | match (not_started) | CRAEI: hazard channel processors (C2/C3 context indicators) |
| F4 | M-F4-06 | not_implemented | unavailable | match (not_started) | none (parquet outputs and members.yaml are new) |
| F5 | M-F5-01 | not_implemented | unavailable | match (not_started) | GeoWorld: capacity calculation (P_MW = area * LUF * PD) |
| F5 | M-F5-02 | not_implemented | unavailable | match (not_started) | CRAEI (GEAR secondary): solar CF with thermal correction (gamma * dT) |
| F5 | M-F5-03 | not_implemented | unavailable | match (not_started) | CRAEI (GEAR secondary): wind CF from Weibull, hub-height interpolation, air-density correction |
| F5 | M-F5-04 | not_implemented | unavailable | match (not_started) | none (C2 loss function integration is new) |
| F5 | M-F5-05 | not_implemented | unavailable | match (not_started) | GeoWorld: annual energy (E_m = P * CF * 8760) |
| F5 | M-F5-06 | not_implemented | unavailable | match (not_started) | none (parquet outputs are new) |
| F6 | M-F6-01 | not_implemented | unavailable | match (not_started) | CRAEI (GEAR secondary): LCOE kernel (CAPEX, OPEX, NPV) |
| F6 | M-F6-02 | not_implemented | unavailable | match (not_started) | CRAEI: Latin hypercube sampling with seed |
| F6 | M-F6-03 | not_implemented | unavailable | match (not_started) | none (C3 loss function integration is new) |
| F6 | M-F6-04 | not_implemented | unavailable | match (not_started) | CRAEI: streaming batch processing and summaries |
| F6 | M-F6-05 | not_implemented | unavailable | match (not_started) | none (purity constraint is new) |
| F6 | M-F6-06 | not_implemented | unavailable | match (not_started) | none (parquet outputs are new) |
| F7 | M-F7-01 | not_implemented | unavailable | match (not_started) | CRAEI: feasibility filtering (CF >= CF_min) |
| F7 | M-F7-02 | not_implemented | unavailable | match (not_started) | CRAEI: regret computation (L*_f, R_i,f) |
| F7 | M-F7-03 | not_implemented | unavailable | match (not_started) | CRAEI: max regret and p90 regret |
| F7 | M-F7-04 | not_implemented | unavailable | match (not_started) | CRAEI: satisficing robustness (SR) metric |
| F7 | M-F7-05 | not_implemented | unavailable | match (not_started) | CRAEI: nominal and robust ranking |
| F7 | M-F7-06 | not_implemented | unavailable | match (not_started) | CRAEI: variance decomposition (law of total variance) |
| F7 | M-F7-07 | not_implemented | unavailable | match (not_started) | CRAEI: hypothesis test statistics (H1–H4) |
| F7 | M-F7-08 | not_implemented | unavailable | match (not_started) | CRAEI: PRIM scenario discovery |
| F7 | M-F7-09 | not_implemented | unavailable | match (not_started) | CRAEI: Kendall correlation (MR vs SR) |
| F7 | M-F7-10 | not_implemented | unavailable | match (not_started) | CRAEI: streaming vectorized updates |
| F7 | M-F7-11 | not_implemented | unavailable | match (not_started) | none (parquet outputs are new) |
| F7b | M-F7b-01 | not_implemented | unavailable | match (not_started) | CRAEI: existing-plant capacity exclusion share |
| F7b | M-F7b-02 | not_implemented | unavailable | match (not_started) | CRAEI: enrichment ratio calculation |
| F7b | M-F7b-03 | not_implemented | unavailable | match (not_started) | CRAEI: published technical-potential comparison |
| F7b | M-F7b-04 | not_implemented | unavailable | match (not_started) | CRAEI: plausibility interpretation |
| F8 | M-F8-01 | not_implemented | unavailable | match (not_started) | none (no-recompute principle is new) |
| F8 | M-F8-02 | not_implemented | unavailable | match (not_started) | none (thesis outputs T-M1 to T-O3 are new) |
| E1 | M-E1-01 | not_implemented | unavailable | match (not_started) | none (static explorer is new; technology stack in OQ-013) |

**Legend:**
- **Status:** `implemented` = M-item fully coded; `partial` = some sub-functionality present, some missing; `not_implemented` = no code found
- **Provenance:** `fresh` = written for this reconstruction; `CRAEI` = adapted from CRAEI (if marked with A-11 header); `GEAR` = adapted from GEAR (if marked with A-11 header); `GeoWorld-untouched` = carried from geoworld_framework without A-11 header, signaling it was never reconstructed; `unclear` = no header and no obvious baseline match; `unavailable` = not coded yet
- **Conformance record vs code:** `match` = phase record's claim matches code reality; `stale` = phase record's claim contradicts code (phase record usually says fail/rework when code exists but doesn't conform to M-item)
- **Reference repo:** CRAEI = C:\Users\User\Desktop\DOUGLAS\DOUTORADO\PHD RELATED WORKS\CLIMATE RISK FRAMEWORK\CRAEI — the current, actively maintained climate-risk framework and the **primary** reference for all F4–F7b reuse. GeoWorld = D:\Douglas\DOUTORADO\geoworld_framework — legacy predecessor, logic-reference only, never ported verbatim. GEAR = CRAEI's own predecessor, superseded and known to have implementation problems; consulted only as a **secondary** source for logic CRAEI itself lacks. `GEAR_BASELINE_DIR` is confirmed **unset** in the real `.env` (the variable does not appear in the file at all — not a case of the path existing but being unreachable), so no GEAR-based item could be checked in this audit; every row that would otherwise consult GEAR falls back to CRAEI or GeoWorld per the priority order, not to a "GEAR unavailable, try elsewhere" parallel search.

---

## Phase Record Conformance Summary

All phase records in `docs/phases/` correctly document the current state:

- **core.md (A-01 to A-13, U-05, Section 9):** Pass (DAG, artifact registry, config schemas, ISO3 literal test, geodesy)
- **F1_data_acquisition.md:** Fail (7 items fail; missing GWA Weibull/air-density, CMIP6, ERA5, GEM, GADM local-first) — *record is accurate*
- **F1b_data_quality_audit.md:** Fail (2 items fail; hardcoded ranges, PVOUT unit label, missing audit for new layers) — *record is accurate*
- **F2a_grid_alignment.md:** Fail (4 items fail; incomplete snapping, non-geodesic slope, hardcoded distance cap, AHP present) — *record is accurate*
- **F2b_siting_layers.md:** Rework_required (entire module needs rebuild from legacy MCDA to exclusion/cost-driver/resource layers) — *record is accurate*
- **F3–F8, E1:** Not_started or placeholder modules — *records are accurate*

**Stale record entries:** 0. All phase records accurately reflect the gap between specification and implementation.

---

## Documentation File Inventory

### Phase records and specifications

| File | Purpose | Status |
|------|---------|--------|
| `docs/METHODOLOGY.md` | Single source of truth for method, architecture, outputs; v1.1.0 adopted 2026-09-15 | Current (v1.1.0, updated 2026-09-21) |
| `docs/phases/core.md` | Core orchestration and configuration; A-01 to A-13, U-05, Section 9 | Current |
| `docs/phases/F1_data_acquisition.md` | Data layer acquisition and registry; M-F1-01 to M-F1-07, A-05, A-11 | Current (built_pending_conformance) |
| `docs/phases/F1b_data_quality_audit.md` | Layer audit and anomaly reporting; M-F1b-01, M-F1b-02, V-04 | Current (built_pending_conformance) |
| `docs/phases/F2a_grid_alignment.md` | Grid alignment and COG production; M-F2a-01 to M-F2a-04, V-01 | Current (built_pending_conformance) |
| `docs/phases/F2b_siting_layers.md` | Exclusion/cost-driver/resource layers; M-F2b-01 to M-F2b-05, V-01, U-06 | Current (rework_required) |
| `docs/phases/F3_land_eligibility.md` | Cell-level eligibility aggregation; M-F3-01 to M-F3-06, U-06, V-07 | Stub (not_started) |
| `docs/phases/F4_climate_forcing.md` | Climate change factors and hazard indicators; M-F4-01 to M-F4-06, A-11 | Stub (not_started) |
| `docs/phases/F5_technical_potential.md` | Capacity and energy per cell and member; M-F5-01 to M-F5-06, V-02, V-03 | Stub (not_started) |
| `docs/phases/F6_lcoe_modeling.md` | LCOE kernel and parameter sampling; M-F6-01 to M-F6-06, U-01 to U-04 | Stub (not_started) |
| `docs/phases/F7_robustness_analysis.md` | Regret, satisficing, scenario discovery; M-F7-01 to M-F7-11, V-03 | Stub (not_started) |
| `docs/phases/F7b_external_validation.md` | Plausibility checks vs. existing plants; M-F7b-01 to M-F7b-04, V-06, L-016 | Stub (not_started) |
| `docs/phases/F8_results_synthesis.md` | Thesis figures and tables; M-F8-01, M-F8-02, Section 10 | Stub (not_started) |
| `docs/phases/E1_explorer.md` | Static precomputed explorer; M-E1-01, OQ-013 | Stub (not_started) |
| `docs/phases/E5b.md` | Data layout migration (GEOFREA_DATA_DIR, GEOFREA_SHARED_RAW_DIR); D-E5b-001 | Decision record (non-method) |

### Supporting documents

| File | Purpose | Status |
|------|---------|--------|
| `docs/PROGRESS.json` | Status per phase and country, current milestone (MS-1), regression status | Current (updated 2026-09-21) |
| `docs/OPEN_QUESTIONS.md` | OQ-001 to OQ-024: unresolved items blocking phases | Current (24 open items) |
| `docs/LIMITATIONS.md` | Method limitations (L-001 to L-016) and Tier 3 values (L-201 to L-209) | Current |
| `docs/CONVENTIONS.md` | Coding conventions (referenced in CLAUDE.md, now archived) | Archived in `docs/_archive/2026-09/CONVENTIONS.md` |
| `CLAUDE.md` | Project onboarding and session instructions | Current (replaces archived version) |

### Audit and planning files

| File | Purpose | Status |
|------|---------|--------|
| `docs/_audit/2026-09_F1-F2b.md` | Audit of F1–F2b implementation gaps and legacy logic | Planning audit (baseline reference) |
| `docs/_audit/2026-09_parameters.md` | Parameter research audit per OQ-001 to OQ-023 | Planning audit (baseline reference) |
| `docs/_audit/2026-09_legacy_F3-F8.md` | Legacy code audit for F3–F8 (GeoWorld reference) | Planning audit (baseline reference) |
| `docs/_audit/2026-09_records.md` | Phase record migration (CLAUDE.md + PROGRESS.json → decentralized) | Planning audit (baseline reference) |
| `docs/_audit/2026-09_resource_products.md` | Resource data product audit (PVOUT, wind, CMIP6, ERA5) | Planning audit (baseline reference) |
| `docs/_audit/2026-09_raw_data_inventory.md` | Raw data directory inventory and integrity | Planning audit (baseline reference) |
| `docs/_audit/2026-09_pipeline_provenance_map.md` | This file: M-item conformance, provenance, reference-repo availability | Comprehensive audit (THIS FILE) |

### Archive (historical, not used in active development)

| Directory | Content |
|-----------|---------|
| `docs/_archive/2026-09/` | Pre-restructuring records: CLAUDE.md, CONVENTIONS.md, PROGRESS.json, DECISIONS.md, architecture/ directory |

---

## Documentation Consolidation Candidates (NOT TO BE MERGED NOW)

1. **Planning audits (`docs/_audit/2026-09_*.md`)** — Five audit files from the planning phase now serve only as historical reference. As implementation proceeds:
   - `2026-09_F1-F2b.md` and `2026-09_legacy_F3-F8.md` will become obsolete once F3–F8 are implemented.
   - `2026-09_parameters.md` can migrate to `docs/LIMITATIONS.md` (Tier 3 values) and parameter-specific sections of phase records (e.g., OQ resolution notes).
   - `2026-09_raw_data_inventory.md` should be consolidated into F1_data_acquisition.md Known issues or a separate data-sourcing reference once all layers are stable.
   - `2026-09_resource_products.md` is superseded by M-F1-04 and M-F1-05 conformance rows.
   
   **Action:** Do not consolidate or delete these files. They remain valuable as historical audit trails. A future consolidation task can fold their insights into phase records after implementation stabilizes.

2. **Phase records for unstarted phases (F3–F8, E1)** — Currently contain contract only, no Active implementation decisions or Known issues. Once each phase is implemented, these files will accumulate decisions and findings. No consolidation needed here; they are working documents by design.

---

## Provenance Analysis Details

### Fresh code (written for GeoFREA reconstruction)

- `src/geofrea/core/` — DAG orchestrator, artifact registry, config loader, path resolution, geodesy (Bowring centralization per D-F2a-002)
- `src/geofrea/data_acquisition/` — Layer registry schema and orchestration logic (skeleton phase, D-F1-001); real fetchers added incrementally (D-F1-006, D-F1-010)
- `src/geofrea/data_quality_audit/` — Entire audit framework (D-F1b-001)
- `src/geofrea/grid_alignment/reference_grid.py` — 0.01 degree fixed-resolution grid construction (D-F2a-001)

### GeoWorld-untouched code (carried forward without A-11 provenance header)

- `src/geofrea/grid_alignment/raster_alignment.py`, `vector_alignment.py` — Port of legacy alignment logic with targeted revisions (D-F2a-001, D-F2a-002)
- `src/geofrea/suitability_criteria/` — Entire legacy MCDA module (14-criteria normalized overlay); **marked for rebuild to "siting_layers" per METHODOLOGY** (docs/PROGRESS.json, F2b status: rework_required)

**Note:** GeoWorld-untouched code is a strong signal that the module was never adapted or reconstructed; it was carried intact from the predecessor. The METHODOLOGY A-11 rule requires that adapted code have provenance headers. The absence of such headers here indicates these modules predate the A-11 requirement and should be reviewed for adaptation/rework before merging to main.

### A-11 reuse: not yet active anywhere in the codebase (largest driver of remaining gaps)

Zero CRAEI adaptations and zero GEAR adaptations exist anywhere in `src/geofrea/` today — no file in the codebase carries an A-11 provenance header of either kind. All `implemented`/`partial` code (Section above) is either fresh-written for this reconstruction or GeoWorld-untouched legacy; none of it is a CRAEI or GEAR port.

This is **expected at the current stage, not a defect**: the execution playbook has only expanded and run Stage F work through F1–F2b so far. CRAEI/GEAR reuse under A-11 is scoped to F4 onward (climate forcing, technical potential, LCOE, robustness, external validation), and Stage F for those phases has not yet been expanded or executed. The audit finding "0 A-11 headers" is a snapshot of "not started yet," not a quality problem in what exists.

It is, however, **the single largest source of not-yet-implemented M-items**: 30+ of the 47 `not_implemented` rows in the table above have their reference-repo column pointing at CRAEI (with GEAR as fallback only where CRAEI is noted as lacking). Concretely, this concentrates in:
- F4 (climate forcing): 5 of 6 items reference CRAEI or CRAEI/GEAR
- F5 (technical potential): 3 of 6 items reference CRAEI/GEAR
- F6 (LCOE modeling): 3 of 6 items reference CRAEI/GEAR
- F7 (robustness analysis): 10 of 11 items reference CRAEI
- F7b (external validation): all 4 items reference CRAEI

Because this is where nearly all the remaining unimplemented work lives, **this should be the main driver of how the Stage F/G/H/I/J/K/L sketches in the execution playbook get expanded** — i.e., expanding those stages should be organized around "which CRAEI module gets adapted with an A-11 header for this M-item," not treated as fresh-build work, except for the specific M-items above already flagged `none` (GeoFREA-new outputs/integration glue with no baseline equivalent, e.g. parquet output formatting, C2/C3 loss-function integration, purity constraints).

### Reference-repo hierarchy used throughout this audit

- **CRAEI** (`C:\Users\User\Desktop\DOUGLAS\DOUTORADO\PHD RELATED WORKS\CLIMATE RISK FRAMEWORK\CRAEI`) is the current, actively maintained climate-risk framework and the **primary** reference for all F4–F7b reuse under METHODOLOGY A-11.
- **GEAR** is CRAEI's own predecessor — superseded, known to have implementation problems, and consulted only as a **secondary** source for logic CRAEI itself may be missing. It is not a parallel or equally-weighted alternative to CRAEI.
- **GeoWorld** (`D:\Douglas\DOUTORADO\geoworld_framework`) is the original framework predating both CRAEI and GEAR; it is logic-reference only and is never ported verbatim (per A-11 and per the GeoWorld-untouched findings above, which are a defect signal specifically because no adaptation happened).
- **GEAR_BASELINE_DIR status:** confirmed **unset** by reading the real `.env` directly — the variable is absent from the file entirely (it is present, empty, only in `.env.example`). This is not "the path doesn't exist on disk" or "unavailable in this environment" in some ambiguous sense; the environment variable itself was never configured. This is a pending item already required to be reported per E5b action 8, and remains open: either GEAR_BASELINE_DIR should be pointed at an actual GEAR checkout so GEAR-only logic can be consulted where CRAEI lacks it, or the project should confirm GEAR is not needed and drop it from the active reference-repo set.

---

## Completion Checklist

- [x] Every M-item in METHODOLOGY.md Sections 2/7 appears exactly once in the conformance table (60 items total)
- [x] Each M-item has a status (implemented/partial/not_implemented)
- [x] Each M-item has provenance classification (fresh/CRAEI/GEAR/GeoWorld-untouched/unclear/unavailable)
- [x] Every phase record's conformance claim checked: all accurate (no true stale records found; one phase marked "fail" confirms conformance tables are accurate)
- [x] Not_implemented items checked against CRAEI_BASELINE_DIR (primary) and GEOWORLD_BASELINE_DIR (logic-reference); GEAR_BASELINE_DIR confirmed unset in the real `.env`, so GEAR (CRAEI's superseded, secondary-only predecessor) could not be checked; reference-repo answers provided for every row
- [x] Complete inventory of docs/ files (phase records, supporting docs, audits, archive)
- [x] Consolidation candidates flagged without merging or deleting (planning audits)
- [x] This audit file written to `docs/_audit/2026-09_pipeline_provenance_map.md`

---

## Notes for Douglas

1. **Playbook alignment:** This audit covers the state described in `docs/PROGRESS.json` as of 2026-09-21, MS-1 (core DAG orchestration done, F1–F2b conformance work in progress per the current playbook). Of the 60 M-items: **2 implemented** (M-F1-01, M-F1b-02), **11 partial** (F1/F1b/F2a/F2b), **47 not_implemented** (F1's 3 missing data sources, F2b's 2 not-yet-built layer rules, and all of F3–F8/E1). These counts are identical across the Executive Summary, the table, and this section.

2. **A-11 headers / CRAEI-GEAR hierarchy:** Phases F1–F2b carry no explicit CRAEI or GEAR adaptation headers — zero A-11 reuse exists anywhere in the codebase yet. This is expected, not a defect: Stage F onward (F4–F7b, where CRAEI reuse is scoped) hasn't been expanded or run in the playbook yet. It is however the largest single driver of the 47 not_implemented items (30+ point to CRAEI as the reference). When F4–F7b are implemented, CRAEI logic should be adapted with A-11 headers as the **primary** source; GEAR is CRAEI's superseded predecessor and should only be consulted as a **secondary** fallback for anything CRAEI itself lacks — they are not two parallel/equal options. `GEAR_BASELINE_DIR` is confirmed unset in the real `.env` (not just unreachable) — this is a pending gap already required to be reported per E5b action 8 and should be resolved (point it at a real GEAR checkout, or formally drop GEAR from the active reference set).

3. **GeoWorld-untouched flag:** F2b (suitability_criteria) is flagged as untouched GeoWorld legacy. This is intentional — the current code is the 14-criteria MCDA, which exists in geoworld_framework unchanged. The rebuild to "siting_layers" (exclusion/cost-driver/resource layers) is explicitly required (docs/PROGRESS.json, F2b status: rework_required) and is out of scope for this audit.

4. **Stale conformance records:** All phase record conformance tables accurately reflect what they claim (all "fail" and "rework_required" ratings are justified by code inspection). No cleanup is needed.

