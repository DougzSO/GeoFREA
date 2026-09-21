# core: orchestration, configuration, shared utilities

Status: `rework_required`
Methodology items: A-01, A-02, A-03, A-04, A-05, A-06, A-07, A-09, A-10, A-12, A-13, U-05, Section 9

## Contract

Provides to all phases: DAG orchestrator, artifact registry and manifest, configuration loading and validation (`parameters.json`, `technologies.yaml`, `countries.yaml`, `experiments.yaml`, `settings.yaml`), geodesy utilities, raster and vector I/O helpers, HTTP retry.

## Conformance

| Item | Requirement | Current state (from `docs/_audit/2026-09_F1-F2b.md` section 8) | Status |
|---|---|---|---|
| A-01 | `requires`/`produces`, topological order, startup validation | `PhaseSpec.requires`/`produces` (`core/orchestrator.py::PhaseSpec`); graph validation and topological sort in `core/orchestrator.py::_validate_and_order()`, called from `Orchestrator.run()`. Tests: `tests/unit/test_orchestrator.py::test_shuffled_spec_list_produces_the_same_order`, `::test_missing_producer_raises`, `::test_dependency_cycle_raises`, `::test_duplicate_producer_raises` | pass |
| A-02 | Artifact registry with paths, hashes, schema versions; upstream loaded from manifest | `ArtifactEntry`/`RunManifest.artifacts` (`core/orchestrator.py`); registration via `PhaseContext.register_artifact()`, hashed (with size/mtime reuse) in `Orchestrator._hash_with_reuse()`, resumed/upstream artifacts checked in `Orchestrator._verify_artifact_integrity()`. F1/F1b/F2b register their whole output as one JSON artifact via `main.py::_register_json_artifact()`; F2a additionally registers one artifact per aligned raster via `main.py::_register_aligned_rasters()` (`aligned/<layer>`). Per-source-file checksums inside F1's `layer_registry` are not implemented (OQ-024). Tests: `tests/unit/test_orchestrator.py::test_declared_artifact_not_registered_raises`, `::test_undeclared_artifact_registration_raises`, `::test_upstream_outside_current_run_is_loaded_from_manifest`, `::test_artifact_changed_after_registration_raises_integrity_error`, `::test_deleted_artifact_raises_integrity_error_on_upstream_load`, `::test_hash_reused_when_size_and_mtime_unchanged` | pass |
| A-03 | Run targeting | `RunConfig.target_phases`/`force_rerun` (`core/schemas.py`); resolved into an execution set in `Orchestrator.run()` (transitive closure over `requires`/`produces`). Tests: `tests/unit/test_schemas.py::test_run_config_accepts_valid_payload`, `::test_run_config_empty_target_phases_raises`; `tests/unit/test_orchestrator.py::test_force_rerun_reexecutes_target_and_dependents` | pass |
| A-04 | Technology registry | Not present | fail |
| A-05 | Country mappings in `config/countries.yaml`; ISO3 literal test | 12 dict entries in `local_layers.py` and `hydrosheds.py` | fail |
| A-06 | Synthetic country fixture | Not present | fail |
| A-09 | Failure stops dependents only | `Orchestrator.run()` catches a phase's exception, records `PhaseResult(status="failed")`, and does not raise; transitive dependents get `status="skipped_upstream_failed"`, independent branches still run. `main.py::run_geofrea()` derives a non-zero process exit whenever any target phase ends `"failed"` or `"skipped_upstream_failed"`. Tests: `tests/unit/test_orchestrator.py::test_failure_in_one_branch_does_not_block_an_independent_branch`, `::test_failure_upstream_marks_all_dependents_skipped`; `tests/unit/test_main.py::test_run_geofrea_returns_false_when_a_target_phase_fails`, `::test_run_geofrea_returns_false_when_a_target_phase_is_skipped_upstream_failed`, `::test_run_geofrea_returns_true_when_every_target_phase_succeeds` | pass |
| U-05 | Parameter schema with `unit`, `tier`, `range` | `VerifiedValue` without `tier`/`range`; biomass and `capacity_factor` entries present | fail |
| Section 9 | `experiments.yaml`, `technologies.yaml`, `countries.yaml` | Not present | fail |

## Active implementation decisions

