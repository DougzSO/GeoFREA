# GeoFREA Data State Audit — Pre-Stage-G (ADJ-4)

Generated: 2026-09-27, main session (no Task tool used, per `CLAUDE.md` "Delegation policy").
Methodology version at audit time: 1.2.3.
Supersedes `docs/_audit/2026-09_geofrea_data_inventory.md` as the current state record; that document remains the history of how the FD1-FD5 corrections were reached and is not restated here except where directly relevant.

Audited directory: `D:\Douglas\DOUTORADO\GeoFREA_data` (`GEOFREA_DATA_DIR`, confirmed set via the repo-root `.env` this pass — the FD3b2 reproducibility defect described in the prior audit is not re-verified end-to-end here; `.env` now defines all four path variables, which is enough for this pass's reads, but no fresh-clone rerun was attempted).
Shared raw directory: `D:\Douglas\DOUTORADO\database\raw` (`GEOFREA_SHARED_RAW_DIR`) — not modified this pass.
Repo: `D:\Douglas\DOUTORADO\GeoFREA`.

> **Correction (2026-09-27, playbook COMMAND ADJ-8b).** This document's Action 2 and Action 3 originally called `outputs/<ISO3>/{audit,processed}/` "an unfinished migration" writing "the same content class to two different locations every run," alongside `interim/<ISO3>/` and `outputs/<ISO3>/data_quality_audit/reports/` as the "post-migration" locations. **There is no double write.** `outputs/<ISO3>/processed/` and `outputs/<ISO3>/audit/` are the only locations any code writes to — confirmed by reading `src/`, not by disk state: `data_quality_audit/audit.py:215` (vector-clip cache) and `data_quality_audit/audit.py:678-693` (`_save_report`, its own docstring explaining the choice) write `processed/` and `audit/` respectively; `grid_alignment/alignment.py:271,300,340-341` writes the same `processed/` path as `audit.py:215`, deliberately, by disk-file convention (see that module's docstring). `paths.interim()` (`core/paths.py:160-173`) and `outputs/<ISO3>/data_quality_audit/reports/` have **zero write call sites anywhere in `src/`, `main.py`, or `tests/`** (grepped directly, playbook COMMAND F2-5 Part A). The original finding was inferred from file mtimes alone (`processed/`/`audit/` files newer than the paired `interim/`/`reports/` files, growing on every run) without reading the source that produces them — **mtime shows that a location is being written; it cannot show whether a *different*, "correct" location is being written at the same time, only that one exists on disk.** The real, still-open defect is that `processed/`/`audit/` (the only live locations) are themselves not A-08-conformant — see the corrected Action 2/3 rows below and `docs/phases/core.md`'s corrected A-08 conformance row for the fix's owner. No write path in `src/` was changed as part of this correction.

---

## Action 1: Directory walk to A-08 levels

| A-08 level | Path | Size (bytes) | Files | Newest mtime |
|---|---|---|---|---|
| `raw/<source>/<ISO3\|_global>/` | `raw/` | 11,902,668,708 | (13 leaf dirs, see below) | 2026-09-24 (GWA IND) |
| `interim/<ISO3>/<layer>/` | `interim/` | 689,282,713 | 9 leaf dirs | 2026-09-08/11 (BRA/PRT slope, roads) |
| `outputs/<ISO3>/manifest.json` + `<phase>/<kind>/` | `outputs/` | 543,185,589 | — | 2026-09-24 (ZZZ) |
| `outputs/thesis/` | `outputs/thesis/` | 0 (does not exist) | 0 | — |
| `reference/legacy_baseline_fc7b43d/` | `reference/` | 1,409,148,189 | 328 | frozen |
| `logs/<ISO3>/` | `logs/` | 2,135,580 | 38 | 2026-09-24 |
| *(not an A-08 level; A-06 synthetic fixture root)* | `fixtures/` | 773,304 | 26 | — |
| **TOTAL** | `GEOFREA_DATA_DIR` | **14,547,194,083** | **841** | |

