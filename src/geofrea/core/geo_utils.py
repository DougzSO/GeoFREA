"""Shared geometry helpers used across phases.

Ported from geoworld_framework's src/utils/utils.py (get_local_utm_crs)
and src/processors/data_auditor.py (get_mainland_gdf, detect_island_nation)
— generic geometry operations, not audit-specific, so they live in core/
rather than in data_quality_audit/ (grid_alignment and later phases will
also need mainland/UTM handling). See DECISIONS.md 2026-08-20 -
orchestrator + data_quality_audit phase.

clip_vector_to_country() was added 2026-08-24 (see DECISIONS.md same
date - vector layer audit depth). It is a fresh implementation, not a
literal extraction from raster_inspection.py::inspect_land_cover_tiles:
that function's bbox-prefilter + intersection is tightly coupled to
raster windowed reads and per-class pixel accounting, not reusable for
vector data as-is. What IS reused is the *pattern* — bbox prefilter
before an exact geometry intersection — which both
inspect_land_cover_tiles() and geoworld_framework's
criteria_builder.py::compute_protected_areas() already use independently
(the latter via gdf.intersects(mainland_union) then
geometry.intersection(mainland_union), without an explicit bbox
prefilter step). clip_vector_to_country() adds the bbox prefilter
(gdf.cx[]) as a fast first pass, matching inspect_land_cover_tiles()'s
two-step shape more closely than compute_protected_areas() does.

read_clipped_to_country() was added 2026-08-25 (see DECISIONS.md same
date - data_acquisition activation, its clip performance-validation
finding): clip_vector_to_country() alone still requires the ENTIRE
source file loaded into memory first (its own gdf.cx[] prefilter runs
on an already-fully-read GeoDataFrame) — fine for the small synthetic
fixtures every existing caller was tested against, but real HydroLAKES
(820 MB, ~1.4M features) makes that first full read itself the
bottleneck, independent of how fast the clip step is afterward.
read_clipped_to_country() pushes the bbox filter down to the read
itself (gpd.read_file(path, bbox=...)), which GDAL/OGR can satisfy
using the file's own spatial index (confirmed live: shapefiles here
report `fast_spatial_filter: True` via pyogrio.read_info()) without
materializing out-of-bbox features in Python at all — clip_vector_to_
country() still runs afterward for the exact (non-rectangular)
intersection, on the now much smaller bbox-prefiltered result. This
does not replace clip_vector_to_country() — callers that already have
an in-memory GeoDataFrame (e.g. from a source that isn't a lazily-
opened file) still use it directly.

clip_vector_to_country()'s exact-intersection step was rewritten
2026-08-25 to use shapely.STRtree instead of a plain vectorized
.intersects() call (see DECISIONS.md same date, "clip_vector_to_
country() exact-intersection bottleneck (STRtree fix)" for the full
profiling that led here). Confirmed live against real HydroRIVERS/BRA
data + the real GADM Brazil boundary (311,499 vertices after
get_mainland_gdf()): the rectangular gdf.cx[] prefilter alone barely
helps for a geometrically large/irregular country like Brazil (its
bounding box alone captured 74% of ALL features in the South-America
tile) — what actually made the naive approach catastrophically slow
was testing every remaining candidate's .intersects() against that
one large, complex polygon with no spatial index: measured ~150
features/s. shapely.prepare() on the polygon did NOT help (same rate —
the GEOS vectorized ufunc path does not appear to benefit from a
pre-prepared scalar operand the way a per-row prepared-geometry loop
would). shapely.STRtree(candidates).query(country_geom,
predicate="intersects") measured ~300,000 features/s on the same real
data — roughly a 2000x difference — because STRtree's own internal
indexed traversal (not just a single bounding-box prefilter) prunes
candidates BEFORE running the expensive exact predicate, whereas the
naive approach ran the expensive predicate against literally every
bbox-surviving candidate. The subsequent .intersection() (computing
the actual cut geometry, not just yes/no) still runs on the
STRtree-matched subset only — much smaller than the full candidate
set, and prepared geometries don't accelerate geometry-producing ops
the way they do predicates, so no further indexing was applied there.

country_geom simplification, 2026-08-25 (same session as the STRtree
fix above, added right after it): the STRtree fix made the membership
*test* fast (seconds, not hours) but did not fix a second, independent
cost — computing the actual `.intersection()` geometry for every
matched feature. Confirmed live this was NOT a bug: real Brazil
legitimately matches ~772,870 of the ~1.2M bbox-prefiltered HydroRIVERS
`sa`-tile candidates (~48% of the whole continental tile) — verified
by checking country_geom's own computed area (8,711,743 km2 vs
Brazil's real ~8,515,767 km2, a normal ~2.3% GADM-vs-official
difference, not an accidental South-America-wide geometry) and its
bounds (matching Brazil's real extent, not the continent's). Real
country boundaries can be extremely vertex-dense (Brazil: 311,499
vertices after get_mainland_gdf()) — measured live that .intersection()
against the unsimplified polygon ran at ~40 features/s, which at
~772,870 matches would be ~5.4 hours, an order of magnitude worse than
the STRtree fix's own 300,000 features/s for the predicate check alone.
shapely.simplify(country_geom, tolerance=0.001, preserve_topology=True)
— applied only to the clip boundary, never to the candidate features'
own geometries (that would alter real returned data, not just the
exclusion mask) — measured live: 311,499 -> 19,758 vertices (6.34% of
original), .intersection() speed 40 -> 851 features/s (~21x), computed
area distortion 0.0005% (8,711,743 vs 8,711,785 km2) — negligible for
country-scale statistics/exclusion masks, not a meaningful precision
loss for this use case. 0.001 degrees (~111m at the equator) is applied
for geographic CRSs; an equivalent ~100m tolerance is applied for
projected CRSs (meters), via _simplify_for_intersection()'s
crs.is_geographic check — clip_vector_to_country() itself still accepts
"any CRS" per its own docstring, so a fixed degrees-only tolerance would
have been wrong for a projected-CRS caller.

Threaded .intersection(), 2026-08-25 (same session, added right after
the simplification fix above): even simplified, .intersection() on
Brazil's real ~772,846 matched rivers features measured 1223s (~20.4
min, ~632 features/s) — simplification made it ~21x faster than
unsimplified, but a large/complex country's worst case was still
minutes, not seconds. Confirmed live (not assumed) that shapely 2.0
releases the GIL during its GEOS C calls: splitting the same real
matched-feature array into N chunks and running shapely.intersection()
on each chunk in a separate Python thread (concurrent.futures.
ThreadPoolExecutor — threads, not processes: geometries are complex
Python/GEOS objects, expensive to pickle across a process boundary,
and threads need no such serialization since they share memory)
measured near-linear speedup up to the machine's physical core count:
4 workers -> 3.83x, 8 workers (= physical cores here) -> 7.08x, 16
workers (= logical/hyperthreaded) -> 8.93x, diminishing past 8 as
expected for CPU-bound work sharing physical cores. Every threaded run
produced results identical to the single-threaded baseline (verified
geometry-by-geometry, not just row counts). _intersection_threaded()
below is only used above a minimum candidate count
(_THREADED_INTERSECTION_MIN_FEATURES) — thread-pool setup/chunking
overhead is not worth it for the small candidate counts every existing
non-Brazil-scale caller and test fixture actually has.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, NamedTuple

import geopandas as gpd
import numpy as np
import pyogrio
import shapely


class GeometryRepairReport(NamedTuple):
    """Traceability record for invalid-geometry repair on a clip path.

    Moved here 2026-09-21 from suitability_criteria's WDPA-only
    `WdpaGeometryRepairReport` (see docs/phases/core.md, docs/phases/
    F2b_siting_layers.md) so every caller of `clip_vector_to_country()`/
    `read_clipped_to_country()` gets the same repair, not just
    `compute_protected_areas()`. Real-world vector data (WDPA confirmed
    live: BRA 383/4190, PRT 61/442) legitimately contains topologically
    invalid polygons (self-intersections) — a known dataset
    characteristic, not evidence of a truncated/corrupted download.

    Args:
        n_total: Feature count in `gdf` as passed in.
        n_invalid: How many of those were topologically invalid
            (`shapely.is_valid` False) before repair.
        n_repaired: Of `n_invalid`, how many are valid after
            `shapely.make_valid(method="structure")` — almost always
            equal to `n_invalid`; lower only if make_valid itself
            produced a still-invalid result (rare, reported so it is
            never silently assumed away).
        n_dropped_empty: Feature rows dropped because their geometry
            was (or became, after repair) empty.
        invalid_reasons: `shapely.is_valid_reason()` on the invalid
            subset, summarized by category (the text before the
            coordinate-bearing `[...]` suffix, e.g. "Self-intersection")
            with per-category counts — not the raw per-feature strings,
            which each carry unique coordinates.
        country_polygon_repaired: Whether the clip boundary itself
            (the simplified country polygon) needed repair after
            `shapely.simplify()` — see `_simplify_for_intersection()`'s
            pre-simplify repair, which this reports on the post-simplify
            side. False for every caller that supplies a well-formed
            country boundary (the common case).
    """

    n_total: int
    n_invalid: int
    n_repaired: int
    n_dropped_empty: int
    invalid_reasons: dict[str, int]
    country_polygon_repaired: bool


_EMPTY_GEOMETRY_REPAIR_REPORT = GeometryRepairReport(0, 0, 0, 0, {}, False)


def repair_invalid_geometries(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, GeometryRepairReport]:
    """Repair topologically invalid geometries in `gdf`, in place semantics aside.

    `shapely.make_valid(method="structure")`: chosen over the "linework"
    default and over `buffer(0)` — live-verified 2026-09-11 against real
    WDPA data that "linework" throws `GEOSException:
    IllegalArgumentException: Overlay input is mixed-dimension` on a
    real subset of invalid polygons, while "structure" (reasoning from
    ring exterior/hole structure rather than noding all edges) handled
    every invalid geometry in both BRA (383/383) and PRT (61/61)
    without error. Requires GEOS >= 3.10.

    Args:
        gdf: Any GeoDataFrame. Not mutated — a new frame is returned.

    Returns:
        (repaired_gdf, GeometryRepairReport). `repaired_gdf` has had
        invalid geometries replaced by their `make_valid()` result and
        any now-empty (or already-empty) rows dropped.
    """
    n_total = len(gdf)
    gdf = gdf.copy()

    invalid_mask = ~gdf.geometry.is_valid
    n_invalid = int(invalid_mask.sum())

    invalid_reasons: dict[str, int] = {}
    n_repaired = 0
    if n_invalid:
        invalid_geoms = gdf.loc[invalid_mask, "geometry"]
        for reason in shapely.is_valid_reason(invalid_geoms.to_numpy()):
            category = reason.split("[")[0].strip()
            invalid_reasons[category] = invalid_reasons.get(category, 0) + 1

        repaired_geoms = shapely.make_valid(invalid_geoms.to_numpy(), method="structure")
        gdf.loc[invalid_mask, "geometry"] = repaired_geoms
        n_repaired = int(shapely.is_valid(repaired_geoms).sum())

    n_before_drop = len(gdf)
    gdf = gdf[~gdf.geometry.is_empty]
    n_dropped_empty = n_before_drop - len(gdf)

    report = GeometryRepairReport(
        n_total=n_total,
        n_invalid=n_invalid,
        n_repaired=n_repaired,
        n_dropped_empty=n_dropped_empty,
        invalid_reasons=invalid_reasons,
        country_polygon_repaired=False,
    )
    return gdf, report


def get_local_utm_crs(geometry: Any) -> str:
    """Compute the local UTM EPSG code from the centroid of a geometry.

    Args:
        geometry: Shapely geometry, GeoSeries, or GeoDataFrame.

    Returns:
        EPSG code string for the local UTM zone (e.g. "EPSG:32629").
    """
    if isinstance(geometry, gpd.GeoDataFrame):
        geometry = (
            geometry.geometry.union_all()
            if hasattr(geometry.geometry, "union_all")
            else geometry.geometry.unary_union
        )

    if not isinstance(geometry, gpd.GeoSeries):
        geometry = gpd.GeoSeries([geometry], crs="EPSG:4326")

    centroid = (
        geometry.union_all().centroid
        if hasattr(geometry, "union_all")
        else geometry.unary_union.centroid
    )

    lon = centroid.x
    lat = centroid.y

    utm_zone = int((lon + 180) // 6) + 1
    hemisphere = 326 if lat >= 0 else 327

    return f"EPSG:{hemisphere}{utm_zone:02d}"


def get_mainland_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame containing only the largest polygon (mainland).

    Removes islands, enclaves, and fragments before any analysis.

    Args:
        gdf: Full country GeoDataFrame.

    Returns:
        Single-row GeoDataFrame with the largest polygon, in EPSG:4326.
    """
    union = (
        gdf.geometry.union_all()
        if hasattr(gdf.geometry, "union_all")
        else gdf.geometry.unary_union
    )

    utm_crs = get_local_utm_crs(union)
    exploded = gdf.to_crs(utm_crs).explode(index_parts=False).reset_index(drop=True)
    idx = exploded.geometry.area.idxmax()

    return exploded.iloc[[idx]].to_crs("EPSG:4326")


