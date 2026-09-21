# OPEN_QUESTIONS.md: GeoFREA

Unresolved items only. When an item is resolved, record the resolution in the relevant phase record, update `docs/METHODOLOGY.md` only if authorized, and delete the item here.

Entry fields: blocking phase, question, resolution protocol, owner, status (`open`, `research_in_progress`, `awaiting_verdict`).

| ID | Blocks | Question | Resolution protocol | Owner | Status |
|---|---|---|---|---|---|
| OQ-001 | F6 | Values and ranges for `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km` per country. | Literature and agency sources per country; transfer from other regions allowed as Tier 2 with rationale; ranges recorded per U-05. | Douglas | open |
| OQ-002 | F2b | `slope_max_deg` for solar and wind (current configuration holds conflicting wind values). | Literature review of utility-scale siting constraints; one nominal and range per technology; country differentiation only with a source. | Douglas | open |
| OQ-003 | F2b | `pop_density_max` per technology, and whether settlement buffers are needed. | Literature on exclusion criteria (Ryberg et al. 2018 and national studies). | Douglas | open |
| OQ-004 | F5 | `PD` and `LUF` nominal values and ranges per technology and country. | Empirical footprint studies and national assessments; variants per U-06. | Douglas | open |
| OQ-005 | F5 | Hub height per country, reference power curves per IEC class, class selection rule, `eta_loss` range. | Open turbine databases and literature; document curve provenance in `technologies.yaml`. | Douglas | open |
| OQ-006 | F4, F5 | Global Wind Atlas reference period and the reference height of the `capacity-factor_IEC` layers. | Official GWA documentation; inspect GeoTIFF metadata of one downloaded CF layer. CF layers are used only as a cross-check of M-F5-03. | Douglas | open |
| OQ-007 | F5, F6 | Loss functions for C2 (extreme heat on PV and inverters, extreme wind cut-out and tracker stow) and C3 (extreme precipitation and flooding on PV). | Targeted literature search; classify each by evidence tier; Tier 1-2 enters F5 or F6, Tier 3 becomes context indicator. | Douglas | open |
| OQ-008 | F7 | Satisficing threshold `tau` (LCOE) per country and technology, and `CF_min` per technology. | Anchor `tau` to recent auction or benchmark prices per country; `CF_min` from bankability literature; ranges tested in sensitivity. | Douglas | open |
| OQ-009 | F4 | Final GCM ensemble. | Execute M-F4-02; record results in `docs/phases/F4_climate_forcing.md`. | Douglas | open |
| OQ-010 | F7 | National capacity targets for the top-k sensitivity. | Official planning documents per country, horizon-matched. | Douglas | open |
| OQ-011 | F1, F2b | Transmission grid layer source per country, voltage attribute availability, minimum voltage for connection. | Inspect local grid data; document source and coverage; decide voltage filter only if attribute is consistent across countries. | Douglas | open |
| OQ-012 | F1 | India data wiring: HydroSHEDS region, GRIP4 region mapping (lookup divergence), land cover and population tiles. | Audit local database for India; move mappings to `config/countries.yaml`. | Douglas | open |
| OQ-013 | E1 | Explorer technology stack and hosting. | Decide after F7 artifacts exist; static bundle preferred. | Douglas | open |
| OQ-014 | Thesis Ch. 2 | Literature justification of min-max regret as primary metric with satisficing and PRIM, answering RQ4. | Literature review; architecture already supports both metrics. | Douglas | open |
| OQ-015 | F2b | Land-cover classes excluded per technology and forest treatment in each land-availability variant. | Map land-cover legend to exclusion literature; define central, strict, lenient sets. | Douglas | open |
| OQ-016 | F6 | Variable OPEX (currently null for solar and wind) and the weak proxy for BRA wind fixed OPEX. | IRENA and national O&M sources; if no source exists, set variable OPEX to zero and record as limitation. | Douglas | open |
| OQ-017 | F6 | CAPEX ranges at commissioning year. | Cost projection sources (IRENA, NREL ATB, IEA) bracketing the commissioning year; Tier 2 transfers documented. | Douglas | open |
| OQ-018 | F6 | Commissioning year and lifetime ranges. | Literature and national planning horizons. | Douglas | open |
| OQ-019 | F6 | Degradation rate ranges for PV and wind. | Jordan and Kurtz (2013); Staffell and Green (2014); later syntheses. | Douglas | open |
| OQ-020 | F7 | Regret reference `q_ref` (minimum or low quantile). | Test sensitivity of top-k to `q_ref` in {0, 0.01}; adopt minimum unless outliers dominate, recorded in F7 record. | Douglas | open |
| OQ-021 | F7 | Top-k percentage `p_k`. | Choose from {5, 10, 20} percent based on sample size per country (Portugal constrains); report sensitivity. | Douglas | open |
| OQ-022 | F6 | Discount rate ranges per country and technology. | IRENA benchmark and cost-of-capital studies per country. | Douglas | open |
| OQ-023 | F5 | Module power temperature coefficient `gamma` range. | Module datasheet surveys and PV performance literature. | Douglas | open |
| OQ-024 | core | `AcquiredLayer` (F1's `layer_registry` artifact) has no per-layer checksum of the source file, only `path`/`paths` — METHODOLOGY A-02's artifact registry hashes the F1 output artifact itself, but not each raw source file it references. Whether A-02 requires a source-file checksum per layer (vs. only the registered-artifact level already implemented) is undecided. | Douglas decides whether to add a `source_sha256` field to `AcquiredLayer`, and if so whether it is computed at fetch time or on demand; record the decision in `docs/phases/core.md` before implementing. | Douglas | open |
