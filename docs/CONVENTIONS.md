# CONVENTIONS.md — GeoFREA

Technical reference for anyone writing code in this repository.

## Language

All source code, comments, docstrings, variable/function names, and
commit messages must be in English.

## Docstrings

Google style: concise but complete. Cover purpose, `Args`, `Returns`,
and — for any geospatial function — units and CRS. A geospatial function
without a documented unit/CRS note is considered incomplete.

See the template in "Docstring template" below.

## Parameters

Every new parameter goes into `config/parameters.json` (scientific/
technology values) or `config/settings.yaml` (operational/infrastructure
values), validated through a Pydantic schema in `src/geofrea/core/`. No
hardcoded values in processing modules — this is a hard project policy,
not a style preference, since hardcoded fallbacks silently diverging
from the canonical config was a recurring bug class in the legacy
pipeline (see `docs/architecture/sensitivity_analysis.md` §c).

## Parameter verification metadata

Every parameter entry in `parameters.json` must carry a standard
verification block alongside its value:

```json
{
    "value": 2720.0,
    "source": "IRENA 2024",
    "verified": true,
    "verified_by": "Douglas",
    "verified_date": "2026-08-20",
    "verification_method": "manual_cross_check"
}
```

- `verified_by` and `verified_date` are `null` when `verified` is `false`.
- `verification_method` is one of `"manual_cross_check"`, `"automated"`,
  or `"unverified"`.

A parameter with `verified: false` is **not** blocked from use — the
pipeline may run with unverified values. What's required is that the
schema exposes this metadata (not just the bare value) and that it is
testable: a test must be able to assert, for any given parameter, what
its current verification status is. See `docs/DECISIONS.md` for the
provenance narrative behind a given `source`/verification (e.g. the
2026-08-19/2026-08-20 biomass CAPEX/OPEX/lifetime entries).

## STRUCTURAL_PRESERVE vs. METHODOLOGY_REVISION

Any decision that preserves or changes the legacy pipeline's scientific/
structural behavior must be logged as an entry in `docs/DECISIONS.md`
(append-only), tagged with one of:

- **STRUCTURAL_PRESERVE** — the legacy logic is kept as-is.
- **METHODOLOGY_REVISION** — the legacy logic is deliberately changed,
  with a documented justification and, where applicable, a literature
  reference.
- **VERIFICATION_UPDATE** — the decision itself is unchanged; only the
  confidence/verification status of a cited source or value is updated
  (e.g. a value moves from unverified to independently confirmed), or
  an earlier entry's scope is narrowed/clarified without reversing it.

A `Tipo:` value may combine a canonical type with a short parenthetical
qualifier (e.g. `STRUCTURAL_PRESERVE (correção da auditoria, não revisão
de método)`) or combine two types with `|` when an entry covers more than
one change of different kinds (e.g. `STRUCTURAL_PRESERVE (itens 2 e 4) |
METHODOLOGY_REVISION (itens 1 e 3)`). The qualifier is free text for
context; the base type before any parenthetical or `|` must still be one
of the three above.

Regression tolerances (`rtol`, pixel-exact comparison thresholds) are
defined in `CLAUDE.md`, not here — `DECISIONS.md` entries that cite a
tolerance should be checked against `CLAUDE.md`, not against this file.

Code that implements a decision recorded this way should reference it,
e.g. `# See DECISIONS.md 2026-08-19 - biomass CAPEX/OPEX/lifetime fallback values`.

## Phase numbering

The pipeline has **nine modules** grouped into **eight numbered phases**.
This is the canonical numbering — use it in code comments, docstrings,
commit messages, `docs/PROGRESS.json`, and architecture docs.

| Phase | Module(s) (`src/geofrea/<name>/`)        | Legacy origin |
|-------|-----------------------------------------|---------------|
| 1     | `data_acquisition` + `data_quality_audit` | Legacy Phase 1 (Audit); `data_acquisition` is a GeoFREA-only split of raw-data fetching out of the audit |
| 2a    | `grid_alignment`                         | Legacy Phase 2a |
| 2b    | `suitability_criteria`                   | Legacy Phase 2b (Criteria) |
| 3     | `suitability_builder`                    | Legacy Phase 3 (Suitability / MCDA) |
| 4     | `potential_analysis`                     | Legacy Phase 4 (Potential) |
| 5     | `lcoe_modeling`                          | Legacy Phase 5 (LCOE) |
| 6     | `results_synthesis`                      | Legacy Phase 6 (Results) |
| 7     | `ghg_abatement`                          | Legacy Phase 7 (GHG Abatement) |
| 8     | `sensitivity_analysis`                   | Legacy Phase 8 (Sensitivity) |

