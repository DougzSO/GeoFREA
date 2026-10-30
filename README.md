# GeoFREA

GeoFREA is a spatially explicit, open-data framework that estimates the technical potential and site-level LCOE of utility-scale solar PV and onshore wind on a 0.05 degree cell grid in Brazil, Portugal and India, and ranks cells by how well their economic ranking holds across climate futures and techno-economic uncertainty (PhD thesis, Douglas).

## Phases

F1 data acquisition, F1b data quality audit, F2a grid alignment, F2b siting layers, F3 land eligibility, F4 climate forcing, F5 technical potential, F6 LCOE modeling, F7 robustness analysis, F7b external validation, F8 results synthesis. Each phase is a package under `src/geofrea/` and writes its artifacts to the per-country manifest.

## Run

1. Copy `.env.example` to `.env` and set the data directories.
2. `pip install -e ".[dev]"`
3. `python main.py PRT` (one country, every phase in `config/settings.yaml`), or `python main.py BRA --phases technical_potential`; upstream phases that are stale are added automatically. `python main.py --help` lists the options.
4. `pytest` runs the suite (about 30 minutes; close other applications).

## Where things are

- How the pipeline works, what each phase reads, writes and costs, and how to run it: [`docs/PIPELINE_GUIDE.md`](docs/PIPELINE_GUIDE.md) (living document).
- Method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), the only place the method is defined; overview in [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).
- Status per phase and country: [`docs/PROGRESS.json`](docs/PROGRESS.json); open items in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md); limits in [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md); decisions per phase in `docs/phases/`.
- Conventions: [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) and [`CLAUDE.md`](CLAUDE.md).
- Data and outputs live outside the repository, in `GeoFREA_data/` (`raw`, `interim`, `outputs`, `logs`, `archive`); audit and performance records are in `docs/_audit/` (index in its README).
- The legacy port documents of September 2026 are kept in [`docs/_archive/2026-09/`](docs/_archive/2026-09/).
