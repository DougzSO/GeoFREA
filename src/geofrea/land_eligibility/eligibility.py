"""Pixel eligibility from the six exclusions, for one technology and one parameter set (M-F3-01, M-F2b-01).

`eligible fraction of a pixel = valid * (1 - E1) * (1 - E2) * (1 - E3) * (1 - E4) * (1 - E5) * (1 - E6)`

E1 (protected areas), E2 (lakes) and E3 (riparian setback) are shares of the pixel in [0, 1] measured on sub-pixels
(`fractions.py`). E5 is the share of the pixel's 10 m land-cover samples that are not in an allowed class (D-F2a-015): samples of
no class (open sea) count as not allowed. E4 is the share of the pixel's 30 m samples steeper than the slope maximum (D-F2a-016) and E6 (population density above the maximum) is 0 or 1.
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
    slope_counts: np.ndarray  # uint16 (1 degree bin, row, col): 30 m samples per slope bin; the last bin is open ended
    slope_valid: np.ndarray  # bool, False where the pixel has no slope sample at all
    population_count: np.ndarray  # people per pixel, NaN where missing
    land_cover_counts: np.ndarray  # uint16 (class, row, col): 10 m samples per WorldCover class in each pixel
    land_cover_classes: tuple[int, ...]  # WorldCover code of each band of `land_cover_counts`
    land_cover_valid: np.ndarray  # bool, False where the pixel has no land-cover data at all
    samples_per_pixel: int  # 10 m samples in a full pixel (14400 for a 0.01 degree pixel)
    lakes_fraction: np.ndarray  # E2 share
    protected_fraction: dict[tuple[str, ...], np.ndarray]  # E1 share per category set (sorted tuple of categories)
    riparian_fraction: dict[tuple[float, float], np.ndarray]  # E3 share per (minimum discharge m3/s, setback km)
    required_valid: dict[str, np.ndarray]  # layer name -> bool (resource layers that must exist for the technology)


def _bracket(value: float, keys: list[float], what: str) -> tuple[float, float, float]:
    """(lower key, upper key, weight of the upper one) around `value`; never extrapolates."""
    if not keys or value < keys[0] or value > keys[-1]:
        raise MissingExclusionLayerError(f"no riparian share prepared around a {what} of {value} (have {keys})")
    hi = next(k for k in keys if k >= value)
    lo = max(k for k in keys if k <= value)
    return lo, hi, 0.0 if hi == lo else (value - lo) / (hi - lo)


def _riparian_for(setback_km: float, discharge_m3s: float, shares: dict[tuple[float, float], np.ndarray]) -> np.ndarray:
    """The riparian share at (`discharge_m3s`, `setback_km`): exact when prepared, bilinear between prepared values.

    The share grows with the setback and falls with the discharge threshold, so the interpolation is a monotone approximation.
    """
    q_lo, q_hi, wq = _bracket(discharge_m3s, sorted({q for q, _ in shares}), "discharge")
    t_lo, t_hi, wt = _bracket(setback_km, sorted({t for _, t in shares}), "setback")
    try:
        at = lambda q: (1.0 - wt) * shares[(q, t_lo)] + (wt * shares[(q, t_hi)] if wt else 0.0)
        return (1.0 - wq) * at(q_lo) + (wq * at(q_hi) if wq else 0.0)
    except KeyError as exc:
        raise MissingExclusionLayerError(f"riparian share for (discharge, setback) {exc.args[0]} was not prepared") from exc


def _steep_share(counts: np.ndarray, threshold_deg: float) -> np.ndarray:
    """Share of the pixel's 30 m samples with a slope above `threshold_deg`, from 1 degree bin counts.

    Whole bins above the threshold count fully; the bin that contains it counts in proportion (samples assumed uniform within a
    degree). The last bin is open ended (40 degrees and above), so thresholds above 40 degrees cannot be resolved and raise.
    """
    n_bins = counts.shape[0]
    if not 0 <= threshold_deg <= n_bins - 1:
        raise MissingExclusionLayerError(f"slope maximum {threshold_deg} deg is outside the resolvable range 0-{n_bins - 1} deg")
    lo = int(np.floor(threshold_deg))
    above = counts[lo + 1 :].sum(axis=0, dtype=np.float32) + np.float32(lo + 1 - threshold_deg) * counts[lo]
    total = counts.sum(axis=0, dtype=np.float32)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total > 0, above / total, 0.0)
    return np.clip(share, 0.0, 1.0).astype(np.float32)


def _excluded_class_share(layers: EligibilityLayers, params: ParameterSet) -> np.ndarray:
    """E5: 1 minus the share of the pixel's samples that lie in a class which is not excluded."""
    excluded = set(params.excluded_classes)
    unknown = excluded - set(layers.land_cover_classes)
    if unknown:
        raise MissingExclusionLayerError(f"excluded land-cover classes {sorted(unknown)} are not in the prepared bands")
    allowed = np.zeros(layers.country_mask.shape, dtype=np.float32)
    for band, code in enumerate(layers.land_cover_classes):
        if code not in excluded:
            allowed += layers.land_cover_counts[band]
    total = np.float32(layers.samples_per_pixel)  # samples of no class (open sea) are in no band: never allowed
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total > 0, 1.0 - allowed / total, 1.0)
    return np.clip(share, 0.0, 1.0).astype(np.float32)


def exclusion_fractions(layers: EligibilityLayers, params: ParameterSet) -> dict[str, np.ndarray]:
    """E1-E6 excluded shares (float32 in [0, 1]) for one parameter set."""
    key = tuple(sorted(params.iucn_categories))
    if key not in layers.protected_fraction:
        raise MissingExclusionLayerError(f"no protected-area share prepared for IUCN categories {key}")
    with np.errstate(invalid="ignore"):
        density = layers.population_count / layers.pixel_area_km2
        e4 = _steep_share(layers.slope_counts, params.slope_max_deg)
        e6 = (density > params.pop_density_max_per_km2).astype(np.float32)
        e5 = _excluded_class_share(layers, params)
    return {
        "E1": layers.protected_fraction[key].astype(np.float32),
        "E2": layers.lakes_fraction.astype(np.float32),
        "E3": _riparian_for(params.riparian_setback_km, params.riparian_min_discharge_m3s, layers.riparian_fraction).astype(np.float32),
        "E4": e4,
        "E5": e5,
        "E6": e6,
    }


def valid_pixels(layers: EligibilityLayers) -> np.ndarray:
    """Pixels inside the country where slope, land cover (any sample), population and every required resource layer have a value."""
    ok = layers.country_mask & layers.slope_valid & layers.land_cover_valid
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
