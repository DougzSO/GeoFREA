"""Pixel eligibility from the six exclusions, for one technology and one parameter set (M-F3-01, M-F2b-01).

`eligible fraction of a pixel = valid * (1 - E1) * (1 - E2) * (1 - E3) * (1 - E4) * (1 - E5) * (1 - E6)`

E1 (protected areas), E2 (lakes), E3 (river corridors) and E6 (settlement setback) are shares of the pixel in [0, 1] measured on sub-pixels
(`fractions.py`). E5 is the share of the pixel's 10 m land-cover samples that are not in an allowed class (D-F2a-015): samples of
no class (open sea) count as not allowed. E4 is the share of the pixel's 30 m samples steeper than the slope maximum (D-F2a-016).
Shares of different constraints are combined as independent, which counts overlapping constraints (a lake inside a protected area)
twice and so understates the eligible area: the conservative direction (docs/_audit/2026-10_f3_parameter_research.md).

E3 is the corridor share net of the water the land cover already excludes: the corridor is the union of every reach's corridor and the water classes of
the land cover, so the channel is not counted twice (Group 6, `subsec:g6_riparian`). With `w` the share of the pixel's samples in a water class and `c`
the corridor share, the corridor holds the water where it is nested (the width estimate reaches the real width), and what it adds beyond the water falls on
the rest of the land: E3 = max(0, (c - w) / (1 - w)), so that (1 - E5)(1 - E3) removes the union (max(c, w) where the water lies in the corridor) and not the sum.

E6 is the share of the pixel within the setback of a settlement of the GHS settlement model (`settlement_share`, by technology and scenario). The named
sensitivity `population_density_200` replaces it by the former density rule: 1 where the population per km2 is above `pop_density_max_per_km2`, 0 elsewhere.

A pixel is valid only if every required layer has a value there (M-F3-01); a missing value is never read as "free" (A-09).
Population density is the count per pixel over the geodesic pixel area (the aligned population is a sum of counts, D-F2a-014).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from geofrea.config_models.land_availability import ParameterSet

EXCLUSION_NAMES = ("E1", "E2", "E3", "E4", "E5", "E6")


class MissingExclusionLayerError(KeyError):
    """A shared layer needed by the parameter set (a protected-area level, a corridor or a setback) was not prepared."""


def corridor_key(params: ParameterSet) -> tuple:
    """What the river-corridor share of a parameter set depends on: the width exponent (and its range) and the buffer steps of the country."""
    rng = params.river_width_exponent_range
    return (
        float(params.river_width_exponent),
        None if rng is None else (float(rng[0]), float(rng[1])),
        tuple(params.river_buffer_steps),
    )


@dataclass
class EligibilityLayers:
    """Everything the six exclusions read, on one country grid (shape = pixel grid)."""

    country_mask: np.ndarray  # bool, True inside the country
    pixel_area_km2: np.ndarray  # float, geodesic area of each pixel
    slope_counts: (
        np.ndarray | None
    )  # uint16 (1 degree bin, row, col): 30 m samples per slope bin; the last bin is open ended; None when only the shares are kept
    slope_valid: np.ndarray  # bool, False where the pixel has no slope sample at all
    population_count: np.ndarray  # people per pixel, NaN where missing
    land_cover_counts: (
        np.ndarray
    )  # uint16 (class, row, col): 10 m samples per WorldCover class in each pixel
    land_cover_classes: tuple[int, ...]  # WorldCover code of each band of `land_cover_counts`
    land_cover_valid: np.ndarray  # bool, False where the pixel has no land-cover data at all
    samples_per_pixel: int  # 10 m samples in a full pixel (14400 for a 0.01 degree pixel)
    lakes_fraction: np.ndarray  # E2 share
    protected_fraction: dict[
        tuple[str, ...], np.ndarray
    ]  # E1 share per category set (sorted tuple of categories)
    required_valid: dict[
        str, np.ndarray
    ]  # layer name -> bool (resource layers that must exist for the technology)
    river_corridor: dict[tuple, np.ndarray] = field(
        default_factory=dict
    )  # share inside the corridor union, by `corridor_key` of the scenarios
    settlement_share: dict[float, np.ndarray] = field(
        default_factory=dict
    )  # share within the setback of a settlement, by setback in metres
    settlement_valid: np.ndarray | None = (
        None  # bool, False where the settlement layer has no value; None: the layer is not read (the density sensitivity)
    )
    slope_steep_share: dict[float, np.ndarray] = field(
        default_factory=dict
    )  # E4 share per slope maximum (deg), prepared from the bins by `slope_steep_shares` (COMMAND 75: the 41 bins need not stay in memory)


def _steep_share(counts: np.ndarray, threshold_deg: float) -> np.ndarray:
    """Share of the pixel's 30 m samples with a slope above `threshold_deg`, from 1 degree bin counts.

    Whole bins above the threshold count fully; the bin that contains it counts in proportion (samples assumed uniform within a
    degree; the error of that reading against the exact share of the samples was measured at 0.33 % of the slope-eligible area at most for
    thresholds of 3 % to 30 %, `docs/_audit/group6_audit_97.md`). The last bin is open ended (40 degrees and above), so thresholds above 40 degrees
    cannot be resolved and raise.
    """
    n_bins = counts.shape[0]
    if not 0 <= threshold_deg <= n_bins - 1:
        raise MissingExclusionLayerError(
            f"slope maximum {threshold_deg} deg is outside the resolvable range 0-{n_bins - 1} deg"
        )
    lo = int(np.floor(threshold_deg))
    above = (
        counts[lo + 1 :].sum(axis=0, dtype=np.float32)
        + np.float32(lo + 1 - threshold_deg) * counts[lo]
    )
    total = counts.sum(axis=0, dtype=np.float32)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total > 0, above / total, 0.0)
    return np.clip(share, 0.0, 1.0).astype(np.float32)


def slope_steep_shares(counts: np.ndarray, thresholds) -> dict[float, np.ndarray]:
    """E4 for each slope maximum in `thresholds`, from the 1 degree bin counts: what `exclusion_fractions` would compute from `counts` (same function).

    The 41 bins are 80 bytes a pixel (BRA: 1.2 GB); the shares of the few slope maxima the scenarios use are 4 bytes a pixel each, so F3
    prepares them once and drops the bins.
    """
    return {float(t): _steep_share(counts, float(t)) for t in sorted({float(t) for t in thresholds})}


def _class_share(layers: EligibilityLayers, classes) -> np.ndarray:
    """The share of the pixel's samples that lie in `classes` (zeros for an empty set)."""
    shape = layers.country_mask.shape
    classes = set(classes)
    unknown = classes - set(layers.land_cover_classes)
    if unknown:
        raise MissingExclusionLayerError(
            f"land-cover classes {sorted(unknown)} are not in the prepared bands"
        )
    inside = np.zeros(shape, dtype=np.float32)
    for band, code in enumerate(layers.land_cover_classes):
        if code in classes:
            inside += layers.land_cover_counts[band]
    return inside / np.float32(layers.samples_per_pixel)