def detect_island_nation(gdf: gpd.GeoDataFrame, threshold_pct: float = 0.60) -> bool:
    """Detect whether get_mainland_gdf() would discard too much territory.

    Args:
        gdf: Country GeoDataFrame.
        threshold_pct: Fraction threshold above which the country is
            considered an island nation (default 0.60).

    Returns:
        True if the largest polygon represents less than (1 - threshold_pct)
        of total territory, indicating that mainland-only filtering would
        discard a large share of the country's actual territory.
    """
    try:
        union = (
            gdf.geometry.union_all()
            if hasattr(gdf.geometry, "union_all")
            else gdf.geometry.unary_union
        )
        utm_crs = get_local_utm_crs(union)
        gdf_proj = gdf.to_crs(utm_crs)
        exploded = gdf_proj.explode(index_parts=False).reset_index(drop=True)

        total_area = float(exploded.geometry.area.sum())
        largest_area = float(exploded.geometry.area.max())

        if total_area == 0:
            return False

        largest_pct = largest_area / total_area
        return largest_pct < (1.0 - threshold_pct)

    except Exception:  # noqa: BLE001 — diagnostic-only helper, never fatal (matches legacy)
        return False


def load_mainland_boundary(path: str | Path) -> gpd.GeoDataFrame:
    """Read a country-boundary vector file and reduce it to its mainland polygon.

    Mechanical read + get_mainland_gdf() only — no None-handling, no
    fallback. Extracted 2026-09-08 (see docs/DECISIONS.md same date,
    grid_alignment orchestrator wiring) from
    data_acquisition/adapter.py's `_load_mainland_boundary()`, which
    grid_alignment/adapter.py now also needs — the two callers differ
    on what to do when the boundary is MISSING (data_acquisition's
    adapter degrades to country_gdf=None; grid_alignment's raises,
    see GridAlignmentRequiresBordersError), so that decision stays in
    each caller; this function only does the part both share.

    Args:
        path: Path to the country-boundary vector file (all polygons —
            mainland, islands, enclaves).

    Returns:
        Single-row GeoDataFrame with the largest polygon, in EPSG:4326.
    """
    return get_mainland_gdf(gpd.read_file(path))


