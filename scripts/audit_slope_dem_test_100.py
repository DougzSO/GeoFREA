"""Slope test of COMMAND 100: E4 and eligible area from GLO-30, FABDEM and GLO-30 smoothed to a 90 m support, on 1 degree tiles.

    python scripts/audit_slope_dem_test_100.py [--out docs/_audit/slope_dem_test_100.md]

Nothing in the pipeline changes; this reads the rounds of IND, BRA and PRT and the FABDEM tiles of `external/fabdem/` (scripts/acquire_fabdem_test_100.py).

Three versions of the slope of a tile, each as the 1 degree bins F2a writes (`grid_alignment.raster_alignment`): central differences on the 30 m samples with the WGS84
geodesic spacing of each row, a sample counted in the 0.01 degree pixel that holds its centre (the tile's first sample sits on its integer corner, so pixel = sample
index // 36), E4 of a pixel = `eligibility._steep_share` of its bins (the function F3 uses).
  glo30     Copernicus GLO-30 (a DSM): what the pipeline uses.
  fabdem    FABDEM V1-2: GLO-30 with forests and buildings removed, same 30 m grid.
  smooth90  GLO-30 after a 3 x 3 mean (a 90 m support), then the same gradient on the 30 m grid.
The frame of two samples of the tile is left out of all three, so that they share one support (the 3 x 3 mean needs a neighbour, and the neighbour tiles of FABDEM are
not fetched); the pixels on the tile edge have 34 to 36 samples in the three versions alike.

Eligible area: the F3 engine itself (`windows.ScenarioStripes._compute`, `eligibility.eligible_fraction`) on the 100 rows of the tile, with the shares of lakes, protected
areas, river corridors and settlement setbacks, the land-cover counts and the population of the round on disk, and the E4 of the version in place of the aligned one.
It is the eligible fraction BEFORE the minimum-area rules (those label clusters over the whole grid) and without the siting-resource validity (a pixel must have a slope
sample and a land-cover sample; the resources of a pixel inside these tiles are present). The check against the eligible-fraction raster of the round is in the report.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import uniform_filter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.config_models.land_availability import load_land_availability
from geofrea.core import paths as core_paths
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.land_eligibility.cells import pixel_row_area_km2
from geofrea.land_eligibility.eligibility import _steep_share
from geofrea.land_eligibility.pipeline import _share_needs
from geofrea.land_eligibility.scenarios import scenario_sets
from geofrea.land_eligibility.windows import (
    ClassCountRows,
    NpyRows,
    RasterRows,
    ScenarioStripes,
    StripeInputs,
)

TILES = {
    "S18W051": ("BRA", "Cerrado, flat plateau"),
    "S23W052": ("BRA", "Southeast pasture"),
    "S13W046": ("BRA", "MATOPIBA"),
    "N17E075": ("IND", "Deccan"),
    "N27E073": ("IND", "Rajasthan"),
    "N26E080": ("IND", "Gangetic plain"),
    "N38W008": ("PRT", "Alentejo"),
}
VERSIONS = ("glo30", "fabdem", "smooth90")
PERCENTS = (3, 5, 10, 20, 30)
CLASSES = {"shrubs": 20, "grassland": 30, "cropland": 40}  # the eligible classes of the command; cropland is excluded for PV, eligible for wind
N_SAMPLES, PIXEL = 3600, 36
SLOPE_BINS = 41
SCENARIOS = ("restrictive", "central", "permissive")
TECHS = ("solar", "wind")
EXPERIMENTS = REPO / "config" / "experiments.yaml"


def _name(lat: int, lon: int, glo: bool) -> str:
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    if glo:
        return f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM.tif"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}_FABDEM_V1-2.tif"


def corner(tile: str) -> tuple[int, int]:
    return int(tile[1:3]) * (1 if tile[0] == "N" else -1), int(tile[4:7]) * (1 if tile[3] == "E" else -1)


def read_dem(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        if (src.height, src.width) != (N_SAMPLES, N_SAMPLES):
            raise ValueError(f"{path.name}: expected 3600 x 3600, got {src.height} x {src.width}")
        z = src.read(1).astype(np.float32)
        nodata = src.nodata
    if nodata is not None:
        z[z == nodata] = np.nan
    z[~np.isfinite(z)] = np.nan
    return z


def smooth_3x3(z: np.ndarray) -> np.ndarray:
    """3 x 3 mean; NaN wherever a neighbour is missing (the F2a rule: a stencil that touches a missing value gives no slope)."""
    valid = np.isfinite(z)
    total = uniform_filter(np.where(valid, z, 0.0).astype(np.float64), size=3, mode="nearest") * 9.0
    count = uniform_filter(valid.astype(np.float64), size=3, mode="nearest") * 9.0
    out = np.where(count > 8.5, total / 9.0, np.nan).astype(np.float32)
    out[0, :] = out[-1, :] = np.nan
    out[:, 0] = out[:, -1] = np.nan
    return out


def slope_bins(z: np.ndarray, lat: int) -> np.ndarray:
    """(41, 100, 100) uint16 bin counts per 0.01 degree pixel of the tile, as F2a builds them (see the module docstring)."""
    lat_c = lat + 1 - np.arange(N_SAMPLES) / N_SAMPLES  # latitude of each sample row (rows run southwards from the tile's north edge)
    lat_km, lon_km = wgs84_km_per_degree(lat_c.reshape(-1, 1))
    dz_drow, dz_dcol = np.gradient(z, 1.0, 1.0)
    dz_dy = -dz_drow / (lat_km * 1000.0 / N_SAMPLES)
    dz_dx = dz_dcol / (lon_km * 1000.0 / N_SAMPLES)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    slope[~np.isfinite(z)] = np.nan
    slope[:2, :] = slope[-2:, :] = np.nan  # the common support: a frame of two samples is left out in every version
    slope[:, :2] = slope[:, -2:] = np.nan
    valid = np.isfinite(slope)
    bins = np.clip(np.floor(np.where(valid, slope, 0)), 0, SLOPE_BINS - 1).astype(np.int32)
    pixel = (np.arange(N_SAMPLES) // PIXEL)[:, None] * (N_SAMPLES // PIXEL) + (np.arange(N_SAMPLES) // PIXEL)[None, :]
    flat = np.bincount(((pixel * SLOPE_BINS) + bins)[valid], minlength=(N_SAMPLES // PIXEL) ** 2 * SLOPE_BINS)
    return flat.reshape(N_SAMPLES // PIXEL, N_SAMPLES // PIXEL, SLOPE_BINS).transpose(2, 0, 1).astype(np.uint16)


class _Rows:
    """A (rows, full width) array whose tile columns hold `values` and the rest `fill`: what `windows.ScenarioStripes` reads by rows."""

    def __init__(self, values: np.ndarray, col0: int, width: int, fill):
        self.values, self.col0, self.width, self.fill = values, col0, width, fill

    def __getitem__(self, rows: slice) -> np.ndarray:
        out = np.full((self.values.shape[0], self.width), self.fill, dtype=self.values.dtype)
        out[:, self.col0 : self.col0 + self.values.shape[1]] = self.values
        return out[rows]


class _TileSlope:
    def __init__(self, valid: np.ndarray, steep: dict[float, np.ndarray], col0: int, width: int):
        self.valid = _Rows(valid, col0, width, False)
        self.steep = {k: _Rows(v, col0, width, 0.0) for k, v in steep.items()}


class _RowsFromBand:
    """A shared layer read for the 100 rows of the tile only: row index r0..r1 are taken relative to the tile's first row."""

    def __init__(self, source, row0: int, n: int):
        self.source, self.row0, self.n = source, row0, n

    def __getitem__(self, rows: slice):
        assert rows.start == 0 and rows.stop == self.n, (rows, self.n)
        return self.source[self.row0 : self.row0 + self.n]


