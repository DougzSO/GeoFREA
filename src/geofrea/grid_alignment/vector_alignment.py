"""Vector rasterization/distance-transform logic for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`_calculate_wgs84_isotropic_distance()` L550-594, `_align_linear_features()`
L597-681, `_align_lakes()` L684-739, `_align_rivers()` L742-800,
`_align_plants()` L803-879) — see docs/_archive/2026-09/DECISIONS.md 2026-09-08,
grid_alignment Passo 3.

Load/clip split from legacy (per Passo 1's design correction, same
DECISIONS.md date): legacy's `_align_linear_features()`/`_align_lakes()`/
`_align_rivers()` each called `_load_and_clip_vector_data()` (a bbox
read + CRS reproject) internally before rasterizing. Here, that call is
moved OUT to the caller (alignment.py):
  - roads/lakes/rivers (global source files) arrive as an
    ALREADY-CLIPPED GeoDataFrame, produced by the caller via
    core.geo_utils.read_clipped_to_country() against the same on-disk
    cache_path convention data_quality_audit's audit.py uses — see
    schemas.py's module docstring for the full rationale.
  - grid (already country-scoped at the acquisition source) is loaded
    via load_vector_bbox() below, a near-verbatim port of legacy's
    `_load_and_clip_vector_data()` — a lightweight bbox prefilter with
    no exact-intersection clip and no cache, since the file is already
    small and single-country.

This means rasterize_linear_distance() below (used for both roads and
grid) receives an already-loaded GeoDataFrame, not a path — the one
legacy function it replaces (`_align_linear_features()`) has had its
own internal load call removed accordingly. Everything downstream of
the load (STRtree intersects filter, simplify, rasterize, distance
transform, clip, write) is otherwise unchanged from legacy.

`_align_rivers()`'s asymmetry vs. `_align_linear_features()` is
preserved AS-IS, not unified: legacy's rivers path has no STRtree
intersects-prefilter step (rasterizes every loaded feature directly)
and does NOT AND the rasterized mask with grid.country_mask before the
distance transform (roads/grid do both). At the FUNCTION level (what
is unit-tested here) this means a river feature outside grid.country_mask
still contributes to the distance transform, while a road/grid feature
outside it does not — a real, testable difference regardless of what
the caller passes in. Its practical impact on the full pipeline is
smaller than in legacy, though, precisely BECAUSE of Passo 1's
pre-clipping: rivers_gdf/roads_gdf arrive already cut to the country
polygon by read_clipped_to_country() before reaching align_rivers()/
rasterize_linear_distance(), so there is no longer a large "just
outside the country" feature population left to matter — what remains
is at most a sub-pixel sliver from clip_vector_to_country()'s geometry
simplification tolerance at the border (country_mask is rasterized
from the UNsimplified polygon; the vector clip uses a simplified one).
`grid` (load_vector_bbox(), no exact clip) is NOT pre-clipped this way
and still fully exhibits the original-scale asymmetry. This was true
in legacy before this port and is not a numeric parameter — it is a
structural difference between two functions that happened to diverge —
so it is called out here rather than silently ported without comment,
but NOT changed (out of scope for this stage; see docs/_archive/2026-09/DECISIONS.md
2026-09-08, grid_alignment Passo 4, for the numerically-hardcoded parts
of this same asymmetry — the 50km vs. 100km distance cap — which ARE
flagged there as pending).
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Geod
from rasterio.features import rasterize
from scipy.spatial import cKDTree
from shapely.geometry import mapping
from shapely.strtree import STRtree

from geofrea.core.checkpoint import CheckpointStore, digest_inputs, make_key
from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.core.geometry_memo import country_union
from geofrea.core.raster_io import safe_raster_write
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)


def load_vector_bbox(
    path, country_gdf: gpd.GeoDataFrame, label: str, buffer_deg: float = 0.01
) -> gpd.GeoDataFrame | None:
    """Load a vector file, bbox-prefiltered to the country's extent.

    Lightweight port of legacy's `_load_and_clip_vector_data()` — a
    read-time bbox filter only, no exact-geometry clip, no cache. Used
    for `grid` only: unlike roads/lakes/rivers, the grid source file is
    already country-scoped at acquisition (small, single-country), so
    the heavier read_clipped_to_country() + cache machinery (used for
    the global-source layers, see module docstring) is not needed here.

    Args:
        path: Vector file to load.
        country_gdf: Country GeoDataFrame, for the bbox reference.
        label: Descriptive label for logging.
        buffer_deg: Bounding-box buffer, in degrees.

    Returns:
        Clipped GeoDataFrame in country_gdf's CRS, or None if the
        result is empty or the read failed.
    """
    try:
        minx, miny, maxx, maxy = country_gdf.total_bounds
        bbox = (minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg)

        vector_data = gpd.read_file(path, bbox=bbox)

        if vector_data.empty:
            return None

        if vector_data.crs != country_gdf.crs:
            vector_data = vector_data.to_crs(country_gdf.crs)

        logger.info("    [%s] %d features loaded.", label, len(vector_data))
        return vector_data
    except Exception as e:  # noqa: BLE001 — one bad vector source must not abort alignment
        logger.error("    [%s] Driver error during vector subsetting: %s", label, e)
        return None


def filter_road_classes(gdf: gpd.GeoDataFrame | None, classes) -> gpd.GeoDataFrame | None:
    """Keep the roads of the configured classes (Group 3: primary and secondary roads; the distance to the road is a distance to a main road).

    GRIP4 carries the class in `GP_RTP` (1 highways, 2 primary, 3 secondary, 4 tertiary, 5 local) and OSM in `highway`. A frame with neither
    column is returned unchanged (the synthetic country has no road classes); `classes` None keeps every road.

    Implements: M-F2a-10.
    """
    if gdf is None or classes is None or gdf.empty:
        return gdf
    if "GP_RTP" in gdf.columns:
        kept = gdf[gdf["GP_RTP"].isin(classes.grip4_gp_rtp)]
    elif "highway" in gdf.columns:
        kept = gdf[gdf["highway"].isin(classes.osm_highway)]
    else:
        return gdf
    logger.info("    [roads] %d of %d features in the configured road classes.", len(kept), len(gdf))
    return kept if not kept.empty else None


_GEOD = Geod(ellps="WGS84")
_DENSIFY_M = 100.0  # the longest stretch between two vertices of a line, in metres (M-F2a-03)
_FEATURE_CHUNK = 20_000  # features densified and converted to vertices at a time (COMMAND 88: the memory of a layer is its own working set)
_STRIP_ROWS = 64  # rows of pixels whose distance is computed (and stored in the checkpoint) at a time
# Most vertices a nearest-neighbour tree holds at once (about 60 bytes each). The grid, roads and substations of IND, BRA and PRT (at most 5.8 million
# vertices) fit in one block; the 26.5 million vertices of the rivers of BRA go in five, so that the process of the layer stays under the cap.
_BLOCK_VERTICES = 6_000_000
# The rivers have 5 to 25 times more vertices than any other layer and their process also holds the vector: smaller blocks (2 million, about 150 MB of tree),
# so that the process of the layer stays under 1,300 MB on BRA (COMMAND 117).
_RIVER_BLOCK_VERTICES = 2_000_000
_SEED_STEP = 32  # every 32nd vertex gives each pixel an upper bound (a real vertex) for the search in the blocks


def _ecef(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Earth-centred Cartesian coordinates (metres) of geodetic points on the WGS84 ellipsoid, shape `(n, 3)`."""
    phi, lam = np.radians(lat), np.radians(lon)
    prime_vertical = _GEOD.a / np.sqrt(1.0 - _GEOD.es * np.sin(phi) ** 2)
    return np.column_stack(
        [
            prime_vertical * np.cos(phi) * np.cos(lam),
            prime_vertical * np.cos(phi) * np.sin(lam),
            prime_vertical * (1.0 - _GEOD.es) * np.sin(phi),
        ]
    )


