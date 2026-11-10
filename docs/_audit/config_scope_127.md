# Configuration scope of F2a and F3, the recorder of reads and the rebaseline by proof (COMMAND 127, item 5)

Written for: the author. Branch `config-scope-fix`, from `main` at `3e7e224`. The real manifests were read (dry run) and not written; no phase was run. Defect 1 of `docs/_audit/generality_audit.md`.

## 5a. What F2a and F3 read and the scope did not name

`PHASE_CONFIG_SCOPE` (`core/config_fingerprint.py`) now names:

| phase | file | selector | read in |
|---|---|---|---|
| `grid_alignment` | parameters.json | `countries.{iso}.connection.poi_voltage_threshold_kv` | `main.py::_build_grid_alignment_inputs` |
| `grid_alignment` | parameters.json | `countries.{iso}.connection.poi_sensitivity_threshold_kv` | idem |
| `land_eligibility` | parameters.json | `countries.{iso}.connection.reference_project_mw` | `main.py::_project_area_km2` |
| `land_eligibility` | parameters.json | `countries.{iso}.technologies.*.power_density_mw_per_km2` | idem |
| `land_eligibility` | settings.yaml | `geospatial.pvcz_csv` | `main.py::_zone_source` |
| `land_eligibility` | settings.yaml | `geospatial.pvcz_max_distance_km` | idem |

The selectors take the whole parameter entry (value, scenario values, note, source, verification), as `technical_potential` already takes `countries.{iso}`. F2a already named `settings.geospatial`.

## 5b. The test that records the reads

`tests/synthetic/config_trace.py` records, while the pipeline runs on ZZZ, every read of a field of a validated config model, every dump of one, and every read of the raw `experiments.yaml` (a `yaml.safe_load` outside the config loader), each with the phase running (`PhaseSpec.run` is wrapped) and its dotted path in the file. `test_every_key_a_phase_reads_is_in_its_scope` (in `tests/synthetic/test_zzz_end_to_end.py`, on the ZZZ run that module already makes) requires every leaf read to lie under a selector of the scope of its phase. `tests/unit/test_config_trace.py` tests the recorder itself (13 tests).

On the code before 5a, the first run of the recorder named the keys of the table above for F2a and F3. After 5a it names no gap in F2a or F3, and two others (**OQ-085**, opened): `technical_potential` reads `audit.country_overrides`, and `potential_maps` reads `parameters.countries.ZZZ.technologies.*` and `technologies.yaml` (26 leaves), and neither names them. They are listed in the test as known gaps, so it still stops every new one, and it fails when one is closed without removing the entry. They were not added to the scopes: the command asked for F2a and F3, and each addition changes the fingerprint of the phase in three countries.

Blind spots, stated in the module: `countries.yaml` is read by the loader as a plain dict and is not traced; a model copied with `model_copy` loses its path (it is reported as unattributed; none was); a model read by iteration is not seen; the reads that a schema validator makes of its own model are not the phase reading it and are skipped (the first run counted `hypothesis_rules` for seven phases for that reason).

## 5c. The rebaseline by proof

`core/config_rebaseline.py` (not imported by any phase or by the orchestrator: no fingerprint of code changes) and `scripts/rebaseline_config_fingerprint.py`. For a phase and a country, the fingerprint of the manifest is rewritten only if:

- **A**: for each execution date of the entry (`started_at`, and `cold_started_at` when it differs), the commit in force then (the last commit of `main` before it) gives, with the scope the phase had before 5a, the fingerprint the manifest recorded;
- **B**: the value of each key 5a added is the same in each of those commits and in the current files;
- **C**: the current files give, with the old scope, the recorded fingerprint (no key the phase already declared has changed since).

Anything else is a refusal that names the cause, and nothing is written; the script writes a country's manifest only when every phase asked for is proved, in one atomic replace, and is a dry run unless `--apply` is given. The manifest (schema **2.9**) gets `config_rebaselines` in each phase entry: the change id, the date, the previous and new fingerprints, the date and commit of each execution, each key with its value in each commit and now, the fingerprint of the old scope on the current files, whether the manifest said its run was dirty, and the SHA-256 of all that. The version bump follows 2.5 to 2.8: older manifests are read as before (the new list defaults to empty), and the three tests that pinned "2.8" now pin "2.9". `phase_config_payload` and `config_fingerprint` take an optional `scope`, used to compute the old fingerprint.

`tests/unit/test_config_rebaseline.py` (16 tests) builds a scratch git repository with a copy of `config/` in commits with chosen dates and its own manifests: the proof holds with nothing changed and with an unrelated change after the run; it is refused when a key 5a added changed after the run (F3, which does not read it, is still proved), when it differed on the cold run, when a key the phase already declared changed, when the commit of the run does not reproduce the recorded fingerprint, when a date has no commit, with an entry that is not a success or has no fingerprint, and with a dirty manifest under `--refuse-dirty`; `apply` writes the two fields and nothing else, is idempotent, and refuses a manifest that changed after the proof; the script is a dry run by default and writes nothing when any phase is refused.

**The three real manifests say `dirty: true`.** With a dirty working tree at the time of the run, an uncommitted edit to a key 5a added cannot be told from a clean one (A only sees the keys the phase already declared), so the commit is the reference, as the command asked, and the flag goes into the proof; `--refuse-dirty` refuses on it and would refuse all six.

## 5d. Which entries change fingerprint

Computed on the three real manifests (36 phase entries, 12 per country): **exactly 6 change** and 30 do not.

| country | `grid_alignment` | `land_eligibility` |
|---|---|---|
| PRT | 541db5cb39a4 -> 6c31df31a8e0 | f85925b15239 -> b2dc54e7e12e |
| IND | 541db5cb39a4 -> 5505e7740fb8 | f85925b15239 -> cde868d2d614 |
| BRA | 541db5cb39a4 -> f78b188a5f00 | f85925b15239 -> 74bf1d4fa773 |

Without the rebaseline, a run would execute F2a and F3 again in each country, and with them every phase that requires them. The dry run of the script on the three manifests (`--countries PRT IND BRA`, nothing written) **proves all six**: A, B and C hold at the dates of `started_at` (2026-11-09) and, for F3 of PRT, at `cold_started_at` (2026-11-06; commits `26ccb4303f` and `e2a103d6a1`). Fingerprints of code and caches: 19 of 19 phases and 13 of 13 caches unchanged (the changes are in `core/orchestrator.py` and `core/config_fingerprint.py`, infrastructure modules outside the closures, and in a module only the script imports).
