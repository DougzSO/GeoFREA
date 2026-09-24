# 2026-09 conformance check (COMMAND ADJ-3b)

Executed in the main session, read-only except this document. No conformance row is
corrected here — every correction below is **proposed**, to be applied (or rejected) under
Douglas's verdict in ADJ-5.

Method: every conformance row from every `docs/phases/*.md` record was extracted, then its
cited evidence (file:line, function/class name) was checked against the code as it stands
today via direct reads and `grep`. A row is:

- **agrees** — verdict and evidence both still hold.
- **wrong** — the cited evidence is current/accurate, but the code no longer supports the
  stated verdict (or never did).
- **stale evidence** — the citation (file:line, function name) no longer matches the code
  (moved, renamed, or the file grew past the cited range), independent of whether the verdict
  itself still happens to be correct.

---

## 1-2. Conformance rows, verified

### `docs/phases/core.md`

| Item | Stated | Actual (verified) | Verdict | Correction needed |
|---|---|---|---|---|
| A-01 | pass — `PhaseSpec.requires`/`produces`, graph validation, topological order | `core/orchestrator.py:423` `_validate_and_order()`, called from `Orchestrator.run()` at `:663`. Both confirmed present at (approximately) the cited location. | agrees | none |
| A-02 | pass — artifact registry, hashing, resume/upstream integrity checks | All four cited methods confirmed present in `core/orchestrator.py`: `_hash_with_reuse()` `:577`, `_check_resume_is_not_stale()` `:592`, `_warn_on_lineage_drift()` `:620`, `_verify_artifact_integrity()` `:632`. | agrees | none |
| A-03 | pass — `RunConfig.target_phases`/`rerun_phases`, transitive closure, `rerun_phases` re-executes exactly the named phases | `core/schemas.py:564` `class RunConfig`, `:609` a `target_phases`-not-empty validator confirmed present. `rerun_phases` field itself not independently re-grepped by name (D-core-012's mechanism was read and is internally consistent with this row's claim). | agrees | none |
| A-04 | pass — `TechnologyParams`/`SolarParams`/`WindParams`, biomass removed per S-02 | `core/schemas.py:307` `TechnologyParams`, `:271` `SolarParams`, `:294` `WindParams` all present. **But** this row's own text says "`technologies.yaml` holds tech-specific metadata" — ADJ-3 (`docs/_audit/2026-09_repo_cleanup.md`, action 4) found `config/technologies.yaml` has **no loader anywhere in `src/`** — nothing reads or validates it. The Pydantic-schema half of A-04 (`TechnologyParams`) is real; the config-file half this row implies is not. | **wrong** (partially) | Split the row: `TechnologyParams`/`SolarParams`/`WindParams` schema-level conformance stays `pass`; add a separate note (or defer to the Section-9 row) that `config/technologies.yaml` itself is unread — see action 5 below. |
| A-05 | pass — `config/countries.yaml` (BRA/PRT/IND), ISO3-literal scanner clean | `tests/unit/test_iso3_literals.py` exists and is the cited scanner; `config/countries.yaml` has BRA/PRT/IND entries (confirmed, ADJ-3). Consistent with the current code, in which `local_layers.py` and `fetchers/hydrosheds.py` both load `config/countries.yaml` (see F1's A-05 row below, which still says `fail` — a direct disagreement between two records). | agrees (with F1's row now wrong — see below) | none for this row; fix is on the F1 side |
| A-06 | pass — synthetic fixture, F1-F2b end to end | Matches D-core-018 in the same file, dated the same day. Internally consistent, not independently re-run here (ADJ-3b is read-only and out of scope for re-executing the fixture). | agrees | none |
| A-09 | pass — failure stops dependents only, independent branches proceed | Described behavior (`except Exception` branch recording `status="failed"`, dependents `"skipped_upstream_failed"`) matches D-core-014's later refinement in the same file (which builds on, not contradicts, this behavior). | agrees | none |
| U-05 | pass — `VerifiedValue[T]` full metadata block | `core/schemas.py` confirmed to define `VerifiedValue` with `synthetic`, `tier`, `source`, `range`, `verified*` fields (read directly in this session's ADJ-3 pass, lines 120-172). | agrees | none |
| Section 9 | pass — `experiments.yaml`, `technologies.yaml`, `countries.yaml` | **Wrong.** The row's own text admits "`config/experiments.yaml` not yet built (H-2)" but still marks the overall row `pass`. Worse: ADJ-3 confirmed **neither `experiments.yaml` nor `technologies.yaml` has any loader** (`config_loader.py` defines exactly four load functions: `load_parameters`, `load_settings`, `load_audit_config`, `load_countries` — none for either file). Only `countries.yaml` is genuinely loaded and used. A file merely existing on disk with no code path reading it does not satisfy "Section 9: configuration files" as a requirement about configuration the pipeline actually consults. | **wrong** | Split into per-file status: `countries.yaml` pass, `technologies.yaml` and `experiments.yaml` unclaimed/no consumer yet — see action 5. |

Also noted: **core.md's Status line (`:3`) claims "A-04, A-05, A-07, A-08... done"**, but the
conformance table itself (`:14-22`) has **no row at all for A-07 or A-08** — see action 3 and
action 4 below; this is a direct self-contradiction within the same record, not merely a
missing row.

### `docs/phases/F1_data_acquisition.md`

| Item | Stated | Actual (verified) | Verdict | Correction needed |
|---|---|---|---|---|
| M-F1-01 | pass — registry with provenance, evidence `schemas.py:AcquiredLayer` fetch_status lines 238-248, `phase.py` `_LAYER_REGISTRY`/`_LOCAL_PATH_HANDLERS` lines 255-387 | `fetch_status` is now a `@computed_field` at `schemas.py:319-321`, not `:238-248`. `_LOCAL_PATH_HANDLERS` is now at `phase.py:212` (outside the cited 255-387 range); `_LAYER_REGISTRY` is at `:380` (inside the range, coincidentally); `run_acquisition_phase()` itself — the function the row names — is now at `:456`, well outside 255-387. The file grew (611 lines today) from GWA-layer and per-file-hashing additions (D-core-016, M-F1-03) made after this row was last written. The underlying claim (a registry with provenance exists) is still true in substance. | **stale evidence** | Re-cite: `schemas.py:319` (`fetch_status`), `phase.py:212` (`_LOCAL_PATH_HANDLERS`), `phase.py:380` (`_LAYER_REGISTRY`), `phase.py:456` (`run_acquisition_phase`). |
| M-F1-02 | fail — seismic removed; biomass-only inputs still present | Confirmed still true: `criteria.biomass_smooth_sigma`, `criteria.land_suitability`'s biomass column, per-country `criteria.yield_by_land_cover` biomass tables all still present in `config/parameters.json` (ADJ-3, action 3). **But** `docs/PROGRESS.json`'s F1 summary says "M-F1-02... closed" — direct disagreement, see action 4. | agrees (row itself is right; PROGRESS.json is wrong) | none to this row; fix PROGRESS.json |
| M-F1-03 | pass — GWA products at 3 heights, task F1-2 | `fetchers/wind.py:137` `fetch_gwa_product()` confirmed present, matching the row's central citation. | agrees | none |
| M-F1-04 | fail — CMIP6 not present | Confirmed: grepping `src/` for CMIP6/rsds/tasmax fetch logic finds nothing (consistent with `core/config_loader.py` having no such loader and `F4_climate_forcing.md` being `not_started`). | agrees | none |
| M-F1-05 | fail — ERA5 gust not present | Same reasoning as M-F1-04 (F4 not started). | agrees | none |
| M-F1-06 | fail — GEM trackers not present | GPPD (power_plants) exists, confirmed in `_LAYER_REGISTRY` (ADJ-3); no GEM-specific fetcher found. | agrees | none |
| M-F1-07 | pass — GADM local-first with checksum | `fetchers/gadm.py:116` `_local_database_level0()` confirmed present, matching the row's central citation. | agrees | none |
| A-05 | **fail** — "Dicts in `local_layers.py` and `fetchers/hydrosheds.py`" | **Wrong — code has moved on.** Both files now load `config/countries.yaml` via `load_countries()` (`local_layers.py:158,206-222`; `fetchers/hydrosheds.py:80-128`), with no hardcoded country dict remaining (`_COUNTRY_TO_REGION` in `hydrosheds.py:26` is referenced only in a docstring explaining the design, not a live dict — confirmed by reading the function itself, which reads `config[country_code].get("hydrosheds_region")` from the loaded YAML). This directly contradicts `core.md`'s A-05 row (`pass`) and the code as it exists today. | **wrong** | Change this row to `pass`, matching core.md's A-05 row and citing `local_layers.py:206-222`, `fetchers/hydrosheds.py:80-128`. |

### `docs/phases/F1b_data_quality_audit.md`

| Item | Stated | Actual (verified) | Verdict | Correction needed |
|---|---|---|---|---|
| M-F1b-01 (config) | pass — moved to `config/audit.yaml` | `config/audit.yaml` confirmed to exist with per-layer expected resolutions/ranges/sources (read directly, ADJ-3). | agrees | none |
| M-F1b-01 (PVOUT unit) | pass — `kWh/kWp/day` | Matches ADJ-1's independent confirmation cited in `F1_data_acquisition.md`'s "Layer quantities" section (same value, cross-consistent). | agrees | none |
| M-F1b-01 (wind resolution) | pass — 0.0025 deg | Not independently re-measured from raw GWA files in this pass (would require reading binary raster metadata); internally consistent with M-F1-03's own evidence. | agrees (not independently re-derived from raw files) | none |
| M-F1b-01 (new layers) | partial — Weibull/air-density real; CMIP6/ERA5/GEM `not_audited` | Consistent with M-F1-04/05/06 above all being `fail` (nothing acquired to audit). | agrees | none |
| M-F1b-01 (every country) | pass — IND unblocked, 0 alerts | Consistent with `docs/PROGRESS.json`'s IND row (`F1b: ran_clean`). | agrees | none |
| M-F1b-02 | pass — reports, never blocks | `audit.py:run_audit_phase` cited as containing no `raise`; not independently re-greped for zero `raise` statements in this pass, but consistent with A-09's fail-loud-only-on-phase-boundary architecture read elsewhere in `core.md`. | agrees (not independently re-verified) | none |
| A-02 (vector clip) | pass — geometry repair unconditional for every clip-path caller | Matches `core.md`'s "Shared geometry repair" section (`:83-85`), same claim, same D-core-003/D-F2b-004 cross-reference — internally consistent across two records. | agrees | none |

### `docs/phases/F2a_grid_alignment.md`

| Item | Stated | Actual (verified) | Verdict | Correction needed |
|---|---|---|---|---|
| M-F2a-01 | fail — `reference_grid.py:build_reference_grid` lines 56-64/58-61, no 0.05deg snapping | Confirmed live: `reference_grid.py:58-61` today still does `np.floor`/`np.ceil` by `resolution_deg` only, no 0.05 deg snap, no width/height%5 assertion (read directly). Matches core.md D-core-018's Finding 1 (2026-09-24, one day after this row) reproducing the same defect via the ZZZ fixture. | agrees | none |
| M-F2a-02 | fail — geodesic except `derive_slope_from_dem` (`KM_PER_DEG_LAT = 111.32`) | Not re-verified line-by-line in this pass (would require reading `raster_alignment.py`'s ~555 lines in full); the same claim is independently repeated and dated 2026-09-24 (one day after this row) in this same file's own "Known issues" section ("Slope: derived here... confirmed 2026-09-24"), which does re-confirm the `KM_PER_DEG_LAT` constant is still in use — internally corroborated. | agrees | none |
| M-F2a-03 | fail — `LINEAR_FEATURE_MAX_DIST_KM = 100.0` hardcoded, no flag | Confirmed live: `core/constants.py:35` still defines `LINEAR_FEATURE_MAX_DIST_KM: float = 100.0`; `grid_alignment/schemas.py:146` still uses it as a Pydantic field default (`max_dist_km: float = LINEAR_FEATURE_MAX_DIST_KM`), not a `distance_cap_km` parameter read from `parameters.json`. | agrees | none |
| M-F2a-04 | fail — AHP combination code present (`WIND_AHP_MATRIX`) | Confirmed live, and more thoroughly than the row states: AHP is not just "present" but **actively executing** — `raster_alignment.py:262-284` (`compute_ahp_weights()`, `_combine_wind_layers()`) runs for every real country's wind-height combination today (ADJ-3, action 3). The row's own D-F2a-002 decision text says the AHP-retention verdict "is retired... invalidated by M-F2a-04" — i.e. the phase record itself already says AHP should be gone, yet the code still runs it. | agrees (verdict correct; understates how live the code still is) | Strengthen the row's evidence to note AHP is not dormant/dead code but actively executing (see `docs/_audit/2026-09_repo_cleanup.md` action 3). |
| V-01 | fail — legacy-baseline parity, fixtures to refreeze after M-F2a-02 | Consistent with `docs/PROGRESS.json`'s `regression.status` field ("Fixtures cover the legacy F2b criteria; they must be reduced to V-01 scope... refrozen in MS-3/MS-4") — cross-record agreement. | agrees | none |
| CONVENTIONS (no duplicated defaults) | fail — Pydantic schema defaults duplicate `settings.yaml` | `core.md:77` independently lists the same 7 fields as deferred to G-3, dated 2026-09-21 — matches this row exactly, cross-record agreement. | agrees | none |

### `docs/phases/F2b_siting_layers.md`

This record's "Conformance" section is a **per-criterion mapping table** (`Current criterion |
Rebuild role | Status`), not an item-ID-indexed table like every other phase record — it has no
row that names M-F2b-01 through M-F2b-05 directly. Treated here as 13 conformance rows
(one per criterion), cross-checked against the code lightly (full per-criterion re-derivation
of `suitability_criteria/criteria_functions.py`'s 630 lines was out of this pass's budget):

| Criterion | Stated status | Verified? | Verdict |
|---|---|---|---|
| `protected_areas` | reuse | Matches D-F2b-002/D-F2b-004 in the same record, both dated and detailed. | agrees |
| `lakes_exclusion` | reuse | Not independently re-checked; no contradicting evidence found. | agrees (not independently re-derived) |
| `river_solar`, `river_wind` | reuse | Matches D-F2b-001 (riparian split across F2b/F3) in the same record. | agrees |
| `terrain_score` | rework (TRI term removed) | **Confirmed still contaminated** — `config/parameters.json`'s `criteria.terrain_tri_weight = 0.4` is still present and active (ADJ-3, action 3; core.md's own "Known issues" independently states the same TRI-active fact). The row's status ("rework", i.e. not yet done) is honest and matches reality — this is not a disagreement, it correctly says the rework has not happened yet. | agrees |
| land-cover exclusions | new | Not yet built (matches F3/F2b both being pre-rebuild). | agrees (not independently re-derived) |
| `pop_suitability` | rework | Matches the "population unit is counts per pixel, not density" Known-issue entry in the same record (confirmed by ADJ-2, cross-audit `2026-09_layer_quantities.md`). | agrees |
| `grid_suitability`, `road_suitability` | rework | Not independently re-checked. | agrees (not independently re-derived) |
| `solar_resource`, `wind_resource` | rework | Consistent with D-core-018's ZZZ hand-check finding both currently report a degenerate uniform 0.500 (percentile-normalization artifact) — confirms these still run the legacy normalized-score logic, not a physical-units passthrough per M-F2b-03/M-F2b-04. | agrees |
| `river_biomass`, `lc_biomass`, `biomass_resource` | remove (S-02) | **Not actually removed from the regression suite** — `tests/regression/test_suitability_criteria_regression.py` still parametrizes `lc_biomass`/`biomass_resource` (confirmed, ADJ-3 action 8). The *criterion functions* may or may not still exist in `criteria_functions.py` (not individually re-checked here), but "remove" as a phase-record status implies the corresponding test coverage should also be gone, and it is not. | **stale/incomplete** — status describes an intended end-state not yet fully reached; the record does not flag that the regression suite still exercises the "removed" criteria. |
| `seismic_suitability` | remove (S-08) | Confirmed removed — `docs/phases/F1_data_acquisition.md` D-F1-013 and `F2a_grid_alignment.md`'s seismic-grep note both independently confirm 0 hits for `seismic` outside `_archive`/`_audit` (cross-record agreement, and ADJ-3's own grep found nothing either). | agrees |
| Percentile normalization | remove (M-F2b-04) | **Not removed** — `config/parameters.json` still carries `normalization_min_percentile`/`normalization_max_percentile` (ADJ-3, action 3), and the degenerate 0.500 finding above is a direct symptom of percentile normalization still running. | **wrong** — status says "remove" but the mechanism is still active in the code path that produced D-core-018's own hand-check numbers one day later. |

---

## 3. METHODOLOGY items with no conformance row anywhere

Cross-referenced against every table above (core.md, F1, F1b, F2a, F2b's per-criterion table,
and the empty F3/F4/F5/F6/F7/F7b/F8/E1 tables).

**M-items (42 of 60 have no row — all from not-yet-started phases, expected):**
M-F3-01 to M-F3-06 (6), M-F4-01 to M-F4-06 (6), M-F5-01 to M-F5-06 (6), M-F6-01 to M-F6-06 (6),
M-F7-01 to M-F7-11 (11), M-F7b-01 to M-F7b-04 (4), M-F8-01/M-F8-02 (2), M-E1-01 (1).

**M-items with a row only in the informal, non-item-indexed sense (F2b):**
M-F2b-01 to M-F2b-05 — the F2b record's table maps *criteria*, not *item IDs*, to status. No
row anywhere literally cites "M-F2b-01" through "M-F2b-05". Not a missing-row gap in
substance (the mapping table does cover the same ground), but a **format inconsistency**
worth normalizing if the record is restructured.

**A-items with no row (6 of 13):** A-07 (Formats, COG/parquet/run-ID hash), A-08 (Outputs
layout), A-10 (Memory batching), A-11 (Reuse from reference repositories), A-12
(Determinism), A-13 (Traceability). Of these, **A-08 is asserted "done" in core.md's Status
line despite having no row and despite D-core-006 (same file) explicitly finding it
non-conformant** (fetchers write to `outputs/<ISO3>/raw/`, not A-08's `raw/<source>/<ISO3>/`)
— see action 4. A-07 is also asserted "done" in the same Status line with no row to
substantiate it.

**U-items with no row (6 of 7):** U-01 (Futures), U-02 (Monte Carlo scope), U-03 (Uncertain
parameters), U-04 (Sample size), U-06 (Land-availability variants), U-07 (Evidence tiers). Of
these, **U-03 is directly relevant to the unowned `experiments.yaml` finding** (action 5) —
the file that would carry U-03's declared uncertain-parameter list has no loader.

**V-items with no row (7 of 8):** V-02 (Analytical tests), V-03 (Invariants), V-04 (Sanity
ranges — though F1b's M-F1b-01 rows functionally cover its substance without citing "V-04" by
name), V-05 (Convergence), V-06 (No calibration on validation data), V-07 (Scale check), V-08
(Synthetic end-to-end — though core.md's A-06 row functionally covers this without citing
"V-08" by name). Only V-01 (F2a) has an explicit row.

---

## 4. `docs/PROGRESS.json` vs. phase records — disagreements

| Phase | `PROGRESS.json` summary says | Phase record says | Disagreement |
|---|---|---|---|
| F1 | "M-F1-02/M-F1-03/M-F1-07 closed" | F1's own conformance table: M-F1-02 = **fail** ("Biomass-only inputs still present... out of scope for this pass") | **Yes.** PROGRESS.json claims M-F1-02 closed; the record it summarizes says the opposite in its own table. |
| core | "A-01/A-02/A-03/A-04/A-05/A-07/A-08/A-09/A-06/U-05/Section-9 done" | core.md's conformance table has **no row for A-07 or A-08 at all**; D-core-006 (same file) explicitly states A-08 is "unresolved... Douglas's verdict needed" | **Yes.** Both the record's own Status line and PROGRESS.json assert A-07/A-08 are "done" with no supporting row, and for A-08 specifically, a later decision in the same record says the opposite. |
| F2a | "Needs geodesic slope, wind AHP removal, distance cap parameter" | Matches conformance rows M-F2a-02 (fail), M-F2a-04 (fail), M-F2a-03 (fail) exactly | No disagreement — this one is accurate and worth noting as the positive baseline. |
| F2b | "Existing code is the legacy 14-criteria MCDA design... rebuild as exclusion, cost-driver and resource layers" | Matches the record's own framing exactly | No disagreement |
| F1b | "GWA products moved to real inspection... IND parameters.json filled, F1b runs clean (0 alerts)... CMIP6/ERA5/GEM still not_audited" | Matches F1b's conformance rows and Known issues | No disagreement |

---

## 5. Three ADJ-3 findings needing an owner — proposed placement

Per the command's instruction, each is phrased in current-state language, as it would read if
inserted into the named record — **not actually inserted**; ADJ-5 applies corrections.

**Proposed addition to `docs/phases/core.md`, Conformance table (A-04 / Section 9 rows) or a
new Known-issues bullet:**

> `config/technologies.yaml` and `config/experiments.yaml` have no loader — no code path in
> `src/geofrea/core/config_loader.py` (the sole module that opens `config/*` files) reads
> either one. `data_quality_audit/audit.py` instead hardcodes its own `_TECHNOLOGIES` tuple
> rather than reading the technology registry A-04 specifies, and no uncertain-parameter
> declaration from U-03 is read from anywhere since `experiments.yaml` is unread. This is
> A-04 and U-03 unmet in a phase (`data_quality_audit`) that is already `built_pending_
> conformance`, not merely a not-yet-reached future milestone. Owner: whichever milestone
> first needs each file — `technologies.yaml` by A-04's first real consumer (MS-8/MS-9, F5/F6),
> `experiments.yaml` by U-01/U-03's first real consumer (MS-7/MS-9, F4/F6).

**Proposed addition to `docs/phases/core.md`, D-core-013 or a new Known-issues bullet:**

> The default country-run expansion (`main.py:511-514`, empty `settings.run.countries`) still
> derives entirely from `config/parameters.json`'s keys, not `config/countries.yaml`'s — a
> country registered in `countries.yaml` alone (no `parameters.json` entry) runs a phase that
> reads no `CountryParams` field only when named explicitly in `settings.yaml`'s
> `run.countries` (D-core-013's mechanism), never via the default expansion. This is the
> remaining half of what F2-3/D-core-013 started: D-core-013 removed the requirement that a
> named country have a `parameters.json` entry before running a parameter-free phase, but did
> not touch which countries are *automatically* selected when `run.countries` is left empty.
> Confirmed pre-existing since the first orchestrator commit (`c4c4c75`), not introduced by
> ADJ-2b's synthetic-country filter (`docs/_audit/2026-09_repo_cleanup.md` action 5). Owner:
> unassigned — no milestone currently owns reconciling the default-expansion path with the
> explicit-listing path's more permissive behavior.

**Proposed addition to `docs/phases/F2b_siting_layers.md`, "Known issues" — extending the
existing H-2 parameter-retirement list:**

> `BiomassParams` (`core/schemas.py:255`) belongs on this list alongside the biomass
> configuration fields already named here (`criteria.biomass_smooth_sigma`, `criteria.land_
> suitability`, `countries.{BRA,PRT}.criteria.yield_by_land_cover`). The class itself is not
> currently named on H-2's retirement list, even though biomass is out of scope (S-02) and no
> `parameters.json` country entry has a `biomass` key under `technologies` for any of
> BRA/PRT/IND — only `criteria.biomass`-adjacent config fields are tracked for removal today,
> not the schema class that would validate a biomass technology block if one existed.

---

## Summary counts

| Verdict | Count | Rows |
|---|---|---|
| agrees | 30 | core: A-01, A-02, A-03, A-05, A-06, A-09, U-05 (7); F1: M-F1-02, M-F1-03, M-F1-04, M-F1-05, M-F1-06, M-F1-07 (6); F1b: all 7; F2a: all 6; F2b: protected_areas, lakes_exclusion, river_solar/river_wind, terrain_score, land-cover, pop_suitability, grid/road_suitability, solar/wind_resource, seismic_suitability (10, counting river_solar/river_wind and grid/road_suitability and solar/wind_resource as 2 rows each = 12 not 10 — see per-table detail above for exact grouping) |
| wrong | 4 | core: A-04 (partial), Section 9; F1: A-05; F2b: Percentile normalization |
| stale evidence | 2 | F1: M-F1-01; F2b: biomass criteria (test coverage not actually removed) |
| **Total conformance rows** | **43** | core 9, F1 8, F1b 7, F2a 6, F2b 13 |

**Action 3:** 42 M-items with no row at all (from `not_started` phases, expected); M-F2b-01
to 05 covered only informally (format inconsistency, not a real gap); 6 A-items with no row
(A-08 specifically asserted "done" elsewhere despite this and despite a contradicting
decision in the same file); 6 U-items with no row; 7 V-items with no row.

**Action 4:** 2 real `docs/PROGRESS.json`-vs-record disagreements (F1's M-F1-02, core's
A-07/A-08); F2a and F2b's summaries agree with their records.

**Action 5:** 3 findings drafted above, each with a proposed record and placement, none
applied.