- **D-core-001 — Technology-level discount rate.** IRENA reports genuinely different discount rates per technology for the same country, so `discount_rate` lives under `parameters.json`'s per-technology entries, never at country level.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - discount_rate architecture fix
- **D-core-002 — Solar and wind parameters from IRENA.** Solar and wind cost/performance parameters (CAPEX, OPEX, lifetime, capacity factor) are populated from IRENA 2024/2025 editions, differentiated per country where the source provides country-level figures.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - solar and wind parameters populated (IRENA 2024/2025)
- **D-core-003 — Single orchestration and audit mechanism, implementing A-01/A-02/A-03/A-09 (verdicts OQ-E2-1 to OQ-E2-4; E4 artifact-granularity closeout).** `PhaseSpec` carries `requires`/`produces`; `Orchestrator.run()` validates the graph (`MissingProducerError`, `DependencyCycleError`, `DuplicateProducerError`) and topologically orders phases (stable tie-break by name) from `RunConfig.target_phases`/`force_rerun`. `PhaseContext.register_artifact()` feeds `RunManifest.artifacts` (path, sha256, size, mtime, schema_version, phase, run_id), reused when size/mtime match and integrity-checked (missing file or hash mismatch, never recomputed) whenever a phase is resumed *or* loaded as an upstream artifact outside the current run's target set. `RunManifest.schema_version` is pinned `"2.0"` (`LegacyManifestError` otherwise, no migration). A failure records `status="failed"` without raising; dependents get `"skipped_upstream_failed"`; independent branches still run. Artifact granularity per phase: F1 (`data_acquisition`) and F1b (`data_quality_audit`) register one artifact each — a JSON dump of the whole phase output (`layer_registry`, `audit_report`) — because neither phase's output has natural per-item files to hash separately (F1b's report is one document; F1's `AcquiredLayer` entries have no per-layer checksum today, see OQ-024). F2a (`grid_alignment`) registers one artifact per aligned raster field (`aligned/<layer>`, `main.py::_register_aligned_rasters()`) plus the `aligned_rasters` JSON summary, since each raster is independently a real, hashable, resumable file. F2b (`suitability_criteria`) still registers only its own output model as one artifact (see Known issues) — unlike F1/F1b, this is a temporary exception, not the final design, pending the Estágio H rebuild.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit phase
- **D-core-004 — Slope threshold as a technology parameter.** Terrain slope tolerance is a scientific parameter in `config/parameters.json`, keyed per technology, not a single unsourced country-level fallback — each technology has a physically distinct terrain tolerance. Carried forward into M-F2b-01 E4 (`slope_max_deg[tech]`), same underlying rationale.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - slope_threshold_deg movido para parameters.json

## Known issues

- Pydantic schema defaults duplicate `settings.yaml` values (`resolution_deg`, `adaptive_*`, `max_dist_km`).
- Five `criteria.*` parameters are validated but never read.
- F2b (`suitability_criteria`) registers only one artifact for its whole output model (`suitability_criteria_result`), not a per-layer breakdown — temporary, pending the Estágio H rebuild of F2b into `siting_layers` (exclusion/cost-driver/resource layers, METHODOLOGY M-F2b-01 to M-F2b-05).
- F2a's `produces` hardcodes 11 raster keys (`main.py::_ALIGNED_RASTER_LAYER_KEYS`, excludes only `seismic`, out of scope per S-08). This holds for PRT and BRA today (every field resolves to a real raster). A future country legitimately missing one of these 11 inputs (e.g. IND, OQ-012) — or a country with zero existing plants, leaving `GridAlignmentResult.plants` `None` — would raise `UndeclaredArtifactMissingError` at `grid_alignment`, not a graceful partial result. Revisit when IND is wired (MS-2).
- WDPA (protected areas) for PRT: `data_quality_audit` reports `[ERROR] found (unreadable)` — `TopologyException: side location conflict` in `core/geo_utils.py::clip_vector_to_country()`'s `.intersection()` step, on the live-fetched `PRT_protected_areas_wdpa.geojson` (442 features, 2026-09-21). Confirmed pre-existing: reproduced against unmodified commit `e1a57ed` code on the same file (git worktree, see E4 report in session transcript) — not a regression from the orchestrator redesign. Root cause is an invalid/self-intersecting geometry in the live Protected Planet response; unresolved (no fix applied, per instruction: report only, since not a regression).

## History

- D-core-005 (E2 draft design for A-01/A-02/A-03/A-09, "awaiting verdict") — approved (OQ-E2-1 to OQ-E2-4) and implemented; superseded by D-core-003's updated text above.
