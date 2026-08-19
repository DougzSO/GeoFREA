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

## STRUCTURAL_PRESERVE vs. METHODOLOGY_REVISION

Any decision that preserves or changes the legacy pipeline's scientific/
structural behavior must be logged as an entry in `docs/DECISIONS.md`
(append-only), tagged with one of:

- **STRUCTURAL_PRESERVE** — the legacy logic is kept as-is.
- **METHODOLOGY_REVISION** — the legacy logic is deliberately changed,
  with a documented justification and, where applicable, a literature
  reference.

Code that implements a decision recorded this way should reference it,
e.g. `# See DECISIONS.md 2026-08-19 - biomass CAPEX/OPEX/lifetime fallback values`.

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
