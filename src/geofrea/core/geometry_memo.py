"""A memo of the union of a country polygon, shared by the phases that ask for it again and again (COMMAND 77, item 4)."""

from __future__ import annotations

import hashlib
from typing import Any

import geopandas as gpd

_UNION_MEMO: dict[str, Any] = {}
_UNION_MEMO_MAX = 8


def geometry_digest(geometry: Any) -> str:
    """SHA-256 over the WKB of every geometry of the sequence, in order (None counts as empty)."""
    h = hashlib.sha256()
    for g in geometry:
        h.update(g.wkb if g is not None else b"")
        h.update(b"")
    return h.hexdigest()


def country_union(geometry: gpd.GeoSeries | gpd.GeoDataFrame) -> Any:
    """`union_all()` of a country layer, computed once per process for the same coordinates.

    The phases ask for the union of the country polygon again and again (the audit, the clip, every raster inspection; 11 to 47 s of CPU
    per phase in PRT in docs/_audit/profile_76.md B.3). The memo is keyed by the WKB of the features, so a polygon with other coordinates
    is another entry, and the result is the object `union_all()` returned the first time (shapely geometries are immutable).
    """
    series = geometry.geometry if isinstance(geometry, gpd.GeoDataFrame) else geometry
    key = geometry_digest(series.values)
    if key not in _UNION_MEMO:
        if len(_UNION_MEMO) >= _UNION_MEMO_MAX:
            _UNION_MEMO.pop(next(iter(_UNION_MEMO)))
        _UNION_MEMO[key] = series.union_all()
    return _UNION_MEMO[key]
