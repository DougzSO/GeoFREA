# F3 / H-3 parameter research — proposed exclusion parameters, sources, and four findings on the inputs

Date: 2026-10-07. Scope: the parameters that E1-E6 (M-F2b-01) and the F3 candidate filter (M-F3-04) need: OQ-002 (slope), OQ-003
(population density), OQ-015 (land cover, forest, IUCN), the riparian setback, and `min_eligible_area_km2` (no OQ existed; it is
OQ-044 now). Method: targeted web search, then the sources below were opened and read as PDF or HTML text; what could not be opened
is marked **lead only**. Nothing here is in `config/` yet: every value waits for Douglas's verdict (A-09, no invented values).

## 1. Proposed values

"Opened" = the table or sentence was read in the document. Slopes are given in degrees; sources quoted in % are converted
(degrees = atan(percent / 100)).

| Parameter | Solar PV | Onshore wind | Evidence |
|---|---|---|---|
| **E4 slope, central** | 10 deg | 16.7 deg (30%) | Solar: 10 deg in the MAPRE site-suitability set (Patankar et al., Table B1; Owusu-Obeng et al.; both cite Leslie et al. and Wu et al.). Wind: 30% for Europe (Ryberg et al., 2020, quoted by the ENSPRESO 2 report), near MAPRE's 19 deg. |
| E4 slope, strict | 3-5 deg (candidate) | 10.2 deg (18%) | Wind: ENSPRESO 2 adopts 18% as "conservative" (JRC144438, section 2.1.5). Solar: **lead only**, a study reporting 85% of the 100 largest operating PV sites on slopes of 3.1 deg or less (not opened). |
| E4 slope, lenient | 14 deg (candidate) | 30 deg | Wind: upper end of the 1-30 deg range of McKenna et al. (2022), Table 2. Solar: **lead only**, a study that treats up to 14.04 deg (25%) as suitable (not opened); another PV model excludes above 30 deg (Applied Energy, Poland, via a trade-press summary). |
| **E6 population density, central** | 100 persons/km2 | 100 persons/km2 | MAPRE Table B1 (LandScan, 1 km): "exclude areas > 100" for solar and wind (Patankar et al.). |
| E6 lenient | 200 persons/km2 | 200 persons/km2 | The value already in `parameters.json` (`pop_density_threshold`, unverified, "about 193/km2, a US solar-siting threshold", DECISIONS 2026-09-10). |
| E6 strict | no source found | no source found | Left for Douglas; 50 persons/km2 is a candidate with no citation. |
| **E3 riparian setback, central** | 0.5 km | 0.5 km | Range in the literature: water bodies 0-1 km (McKenna et al., Table 2); 250 m for water bodies and rivers (MAPRE Table B1); 0.5 km is the existing unverified value (Brazilian Forest Code scale). **But see finding B: the value cannot matter below about 1.1 km at this resolution.** |
| **E1 protected areas, central** | IUCN Ia, Ib, II | IUCN Ia, Ib, II | The global Enertile model (Franke et al., 2024, Renewable Energy 226:120376) excludes Ia, Ib and II (stated in Brooks et al., arXiv 2511.23339); matches the category list already in `parameters.json`. |
| E1 strict | every IUCN category | every IUCN category | ESMAP "practical" PV potential excludes "protected areas with any status" of the IUCN system. |
| E1 lenient | Ia, Ib | Ia, Ib | **No source found**; a candidate only. |
| **`min_eligible_area_km2`** | 0.1 km2 (by analogy) | 0.1 km2 | ENSPRESO 2 (JRC144438) assumes that 10 ha of suitable land within a cell is enough for one 3 MW turbine and treats cells below 10% of 1 km2 as unsuitable; it names this the "small area problem" (also McKenna et al.; Ryberg et al.). For solar the 10 ha figure is applied by analogy and is not sourced. Linked to F5: capacity = area x LUF x PD (OQ-004). |

### E5 land cover (ESA WorldCover classes, those present in PRT, IND, BRA)

