"""GEM trackers (F5-1, M-F1-06) and the V-06 guard: plant data is validation-only."""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from geofrea.data_acquisition.fetchers import gem_trackers as gem

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "geofrea"
ALLOWED_IMPORTERS = {
    "data_acquisition/fetchers/gem_trackers.py",  # the acquisition of the file
    "external_validation/inventory.py",  # F7b, the only phase that reads the inventory (D-F7b-005)
}


def test_snapshot_date_needs_a_date_in_the_name():
    assert (
        gem.snapshot_date_from_name("gem_global_integrated_power_tracker_{20260809}.xlsx")
        == "2026-08-09"
    )
    with pytest.raises(gem.GemSnapshotError):
        gem.snapshot_date_from_name("gem_latest.xlsx")


def _plants():
    return pd.DataFrame(
        {
            "Country/area": ["Portugal", "Portugal", "Spain"],
            "lat": [39.0, 32.7, 40.0],
            "lon": [-8.0, -17.0, -4.0],
            "tech": ["solar", "wind", "wind"],
            "status": ["operating", "operating", "operating"],
            "capacity_mw": [10.0, 5.0, 7.0],
        }
    )


def test_clip_keeps_country_name_and_mainland_only():
    mainland = gpd.GeoDataFrame(geometry=[box(-10, 36, -6, 42)], crs="EPSG:4326")
    out = gem.clip_country(_plants(), "PRT", "Portugal", mainland)
    assert out["capacity_mw"].tolist() == [10.0]  # Madeira outside the mainland, Spain by name
    assert gem.counts(out) == {"solar/operating": {"n": 1, "mw": 10.0}}


def test_clip_fails_loud_without_coordinates():
    bad = _plants()
    bad.loc[0, "lat"] = None
    with pytest.raises(gem.GemSnapshotError):
        gem.clip_country(
            bad,
            "PRT",
            "Portugal",
            gpd.GeoDataFrame(geometry=[box(-10, 36, -6, 42)], crs="EPSG:4326"),
        )


def test_v06_no_other_module_imports_the_tracker():
    offenders = []
    for py in SRC.rglob("*.py"):
        rel = py.relative_to(SRC).as_posix()
        if rel in ALLOWED_IMPORTERS:
            continue
        if re.search(
            r"gem_trackers|raw/gem|fetched_raw\(\s*[\"']gem[\"']", py.read_text(encoding="utf-8")
        ):
            offenders.append(rel)
    assert offenders == [], (
        f"V-06: plant data must stay out of the pipeline before F7b: {offenders}"
    )


def test_v06_no_plant_derived_value_in_config():
    hits = []
    for cfg in (ROOT / "config").glob("*.yaml"):
        for n, line in enumerate(cfg.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*(gem_existing_plants:\s*$|gem_country_name:)", line):
                continue  # an audit layer key with null value, and the country-name label: no plant-derived value
            if re.search(
                r"gem[_ ]|global energy monitor|gppd|power.?plant|existing.?plant",
                line,
                re.IGNORECASE,
            ):
                hits.append(f"{cfg.name}:{n}: {line.strip()}")
    assert hits == [], f"V-06: config must not carry plant-derived values or references: {hits}"