# ~111m at the equator (geographic CRSs) / ~100m (projected CRSs, in
# CRS units, assumed meters) — see module docstring, "country_geom
# simplification, 2026-08-25", for the measured speed/precision
# trade-off this specific value was chosen from (21x faster
# .intersection(), 0.0005% area distortion on real Brazil data).
_SIMPLIFY_TOLERANCE_DEG = 0.001
_SIMPLIFY_TOLERANCE_M = 100.0


def _simplify_for_intersection(geom: Any, crs: Any) -> tuple[Any, bool]:
    """Simplify a clip-boundary geometry before using it in `.intersection()`.

    Only ever applied to the COUNTRY polygon (the clip boundary), never
    to the candidate features being clipped — simplifying the data
    itself would silently alter what's returned, not just how fast the
    exclusion mask is computed. See module docstring for the full
    rationale and the real-data measurements behind the tolerance
    values.

    Args:
        geom: The (already unioned) country geometry.
        crs: The CRS `geom` is in — determines whether the degrees or
            meters tolerance applies. `clip_vector_to_country()`
            accepts "any CRS", so this cannot hardcode one unit.

    Returns:
        (simplified_geom, repaired): a simplified, topology-preserving
        version of `geom`, and whether either the pre-simplify input or
        the post-simplify output needed repair. Invalid input is
        repaired (`buffer(0)`) before simplification — GEOS
        simplification of an invalid geometry can itself produce
        invalid or unexpected output — and the simplified result is
        checked again afterward and repaired the same way if still
        invalid, since `shapely.simplify()` is not itself guaranteed to
        preserve validity in every case.
    """
    repaired = False
    if not shapely.is_valid(geom):
        geom = geom.buffer(0)
        repaired = True

    is_geographic = crs is not None and crs.is_geographic
    tolerance = _SIMPLIFY_TOLERANCE_DEG if is_geographic else _SIMPLIFY_TOLERANCE_M
    simplified = shapely.simplify(geom, tolerance=tolerance, preserve_topology=True)

    if not shapely.is_valid(simplified):
        simplified = simplified.buffer(0)
        repaired = True

    return simplified, repaired