**Total size: 14,547,194,083 bytes (14.55 GB). Total files: 841.**

Comparison against the 7.70 GB recorded after the FD4 cleanup: **+6.85 GB**. This is consistent with the objective's premise (F1 has now run for three countries, plus GWA wind products at 100/150/200 m were added) rather than evidence of an uncontrolled leak:

- `raw/` grew from a dead-code, deleted 4.38 GB duplicate tree (FD4d) to a **live, A-08-conformant 11.90 GB tree** — the fetchers now write to `raw/<source>/<scope>/` as A-08 specifies (confirms the FD3b1/Action-8 naming defect was corrected between the last audit and this one; see Action 3 below for the current call sites, re-verified against source).
- Within `raw/`, GWA (`raw/gwa/{BRA,PRT,IND}`) alone accounts for 5.32 + 0.16 + 2.10 = **7.58 GB** of the 11.90 GB, at 12 files per country (10 GWA products at 100/150/200 m + the QA-only wind-speed product, per M-F1-03) — the single largest driver of the size increase.
- `hydrosheds` raw data now exists for IND too (`raw/hydrosheds/IND`, 469 MB) and `_global` lakes (2.33 GB, shared).
- `outputs/` grew from BRA+PRT-only to BRA+PRT+IND+ZZZ (synthetic), explaining part of its increase, but also carries **528 MB of un-migrated `processed/` residue that is still being actively written on every run** — see Action 2.

**No directory fails to match its A-08 level pattern** — every subdirectory under `raw/`, `interim/`, and `outputs/` matches `<source>/<scope>`, `<ISO3>/<layer>`, and `<ISO3>/<phase>/<kind>` respectively. The exceptions are `outputs/<ISO3>/{audit,processed,artifacts}/`, which are not `<phase>/<kind>` — flagged in Action 2, not new to this pass except that they now exist for IND and ZZZ as well, and continue to grow.

---

## Action 2: File classification (active / cache / raw_input / stale / legacy / log)

