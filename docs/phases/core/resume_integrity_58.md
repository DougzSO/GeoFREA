# Resume integrity, GWA coverage and E1 of IND (COMMAND 58)

Written for Douglas. METHODOLOGY 15.2.1 (A-02, M-F1-02, M-F1-03, M-F1b-01), decisions D-core-042, D-F1-030, D-F1b-017, D-F3-020 and, found afterwards, D-F3-021; OQ-062 closed, OQ-063 opened; L-047 reworded. Branch `fix/resume-integrity`, merged to main at `1d915a1` (2026-10-20); the follow-up of COMMAND 59 (the share caches, D-F3-021) is on `fix/coverage-59`.

## 1. Where each criterion stands

| Criterion of the command | State |
|---|---|
| Tests of steps 2 and 3 pass | yes (section 2) |
| E1 of IND deterministic between two executions | yes, and, after D-F3-021, the pipeline file and two new executions are identical pixel by pixel (section 4) |
| GWA coverage of the mask at least 99% in the three countries, or the reason | PRT 100%, BRA 99.99%, **IND 94.2% with the reason recorded** (section 5): the three GWA files that exist (IND, PAK, CHN) do not hold a value in the two blocks that the contiguous mask added to IND |
| F5 `ran_clean` in the three countries | yes: the checks of 49b (`check_f5_r3.py`) pass in PRT, IND and BRA (`ALL_PASS True`) in the final runs of 2026-10-20 |
| Push done | see the end of the record of COMMAND 59 |

Two things in this command did not come out as the text of the command expected, and one defect of mine was found afterwards: the GWA does not reach 99% for IND (section 5); the comparison of the grid sources is in `docs/data/grid_provenance.md`; the F3 share caches ignored the code, so the first real run did not carry the E1 fix (section 4.4).

## 2. Steps 2 and 3: code fingerprint and content hash (manifest 2.6)

- `core/code_fingerprint.py`: `code_fingerprint(phase)`, the SHA-256 of the normalised syntax tree of the modules of the phase and, transitively, of every `geofrea` module they import (comments, docstrings, blank lines and formatting do not count; the manifest infrastructure does not either). The orchestrator runs a phase again when it differs from the recorded one.
- `core/content_hash.py`: `content_sha256`, the canonical content of an artifact (parquet by column names, types and values; GeoTIFF by data, CRS, transform and nodata; JSON and YAML by the parsed document; PNG by pixels). A consumer is stale only by a changed `content_sha256`; the byte hash stays for the integrity of the file. A manifest of an earlier schema is compared by bytes until a rerun records the hashes; `scripts/stamp_manifest_hashes.py <ISO3> --revision <rev>` writes both into a real manifest without running anything (it was applied to PRT, IND and BRA with the fingerprints of `d004027`).
- Tests (`tests/unit/test_code_fingerprint.py`, 13; `test_content_hash.py`, 9; `test_stamp_manifest_hashes.py`, 3): **a calculation line of F3 changes the fingerprint of F3 to F8 and of nothing before it; a comment, a docstring, a blank line or a reformat changes nothing**; a core module changes only the phases that import it; **rewriting an artifact with identical content and other file metadata does not mark the consumers stale**, another value or type does; an entry without a fingerprint is resumed once and adopts the current one.
- **What the real runs showed.** In the first run after the change, PRT ran `data_acquisition` again (its code changed) and the phases after it were **not** marked stale (the content of its artifact is the same); `data_quality_audit`, `climate_forcing`, `climate_maps`, `hazard_context` and `siting_layers` stayed; `grid_alignment` and `land_eligibility` ran because their own code had changed, and `overview` because the content of `land_eligibility` changed (the E1 fix, section 4). BRA ran `data_acquisition`, whose artifact changed (the new fields of the GWA coverage), and its consumers were marked stale (`stale_upstream`) and ran. These are the phases that depend on changed code or changed content, and no others.

## 3. Step 6: the elevation file leaves F1 and F1b

`<ISO3>_elevation.tif` is no longer a layer of the F1 registry or of the F1b audit (no phase reads it since COMMAND 55, M-F2a-08): the layer, its handler and `resolve_elevation_path` are removed, the entries of `config/audit.yaml` too; the tests that named it use the population layer or were removed.

## 4. Step 4: E1 of IND

### 4.1 What changed between the rounds
Between the round of 2026-10-18 and the current one (200 interior cells more than 20 km from the border, and then all of them): of 105,952 cells of both grids, **19,527 of the 95,127 interior cells had the protected area E1 changed by more than 1e-6 km2** (18,728 by more than 0.01); the median change is 0, the 95th percentile 0.036 km2, the largest 26.6 km2. In the sample of 200 cells 41 changed, by at most 6.2 km2 (sum 1,191.6 to 1,197.9 km2).

### 4.2 What it was not
- **Not the clip, the dissolve or the simplification of the polygon**: the diagnostic computed the shares of the 200 cells four ways (the current clip, the raw WDPA with no clip, the raw file clipped with the old mask, the raw file clipped with the current mask) and the current clip, the raw file and the current mask gave the same result; clipped with the **old** mask the shares of the territory of the old mask are the same (465 of 2,610,287 pixels differ, 464 of them within 5 km of its border) and only the added blocks, which that mask does not hold, differ.
- **Not the CRS of an area calculation**: the quantity that changed is the share of a pixel covered by the polygons, computed in degrees on the lattice, and it changed pixel by pixel on the same lattice (section 4.3); no area in another CRS enters it.
- **Not non-determinism of the rasteriser**: two executions on the same grid give identical arrays.

