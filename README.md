# GeoFREA

GeoFREA is a spatially explicit, open-data framework that estimates the technical potential and site-level LCOE of utility-scale solar PV and onshore wind on a 0.05 degree cell grid in Brazil, Portugal and India, and ranks cells by how well their economic ranking holds across climate futures and techno-economic uncertainty (PhD thesis, Douglas).

## Phases

F1 data acquisition, F1b data quality audit, F2a grid alignment, F2b siting layers, F3 land eligibility, F4 climate forcing, F5 technical potential, F6 LCOE modeling, F7 robustness analysis, F7b external validation, F8 results synthesis. Each phase is a package under `src/geofrea/` and writes its artifacts to the per-country manifest.

The names of the phases (the id is what the code, the manifests and the output folders use; the English name is what the plan and the log print) are kept in `config/phases.yaml`; this table is generated from it by `scripts/render_phase_tables.py`.

<!-- phases:begin (generated from config/phases.yaml by scripts/render_phase_tables.py; do not edit by hand) -->
| Code | Phase id | Name | Group | Orchestrated |
|---|---|---|---|---|
| F1 | `data_acquisition` | Data acquisition | Data | yes |
| F1b | `data_quality_audit` | Data audit | Data | yes |
| - | `external_inputs` | Climate inputs registry | Climate | yes |
| F2a | `grid_alignment` | Grid alignment | Territory | yes |
| F2b | `siting_layers` | Siting layers | Territory | yes |
| F3 | `land_eligibility` | Land eligibility | Territory | yes |
| F4 | `climate_forcing` | Climate signal | Climate | yes |
| - | `hazard_context` | Hazard context | Climate | yes |
| - | `climate_maps` | Climate maps | Climate | yes |
| - | `overview` | Country overview | Territory | yes |
| F5 | `technical_potential` | Technical potential | Potential | yes |
| - | `potential_maps` | Potential maps | Potential | yes |
| F6 | `lcoe_modeling` | Levelized cost | Economics | yes |
| - | `sample_size_convergence` | Sample-size convergence | Economics | yes |
| - | `lcoe_maps` | Cost maps | Economics | yes |
| F7 | `robustness_analysis` | Robustness and hypotheses | Robustness | yes |
| - | `robustness_maps` | Robustness maps | Robustness | yes |
| - | `exploratory_analysis` | Exploratory analyses | Robustness | yes |
| - | `cross_country_h4` | Cross-country comparison | Robustness | no |
| F7b | `external_validation` | External validation | Validation | yes |
| F8 | `results_synthesis` | Results synthesis | Synthesis | yes |
| E1 | `explorer` | Explorer | Platform | no |
<!-- phases:end -->

## Run

1. Copy `.env.example` to `.env` and set the data directories (`GEOFREA_DATA_DIR` at least).
2. `pip install -c ci/constraints.txt -e ".[dev]"`. The constraints file pins the libraries the tests and the manifests were made with (pandas, pyarrow, numpy, geopandas, rasterio, pyproj, ruff); a plain `pip install -e ".[dev]"` takes the newest ones, and geopandas 1.2.0 breaks 52 figure tests (OQ-074).
3. `python main.py PRT` (one country, every phase in `config/settings.yaml`), or `python main.py BRA --phases technical_potential`; upstream phases that are stale are added automatically. `python main.py --help` lists the options.
4. `pytest -n 3` runs the suite; see "Tests" below for the time and the memory.

### The whole pipeline, in the order a real country is run

`python main.py <ISO3>` runs only the phases listed in `run.target_phases` of `config/settings.yaml`, and what they require: F1 `data_acquisition`, F1b `data_quality_audit`, F2a `grid_alignment`, F2b `siting_layers`, F3 `land_eligibility`, `external_inputs`, F4 `climate_forcing`, `hazard_context`, `climate_maps`, and `overview`. The later phases are registered in `main.py` and are named with `--phases`; the orchestrator adds the upstream phases that are stale, so each line below can be run alone, in this order:

```
python main.py PRT IND BRA                                                  # F1 to F4, F3 and the figures of the default list
python main.py PRT IND BRA --phases technical_potential,potential_maps     # F5 (the two parameter-dependent phases) and its maps
python main.py PRT IND BRA --phases lcoe_modeling,lcoe_maps --real-run     # F6 (--real-run: see below)
python main.py PRT IND BRA --phases robustness_analysis,sample_size_convergence,robustness_maps --real-run   # F7
python main.py PRT IND BRA --phases external_validation --real-run         # F7b (needs the plant inventory, OQ-057)
python main.py PRT IND BRA --phases results_synthesis --real-run           # F8 (reads the results of every country)
python main.py PRT --phases lcoe_modeling --plan                           # what the invocation would do; nothing runs, no manifest is written
```

`--real-run` is required to run the phases of F6 onwards (`lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, `cross_country_h4`, `external_validation`, `lcoe_maps`, `robustness_maps`, `results_synthesis`) on a real country: without it `main.py` refuses the invocation, lists the phases and runs nothing. A synthetic country does not need it, and the pre-registration guard (the tag `prereg-v1`) still applies with it. `--plan` prints, per country, the phases the invocation would execute, the ones it would resume from the manifest and the ones that would be stale, with the reason; it executes nothing and writes no manifest.

The reference store (`GeoFREA_data/references/`, what `config/deferred_checks.yaml` compares a run with) is never written by a run of the pipeline. After a round that you accept, publish it explicitly: `python main.py PRT IND BRA --publish-reference`, or `python scripts/publish_reference.py PRT IND BRA --note "..."` (`--first` for a country with no reference, `--allow-without-reference <phase>` for a new phase). Both compare every phase of the round with the current reference and refuse, writing nothing, if one is different or has no comparison (OQ-080, `docs/phases/core.md` D-core-054).

Why they are outside `target_phases` (`config/settings.yaml`): F5 and the phases after it fail loudly, by name, when a parameter they consume has no value, and F6 onward need F5 tables and the F6 parameters and ranges (OQ-001, OQ-016 to OQ-019); a plain `python main.py PRT` therefore runs what has values and is safe to repeat, and the later phases are asked for by name. `--production` refuses to start when a consumed parameter is a proxy. F1 to F8 have run on PRT, IND and BRA (v1.0, `docs/PROGRESS.json`; the exact sequence is in "Reproduce v1.0" below). The phase caps of `config/memory_budget.json` were measured with one country per process (as in the clean round of COMMAND 133), so for BRA run `python main.py BRA ...` on its own; the caps bind the run (`GEOFREA_MEMORY_CAPS=0 switches them off).

## Reproduce v1.0

The results of the thesis (tag `v1.0`) come from the sequence below, run with `GEOFREA_DATA_DIR` set, one country per process (the memory caps of `config/memory_budget.json` were measured that way, COMMAND 133, V179c), in the order of the commands of the closing sequence (COMMANDS 179 to 190). Before each real run use `--plan` with the same arguments: it must show only the phases you expect to execute. `GEOFREA_MEMORY_CAPS=0` was used only where a phase's cap is recorded as exceeded in `docs/_audit/` (BRA `robustness_analysis`, BRA `results_synthesis`).

```
# F1 to F5 and the maps (COMMANDS 130 to 178): python main.py PRT IND BRA ; python main.py PRT IND BRA --phases technical_potential,potential_maps
# 179 to 182 (F6 and the sample size of U-04), one country per process, PRT, then IND, then BRA
python main.py <ISO> --phases lcoe_modeling,sample_size_convergence --real-run --production
# 183 to 186 (F7, window 2041-2070 core and 2071-2100 sensitivity, and the H4 verdict across countries)
python main.py <ISO> --phases lcoe_modeling,robustness_analysis --real-run --production
# 187 to 188A (F7b by windows of rows, then the maps)
python main.py <ISO> --phases external_validation,lcoe_maps,robustness_maps --real-run
# 189 (scale check of V-07, files under <phase>__0p1deg, manifest__0p1deg.json)
python main.py <ISO> --scale 0p1deg --phases lcoe_modeling,sample_size_convergence,robustness_analysis --real-run
# 190 to 191A (F8; the H4 verdict reads all three countries, so PRT and IND must have their h4_country tables first)
python main.py <ISO> --phases results_synthesis --real-run
# last step, only after the gate passes
python main.py PRT IND BRA --publish-reference
```

