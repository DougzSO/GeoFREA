# Coverage of the spatial inputs against the country mask (COMMAND 59)

Date: 2026-10-20 (before) and 2026-10-25 (after). Written by the audit `scripts/coverage_audit_59.py`; read only. Draft for the author's review.

## 1. Method

- **Mask**: the contiguous territory of M-F2a-01 (`raw/gadm/<ISO3>/gadm41_<ISO3>_0_mainland.shp`), the same geometry for every input.
- **Samples**: a regular lattice every 0.05 degree inside the mask (PRT 3,736 points, IND 111,191, BRA 284,017); each stands for 0.05 x 0.05 degree.
- **Gridded climate (ERA5, ISIMIP3b, CMIP6, W5E5)**: a sample is covered when a native cell **with a value** lies within one native cell of it (the pipeline reads the nearest valid cell; the gust tolerance of `hazard_context` is two cells). For a set of files the worst file is shown.
- **Rasters (GWA, GSA, population, land cover, DEM)**: a sample is covered when the raster, read at about 0.01 degree, holds a valid value there (not nodata, finite).
- **Vectors (WDPA, transmission grid, roads)**: the absence of a feature is not missing data; the file box against the mask box and the features inside the mask are reported, nothing is marked FALHA.
- **FALHA**: a gridded or raster input below 99% of the mask.

## 2. Before (state of the data at the start of COMMAND 59)

### PRT

