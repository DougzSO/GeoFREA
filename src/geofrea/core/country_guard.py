"""Guards on the country configuration, applied once by `main.py` before any phase runs (COMMAND 126, defect 2 of the generality audit).

Two checks live here, outside every function a phase reaches (so no phase or cache fingerprint depends on them):

1. **Schema of `config/countries.yaml` and `config/country_names.yaml`** (`validate_countries_config`, `validate_country_names`). Both files had
   no schema: a misspelled key (`mainland_onlly`) was ignored and the country silently kept its islands. Every model forbids extra keys, so a
   key the code does not read is an error, and the keys the code needs for every country are required (a null value is still allowed: it
   means "not determined yet", as the header of `countries.yaml` says).
2. **Antimeridian refusal** (`refuse_antimeridian_countries`). The lattice (`cell_id = row * 7200 + col`, origin 180 W), the UTM zone chosen from the
   centroid, the F4 bounding box and the clip box all assume that the territory is one block of continuous longitudes in -180..180. A country whose
   polygon crosses 180 degrees would give a world-wide grid or a wrong zone without a message, so it is refused by name.

Neither check reads or writes any output; both raise a named error that `main.py` reports and turns into exit code 1.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Any

import geopandas as gpd
from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, ValidationError

logger = logging.getLogger(__name__)

Iso3 = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]

#: Tolerance (degrees) for "touches the 180 meridian" when a polygon is split at the seam.
SEAM_TOLERANCE_DEG = 1e-6
#: A single part wider than this (degrees of longitude) has been drawn the long way round the globe.
MAX_PART_WIDTH_DEG = 180.0


class CountryConfigError(ValueError):
    """`countries.yaml` or `country_names.yaml` does not match its schema (unknown key, missing required key, wrong type)."""


class AntimeridianCountryError(ValueError):
    """The polygon of a requested country crosses the 180 degree meridian, which the code does not support (docs/LIMITATIONS.md)."""


class CountryEntry(BaseModel):
    """One country of `config/countries.yaml`. Every key the code reads is here; any other key is an error."""

    model_config = ConfigDict(extra="forbid")

    hydrosheds_region: str | None
    grip4_region_dir: str | None
    grip4_region_file: str | None
    gem_country_name: str | None = None
    mainland_only: StrictBool = False
    gadm_dir: str | None = None
    gadm_level0_sha256: str | None = None
    excluded_land_cover_tiles: list[str] | None = None
    gwa_neighbours: list[Iso3] | None = None
    synthetic_fixture_root: str | None = None


class CountryNames(BaseModel):
    """`config/country_names.yaml`: the name of a country in a figure title, by language (`viz/mapstyle.py`)."""

    model_config = ConfigDict(extra="forbid")

    en: dict[Iso3, str]
    pt: dict[Iso3, str]


def _explain(name: str, exc: ValidationError) -> CountryConfigError:
    lines = [f"{name} does not match its schema:"]
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"  {where}: {err['msg']} ({err['type']})")
    return CountryConfigError("\n".join(lines))


def validate_countries_config(raw: Mapping[str, Any] | None) -> dict[str, CountryEntry]:
    """Validate the content of `countries.yaml` (as read by `load_countries`); return the entries by ISO code.

    Raises:
        CountryConfigError: a country code that is not three capital letters, a key the code does not read, a required key
            (`hydrosheds_region`, `grip4_region_dir`, `grip4_region_file`) absent, or a value of the wrong type.
    """
    if not isinstance(raw, Mapping) or not raw:
        raise CountryConfigError("countries.yaml is empty or is not a mapping of ISO3 codes to entries")
    entries: dict[str, CountryEntry] = {}
    problems: list[str] = []
    for iso, body in raw.items():
        if not isinstance(iso, str) or len(iso) != 3 or not iso.isalpha() or not iso.isupper():
            problems.append(f"  {iso!r}: a country code must be three capital letters")
            continue
        try:
            entries[iso] = CountryEntry.model_validate(body)
        except ValidationError as exc:
            for err in exc.errors():
                where = ".".join(str(p) for p in err["loc"]) or "<entry>"
                problems.append(f"  {iso}.{where}: {err['msg']} ({err['type']})")
    if problems:
        raise CountryConfigError("countries.yaml does not match its schema:\n" + "\n".join(problems))
    return entries


def validate_country_names(raw: Mapping[str, Any] | None) -> CountryNames:
    """Validate the content of `country_names.yaml`.

    Raises:
        CountryConfigError: a language other than `en` and `pt`, a missing language, a code that is not an ISO3 code, or a name that is not text.
    """
    try:
        return CountryNames.model_validate(raw)
    except ValidationError as exc:
        raise _explain("country_names.yaml", exc) from exc


def polygon_crosses_antimeridian(gdf: gpd.GeoDataFrame) -> str | None:
    """Why the polygon crosses 180 degrees, or None when it does not.

    The three signs, on the parts of the geometry in EPSG:4326: (1) a longitude outside -180..180 (drawn in 0..360 across the seam);
    (2) one part wider than 180 degrees (drawn the long way round); (3) parts on both sides of the seam, one touching +180 and
    another touching -180 (a polygon cut at the seam, as GADM does for Fiji or Russia).
    """
    parts = gdf.to_crs("EPSG:4326") if gdf.crs is not None else gdf
    parts = parts.explode(index_parts=False)
    if parts.empty:
        return None
    bounds = parts.geometry.bounds
    if (bounds["minx"] < -180.0 - SEAM_TOLERANCE_DEG).any() or (bounds["maxx"] > 180.0 + SEAM_TOLERANCE_DEG).any():
        return "has a longitude outside -180..180"
    if ((bounds["maxx"] - bounds["minx"]) > MAX_PART_WIDTH_DEG).any():
        return f"has a part wider than {MAX_PART_WIDTH_DEG:g} degrees of longitude"
    if (bounds["maxx"] >= 180.0 - SEAM_TOLERANCE_DEG).any() and (bounds["minx"] <= -180.0 + SEAM_TOLERANCE_DEG).any():
        return "has parts that touch both +180 and -180"
    return None


def _read_level0(iso: str, entry: CountryEntry, raw_gadm_dir: Path | None) -> gpd.GeoDataFrame | None:
    """The pre-placed GADM level-0 polygon of the country (all parts), or None when it is not placed locally."""
    if raw_gadm_dir is None or entry.gadm_dir is None:
        return None
    shp = raw_gadm_dir / iso / f"gadm41_{iso}_shp" / f"gadm41_{iso}_0.shp"
    return gpd.read_file(shp) if shp.exists() else None


def _crossing_of_the_analysed_territory(gdf: gpd.GeoDataFrame, mainland_only: bool) -> str | None:
    """Why the territory the analysis uses crosses 180 degrees, or None.

    The whole polygon is tested first (fast). When the country is `mainland_only`, a crossing found only in far islands does not count (the
    analysis keeps the contiguous territory), so the rule that keeps it is applied, read-only (no cache file), and only then.
    """
    reason = polygon_crosses_antimeridian(gdf)
    if reason is None or not mainland_only:
        return reason
    from geofrea.core.geo_utils import contiguous_mainland_report

    parts = gdf.explode(index_parts=False).reset_index(drop=True).to_crs("EPSG:4326")
    kept = contiguous_mainland_report(gdf)["kept"].to_numpy()
    return polygon_crosses_antimeridian(parts[kept])


def refuse_antimeridian_countries(
    countries: Iterable[str], entries: Mapping[str, CountryEntry], raw_gadm_dir: Path | None
) -> list[str]:
    """Refuse a requested country whose polygon crosses 180 degrees.

    Reads only the pre-placed GADM level-0 shapefile (`<raw_gadm_dir>/<ISO>/gadm41_<ISO>_shp`). A country with no such file is not checked
    here (its polygon does not exist before data_acquisition); the names of those countries are returned so the caller can log them.

    Raises:
        AntimeridianCountryError: naming the country and the sign found.
    """
    unchecked: list[str] = []
    for iso in countries:
        entry = entries.get(iso)
        gdf = None if entry is None or entry.synthetic_fixture_root else _read_level0(iso, entry, raw_gadm_dir)
        if gdf is None:
            unchecked.append(iso)
            continue
        reason = _crossing_of_the_analysed_territory(gdf, entry.mainland_only)
        if reason is not None:
            raise AntimeridianCountryError(
                f"{iso}: the polygon {reason}. A country that crosses the 180 degree meridian is not supported "
                "(lattice, UTM zone, F4 and clip boxes assume continuous longitudes in -180..180; docs/LIMITATIONS.md)"
            )
    return unchecked
