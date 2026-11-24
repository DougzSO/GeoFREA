# GeoFREA

GeoFREA is a spatially explicit, open-data framework for the climate adaptation of power supply planning. It measures how climate change redistributes the generation of the existing and planned fleet of a country (hydro, solar, wind), the supply gap this creates and where to add solar and wind, at the lowest cost and risk, to compensate for it. Brazil, India and Portugal are the test cases; the code serves any country with data (PhD thesis, Douglas). The method is `docs/METHODOLOGY.md` (v2.0.0).

The results of v1 (tags `v1.0`, `v1.1`) are summarised in [`docs/v1/record.md`](docs/v1/record.md); `git checkout v1.1` with `ci/constraints.txt` reproduces them.

## Phases

The chain F1 to F6, F7b and F8 comes from v1 and is kept; F4 and F7 are rebuilt and the modules M1 (fleet risk), M2 (supply gap) and M3 (adaptive expansion) are new, as specified in `docs/METHODOLOGY.md`. The code still holds the v1 versions of F4, F7 and F8 until they are rebuilt. Each phase is a package under `src/geofrea/` and writes its artifacts to the per-country manifest.

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
4. `pytest -n 3` runs the suite; see "Tests" below.

`python main.py <ISO3>` runs only the phases listed in `run.target_phases` of `config/settings.yaml` and what they require; later phases are named with `--phases`. `--plan` prints, per country, the phases the invocation would execute, resume or find stale, with the reason, and writes nothing. `--real-run` is required to run the phases from F6 onwards on a real country, and the decision phases (F7, M1, M2, M3) refuse real data until the tag `prereg-v2` exists (METHODOLOGY M-F7-13). Where the outputs are, what each phase costs and the rest of the options are in [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md).

The reference store (`GeoFREA_data/references/`, what `config/deferred_checks.yaml` compares a run with) is never written by a run. After a round you accept, publish it explicitly: `python main.py PRT IND BRA --publish-reference`, or `python scripts/publish_reference.py PRT IND BRA --note "..."`.

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

The hourly `fg10` files (the per-year bbox files in `GeoFREA_data/raw/era5/_global`, and `BRA/BRA_fg10_hourly.nc`, `PRT/PRT_fg10_hourly.nc`; 63 files, 38.65 GB) are in `GeoFREA_data/raw/era5`, copied back from the archive. The archive keeps its own copy, with the SHA-256 of each file in `manifest.json`: `D:\Douglas\DOUTORADO\database\archive\geofrea_2026-10\raw\era5`. The pipeline does not read them (it reads the annual maxima `<ISO3>_fg10_annual_max.nc`); they are the input of `scripts/acquire_era5_gust.py` and of a rebuild of the cache `era5_reduction` (about 27 min of computing, no download). To check the hashes (read-only):

```
python scripts/verify_era5_hourly.py --archive D:\Douglas\DOUTORADO\database\archive\geofrea_2026-10
```

It compares every `year_sha256` and `reduced_sha256` of `era5_registry.json` and, with `--archive`, each file against the manifest (`GEOFREA_DATA_DIR` or `--data-root` gives the data directory); exit code 0 when all agree.

## Where things are

- Index of the documents: [`docs/README.md`](docs/README.md).
- Method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), the only place the method is defined. How the pipeline works and what it costs: [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md).
- Status per phase and country: [`docs/PROGRESS.json`](docs/PROGRESS.json); open items in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md); limits in [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md); decisions in [`docs/DECISIONS.md`](docs/DECISIONS.md) and per phase in `docs/phases/`.
- Conventions: [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) and [`CLAUDE.md`](CLAUDE.md).
- Data and outputs live outside the repository, in `GeoFREA_data/` (`raw`, `interim`, `outputs`, `logs`, `archive`). Measurement and audit reports that the documents cite are in `docs/evidence/`.
