# Pipeline state and `main.py` wiring — what exists, what runs, what is missing

Date: 2026-10-07. Written when the F4 phases (J-3, J-4, J-5) and the F2b physical-unit layers (H-4) were wired into `main.py`
and a command line was added. Sources: `main.py`, `config/settings.yaml`, the phase records in `docs/phases/`, and a
count of the code in `src/geofrea/`. Statements about runs reflect what was executed on 2026-10-06/07.

## 1. How to run

```
python main.py PRT                  # one country, every phase of settings.yaml run.target_phases, in dependency order
python main.py PRT BRA IND          # several countries, one after the other
python main.py BRA --phases grid_alignment --rerun grid_alignment
python main.py                      # run.countries from settings.yaml, else every thesis country (never ZZZ)
```

The orchestrator (`core/orchestrator.py`) derives the order from each phase's `requires` and `produces` artifact keys, skips
what the manifest already records as successful, marks dependents of a re-executed phase `stale_upstream`, and stops a
branch when one of its inputs failed (A-09). The manifest is `outputs/<ISO3>/manifest.json`.

## 2. Phases registered in `main.py`

| Order | Phase | Method phase | Requires | Produces | In the default run |
|---|---|---|---|---|---|
| 1 | `data_acquisition` | F1 | nothing | `layer_registry` | yes |
| 2 | `data_quality_audit` | F1b | `layer_registry` | `audit_report` | yes |
| 3 | `grid_alignment` | F2a | `layer_registry` | `aligned_rasters`, `aligned/<layer>` (elevation, slope, solar, land cover, population, roads, grid, lakes, rivers, plants, the three `distance_capped` flags, 12 wind layers) | yes |
| 4 | `siting_layers` | F2b (H-4) | `aligned_rasters` | `siting_layers` (12 physical-unit layers, no normalization) | yes |
| 5 | `climate_forcing` | F4 (J-3) | `aligned_rasters` | `forcing`, `forcing_masked`, `members` | yes |
| 6 | `hazard_context` | F4 (J-4) | `members`, `aligned_rasters` | `hazard_context` | yes |
| 7 | `climate_maps` | F4 (J-5) | `forcing`, `forcing_masked` | `climate_maps` (one PNG per member) | yes |
| — | `suitability_criteria` | legacy F2b | `aligned_rasters`, `layer_registry` | `suitability_criteria_result` | **no** (registered, run only if named) |

Consistency of this graph is checked by `tests/unit/test_main.py` (every required artifact has exactly one producer).

## 3. What a run depends on that is not a phase

Some inputs are acquired once, outside the graph, because they are large or queue for hours. A phase that needs them fails
loud (named error) if they are absent:

| Input | Acquired by | Used by | Status |
|---|---|---|---|
| CMIP6 monthly `rsds`, `tas`, `sfcWind`, 14 models, `historical` + 3 SSPs, global files + registry | `scripts/acquire_cmip6_resource_channel.py` | `climate_forcing` | complete (CESM2 excluded by realization mismatch) |
| ISIMIP3b daily `tasmax`, `pr` crops (5 GCMs, 4 experiments, 3 countries) | copy from CRAEI (OQ-036) | `hazard_context` | **2041-2070 only**; 2071-2100 not acquired (see section 5) |
| ERA5 gust annual maxima, 1995-2014 | `scripts/acquire_era5_gust.py` | `hazard_context` | complete, mainland only |
| Existing-plant trackers (GEM) | F5-1 (not started) | F7b | not acquired |

## 4. Code that exists but is not a phase, and phases that do not exist

| Piece | State |
|---|---|
| `land_eligibility/cells.py` (F3) | kernels on synthetic grids: global 0.05 degree lattice, `cell_id`, 5 x 5 aggregation, candidate filter. **No phase, no real data.** |
| F3 phase, `candidates_<tech>.parquet`, COGs | not built (I-2, I-3) |
| Exclusion layers E1-E6 (H-3) | not built; E1 (WDPA) and E2 (lakes) exist only as legacy criteria, E3 needs `riparian_setback_km` (OQ-002), E4 slope threshold, E5 land-cover classes (OQ-015), E6 population density (OQ-003). Blocked on research (Stage R). |
| F5 technical_potential, F6 lcoe_modeling, F7 robustness_analysis, F7b external_validation, F8 results_synthesis, E1 explorer | directories exist, **no code** |
| Legacy `suitability_criteria` (2,187 lines) | still in the repository and registered. It computes 14 normalized criteria for a weighted overlay, which M-F2b-04 forbids; it is kept only because its E1-E3 pieces are to be reused in H-3 and its removal is part of H-5/H-6. It is not in the default run. |
| `siting_layers` outputs | written under `outputs/<ISO3>/siting_layers/artifacts/`; no consumer yet (F3 will read them) |

## 5. What the F4 phases produce and their known limits

- `forcing.parquet`: `cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind` for the reference member `m0` (identity) and 36 members
  (6 GCMs x 3 SSPs x 2 windows), on the 0.05 degree cells that hold at least one in-country pixel of the F2a grid.
- `forcing_masked.parquet`: the cell-members removed because `delta_wind` fell outside `wind_factor_valid_range` (0.5-1.5;
  OQ-042 option C). Absence in `forcing.parquet` is always declared here (D-F4-004); `assert_forcing_usable()` is the guard F5 must
  call (it fails if a factor is out of range or an absence is undeclared).
- `members.yaml`: members, channels, realization, native grid, TCR, `tcr_exception` for IPSL-CM6A-LR, sources with sha256, masked
  counts, factor ranges after masking.
- `hazard_context.parquet`: for the members with a hazard channel (GFDL-ESM4, IPSL-CM6A-LR, MRI-ESM2-0 x 3 SSPs, window 2041-2070):
  TX35/TX40 days, Rx5day, wet-day P95 exceedance, with reference values, plus the scenario-invariant ERA5 gust. **No hazard row exists
  for 2071-2100**: D-F4-002 accepted that download (~183 GB) but it has not been made; members of that window are declared
  `hazard: false` in `members.yaml`.
- Context indicators only: nothing here enters regret or satisficing until OQ-007 gives a loss function of Tier 1 or 2.
- Method deviations recorded: IPSL-CM6A-LR kept above the likely TCR range (M-F4-02 item 5); `delta_wind` is a ratio of 3 x 3
  neighbourhood means (M-F4-03); masked cell-members (M-F4-07).

## 6. Gaps in the wiring itself

- `hazard_context` and `climate_forcing` read the CMIP6 registry, ISIMIP3b and ERA5 from fixed locations under
  `GEOFREA_DATA_DIR/raw`; a missing file raises a named error, but there is no phase that acquires them.
- The orchestrator manifest of PRT, IND and BRA recorded the older artifact keys of `grid_alignment`; a changed `produces` set
  raises `StaleManifestEntryError`, so the first `python main.py <ISO3>` after this change needs `--rerun grid_alignment`.
- `climate_forcing`, `hazard_context` and `climate_maps` do not yet depend on `data_quality_audit`; the audit does not gate them.
- No phase writes the thesis outputs (T-R, T-O); that is F8.
