# F1 data_acquisition

Status: `built_pending_conformance`
Methodology items: M-F1-01 to M-F1-07, A-05, A-11

## Contract

Requires: configuration. Produces: layer registry artifact (`acquisition_registry`) with, per layer, paths, provenance, fetch status, source version, checksum.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F1-01 | Registry with provenance | Implemented for 14 legacy layers | pass (pending audit) |
| M-F1-02 | Active layer set | Seismic layer still registered; biomass-only inputs present | fail |
| M-F1-03 | GWA Weibull A/k, air density, wind speed at 100/150/200 m | Only `wind-speed` at 100 m fetched | fail |
| M-F1-04 | CMIP6 monthly rsds/tas/sfcWind and daily tasmax/pr | Not present in GeoFREA (GEAR has daily tasmax/pr/tas 2041-2070 only) | fail |
| M-F1-05 | ERA5 gust | Not present in GeoFREA | fail |
| M-F1-06 | GEM solar and wind trackers | Not present (GPPD power plants exist) | fail |
| M-F1-07 | GADM local-first with checksum | Network download with NaturalEarth fallback | fail |
| A-05 | Country mappings in config | Dicts in `local_layers.py` and `fetchers/hydrosheds.py` | fail |

## Active implementation decisions

To be populated by the records migration task from still-valid rationale (see `docs/_audit/2026-09_records.md` section 4).

## Known issues

- BRA rivers and roads run about 1.8x slower in full pipeline than in isolation; root cause unconfirmed. Not on the critical path because raster phases run once per country.
- Six corrupted BRA land-cover tiles in the local database; handled per tile.
- GRIP4 `regions_lookup.json` diverges from shapefile region numbering outside BRA and PRT; blocks India (OQ-012).
- GWA API redirects without validating product or height; existence must be checked on the CDN response.

## History

None.
