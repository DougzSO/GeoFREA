# GeoFREA

GeoFREA is a from-scratch reconstruction of the **GeoWorld Framework**, a
9-phase geospatial pipeline for renewable-energy siting suitability
(solar, wind, biomass). The goal is not a line-by-line port of the legacy
code, but a clean rebuild of the underlying scientific logic — preserving
validated behavior where it holds up, and deliberately revising it where
it doesn't, with every such decision logged in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Legacy reference

`geoworld_framework/` (a sibling directory on disk, path configured via
`GEOWORLD_BASELINE_DIR` in `.env`) is the legacy pipeline. It is a
**read-only** source of scientific/architectural knowledge: formulas,
parameter values, known issues, and regression baselines. It is never
modified as part of GeoFREA's development.

## Setup

1. Copy `.env.example` to `.env` and fill in the values (raw/processed/
   output data directories, and `GEOWORLD_BASELINE_DIR` pointing at the
   legacy repository).
2. Install the package in editable mode with dev dependencies:
   ```
   pip install -e ".[dev]"
   ```

## Running tests

```
pytest tests/unit/
pytest tests/regression/
```

Regression tests compare GeoFREA outputs against the frozen legacy
baselines documented in `docs/architecture/baseline-manifest.md`.

## Project documentation

- [`docs/architecture/`](docs/architecture/) — per-module documentation of the legacy
  pipeline's science, parameters, and known issues, module-by-module.
- [`docs/architecture/module-mapping.md`](docs/architecture/module-mapping.md) — traceability anchor between legacy
  phases and GeoFREA modules.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — append-only log of structural/methodological
  decisions made during the reconstruction.
- [`CLAUDE.md`](CLAUDE.md) — project conventions and session workflow for AI-assisted
  development.
- [`docs/PROGRESS.json`](docs/PROGRESS.json) — machine-readable snapshot of what has been
  built, documented, or still needs a decision.

## Status

Early scaffolding. No production code yet — only the package skeleton,
project conventions, and the architecture/decision documentation carried
over from the audit of the legacy pipeline.