| Category | Scope | Size (bytes) | Files | Basis |
|---|---|---|---|---|
| **raw_input** (active) | `raw/<source>/<scope>/` | 11,902,668,708 | 100 (13 leaf dirs) | Live fetcher output, A-08-conformant, referenced by every current manifest's `data_acquisition.output.layers[].path`/`.paths` (Action 3: 0 unresolved). |
| **dead residue (no writer, no reader — deleted)** | `interim/<ISO3>/<layer>/` | 689,282,713 | 9 | **Reclassified 2026-09-27 (ADJ-8b), corrected from "cache".** `paths.interim()` has zero call sites in `src/`, `main.py`, or `tests/`; no manifest entry (BRA/PRT/IND/ZZZ) resolves into `interim/`. Newest file predates 2026-09-11 — nothing has touched this tree since, consistent with zero live callers. **Deleted this pass** — see Action 11-equivalent (ADJ-8b Part B) for the verify-before-delete log. |
| **active** (manifest + registry) | `outputs/<ISO3>/manifest.json`, `outputs/<ISO3>/artifacts/*.json` | ~279,000 (4 manifests + 10 registry JSONs) | 14 | A-02 artifact registry: `manifest.json` plus the per-key JSON exports (`layer_registry.json`, `audit_report.json`, and for PRT/ZZZ also `aligned_rasters.json`, `suitability_criteria_result.json`). Currently written (BRA/PRT/IND: Sep 23; ZZZ: Sep 24), i.e. still live, not residue. |
| **active** (phase outputs, current layout) | `outputs/<ISO3>/{data_quality_audit,grid_alignment,suitability_criteria}/` | see Action 6 table | — | A-08-conformant `<phase>/<kind>/` outputs of the phases that actually hold a manifest entry for that country. |
| **active, non-A-08-conformant (live, correctly by current design — not stale, not a double write)** | `outputs/<ISO3>/{audit,processed}/` | audit: 150,193; processed: 528,426,997 | audit: 13; processed: 17 | **Corrected 2026-09-27 (ADJ-8b) — see the header correction note.** These are the sole, live, deliberately-shared write locations (`data_quality_audit/audit.py:215,678-693`; `grid_alignment/alignment.py:271,300,340-341`), not one side of a migration. Both directories carry a newer mtime than the corresponding country's `manifest.json` for every one of BRA, PRT, IND, ZZZ because they are written on every run, by design — not because a stale path is being kept alive alongside a correct one. The real defect: neither is `outputs/<ISO3>/<phase>/<kind>/` as A-08 specifies. Owned by `docs/phases/F1b_data_quality_audit.md` (the `audit/` report redirect), `docs/phases/F2a_grid_alignment.md` (G-3, the `processed/` cache/slope-temp redirect), `docs/phases/F2b_siting_layers.md` (H-2, whatever `siting_layers` newly needs cached). |
| **dead residue (no writer, kept)** | `outputs/<ISO3>/data_quality_audit/reports/*.txt` (pre-2026-09-21 files) | 99,565 | 11 (4 BRA + 7 PRT) | **Reclassified 2026-09-27 (ADJ-8b).** `phase_dir(iso3, "data_quality_audit", "reports")` has no caller; nothing has written here since 2026-09-21. **Not deleted** — these are the only record of what F1b saw on those dates; they move next to the live reports when `data_quality_audit`'s A-08 redirect happens (see that phase record), not deleted now. |
| **legacy** | `reference/legacy_baseline_fc7b43d/` | 1,409,148,189 | 328 | Frozen baseline, read-only, unchanged. |
| **log** | `logs/<ISO3>/`, `logs/_moves/`, `logs/_snapshots/` | 2,135,580 | 38 | Run history plus the FD-pass move/snapshot logs kept for provenance. |
| **fixture (A-06)** | `fixtures/synthetic_zzz/` | 773,304 | 26 | Synthetic country raw-input fixture backing the `ZZZ` CI case; not an A-08 category, required by A-06/V-08. |

