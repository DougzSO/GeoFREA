# Layer quantities, units and ranges — read-only verification (ADJ-1)

Date: 2026-09-24. Scope: direct, independent verification of what every acquired layer physically
holds — quantity, unit, nodata, range, CRS/resolution, class legend — read from the files on disk
(GDAL/rasterio metadata, embedded XML sidecars, direct masked/chunked statistics), not re-derived
from `config/audit.yaml` or prior phase records. This is the reference table a later stage reads
instead of re-deriving these facts. Read-only command; no phase was run, nothing was committed.

Attachments consulted: `CLAUDE.md`, `docs/METHODOLOGY.md` (M-F1-02, M-F1-03, M-F1b-01, M-F5-02,
M-F5-03, V-04), `config/audit.yaml`, `docs/phases/F1b_data_quality_audit.md`,
`docs/phases/F1_data_acquisition.md`, `src/geofrea/data_acquisition/local_layers.py`,
`docs/OPEN_QUESTIONS.md`.

Method note: statistics below are computed either (a) masked to the real GADM country polygon
(solar — a single global file, so per-country clipping is required to get a meaningful range) or
(b) over the whole per-country raster with its own nodata mask (elevation, population, wind-speed,
Weibull-A, Weibull-k, air-density — these files are already cropped to each country's extent by
the resolver, so a further polygon clip only changes the nodata share at the border margin, not the
value range). Both are direct reads of the actual files under `GEOFREA_SHARED_RAW_DIR` /
`GEOFREA_DATA_DIR`, run 2026-09-24.

---

## 1. Solar (Global Solar Atlas v2 PVOUT) — verified first, per instruction

**File**: `GEOFREA_SHARED_RAW_DIR/solar_potential/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif`
(single global file, shared by all three countries; `resolve_solar_path()` does not split it).

**GDAL-exposed metadata** (`rasterio` tags, read 2026-09-24):
- Driver: GTiff, CRS: EPSG:4326, resolution: 0.0083333333 deg (30 arcsec) both axes, size 43200x15000, dtype float32, `nodata` not set at the file level.
- Dataset tag `TIFFTAG_IMAGEDESCRIPTION`: "This data layer represents an output from the Solargis database... delivered for the Global Solar Atlas... under CC BY 4.0."
- Band 1 tags: `STATISTICS_MINIMUM=0.727`, `STATISTICS_MAXIMUM=6.731`, `STATISTICS_MEAN=4.195`, `STATISTICS_STDDEV=0.761` (global statistics, embedded by the producer).

**Per-country masked statistics** (clipped to the real GADM level-0 polygon, not a bounding box; a fill value of -9999 was used for pixels outside the polygon and excluded from the stats, along with any genuine NaN pixel found inside the polygon):

| Country | n valid px | nodata share (outside-polygon fraction of the bbox window) | min | p1 | p50 | mean | p99 | max | genuine NaN px found |
|---|---|---|---|---|---|---|---|---|---|
| BRA | 10,226,985 | 59.7% | 2.559 | 3.664 | 4.227 | 4.248 | 4.846 | 5.242 | 13 |
| PRT | 138,740 | 96.8% | 2.556 | 3.214 | 4.324 | 4.276 | 4.674 | 4.822 | 0 |
| IND | 4,011,915 | 66.9% | 1.370 | 3.090 | 4.310 | 4.277 | 5.056 | 6.064 | 0 |

(The "nodata share" here is the share of the bounding-box crop window that falls outside the
country polygon — expected and large for irregularly shaped countries clipped from a rectangular
window, not a data-quality defect. It is not comparable to a true sensor/product nodata share.)

**Expected bands, both quantities, with reasoning**:
- **Specific yield of a 1 kWp system (kWh/kWp/day)**: for BRA/PRT/IND, typical published PVOUT
  figures from the Global Solar Atlas itself run roughly 3.5-5.5 kWh/kWp/day for the bulk of each
  country's territory (higher in NE Brazil and inland India, lower in coastal Portugal/southern
  Brazil forest belt). The measured means (4.25, 4.28, 4.28) and full ranges (1.37-6.06 across all
  three) sit squarely inside this band.