# Below this many candidate geometries, thread-pool setup/chunking
# overhead is not worth it — every existing non-Brazil-scale caller and
# test fixture stays well under this and just takes the plain
# single-threaded path. See module docstring, "Threaded .intersection(),
# 2026-08-25".
_THREADED_INTERSECTION_MIN_FEATURES = 10_000

# Cap on thread-pool workers, 2026-08-25 (Douglas's explicit adjustment
# after reviewing the real numbers): the measured speedup saturates
# past physical core count — on the dev machine (8 physical / 16
# logical cores), 4->8 workers gained +1.85x, but 8->16 only gained a
# further +1.26x. os.cpu_count() returns LOGICAL cores, which on a
# shared/CI environment can overstate real available parallelism (and
# is what earlier let this default to 16 on the dev machine). There is
# no portable, dependency-free way to query physical core count alone
# (that needs e.g. psutil, not currently a project dependency) — a
# fixed cap of 8 is the simple fallback Douglas asked for instead:
# min(os.cpu_count(), 8) rather than os.cpu_count() unconditionally.
_MAX_INTERSECTION_WORKERS = 8


def _intersection_threaded(geoms: np.ndarray, clip_geom: Any) -> np.ndarray:
    """Compute `shapely.intersection(geoms, clip_geom)`, parallelized across threads.

    Falls back to the plain single-threaded vectorized call below
    _THREADED_INTERSECTION_MIN_FEATURES. See module docstring for the
    real-data speedup measurements (near-linear up to physical core
    count, diminishing beyond it) and why threads, not processes.

    Args:
        geoms: Array of candidate geometries (already STRtree-matched —
            this does no membership filtering itself).
        clip_geom: The (already simplified) clip boundary.

    Returns:
        Array of intersection geometries, same order/length as `geoms`.
    """
    if len(geoms) < _THREADED_INTERSECTION_MIN_FEATURES:
        return shapely.intersection(geoms, clip_geom)

    n_workers = min(os.cpu_count() or 1, _MAX_INTERSECTION_WORKERS)
    chunks = np.array_split(geoms, n_workers)
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(lambda chunk: shapely.intersection(chunk, clip_geom), chunks))
    return np.concatenate(results)


