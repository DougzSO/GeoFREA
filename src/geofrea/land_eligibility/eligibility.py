"""Pixel eligibility from the six exclusions, for one technology and one parameter set (M-F3-01, M-F2b-01).

`eligible fraction of a pixel = valid * (1 - E1) * (1 - E2) * (1 - E3) * (1 - E4) * (1 - E5) * (1 - E6)`

E1 (protected areas), E2 (lakes) and E3 (riparian setback) are shares of the pixel in [0, 1] measured on sub-pixels
(`fractions.py`); E4 (slope above the maximum), E5 (excluded land-cover class at the pixel's sample) and E6 (population density
above the maximum) are 0 or 1. When the land-cover layer becomes class shares, E5 becomes a share too without any change here.
Shares of different constraints are combined as independent, which counts overlapping constraints (a lake inside a riparian
setback) twice and so understates the eligible area: the conservative direction (docs/_audit/2026-10_f3_parameter_research.md).

A pixel is valid only if every required layer has a value there (M-F3-01); a missing value is never read as "free" (A-09).
Population density is the count per pixel over the geodesic pixel area (the aligned population is a sum of counts, D-F2a-014).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geofrea.land_eligibility.parameters import ParameterSet

EXCLUSION_NAMES = ("E1", "E2", "E3", "E4", "E5", "E6")


class MissingExclusionLayerError(KeyError):
    """A shared layer needed by the parameter set (a protected-area level or a riparian setback) was not prepared."""


@dataclass
class EligibilityLayers:
    """Everything the six exclusions read, on one country grid (shape = pixel grid)."""

    country_mask: np.ndarray  # bool, True inside the country
    pixel_area_km2: np.ndarray  # float, geodesic area of each pixel
    slope_deg: np.ndarray  # NaN where missing
    population_count: np.ndarray  # people per pixel, NaN where missing
    land_cover: np.ndarray  # ESA WorldCover class, NaN where missing
    lakes_fraction: np.ndarray  # E2 share
    protected_fraction: dict[tuple[str, ...], np.ndarray]  # E1 share per category set (sorted tuple of categories)
    riparian_fraction: dict[float, np.ndarray]  # E3 share per setback in km
    required_valid: dict[str, np.ndarray]  # layer name -> bool (resource layers that must exist for the technology)


def _riparian_for(setback_km: float, shares: dict[float, np.ndarray]) -> np.ndarray:
    """The riparian share at `setback_km`: exact when prepared, linear in the setback between two prepared values."""
    if setback_km in shares:
        return shares[setback_km]
    keys = sorted(shares)
    if not keys or setback_km < keys[0] or setback_km > keys[-1]:
        raise MissingExclusionLayerError(f"no riparian share prepared around a setback of {setback_km} km (have {keys})")
    hi = next(k for k in keys if k >= setback_km)
    lo = max(k for k in keys if k <= setback_km)
    w = (setback_km - lo) / (hi - lo)
    return (1.0 - w) * shares[lo] + w * shares[hi]


def exclusion_fractions(layers: EligibilityLayers, params: ParameterSet) -> dict[str, np.ndarray]:
    """E1-E6 excluded shares (float32 in [0, 1]) for one parameter set."""
    key = tuple(sorted(params.iucn_categories))
    if key not in layers.protected_fraction:
        raise MissingExclusionLayerError(f"no protected-area share prepared for IUCN categories {key}")
    with np.errstate(invalid="ignore"):
        density = layers.population_count / layers.pixel_area_km2
        e4 = (layers.slope_deg > params.slope_max_deg).astype(np.float32)
        e6 = (density > params.pop_density_max_per_km2).astype(np.float32)
        e5 = np.isin(np.nan_to_num(layers.land_cover, nan=-1).astype(int), list(params.excluded_classes)).astype(np.float32)
    return {
        "E1": layers.protected_fraction[key].astype(np.float32),
        "E2": layers.lakes_fraction.astype(np.float32),
        "E3": _riparian_for(params.riparian_setback_km, layers.riparian_fraction).astype(np.float32),
        "E4": e4,
        "E5": e5,
        "E6": e6,
    }


def valid_pixels(layers: EligibilityLayers) -> np.ndarray:
    """Pixels inside the country where slope, land cover, population and every required resource layer have a value."""
    ok = layers.country_mask & np.isfinite(layers.slope_deg) & np.isfinite(layers.land_cover)
    ok &= np.isfinite(layers.population_count)
    for valid in layers.required_valid.values():
        ok &= valid
    return ok


def eligible_fraction(layers: EligibilityLayers, params: ParameterSet) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """(eligible share of each pixel in [0, 1], the six excluded shares); zero outside the valid pixels."""
    excl = exclusion_fractions(layers, params)
    eligible = np.ones(layers.country_mask.shape, dtype=np.float32)
    for share in excl.values():
        eligible *= 1.0 - share
    eligible = np.where(valid_pixels(layers), eligible, 0.0).astype(np.float32)
    return eligible, excl
