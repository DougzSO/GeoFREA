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

None yet.

## Known issues

- Pydantic schema defaults duplicate `settings.yaml` values (`resolution_deg`, `adaptive_*`, `max_dist_km`).
- Five `criteria.*` parameters are validated but never read.

## History

None.