def _excluded_class_share(layers: EligibilityLayers, params: ParameterSet) -> np.ndarray:
    """E5: 1 minus the share of the pixel's samples that lie in a class which is not excluded."""
    excluded = set(params.excluded_classes)
    unknown = excluded - set(layers.land_cover_classes)
    if unknown:
        raise MissingExclusionLayerError(
            f"excluded land-cover classes {sorted(unknown)} are not in the prepared bands"
        )
    allowed = np.zeros(layers.country_mask.shape, dtype=np.float32)
    for band, code in enumerate(layers.land_cover_classes):
        if code not in excluded:
            allowed += layers.land_cover_counts[band]
    total = np.float32(
        layers.samples_per_pixel
    )  # samples of no class (open sea) are in no band: never allowed
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total > 0, 1.0 - allowed / total, 1.0)
    return np.clip(share, 0.0, 1.0).astype(np.float32)


def corridor_net_of_water(corridor: np.ndarray, water: np.ndarray) -> np.ndarray:
    """E3 from the corridor share `corridor` and the water share `water`: `max(0, (corridor - water) / (1 - water))`, 0 where the pixel is all water."""
    with np.errstate(invalid="ignore", divide="ignore"):
        net = np.where(water < 1.0, (corridor - water) / (1.0 - water), 0.0)
    return np.clip(net, 0.0, 1.0).astype(np.float32)