Rules:

- **Never write an unqualified "Phase 2".** `grid_alignment` is `2a` and
  `suitability_criteria` is `2b` — distinct phases that merely share the
  legacy's Phase 2 lineage. Always write `2a` or `2b`.
- Transport Decarbonisation (legacy Phase 9) is permanently excluded and
  has no GeoFREA phase number (see "Excluded modules" below).
- `fase_legado` in `docs/PROGRESS.json` records each module's legacy
  phase of origin and is intentionally coarser (both `grid_alignment`
  and `suitability_criteria` carry `fase_legado: 2`). It is provenance
  metadata, not the GeoFREA phase number.

Modules in `docs/PROGRESS.json`'s `modulos` array use one of three status
values: `construido` (built), `documentado_nao_construido` (documented,
not yet built), or `parcialmente_implementado` (production code exists
and is wired into `main.py`, but not all of the module's scope is
implemented — e.g. `data_acquisition`, where some layers have real fetch
and others resolve from local files only). A module marked `construido`
may depend on a Fase 1 module that is only `parcialmente_implementado` —
this is not itself an error, but the dependency gap should stay visible
in status fields rather than only in free-text `observacao`.

### Project-milestone numbering (`fase_atual`)

`docs/PROGRESS.json`'s `fase_atual` field is a **separate axis** from the
pipeline phase numbers above. It tracks GeoFREA *reconstruction*
milestones, not the pipeline:

| `fase_atual` | Milestone |
|--------------|-----------|
| `0`   | Legacy audit complete and all `docs/architecture/*.md` written (2026-08-19) |
| `0.5` | Regression baseline (PRT + BRA) regenerated at legacy commit `fc7b43d` (2026-08-20, commit `d6def9c` — "Fase 0.5: regenerate regression baseline") |
| `1`+  | Module construction under way — carry the **pipeline phase label** of the module currently being built (e.g. `2b` while `suitability_criteria` is being implemented) |

The fractional `0.5` is real: it names the baseline-regeneration
milestone that sits between the audit (`0`) and the first module build.
It is not a placeholder. Once construction is under way, keep
`fase_atual` set to the pipeline phase label of the work in progress, and
update it at end of session (see `CLAUDE.md` § "Início e fim de sessão").

## Excluded modules

GeoFREA does not include a Transport Decarbonisation phase (see
`DECISIONS.md` 2026-08-20 - Transport phase permanently excluded). This
is a deliberate scope decision, not a gap.

## Referencing DECISIONS.md addenda

`DECISIONS.md` is append-only: a decision entry is never edited, even
when a later addendum updates its verification status or narrows its
scope. When a decision has been superseded *in part* by a later
addendum (not replaced outright), code comments referencing that
decision must point to the addendum date, not the original entry's
date — the addendum is what's current.

```python
# See DECISIONS.md 2026-08-20 (addendum to 2026-08-19) - biomass CAPEX/OPEX/lifetime
```

This is the fixed convention going forward: always cite the most recent
addendum that touches the specific point the code depends on, and name
the original entry's date in parentheses for traceability back through
the append-only log.

## Docstring template

```python
def compute_protected_area_score(
    wdpa_gdf: gpd.GeoDataFrame,
    transform: Affine,
    out_shape: tuple[int, int],
    as_exclusion: bool = True,
) -> np.ndarray:
    """Rasterize IUCN protected-area categories into a suitability score.

    Pixels inside categories Ia/Ib/II are scored 0.0 when as_exclusion is
    True (hard exclusion); all other pixels default to 1.0 (unrestricted).
    See DECISIONS.md 2026-08-19 - protected_areas / IUCN exclusion categories.

    Args:
        wdpa_gdf: WDPA polygons with an IUCN category column, in the same
            CRS as the target grid (EPSG:4326).
        transform: Affine geotransform of the output raster.
        out_shape: (height, width) of the output raster, in pixels.
        as_exclusion: If True, strict categories (Ia/Ib/II) are scored
            0.0 instead of their WDPA-derived score.

    Returns:
        np.ndarray of shape out_shape, dtype float32, values in [0, 1].
        1.0 = unrestricted, 0.0 = excluded.
    """
```
