# DECISIONS.md: GeoFREA

Log of the architectural and methodological decisions of GeoFREA v2. Append-only: an existing entry is never edited or deleted. A decision that replaces another says in `Substitui:` which one (DEC-nnn and one sentence), and the old entry stays as written. The decisions of v1 (DEC-001 to DEC-100 of the v1 numbering) are in the tags `v1.0`, `v1.1` and `v1-final`; `docs/v1/inheritance.md` maps each one that still holds to its place in v2. The v1 numbers are not reused in the v2 numbering below: a v2 reference to a v1 decision is written "v1 DEC-nnn".

Entry template:

## [date] DEC-nnn - [module name]
Tipo: STRUCTURAL_PRESERVE | METHODOLOGY_REVISION | VERIFICATION_UPDATE
Descrição:
Justificativa (if METHODOLOGY_REVISION):
Referência (literature or discussion, if applicable):
Fase: (affected phase, optional)
Implementa: (the D-... of the phase record that applies the decision, optional)
Substitui: (DEC-nnn and one sentence, optional)

ID: `DEC-nnn`, where nnn is the position of the header in the file (the first entry header is DEC-001), written in the header of every entry.

---

## [2026-11-24] DEC-001 - GeoFREA v2 adopted
Tipo: METHODOLOGY_REVISION

Descrição: GeoFREA v2 replaces the decision machinery of v1. The question becomes the redistribution of generation of the existing and planned fleet by climate change, the supply gap it creates and the adaptive expansion that covers it (`docs/METHODOLOGY.md` v2.0.0, Sections 1 to 3).
- Modules: M1 fleet risk (GEM plants; relative change of runoff from the ISIMIP3b global hydrological models and of the solar and wind capacity factor), M2 supply gap, M3 adaptive expansion. Scope of v2.0: hydro, solar and wind fleet; solar and wind expansion; thermal plants in v2.1.
- Climate: five ISIMIP3b models (GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL) x SSP1-2.6, SSP3-7.0, SSP5-8.5, bias adjusted; main window 2041-2070, reference 1995-2014. The 2071-2100 window is not in v2.0 (OQ-118). `tas` is acquired, not approximated by `tasmax` and `tasmin`. The four hydrological models (cwatm, h08, miroc-integ-land, watergap2-2e) are an ensemble: each hydrological member is (climate model, hydrological model, SSP), reported as median and range, and a sign is robust when at least 2/3 of the combinations agree.
- Robustness: sign agreement in at least 2/3 of the models, with the worst case and the median; cost uncertainty is a range of the totals, not an axis of futures (U-09).
- Leaves: the economic threshold and the satisficing ratio, PRIM scenario discovery, the 4000-draw convergence of F7, the top-k fraction, the relative max-regret as central metric, H1 to H5 of v1 and the explorer. F7 evaluates the 15 members with nominal parameters. The scale stays 0.05 degree, with 0.1 degree as a documented sensitivity.
- GEM has two separate uses: input of the fleet (M1) and external validation (F7b); no parameter is fitted to plants without a spatial train and test split (V-06).
- Guard: until the tag `prereg-v2` exists, the decision phases F7, M1, M2 and M3 refuse real data (M-F7-13); the lock `--real-run` stays.
- Records: the results of v1 stay in the tags `v1.0`, `v1.1` and `v1-final` and are summarised in `docs/v1/record.md`; `docs/v1/inheritance.md` has one row per item of v1 that carries over. The documents of the work tree describe only the current state; the history is in git.

Justificativa: the diagnosis of v1 (`docs/v1/record.md`) showed that the cost threshold and the satisficing ratio did not discriminate between cells in most country and technology pairs, that cost uncertainty shifted all cells together without changing their order, and that the 72,000-future evaluation answered a question (ranking of sites) that is not the one the thesis needs (what climate does to the generation of the fleet and where to compensate it).

Referência: author's design of 2026-11-24 (Part A of `GeoFREA_v2_desenho_e_comandos.md`); author's verdicts on the cleanup proposal (`decisoes_302_v2.md`: P1 to P6, D1 to D13). Verdicts that shape the repository: only what v2 uses or cites stays in the work tree; everything else is in the tags and, outside git, in `_arquivo_GeoFREA/`; `docs/evidence/` holds only the reports cited by the v2 documents; IDs of v1 cited in code are rewritten at COMMAND 306 (no `v1:` prefix); the configuration sections of the removed machinery leave at COMMAND 306 under proof that no phase F1 to F3 becomes stale; `explorer` and `exploratory_analysis` leave at COMMAND 306.

Fase: all
Implementa: not applicable (adopts the specification)