def _river_share(layers: EligibilityLayers, params: ParameterSet) -> np.ndarray:
    key = corridor_key(params)
    if key not in layers.river_corridor:
        raise MissingExclusionLayerError(f"no river-corridor share prepared for {key}")
    return corridor_net_of_water(
        layers.river_corridor[key], _class_share(layers, params.water_classes)
    )


def _settlement_share(layers: EligibilityLayers, params: ParameterSet) -> np.ndarray:
    if params.pop_density_max_per_km2 is not None:  # the named sensitivity `population_density_200`: the former density rule, no settlement mask
        with np.errstate(invalid="ignore"):
            density = layers.population_count / layers.pixel_area_km2
            return (density > params.pop_density_max_per_km2).astype(np.float32)
    key = float(params.settlement_setback_m)
    if key not in layers.settlement_share:
        raise MissingExclusionLayerError(
            f"no settlement share prepared for a setback of {key} m (have {sorted(layers.settlement_share)})"
        )
    return layers.settlement_share[key].astype(np.float32)


def exclusion_fractions(layers: EligibilityLayers, params: ParameterSet) -> dict[str, np.ndarray]:
    """E1-E6 excluded shares (float32 in [0, 1]) for one parameter set.

    Implements: M-F2b-01.
    """
    key = tuple(sorted(params.iucn_categories))
    if key not in layers.protected_fraction:
        raise MissingExclusionLayerError(
            f"no protected-area share prepared for IUCN categories {key}"
        )
    e4 = layers.slope_steep_share.get(float(params.slope_max_deg))
    if e4 is None:
        if layers.slope_counts is None:
            raise MissingExclusionLayerError(
                f"no slope share prepared for a maximum of {params.slope_max_deg} deg (have {sorted(layers.slope_steep_share)})"
            )
        e4 = _steep_share(layers.slope_counts, params.slope_max_deg)
    return {
        "E1": layers.protected_fraction[key].astype(np.float32),
        "E2": layers.lakes_fraction.astype(np.float32),
        "E3": _river_share(layers, params),
        "E4": e4,
        "E5": _excluded_class_share(layers, params),
        "E6": _settlement_share(layers, params),
    }


def valid_pixels(layers: EligibilityLayers) -> np.ndarray:
    """Pixels inside the country where slope, land cover (any sample), population and every required resource layer have a value.

    The settlement layer must also have a value (`settlement_valid`), except when only the density sensitivity runs and the layer is not read (None).
    """
    ok = layers.country_mask & layers.slope_valid & layers.land_cover_valid
    ok &= np.isfinite(layers.population_count)
    if layers.settlement_valid is not None:
        ok &= layers.settlement_valid
    for valid in layers.required_valid.values():
        ok &= valid
    return ok


def eligible_fraction(
    layers: EligibilityLayers, params: ParameterSet
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """(eligible share of each pixel in [0, 1], the six excluded shares); zero outside the valid pixels.

    Implements: M-F3-01.
    """
    excl = exclusion_fractions(layers, params)
    eligible = np.ones(layers.country_mask.shape, dtype=np.float32)
    for share in excl.values():
        eligible *= 1.0 - share
    eligible = np.where(valid_pixels(layers), eligible, 0.0).astype(np.float32)
    return eligible, excl