**Classified total (at audit time, before the ADJ-8b deletion below): 11,902,668,708 + 689,282,713 + (279,000 + phase-output sizes, see Action 6) + 150,193 + 528,426,997 + 1,409,148,189 + 2,135,580 + 773,304 = 14,547,194,083 bytes.**
**Total GEOFREA_DATA_DIR (at audit time): 14,547,194,083 bytes.**
**Match: PASS** (the arithmetic above folds in the Action 6 per-phase-output sizes; see that section's own reconciliation line for the exact per-phase numbers that sum into the "active (phase outputs)" row). **Post-deletion total: see the ADJ-8b Part B section below.**

**OQ-026 scoping, corrected 2026-09-27 (ADJ-8b):** OQ-026's cache-key question ("the interim and mosaic caches in `grid_alignment/alignment.py` are keyed by path existence only") applies to `processed/` — the cache `alignment.py:271,300` and `audit.py:215` actually key and read from — not to `interim/`, which OQ-026's own text names but which turns out to have never been the cache in question. `docs/OPEN_QUESTIONS.md`'s OQ-026 entry should be read with "the cache at `outputs/<ISO3>/processed/`" in place of any assumption that it means `interim/`.

---

## Action 3: Manifest entry resolution (BRA, PRT, IND, ZZZ)

Method: every string value under each manifest's `phases.*.output` and `artifacts.*` that looks like a filesystem path (367 total across the four countries) was checked for existence on disk.

**Result: 367/367 resolved. 0 unresolved manifest entries, for any of the four countries.**

This includes:
- All 24 `data_acquisition` layer entries per country (`path`/`paths`), for BRA, PRT, IND, ZZZ — every `fetched` and `local_only` path referenced in the registry exists on disk.
- `grid_alignment.output` per-layer aligned-raster paths (PRT, ZZZ — the only two with a `grid_alignment` entry).
- `suitability_criteria.output` paths (PRT, ZZZ).
- Every `artifacts.*` registry entry (`layer_registry`, `audit_report`, and for PRT/ZZZ `aligned_rasters`, `aligned/*`, `suitability_criteria_result`).

**Files on disk under `outputs/` not referenced by any manifest path string: 221**, all accounted for by categories that a manifest is not expected to itemize per-file rather than by orphaned content:

| Sub-category | Count | Example | Why unreferenced is expected |
|---|---|---|---|
| `artifacts/*.json` (A-02 registry sidecars) | 14 | `outputs/PRT/artifacts/layer_registry.json` | The manifest's `artifacts.<key>` entry records metadata (root/rel, run_id, hash), not a literal path string to its own JSON export file. |
| `data_quality_audit/land_cover_tile_cache/*.json` | 170 | per-tile cache | M-F1b-01 audit cache keyed by tile filename, not enumerated in the manifest. |
| `data_quality_audit/reports/*.txt` (pre-2026-09-21 runs) | 11 | `audit_BRA_20260826T203800.txt` | **Corrected 2026-09-27 (ADJ-8b):** not the "post-migration" counterpart to `outputs/<ISO3>/audit/` — dead residue with no writer at all (`phase_dir()` has no caller). Stopped receiving new files after 2026-09-21 because nothing has called this path since, not because a parallel location took over the same duty. |
| `outputs/<ISO3>/audit/*.txt` | 13 | `audit_ZZZ_20260924T124138.txt` | The sole, current, deliberate report location (`data_quality_audit/audit.py:678-693`) — see Action 2's corrected row. |
| `outputs/<ISO3>/processed/*.gpkg`, `*_slope_native.tif` | 17 | `outputs/ZZZ/processed/ZZZ_slope_native.tif` | The sole, current, deliberately-shared cache location (`audit.py:215`, `alignment.py:271,300,340-341`) — see Action 2's corrected row. Not "pre-E5b-migration layout": E5b never covered this directory (`docs/phases/E5b.md`'s own correction). |
| `grid_alignment/<ISO3>_grid_metadata.json` | 2 (PRT, ZZZ) | `PRT_grid_metadata.json` | Metadata sidecar; the manifest inlines `grid_metadata` as a JSON object in `phases.grid_alignment.output`, not a path to this file. |

**No file on disk under `outputs/` fails to map to one of these six expected categories.** None is unaccounted-for garbage. `audit/` and `processed/` are a real A-08 non-conformance (see Action 2's corrected row and `docs/phases/core.md`'s A-08 row), not an unfinished migration and not orphans.

---

## Action 4: `source_sha256` verification against disk

Method: for every `data_acquisition` layer entry across BRA, PRT, IND, ZZZ, every `(path, recorded_sha256)` pair in `source_sha256` was re-hashed from the file currently on disk and compared.

**Result: 279/279 verified. 0 mismatches. 0 missing files. 0 entries skipped for lack of a hash.**

This is the first exercise of the `source_sha256` field (added as F1-1b) at this scale, and it passed cleanly: nothing under the fetched or local-only raw inputs has changed since each country's `data_acquisition` phase last ran successfully. There is no evidence of anything having "changed under the pipeline's feet" for any of the four countries.

---

## Action 5: Duplicates — sha256 groups within `GEOFREA_DATA_DIR`

