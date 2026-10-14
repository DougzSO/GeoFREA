# docs/thesis

LaTeX text of the thesis, generated from the method. `docs/METHODOLOGY.md` stays the single source of truth for the method; a text here
states a result definition or a decision rule in the form the thesis uses and must agree with the METHODOLOGY version it cites.

- `hypotheses/`: one file per hypothesis section (`H1_climate_rank_robustness.tex` to `H5_climate_threat_to_targets.tex`).
- `methods/`: method sections that are not a hypothesis (`synthesis_and_scenario_discovery.tex`: the cross-country synthesis of T-R8 and the PRIM scenario discovery).
- `notation.tex`: the notation common to H1 to H5, the synthesis and PRIM scenario discovery, as one table (symbol, meaning, where it is defined, name in METHODOLOGY and in the tables); it restates no definition and changes no hypothesis text (I-6 of the pre-research audit, 2026-10-14).
- Thesis figures and tables are not stored here. F8 writes them to `GEOFREA_DATA_DIR/outputs/thesis/`, named by their T-ID.

Scientific content of a `.tex` file changes only with the author's authorization.