- **Horizontal/global irradiation (kWh/m²/day)**: GHI for these same countries typically runs
  3-6.5 kWh/m²/day too — numerically close to the specific-yield band by coincidence (the two
  quantities differ by a system/inverter efficiency factor of roughly 0.75-0.85 and a tilt-vs-
  horizontal geometry factor, which happen to roughly offset for these latitudes), so the *numeric*
  range alone cannot separate the two quantities here — the file's own declared unit and the
  reference documentation are the deciding evidence below, not the value distribution.

## 2. Global Solar Atlas documentation (PVOUT definition)

- **Web fetch attempted**: `https://globalsolaratlas.info/support/faq-and-definitions` — **unreachable
  in usable form**: the page is JavaScript-rendered; the fetch returned only the page title
  ("Global Solar Atlas"), no substantive content. Per instruction, this is reported as unreachable
  rather than inferred from memory.
- **Local primary source used instead** (equally authoritative — it is the file's own producer
  metadata, shipped alongside the exact file GeoFREA reads): `PVOUT.tif.xml` and `PVOUT.tif.pdf`
  (ISO 19115/19139 metadata, identical text in both formats), same directory as the raster.
  - `gmd:abstract` / title: "Longterm average of daily totals of potential photovoltaic electricity
    production", unit token found directly in the abstract text: **"kWh/kWp"**, covering "the period
    from 1994/1999/2005/2007/2018/2019 (depending on the region) to 2024".
  - PV system configuration assumed by the product: "free standing PV power plant with c-Si modules
    mounted at optimum tilt to maximize monthly PV production" (not horizontal, not tracking).
  - Declared spatial resolution: "30 arc-sec" — matches the measured 0.0083333 deg exactly.
  - This cross-checks a prior independent read of the same file (`docs/_audit/2026-09_resource_products.md`
    section 3.1, 2026-09-15), which found the identical abstract text and resolution figure.

## 3. Solar verdict

**Specific yield, kWh/kWp/day.** No conflict between the two lines of evidence (file metadata text,
and the value distribution being consistent with a plausible specific-yield band for these three
countries) — both agree. This confirms M-F1-02 ("solar PVOUT... kWh/kWp/day") and `config/audit.yaml`'s
existing `solar.unit: "kWh/kWp/day"` (previously corrected 2026-09-22, D-F1b-002/`docs/phases/F1b_data_quality_audit.md`
conformance row). M-F5-02's `CF0 = pvout_kwh_kwp_day / 24` is valid as written: dividing a
kWh/kWp/day figure by 24 h/day yields a dimensionless capacity factor in [0, 1], which the measured
range (0.727/24 = 0.030 to 6.731/24 = 0.280 globally; 0.057-0.253 for the three in-scope countries)
satisfies. No OQ needed for this item — already closed, re-confirmed here independently.

## 4. Every other acquired layer — quantity, unit, nodata, range, CRS/resolution, per country

