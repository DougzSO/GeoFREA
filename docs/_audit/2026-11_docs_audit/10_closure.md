# What stays open after the docs audit of 2026-11-13 (report 10)

Written for: the author. State of the repository at HEAD `b73b95f` plus the changes of 2026-11-15 (commands F1 and F2 and batches D6b to D9). Nothing here is decided; each item says who acts and when.

## Open questions and verdicts

| Item | State | Next step |
|---|---|---|
| OQ-087 (primary `tau`) | `awaiting_verdict`: nothing implemented, `tau_lcoe_usd_per_mwh` is null, no rule decides | author verdict after the comparison of the two values per country and technology |
| OQ-088 (upper limit of the `tau` range for Portugal) | `awaiting_verdict`: same | author verdict on the upper limit |
| OQ-094 (rule of the sensitivity axes of `tau`, `CF_min` and `q_ref`) | `awaiting_verdict`, not decided on purpose | author verdict; then M-F7-07 is updated |
| DEC-070 to DEC-074 (OQ-092, OQ-093, OQ-089, OQ-090, OQ-091) | recorded on 2026-11-15 as the author's decision delegated to the assistant, open to veto in the final command | veto or confirmation by the author |

To check by the author (no access on 2026-11-15, HTTP 403): the Annual Report 2025-26 of the Ministry of Power and the PIB reply of 04/02/2026 (the figures 447, 138 and 1,029 GW, DEC-070); the RT ONS DGL 0189/2025 (curtailment 0.5, 3.6 and 9.3 %, DEC-073); the IRENA Data Appendix (Figure A1, country WACC of 2021, DEC-072); the AC or DC basis of the IRENA solar capacity factor against `pvout_kwh_kwp_day` (DEC-073). The values of DEC-072 stay `verified: false`.

`docs/METHODOLOGY.md` (not edited in this round) still says in M-F7-02 and in the row 19.4.1 of the changelog that "OQ-020 and OQ-091 are open"; OQ-091 is closed by DEC-074 (`q_ref` stays 0). Change it with the next PATCH of METHODOLOGY.

## Conformance rows still `not found` (report 09)

Of the 35 rows, 23 got a symbol or a test (the verdict (a)); the 12 below were left as they are. Some (a) rows still have one `not found` cell, because only the cell with evidence was written.

- **(c) real gap, no L or OQ names it:** M-F1-05 (`write_annual_maxima_incremental` has no test), A-11 (the provenance headers of the copied code are not checked by a test), A-13 (no test that a function implementing a rule carries `Implements: M-`).
- **(d) not decided:** M-F1-04 (row `partial`, reason not written), M-F1b-01 on the wind resolution and on the coverage of the new layers (`partial`), U-02, U-06 (the row says `strict` and `lenient`, the code has `restrictive` and `permissive`), U-07, V-02 (partial evidence), V-06, V-07.

## Markers `<!-- lint: skip -->` kept (25 lines in 8 files, were 27)

All are dated records of something that no longer exists, except two groups.

- `docs/phases/core.md` lines 53, 55, 71, 73, 91, 99, 114, 115 and 123: removed scripts, tests and functions (`scripts/migrate_manifest_2_0_to_2_1.py`, `scripts/migrate_clip_cache_keys.py`, `scripts/restamp_caches.py`, `scripts/plot_plants_over_grid.py`, `_build_suitability_criteria_inputs` and the tests of the old audit inputs).
- `docs/phases/F1_data_acquisition.md` lines 87, 89, 91, 171, 175 and 193: removed scripts (`scripts/place_local_inputs.py`, `scripts/era5_ext_queue.py`, `scripts/extend_era5_gust.py`, `scripts/patch_era5_cells.py`) and symbols; line 87 cites `netCDF4_.py`, a file of the xarray library, not of this repository.
- `docs/phases/F3_land_eligibility.md` lines 162 and 181, `docs/phases/F4_climate_forcing.md` lines 32 and 36, `docs/phases/F5_technical_potential.md` line 70, `docs/LIMITATIONS.md` line 78, `docs/data/coverage_audit_59.md` line 125: removed scripts and a removed test.
- `tests/unit/test_methodology_changelog.py` lines 142, 146 and 147: the identifier `M-F5-010` is a fixture of that test, not a citation.

Two markers were removed in this round (`docs/phases/E5b.md` line 47 and `docs/phases/F2a_grid_alignment.md` line 48): their targets exist.

## Files and tests outside this round

- **Archived scripts with `parents[3]` and `parents[1]`** (`docs/_archive/2026-11/2026-10_data_diagnostics_scripts/`): written for the old depth, do not run from the archive. D10 deletes them.
- **Three notes of `config/parameters.json`** (lines 737, 1493 and 2249, the access road of the three countries) cite `docs/phases/F5/groups1-2_implementation_report.md`, which now is `docs/_audit/groups1-2_implementation_report.md`. Editing them moves the configuration fingerprint of 7 phases. Listed as item 9 of `docs/_audit/window_list_131.md`; to be done when the next configuration fingerprint is accepted (COMMAND 155).
- **Protected-area footprint of PRT and BRA:** the regression test is back (`tests/regression/test_protected_footprint.py`), frozen on 2026-11-15 on the local data; it is skipped without `GEOFREA_DATA_DIR` in `.env`. The WDPA release is not recorded in the file or in the layer registry: the fixture keeps the sha256 of the file.
- **Bibliography:** `docs/thesis/methods/refs_grupos_4_5_7.bib` (not committed, goes in COMMAND 165) has `irena2023financeappendix` (title and year to check against the PDF) and `wb_gdpdefl_usa`. Missing fields that were not invented: the Annual Report 2025-26 of the Ministry of Power (publisher address, month, URL) and the RT ONS DGL 0189/2025 (URL, date). The PIB entry was not added because the release was not confirmed.
- **Items of the F1 report and of batches D6b to D9** that were not in the conversation of 2026-11-15 could not be listed here; only what the commands said is above.