def clip_vector_to_country(
    gdf: gpd.GeoDataFrame, country_gdf: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, GeometryRepairReport]:
    """Clip a GeoDataFrame's geometries to a country polygon.

    Two-step strategy: a fast bounding-box prefilter (gdf.cx[]) before
    the exact geometry intersection, so a huge global file (HydroLAKES,
    HydroRIVERS, WDPA) is not intersected feature-by-feature against
    the full country geometry when most features are nowhere near it.
    See module docstring for how this relates to
    inspect_land_cover_tiles() and compute_protected_areas().

    The exact-intersection membership test uses shapely.STRtree, not a
    plain vectorized `.intersects(country_geom)` — see module
    docstring ("clip_vector_to_country()'s exact-intersection step was
    rewritten 2026-08-25") for why: the bbox prefilter above alone is
    not enough for a geometrically large/irregular country (a
    rectangle is a loose bound), and the naive vectorized predicate
    against one large complex polygon measured ~150 features/s on real
    data (Brazil) versus ~300,000 features/s via STRtree — confirmed,
    not assumed.

    `country_geom` is also simplified (shapely.simplify(),
    preserve_topology=True) before being used in `.intersection()` —
    see module docstring ("country_geom simplification, 2026-08-25")
    for why STRtree alone was not enough: real Brazil boundary data has
    311,499 vertices, and a large/complex country like Brazil legitimately
    matches a large fraction of a continental river dataset (confirmed,
    not a bug — ~48% of the whole HydroRIVERS `sa` tile), so even after
    STRtree cuts the *membership test* to seconds, computing the actual
    cut geometry (`.intersection()`, which does not benefit from
    STRtree/prepared-geometry the way a yes/no predicate does) for
    hundreds of thousands of matched features against an unsimplified
    311K-vertex polygon remained a real bottleneck on its own.

    Above _THREADED_INTERSECTION_MIN_FEATURES matched candidates, the
    final `.intersection()` call itself is parallelized across threads
    (see module docstring, "Threaded .intersection(), 2026-08-25") —
    confirmed near-linear speedup with real data, since shapely 2.0
    releases the GIL during its GEOS calls.

    Args:
        gdf: Vector layer to clip, any CRS.
        country_gdf: Country polygon(s) to clip against — reprojected
            to gdf's CRS internally if they differ.

    Returns:
        (clipped_gdf, GeometryRepairReport). `clipped_gdf` has
        geometries intersected against the (simplified) country
        polygon; features with no overlap are dropped, and boundary-
        crossing features are cut to the country's extent. Every
        caller's invalid input geometries (`gdf`) are repaired via
        `repair_invalid_geometries()` before the intersection — this is
        unconditional, not opt-in (2026-09-21, see docs/phases/core.md
        — moved here from suitability_criteria's WDPA-only repair so
        every phase using this shared clip path gets it). The report is
        always returned, never just logged, so a caller cannot
        silently miss that a repair happened.
    """
    gdf, feature_repair_report = repair_invalid_geometries(gdf)

    country_in_gdf_crs = (
        country_gdf.to_crs(gdf.crs) if gdf.crs is not None else country_gdf
    )
    country_geom = (
        country_in_gdf_crs.geometry.union_all()
        if hasattr(country_in_gdf_crs.geometry, "union_all")
        else country_in_gdf_crs.geometry.unary_union
    )

    minx, miny, maxx, maxy = country_in_gdf_crs.total_bounds
    prefiltered = gdf.cx[minx:maxx, miny:maxy]

    simplified_country_geom, country_repaired = _simplify_for_intersection(
        country_geom, gdf.crs
    )

    tree = shapely.STRtree(prefiltered.geometry.values)
    matched_positions = tree.query(simplified_country_geom, predicate="intersects")

    clipped = prefiltered.iloc[matched_positions].copy()
    clipped["geometry"] = gpd.GeoSeries(
        _intersection_threaded(clipped.geometry.values, simplified_country_geom),
        index=clipped.index,
        crs=clipped.crs,
    )
    n_before_drop = len(clipped)
    clipped = clipped[~clipped.geometry.is_empty]

    report = feature_repair_report._replace(
        n_dropped_empty=feature_repair_report.n_dropped_empty + (n_before_drop - len(clipped)),
        country_polygon_repaired=country_repaired,
    )
    return clipped, report


