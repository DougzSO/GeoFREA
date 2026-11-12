# GeoFREA

GeoFREA is a spatially explicit, open-data framework that estimates the technical potential and site-level LCOE of utility-scale solar PV and onshore wind on a 0.05 degree cell grid in Brazil, Portugal and India, and ranks cells by how well their economic ranking holds across climate futures and techno-economic uncertainty (PhD thesis, Douglas).

## Phases

F1 data acquisition, F1b data quality audit, F2a grid alignment, F2b siting layers, F3 land eligibility, F4 climate forcing, F5 technical potential, F6 LCOE modeling, F7 robustness analysis, F7b external validation, F8 results synthesis. Each phase is a package under `src/geofrea/` and writes its artifacts to the per-country manifest.

## Run

1. Copy `.env.example` to `.env` and set the data directories (`GEOFREA_DATA_DIR` at least).
2. `pip install -c ci/constraints.txt -e ".[dev]"`. The constraints file pins the libraries the tests and the manifests were made with (pandas, pyarrow, numpy, geopandas, rasterio, pyproj, ruff); a plain `pip install -e ".[dev]"` takes the newest ones, and geopandas 1.2.0 breaks 52 figure tests (OQ-074).
3. `python main.py PRT` (one country, every phase in `config/settings.yaml`), or `python main.py BRA --phases technical_potential`; upstream phases that are stale are added automatically. `python main.py --help` lists the options.
4. `pytest` runs the suite; see "Tests" below for the time and the parallel run.

## The synthetic country ZZZ

ZZZ is a 30 x 20 pixel country built by hand so every result can be computed by hand (METHODOLOGY A-06). To build its inputs and run the pipeline on it from a clean clone:

1. `python scripts/generate_zzz_fixture.py`: writes the raw layers under `GEOFREA_DATA_DIR/fixtures/synthetic_zzz/` and the climate inputs under `GEOFREA_DATA_DIR/raw/`. It reads `GEOFREA_DATA_DIR` from the environment or from the repository `.env`, as `main.py` does. Use a scratch `GEOFREA_DATA_DIR`: a real data directory is not to be mixed with the fixture (`ZZZ_CLIMATE=0` skips the climate inputs).
2. `python main.py ZZZ` runs the default phases of `config/settings.yaml` (F1 to F4, the support phases, F3 and the two figure phases `climate_maps` and `overview`; about 3 minutes). `python main.py ZZZ --phases technical_potential,lcoe_modeling` adds F5 and F6.
3. **F6 onwards is not reached by `main.py ZZZ`**: `sample_size_convergence` fails because `sampler.max_size_for_convergence` is null in `config/experiments.yaml` (the author's ceiling, D-F6-004), and F7 to F8 have no real-country inputs yet. They run, with test values of the configuration and a synthetic power curve, through `pytest tests/synthetic` (the end-to-end tests `tests/synthetic/test_zzz_end_to_end.py` and `test_zzz2_end_to_end.py`, which is what the CI job does).

## Tests

- `pytest tests/unit -m "not slow"` is what the CI runs on every push (Python 3.11 and 3.12, with the constraints above).
- The complete suite (`pytest`, 2,500 tests, about 40 minutes in one process on the development machine) includes the synthetic worlds and the frozen V-01 regression. Close other applications first: it holds 1 to 2 GB.

## Where things are

- How the pipeline works, what each phase reads, writes and costs, and how to run it: [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md) (living document).
- Method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), the only place the method is defined; overview in [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).
- Status per phase and country: [`docs/PROGRESS.json`](docs/PROGRESS.json); open items in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md); limits in [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md); decisions per phase in `docs/phases/`.
- Conventions: [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) and [`CLAUDE.md`](CLAUDE.md).
- Data and outputs live outside the repository, in `GeoFREA_data/` (`raw`, `interim`, `outputs`, `logs`, `archive`); audit and performance records are in `docs/_audit/` (index in its README).
- The legacy port documents of September 2026 are kept in [`docs/_archive/2026-09/`](docs/_archive/2026-09/).