class _ClassRowsFromBand(_RowsFromBand):
    classes = ()
    samples_per_pixel = 0


def stripe_inputs(iso: str, row0: int, n: int, slope: _TileSlope, la, sets) -> StripeInputs:
    a = core_paths.data_root() / "outputs" / iso / "grid_alignment" / "artifacts"
    interim = core_paths.data_root() / "interim" / iso / "land_eligibility"
    needs = _share_needs([p for ps in sets.values() for p in ps.values()])
    with rasterio.open(a / f"{iso}_grid_aligned.tif") as src:
        transform = src.transform
        shape = (src.height, src.width)
        mask_rows = np.isfinite(src.read(1, window=Window(0, row0, shape[1], n)).astype("float64"))
    country_mask = np.zeros((n, shape[1]), dtype=bool)
    country_mask[:] = mask_rows
    lc = ClassCountRows(a / f"{iso}_land_cover_counts_aligned.tif")
    lc_band = _ClassRowsFromBand(lc, row0, n)
    lc_band.classes, lc_band.samples_per_pixel = lc.classes, lc.samples_per_pixel
    protected_dir = interim / "protected_fraction_any"
    return StripeInputs(
        transform=transform,
        shape=(n, shape[1]),
        country_mask=country_mask,
        area_row=pixel_row_area_km2(transform, shape[0])[row0 : row0 + n],
        population=_RowsFromBand(RasterRows(a / f"{iso}_population_aligned.tif", "population"), row0, n),
        land_cover=lc_band,
        slope=slope,
        lakes=_RowsFromBand(NpyRows(interim / "lakes_fraction" / "a.npy"), row0, n),
        protected={("*",): _RowsFromBand(NpyRows(protected_dir / "a.npy"), row0, n)},
        corridor={key: _RowsFromBand(NpyRows(interim / "river_corridor" / f"c{i}.npy"), row0, n) for i, key in enumerate(needs.corridors)},
        settlement={t: _RowsFromBand(NpyRows(interim / "settlement_fraction" / f"s{t}.npy"), row0, n) for t in needs.setbacks_m},
        settlement_class=_RowsFromBand(RasterRows(a / f"{iso}_settlements_aligned.tif", "settlements", "float32"), row0, n),
        flags={},
    )