def read_clipped_to_country(
    path: str | Path, country_gdf: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, GeometryRepairReport]:
    """Read a vector file pre-filtered to a country's bbox, then exactly clip it.

    See module docstring ("read_clipped_to_country() was added
    2026-08-25") for why this exists alongside clip_vector_to_country()
    rather than replacing it: this is for the common case of clipping a
    large file that hasn't been read into memory yet (e.g. HydroLAKES),
    where the read itself — not the clip — is the bottleneck.

    Args:
        path: Vector file to read. Any format geopandas/pyogrio
            supports; the read-time bbox filter is fastest when the
            format has its own spatial index (e.g. a shapefile's
            .sbn/.sbx sidecars — GDAL reports this via
            pyogrio.read_info()'s `fast_spatial_filter` capability, not
            checked explicitly here since the bbox filter is still
            correct, just not accelerated, without one).
        country_gdf: Country polygon(s) to clip against.

    Returns:
        The same result clip_vector_to_country(gpd.read_file(path),
        country_gdf) would produce — just without ever materializing
        far-away features in memory.
    """
    file_crs = pyogrio.read_info(str(path))["crs"]
    country_in_file_crs = country_gdf.to_crs(file_crs) if file_crs else country_gdf
    bbox = tuple(country_in_file_crs.total_bounds)

    gdf = gpd.read_file(str(path), bbox=bbox)
    return clip_vector_to_country(gdf, country_gdf)
