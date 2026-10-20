"""COMMAND 59 step 1: fraction of the country mask covered by valid data, and file bbox against mask bbox, for every spatial input. Read only.

Usage: python scripts/coverage_audit_59.py ISO3 [ISO3 ...]   -> GEOFREA_DATA_DIR/interim/coverage_audit_59/audit_<ISO3>.json

Definitions (the same for every country, no country name in the logic):
  mask      the contiguous territory used by the pipeline (raw/gadm/<ISO3>/gadm41_<ISO3>_0_mainland.shp)
  samples   a regular lattice of points every 0.05 degree inside the mask (area-representative, the mask is in geographic coordinates)
  gridded   a sample is covered when it lies in the footprint of a native cell that holds a finite value (first time step with data)
  raster    a sample is covered when the raster, read at about 0.01 degree, holds a valid (not nodata, finite) value there
  vector    not a field: the file extent against the mask extent, and the features inside the mask (a missing feature is not missing data)
"""

import json
import re
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import shapely
import xarray as xr

warnings.filterwarnings("ignore")
import os

DATA = Path(os.environ.get("GEOFREA_DATA_DIR", "D:/Douglas/DOUTORADO/GeoFREA_data"))
RAW = DATA / "raw"
STEP = 0.05
OUT = DATA / "interim" / "coverage_audit_59"


def mask_and_samples(iso):
    gdf = gpd.read_file(RAW / f"gadm/{iso}/gadm41_{iso}_0_mainland.shp").to_crs("EPSG:4326")
    geom = gdf.geometry.union_all()
    minx, miny, maxx, maxy = geom.bounds
    xs = np.arange(np.floor(minx / STEP) * STEP + STEP / 2, maxx, STEP)
    ys = np.arange(np.floor(miny / STEP) * STEP + STEP / 2, maxy, STEP)
    gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(geom, gx.ravel(), gy.ravel())
    return geom, gx.ravel()[inside], gy.ravel()[inside]


def bbox_of_mask(geom):
    return [round(v, 4) for v in geom.bounds]


def _contains(file_bbox, mask_bbox, tol=1e-6):
    return bool(
        file_bbox[0] <= mask_bbox[0] + tol
        and file_bbox[1] <= mask_bbox[1] + tol
        and file_bbox[2] >= mask_bbox[2] - tol
        and file_bbox[3] >= mask_bbox[3] - tol
    )


def _region_km2(lat, share_mask):
    """area of the samples that are not covered, in km2 (each sample stands for a 0.05 x 0.05 degree cell)."""
    return float((0.05 * 111.32) ** 2 * np.cos(np.radians(lat[share_mask])).sum())


def gap_summary(sx, sy, covered):
    miss = ~covered
    if not miss.any():
        return {"gap_km2": 0.0, "gap_bbox": None}
    return {
        "gap_km2": round(_region_km2(sy, miss), 0),
        "gap_bbox": [
            round(float(sx[miss].min()), 2),
            round(float(sy[miss].min()), 2),
            round(float(sx[miss].max()), 2),
            round(float(sy[miss].max()), 2),
        ],
    }