def run_tile(tile: str, la) -> dict:
    iso, where = TILES[tile]
    data = core_paths.data_root()
    lat, lon = corner(tile)
    glo = read_dem(data / "raw" / "copernicus_dem30" / iso / _name(lat, lon, True))
    fab = read_dem(data / "external" / "fabdem" / _name(lat, lon, False))
    dems = {"glo30": glo, "fabdem": fab, "smooth90": smooth_3x3(glo)}
    bins = {v: slope_bins(z, lat) for v, z in dems.items()}
    del dems
    a = data / "outputs" / iso / "grid_alignment" / "artifacts"
    with rasterio.open(a / f"{iso}_grid_aligned.tif") as src:
        t = src.transform
        width = src.width
        row0f, col0f = (t.f - (lat + 1)) / abs(t.e), (lon - t.c) / t.a
    row0, col0 = round(row0f), round(col0f)
    if abs(row0f - row0) > 1e-6 or abs(col0f - col0) > 1e-6:
        raise ValueError(f"{tile}: the tile is not on the pixel lattice of {iso} ({row0f}, {col0f})")
    with rasterio.open(a / f"{iso}_land_cover_counts_aligned.tif") as src:
        counts = src.read(window=Window(col0, row0, 100, 100))
        classes = tuple(int(c) for c in src.tags()["worldcover_classes"].split(","))
        spp = float(src.tags()["samples_per_pixel"])
        nodata = src.nodata
    lc_out = (counts == nodata).all(axis=0)
    counts[:, lc_out] = 0
    share = {name: counts[classes.index(c)].astype(np.float32) / spp for name, c in CLASSES.items()}
    dominant = {name: share[name] >= 0.5 for name in CLASSES}
    row_area = pixel_row_area_km2(t, 10**6)[row0 : row0 + 100]
    area = np.repeat(row_area[:, None], 100, axis=1)
    with rasterio.open(a / f"{iso}_grid_aligned.tif") as src:
        inside = np.isfinite(src.read(1, window=Window(col0, row0, 100, 100)).astype("float64"))
    sets = {tech: scenario_sets(la, tech, iso, dict.fromkeys(SCENARIOS, 1.0)) for tech in TECHS}  # the project area only sets the minimum-area rules, not run here
    out = {"tile": tile, "iso": iso, "where": where, "inside_px": int(inside.sum()), "e4": [], "eligible": [], "check": []}
    # E4 per threshold, version and group
    with rasterio.open(a / f"{iso}_slope_counts_aligned.tif") as src:
        pipeline_bins = src.read(window=Window(col0, row0, 100, 100))
    pipeline_bins[:, (pipeline_bins == 65535).all(axis=0)] = 0
    inside = inside & (pipeline_bins.sum(axis=0, dtype=np.uint32) > 0) & ~lc_out  # the country as the pipeline sees it: a slope and a land-cover sample
    out["inside_px"] = int(inside.sum())
    for pct in PERCENTS:
        deg = math.degrees(math.atan(pct / 100.0))
        e4 = {v: _steep_share(b, deg) for v, b in bins.items()}
        ref = _steep_share(pipeline_bins, deg)
        sel = {"all": inside & (bins["glo30"].sum(axis=0) > 0)}
        sel.update({name: sel["all"] & dominant[name] for name in CLASSES})
        for group, m in sel.items():
            w = area * m
            row = {"tile": tile, "iso": iso, "slope_pct": pct, "group": group, "pixels": int(m.sum()), "area_km2": float(w.sum())}
            for v in VERSIONS:
                row[f"E4_{v}"] = float((e4[v] * w).sum() / w.sum()) if w.sum() else float("nan")
            row["E4_pipeline"] = float((ref * w).sum() / w.sum()) if w.sum() else float("nan")
            out["e4"].append(row)
    # eligible area from the F3 engine, per technology and scenario
    for tech in TECHS:
        for scenario in SCENARIOS:
            params = sets[tech][scenario]
            key = float(params.slope_max_deg)
            result = {}
            for v in VERSIONS + ("pipeline",):
                b = pipeline_bins if v == "pipeline" else bins[v]
                valid = b.sum(axis=0) > 0
                slope = _TileSlope(valid, {key: _steep_share(b, key)}, col0, width)
                inputs = stripe_inputs(iso, row0, 100, slope, la, sets)
                window = ScenarioStripes(inputs, {}, None, params)._compute(0, 100, with_elevation=False)
                result[v] = window.eligible[:, col0 : col0 + 100] * area * inside
            sel = {"all": inside}
            sel.update({name: inside & dominant[name] for name in CLASSES})
            for group, m in sel.items():
                row = {"tile": tile, "iso": iso, "technology": tech, "scenario": scenario, "slope_pct": params.slope_max_pct, "group": group}
                for v in VERSIONS + ("pipeline",):
                    row[f"eligible_km2_{v}"] = float((result[v] * m).sum())
                row["area_km2"] = float((area * m).sum())
                out["eligible"].append(row)
            # check against the eligible-fraction raster of the round (after the minimum-area rules of the scenario)
            suffix = "" if scenario == "central" else f"__{scenario}"
            with rasterio.open(core_paths.data_root() / "outputs" / iso / "land_eligibility" / "artifacts" / f"eligible_fraction_{tech}{suffix}.tif") as src:
                raster = src.read(1, window=Window(col0, row0, 100, 100)).astype("float64")
                raster = np.where(np.isfinite(raster) & (raster != src.nodata), raster, 0.0)
            out["check"].append(
                {
                    "tile": tile,
                    "technology": tech,
                    "scenario": scenario,
                    "round_raster_km2": float((raster * area * inside).sum()),
                    "engine_glo30_pipeline_bins_km2": float(result["pipeline"].sum()),
                    "engine_glo30_own_bins_km2": float(result["glo30"].sum()),
                }
            )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _ratio(x: float, base: float) -> str:
    return f"{x / base:.2f}" if base and not math.isnan(base) else "n/a"