| Class | Solar central | Wind central | Basis |
|---|---|---|---|
| 10 Tree cover | excluded | excluded | ESMAP excludes forests with tree density >= 50%; ENSPRESO 2 excludes all forest classes; McKenna et al. report full exclusion as the common rule, partial allowance in some studies. |
| 20 Shrubland, 30 Grassland | allowed | allowed | ENSPRESO 2 allows natural grassland and shrub classes. |
| 40 Cropland | **excluded** | allowed | ESMAP excludes cropland (level-2 constraint); ENSPRESO 2 allows non-irrigated arable land, pasture and mixed agriculture for wind. Opposite practice exists for PV (Patankar et al. restrict US PV to agricultural land), so this is a policy choice (see decisions). |
| 50 Built-up | excluded | excluded | ENSPRESO 2, ESMAP (urban). |
| 60 Bare / sparse vegetation | allowed | allowed | ENSPRESO 2 allows bare rock and sparse vegetation. |
| 70 Snow and ice | excluded | excluded | ENSPRESO 2 (glaciers and perpetual snow). |
| 80 Permanent water | excluded | excluded | ENSPRESO 2, ESMAP; overlaps E2 (lakes). |
| 90 Herbaceous wetland, 95 Mangroves | excluded | excluded | ENSPRESO 2 (wetlands). |
| 100 Moss and lichen | no source | no source | 0.2% of IND only; excluded unless Douglas says otherwise. |

Variants (U-06): `strict` also excludes cropland for wind; `lenient` allows tree cover for wind (`forest_excluded: false`, a
treatment found in the literature, McKenna et al.) and cropland for solar. No source sets the exact variant shares.

## 2. Findings that change the plan (found while checking the inputs for this research)

**A. The aligned population layer is wrong by a factor of 144 (a defect in F2a, not a parameter issue).** The sum of
`<ISO3>_population_aligned.tif` is 7.07e4 for PRT (real population about 1.03e7), 9.65e6 for IND (about 1.40e9), 1.51e6 for BRA
(about 2.13e8): in all three the ratio is 0.007, which is (0.00083 / 0.01)^2 = 1/144. The 100 m WorldPop counts are brought to the
0.01 deg grid with `reproject_to_grid`, whose default is bilinear resampling, so each 1.1 km pixel receives about one 100 m sample
instead of the sum of the 144 counts under it (`grid_alignment/alignment.py`, `raster_alignment.py`). E6 would exclude nothing
(0.0-0.1% of pixels at 100 persons/km2 in the preview below). The fix is to aggregate counts by sum and derive density as
count / geodesic pixel area. It changes the frozen V-01 fixture for the population layer of ZZZ.

**B. At 0.01 deg (about 1.1 km) a riparian setback below about 1.1 km is the same as "the pixel contains a river".** In the aligned
distance-to-river raster 27.2% (PRT), 32.4% (IND) and 35.6% (BRA) of pixels have distance 0, and the smallest positive distance is
0.98-1.09 km. Any setback between 0 and about 1 km therefore excludes exactly those pixels, so (i) the central 0.5 km, the 0.25 km of
MAPRE and the 1.0 km of a "strict" variant give the same result, and (ii) E3 removes a third of all land because HydroRIVERS lists
small streams too (catchment of at least 10 km2 or flow of at least 0.1 m3/s per its documentation, not re-checked here), while the literature buffers mapped water bodies and large rivers. Options in the
decisions below.

**C. Land cover is a point sample, not a class share.** The 10 m WorldCover tiles are brought to 0.01 deg with nearest-neighbour
resampling (`raster_alignment.py`), so each pixel carries the class of one 10 m sample out of about 12,000, and a 0.05 deg cell
rests on 25 such samples. The share of a cell excluded by E5 is then noisy (roughly +/-10 percentage points at a 50% share) though
not biased. Class fractions per pixel, computed from the native tiles, would remove the noise at the cost of decoding all tiles once
(hours for BRA).

