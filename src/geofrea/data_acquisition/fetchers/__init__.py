"""Real fetch implementations for data_acquisition, one module per SOURCE.

Organized by source/provider (GADM, WRI, Global Wind Atlas, HydroSHEDS,
Protected Planet, ...), not by authentication pattern — a deliberate
architectural decision, not a default. See docs/DECISIONS.md 2026-08-25
"real fetchers for power_plants/wind/lakes/rivers" (its "Por que fetch
por FONTE" section) for the full (a) vs (b) rationale, summarizing the
research conducted earlier the same session.

Each module here owns exactly one source: URL construction, response
parsing, and any source-specific quirks (region/country mapping,
pinned versions, pagination). None of them know about AcquiredLayer,
_LAYER_REGISTRY, or the orchestrator — phase.py wires a module's
public fetch_*() function into the layer registry loop; a fetcher
module only ever returns a Path (or raises/returns None on failure)
and never constructs Pydantic models itself.
"""

from __future__ import annotations
