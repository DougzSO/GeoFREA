"""M-F4-02 criterion 3: change-factor spread over the acquired CMIP6 candidate models (task J-1).

Selection diagnostic, not F4's production change-factor artifact (no bilinear interpolation, unweighted mean over
the in-polygon cells of each country crop). For every registered model and each study country it computes, for
SSP3-7.0, 2041-2070 against 1995-2014 (M-F4-03 formulas, annual means of the monthly values):

    delta_rsds, delta_wind (ratios), dT (K)

then reports the spread and proposes a model set that spans it: farthest-point sampling in the standardized
(country x variable) space, started from the mandatory models (S-04) and from `--exclude`-d candidates removed.

Read-only: writes a markdown report under docs/_audit/, touches no registry.

Run: `python scripts/gcm_selection_spread.py [--k 6] [--exclude a,b] [--out PATH]`
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry

REPO_ROOT = Path(__file__).resolve().parents[1]
MANDATORY = ("gfdl_esm4", "miroc6")  # S-04
COUNTRIES = ("BRA", "PRT", "IND")
VARIABLES = ("rsds", "sfcWind", "tas")
COLUMNS = {"rsds": "delta_rsds", "sfcWind": "delta_wind", "tas": "dT"}
REF, WINDOW = (1995, 2014), (2041, 2070)


def _window_mean(path: str, var: str, years: tuple[int, int]) -> float:
    """Mean over the window of the annual means, then over in-polygon cells (NaN-aware)."""
    with xr.open_dataset(path) as ds:
        da = ds[var].sel(time=slice(str(years[0]), str(years[1])))
        annual = da.groupby("time.year").mean("time")
        return float(np.nanmean(annual.mean("year").values))


def _crop_path(entry, country: str) -> str | None:
    for crop in entry.country_crops:
        if crop.country_code == country:
            return crop.path
    return None


def change_factors(registry: Cmip6Registry, model: str, country: str) -> dict[str, float] | None:
    out: dict[str, float] = {}
    for var in VARIABLES:
        hist = registry.entries.get(f"cmip6/{model}/historical/{var}")
        fut = registry.entries.get(f"cmip6/{model}/ssp370/{var}")
        if not (hist and fut and hist.status == "registered" and fut.status == "registered"):
            return None
        hp, fp = _crop_path(hist, country), _crop_path(fut, country)
        if hp is None or fp is None:
            return None
        ref, win = _window_mean(hp, var, REF), _window_mean(fp, var, WINDOW)
        out[COLUMNS[var]] = (win - ref) if var == "tas" else win / ref
    return out


def farthest_point_selection(
    matrix: np.ndarray, names: list[str], start: list[str], k: int
) -> list[str]:
    """Greedy max-min distance selection in the column-standardized space, seeded with `start`."""
    std = matrix.std(axis=0)
    z = (matrix - matrix.mean(axis=0)) / np.where(std == 0, 1.0, std)
    chosen = [names.index(m) for m in start if m in names]
    if not chosen:  # no seed present: start from the point farthest from the centroid
        chosen = [int(np.argmax(np.linalg.norm(z, axis=1)))]
    while len(chosen) < min(k, len(names)):
        dist = np.min(
            np.linalg.norm(z[:, None, :] - z[chosen][None, :, :], axis=2), axis=1
        )
        dist[chosen] = -1.0
        chosen.append(int(np.argmax(dist)))
    return [names[i] for i in chosen]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", type=int, default=6, help="size of the proposed set (4-6)")
    parser.add_argument("--exclude", default="", help="comma-separated models to leave out")
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "docs" / "_audit" / "2026-10_gcm_selection_spread.md")
    )
    args = parser.parse_args()
    excluded = {m.strip() for m in args.exclude.split(",") if m.strip()}

    load_dotenv(REPO_ROOT / ".env", override=False)
    registry = Cmip6Registry.load(core_paths.fetched_raw("cmip6", "_global") / "cmip6_registry.json")
    models = sorted(
        {e.model for e in registry.entries.values() if e.status == "registered"} - excluded
    )

    factors: dict[str, dict[str, dict[str, float]]] = {}
    skipped: list[str] = []
    for model in models:
        per_country = {c: change_factors(registry, model, c) for c in COUNTRIES}
        if all(v is not None for v in per_country.values()):
            factors[model] = per_country  # type: ignore[assignment]
        else:
            skipped.append(model)

    names = sorted(factors)
    columns = [(c, v) for c in COUNTRIES for v in COLUMNS.values()]
    matrix = np.array([[factors[m][c][v] for c, v in columns] for m in names])

    lines = [
        "# M-F4-02 criterion 3 — change-factor spread (selection diagnostic)",
        "",
        (
            "SSP3-7.0, 2041-2070 vs 1995-2014, M-F4-03 formulas on annual means of the monthly "
            "values, mean over the in-polygon cells of each country crop (unweighted, no "
            "interpolation). Generated by `scripts/gcm_selection_spread.py`; not F4's production "
            "change factors."
        ),
        "",
        f"Models with complete data: {len(names)}. Not usable (missing data): {', '.join(skipped) or 'none'}.",
        "",
    ]
    for country in COUNTRIES:
        lines += [f"## {country}", "", "| model | delta_rsds | delta_wind | dT (K) |", "|---|---:|---:|---:|"]
        for m in names:
            f = factors[m][country]
            lines.append(f"| {m} | {f['delta_rsds']:.4f} | {f['delta_wind']:.4f} | {f['dT']:.3f} |")
        col = {v: matrix[:, columns.index((country, v))] for v in COLUMNS.values()}
        lines.append(
            "| **range (min-max)** | "
            + " | ".join(f"**{col[v].min():.4f}-{col[v].max():.4f}**" for v in COLUMNS.values())
            + " |"
        )
        lines.append("")

    proposal = farthest_point_selection(matrix, names, [m for m in MANDATORY if m in names], args.k)
    lines += [
        "## Proposed spanning set",
        "",
        (
            f"Farthest-point (max-min distance) selection of {args.k} models in the standardized "
            "(country x variable) space, seeded with the S-04 mandatory models "
            f"({', '.join(MANDATORY)}): **{', '.join(proposal)}**."
        ),
        "",
        "This is a diagnostic proposal for Douglas's verdict (OQ-009), not a decision.",
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}; proposal: {proposal}")


if __name__ == "__main__":
    main()