def gridded_coverage(path, sx, sy, varname=None):
    with xr.open_dataset(path, decode_times=False, mask_and_scale=True) as ds:
        if varname is None:
            cands = [
                v
                for v in ds.data_vars
                if ds[v].ndim >= 2
                and not v.endswith("bnds")
                and "bnds" not in v
                and "bounds" not in v
            ]
            varname = cands[0]
        da = ds[varname]
        latn = next(d for d in da.dims if d.lower() in ("lat", "latitude", "y"))
        lonn = next(d for d in da.dims if d.lower() in ("lon", "longitude", "x"))
        lat = ds[latn].values.astype(float)
        lon = ds[lonn].values.astype(float)
        lon = np.where(lon > 180, lon - 360, lon)
        other = [d for d in da.dims if d not in (latn, lonn)]
        sl = da.isel({d: 0 for d in other}) if other else da
        a = sl.transpose(latn, lonn).values
        valid = np.isfinite(a)
        if other and not valid.any():
            for i in range(1, min(da.sizes[other[0]], 12)):
                a = da.isel({other[0]: i, **{d: 0 for d in other[1:]}}).transpose(latn, lonn).values
                valid = np.isfinite(a)
                if valid.any():
                    break
    dlat = float(np.median(np.abs(np.diff(lat)))) if len(lat) > 1 else 1.0
    dlon = float(np.median(np.abs(np.diff(lon)))) if len(lon) > 1 else 1.0
    order_lat = np.argsort(lat)
    order_lon = np.argsort(lon)
    lat_s, lon_s = lat[order_lat], lon[order_lon]
    v = valid[np.ix_(order_lat, order_lon)]
    ia = (
        np.clip(np.searchsorted(lat_s, sy), 1, max(len(lat_s) - 1, 1))
        if len(lat_s) > 1
        else np.zeros(len(sy), dtype=int)
    )
    ja = (
        np.clip(np.searchsorted(lon_s, sx), 1, max(len(lon_s) - 1, 1))
        if len(lon_s) > 1
        else np.zeros(len(sx), dtype=int)
    )
    if len(lat_s) > 1:
        ia = np.where(np.abs(lat_s[ia - 1] - sy) < np.abs(lat_s[ia] - sy), ia - 1, ia)
    if len(lon_s) > 1:
        ja = np.where(np.abs(lon_s[ja - 1] - sx) < np.abs(lon_s[ja] - sx), ja - 1, ja)
    footprint = (
        (np.abs(lat_s[ia] - sy) <= dlat / 2 + 1e-9)
        & (np.abs(lon_s[ja] - sx) <= dlon / 2 + 1e-9)
        & v[ia, ja]
    )
    # nearest native cell WITH a value: distance in degrees, tolerance one native cell (the pipeline samples the nearest valid cell)
    from scipy.spatial import cKDTree

    la, lo = np.meshgrid(lat_s, lon_s, indexing="ij")
    tree = cKDTree(np.column_stack([la[v], lo[v]]))
    dist, _ = tree.query(np.column_stack([sy, sx]))
    covered = dist <= max(dlat, dlon) + 1e-9
    fbbox = [
        float(lon.min() - dlon / 2),
        float(lat.min() - dlat / 2),
        float(lon.max() + dlon / 2),
        float(lat.max() + dlat / 2),
    ]
    info = {
        "var": varname,
        "res_deg": [round(dlat, 4), round(dlon, 4)],
        "valid_cells_share": round(float(valid.mean()), 3),
        "footprint_pct": round(100.0 * float(footprint.mean()), 2),
        "max_dist_to_valid_cell_deg": round(float(dist.max()), 3),
    }
    return covered, fbbox, info


