# ISIMIP3b acquisition of the v2 climate channel

The package `src/geofrea/climate_acquisition/` acquires the ISIMIP3b data that M1 to M3 and F4 read (M-F1-04, S-04, S-05). It is a data-preparation step outside the code of every phase: its configuration is `config/climate_acquisition.yaml`, which no phase reads, and its record is the manifest `raw/isimip3b/isimip3b_v2_manifest.json` below `GEOFREA_DATA_DIR`. The files `pr`, `tasmax` and `tasmin` of the hazard channel in `raw/isimip3b/<ISO3>/` are not part of it and are not touched.

## What is acquired

| Family | Variables | Time step | Scope |
|---|---|---|---|
| atmosphere (`InputData`, bias adjusted) | `tas`, `rsds`, `sfcwind` | daily | 5 GCMs x (`historical` + SSP1-2.6, SSP3-7.0, SSP5-8.5) x BRA, IND, PRT; the decade blocks that overlap 1995-2014 (historical) and 2041-2070 (SSPs) |
| water (`OutputData`, `water_global`) | `dis`, `qtot` | monthly | 4 GHMs (cwatm, h08, miroc-integ-land, watergap2-2e) x 5 GCMs x (`historical` + 3 SSPs) x BRA, IND, PRT; one file per combination covers the whole experiment |

The boxes are cut on the ISIMIP server (`cutout_bbox`): BRA [-74.5, -34.0, -34.5, 6.0], IND [68.0, 98.0, 6.0, 37.5], PRT [-31.5, -6.0, 32.5, 42.5] (west, east, south, north). The native grid is 0.5 degree.

Human-forcing scenario of the water files: `histsoc` in the historical experiment and the `2015soc` variant the server publishes for each pair in the SSPs. Which scenario M1 uses for the relative change of discharge is OQ-125.

## Files and layout

```
raw/isimip3b/
  atmosphere/<ISO3>/<gcm>/<scenario>/<variable>/<ISIMIP file name with the box tag>.nc
  water/<ISO3>/<ghm>/<gcm>/<scenario>/<variable>/<ISIMIP file name with the box tag>.nc
  isimip3b_v2_manifest.json     one record per file
  isimip3b_v2_plan.json         requirement matrix, status of each file, estimated sizes, gaps
```

Each manifest record has: `sha256`, `size_bytes`, `url`, `accessed_utc`, `bbox`, `gcm`, `ghm` (water only), `scenario`, `variable`, `country`, `period`, `time_step`, `spatial_resolution_deg`, `origin`, `effective_source`, `isimip_file`, `soc` and `source_sha256`. A file enters the manifest only when it is complete; a partial file lives in `raw/isimip3b/_staging/` with the suffix `.part`.

## Sources and order of use

1. A file already in the manifest and intact is not fetched again.
2. A Brazil file that the CRAEI holds (`rsds`, `sfcwind`, `dis`, `qtot`) is copied, never moved. The reference hash is the one in the CRAEI extension manifest; if the CRAEI has none for a file, the hash is computed on both sides. The CRAEI tree is read only.
3. The rest is cut on the ISIMIP server (files API v2). A job that was submitted is saved in `logs/climate_acquisition/jobs.json` so that a run resumes it after a crash; the zip is fetched with HTTP Range resume.
4. If the server cut-out fails, the global file is downloaded from `files.isimip.org`, checked against the catalogue checksum and cropped locally (`origin = isimip_server_global_crop`).
5. If the catalogue is unreachable, the daily file paths come from the decade naming convention and are checked on the files server; water paths come from the CRAEI extension manifest.

## Commands

```
python -m geofrea.climate_acquisition plan        # reads the catalogue, writes isimip3b_v2_plan.json
python -m geofrea.climate_acquisition copy-local  # copies the CRAEI Brazil files with the hash checked
python -m geofrea.climate_acquisition download    # fetches what the plan lists as `download`
python -m geofrea.climate_acquisition verify      # re-hashes every file of the manifest
```

`GEOFREA_DATA_DIR` locates the data; `--craei-raw` (or `CRAEI_RAW_CLIMATE_DIR`) and `--craei-manifest` (or `CRAEI_EXTENSION_MANIFEST`) locate the read-only CRAEI inputs. `download` stops when the estimated size does not fit in the free space of the drive minus the margin in the configuration.

## Gaps

A combination that the catalogue does not offer, or offers only with another time step, is written to `gaps` in the plan with the URLs consulted. Its pair is not downloaded; the others proceed.