### 4.3 What it was
The vertices of the WDPA polygons of IND lie on a 0.001 degree lattice, finer than the sub-pixel of the rasteriser; a diagonal edge then passes exactly through the centres of sub-pixels, and which side of the edge the centre falls on is decided by the floating-point noise of the origin of the grid. The origin changed when the mask grew (COMMAND 55), so the same polygons gave other shares in cells far from the border. Between the grid of 2026-10-18 and the current one, over 7,259,375 common pixels, 4,216 differed (by up to 0.10) with the same polygons. Fix (`land_eligibility/fractions.py`, D-F3-020): the sampling points of the polygon coverage are shifted by `TIE_BREAK_DEG = 1e-7` degree east and by that times the irrational `TIE_BREAK_SOUTH_RATIO = 0.618...` south (an equal shift in x and y left the edges of slope minus one tied: 3,582 pixels still differed; with the irrational ratio none does), and the riparian strips, which are lines, are anchored on the absolute lattice of rows and are not shifted. On the real IND the shares of the two grids are identical pixel by pixel over the common pixels. Tests: an edge through sub-pixel centres gives the same shares for every float noise of the origin; the same polygons on two grids of one lattice give the same shares for edges of slope plus and minus one and one and a half; without the tie-break the noise does change the shares; the tie-break moves a share by far less than a sub-pixel; the strips and the riparian shares do not depend on where the grid begins.

### 4.4 The cache that hid the fix (found in COMMAND 59, D-F3-021)
The first real run after the merge reported `land_eligibility` as run, and the check "F3 twice" gave identical results, but the share caches of the pipeline (`interim/<ISO3>/land_eligibility/*_fraction.npz`) were keyed by input file, modification time, grid and categories, and **not by the algorithm**: the shares of the day before were read as current and the fix had not been used. It showed when the protected share computed outside the pipeline differed from the saved file in 219,688 pixels. The key now holds the hash of the normalised source of `fractions.py`; after the rerun, the pipeline file and two new executions of IND are identical (`run1_vs_run2_identical: true`, 0 pixels over 1e-6 against the saved file; sum of the protected share 529,901.5 pixels against 529,978.8 of the old algorithm). PRT, IND and BRA were run again from F1 to F5 with it.

## 5. Step 5 (OQ-062): GWA covers the mask, or the reason

`fetchers/wind.py` measures, for each of the 12 products (4 products x 3 heights), the share of the mask pixels (`all_touched`) with a valid value (`mask_coverage_pct`); below 99% it completes the country file with the files of the same product and height of the countries in `config/countries.yaml` `gwa_neighbours` (IND: PAK, CHN), in that order, only where the country file has no value, nothing resampled, and cuts the result to the mask; the F1b audit records `mask_coverage_pct` and alerts below 99% (D-F1b-017). No country name is in the code.

| Country | Before the completion | After | Neighbours used |
|---|---|---|---|
| PRT | 100% | 100% | none needed |
| BRA | 99.99% | 99.99% | none needed (the 0.01% is at the coast) |
| IND | 94.1% | **94.2%** | PAK, CHN (all 12 products) |

**The completion adds 0.1 percentage point for IND and the reason is in the data.** The part of the mask that stays without value is the two blocks the contiguous mask added: the north block (32.3 to 35.5 N, 73.8 to 79.3 E, about 102,700 km2) and Arunachal Pradesh (26.9 to 29.4 N, 91.6 to 97.4 E, about 64,100 km2), plus about 3,000 km2 of small patches. Each country file of GWA is cut to the border that GWA draws for that country; the file of IND ends at 33.3 N and has a value at 32% (north block) and 22% (Arunachal) of the boxes of the blocks, that of PAK at 15% of the north block, that of CHN at 3% and 30%; none of the three draws the whole territory that GADM gives IND. The wind potential of the added blocks is therefore absent, not zero by physics (L-047). **The recovered blocks are not covered at 99% and cannot be by this route.** The global GWA files exist (`globalwindatlas.info/api/gis/global/<product>/<height>`, 12 products) but the link redirects to figshare behind an AWS WAF challenge (HTTP 202, `x-amzn-waf-action: challenge`): a browser is needed. Coverage audit of all inputs: `docs/data/coverage_audit_59.md`.

**Variation of the wind potential of IND** (central scenario, reference climate; D-F5-031 against the final run of 2026-10-20): capacity 189.79 to 189.81 GW (+0.01%), energy 299.47 to 299.50 TWh per year (+0.01%); permissive 630.35 to 630.41 GW. The change is the 0.1 point of the mask the neighbours filled plus the E1 of F3 (D-F3-020 and D-F3-021); nothing is added in the north block or in Arunachal.

## 6. The transmission grid (OQ-063)

`docs/data/grid_provenance.md` holds the metadata of `grid.gpkg` (one layer `grid`, LineString, EPSG:4326, one field `source` in gridfinder and openstreetmap, 3,678,243 lines, change date 2019-11-12 in `gpkg_contents`), the draft of the provenance for the author to complete (source, version, licence) and the comparison with the OSM extracts by country (total length, number of lines, lines in the blocks IND gained). **The source of the grid is not changed in the code**; the change is Group 3 and needs the confirmed provenance.

## 7. Tests and records

The full suite of the branch passes (1,523 tests at `1ea2d9e`; the later commits of COMMAND 59 and 60 were run with their own subsets and the full suite before the merge). Decisions: `docs/phases/core.md` D-core-042, `F1_data_acquisition.md` D-F1-030, `F1b_data_quality_audit.md` D-F1b-017, `F3_land_eligibility.md` D-F3-020 and D-F3-021; `docs/OPEN_QUESTIONS.md` (OQ-062 removed, OQ-063 added); `docs/LIMITATIONS.md` L-047.