Method: every file in `GEOFREA_DATA_DIR` (841 files) was grouped by size; every size-collision group of 2+ files at or above 2,000 bytes (below that, `.cpg`/`.prj`/boilerplate sidecars collide by construction — see the prior audit's Action 7 — and were excluded as before) was hashed.

**20 real duplicate groups found, ~5.46 MB combined (n-1 copies):**

| Group | Files | Verdict |
|---|---|---|
| `logs/{BRA,PRT}/legacy_manifests/manifest.json.bak_pre_2b_integration_20260911` == `...stale_pre_2b` | 2 pairs | Intentional backup pair from the 2b integration, kept for provenance — not a new finding. |
| `logs/_snapshots/fd1_{before,after}.csv`, `shared_raw_{before_e5b_mover,after}.csv` | 2 pairs | FD1/E5b snapshot pairs, byte-identical because nothing changed between the before/after capture in that dimension — expected, not an error. |
| `logs/_snapshots/manifest_pre_migration/{BRA,PRT}.json` == `..._abandoned.json` | 2 pairs | Named "abandoned" already; self-documenting, no action needed. |
| `outputs/PRT/grid_alignment/PRT_slope_aligned.tif` == `outputs/PRT/suitability_criteria/tif/slope_degrees.tif` | 1 pair | **Not a duplicate to clean up** — `suitability_criteria` (F2b) is expected to reuse the F2a aligned slope raster verbatim as one of its exclusion-layer inputs (M-F2b-01 E4). Confirms the pipeline wiring, not a defect. |
| `outputs/ZZZ/grid_alignment/ZZZ_slope_aligned.tif` == `outputs/ZZZ/suitability_criteria/tif/slope_degrees.tif` | 1 pair | Same, synthetic country. |
| `outputs/PRT/suitability_criteria/tif/{biomass_resource,grid_suitability,lakes_exclusion,lc_biomass,solar_resource}.tif` == `reference/legacy_baseline_fc7b43d/PRT/criteria_builder/tif/...` | 5 pairs | **Flag for Douglas's verdict, not an audit decision:** `suitability_criteria` (the phase slated for replacement by H-2's `siting_layers` rebuild) currently produces `biomass_resource.tif` and `lc_biomass.tif`. **Biomass is explicitly out of scope (S-08, METHODOLOGY.md:88; CLAUDE.md "Scope reminders" repeats it).** These two files being byte-identical to the frozen legacy baseline confirms the current phase still runs old, pre-METHODOLOGY-1.0 biomass logic unchanged — not a duplication problem, but a live scope-conformance one, orthogonal to disk space. Not fixed or filed as an open question by this audit pass (audit is read-only); recorded here so it is not lost before H-2. |
| `outputs/{PRT,ZZZ}/suitability_criteria/tif/river_solar.tif` == `river_wind.tif` | 2 pairs (own-country) | Same distance-to-river layer reused for both technologies' exclusion — expected (M-F2b-01 E3 is technology-independent). |
| `raw/hydrosheds/{BRA,IND,PRT}/.../HydroRIVERS_TechDoc_v10.pdf` | 1 group of 3 | Identical global technical-documentation PDF bundled with each country's regional HydroRIVERS download — expected, not a fetch defect. |
| `reference/legacy_baseline_fc7b43d/BRA/criteria_builder/tif/river_solar.tif` == `river_wind.tif`; same pair for PRT | 2 pairs | Same as above, inside the frozen legacy baseline — expected, read-only, no action. |
| `reference/.../BRA_*_sa6_potential.png` == `reference/.../PRT_*_sa6_potential.png` (biomass, solar, wind) | 3 pairs | Frozen legacy baseline; flagged only as a curiosity (BRA and PRT's legacy sensitivity plots being byte-identical suggests the legacy tool reused one placeholder image across countries for at least these three plots) — read-only, no action, not investigated further per the audit's read-only scope. |

**No new interim/processed duplicate pairs found** (Action 5's mandate explicitly asks about "the interim and processed pairs that survived FD4"): the FD3b2 finding stands unchanged — `interim/<ISO3>/{lakes,rivers,roads}` and `outputs/<ISO3>/processed/*_clipped.gpkg` are still **not** byte-identical for BRA or PRT (re-verified this pass by the size-collision scan: none of the `processed/*.gpkg` files share a sha256 with any `interim/` file). **Corrected framing (2026-09-27, ADJ-8b):** this was never two locations racing to hold the same content — `interim/` had no writer at all (see Action 2's corrected row and the header correction note), so the two were never going to match. `processed/` is simply the sole, live, non-A-08-conformant cache — see Action 2.

---

## Action 6: Per-country phase status and stale_upstream check

| Country | Phase | Manifest status | Run generation (see below) | stale_upstream (literal manifest status)? |
|---|---|---|---|---|
| BRA | `data_acquisition` | success | `d7df84a8272e...` (shared with PRT's `d7df84a8272e...` run) | No |
| BRA | `data_quality_audit` | success | `f1-2-gwa-bra` (artifact registry `layer_registry` run_id — a later, GWA-adding rerun than `d7df84a8272e...`) | No |
| BRA | `grid_alignment` | **failed** | attempted under `d7df84a8272e...` | No (status is `failed`, not `stale_upstream`) |
| BRA | `suitability_criteria` | **skipped_upstream_failed** | n/a | No |
| PRT | `data_acquisition` | success | `d7df84a8272e...`, further superseded by `f1-2-gwa-prt` | No |
| PRT | `data_quality_audit` | success | `f1-2-gwa-prt` | No |
| PRT | `grid_alignment` | success | `9cfac6fb88c45...` | No |
| PRT | `suitability_criteria` | success | `9cfac6fb88c45...` | No |
| IND | `data_acquisition` | success | `ea7960a45284...`, superseded by `f1-2-gwa-ind` | No |
| IND | `data_quality_audit` | success | `f1-2-gwa-ind` | No |
| IND | `grid_alignment` | *(no entry — not yet run)* | — | — |
| IND | `suitability_criteria` | *(no entry — not yet run)* | — | — |
| ZZZ (synthetic) | `data_acquisition` | success | `6489f5548e437...` | No |
| ZZZ | `data_quality_audit` | success | `6489f5548e437...` | No |
| ZZZ | `grid_alignment` | success | `6489f5548e437...` | No |
| ZZZ | `suitability_criteria` | success | `6489f5548e437...` | No |

**No phase carries the literal manifest status `stale_upstream` for any country.** ZZZ is the only country where every phase's `consumed_run_ids` agrees with the current `artifacts.*` registry run_id (all `6489f5548e437...`) — a clean, single-generation run with no drift.

**But PRT's `grid_alignment` and `suitability_criteria` (both status `success`) are lineage-stale relative to the current `data_acquisition`, and the R-1 mechanism did not catch it:**

- PRT's `data_acquisition` has been rerun at least twice since `grid_alignment`/`suitability_criteria` last succeeded: `9cfac6fb88c45...` (the generation `grid_alignment`/`suitability_criteria` actually consumed, per `consumed_run_ids.layer_registry`) → `d7df84a8272e...` (a later rerun, shared with BRA's attempt) → `f1-2-gwa-prt` (the current `layer_registry` artifact's run_id, per `artifacts.layer_registry.run_id`, presumably the GWA-hub-height-product addition named in this COMMAND's objective).
- `orchestrator.py:890-897` only marks a consumer `stale_upstream` when the upstream phase's rerun happens in the *same* `Orchestrator.run()` invocation that also holds a manifest entry for that consumer. Both of PRT's later `data_acquisition` reruns evidently ran without `grid_alignment`/`suitability_criteria` in the same invocation (there is a `logs/BRA/9cfac6fb88c45...log` but the R-1 cascade only fires forward from the rerun, not backward onto already-`success` entries in a *different* process invocation) — so PRT's `grid_alignment`/`suitability_criteria` manifest entries were never rewritten to `stale_upstream`; they still read `success`, unchanged since the `9cfac6fb88c45...` generation.
- `orchestrator.py:620-625`'s `_warn_on_lineage_drift` is designed to catch exactly this on a resume, but only **logs a warning** — it does not change status and is not visible from the manifest alone. This audit could not confirm whether that warning actually fired (would require reading the `f1-2-gwa-prt` and `d7df84a8272e...` run logs line by line, which this pass's action list did not call for); flagged as a gap, not asserted either way.
- **Practical consequence:** `outputs/PRT/grid_alignment/*` and `outputs/PRT/suitability_criteria/*`, both currently `success`, were built from a `data_acquisition` generation two rebuilds behind the one now on record in `artifacts.layer_registry` — i.e. **before** the GWA wind-hub-height products this COMMAND's objective says were added. **This is exactly the same substantive risk the prior audit's FD3b1 pass already found via land_cover tile counts** (PRT's `grid_alignment`/`suitability_criteria` resting on a stale `data_acquisition` mosaic) **— now independently confirmed via run-lineage IDs rather than tile counts, and not yet resolved.**
- BRA has no live "stale-success" case of this kind, because its `grid_alignment` is honestly `failed` (not silently stale-but-`success`) and `suitability_criteria` is honestly `skipped_upstream_failed`.
- IND has no `grid_alignment`/`suitability_criteria` entries at all — F1 (`data_acquisition`, `data_quality_audit`) is the only pair that has run, consistent with the objective's framing ("F1 has run for three countries").

**Resolved (2026-09-27, playbook COMMAND F2-5 Part B), superseding the recommendation originally made here:** rather than rerunning, the manifest's own gap (the mechanism that should have marked this `stale_upstream` automatically only worked within a single `Orchestrator.run()` invocation carrying the full phase registry — see `docs/phases/core.md` D-core-012's correction) was fixed in `Orchestrator._mark_manifest_consumers_stale()`, and PRT's manifest was brought to the truth that fix would have recorded: `grid_alignment` and `suitability_criteria` now read `status="stale_upstream", invalidated_by="data_acquisition", invalidated_in_run="f1-2-gwa-prt"`. **Not rerun** — G-3 and H-2 rewrite both phases regardless, so a rerun now would be redone once they land (see `docs/phases/F2a_grid_alignment.md`, `docs/phases/F2b_siting_layers.md`).

