# core: orchestration, configuration, shared utilities

Status: `rework_required`
Methodology items: A-01, A-02, A-03, A-04, A-05, A-06, A-07, A-09, A-10, A-12, A-13, U-05, Section 9

## Contract

Provides to all phases: DAG orchestrator, artifact registry and manifest, configuration loading and validation (`parameters.json`, `technologies.yaml`, `countries.yaml`, `experiments.yaml`, `settings.yaml`), geodesy utilities, raster and vector I/O helpers, HTTP retry.

## Conformance

| Item | Requirement | Current state (from `docs/_audit/2026-09_F1-F2b.md` section 8) | Status |
|---|---|---|---|
| A-01 | `requires`/`produces`, topological order, startup validation | `PhaseSpec` has `name`, `output_model`, `run`; order depends on list position in `main.py` | fail |
| A-02 | Artifact registry with paths, hashes, schema versions; upstream loaded from manifest | Manifest stores phase status and a loose output dict; artifacts written by phases outside the orchestrator | fail |
| A-03 | Run targeting | Boolean per-phase toggles in `settings.yaml` | fail |
| A-04 | Technology registry | Not present | fail |
| A-05 | Country mappings in `config/countries.yaml`; ISO3 literal test | 12 dict entries in `local_layers.py` and `hydrosheds.py` | fail |
| A-06 | Synthetic country fixture | Not present | fail |
| A-09 | Failure stops dependents only | Any failure stops all following phases | fail |
| U-05 | Parameter schema with `unit`, `tier`, `range` | `VerifiedValue` without `tier`/`range`; biomass and `capacity_factor` entries present | fail |
| Section 9 | `experiments.yaml`, `technologies.yaml`, `countries.yaml` | Not present | fail |

## Active implementation decisions

- **D-core-001 — Technology-level discount rate.** IRENA reports genuinely different discount rates per technology for the same country, so `discount_rate` lives under `parameters.json`'s per-technology entries, never at country level.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - discount_rate architecture fix
- **D-core-002 — Solar and wind parameters from IRENA.** Solar and wind cost/performance parameters (CAPEX, OPEX, lifetime, capacity factor) are populated from IRENA 2024/2025 editions, differentiated per country where the source provides country-level figures.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - solar and wind parameters populated (IRENA 2024/2025)
- **D-core-003 — Single orchestration and audit mechanism.** Orchestration and data-quality auditing run through one consolidated, testable mechanism with a typed output contract and genuine resumability, rather than ad hoc per-phase glue code. Still the design intent for the orchestrator rebuild under A-01/A-02 (see Conformance).
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit phase
- **D-core-004 — Slope threshold as a technology parameter.** Terrain slope tolerance is a scientific parameter in `config/parameters.json`, keyed per technology, not a single unsourced country-level fallback — each technology has a physically distinct terrain tolerance. Carried forward into M-F2b-01 E4 (`slope_max_deg[tech]`), same underlying rationale.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-20 - slope_threshold_deg movido para parameters.json

## Known issues

- Pydantic schema defaults duplicate `settings.yaml` values (`resolution_deg`, `adaptive_*`, `max_dist_km`).
- Five `criteria.*` parameters are validated but never read.

## History

None.