| Layer | Country | Quantity/unit | CRS / native res | nodata value | nodata share (whole per-country file) | Min | p1 | p50 | mean | p99 | Max | Physically plausible? | Disagrees with config/audit.yaml or code? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solar PVOUT | BRA/PRT/IND | kWh/kWp/day | EPSG:4326, 0.0083333 deg | none (float, no declared nodata) | see §1 | 1.37 | — | — | 4.25 | — | 6.06 | Yes | No — matches `sanity_range: [0.7, 6.8]` |
| elevation | BRA | m (Copernicus DEM) | EPSG:4326, 0.005 deg | -9999 | 26.1% | -45.48 | -23.86 | 233.96 | 555.73 | 4520.27 | 6757.43 | Yes (Andes foothills/coast to Amazon lowlands) | No — res matches `expected_resolution_deg: 0.005` |
| elevation | PRT | m | EPSG:4326, 0.005 deg | NaN (declared nodata is `nan`, not a sentinel value) | 8.9% | -1.59 | 0.0 | 252.48 | 323.19 | 1131.98 | 1971.46 | Mostly — a small negative minimum (-1.59 m) is within DEM vertical-error tolerance for near-sea-level/ocean-adjacent pixels, not a defect | No |
| elevation | IND | m | EPSG:4326, 0.005 deg | -9999 | 31.7% | -177.81 | -96.80 | 286.76 | 1306.19 | 5564.92 | 8479.01 | Yes (below-sea-level basins to Himalayan foothills; full 8000m+ Himalaya peaks fall outside a 0.005deg DEM's usual max only if the true summits aren't covered — 8479 m is plausible for this DEM, below Everest's 8849 m, consistent with a moderate-resolution DEM smoothing peaks) | No |
| population | BRA | people (see §5 — unit not confirmed as count vs density) | EPSG:4326, 0.00083333 deg (~100 m, WorldPop-pattern) | -99999 | 60.2% | 0.0 | — | 0.00239 | 0.2155 | 1.151 | 3691.75 | See §5 | **Gap, not a disagreement: `config/audit.yaml` has no `population` entry at all** — pre-existing, already flagged in `docs/phases/F1b_data_quality_audit.md` Known issues |
| population | PRT | people | EPSG:4326, 0.00083333 deg | -99999 | 96.8% | 0.0 | — | 0.00094 | 0.774 | 13.78 | 1120.67 | See §5 | same gap |
| population | IND | people | EPSG:4326, 0.00083333 deg | -99999 | 67.4% | 0.0 | — | 1.577 | 3.576 | 28.73 | 2404.04 | See §5 | same gap |
| wind-speed 100m | BRA | m/s | EPSG:4326, 0.0025 deg | NaN | 53.8% | 0.447 | 1.841 | 4.475 | 4.696 | 9.074 | 18.286 | Yes | No — matches `expected_resolution_deg: 0.0025` |
| wind-speed 100m | PRT | m/s | EPSG:4326, 0.0025 deg | NaN | 32.1% | 1.770 | 3.971 | 8.117 | 7.610 | 8.977 | 11.836 | Yes | No |
| wind-speed 100m | IND | m/s | EPSG:4326, 0.0025 deg | NaN | 55.2% | 0.052 | 1.693 | 4.915 | 5.052 | 7.569 | 27.339 | Yes | No |
| combined-Weibull-A 100m | BRA | m/s (Weibull scale parameter) | **no embedded CRS** (assumed EPSG:4326 by grid-identity match, D-F1b-006), 0.0025 deg | NaN | 53.8% | 0.411 | 2.072 | 5.031 | 5.265 | 10.231 | 20.419 | Yes | No |
| combined-Weibull-A 100m | PRT | m/s | no embedded CRS, 0.0025 deg | NaN | 32.1% | 1.572 | 4.359 | 9.141 | 8.573 | 10.133 | 13.364 | Yes | No |
| combined-Weibull-A 100m | IND | m/s | no embedded CRS, 0.0025 deg | NaN | 55.2% | 0.050 | 1.806 | 5.541 | 5.685 | 8.477 | 29.147 | Yes | No |
| combined-Weibull-k 100m | BRA | dimensionless (Weibull shape parameter) | no embedded CRS, 0.0025 deg | NaN | 53.8% | 0.722 | 1.517 | 2.384 | 2.562 | 4.442 | 5.619 | Yes (typical wind-resource k in 1.5-3.5) | No |
| combined-Weibull-k 100m | PRT | dimensionless | no embedded CRS, 0.0025 deg | NaN | 32.1% | 0.807 | 1.334 | 2.413 | 2.330 | 2.666 | 2.811 | Yes | No |
| combined-Weibull-k 100m | IND | dimensionless | no embedded CRS, 0.0025 deg | NaN | 55.2% | 0.493 | 1.105 | 2.186 | 2.164 | 3.034 | 3.862 | Yes | No |
| air-density 100m | BRA | kg/m³ | EPSG:4326, 0.0025 deg | NaN | 52.3% | 0.895 | 1.050 | 1.136 | 1.131 | 1.193 | 1.200 | Yes (sea-level to high-elevation air density band) | No |
| air-density 100m | PRT | kg/m³ | EPSG:4326, 0.0025 deg | NaN | 25.1% | 0.989 | 1.107 | 1.204 | 1.196 | 1.211 | 1.213 | Yes | No |
| air-density 100m | IND | kg/m³ | EPSG:4326, 0.0025 deg | NaN | 55.1% | 0.479 | 0.845 | 1.136 | 1.120 | 1.152 | 1.158 | Yes (min reflects thin air at Himalayan altitude) | No |
| slope | BRA/PRT/IND | — (not an F1 layer; derived by `grid_alignment` from the DEM, D-F1b-004) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Not applicable — no file exists to audit at F1/F1b |
| land_cover (ESA WorldCover 10m) | BRA/PRT/IND | categorical, ESA WorldCover 2020 legend | EPSG:4326, 0.0000833 deg per config (matches D-F1b-002 sourcing) | class 0 present (no-data/unclassified per ESA legend) | not computed here (per-tile, not per-pixel across the mosaic; see §6) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | No — classes present are a subset of the standard legend, see §6 |
| grid (OSM power grid) | BRA | vector, LineString/Point, no physical unit (geometry only) | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 20,633 features (20,437 LineString + 196 Point), 0 invalid geometries | No |
| grid | PRT | vector | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 7,767 features (7,265 LineString + 502 Point), 0 invalid | No |
| grid | IND | vector | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 29,996 features (29,789 LineString + 207 Point), 0 invalid | No |
| protected (WDPA) | BRA | vector, polygon, IUCN category attribute | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 4,190 features, 383 invalid geometries pre-repair (repaired at read time, D-F1b-001) | No |
| protected | PRT | vector | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 442 features, 61 invalid pre-repair | No |
| protected | IND | vector | EPSG:4326 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 90 features, 9 invalid pre-repair | No |

Roads (GRIP4) and lakes/rivers (HydroSHEDS) were not re-inspected in this pass beyond what
`docs/phases/F1_data_acquisition.md`/`F1b_data_quality_audit.md` already document (feature counts
and clip timings recorded there, 2026-09-08/2026-09-23) — re-reading the full continental-scale
GRIP4/HydroRIVERS files was out of the time budget for this read-only pass; nothing here
contradicts what those records already state.

## 5. Four specific questions (per instruction, action 5)

- **Population: counts per pixel, or density? CONFIRMED 2026-09-24 (ADJ-2): counts per pixel.**
  The magnitude argument in the prior version of this entry (per-pixel maxima implying implausible
  density) was not decisive on its own and is superseded by the summation test below, which is
  unambiguous. See §8 for the full evidence.
- **Slope: degrees or percent?** Not answerable yet — slope does not exist as a file at F1/F1b (see
  §4 row, and D-F1b-004). It is derived later by `grid_alignment/raster_alignment.py::derive_slope_from_dem()`;
  its unit is a property of that function's implementation, not of any acquired input layer, so it
  is out of this command's read-only, F1/F1b-scoped remit. `docs/phases/F2a_grid_alignment.md` Known
  issues is where this question is tracked.
- **Do the wind products' units match what M-F5-03 expects?** Yes. M-F5-03 (and M-F2b-03) specify
  Weibull A in m/s, Weibull k dimensionless, air density in kg/m³, with power-law height
  interpolation applied to A. The measured Weibull-A ranges (0.41-29.1 m/s across the three
  countries) are wind-speed-scale values consistent with a Weibull scale parameter in m/s; Weibull-k
  (0.49-5.62) is in the expected dimensionless shape-parameter band (~1.5-3.5 typically, with wider
  tails at extreme/sheltered sites); air density (0.48-1.20 kg/m³) is the expected physical band
  (thin-air Himalayan minimum for IND, sea-level-consistent values for BRA/PRT). No mismatch found.
- **Do land cover's class values match the `excluded_classes` the configuration names?** **Not
  checkable yet — `excluded_classes[tech]` does not exist anywhere in the configuration.** Searched
  `config/*.yaml`, `config/parameters.json`: no `excluded_classes` key exists; `M-F2b-01`'s `E5
  land_cover` exclusion criterion belongs to `siting_layers` (F2b), which is `rework_required` and
  not yet built (OQ-015 is the open tracking question for which classes should be excluded per
  technology). The class values actually present on disk (sampled from 3 tiles per country: `{0,
  10, 20, 30, 40, 50, 60, 80, 90}` for PRT, plus `95` for BRA/IND) are all valid ESA WorldCover 2020
  legend codes (10 tree cover, 20 shrubland, 30 grassland, 40 cropland, 50 built-up, 60 bare/sparse
  vegetation, 80 permanent water, 90 herbaceous wetland, 95 mangroves; 0 is the product's own
  no-data/unclassified sentinel). This matches the class keys already used by
  `config/parameters.json`'s `criteria.yield_by_land_cover` tables (10, 20, ..., 95) for all three
  countries, so there is no legend mismatch to report there — but since `excluded_classes[tech]`
  itself doesn't exist, this question genuinely has nothing to check "against" yet.

## 6. Class values sampled (land_cover, 3 tiles per country, not the full country mosaic)

| Country | n tiles registered | Classes seen in first 3 tiles |
|---|---|---|
| BRA | 155 on disk (112 pass the geometry filter per `docs/phases/F1_data_acquisition.md`) | 0, 10, 20, 30, 40, 50, 60, 80, 90, 95 |
| PRT | 26 on disk (11 pass) | 0, 10, 20, 30, 40, 50, 60, 80, 90 |
| IND | 91 on disk (63 pass) | 0, 10, 20, 30, 40, 50, 60, 80, 90, 95 |

(A 3-tile sample per country is not exhaustive of every class that could appear across the full
mosaic — e.g. class 70 snow/ice or 100 moss/lichen could exist in unsampled high-altitude tiles for
BRA/IND — but every class actually observed is a legend-valid code, which is what action 4 asked to
flag: no illegal/out-of-legend value found in the sample.)

## 7. Configuration changes made by this command (ADJ-1 pass)

**None in the ADJ-1 pass.** Action 4 found no disagreement between `config/audit.yaml`'s existing
sourced values (resolution, solar unit, solar sanity range) and the values read directly from disk
— every measurement above corroborates what is already recorded there. Population's gap and
count-vs-density ambiguity were left open for a follow-up; resolved below in the ADJ-2 pass, which
does add a `population` entry to `config/audit.yaml` (see §9).

## 8. Population count-vs-density: resolved by summation (ADJ-2, 2026-09-24)

**Method.** Sum every valid pixel inside each country's real GADM level-0 polygon (windowed/chunked
read + `rasterio.features.geometry_mask`, since BRA's population file cannot be loaded whole into
memory — same constraint noted in `docs/phases/F2a_grid_alignment.md`'s memory known issue) and
compare the total against a reference 2020 population figure for that country. If the raster holds
**counts**, the sum should equal the country's population within a few percent (national aggregates
from a modeled gridded product routinely differ from official counts by a few percent, due to
modeling/census-vintage differences). If the raster holds **density** (people/km²), summing raw
pixel values is dimensionally wrong; the population-equivalent total under that reading is instead
`sum(pixel_values) x pixel_area_km2` (pixel area computed geodesically at the country's bounding-box
mid-latitude via `core/geodesy.py::wgs84_km_per_degree`, per M-F2a-02's geodesic requirement, not a
flat degrees-to-km constant).

**Action 1 — pixel geometry, dtype, nodata, and percentiles** (windowed stats over the real GADM
polygon; extends §4's whole-file-bbox numbers with a true polygon mask and the requested 99.9th
percentile):

| Country | pixel size (deg) | mid-lat | geodesic pixel area (km²) | dtype | nodata | min | max | mean | p99 | p99.9 |
|---|---|---|---|---|---|---|---|---|---|---|
| BRA | 0.00083333 | -14.241 | 0.008292 | float32 | -99999.0 | 0.0 | 3691.75 | 0.2155 | 1.134 | 52.70 |
| PRT | 0.00083333 | 36.092 | 0.006940 | float32 | -99999.0 | 0.0 | 1120.67 | 0.7752 | 13.90 | 108.82 |
| IND | 0.00083333 | 21.128 | 0.007987 | float32 | -99999.0 | 0.0 | 2404.04 | 3.578 | 29.04 | 149.55 |

**Action 2 — summation table:**

| Country | Sum of valid pixels (raw) | Reference 2020 population | Source | Ratio (sum / reference) | Sum x pixel_area_km2 (density-interp. total) |
|---|---|---|---|---|---|
| BRA | 217,122,659.6 | 211,242,542 | Brazil vital-statistics/registered count table, `en.wikipedia.org/wiki/Demographics_of_Brazil` (fetched 2026-09-24) | **1.028** | 1,800,382.8 |
| PRT | 10,694,413.3 | 10,394,297 | Portugal population table, `en.wikipedia.org/wiki/Demographics_of_Portugal` (fetched 2026-09-24) | **1.029** | 74,214.5 |
| IND | 1,408,562,188.1 | 1,402,617,692 | UN World Population Prospects 2024 revision, mid-2020 estimate, via `en.wikipedia.org/wiki/Demographics_of_India` (fetched 2026-09-24) | **1.004** | 11,250,533.6 |

The raw sum matches the reference population within 0.4-2.9% for all three countries — inside the
"a few percent" band the instruction treats as decisive for **counts**. The density-interpretation
total, by contrast, undershoots the real population by a factor of ~117-140x (BRA 1.80M vs. 211M;
PRT 74k vs. 10.4M; IND 11.25M vs. 1.40B) — consistent with the instruction's alternative signature
("larger by roughly the inverse of the pixel area", ~1/0.0083 = ~121x, which is what a true density
field would need multiplying by to become a population count, not what was found here). Both
signatures agree on the same verdict: **counts, not density.**

**Action 3 — cross-check: p99.9 converted to persons/km² under the counts interpretation**
(`p99.9 / pixel_area_km2`):

| Country | p99.9 (people/pixel) | pixel_area_km2 | p99.9 as persons/km² | Plausible for a dense urban pixel? |
|---|---|---|---|---|
| BRA | 52.70 | 0.008292 | **6,354** | Yes — comparable to dense Brazilian urban census tracts (favela-adjacent areas commonly run several thousand to ~20,000/km²; this is well inside that band, not an outlier). |
| PRT | 108.82 | 0.006940 | **15,682** | Yes — comparable to dense Lisbon/Porto urban parishes. |
| IND | 149.55 | 0.007987 | **18,725** | Yes — comparable to dense Indian metro areas (parts of Mumbai/Delhi exceed 20,000-30,000/km²; this sits just below that). |

No implausible value at the 99.9th percentile under the counts reading — reinforces the summation
verdict rather than contradicting it. (The single-pixel maximum, e.g. BRA's 3691.75, converts to
~445,150/km² — an extreme outlier, most plausibly a single small institutional/high-rise footprint
rather than a representative dense-urban value; p99.9 rather than the bare max is the meaningful
plausibility check, as the instruction frames it.)

**Action 4 — product's own metadata and WorldPop documentation.**
- File-level: no unit tag, band description, or XML/JSON/TXT sidecar exists next to
  `<iso3>_pop_2020.tif` under `GEOFREA_SHARED_RAW_DIR/population/` (re-confirmed, same as the ADJ-1
  finding) — the file itself states no unit.
- **WorldPop's own methods documentation** (`https://www.worldpop.org/methods/populations`, fetched
  2026-09-24): describes the standard gridded product as disaggregating "census counts to counts for
  each 100x100m or 1x1km grid cell" — wording consistent with a counts product, though this general
  methods page does not name the exact dataset/version behind GeoFREA's specific file, so it is
  corroborating, not file-specific, evidence.
