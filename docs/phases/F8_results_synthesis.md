# F8 results_synthesis

Methodology items: M-F8-01, M-F8-02, Section 10

## Contract

Requires: persisted artifacts of F4 (`members`), F5 (`potential_aggregates_<tech>`), F6 (`supply_curve_<tech>`), F7 (`robustness_`, `hypothesis_`, `h1_summary_`, `hazard_exposure_` and `potential_below_tau_<tech>__<window>`) and F7b (the four validation tables), all read through the manifest of the country (`inputs.py:ArtifactReader`), and the configuration files for T-M2 and T-M3. Produces, per country, under `outputs/thesis/` (`outputs/thesis__<scale id>/` at another scale): tables as `.csv` and `.tex`, figures as `.png` and `.pdf`, a `<stem>.provenance.json` beside each output, and `thesis_manifest.json` (what was built and what was not, per country). The phase registers `results_synthesis.json` (the summary).

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|
| M-F8-01, D-F8-001 | F8 reads persisted artifacts through the manifest and never recomputes a scientific quantity; the hash of every artifact is checked, an unknown schema version is refused | `inputs.py:ArtifactReader` | `test_results_synthesis.py` (reader, import allow-list, no kernel or evaluator loaded by the runner), `test_zzz_end_to_end.py::test_f8_is_deterministic_and_needs_only_the_registered_artifacts`, `test_f8_refuses_an_artifact_that_changed_after_it_was_registered` | pass |
| M-F8-02, D-F8-002, D-F8-003 | One style, one script per T-ID, thesis names | `style.py`, `names.py`, `runner.py:SCRIPTS` | `test_names_follow_the_thesis_convention`, `test_f8_writes_every_implemented_output_with_its_thesis_name_and_a_provenance_file` | pass |
| T-M2, T-M3, D-F8-007 | Method tables from configuration; proxy and test values refused in a thesis build | `method_tables.py` | `test_a_thesis_build_refuses_test_values_and_a_test_build_accepts_them`, ZZZ end to end | pass |
| T-R2, T-O3 | Potential and its ranges from F5; supply curves from F6 | `potential_and_cost.py` | `test_f8_numbers_equal_the_rows_they_were_read_from` | pass |
| T-R6, T-R9, T-R10, T-R12, T-O2 | The F7 and F7b tables, a skipped table shown as empty with its reason | `robustness_tables.py` | same, and `test_f8_shows_the_empty_published_comparison_as_empty_and_says_why` | pass |
| D-F8-008 | Provenance file per output, no time, no machine path, same inputs give the same bytes | `output.py` | `test_a_table_is_written_with_a_provenance_file_that_holds_no_time_and_no_path`, the determinism test | pass |

## Active implementation decisions

Decisions D1 to D10 of `docs/_audit/2026-10_F8_design.md` that the first nine scripts use were accepted on 2026-10-13 as the report recommends.

- **D-F8-001 — Reader (report section 2, item 2).** `ArtifactReader` finds an artifact by its manifest key, checks the file against the SHA-256 registered with it, refuses a Parquet table whose schema version is not the one named, and records what it read so that each output cites it. A path is never built by hand. F8 imports no kernel, evaluator, eligibility engine or pipeline; a test scans the imports against an allow-list and a second test checks in a fresh process that loading the runner loads none of those modules.
- **D-F8-002 — D1(a): style (recommended, accepted 2026-10-13).** `style.py` extends `overview/style.py` (the map style) with fonts, sizes, one colour per SSP, one for the reference member, one per technology by its position in the run's list, and a deterministic save (no creation date or software tag).
- **D-F8-003 — D4(a): `figures` (recommended, accepted 2026-10-13).** Thesis outputs do not follow `settings.yaml` `figures`; a thesis build always writes everything. Names are `T-<id>_<what>_<ISO3>_<tech>.<ext>` (`names.py`).
- **D-F8-004 — D5(a): weighting (recommended, accepted 2026-10-13).** One weighting across the thesis: capacity. The nine outputs show F7's statistics as F7 wrote them (H2 and H3 are already capacity-weighted); F8 weights nothing itself.
- **D-F8-005 — D7(a): missing inputs (recommended, accepted 2026-10-13).** A script builds what exists and records what it did not build, with the reason, in `thesis_manifest.json` and in the phase summary; a table that a producer wrote empty (null `tau`, no hazard threshold, no published estimate) is written empty with the reason in its caption, never as zero. The run fails only when an Essential T-ID has no output at all for the country (`ThesisBuildError`).
- **D-F8-006 — D8(a): what is built before real data (recommended, accepted 2026-10-13).** Everything of section 4 of the report on the synthetic country; the real build waits for the real F7 and F7b. The first group of nine outputs is built now: T-M2, T-M3, T-R2, T-R6, T-R9, T-R10, T-R12, T-O2, T-O3. None of them depends on D2 or D6.
- **D-F8-007 — D9(a): test values (recommended, accepted 2026-10-13).** A thesis build refuses a parameter that is a proxy or a test value, and an uncertain parameter without a value or a range (`ThesisValueError`). A country whose every value is a test value (the synthetic fixture) is built as a test build, which stamps "TEST VALUES" on every caption and in every provenance file.
- **D-F8-008 — D10(a): formats (recommended, accepted 2026-10-13).** Tables as CSV and LaTeX (booktabs; the unit table of T-R9 as CSV only), figures as PNG and PDF, a provenance JSON per output (artifact keys and hashes, configuration hashes, METHODOLOGY version, scale, caption) and `thesis_manifest.json` per thesis directory.
- **D-F8-009 — Scales (V-07, T-R6).** The run at the default scale writes `outputs/thesis`; a run at another scale writes `outputs/thesis__<scale id>` so it never overwrites the thesis outputs. T-R6 reads the manifests of both scales and shows the rows of the 2071-2100 window and of the other scale beside the core ones.
- **D-F8-010 — Outputs not built here and the decision that blocks each.** T-R3 waits for D2 (the GCM-agreement convention) and T-R8 for D6 (the combination rule and the rules of OQ-050); both stay untouched until the author decides. T-M1, T-R1, T-R4, T-R5, T-R7, T-R11 and T-O1 were not in the group of outputs whose inputs are all on the synthetic country; they follow in later commands.

## Known issues

- The LaTeX tables and the PDF figures have not been compiled in an environment with a TeX engine.
- The real thesis build needs the real F5 to F7b runs, the rules of OQ-050 for H2 to H5, and the sourced parameter values (D9 refuses test and proxy values).

## History

- 2026-10-13: design report verdicts D1, D4, D5, D7, D8, D9, D10 accepted as recommended; reader, names, style, provenance, runner and the first nine scripts (T-M2, T-M3, T-R2, T-R6, T-R9, T-R10, T-R12, T-O2, T-O3); PhaseSpec `results_synthesis`.