**D. The slope is derived at the native DEM resolution and then resampled**, so it is a mean slope per 1.1 km pixel, lower than
the 30-100 m slopes the cited thresholds were built on. This biases E4 toward eligibility; it is a limitation to state, not a defect.

## 3. Preview of the effect (E2-E6 only, proposed central values; E1 not included; for orientation, not a result)

Shares of country pixels excluded by each constraint, and the eligible share of all country pixels. E6 is not meaningful until
finding A is fixed (it shows 0.0-0.1%).

| Country, tech | E2 lakes | E3 riparian 0.5 km | E4 slope | E5 land cover | E6 pop | Eligible without E3 | Eligible with E3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| PRT solar (10 deg) | 2.5 | 27.2 | 3.5 | 39.4 | 0.0 | 57.3% | 42.9% |
| PRT wind (16.7 deg) | 2.5 | 27.2 | 0.1 | 33.9 | 0.0 | 64.8% | 48.5% |
| IND solar | 2.2 | 32.4 | 5.6 | 79.8 | 0.1 | 18.0% | 13.0% |
| IND wind | 2.2 | 32.4 | 2.4 | 27.4 | 0.1 | 70.2% | 48.6% |
| BRA solar | 1.9 | 35.6 | 0.6 | 67.1 | 0.0 | 32.4% | 22.3% |
| BRA wind | 1.9 | 35.6 | 0.0 | 58.7 | 0.0 | 40.8% | 28.7% |

Land cover (class share of country pixels): PRT tree cover 29.8%, grassland 49.4%, cropland 5.5%; IND cropland 52.4%, tree cover
23.0%; BRA tree cover 55.2%, grassland 21.8%, shrubland 10.3%. Excluding cropland for solar therefore removes 52% of India.

## 4. Sources read

- McKenna R. et al. (2022), "Reviewing methods and assumptions for high-resolution large-scale onshore wind energy potential
  assessments", Renewable Energy, arXiv:2103.09781: Table 2 (criteria and ranges), forest treatment, settlement setbacks.
- JRC (2025), "The Onshore Wind Potential of the EU and Neighbouring Countries" (ENSPRESO 2), JRC144438: slope, land-cover suitability
  key (Table 1), Natura 2000 buffer, 10 ha minimum, small-area problem; it also lists slope choices of 3% (ENSPRESO 1), 9% (UK),
  20% (Bosch et al., 2017, global), 30% (Germany, Europe; Ryberg et al., 2020), 36% (China).
- Patankar N. et al., "Land Use Trade-offs in Decarbonization of Electricity Generation in the American West", arXiv:2211.05062,
  SI Table B1 (MAPRE site-suitability set: slope solar 10 deg, wind 19 deg; population density 100 persons/km2; water 250 m; urban
  500 m solar, 1,000 m wind).
- Owusu-Obeng P.Y., Mills S.B., Craig M.T., arXiv:2401.16626: "10 degrees for solar and 19 degrees for wind", citing Leslie et al.
  and Wu et al.
- World Bank / ESMAP (2020), "Global Photovoltaic Power Potential by Country": level-1 and level-2 exclusions of the practical
  potential (complex terrain by intra-pixel elevation range > 300 m, forests >= 50% tree density, permanent water, urban > 50%,
  cropland, all IUCN protected areas).
- Brooks V. et al., arXiv:2511.23339, citing Franke K. et al. (2024), Renewable Energy 226:120376 (Enertile): IUCN Ia, Ib, II.
- Ryberg D.S., Robinius M., Stolten D. (2018), Energies 11(5):1246, and Ryberg et al. (2020), Renewable Energy 146:921-931: found,
  abstracts only (the publisher page returned 403); their slope value (30%) is taken from the ENSPRESO 2 report.
- Not opened (leads only): the PV slope studies behind 3.1 deg and 14.04 deg; NREL Lopez et al. (2012), "U.S. Renewable Energy
  Technical Potentials: A GIS-Based Analysis" (host not reachable); the Silicon PV model, Applied Energy (Poland), seen through a
  pv magazine summary (elevation above 2,000 m or slope above 30 deg excluded).