- A second fetch, of a WorldPop dataset summary page guessed by ID rather than confirmed as the
  exact product in use, returned "The units are number of people per pixel" / "Estimated total
  number of people per grid-cell" — also consistent with counts, but flagged here as **not
  confirmed to be the exact product GeoFREA's file came from** (the page was reached by an
  unverified ID guess, not by tracing GeoFREA's file back to its exact WorldPop catalog entry) — not
  relied on as primary evidence, only as a second data point pointing the same direction as the
  summation test.

**Action 5 — Verdict: population holds counts per pixel, not density.** Actions 2 and 4 agree (no
conflict, so no OQ is opened): the summation test (decisive, file-specific, ratio 0.4-2.9% for all
three countries) and the WorldPop methods-documentation wording (corroborating, product-family-level)
both point to counts. The cross-check in action 3 finds nothing implausible under that reading. This
resolves the ADJ-1 flag; §5 above now records the confirmed verdict with this section as its
evidence trail.

## 9. `config/audit.yaml` — population entry added (ADJ-2, was absent until now)

`config/audit.yaml` had no `population` entry at all before this pass (flagged as a known gap in
`docs/phases/F1b_data_quality_audit.md` Known issues, "population has no configured
`expected_resolution_deg`..."). Added: `expected_resolution_deg: 0.00083333` (measured directly
above, all three countries agreeing), `unit: "count (people per pixel)"`, and a `sanity_range`
derived from this pass's measurements: `[0, 3692]` (the observed max across BRA/PRT/IND, rounded
outward to the nearest integer; not a percentile-based range, since a legitimate single-pixel count
spike, per action 3's analysis, is not itself an anomaly — the audit's sanity range exists to catch
gross corruption, e.g. a negative count or an obviously-miscoded density value orders of magnitude
larger than any observed pixel, not to flag genuine high-density outliers). Source string records
this section and its evidence date. See `config/audit.yaml` itself for the exact entry, not
reproduced here.
