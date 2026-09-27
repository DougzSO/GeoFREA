# E5b: data layout migration (GEOFREA_DATA_DIR, GEOFREA_SHARED_RAW_DIR)

## Contract

Move all GeoFREA pipeline data out of the repository into the approved
external layout (`GEOFREA_DATA_DIR`), with `GEOFREA_SHARED_RAW_DIR` read-only
and never modified. See METHODOLOGY.md A-07, A-08 and `docs/phases/core.md`
D-core-005 (`paths.py`, `StoredPath`, manifest schema 2.1) for the code side
of this migration.

## Decisions

- **D-E5b-001 — BRA (8) vs PRT (6) manifest-backup count asymmetry is real
  dev history, not a file-discovery gap.** The pre-execution dry-run
  classification of `outputs/{BRA,PRT}/manifest.json.{bak,broken,stale,pre}_*`
  found 8 files under BRA and 6 under PRT. This was independently confirmed
  on 2026-09-21 by a filesystem glob run directly against `outputs/BRA/` and
  `outputs/PRT/` (not derived from the prior dry-run report), which matched
  the classified list exactly in both countries — zero discrepancy.

  BRA has 3 backups absent from PRT:
  `manifest.json.bak_pre_cartography_20260911142321`,
  `manifest.json.broken_partial_run1`, `manifest.json.broken_partial_run2`.

  PRT has 1 backup absent from BRA:
  `manifest.json.bak_pre_orchestrator_redesign_20260921`.

  Net: BRA 8, PRT 6. This reflects real per-country development history —
  BRA accumulated a cartography-stage backup and two broken-partial-run
  recovery snapshots that PRT never needed, while PRT separately has one
  backup from an orchestrator redesign that predates the point where BRA's
  own backup sequence starts. It is not a gap in file discovery: both
  directories were enumerated with the same glob patterns
  (`manifest.json.bak_*`, `.broken_*`, `.stale_*`, `.pre_*`) and every match
  in both directories is accounted for in the E5b move plan (destination:
  `GEOFREA_DATA_DIR\logs\<ISO3>\legacy_manifests\`, never migrated to schema
  2.1, never read by code).

  No downstream effect on Tier 1-3 analysis: these are stale manifest
  snapshots from earlier manual reruns, superseded by the current
  `manifest.json` per country, and are moved (not deleted) purely for
  provenance. No LIMITATIONS.md entry is added — there is no concrete
  downstream effect on any Tier 1-3 result to declare.

## Correction (2026-09-27, playbook COMMAND F2-5 Part A item 5)

**E5b's actual scope was narrower than `docs/phases/core.md` D-core-009 later described, and this record was closed without saying so.** What E5b actually did, confirmed against the current code: move `manifest.json.{bak,broken,stale,pre}_*` backups to `logs/<ISO3>/legacy_manifests/` (D-E5b-001 above) and land the `StoredPath`/manifest-schema-2.1 portable-path migration (`docs/phases/core.md` D-core-005) — `ArtifactEntry.path` changed from a plain string to `StoredPath(root, rel)`, resolved through `core/paths.py`. That part is real, complete, and correct: `StoredPath` is live on every artifact-registration path today (`orchestrator.py::to_stored_path()`), and no manifest predating schema 2.1 is silently trusted (`LegacyManifestError`).

**What E5b never did, and never covered:** any migration of `outputs/<ISO3>/processed/` to `interim/<ISO3>/`, or of `outputs/<ISO3>/audit/` to `outputs/<ISO3>/data_quality_audit/reports/`. `docs/phases/core.md` D-core-009 ("E5b migration left old-layout directories in place alongside the new ones") assumed these were before/after pairs from a data-*layout* migration E5b performed. Call-site research (playbook COMMAND F2-5, 2026-09-27) found otherwise: `interim(iso3, layer)` (`core/paths.py`) and `outputs/<ISO3>/data_quality_audit/reports/` have **zero write call sites anywhere in `src/`, today or at any point E5b covers** — they were never the "new" side of a migration E5b performed. `outputs/<ISO3>/processed/` (`data_quality_audit/audit.py:215`, `grid_alignment/alignment.py:271,300,340-341`) and `outputs/<ISO3>/audit/` (`data_quality_audit/audit.py:678-693`) are the sole, current, deliberately-shared-by-convention locations, unrelated to E5b's `StoredPath` work. See `docs/phases/core.md`'s correction to D-core-009 for the detail and for why this record's closure was premature: it declared the migration complete on the basis of the `StoredPath` half alone, without checking whether the directory-pair question it also raised (`processed/` vs `interim/`, `audit/` vs `reports/`) was actually part of what it migrated.

## Completion status, made specific (2026-09-27, playbook COMMAND ADJ-8b)

Both halves of what "the data layout migration" could mean are now known, so the closure can be stated precisely instead of as one blanket "done":

| Half | Scope | Status |
|---|---|---|
| Portable paths (`StoredPath`, manifest schema 2.1) | `ArtifactEntry.path` as `StoredPath(root, rel)`; manifest backups moved to `logs/<ISO3>/legacy_manifests/` (D-E5b-001) | **Complete.** This is what E5b actually contracted to do (see this record's own Contract section) and it holds today, unchanged since 2026-09-21. |
| Raw-fetch layout (A-08's `raw/<source>/<ISO3\|_global>/`) | Every fetcher (`gadm.py`, `hydrosheds.py`, `wind.py`, `protected_planet.py`) writes there; the duplicate `outputs/<ISO3>/raw/` tree is gone | **Complete, but not by E5b.** Fixed later, separately (commit `c98b89b`, 2026-09-2x; confirmed by `docs/_audit/2026-09_data_state_pre_G.md`), under `docs/phases/core.md` D-core-006, not this record. Mentioned here only so "raw moved" isn't mistaken for something E5b itself did. |
| Phase-output layout (A-08's `outputs/<ISO3>/<phase>/<kind>/`) | `data_quality_audit`'s report (`outputs/<ISO3>/audit/`) and clip cache (`outputs/<ISO3>/processed/`, shared with `grid_alignment`) | **Not done, and never in scope here.** This record's Contract never named phase outputs — only "all GeoFREA pipeline data" moving out of the repository into `GEOFREA_DATA_DIR`, which these directories already satisfy (they are under `GEOFREA_DATA_DIR`, just not laid out the way A-08's `<phase>/<kind>/` pattern wants). Owned by `docs/phases/F1b_data_quality_audit.md` (report redirect), `docs/phases/F2a_grid_alignment.md` (G-3, cache redirect), `docs/phases/F2b_siting_layers.md` (H-2) — see each record's own entry, added the same day as this one.

**What made the prior "premature closure" correction non-specific:** it named the right symptom (D-core-009 over-described E5b's scope) without saying, item by item, what was actually inside E5b's own contract versus what got swept in by a later document's assumption. The table above is that item-by-item account.

## History

- 2026-09-21: D-E5b-001 recorded, closing the count asymmetry as a
  confirmed, justified decision ahead of `--execute`.
- 2026-09-27: Scope correction recorded above (playbook COMMAND F2-5) — the `StoredPath`/schema-2.1 half of this record stands unchanged; the `processed/`/`interim/` and `audit/`/`reports/` directory-pair question was never part of E5b and should not have been described as its residue.
- 2026-09-27: Completion status made specific (playbook COMMAND ADJ-8b), per-half table above.
