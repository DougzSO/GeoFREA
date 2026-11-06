"""Slope x canopy diagnostic (COMMAND 99, step 2): how much of the area cut by the slope criterion falls on land-cover classes F3 already excludes.

    python scripts/audit_slope_canopy_99.py BRA IND [--out docs/_audit/slope_canopy_99.md]

GLO-30 is a surface model (DSM): a canopy edge or a tall stand reads as a steep sample. This script only measures; it changes nothing in the pipeline.

Cut = E4 (the share of a pixel's 30 m samples steeper than the slope maximum of the scenario, from the 1 degree bins of `slope_counts`, the same
`slope_steep_shares` F3 uses) x geodesic pixel area, summed over the pixels of the country with a slope and a land-cover value. Classes: the 11 WorldCover
bands of `land_cover_counts` (10 m samples, 14,400 a pixel), grouped as trees (10), shrubs (20), cropland (40), grassland (30) and other (50, 60, 70, 80, 90,
95, 100 and samples of no class).

The slope bins (30 m) and the class counts (10 m) are aligned to the same 0.01 degree pixel but are not co-registered below it, so the joint distribution
inside a pixel is not in the data. Three readings of the overlap of the cut with a set of classes (share F of the pixel's samples in the set, E4 = e):
  - independent: e x F (what F3 itself assumes when it multiplies the two shares); the headline;
  - lower bound: max(0, e + F - 1), the least overlap any arrangement inside the pixel allows;
  - upper bound: min(e, F), the most (the steep samples sit first in the classes of the set).
A canopy artifact of the DSM is a positive association between steepness and tree cover inside the pixel, so the truth is likely above the independent value
for trees; the bounds say how far it can go.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from rasterio.windows import Window

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.raster_io import safe_raster_open
from geofrea.land_eligibility.cells import pixel_row_area_km2
from geofrea.land_eligibility.eligibility import _steep_share

ROWS = 64  # rows per strip: 41 uint16 bands x 64 x 4,000 is about 21 MB
GROUPS = {"trees": (10,), "shrubs": (20,), "cropland": (40,), "grassland": (30,), "other": (50, 60, 70, 80, 90, 95, 100)}
SCENARIOS = ("restrictive", "central", "permissive")
TECHNOLOGIES = ("solar", "wind")


def _load_parameters(iso: str) -> dict:
    """`(technology, scenario) -> (slope_max_deg, slope_max_pct, excluded classes)` from the F3 summary of the country (what the round ran with)."""
    import json

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    from geofrea.core import paths

    summary = json.loads((paths.data_root() / "outputs" / iso / "artifacts" / "land_eligibility.json").read_text(encoding="utf-8"))
    out = {}
    for tech in TECHNOLOGIES:
        for scenario in SCENARIOS:
            ps = summary["technologies"][tech]["scenarios"][scenario]["parameter_set"]
            pct = float(ps["slope_max_pct"])
            out[(tech, scenario)] = (float(np.degrees(np.arctan(pct / 100.0))), pct, tuple(int(c) for c in ps["excluded_classes"]))
    return out


def diagnose(iso: str, artifacts: Path, parameters: dict) -> list[dict]:
    """One row per technology and scenario: the cut by slope (km2) split by class group, and the overlap with the excluded classes (three readings)."""
    slope_path = artifacts / f"{iso}_slope_counts_aligned.tif"
    lc_path = artifacts / f"{iso}_land_cover_counts_aligned.tif"
    grid_path = artifacts / f"{iso}_grid_aligned.tif"
    keys = list(parameters)
    cut = {k: 0.0 for k in keys}
    by_group = {k: {g: 0.0 for g in GROUPS} for k in keys}
    overlap = {k: {"independent": 0.0, "lower": 0.0, "upper": 0.0} for k in keys}
    pure = {k: {"trees": [0.0, 0.0], "open": [0.0, 0.0]} for k in keys}  # [sum of E4 x area, sum of area] in pixels with >= 90 % trees / >= 90 % open vegetation
    country_km2 = 0.0
    with safe_raster_open(slope_path) as slope_src, safe_raster_open(lc_path) as lc_src, safe_raster_open(grid_path) as grid_src:
        classes = tuple(int(c) for c in lc_src.tags()["worldcover_classes"].split(","))
        samples = float(lc_src.tags()["samples_per_pixel"])
        height, width = slope_src.height, slope_src.width
        row_area = pixel_row_area_km2(slope_src.transform, height)
        band_of = {code: i for i, code in enumerate(classes)}
        for r0 in range(0, height, ROWS):
            n = min(ROWS, height - r0)
            window = Window(0, r0, width, n)
            slope = slope_src.read(window=window)
            lc = lc_src.read(window=window)
            inside = np.isfinite(grid_src.read(1, window=window).astype("float64"))
            slope_nodata, lc_nodata = slope_src.nodata, lc_src.nodata
            slope_out = (slope == slope_nodata).all(axis=0)
            lc_out = (lc == lc_nodata).all(axis=0)
            slope[:, slope_out] = 0
            lc[:, lc_out] = 0
            valid = inside & ~slope_out & ~lc_out & (slope.sum(axis=0, dtype=np.uint32) > 0) & (lc.sum(axis=0, dtype=np.uint32) > 0)
            if not valid.any():
                continue
            area = np.repeat(row_area[r0 : r0 + n, None], width, axis=1) * valid
            country_km2 += float(area.sum())
            share = {g: sum(lc[band_of[c]] for c in cs).astype(np.float32) / np.float32(samples) for g, cs in GROUPS.items()}
            cache: dict[float, np.ndarray] = {}
            for key in keys:
                deg, _, excluded = parameters[key]
                e4 = cache.setdefault(deg, _steep_share(slope, deg))
                e4 = np.where(valid, e4, 0.0)
                cut[key] += float((e4 * area).sum())
                for g in GROUPS:
                    by_group[key][g] += float((e4 * share[g] * area).sum())
                for name, mask in (("trees", share["trees"] >= 0.9), ("open", (share["shrubs"] + share["grassland"] + share["cropland"]) >= 0.9)):
                    pure[key][name][0] += float((e4 * area)[mask].sum())
                    pure[key][name][1] += float(area[mask].sum())
                f_ex = sum(lc[band_of[c]] for c in excluded).astype(np.float32) / np.float32(samples)
                overlap[key]["independent"] += float((e4 * f_ex * area).sum())
                overlap[key]["lower"] += float((np.maximum(0.0, e4 + f_ex - 1.0) * area).sum())
                overlap[key]["upper"] += float((np.minimum(e4, f_ex) * area).sum())
    rows = []
    for key in keys:
        tech, scenario = key
        deg, pct, excluded = parameters[key]
        total = cut[key]
        no_class = total - sum(by_group[key].values())  # samples of no class (open sea): in no band
        rows.append(
            {
                "country": iso,
                "technology": tech,
                "scenario": scenario,
                "slope_max_pct": pct,
                "excluded_classes": excluded,
                "country_km2": country_km2,
                "cut_km2": total,
                "cut_pct_of_country": 100.0 * total / country_km2 if country_km2 else float("nan"),
                **{f"cut_{g}_km2": by_group[key][g] for g in GROUPS},
                "cut_no_class_km2": no_class,
                "pure_trees_area_km2": pure[key]["trees"][1],
                "pure_open_area_km2": pure[key]["open"][1],
                "pure_trees_mean_e4": pure[key]["trees"][0] / pure[key]["trees"][1] if pure[key]["trees"][1] else float("nan"),
                "pure_open_mean_e4": pure[key]["open"][0] / pure[key]["open"][1] if pure[key]["open"][1] else float("nan"),
                "in_excluded_independent_km2": overlap[key]["independent"],
                "in_excluded_lower_km2": overlap[key]["lower"],
                "in_excluded_upper_km2": overlap[key]["upper"],
            }
        )
    return rows


def render(all_rows: list[dict]) -> str:
    lines = [
        "# Slope x canopy (COMMAND 99, step 2)",
        "",
        "Diagnostic only; nothing in the pipeline changed. Script: `scripts/audit_slope_canopy_99.py`. GLO-30 is a DSM, so tree canopy can read as slope.",
        "",
        "**Cut** = E4 x geodesic pixel area (km2), over the in-country pixels with a slope and a land-cover value; E4 = share of the pixel's 30 m samples steeper than the",
        "slope maximum of the scenario. **Classes** = WorldCover 10 m samples of the pixel. Slope bins (30 m) and class counts (10 m) are not co-registered inside a",
        "0.01 degree pixel, so the overlap is given three ways: *independent* (e x F, the assumption F3 itself makes), and the *lower* and *upper* bounds any arrangement",
        "inside the pixel allows (max(0, e + F - 1) and min(e, F)). The classes the land cover already excludes are those of the scenario (solar: 10, 40, 50, 70, 80, 90, 95;",
        "wind: 10, 50, 70, 80, 90, 95).",
        "",
    ]
    for iso in dict.fromkeys(r["country"] for r in all_rows):
        rows = [r for r in all_rows if r["country"] == iso]
        lines += [f"## {iso}", "", f"Country area with slope and land cover: {rows[0]['country_km2']:,.0f} km2.", ""]
        lines += [
            "### Cut by class group (independent reading, km2)",
            "",
            "| technology | scenario | slope max % | cut km2 | cut % of country | trees | shrubs | cropland | grassland | other |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {r['technology']} | {r['scenario']} | {r['slope_max_pct']:g} | {r['cut_km2']:,.0f} | {r['cut_pct_of_country']:.2f} | "
                + " | ".join(f"{r[f'cut_{g}_km2']:,.0f}" for g in GROUPS)
                + " |"
            )
        lines += [
            "",
            "### Cut inside classes the land cover already excludes, and inside eligible classes (km2 and % of the cut)",
            "",
            "| technology | scenario | cut km2 | in excluded: independent | % | in excluded: lower | % | in excluded: upper | % | in eligible classes: independent | % |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            c = r["cut_km2"]

            def pct(v: float, c: float = c) -> str:
                return f"{100.0 * v / c:.1f}" if c else "n/a"

            ind, lo, up = r["in_excluded_independent_km2"], r["in_excluded_lower_km2"], r["in_excluded_upper_km2"]
            lines.append(
                f"| {r['technology']} | {r['scenario']} | {c:,.0f} | {ind:,.0f} | {pct(ind)} | {lo:,.0f} | {pct(lo)} | {up:,.0f} | {pct(up)} | {c - ind:,.0f} | {pct(c - ind)} |"
            )
        lines += [
            "",
            "### Is steepness higher under tree cover? Mean E4 in pixels dominated by one kind of cover (no independence assumption)",
            "",
            "Pixels with at least 90 % of the samples in trees, against pixels with at least 90 % in shrubs, grassland or cropland. A DSM canopy artifact would make the first rate higher at the same terrain.",
            "",
            "| technology | scenario | tree pixels km2 | mean E4, tree pixels | open pixels km2 | mean E4, open pixels | ratio |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            ratio = r["pure_trees_mean_e4"] / r["pure_open_mean_e4"] if r["pure_open_mean_e4"] else float("nan")
            lines.append(
                f"| {r['technology']} | {r['scenario']} | {r['pure_trees_area_km2']:,.0f} | {r['pure_trees_mean_e4']:.3f} | {r['pure_open_area_km2']:,.0f} | {r['pure_open_mean_e4']:.3f} | {ratio:.2f} |"
            )
        lines.append("")
    lines += [
        "## Check",
        "",
        "The cut and the country area equal, to the km2, the sums of `excluded_area_km2_E4` and `cell_area_km2` of the F3 cell tables of the round (`cells_<tech>__<scenario>.parquet`).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("countries", nargs="+")
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "_audit" / "slope_canopy_99.md")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    from geofrea.core import paths

    rows = []
    for iso in args.countries:
        artifacts = paths.data_root() / "outputs" / iso / "grid_alignment" / "artifacts"
        rows += diagnose(iso, artifacts, _load_parameters(iso))
        print(f"{iso}: done")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows), encoding="utf-8", newline="\n")
    print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