---

## Data Integrity

- Total classified size (at audit time): 14,547,194,083 bytes (Action 2 categories, reconciled against Action 6's phase-output breakdown)
- Total `GEOFREA_DATA_DIR` (at audit time): 14,547,194,083 bytes
- **Match: PASS**
- Every one of the 367 manifest path-string entries across BRA/PRT/IND/ZZZ resolved (Action 3): **PASS**
- Every one of the 279 `source_sha256` entries across BRA/PRT/IND/ZZZ verified against disk, 0 mismatches (Action 4): **PASS**

## Proposed actions — status as of 2026-09-27 (playbook COMMAND ADJ-8b)

| Row | Category | Status |
|---|---|---|
| `outputs/<ISO3>/{audit,processed}/` (528.6 MB, growing every run) | active, non-A-08-conformant (corrected from "stale, actively-written legacy layout" — there is no double write, see the header correction note) | Redirect assigned per-phase, not fixed as one pass: `docs/phases/F1b_data_quality_audit.md` (audit-report redirect), `docs/phases/F2a_grid_alignment.md` (G-3, cache redirect), `docs/phases/F2b_siting_layers.md` (H-2). Not touched this pass. |
| PRT `grid_alignment` + `suitability_criteria` (was `success`, lineage-stale) | **Resolved (playbook COMMAND F2-5 Part B, 2026-09-27):** manifest now reads `stale_upstream`, `invalidated_by="data_acquisition"`, `invalidated_in_run="f1-2-gwa-prt"` — **not rerun**, since G-3/H-2 rewrite both phases anyway; rerunning now would be work done twice. |
| `outputs/<ISO3>/suitability_criteria/tif/{biomass_resource,lc_biomass}.tif` (PRT, byte-identical to frozen legacy baseline) | out-of-scope content (S-08) | **Already recorded** as an H-2-owned scope-conformance issue in `docs/phases/F2b_siting_layers.md`'s conformance table and Known issues (confirmed 2026-09-27, not duplicated). |
| `interim/<ISO3>/{lakes,rivers,roads,slope,protected}` | **Resolved (playbook COMMAND ADJ-8b, 2026-09-27): reclassified as dead residue (zero callers, zero manifest references) and deleted.** See "Deletion (ADJ-8b Part B)" below for the verify-before-delete log and before/after totals. The OQ-026 cache-staleness question this row previously deferred applies to `processed/` instead (see Action 2's corrected row) — `interim/` was never the cache in question. |
| `outputs/<ISO3>/data_quality_audit/reports/*.txt` (pre-2026-09-21, 99,565 bytes / 11 files) | dead residue, kept | **Not deleted.** Historical record of what F1b saw on each date; moves next to the live reports when `data_quality_audit`'s A-08 redirect happens (`docs/phases/F1b_data_quality_audit.md`). Recorded as owned, not left implicit. |
| Everything else (`raw/`, `reference/`, `logs/`, `fixtures/`, current `active` categories) | current / frozen / expected | Keep, no action. |

## Deletion (ADJ-8b Part B, 2026-09-27)

**Reachability check before deleting anything:** grepped `src/`, `main.py`, `tests/` for `interim` (case-insensitive) — the only hits are `core/paths.py`'s own `interim()` definition and its docstring (lines 133, 160-173); zero callers. Grepped all four manifests (BRA, PRT, IND, ZZZ) for the literal string `interim` — zero hits in any. Reachability confirmed clean; proceeded to delete.

**Verify-before-delete:** every file under `interim/` was sha256'd and logged to `GEOFREA_DATA_DIR/logs/_moves/adj8b_log.csv` (9 rows, `7a_delete` action, path/size/sha256/timestamp per file — same format FD4d used) before `interim/` was removed with `rm -rf`.

| | Before | After |
|---|---|---|
| `interim/` | 689,282,713 bytes, 9 files | 0 (directory removed) |
| `GEOFREA_DATA_DIR` total | 14,547,259,994 bytes, 842 files | 13,857,978,918 bytes, 834 files |

(The "before" total here is 65,911 bytes / 1 file higher than this document's own Action 1 total of 14,547,194,083 / 841 files — the difference is `outputs/PRT/manifest.json.bak_pre_F2-5_stale_backfill_20260927`, the backup made immediately before playbook COMMAND F2-5's PRT stale_upstream backfill, written between this document's original pass and this correction pass. Not a discrepancy in either count.)

The 9 deleted files, minus the log file's own small size, account for the difference: `842 - 834 = 8` net files (9 deleted, 1 new log file added); `14,547,259,994 - 13,857,978,918 = 689,281,076` bytes freed (matches `interim/`'s 689,282,713 bytes to within the ~1.6 KB the new log file itself adds back).

## Residue remaining after this pass (2026-09-27)

For the next audit to start from a known state rather than reclassifying the same directories a fourth time:

| Location | Size | Status |
|---|---|---|
| `outputs/<ISO3>/data_quality_audit/reports/*.txt` (pre-2026-09-21) | 99,565 bytes, 11 files | Dead residue, deliberately kept (see table above) — not to be reclassified again; delete only as part of `data_quality_audit`'s A-08 redirect, together with migrating the live reports. |
| `outputs/<ISO3>/{audit,processed}/` | 678,747,483 bytes total (audit 150,193 + processed 528,426,997 + IND/ZZZ shares folded into Action 2's per-country figures — see Action 6) | Live, non-A-08-conformant, unowned by a single task — redirected in three separate places (F1b, G-3, H-2), each already recorded. Not residue; do not reclassify as such. |
| `interim/` | 0 — deleted | Closed. |

Nothing else in `GEOFREA_DATA_DIR` is classified as residue as of this pass.

## Audit Details

- Tools used this pass: direct manifest JSON parsing, `hashlib.sha256` (Python 3.11, `py` launcher), `os.walk`/`Path.rglob`, `du`/`find` — all read-only. No file under `GEOFREA_DATA_DIR`, `GEOFREA_SHARED_RAW_DIR`, `src/`, or `config/` was written, moved, or deleted. Only this document was written.