def raster_coverage(paths, sx, sy, target_deg=0.01):
    """union over the files of the samples that hold a valid value; decimated read, so a 10 m or 30 m tile costs little."""
    covered = np.zeros(len(sx), dtype=bool)
    fb = None
    infos = []
    for p in paths:
        with rasterio.open(p) as ds:
            b = ds.bounds
            fb = (
                [b.left, b.bottom, b.right, b.top]
                if fb is None
                else [
                    min(fb[0], b.left),
                    min(fb[1], b.bottom),
                    max(fb[2], b.right),
                    max(fb[3], b.top),
                ]
            )
            sel = (sx >= b.left) & (sx < b.right) & (sy > b.bottom) & (sy <= b.top) & ~covered
            if not sel.any():
                continue
            px = abs(ds.transform.a)
            k = max(1, round(target_deg / px))
            h, w = max(1, ds.height // k), max(1, ds.width // k)
            a = ds.read(
                1, out_shape=(h, w), masked=True, resampling=rasterio.enums.Resampling.nearest
            )
            data = np.ma.getdata(a)
            ok = ~np.ma.getmaskarray(a)
            if data.dtype.kind == "f":
                ok &= np.isfinite(data)
            col = np.clip(((sx[sel] - b.left) / (b.right - b.left) * w).astype(int), 0, w - 1)
            row = np.clip(((b.top - sy[sel]) / (b.top - b.bottom) * h).astype(int), 0, h - 1)
            idx = np.where(sel)[0]
            covered[idx] = ok[row, col]
            infos.append((Path(p).name, ds.crs.to_string() if ds.crs else None))
    return covered, fb, {"files": len(paths)}


def vector_extent(path, mask_geom, layer=None):
    import pyogrio

    info = pyogrio.read_info(path, layer=layer)
    fb = list(info["total_bounds"]) if info.get("total_bounds") is not None else None
    return fb, int(info["features"])


def vector_in_mask(path, mask_geom, layer=None):
    import pyogrio

    g = pyogrio.read_dataframe(path, mask=mask_geom, layer=layer, columns=[])
    g = gpd.GeoDataFrame(g, crs="EPSG:4326") if g.crs is None else g.to_crs("EPSG:4326")
    return g


def cell_presence(g, sx, sy, size=1.0):
    """share of the mask's size x size degree cells (those holding a sample) that hold at least one feature (info only)."""
    if g is None or len(g) == 0:
        return 0.0
    cells = {(int(np.floor(x / size)), int(np.floor(y / size))) for x, y in zip(sx, sy)}
    have = set()
    bb = g.geometry.bounds
    for r in bb.itertuples():
        for i in range(int(np.floor(r.minx / size)), int(np.floor(r.maxx / size)) + 1):
            for j in range(int(np.floor(r.miny / size)), int(np.floor(r.maxy / size)) + 1):
                if (i, j) in cells:
                    have.add((i, j))
    return round(len(have) / len(cells), 3)


def audit(iso):
    geom, sx, sy = mask_and_samples(iso)
    mb = bbox_of_mask(geom)
    res = {"iso": iso, "mask_bbox": mb, "samples": len(sx), "inputs": []}

    def add(name, kind, covered=None, fbbox=None, extra=None, files=None):
        row = {
            "input": name,
            "kind": kind,
            "files": files,
            "file_bbox": [round(v, 3) for v in fbbox] if fbbox else None,
            "bbox_contains_mask": _contains(fbbox, mb) if fbbox else None,
        }
        if covered is not None:
            row["coverage_pct"] = round(100.0 * float(covered.mean()), 2)
            row.update(gap_summary(sx, sy, covered))
        if extra:
            row.update(extra)
        res["inputs"].append(row)
        print(iso, name, row.get("coverage_pct"), row.get("bbox_contains_mask"), flush=True)

    # --- gridded climate
    p = RAW / f"era5/{iso}/{iso}_fg10_annual_max.nc"
    if p.exists():
        c, fb, ex = gridded_coverage(p, sx, sy)
        add("ERA5 fg10 annual max (1995-2014)", "gridded", c, fb, ex, 1)
    for label, pat in (
        ("ISIMIP3b", f"isimip3b/{iso}/*.nc"),
        ("CMIP6 (F4)", f"cmip6/{iso}/*.nc"),
        ("W5E5 tasmax", f"w5e5/{iso}/*.nc"),
    ):
        files = sorted(RAW.glob(pat))
        groups = {}
        for f in files:
            m = re.match(r"(.+?)_(historical|ssp\d+)_(\w+?)_" + iso, f.name)
            key = (m.group(3) if m else f.stem.split("_")[-2]) if "w5e5" not in pat else "tasmax"
            groups.setdefault(key, []).append(f)
        for var, fl in sorted(groups.items()):
            worst, wf, fbb, ex = 101.0, None, None, None
            for f in fl:
                try:
                    c, fb, ex2 = gridded_coverage(f, sx, sy)
                except Exception as e:  # noqa: BLE001
                    add(
                        f"{label} {var} {f.name}", "gridded", None, None, {"error": str(e)[:120]}, 1
                    )
                    continue
                pct = 100 * float(c.mean())
                if pct < worst:
                    worst, wf, fbb, ex, cw = pct, f.name, fb, ex2, c
            if wf:
                add(
                    f"{label} {var} (worst of {len(fl)} files: {wf})",
                    "gridded",
                    cw,
                    fbb,
                    ex,
                    len(fl),
                )

    # --- rasters
    gw = RAW / f"gwa/{iso}"
    for prod in ("wind_speed", "weibull_a", "weibull_k", "air_density"):
        for h in (100, 150, 200):
            pm = gw / f"{iso}_{prod}_{h}m_mask.tif"
            p0 = gw / f"{iso}_{prod}_{h}m.tif"
            if prod == "wind_speed" and h != 100:
                continue
            if h != 100 and prod != "weibull_a":
                continue
            for lab, pp in (("country file", p0), ("completed to mask", pm)):
                if pp.exists():
                    c, fb, ex = raster_coverage([pp], sx, sy, 0.01)
                    add(f"GWA {prod} {h} m ({lab})", "raster", c, fb, ex, 1)
    pv = (
        RAW
        / "solar_potential/_global/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif"
    )
    if pv.exists():
        c, fb, ex = raster_coverage([pv], sx, sy, 0.01)
        add("GSA PVOUT (global file)", "raster", c, fb, ex, 1)
    pop = sorted((RAW / "population" / iso).glob("*.tif"))
    if pop:
        c, fb, ex = raster_coverage(pop, sx, sy, 0.01)
        add("Population (WorldPop)", "raster", c, fb, ex, len(pop))
    lc = sorted((RAW / "land_cover" / iso).glob("*.tif"))
    if lc:
        c, fb, ex = raster_coverage(lc, sx, sy, 0.01)
        add("Land cover (ESA WorldCover, tiles)", "raster", c, fb, ex, len(lc))
    dem = sorted((RAW / "copernicus_dem30" / iso).glob("*.tif"))
    if dem:
        c, fb, ex = raster_coverage(dem, sx, sy, 0.01)
        add("DEM (Copernicus GLO-30, tiles)", "raster", c, fb, ex, len(dem))

    # --- vectors (extent and features in the mask)
    vecs = [
        ("WDPA protected areas", RAW / f"wdpa/{iso}/{iso}_protected_areas_wdpa.geojson", None),
        (
            "Transmission grid (OSM extract)",
            RAW / f"infrastructure_grid/{iso}/{iso}_grid_osm.geojson",
            None,
        ),
    ]
    for label, path, layer in vecs:
        if path.exists():
            fb, n = vector_extent(path, geom, layer)
            g = vector_in_mask(path, geom, layer)
            add(
                label,
                "vector",
                None,
                fb,
                {
                    "features_file": n,
                    "features_in_mask": len(g),
                    "mask_1deg_cells_with_feature": cell_presence(g, sx, sy),
                },
                1,
            )
    for d in sorted((RAW / f"hydrosheds/{iso}").glob("HydroRIVERS*")):
        shp = next(d.glob("*.shp"), None)
        if shp:
            fb, n = vector_extent(shp, geom)
            g = vector_in_mask(shp, geom)
            add(
                "HydroRIVERS (continental file)",
                "vector",
                None,
                fb,
                {
                    "features_file": n,
                    "features_in_mask": len(g),
                    "mask_1deg_cells_with_feature": cell_presence(g, sx, sy),
                },
                1,
            )
    lakes = next((RAW / "hydrosheds/_global/HydroLAKES_polys_v10_shp").glob("*.shp"), None)
    if lakes:
        fb, n = vector_extent(lakes, geom)
        add("HydroLAKES (global file)", "vector", None, fb, {"features_file": n}, 1)
    # roads: GRIP4 region file named in countries.yaml
    import yaml

    cy = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "config" / "countries.yaml").read_text(
            encoding="utf-8"
        )
    )
    cfg = (cy.get("countries") or cy).get(iso, {})
    rd, rf = cfg.get("grip4_region_dir"), cfg.get("grip4_region_file")
    if rd and rf:
        shp = RAW / "infrastructure_roads/_global" / rd / rf
        if shp.exists():
            fb, n = vector_extent(shp, geom)
            g = vector_in_mask(shp, geom)
            add(
                "Roads (GRIP4 regional file)",
                "vector",
                None,
                fb,
                {
                    "features_file": n,
                    "features_in_mask": len(g),
                    "mask_1deg_cells_with_feature": cell_presence(g, sx, sy),
                },
                1,
            )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"audit_{iso}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    for iso in sys.argv[1:]:
        audit(iso)
