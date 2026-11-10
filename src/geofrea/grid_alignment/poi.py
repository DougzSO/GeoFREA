"""Point of interconnection (POI) layer of Group 3: substations of the OSM grid that a plant of about 100 MW can connect to.

A substation is eligible when its nominal voltage is at least the country threshold `poi_voltage_threshold_kv` (parameters.json, Tier 2).
The voltage comes from the OSM `voltage` tag; a substation without one takes the highest voltage of the OSM lines that reach it (within
`tolerance_m`); a substation whose voltage cannot be inferred is excluded. A polygon is represented by `representative_point`.

The functions are pure (frames in, frames and counts out); the geodesic distance to the points returned here (exact coordinates, no pixel) is computed in `vector_alignment.py`.

Implements: M-F2a-09 (Group 3 POI layer, `docs/thesis/methods/group3_connection_degradation.tex`, subsection "Point of Interconnection").
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

import geopandas as gpd
import pandas as pd
from shapely import affinity
from shapely.geometry import box
from shapely.strtree import STRtree

from geofrea.core.geodesy import wgs84_km_per_degree

POI_ALGORITHM_VERSION = 2  # part of the cache key of the `poi` layer: bump when the selection or the voltage parsing changes

# OSM writes several voltages as one value ("138000;69000", "138000_69000_23000", "132000/133000")
_SEPARATORS = re.compile(r"[;/_,|]")
_NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(kv|v)?\s*$", re.IGNORECASE)
# OSM stores volts; a bare value below this is not a plausible grid voltage in volts, and without a unit it is not guessed
_MIN_BARE_VOLTS = 1000.0


class PoiError(ValueError):
    """An input of the POI layer breaks its contract."""


def parse_voltage_kv(raw: object) -> float | None:
    """The highest voltage of an OSM `voltage` tag, in kV, or None when the tag gives no usable value.

    Implements: M-F2a-09.

    Values are volts (the OSM convention) and are converted to kV; a value with an explicit `kV` suffix is taken as kV. Lists separated by
    `;`, `_`, `/`, `,` or `|` give their largest valid value. A token that is not a number, is zero, or is a bare number below 1000 (neither a
    volt value nor labelled kV, so its unit would be a guess) is ignored; a tag with no valid token is absent, never zero.
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    best: float | None = None
    for token in _SEPARATORS.split(str(raw)):
        match = _NUMBER.match(token)
        if match is None:
            continue
        value = float(match.group(1).replace(",", "."))
        unit = (match.group(2) or "").lower()
        if value <= 0:
            continue
        if unit == "kv":
            kv = value
        elif value >= _MIN_BARE_VOLTS:
            kv = value / 1000.0
        else:
            continue
        best = kv if best is None else max(best, kv)
    return best


@dataclass(frozen=True)
class PoiCounts:
    """Substations of one country by what happened to them (reported per country, recorded in the manifest).

    Args:
        total: Substations read, after the nodes inside a polygon were dropped.
        with_tag: With a usable `voltage` tag.
        inferred: Without one, voltage taken from the OSM lines that touch or cross them (within the tolerance).
        excluded_no_voltage: No tag and no tagged line within the tolerance.
        below_threshold: A voltage was found but it is under the threshold.
        eligible: At or above the threshold: the points of the POI layer.
        nodes: Of `total`, mapped as a point.
        polygons: Of `total`, mapped as an area (closed way or relation).
        duplicates_removed: Nodes inside a polygon, dropped in favour of the polygon.
    """

    total: int
    with_tag: int
    inferred: int
    excluded_no_voltage: int
    below_threshold: int
    eligible: int
    nodes: int = 0
    polygons: int = 0
    duplicates_removed: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def drop_nodes_inside_polygons(substations: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, int]:
    """Remove each point that lies inside (or on) a substation polygon, keeping the polygon; returns the frame and how many were dropped."""
    is_point = (substations.geom_type == "Point").to_numpy()
    if not is_point.any() or is_point.all():
        return substations, 0
    polygons = substations.geometry[~is_point]
    points = substations.geometry[is_point]
    tree = STRtree(polygons.to_numpy())
    inside_idx = tree.query(points.to_numpy(), predicate="intersects")[0]
    drop = points.index[sorted(set(inside_idx.tolist()))]
    return substations.drop(index=drop), len(drop)


