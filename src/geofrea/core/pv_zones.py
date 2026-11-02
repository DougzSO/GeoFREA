"""PV thermal zones (Karin et al. 2019, PVCZ-2019) and the degradation rate of each zone (Group 3).

Two pure pieces:

- the zone of a cell: classification of the equivalent temperature of an open-rack module into T1 to T10 (`classify_zone`), and the zone of the
  nearest PVCZ land point of a cell centre (`nearest_land_zone`, geodesic by chord on the unit sphere, with a declared maximum distance);
- the rate of each zone T1 to T7 from the public fleet data of Jordan et al. (`derive_zone_rates`): median and mean of the positive annual
  degradation rate, with a zone of fewer than `min_systems` systems pooled with the nearest zone.

A zone hotter than T7 takes the T7 rate (`cap_zone`). The zone is a property of the site's historical climate and does not change across climate members.

Implements: M-F6-09 (Group 3 degradation, `docs/thesis/methods/group3_connection_degradation.tex`, subsection "Degradation").
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Upper limits (deg C) of the equivalent temperature of an open-rack module, T_equiv_rack_1p1eV, between zones T1 and T10 (Karin et al. 2019,
# variable `T_equiv_rack_1p1eV_zone` of the PVCZ dataset, 0 to 9). A value on a limit belongs to the hotter zone.
ZONE_LIMITS_C = (14.0, 19.0, 24.0, 29.0, 34.0, 39.0, 44.0, 49.0, 54.0)
FLEET_TOP_ZONE = 7  # the fleet of Jordan et al. covers up to T7; hotter cells take its rate
NO_ZONE = 0  # missing zone in the int8 layer (zones are 1 to 10)
EARTH_RADIUS_KM = 6371.0088


class ZoneError(ValueError):
    """An input of the zone classification or of the rate derivation breaks its contract."""


def classify_zone(t_equiv_c: np.ndarray | float) -> np.ndarray:
    """The zone number (1 for T1 to 10 for T10) of an equivalent temperature in deg C; NaN gives `NO_ZONE`.

    Implements: M-F6-09.

    Limits 14, 19, ..., 54: below 14 is T1, from 14 up to 19 is T2, and so on; 54 and above is T10.
    """
    t = np.atleast_1d(np.asarray(t_equiv_c, dtype="float64"))
    zone = np.searchsorted(np.asarray(ZONE_LIMITS_C), t, side="right") + 1
    return np.where(np.isnan(t), NO_ZONE, zone).astype("int8")


def cap_zone(zone: np.ndarray, top: int = FLEET_TOP_ZONE) -> np.ndarray:
    """Zones above `top` become `top`; `NO_ZONE` stays missing."""
    z = np.asarray(zone)
    return np.where(z > top, top, z).astype("int8")


def _unit_vectors(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def nearest_land_zone(
    lat: np.ndarray,
    lon: np.ndarray,
    point_lat: np.ndarray,
    point_lon: np.ndarray,
    point_zone: np.ndarray,
    max_distance_km: float,
) -> tuple[np.ndarray, np.ndarray]:
    """The zone of the nearest PVCZ point for each (lat, lon), and that distance in km; beyond `max_distance_km` the zone is `NO_ZONE`.

    Implements: M-F6-09.

    The PVCZ dataset has land points only, so a coastal cell takes the nearest land neighbour; the maximum distance is declared in config.
    Distances are great-circle distances through the chord on the unit sphere.

    Raises:
        ZoneError: no PVCZ point, or a non-positive maximum distance.
    """
    if max_distance_km <= 0:
        raise ZoneError("max_distance_km must be positive")
    point_zone = np.asarray(point_zone)
    if point_zone.size == 0:
        raise ZoneError("no PVCZ points to look the zone up")
    tree = cKDTree(_unit_vectors(np.asarray(point_lat, float), np.asarray(point_lon, float)))
    chord, index = tree.query(_unit_vectors(np.asarray(lat, float), np.asarray(lon, float)))
    distance_km = 2.0 * EARTH_RADIUS_KM * np.arcsin(np.clip(chord / 2.0, 0.0, 1.0))
    zone = np.where(distance_km <= max_distance_km, point_zone[index], NO_ZONE).astype("int8")
    return zone, distance_km


@dataclass(frozen=True)
class ZoneSource:
    """Where the zone of a cell comes from: the PVCZ land points (CSV with `lat`, `lon`, `T_equiv_rack_1p1eV_zone`) and the largest lookup distance."""

    csv_path: Path
    max_distance_km: float


@lru_cache(maxsize=2)
def _load_points(csv_path: str, mtime_ns: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame = pd.read_csv(csv_path, usecols=["lat", "lon", "T_equiv_rack_1p1eV_zone"])
    return (
        frame["lat"].to_numpy(dtype="float64"),
        frame["lon"].to_numpy(dtype="float64"),
        (frame["T_equiv_rack_1p1eV_zone"].to_numpy(dtype="float64") + 1).astype("int8"),  # 0-9 in the file, 1-10 here
    )


def zones_for_cells(lat: np.ndarray, lon: np.ndarray, source: ZoneSource) -> np.ndarray:
    """The zone number (1 to 10, `NO_ZONE` beyond the lookup distance) of each cell centre, from the PVCZ points of `source`.

    Implements: M-F6-09.

    Raises:
        FileNotFoundError: the PVCZ file is absent (`scripts/export_pvcz_csv.py` writes it).
    """
    path = Path(source.csv_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"PVCZ points not found: {path}; run scripts/export_pvcz_csv.py (pip install pvcz) to write them"
        )
    point_lat, point_lon, point_zone = _load_points(str(path), path.stat().st_mtime_ns)
    zone, _ = nearest_land_zone(lat, lon, point_lat, point_lon, point_zone, source.max_distance_km)
    return zone


@dataclass(frozen=True)
class DerivedZoneRate:
    """Rate of one zone: systems, median and mean of the annual degradation (fractions per year) and the zone it was pooled with."""

    zone: int
    n: int
    median: float
    mean: float
    merged_with: int | None


def _groups_with_enough_systems(counts: Mapping[int, int], zones: list[int], minimum: int) -> list[list[int]]:
    """Partition `zones` into groups of at least `minimum` systems by joining a short group with the nearest zone outside it.

    The nearest zone is the one with the smallest difference in zone number (the colder one on a tie). The loop ends when every group has
    enough systems, or when one group holds every zone.
    """
    groups = [[z] for z in zones]
    while True:
        short = [g for g in groups if sum(counts.get(z, 0) for z in g) < minimum]
        if not short or len(groups) == 1:
            return groups
        group = min(short, key=lambda g: (sum(counts.get(z, 0) for z in g), min(g)))
        others = [g for g in groups if g is not group]
        target = min(
            others,
            key=lambda g: (min(abs(a - b) for a in g for b in group), min(g)),
        )
        groups = [g for g in groups if g is not group and g is not target] + [sorted(group + target)]


def derive_zone_rates(
    fleet: pd.DataFrame,
    min_systems: int,
    zones: Iterable[int] = range(1, FLEET_TOP_ZONE + 1),
    zone_column: str = "pv_climate_zone",
    plr_column: str = "plr_median",
) -> list[DerivedZoneRate]:
    """Median and mean annual degradation of zones T1 to T7 from the fleet, pooling zones with fewer than `min_systems` systems.

    Implements: M-F6-09.

    `plr_column` is the performance loss rate in %/year with a negative sign for a loss; the rate is `-plr / 100`, positive for a loss. A zone
    with too few systems (including none) is pooled with the nearest zone, and the rate of the pooled group is given to each of its zones with
    `merged_with` naming another zone of the group.

    Raises:
        ZoneError: a required column is missing, or the fleet has no valid row.
    """
    for column in (zone_column, plr_column):
        if column not in fleet:
            raise ZoneError(f"the fleet table has no {column!r} column")
    zones = list(zones)
    labels = fleet[zone_column].astype("string").str.upper().str.extract(r"^T(\d+)$")[0]
    valid = labels.notna() & fleet[plr_column].notna()
    if not valid.any():
        raise ZoneError("the fleet table has no row with a zone and a rate")
    zone_number = labels[valid].astype(int)
    rate = -fleet.loc[valid, plr_column].astype("float64") / 100.0
    counts = zone_number.value_counts().to_dict()
    out: list[DerivedZoneRate] = []
    for group in _groups_with_enough_systems(counts, zones, min_systems):
        pooled = rate[zone_number.isin(group)]
        if pooled.empty:
            raise ZoneError(f"no system in zones {group}: the fleet cannot give a rate")
        for z in group:
            others = [g for g in group if g != z]
            out.append(
                DerivedZoneRate(
                    zone=z,
                    n=len(pooled),
                    median=float(pooled.median()),
                    mean=float(pooled.mean()),
                    merged_with=others[0] if others else None,
                )
            )
    return sorted(out, key=lambda r: r.zone)


def zone_degradation_bounds(rate: DerivedZoneRate | Mapping[str, float]) -> tuple[float, float]:
    """The sampling bounds of a zone: from the median up to the mean, never below the median (the sample is skewed toward faster degradation)."""
    median = rate.median if isinstance(rate, DerivedZoneRate) else float(rate["median"])
    mean = rate.mean if isinstance(rate, DerivedZoneRate) else float(rate["mean"])
    return median, max(median, mean)
