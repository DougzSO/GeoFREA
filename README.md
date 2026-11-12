# GeoFREA

GeoFREA is a spatially explicit, open-data framework that estimates the technical potential and site-level LCOE of utility-scale solar PV and onshore wind on a 0.05 degree cell grid in Brazil, Portugal and India, and ranks cells by how well their economic ranking holds across climate futures and techno-economic uncertainty (PhD thesis, Douglas).

## Phases

F1 data acquisition, F1b data quality audit, F2a grid alignment, F2b siting layers, F3 land eligibility, F4 climate forcing, F5 technical potential, F6 LCOE modeling, F7 robustness analysis, F7b external validation, F8 results synthesis. Each phase is a package under `src/geofrea/` and writes its artifacts to the per-country manifest.

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
python main.py PRT IND BRA --phases lcoe_modeling,lcoe_maps                # F6
python main.py PRT IND BRA --phases robustness_analysis,sample_size_convergence,robustness_maps   # F7
python main.py PRT IND BRA --phases external_validation                    # F7b (needs the plant inventory, OQ-057)
python main.py PRT IND BRA --phases results_synthesis                      # F8 (reads the results of every country)
```

Why they are outside `target_phases` (`config/settings.yaml`): F5 and the phases after it fail loudly, by name, when a parameter they consume has no value, and F6 onward need F5 tables and the F6 parameters and ranges (OQ-001, OQ-016 to OQ-019); a plain `python main.py PRT` therefore runs what has values and is safe to repeat, and the later phases are asked for by name. `--production` refuses to start when a consumed parameter is a proxy. F5 and `potential_maps` have run on PRT, IND and BRA; F6 and the phases after it have not run on a real country (`docs/PROGRESS.json`). The phase caps of `config/memory_budget.json` were measured with one country per process (as in the clean round of COMMAND 133), so for BRA run `python main.py BRA ...` on its own; the caps bind the run (`GEOFREA_MEMORY_CAPS=0 switches them off).

## The synthetic country ZZZ

ZZZ is a 30 x 20 pixel country built by hand so every result can be computed by hand (METHODOLOGY A-06). To build its inputs and run the pipeline on it from a clean clone:

1. `python scripts/generate_zzz_fixture.py`: writes the raw layers under `GEOFREA_DATA_DIR/fixtures/synthetic_zzz/` and the climate inputs under `GEOFREA_DATA_DIR/raw/`. It reads `GEOFREA_DATA_DIR` from the environment or from the repository `.env`, as `main.py` does. Use a scratch `GEOFREA_DATA_DIR`: a real data directory is not to be mixed with the fixture (`ZZZ_CLIMATE=0` skips the climate inputs).
2. `python main.py ZZZ` runs the default phases of `config/settings.yaml` (F1 to F4, the support phases, F3 and the two figure phases `climate_maps` and `overview`; about 3 minutes). `python main.py ZZZ --phases technical_potential,lcoe_modeling` adds F5 and F6.
3. **F6 onwards is not reached by `main.py ZZZ`**: `sample_size_convergence` fails because `sampler.max_size_for_convergence` is null in `config/experiments.yaml` (the author's ceiling, D-F6-004), and F7 to F8 have no real-country inputs yet. They run, with test values of the configuration and a synthetic power curve, through `pytest tests/synthetic` (the end-to-end tests `tests/synthetic/test_zzz_end_to_end.py` and `test_zzz2_end_to_end.py`, which is what the CI job does).

## Tests

- `pytest -n 3` runs the whole suite in three processes: about 24 minutes against 46 in one (2,541 tests; the second of two runs on the development machine passed all of them). Three workers hold up to 2.7 GB, so on a machine with 6 GB close the browser and the editor first, or use `-n 2`.
- `pytest tests/unit -m "not slow" -n 3` is what the CI unit job runs on every push (Python 3.11 and 3.12, with the constraints above). The synthetic worlds and the frozen V-01 regression have their own workflows.
- The memory caps of the pipeline (`config/memory_budget.json`, `phase_caps`) bind `python main.py`, not the tests; `GEOFREA_MEMORY_CAPS=0` switches them off for a run.

## Where things are

- How the pipeline works, what each phase reads, writes and costs, and how to run it: [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md) (living document).
- Method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), the only place the method is defined; overview in [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).
- Status per phase and country: [`docs/PROGRESS.json`](docs/PROGRESS.json); open items in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md); limits in [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md); decisions per phase in `docs/phases/`.
- Conventions: [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) and [`CLAUDE.md`](CLAUDE.md).
- Data and outputs live outside the repository, in `GeoFREA_data/` (`raw`, `interim`, `outputs`, `logs`, `archive`); audit and performance records are in `docs/_audit/` (index in its README).
- The legacy port documents of September 2026 are kept in [`docs/_archive/2026-09/`](docs/_archive/2026-09/).