`cross_country_h4` runs once per invocation after F7 and compares every configured country (D-core-056); it refuses when a country has no `h4_country` table. The pre-registration guard applies to every one of these runs: the aggregate digest of the pre-registered subset is `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` and the tag is `prereg-v1`.

Measured wall time of the phases that matter (from `started_at` and `finished_at` of the manifests of the accepted runs; the pixel-level phases F1 to F5 add about 23 minutes for IND and 31 for BRA (PRT less) and are not repeated unless their code changes):

| Phase | PRT | IND | BRA |
|---|---|---|---|
| `lcoe_modeling` (4000 samples) | 1.5 min | 22.8 min | 52.2 min |
| `sample_size_convergence` | 1.0 min | 8.5 min | 17.3 min |
| `robustness_analysis` (F7, 2 windows) | 7.6 min | 154.5 min (2 h 35) | 510.4 min (8 h 30) |
| `external_validation` (F7b) | 3 s | 29 s | 74 s |
| `lcoe_maps` and `robustness_maps` | 30 s | 71 s | 62 s |
| `results_synthesis` (F8) | 25 s | 40 s | 76 s |
| 0.1 degree scale check (F6, convergence, F7) | 3 min | 44 min | 120 min |

The peaks of memory per phase are in `config/memory_budget.json`; the machine of the runs has about 6 GB of RAM (V179c), and BRA `robustness_analysis` is the longest single step. `GEOFREA_DATA_DIR/references/` holds the reference published with the tag; the tag message lists the manifest hashes. E1 (the explorer) is not part of v1.0 (OQ-013).

## Reproduce v1.1

The tag `v1.1` adds to `v1.0` the exploratory analyses of DEC-098 (corrected by DEC-100) and the variant `exact_location_only` of F7b (D-F7b-010). **No pre-registered result changes**: the aggregate digest of the pre-registered subset is the one of `v1.0` (`1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235`), and the content hashes of every artifact of F1 to F7b and of `cross_country_h4` are those of `v1.0` (the primary rows of F7b are equal; the variant is written beside them). Tables T-R1 to T-R12 are identical; T-R9 gains the `row_set` column, and T-X1 to T-X4 are new. Start from the data and the manifests of `v1.0`, then, one country per process (BRA with the memory caps off, as they were measured for the phases of `v1.0`):

```
# 208 to 208A: the F7 code fingerprints are adopted under proof (D-core-057); nothing is computed
# 210 to 213A: the exploratory phase (H5c without tau, VUL, V_f, tau on the cell basis) and its outputs T-X1 to T-X4
python main.py <ISO> --phases exploratory_analysis,results_synthesis --real-run
# 212: the F7b variant, then F8 again
python main.py <ISO> --phases external_validation,results_synthesis --real-run
# BRA: GEOFREA_MEMORY_CAPS=0 python main.py BRA --phases exploratory_analysis,results_synthesis --real-run
```

`python main.py <ISO> --phases exploratory_analysis,results_synthesis --real-run --plan` lists what would run and finds nothing stale outside those two phases. Measured (COMMAND 213A): `exploratory_analysis` 4.5 s (PRT), 52.8 s (IND) and 190.1 s (BRA, peak 1,780 MB, cap 2,624 MB); `results_synthesis` 26.8 s, 52.3 s and 307.2 s. The exploratory outputs are labelled `exploratory: true` in every provenance and never feed T-R1 to T-R12; the choices that would change a result (eligibility, tau on the cell basis, H5c and VUL as primary) go to v2 with a new pre-registration (OQ-116, `docs/OPEN_QUESTIONS.md`).

## The synthetic country ZZZ