def infer_voltage_from_lines(
    geometries: gpd.GeoSeries,
    lines: gpd.GeoDataFrame,
    tolerance_m: float,
    voltage_column: str = "voltage",
) -> pd.Series:
    """For each substation geometry (point or polygon), the highest tagged line voltage (kV) among the lines that touch it or pass within `tolerance_m`; NaN when there is none.

    Implements: M-F2a-09.

    `geometries` and `lines` are in EPSG:4326. The distance is measured in a local frame in kilometres (the scale of a degree changes with
    latitude), so a line that crosses a polygon is at distance zero. The tolerance is declared in `settings.yaml`
    (`geospatial.poi_line_tolerance_m`) and recorded in the manifest.
    """
    if tolerance_m < 0:
        raise PoiError("tolerance_m must not be negative")
    result = pd.Series(float("nan"), index=geometries.index, dtype="float64")
    if len(geometries) == 0 or len(lines) == 0:
        return result
    line_kv = lines[voltage_column].map(parse_voltage_kv) if voltage_column in lines else None
    if line_kv is None:
        return result
    tagged = line_kv.notna().to_numpy()
    geoms = lines.geometry.to_numpy()[tagged]
    kv = line_kv.to_numpy(dtype="float64")[tagged]
    if len(geoms) == 0:
        return result
    tree = STRtree(geoms)
    tolerance_km = tolerance_m / 1000.0
    for index, geometry in geometries.items():
        lat_km, lon_km = wgs84_km_per_degree(geometry.representative_point().y)
        minx, miny, maxx, maxy = geometry.bounds
        window = box(
            minx - tolerance_km / lon_km, miny - tolerance_km / lat_km,
            maxx + tolerance_km / lon_km, maxy + tolerance_km / lat_km,
        )  # fmt: skip
        hits = tree.query(window, predicate="intersects")
        if not len(hits):
            continue
        local = affinity.scale(geometry, xfact=lon_km, yfact=lat_km, origin=(0, 0))
        near = [
            kv[h]
            for h in hits
            if local.distance(affinity.scale(geoms[h], xfact=lon_km, yfact=lat_km, origin=(0, 0)))
            <= tolerance_km
        ]
        if near:
            result.at[index] = float(max(near))
    return result


def select_poi(
    grid: gpd.GeoDataFrame,
    threshold_kv: float,
    tolerance_m: float,
    voltage_column: str = "voltage",
    power_column: str = "power",
) -> tuple[gpd.GeoDataFrame, PoiCounts]:
    """The eligible substations of an OSM grid frame as points with a `voltage_kv` and its origin, and the counts.

    Implements: M-F2a-09.

    Args:
        grid: OSM power features in EPSG:4326: `power == "substation"` rows (points or polygons) and the lines that reach them.
        threshold_kv: Country minimum voltage (`poi_voltage_threshold_kv`).
        tolerance_m: Distance within which a line reaches a substation, for the inference of a missing voltage.

    Raises:
        PoiError: the frame lacks the power column, or the threshold is not positive.
    """
    if threshold_kv <= 0:
        raise PoiError("the voltage threshold must be positive")
    if power_column not in grid:
        raise PoiError(f"the grid frame has no {power_column!r} column")
    substations = grid[grid[power_column] == "substation"].copy()
    lines = grid[grid[power_column].isin(["line", "cable", "minor_line"])]
    substations, duplicates = drop_nodes_inside_polygons(substations)
    n_nodes = int((substations.geom_type == "Point").sum())
    tag = (
        substations[voltage_column].map(parse_voltage_kv)
        if voltage_column in substations
        else pd.Series(float("nan"), index=substations.index, dtype="float64")
    )
    has_tag = tag.notna()
    # the lines are tested against the full geometry (a line that crosses a polygon reaches it), the point is taken afterwards
    inferred = infer_voltage_from_lines(
        substations.geometry[~has_tag], lines, tolerance_m, voltage_column
    )
    substations["geometry"] = substations.geometry.representative_point()
    voltage = tag.astype("float64").copy()
    voltage.loc[inferred.index] = inferred
    known = voltage.notna()
    eligible = known & (voltage >= threshold_kv)
    out = substations.loc[eligible, ["geometry"]].copy()
    out["voltage_kv"] = voltage[eligible]
    out["voltage_source"] = ["tag" if has_tag[i] else "inferred" for i in out.index]
    counts = PoiCounts(
        total=len(substations),
        with_tag=int(has_tag.sum()),
        inferred=int(inferred.notna().sum()),
        excluded_no_voltage=int((~known).sum()),
        below_threshold=int((known & ~eligible).sum()),
        eligible=int(eligible.sum()),
        nodes=n_nodes,
        polygons=len(substations) - n_nodes,
        duplicates_removed=duplicates,
    )
    return gpd.GeoDataFrame(out, geometry="geometry", crs=grid.crs), counts