def densify_step_deg(grid: GridContext) -> float:
    """The `segmentize` step in degrees: 100 m along a meridian, shortened where a degree of longitude is longer, over the latitudes of the grid.

    A segment of this many degrees measures at most `_DENSIFY_M` metres in any direction, so the distance to a densified line differs from the
    distance to the line by at most s^2 / (8 D) (s the step, D the distance to the line).
    """
    south = grid.transform.f + grid.transform.e * grid.height
    north = grid.transform.f
    lat_km, lon_km = wgs84_km_per_degree(np.linspace(min(south, north), max(south, north), 33))
    return _DENSIFY_M / 1000.0 / float(max(lat_km.max(), lon_km.max()))


def feature_vertices(
    geometries, grid: GridContext, *, within_country: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude (float64) of the points a distance to `geometries` is measured to, without rasterizing them.

    A point is itself; a line is densified to at most 100 m between vertices (`densify_step_deg`) and contributes its vertices; a polygon
    contributes the vertices of its rings. A vertex counts when the pixel that contains it is on the grid and, with `within_country`, in the
    country mask: the rule by which a burnt pixel outside the country mask was dropped (roads, grid, substations), a pixel outside the grid never
    having been burnt (rivers: `within_country=False`). The features go `_FEATURE_CHUNK` at a time, and the vertices of a chunk that are exactly
    equal to one another are kept once (a vertex shared by two chunks stays twice: the distance does not change, only the count).

    Implements: M-F2a-03.
    """
    step = densify_step_deg(grid)
    transform = grid.transform
    lons: list[np.ndarray] = []
    lats: list[np.ndarray] = []
    values = np.asarray(geometries.values if hasattr(geometries, "values") else geometries, dtype=object)
    for start in range(0, len(values), _FEATURE_CHUNK):
        chunk = shapely.segmentize(values[start : start + _FEATURE_CHUNK], step)
        coords = shapely.get_coordinates(chunk)
        if not len(coords):
            continue
        col = np.floor((coords[:, 0] - transform.c) / transform.a).astype(np.int64)
        row = np.floor((coords[:, 1] - transform.f) / transform.e).astype(np.int64)
        keep = (col >= 0) & (col < grid.width) & (row >= 0) & (row < grid.height)
        if within_country:
            keep[keep] = grid.country_mask[row[keep], col[keep]]
        xy = np.ascontiguousarray(coords[keep])
        if len(xy):
            # exactly equal vertices (the end shared by two neighbouring features) are one target; no distinct vertex is touched
            _, first = np.unique(xy.view(np.dtype((np.void, 16))).ravel(), return_index=True)
            first.sort()
            xy = xy[first]
        lons.append(xy[:, 0].copy())
        lats.append(xy[:, 1].copy())
        del chunk, coords, xy
    if not lons:
        return np.empty(0), np.empty(0)
    lon_all = np.concatenate(lons)
    del lons
    lat_all = np.concatenate(lats)
    return lon_all, lat_all


def geodesic_distance_to_vertices(
    lon: np.ndarray,
    lat: np.ndarray,
    grid: GridContext,
    *,
    checkpoint_dir: Path | str | None = None,
    checkpoint_key: str | None = None,
    strip_rows: int = _STRIP_ROWS,
    block_vertices: int = _BLOCK_VERTICES,
) -> np.ndarray:
    """Distance in km from the centre of each country pixel to the nearest of the points `lon`, `lat`, on the WGS84 ellipsoid.

    The nearest point is found by nearest neighbour among the points in Earth-centred coordinates (a `cKDTree`); the distance is the WGS84
    geodesic (`pyproj.Geod`) from the pixel centre to that point alone, never an approximation. The chord and the geodesic order the points
    the same way except between points whose distances differ by less than about 1e-6 of the distance. Pixels outside the country mask are NaN.

    With at most `block_vertices` points there is one tree and the rows go `strip_rows` at a time; with a checkpoint directory and the key of the
    layer, the strips an interrupted run finished are taken from it (core/checkpoint.py), and the tree is not built when every strip is done.
    With more points they are split in blocks of `block_vertices`: one tree is alive at a time, and for every country pixel the vertex with the
    smallest chord (the first one on a tie) is kept across the blocks; the geodesic is then computed once, to that winner. The checkpoint keeps
    the state (winner and chord of every pixel) after each block. Either way the result is the same.

    Implements: M-F2a-03.
    """
    if not len(lon):
        raise ValueError("no point to measure the distance to")
    if block_vertices < 1:
        raise ValueError("block_vertices must be positive")
    transform = grid.transform
    out = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
    store = None
    if checkpoint_dir is not None and checkpoint_key is not None:
        store = CheckpointStore(
            checkpoint_dir,
            make_key(
                layer=checkpoint_key, strip_rows=strip_rows, block_vertices=block_vertices, points=digest_inputs(lon, lat)
            ),
            label="distance",
        )
    if len(lon) <= block_vertices:
        tree = None
        for r0 in range(0, grid.height, strip_rows):
            r1 = min(grid.height, r0 + strip_rows)
            rr, cc = np.nonzero(grid.country_mask[r0:r1])
            if not len(rr):
                continue
            unit = f"strip_{r0:08d}"
            stored = store.load_arrays(unit) if store is not None else None
            if stored is not None and stored[0]["d"].shape == (len(rr),):
                out[r0 + rr, cc] = stored[0]["d"]
                continue
            if tree is None:
                tree = cKDTree(_ecef(lon, lat), balanced_tree=False)
            centre_lon = transform.c + (cc + 0.5) * transform.a
            centre_lat = transform.f + (r0 + rr + 0.5) * transform.e
            _, nearest = tree.query(_ecef(centre_lon, centre_lat))
            metres = _GEOD.inv(centre_lon, centre_lat, lon[nearest], lat[nearest])[2]
            strip = (metres / 1000.0).astype(np.float32)
            out[r0 + rr, cc] = strip
            if store is not None:
                store.save_arrays(unit, {"d": strip})
        return out

    # several blocks: the winner of each country pixel (index of the vertex and chord to it) over the blocks, in the order of the pixels by row
    pixels = np.flatnonzero(grid.country_mask.ravel())
    first_of_row = np.searchsorted(pixels, np.arange(0, grid.height + strip_rows, strip_rows) * grid.width)
    n_blocks = -(-len(lon) // block_vertices)

    def centres(lo: int, hi: int) -> np.ndarray:
        rows, cols = np.divmod(pixels[lo:hi], grid.width)
        return _ecef(transform.c + (cols + 0.5) * transform.a, transform.f + (rows + 0.5) * transform.e)

    done = 0
    stored = store.load_arrays("state") if store is not None else None
    if stored is not None and stored[0]["chord"].shape == (len(pixels),):
        best_chord, best_vertex, done = stored[0]["chord"], stored[0]["vertex"], int(stored[1]["blocks_done"])
    else:
        # Every pixel starts with a real vertex (every `_SEED_STEP`-th one) and its chord: an upper bound of the nearest chord that is never below
        # it. A block is then searched only within the largest bound of the strip (`distance_upper_bound`), which a tree far from a pixel cannot
        # otherwise tell: it would visit most of its nodes. A vertex that is not nearer than the bound cannot be the nearest, so the result is the
        # same as without the bound.
        seeds = np.arange(0, len(lon), _SEED_STEP)
        seed_tree = cKDTree(_ecef(lon[seeds], lat[seeds]), balanced_tree=False)
        best_chord = np.empty(len(pixels))
        best_vertex = np.empty(len(pixels), dtype=np.int64)
        for k in range(len(first_of_row) - 1):
            lo, hi = first_of_row[k], first_of_row[k + 1]
            if lo < hi:
                best_chord[lo:hi], nearest = seed_tree.query(centres(lo, hi))
                best_vertex[lo:hi] = seeds[nearest]
        del seed_tree
    for block in range(done, n_blocks):
        a, b = block * block_vertices, min(len(lon), (block + 1) * block_vertices)
        tree = cKDTree(_ecef(lon[a:b], lat[a:b]), balanced_tree=False)
        for k in range(len(first_of_row) - 1):
            lo, hi = first_of_row[k], first_of_row[k + 1]
            if lo == hi:
                continue
            bound = float(best_chord[lo:hi].max()) * (1.0 + 1e-12) + 1e-9
            chord, nearest = tree.query(centres(lo, hi), distance_upper_bound=bound)
            better = chord < best_chord[lo:hi]  # a vertex beyond the bound has chord inf: never better
            best_chord[lo:hi][better] = chord[better]
            best_vertex[lo:hi][better] = nearest[better] + a
        del tree
        if store is not None:
            store.save_arrays("state", {"chord": best_chord, "vertex": best_vertex}, {"blocks_done": block + 1}, compress=False)
    for k in range(len(first_of_row) - 1):
        lo, hi = first_of_row[k], first_of_row[k + 1]
        if lo == hi:
            continue
        rows, cols = np.divmod(pixels[lo:hi], grid.width)
        centre_lon = transform.c + (cols + 0.5) * transform.a
        centre_lat = transform.f + (rows + 0.5) * transform.e
        winner = best_vertex[lo:hi]
        out[rows, cols] = (_GEOD.inv(centre_lon, centre_lat, lon[winner], lat[winner])[2] / 1000.0).astype(np.float32)
    return out


def distance_capped_path(distance_path) -> Path:
    """Path of the `distance_capped` flag raster written beside a distance raster (M-F2a-03, OQ-040)."""
    distance_path = Path(distance_path)
    return distance_path.with_name(f"{distance_path.stem}_capped{distance_path.suffix}")


def _write_distance_and_flag(
    dist_km: np.ndarray, out_path, grid: GridContext, distance_cap_km: float
) -> None:
    """Write the raw geodesic distance raster and its `distance_capped` flag raster.

    OQ-040 (METHODOLOGY 1.4.0, M-F2a-03): the distance is stored as computed, never truncated, because the
    connection-cost model bills the real distance. `distance_cap_km` is only the threshold of the flag
    (uint8: 1 where distance > threshold, 0 elsewhere, nodata outside the country), a quality indicator.
    """
    flag = np.where(dist_km > distance_cap_km, 1, 0).astype(np.uint8)
    flag[~grid.country_mask] = NODATA_UINT8
    dist_km = dist_km.copy()
    dist_km[~grid.country_mask] = NODATA_FLOAT
    common = {
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(
        out_path, driver="GTiff", dtype="float32", nodata=NODATA_FLOAT, **common
    ) as dst:
        dst.write(dist_km, 1)
    with safe_raster_write(
        distance_capped_path(out_path), driver="GTiff", dtype="uint8", nodata=NODATA_UINT8, **common
    ) as dst:
        dst.write(flag, 1)


def rasterize_linear_distance(
    gdf: gpd.GeoDataFrame | None,
    out_path,
    country_gdf: gpd.GeoDataFrame,
    grid: GridContext,
    label: str,
    distance_cap_km: float,
    checkpoint_dir: Path | str | None = None,
    checkpoint_key: str | None = None,
) -> object | None:
    """Write the geodesic distance from each country pixel to the nearest feature (lines, or points), and its `distance_capped` flag raster.

    The features are not rasterized: the distance is measured to their exact vertices (points as they are, lines densified to 100 m), see
    `feature_vertices` and `geodesic_distance_to_vertices` (M-F2a-03).

    Shared by both `roads` (gdf already clipped via
    read_clipped_to_country(), see module docstring) and `grid` (gdf
    from load_vector_bbox()) — legacy used one function
    (`_align_linear_features()`) for both, this preserves that.

    Args:
        gdf: Already-loaded vector data (roads: exactly clipped to the
            country polygon; grid: bbox-prefiltered only), or None.
        out_path: Output path for the distance raster.
        country_gdf: Country GeoDataFrame (for the STRtree intersects
            filter and the final country-mask mirrors legacy's use of
            `mainland_geometry`).
        grid: Target GridContext.
        label: Feature-type label for logging.
        distance_cap_km: Threshold of the `distance_capped` flag raster written beside the distance raster, in
            kilometres (M-F2a-03). It never truncates the stored distance (OQ-040, METHODOLOGY 1.4.0): the
            connection-cost model bills the real distance. No default, so the value stays visible at every call site.
        checkpoint_dir: With `checkpoint_key`, where the strips of rows already computed by an interrupted run are kept (core/checkpoint.py).
        checkpoint_key: The validity key of the layer.

    Returns:
        Path to the output distance raster, or None if gdf is empty/None
        or no feature intersects the country.
    """
    if gdf is None or gdf.empty:
        return None

    try:
        tree = STRtree(gdf.geometry.values)
        intersect_indices = tree.query(country_union(country_gdf), predicate="intersects")
        if len(intersect_indices) == 0:
            return None

        lon, lat = feature_vertices(gdf.geometry.iloc[intersect_indices], grid, within_country=True)
        del tree, gdf
        if not len(lon):
            return None

        dist_km = geodesic_distance_to_vertices(lon, lat, grid, checkpoint_dir=checkpoint_dir, checkpoint_key=checkpoint_key)
        del lon, lat
        _write_distance_and_flag(dist_km, out_path, grid, distance_cap_km)

        return out_path
    except Exception as e:  # noqa: BLE001 — one bad layer must not abort alignment
        logger.error("    [%s] Topology processing failed: %s", label, e)
        return None


def align_lakes(lakes_gdf: gpd.GeoDataFrame | None, out_path, grid: GridContext) -> object | None:
    """Rasterize inland water bodies as a binary hard-exclusion mask.

    Args:
        lakes_gdf: Already-clipped lakes GeoDataFrame (via
            read_clipped_to_country(), see module docstring), or None.
        out_path: Output path for the lake mask raster.
        grid: Target GridContext.

    Returns:
        Path to the output mask raster, or None if no lakes were found.
    """
    if lakes_gdf is None or lakes_gdf.empty:
        return None

    shapes = [(mapping(g), 1) for g in lakes_gdf.geometry if g and not g.is_empty]
    if not shapes:
        return None

    lake_mask = rasterize(
        shapes=shapes,
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    lake_mask[~grid.country_mask] = NODATA_UINT8

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": NODATA_UINT8,
        "compress": "lzw",
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(lake_mask, 1)
    return out_path


def align_rivers(
    rivers_gdf: gpd.GeoDataFrame | None,
    out_path,
    grid: GridContext,
    distance_cap_km: float,
    checkpoint_dir: Path | str | None = None,
    checkpoint_key: str | None = None,
) -> object | None:
    """Write the geodesic distance from each country pixel to the nearest river (exact vertices of the densified lines), and its flag raster.

    Deliberately NOT unified with rasterize_linear_distance() on the
    STRtree-prefilter/country-mask structural asymmetry — see module
    docstring for that. The distance CAP, however, was unified 2026-09-09
    (see docs/_archive/2026-09/DECISIONS.md same date, grid_alignment Passo 4 item 2):
    this used to hardcode a separate 50km inline, diverging from roads/
    grid's 100km with no documented reason; callers now pass the same
    value used for roads/grid, same "explicit, no default" convention
    as rasterize_linear_distance().

    Args:
        rivers_gdf: Already-clipped rivers GeoDataFrame (via
            read_clipped_to_country(), see module docstring), or None.
        out_path: Output path for the river distance raster.
        grid: Target GridContext.
        distance_cap_km: Threshold of the `distance_capped` flag raster, in kilometres — see
            rasterize_linear_distance()'s docstring.
        checkpoint_dir: See rasterize_linear_distance().
        checkpoint_key: See rasterize_linear_distance().

    Returns:
        Path to the output distance raster, or None if no rivers were found.
    """
    if rivers_gdf is None or rivers_gdf.empty:
        return None

    lon, lat = feature_vertices(rivers_gdf.geometry, grid, within_country=False)
    del rivers_gdf  # the vector (about 400 MB for BRA) is not needed once its vertices are: its reference here is the last one
    if not len(lon):
        return None

    dist_km = geodesic_distance_to_vertices(
        lon, lat, grid, checkpoint_dir=checkpoint_dir, checkpoint_key=checkpoint_key, block_vertices=_RIVER_BLOCK_VERTICES
    )
    del lon, lat
    _write_distance_and_flag(dist_km, out_path, grid, distance_cap_km)
    return out_path