ZZZ is a 30 x 20 pixel country built by hand so every result can be computed by hand (METHODOLOGY A-06). To build its inputs and run the pipeline on it from a clean clone:

1. `python scripts/generate_zzz_fixture.py`: writes the raw layers under `GEOFREA_DATA_DIR/fixtures/synthetic_zzz/` and the climate inputs under `GEOFREA_DATA_DIR/raw/`. It reads `GEOFREA_DATA_DIR` from the environment or from the repository `.env`, as `main.py` does. Use a scratch `GEOFREA_DATA_DIR`: a real data directory is not to be mixed with the fixture (`ZZZ_CLIMATE=0` skips the climate inputs).
2. `python main.py ZZZ` runs the default phases of `config/settings.yaml` (F1 to F4, the support phases, F3 and the two figure phases `climate_maps` and `overview`; about 3 minutes). `python main.py ZZZ --phases technical_potential,lcoe_modeling` adds F5 and F6.
3. **F6 onwards is not reached by `main.py ZZZ`**: `sample_size_convergence` fails because `sampler.max_size_for_convergence` is null in `config/experiments.yaml` (the author's ceiling, D-F6-004), and F7 to F8 have no real-country inputs yet. They run, with test values of the configuration and a synthetic power curve, through `pytest tests/synthetic` (the end-to-end tests `tests/synthetic/test_zzz_end_to_end.py` and `test_zzz2_end_to_end.py`, which is what the CI job does).

## Tests

- `pytest -n 3` runs the whole suite in three processes: about 24 minutes against 46 in one (2,541 tests; the second of two runs on the development machine passed all of them). Three workers hold up to 2.7 GB, so on a machine with 6 GB close the browser and the editor first, or use `-n 2`.
- `pytest tests/unit -m "not slow" -n 3` is what the CI unit job runs on every push (Python 3.11 and 3.12, with the constraints above). The synthetic worlds and the frozen V-01 regression have their own workflows.
- The memory caps of the pipeline (`config/memory_budget.json`, `phase_caps`) bind `python main.py`, not the tests; `GEOFREA_MEMORY_CAPS=0` switches them off for a run.

## The ERA5 hourly files

The hourly `fg10` files (the per-year bbox files in `GeoFREA_data/raw/era5/_global`, and `BRA/BRA_fg10_hourly.nc`, `PRT/PRT_fg10_hourly.nc`; 63 files, 38.65 GB) are in `GeoFREA_data/raw/era5`, copied back from the archive of COMMAND 37 on 2026-11-12 (COMMAND 138). The archive keeps its own copy, with the SHA-256 of each file in `manifest.json`: `D:\Douglas\DOUTORADO\database\archive\geofrea_2026-10\raw\era5`. The pipeline does not read them (it reads the annual maxima `<ISO3>_fg10_annual_max.nc`); they are the input of `scripts/acquire_era5_gust.py` and of a rebuild of the cache `era5_reduction` (about 27 min of computing, no download). To check the hashes (read-only):

```
python scripts/verify_era5_hourly.py --archive D:\Douglas\DOUTORADO\database\archive\geofrea_2026-10
```

It compares every `year_sha256` and `reduced_sha256` of `era5_registry.json` and, with `--archive`, each file against the manifest (`GEOFREA_DATA_DIR` or `--data-root` gives the data directory); exit code 0 when all agree.

## Where things are

- How the pipeline works, what each phase reads, writes and costs, and how to run it: [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md) (living document).
- Method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), the only place the method is defined; overview in [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).
- Status per phase and country: [`docs/PROGRESS.json`](docs/PROGRESS.json); open items in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md); limits in [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md); decisions per phase in `docs/phases/`.
- Conventions: [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) and [`CLAUDE.md`](CLAUDE.md).
- Data and outputs live outside the repository, in `GeoFREA_data/` (`raw`, `interim`, `outputs`, `logs`, `archive`); audit and performance records are in `docs/_audit/` (index in its README).
- The legacy port documents of September 2026 were removed in D10 and are recoverable in commit 2726333.