def render(results: list[dict]) -> str:
    L = [
        "# Slope test: GLO-30, FABDEM and a 90 m support (COMMAND 100)",
        "",
        "Diagnostic only; nothing in the pipeline changed. Scripts: `scripts/acquire_fabdem_test_100.py`, `scripts/audit_slope_dem_test_100.py`. Data: FABDEM V1-2 (University of Bristol), 7 tiles in",
        "`GeoFREA_data/external/fabdem/` with the licence text and a manifest (URL, size, ETag, SHA-256, date). **Licence: CC BY-NC-SA 4.0**, read in `license.txt` published with the dataset",
        "(the zips carry no readme or licence file): non-commercial and share-alike, to be cited as Hawker et al. 2022 (Environ. Res. Lett. 17, 034006); a derived table or figure in the thesis carries the same terms.",
        "",
        "**Versions.** `glo30`: the DEM the pipeline uses (a DSM). `fabdem`: the same 30 m grid with forests and buildings removed. `smooth90`: GLO-30 after a 3 x 3 mean (90 m support), same gradient.",
        "All three go through the F2a recipe (central differences, WGS84 geodesic spacing, 1 degree bins, pixel by sample centre) and `eligibility._steep_share`; a frame of two samples of the tile is",
        "left out of all three so that they share one support. **E4** = share of a pixel's 30 m samples steeper than the threshold. Groups are the pixels where the class holds at least half of the 10 m",
        "samples (shrubs 20, grassland 30, cropland 40); `all` is every in-country pixel with a slope.",
        "",
        "## Tiles",
        "",
        "| tile | country | place | pixels in the country |",
        "|---|---|---|---|",
    ]
    L += [f"| {r['tile']} | {r['iso']} | {r['where']} | {r['inside_px']} |" for r in results]
    L += ["", "## Summary", "", "Eligible area (km2, before the minimum-area rules) summed over the tiles of a country and over all seven, `all` pixels. A ratio above 1 means the version keeps more land than GLO-30.", ""]
    L += ["| technology | scenario | slope % | tiles | glo30 | fabdem | smooth90 | fabdem / glo30 | smooth90 / glo30 |", "|---|---|---|---|---|---|---|---|---|"]
    for tech in TECHS:
        for scenario in SCENARIOS:
            for label, isos in (("BRA", ("BRA",)), ("IND", ("IND",)), ("PRT", ("PRT",)), ("all 7", ("BRA", "IND", "PRT"))):
                rows = [e for r in results if r["iso"] in isos for e in r["eligible"] if e["technology"] == tech and e["scenario"] == scenario and e["group"] == "all"]
                g, f, s = (sum(e[f"eligible_km2_{v}"] for e in rows) for v in VERSIONS)
                L.append(f"| {tech} | {scenario} | {rows[0]['slope_pct']:g} | {label} | {g:,.0f} | {f:,.0f} | {s:,.0f} | {f / g:.2f} | {s / g:.2f} |")
    L += ["", "Mean E4 over all in-country pixels of a tile at the PV thresholds, as a share of the GLO-30 value (a share of 0.2 means that 80 % of the GLO-30 cut is not there in FABDEM):", ""]
    L += ["| tile | place | E4 3 % glo30 | fabdem / glo30 | smooth90 / glo30 | E4 5 % glo30 | fabdem / glo30 | smooth90 / glo30 | E4 10 % glo30 | fabdem / glo30 | smooth90 / glo30 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        cells = []
        for pct in (3, 5, 10):
            e = next(x for x in r["e4"] if x["slope_pct"] == pct and x["group"] == "all")
            cells += [f"{e['E4_glo30']:.3f}", f"{e['E4_fabdem'] / e['E4_glo30']:.2f}", f"{e['E4_smooth90'] / e['E4_glo30']:.2f}"]
        L.append(f"| {r['tile']} | {r['where']} | " + " | ".join(cells) + " |")
    L += ["", "## E4 mean by tile and class (area-weighted)", "", "`pipeline` is the E4 of the aligned slope bins of the round, for reference: it differs from `glo30` only by the frame and the tile edge.", ""]
    for pct in PERCENTS:
        L += [
            f"### Threshold {pct} %",
            "",
            "| tile | group | pixels | E4 glo30 | E4 fabdem | E4 smooth90 | fabdem / glo30 | smooth90 / glo30 | E4 pipeline |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in results:
            for e in (x for x in r["e4"] if x["slope_pct"] == pct):
                g, f, s = e["E4_glo30"], e["E4_fabdem"], e["E4_smooth90"]
                L.append(f"| {e['tile']} | {e['group']} | {e['pixels']} | {g:.3f} | {f:.3f} | {s:.3f} | {_ratio(f, g)} | {_ratio(s, g)} | {e['E4_pipeline']:.3f} |")
        L.append("")
    L += [
        "## Eligible area by version (km2, before the minimum-area rules)",
        "",
        "Slope thresholds of the scenarios: PV 3 / 5 / 10 %, wind 10 / 20 / 30 %. Eligible area by the F3 engine with the E4 of the version in place of the aligned one; all other exclusions are those of the round.",
        "",
    ]
    for tech in TECHS:
        L += [
            f"### {tech}",
            "",
            "| tile | scenario | slope % | glo30 | fabdem | smooth90 | fabdem - glo30 | smooth90 - glo30 | fabdem / glo30 | smooth90 / glo30 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in results:
            for e in (x for x in r["eligible"] if x["technology"] == tech and x["group"] == "all"):
                g, f, s = e["eligible_km2_glo30"], e["eligible_km2_fabdem"], e["eligible_km2_smooth90"]
                L.append(f"| {e['tile']} | {e['scenario']} | {e['slope_pct']:g} | {g:,.0f} | {f:,.0f} | {s:,.0f} | {f - g:+,.0f} | {s - g:+,.0f} | {_ratio(f, g)} | {_ratio(s, g)} |")
        L.append("")
    L += ["## Eligible area by class (km2)", "", "Pixels where the class holds at least half of the samples. Cropland is excluded for PV by the land cover, eligible for wind.", ""]
    for tech in TECHS:
        L += [
            f"### {tech}",
            "",
            "| tile | scenario | slope % | class | area km2 | glo30 | fabdem | smooth90 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in results:
            for e in (x for x in r["eligible"] if x["technology"] == tech and x["group"] != "all"):
                L.append(
                    f"| {e['tile']} | {e['scenario']} | {e['slope_pct']:g} | {e['group']} | {e['area_km2']:,.0f} | {e['eligible_km2_glo30']:,.0f} | {e['eligible_km2_fabdem']:,.0f} | {e['eligible_km2_smooth90']:,.0f} |"
                )
        L.append("")
    L += [
        "## Check of the engine against the round",
        "",
        "`round raster` = `eligible_fraction_<tech>[__scenario].tif` of the round (after the minimum-area rules, with the siting-resource validity) x pixel area, over the tile. `engine, pipeline bins` =",
        "the engine here with the aligned slope bins of the round (before the minimum-area rules); the gap to the round raster is the minimum-area rules and the resource validity. `engine, own bins` =",
        "the engine with the bins this script builds from GLO-30: the gap to `pipeline bins` is the frame of two samples and the tile edge.",
        "",
        "| tile | technology | scenario | round raster | engine, pipeline bins | engine, own bins (glo30) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        for c in r["check"]:
            L.append(f"| {c['tile']} | {c['technology']} | {c['scenario']} | {c['round_raster_km2']:,.1f} | {c['engine_glo30_pipeline_bins_km2']:,.1f} | {c['engine_glo30_own_bins_km2']:,.1f} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "_audit" / "slope_dem_test_100.md")
    parser.add_argument("--tiles", nargs="*", default=list(TILES))
    args = parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    la = load_land_availability(EXPERIMENTS)
    results = []
    for tile in args.tiles:
        results.append(run_tile(tile, la))
        print(f"{tile}: done", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.out.with_name("slope_dem_test_100_e4.csv"), [e for r in results for e in r["e4"]])
    write_csv(args.out.with_name("slope_dem_test_100_eligible.csv"), [e for r in results for e in r["eligible"]])
    args.out.write_text(render(results), encoding="utf-8", newline="\n")
    print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