Mask box (W S E N): [-9.5005, 36.961, -6.1891, 42.1543]; 3,736 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 99.73% | no | 240 | [-8.92, 36.98, -6.22, 41.97] | ok |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_PRT.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_PRT.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: ipsl_cm6a_lr_historical_rsds_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| CMIP6 (F4) sfcWind (worst of 24 files: ipsl_cm6a_lr_historical_sfcWind_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| CMIP6 (F4) tas (worst of 24 files: ipsl_cm6a_lr_historical_tas_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_PRT_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 150 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 200 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_k 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA air_density 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 99.12% | no | 788 | [-9.32, 37.02, -6.52, 42.07] | ok |
| Land cover (ESA WorldCover, tiles) | 5 | 100.00% | yes | 0 |  | ok |
| DEM (Copernicus GLO-30, tiles) | 19 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [-34.46, 29.2, -6.189, 44.86] | yes | 442 | 180 | 1.0 |
| Transmission grid (OSM extract) | [-9.443, 37.013, -4.557, 42.339] | no | 7767 | 6689 | 0.833 |
| Roads (GRIP4 regional file) | [-24.53, 5.707, 105.581, 71.164] | yes | 8786966 | 178950 | 0.944 |

### IND

Mask box (W S E N): [68.1862, 8.0765, 97.4152, 35.5013]; 111,191 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 94.39% | no | 164,232 | [68.23, 9.28, 97.37, 35.48] | **FALHA** |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_IND.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_IND.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_IND_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA wind_speed 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 150 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 150 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 200 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 200 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_k 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_k 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA air_density 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA air_density 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 98.07% | no | 61,506 | [68.28, 8.53, 97.37, 35.43] | **FALHA** |
| Land cover (ESA WorldCover, tiles) | 53 | 98.87% | yes | 32,458 | [73.77, 33.03, 79.17, 35.48] | **FALHA** |
| DEM (Copernicus GLO-30, tiles) | 357 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [68.489, 6.747, 97.418, 34.766] | no | 193478 | 193090 | 0.935 |
| Transmission grid (OSM extract) | [68.177, 7.991, 98.201, 34.904] | no | 29996 | 26655 | 0.756 |
| Roads (GRIP4 regional file) | [60.5, -10.937, 155.875, 53.95] | yes | 5244510 | 610658 | 0.986 |

### BRA

Mask box (W S E N): [-73.9897, -33.7463, -34.7931, 5.2649]; 284,017 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 99.98% | no | 1,534 | [-73.78, -33.73, -39.03, 5.22] | ok |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_BRA.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_BRA.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_BRA_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 150 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 200 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_k 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA air_density 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 98.59% | no | 119,725 | [-73.92, -33.53, -34.83, 5.22] | **FALHA** |
| Land cover (ESA WorldCover, tiles) | 111 | 100.00% | yes | 0 |  | ok |
| DEM (Copernicus GLO-30, tiles) | 817 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [-73.982, -34.012, -25.291, 5.272] | no | 4190 | 4150 | 0.968 |
| Transmission grid (OSM extract) | [-75.052, -35.683, -34.8, 5.737] | no | 20633 | 15455 | 0.729 |
| Roads (GRIP4 regional file) | [-117.124, -55.055, -32.4, 32.718] | yes | 3083547 | 549444 | 0.923 |

## 3. Inputs below 99% and what was done

| Country | Input | Covered (before) | Not covered (km2) | Region | Cause |
|---|---|---|---|---|---|
| PRT | CMIP6 (F4) rsds (worst of 24 files: ipsl_cm6a_lr_historical_rsds_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| PRT | CMIP6 (F4) sfcWind (worst of 24 files: ipsl_cm6a_lr_historical_sfcWind_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| PRT | CMIP6 (F4) tas (worst of 24 files: ipsl_cm6a_lr_historical_tas_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | ERA5 fg10 annual max (1995-2014) | 94.39% | 164,232 | [68.23, 9.28, 97.37, 35.48] | The annual-maximum product was built for the mask of before COMMAND 55 (cell centres 8.25-33.0 N, 68.5-97.0 E): the north block and the east end of Arunachal Pradesh have no cell. **Fixed in this command** by `scripts/extend_era5_gust.py` (see section 4). |
| IND | CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | GWA wind_speed 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA wind_speed 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 150 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 150 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 200 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 200 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_k 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_k 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA air_density 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA air_density 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | Population (WorldPop) | 98.07% | 61,506 | [68.28, 8.53, 97.37, 35.43] | Pixels with no value inside the WorldPop file are scattered blobs on rivers, estuaries and the coast (the largest in IND: 84.1-88.5 E, 24.4-26.7 N, the Ganges; none is a region of the territory). The file reaches every part of the mask; the pipeline treats a no-value pixel as no population. **Reason recorded, nothing to acquire.** |
| IND | Land cover (ESA WorldCover, tiles) | 98.87% | 32,458 | [73.77, 33.03, 79.17, 35.48] | The audit reads the 100 m local set here; F2a reads the 10 m tiles of `raw/esa_worldcover/IND`, which cover 100% (checked). |
| BRA | Population (WorldPop) | 98.59% | 119,725 | [-73.92, -33.53, -34.83, 5.22] | Pixels with no value inside the WorldPop file are scattered blobs on rivers, estuaries and the coast (the largest in IND: 84.1-88.5 E, 24.4-26.7 N, the Ganges; none is a region of the territory). The file reaches every part of the mask; the pipeline treats a no-value pixel as no population. **Reason recorded, nothing to acquire.** |

## 4. Downloads and their estimated time

| Input | What | Requests | Size per request | Time estimate |
|---|---|---|---|---|
| ERA5 `fg10`, IND | hourly gust, 1995-2014, the three boxes of the missing parts (north block; east end of Arunachal; the delta coast), joined in one rectangle 73.0-98.1 E, 20.9-36.2 N (6,100 native cells, 53% of the grid of the product) | 20 (one per year) | about 0.3 GB | 3.7 to 5.3 h when the CDS queue is short (11 to 16 min per request, D-F1-018/022), up to 20 h if each request waits an hour |
| GWA, IND | the 12 global files | 12 | not measurable (the link needs a browser) | not downloadable by script; the author downloads them from the GWA site if wanted |
| WorldCover 10 m, IND | none: the 92 tiles on disk already cover the mask | 0 | | |
| Population | none: the gaps are water, not territory | 0 | | |

## 5. After (2026-10-25: PRT and BRA as audited on 2026-10-20 after the completion of the GWA, their inputs did not change; IND after the ERA5 extension and the patch of two cells)

### PRT

Mask box (W S E N): [-9.5005, 36.961, -6.1891, 42.1543]; 3,736 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 99.73% | no | 240 | [-8.92, 36.98, -6.22, 41.97] | ok |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_PRT.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_PRT.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: ipsl_cm6a_lr_historical_rsds_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| CMIP6 (F4) sfcWind (worst of 24 files: ipsl_cm6a_lr_historical_sfcWind_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| CMIP6 (F4) tas (worst of 24 files: ipsl_cm6a_lr_historical_tas_PRT.nc) | 24 | 87.55% | no | 11,186 | [-9.47, 37.02, -6.22, 41.87] | informational |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_PRT_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 150 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_a 200 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA weibull_k 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GWA air_density 100 m (country file) | 1 | 100.00% | yes | 0 |  | ok |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 99.12% | no | 788 | [-9.32, 37.02, -6.52, 42.07] | ok |
| Land cover (ESA WorldCover, tiles) | 5 | 100.00% | yes | 0 |  | ok |
| DEM (Copernicus GLO-30, tiles) | 19 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [-34.46, 29.2, -6.189, 44.86] | yes | 442 | 180 | 1.0 |
| Transmission grid (OSM extract) | [-9.443, 37.013, -4.557, 42.339] | no | 7767 | 6689 | 0.833 |
| Roads (GRIP4 regional file) | [-24.53, 5.707, 105.581, 71.164] | yes | 8786966 | 178950 | 0.944 |

### IND

Mask box (W S E N): [68.1862, 8.0765, 97.4152, 35.5013]; 111,191 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 99.94% | no | 1,950 | [68.23, 9.28, 96.47, 34.38] | ok |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_IND.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_IND.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_IND.nc) | 24 | 95.43% | no | 132,306 | [73.77, 21.58, 97.37, 35.48] | informational |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_IND_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA wind_speed 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 150 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 150 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 200 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_a 200 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA weibull_k 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA weibull_k 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GWA air_density 100 m (country file) | 1 | 93.51% | no | 190,907 | [68.23, 15.73, 97.37, 35.48] | **FALHA** |
| GWA air_density 100 m (completed to mask) | 1 | 94.13% | yes | 172,289 | [68.33, 8.63, 97.37, 35.48] | **FALHA** |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 98.07% | no | 61,506 | [68.28, 8.53, 97.37, 35.43] | **FALHA** |
| Land cover (ESA WorldCover, tiles) | 53 | 98.87% | yes | 32,458 | [73.77, 33.03, 79.17, 35.48] | **FALHA** |
| DEM (Copernicus GLO-30, tiles) | 357 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [68.489, 6.747, 97.418, 34.766] | no | 193478 | 193090 | 0.935 |
| Transmission grid (OSM extract) | [68.177, 7.991, 98.201, 34.904] | no | 29996 | 26655 | 0.756 |
| Roads (GRIP4 regional file) | [60.5, -10.937, 155.875, 53.95] | yes | 5244510 | 610658 | 0.986 |

### BRA

Mask box (W S E N): [-73.9897, -33.7463, -34.7931, 5.2649]; 284,017 samples.

| Input | Files | Covered | File box holds the mask box | Not covered (km2) | Region without data (W S E N) | State |
|---|---|---|---|---|---|---|
| ERA5 fg10 annual max (1995-2014) | 1 | 99.98% | no | 1,534 | [-73.78, -33.73, -39.03, 5.22] | ok |
| ISIMIP3b pr (worst of 12 files: gfdl-esm4_historical_pr_BRA.nc) | 12 | 100.00% | yes | 0 |  | ok |
| ISIMIP3b tasmax (worst of 12 files: gfdl-esm4_historical_tasmax_BRA.nc) | 12 | 100.00% | yes | 0 |  | ok |
| CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_BRA.nc) | 24 | 99.91% | no | 6,741 | [-73.18, -33.73, -35.88, 4.27] | ok |
| W5E5 tasmax tasmax (worst of 1 files: tasmax_W5E5v2.0_BRA_19950101-20141231.nc) | 1 | 100.00% | yes | 0 |  | ok |
| GWA wind_speed 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 150 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_a 200 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA weibull_k 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GWA air_density 100 m (country file) | 1 | 99.82% | yes | 15,422 | [-73.92, -33.73, -44.18, 5.22] | ok |
| GSA PVOUT (global file) | 1 | 100.00% | yes | 0 |  | ok |
| Population (WorldPop) | 1 | 98.59% | no | 119,725 | [-73.92, -33.53, -34.83, 5.22] | **FALHA** |
| Land cover (ESA WorldCover, tiles) | 111 | 100.00% | yes | 0 |  | ok |
| DEM (Copernicus GLO-30, tiles) | 817 | 100.00% | yes | 0 |  | ok |

Vector layers (an absent feature is not missing data; extent and features inside the mask only):

| Input | File box (W S E N) | Holds the mask box | Features in file | Features in the mask | 1 degree cells of the mask with a feature |
|---|---|---|---|---|---|
| WDPA protected areas | [-73.982, -34.012, -25.291, 5.272] | no | 4190 | 4150 | 0.968 |
| Transmission grid (OSM extract) | [-75.052, -35.683, -34.8, 5.737] | no | 20633 | 15455 | 0.729 |
| Roads (GRIP4 regional file) | [-117.124, -55.055, -32.4, 32.718] | yes | 3083547 | 549444 | 0.923 |

### Inputs still below 99%

| Country | Input | Covered (after) | Not covered (km2) | Region | Cause |
|---|---|---|---|---|---|
| PRT | CMIP6 (F4) rsds (worst of 24 files: ipsl_cm6a_lr_historical_rsds_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| PRT | CMIP6 (F4) sfcWind (worst of 24 files: ipsl_cm6a_lr_historical_sfcWind_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| PRT | CMIP6 (F4) tas (worst of 24 files: ipsl_cm6a_lr_historical_tas_PRT.nc) | 87.55% | 11,186 | [-9.47, 37.02, -6.22, 41.87] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | CMIP6 (F4) rsds (worst of 24 files: cnrm_cm6_1_historical_rsds_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | CMIP6 (F4) sfcWind (worst of 24 files: cnrm_cm6_1_historical_sfcWind_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | CMIP6 (F4) tas (worst of 24 files: cnrm_cm6_1_historical_tas_IND.nc) | 95.43% | 132,306 | [73.77, 21.58, 97.37, 35.48] | Polygon crop of F1 (keeps the native cells whose centre lies inside the polygon, 1 to 2.5 degree cells): partial cover of the mask by construction. **No result reads it**: F4 reads the global files (`forcing.py`), which cover the globe (72 files checked: latitude -90 to 90, longitude 0 to 359). |
| IND | GWA wind_speed 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA wind_speed 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 150 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 150 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 200 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_a 200 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_k 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA weibull_k 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA air_density 100 m (country file) | 93.51% | 190,907 | [68.23, 15.73, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | GWA air_density 100 m (completed to mask) | 94.13% | 172,289 | [68.33, 8.63, 97.37, 35.48] | Global Wind Atlas cuts each country file at the border GWA draws for that country. The files of IND, PAK and CHN together leave the north block (32.3-35.5 N, 73.8-79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9-29.4 N, 91.6-97.4 E, about 64,100 km2) without a value (D-F1-030). The global files (12 products) exist at `globalwindatlas.info/api/gis/global/<product>/<height>` but redirect to a figshare link behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed, not a script. **Not obtained**; L-047. |
| IND | Population (WorldPop) | 98.07% | 61,506 | [68.28, 8.53, 97.37, 35.43] | Pixels with no value inside the WorldPop file are scattered blobs on rivers, estuaries and the coast (the largest in IND: 84.1-88.5 E, 24.4-26.7 N, the Ganges; none is a region of the territory). The file reaches every part of the mask; the pipeline treats a no-value pixel as no population. **Reason recorded, nothing to acquire.** |
| IND | Land cover (ESA WorldCover, tiles) | 98.87% | 32,458 | [73.77, 33.03, 79.17, 35.48] | The audit reads the 100 m local set here; F2a reads the 10 m tiles of `raw/esa_worldcover/IND`, which cover 100% (checked). |
| BRA | Population (WorldPop) | 98.59% | 119,725 | [-73.92, -33.53, -34.83, 5.22] | Pixels with no value inside the WorldPop file are scattered blobs on rivers, estuaries and the coast (the largest in IND: 84.1-88.5 E, 24.4-26.7 N, the Ganges; none is a region of the territory). The file reaches every part of the mask; the pipeline treats a no-value pixel as no population. **Reason recorded, nothing to acquire.** |

## 6. What the downloads were in the end

The estimates of section 4 were not met by the CDS: the queue, not the size, set the time. The ERA5 gust of IND was extended with one box request per two years (1996-2014) plus 1995 (1 year) and, for the two cells of the mask that the earlier product and the box left empty, 10 requests of two years over a small box. The times of every job, the limits found in the CDS and the test of the daily-statistics dataset are in D-F1-031 (`docs/phases/F1_data_acquisition.md`). GWA of IND: not downloaded; the three files that exist leave the north block and Arunachal without a value (L-047).
