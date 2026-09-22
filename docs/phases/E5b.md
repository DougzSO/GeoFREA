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

## History

- 2026-09-21: D-E5b-001 recorded, closing the count asymmetry as a
  confirmed, justified decision ahead of `--execute`.
