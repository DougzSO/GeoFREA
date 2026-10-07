# Disk and data inventory — what GeoFREA holds, what can go, what exists elsewhere on `D:\`

Date: 2026-10-07. Method: `du` and `find` on `D:\Douglas\DOUTORADO\GeoFREA_data`, a read-only scan of `D:\` for NetCDF, ISIMIP and
2071-2100 file names (789 matches inspected), and listings of the CRAEI raw-data folders. Nothing was moved or deleted for this
document. Sizes are as measured on 2026-10-07; "regenerable" says how the file comes back and at what cost.

Why nothing is moved into a "to delete" folder: the clip caches in `interim/` and `outputs/<ISO3>/processed/` are keyed by the source
path, size and modification time (D-F1-025, D-F1b-012), so moving a raw file invalidates them and costs hours. The list below is the
deletion plan instead; delete at the end, or earlier if the disk gets tight.

## 1. `GeoFREA_data` — about 80 GB in total

| Folder | Size | Content |
|---|---:|---|
| `raw/era5` | 37 GB | Hourly gust (`BRA` 16 GB, `_global` bbox files 20 GB, `PRT` 291 MB) and the small per-country annual maxima |
| `raw/isimip3b` | 16 GB | Per-country daily tasmax, tasmin, pr crops, 2041-2070 (copied from CRAEI, OQ-036) |
| `raw/cmip6` | 13 GB | Global monthly rsds, tas, sfcWind for 14 models |
| `raw/gwa` | 7.1 GB | Global Wind Atlas tiles |
| `raw/hydrosheds` | 3.4 GB | HydroRIVERS and HydroLAKES |
| `raw/gadm` | 677 MB | Borders and admin1, with the `*_mainland` extracts |
| `raw/gem` | 29 MB | GEM snapshot 2026-08-09 and the per-country solar/wind parquet (validation only, V-06) |
| `raw/wdpa` | 5.5 MB | Protected areas |
| `reference` | 1.4 GB | `legacy_baseline_fc7b43d`, the retired PRT/BRA baseline |
| `interim` | 1.0 GB | Clip caches (BRA 598 MB, IND 352 MB, PRT 60 MB) |
| `outputs` | 2.4 GB | Phase outputs per country |
| `fixtures`, `logs` | 3.6 MB | |

## 2. Cleanup candidates (nothing deleted yet)

| Candidate | Size | Regenerable? | Notes |
|---|---:|---|---|
| `raw/era5/BRA/BRA_fg10_hourly.nc` | 16 GB | Yes, CDS download (slow, queued) | Source of the BRA annual maxima. Only `BRA_fg10_annual_max.nc` is read. |
| `raw/era5/_global/*_bbox*.nc` | 20 GB | Yes, CDS download | Bbox downloads before the polygon crop. |
| `raw/era5/PRT/PRT_fg10_hourly.nc` | about 290 MB | Yes | Same as BRA. |
| `reference/legacy_baseline_fc7b43d` | 1.4 GB | No (it is the old baseline) | Retired in D-F2a-010; Douglas's call. |
| `regression-fixtures.tar.gz` (repository root, ignored by git) | 363 MB | No | Old release artefact; Douglas's call. |
| `outputs/*/suitability_criteria/` | about 11 MB | Yes, rerun of the legacy phase | Output of the legacy phase, which stays until H-3. |
| `outputs/*/audit/*.txt`, `outputs/*/data_quality_audit/reports` | under 1 MB | Yes, rerun of the audit | Older F1b text reports; the F1b record cites some file names, so keep those. |
| `outputs/ZZZ` | small | Yes (`scripts/generate_zzz_fixture.py`) | Synthetic country, old runs. |
| `logs/_moves`, `GeoFREA/logs` | under 3 MB | n/a | Run logs. |

Cleaned on 2026-10-07 (done, not candidates any more): the WRI GPPD download (`raw/wri_gppd`, 12 MB), the `*_plants_aligned.tif`
rasters, the pre-A-08 top-level `*_aligned.tif` copies under `outputs/{PRT,BRA,ZZZ}/grid_alignment/`, the stale
`PRT_wind_aligned.tif` and `BRA_wind_aligned.tif` (the combined-height wind layer no longer exists, M-F2a-04), the PRT manifest
backup, and the stale registry entries `aligned/plants` and `aligned/wind` in the three manifests (D-core-020).

Not candidates: all of `raw/cmip6`, `raw/isimip3b`, `raw/gwa`, `raw/hydrosheds`, `raw/gadm`, `raw/gem`, `raw/wdpa` (inputs, slow
or impossible to fetch again), `interim` (saves hours), and the annual-maximum ERA5 files.

## 3. Data found on `D:\` outside the project

All under `D:\Douglas\OUTROS\`. Scan: `.nc`, `.nc4`, `.zarr`, `.grib`, and names containing `isimip`, `2071`, `2100`.

| Location | Content | Use for GeoFREA |
|---|---|---|
| `CRAEI_isimip_raw_cache/ISIMIP3b/.../bias-adjusted/global/daily` | Global daily files for 5 GCMs (GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL), historical 1981-2014 and SSP1-2.6, SSP3-7.0 and SSP5-8.5 for **2041-2070** only (decades 2041-50, 2051-60, 2061-70), tasmax, tasmin, pr; about 2 GB per file | The source of the per-country copy already used. **No file for 2071-2100 exists**; the OQ-036 copy is complete for what the cache holds. MPI-ESM1-2-HR and UKESM1-0-LL are in the cache but not in the 6-GCM ensemble. |
| `CRAEI_raw_data/raw/climate/isimip3b` | Per-country crops (BRA, IND, PRT), 5 GCMs, 2041-2070 | Same files that were copied (180 files). |
| `CRAEI_raw_data/raw/climate/w5e5v2.0` | W5E5 v2.0 reference (tasmax, tasmin, pr), 2.5 GB | The bias-adjustment reference of ISIMIP3b. Not needed (the hazard indicators use the adjusted data). |
| `CRAEI_raw_data/raw/emdat` | EM-DAT disaster records for Brazil (239 events, 1948-2024), India (622, 1900-2024), Portugal (38, 1941-2024) plus the raw archive; IBTrACS tracks for the three countries | Evidence for **OQ-007** (loss functions of C2/C3 hazards): historical impacts by hazard type, to be used in Stage R, not as a calibration of the model (V-06 spirit). Check the IBTrACS per-country files before use: the Portugal file has 127,245 rows and the Brazil file 119, which looks like basin files rather than country subsets. |
| `CRAEI_raw_data/raw/aqueduct` | WRI Aqueduct 4.0 water-risk data (baseline annual and monthly, future annual, geodatabase), about 1 GB | Possible context for flood and water-stress hazards for OQ-007; its indicators and licence need checking in Stage R before any use. |
| `CRAEI_raw_data/raw/gem` | The GEM Global Integrated Power Tracker snapshot 2026-08-09 | Already imported and pinned (D-F1-026). |
| `CRAEI_raw_data/raw/gadm`, `boundaries` | GADM 4.1 geopackages for the three countries, HydroBASINS level 6, Natural Earth coastline | Redundant with `raw/gadm` and `raw/hydrosheds`; nothing new. |
| `CRAEI_raw_data/raw/validation` | DGEG (Portugal, 2015-2019) and ONS ENA (Brazil, daily inflow energy 2000-2021) | Hydropower validation for CRAEI; no use for solar and wind. |
| `ARTIGOS HIDROGÊNIO/.../data/raw` | Elevation, grid, land use, protected areas, solar, temperature, water bodies and wind for north-east Brazil and north Germany (an earlier article), SRTM tile cache | Different region and sources; not used. |
| `CRAEI_backup`, `ARTIGO PIPELINE`, `ARTIGO RISK ASSESSMENT`, `ARTIGO 1 - REVISAO IAMS`, `D:\Douglas\TESE` | Backups, drafts and literature | Documents, not data. The literature folders may help Stage R. |
| `D:\tmp` | `cmip6_test`, `test_crop_crs.nc` | Test files, deletable. |

## 4. Needed but not on disk

| Gap | Where it matters | Route |
|---|---|---|
| ISIMIP3b 2071-2100 daily tasmax and pr, about 183 GB | Hazard context for the 18 members of the late window (they carry `hazard: false`, D-F4-004, D-F4-016) | Douglas's decision (D-F4-002 accepted it; about two days of download). Not needed by any phase before OQ-007 is resolved. |
| A second source for the transmission grid of IND | OQ-041: the OSM grid is incomplete there (`docs/_audit/2026-10_plants_vs_osm_grid.md`) | Stage R. One candidate to evaluate, not verified here: a predicted-grid dataset such as Gridfinder (Arderne et al., 2020). |
| Published range for the 30-year change in mean near-surface wind speed | OQ-043 (`wind_factor_valid_range`) | Stage R literature search. |
