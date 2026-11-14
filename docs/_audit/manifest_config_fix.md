# Manifest resume and configuration changes (branch `fix/manifest-config`, 2026-10-18)

Status: committed on `fix/manifest-config` and merged into `main` (COMMAND 51, 2026-10-18); decision D-core-041 in `docs/phases/core.md`. Section 4 was closed by `revalidation_52.md`.

## 1. Audit before the fix (read only)

### 1.1 What the manifest 2.4 fingerprinted

Nothing of the configuration. `Orchestrator.run` resumed a phase when `manifest.phases[name].status == "success"`, the recorded artifact keys
equal `produces`, the schema versions equal `produces_schema_versions` and the artifact hashes on disk are the recorded ones
(`core/orchestrator.py`, `_check_resume_is_not_stale`, `_verify_artifact_integrity`). The entry (`PhaseManifestEntry`) held the status,
the time stamps, `consumed_run_ids` (lineage of upstream artifacts), `methodology_version`, `wall_s` and `cpu_s`: no hash of
`experiments.yaml`, `parameters.json`, `audit.yaml`, `technologies.yaml`, `settings.yaml` or `countries.yaml`, and no key of them.
The only config value the manifest kept was the sampler seed (`record_seed`). The `run_id` is a hash of settings and parameters but it
is not compared on resume (and `experiments.yaml`, `audit.yaml`, `technologies.yaml` are not in it). Real manifest (BRA, F3): the entry has
exactly the fields `consumed_run_ids, cpu_s, error, finished_at, invalidated_by, invalidated_in_run, methodology_version, output, phase,
started_at, status, wall_s`.

So the only ways to see a change of configuration were to name the phase in `--rerun`, or a change in the content of an upstream artifact.

### 1.2 The case of COMMAND 49, reproduced before the fix

`D:/tmp_diag/repro_49.py` (outside the repository): a copy of the real `experiments.yaml`, a phase `land_eligibility` whose body reads the
real `land_availability` block with the real loader and writes the limit into its artifact, the real `Orchestrator`. Run 1 with
`elevation_max_m` 3000; then the copy is edited to 2500 and the orchestrator is run again with the same `target_phases` and an empty
`rerun_phases`:

```
RUN 1: status success elevation_max_m 3000.0 body calls [3000.0]
Phase 'land_eligibility' [PRT]: resuming - manifest status 'success' from a prior run ..., rerun_phases does not name it. Skipping re-execution.
RUN 2 (elevation_max_m 3000 -> 2500): status success elevation_max_m in result 3000.0 body calls [3000.0]
RESUMED WITH THE OLD VALUE
```

This is what happened in the real round: F3 ran with `success` and the old result until `--rerun land_eligibility` was given.

### 1.3 What each phase reads

Taken from the code of `main._build_phase_specs` and of the modules the phases call (loaders `load_experiments`, `load_land_availability`,
`load_ensemble`, `load_audit_config`, `load_technologies`, `load_countries`, the settings arguments closed over by the specs, the power-curve
directory and `published_potential.yaml`). The unit of selection is a section (top-level key or dotted path); where a phase reads a part of
a section, the whole section is in the scope (over-approximation: a needless rerun is possible, a stale result is not).

| Phase | Config read (file: sections) |
|---|---|
| F1 data_acquisition | countries.yaml: the country's entry |
| F1b data_quality_audit | audit.yaml: layers, resolution_tolerance, country_overrides; experiments.yaml: `land_availability.technologies.*.slope_max_deg` (strictest slope limit, `audit.py` line 367) |
| F2a grid_alignment | settings.yaml: geospatial (resolutions, distance cap) |
| (external_inputs) | experiments.yaml: gcm_ensemble |
| F2b siting_layers | none |
| F3 land_eligibility | experiments.yaml: land_availability |
| F4 climate_forcing | experiments.yaml: gcm_ensemble |
| F4 hazard_context | experiments.yaml: gcm_ensemble, hazard_indicators |
| F4 climate_maps | settings.yaml: figures |
| F5 technical_potential | technologies.yaml (all); parameters.json: the country; experiments.yaml: gcm_ensemble, land_availability; audit.yaml: derived_ranges; settings.yaml: run.technologies; every file of `config/turbines/` |
| F6 lcoe_modeling | technologies.yaml; parameters.json: the country; experiments.yaml: sampler, uncertain_parameters, land_availability, windows; settings.yaml: run.technologies |
| F6 sample_size_convergence | technologies.yaml; parameters.json: the country; experiments.yaml: sampler, uncertain_parameters, thresholds, windows; settings.yaml: run.technologies |
| F7 robustness_analysis | technologies.yaml; parameters.json: the country; experiments.yaml: sampler, uncertain_parameters, land_availability, windows, thresholds, hypothesis_rules, national_targets, hazard_thresholds, prim; settings.yaml: run.technologies |
| F7b external_validation | technologies.yaml; experiments.yaml: external_validation, land_availability; published_potential.yaml; settings.yaml: run.technologies |
| lcoe_maps | experiments.yaml: windows, gcm_ensemble; settings.yaml: figures, run.technologies |
| robustness_maps | experiments.yaml: windows; settings.yaml: figures, run.technologies |
| potential_maps | settings.yaml: figures, run.technologies |
| F8 results_synthesis | technologies.yaml; parameters.json (all countries); experiments.yaml: hypothesis_rules, land_availability, sampler, synthesis, thesis_figures, uncertain_parameters, windows; settings.yaml: run.technologies |
| overview | settings.yaml: figures |

`settings.memory.max_batch_gb` is not in any scope: it sets the size of the batches, not the result.

## 2. The fix

`fix/manifest-config`; the diff is in section 5.

- **`src/geofrea/core/config_fingerprint.py` (new).** `PHASE_CONFIG_SCOPE` is the table above. `config_fingerprint(phase, country, source)` is the SHA-256 of the
  canonical JSON of the selected values (files are parsed first, so comments, formatting and key order do not count; an absent section
  is recorded as `<absent>`; power curves enter by file hash). `DiskConfigSource` reads the files the pipeline reads (the paths of `main.py`, so a test
  that patches them is honoured); any other store (a git revision) can implement `ConfigSource`.
- **`PhaseSpec.config_fingerprint`** (optional) and **manifest schema 2.5** (`PhaseManifestEntry.config_fingerprint`, optional, written when
  a phase succeeds; 2.4 manifests are readable without migration).
- **Resume rule** (`Orchestrator.run`): a `success` entry whose recorded fingerprint differs from the spec's is not resumed; the phase runs and the log says
  `the configuration it reads changed since it ran (fingerprint a -> b)`. The downstream phases follow the existing rules: the ones whose own scope
  changed run again, the ones that consumed an artifact whose content changed become `stale_upstream`. An artifact that comes out identical does not invalidate its consumers (content, not
  time).
- **Entries without a fingerprint (manifests written before 2.5)**: resumed once, with a warning, and the current fingerprint is recorded (see 4: this
  is the only way not to redo every phase, and its risk).
- `--revalidate` refuses a `stale_upstream` phase whose configuration changed.
- `main._build_phase_specs(..., country_code=...)` fills the fingerprints (`_run_geofrea` passes the country; `thesis_phase_graph` does not need them).

## 3. Tests

`tests/unit/test_config_fingerprint.py` (17 tests) and the schema version in `tests/unit/test_orchestrator.py`:

| Test | What it shows |
|---|---|
| every registered phase has a scope, and only those | a new phase cannot be added without declaring what it reads |
| every section a scope names exists in the real config (PRT, BRA, IND) | a renamed section cannot silently leave a phase reading nothing |
| specs carry fingerprints only with a country | the graph alone (thesis T-M1) needs none |
| a key F3 reads (`elevation_max_m`) changes F3, F5, F6, F7, F7b and F8, and none of F1, F2a, F2b, F4, the maps, overview | the F3-F8 requirement |
| a key F3 does not read (`prim.bootstrap_replicates`) changes only F7 | F3 stays valid |
| `figures`, a power-curve file, the parameters of another country | each reaches only its readers |
| a comment or key order | no change |
| chain F3..F8 in the real `Orchestrator`: unchanged config resumes all; `prim` change reruns F7 only (its output is identical so F8 stays); `elevation_max_m` change reruns F3..F8 and the artifact has the new value | the case of COMMAND 49 corrected |
| a changed fingerprint is recorded and the next run resumes | no loop |
| upstream rerun with new content marks a consumer with an unchanged fingerprint `stale_upstream` | the content rule is kept |
| entry without fingerprint: resumed once, adopts the current one, then a change is seen | legacy manifests |
| spec without fingerprint is never checked | opt-out |
| `--revalidate` refuses after a config change | no bypass |
| a slope limit reaches F1b and F3; the wildcard path selects solar and wind | scope of F1b |

Case of COMMAND 49 after the fix (`D:/tmp_diag/repro_49_after.py`, same script with the fingerprint):

```
Phase 'land_eligibility' [PRT]: executing - the configuration it reads changed since it ran (fingerprint 618bc511e15e -> 5b40057385bf).
RUN 2 (elevation_max_m 3000 -> 2500): status success elevation_max_m in result 2500.0 body calls [3000.0, 2500.0]
REEXECUTED WITH THE NEW VALUE
```

Full suite: **1410 passed** in 731 s (0:12:11), `ruff check` and `ruff format` clean on the files touched. The first run stopped at `test_external_validation.py::test_the_shipped_published_file_is_empty_and_only_f7b_reads_it`, which forbids the string `published_potential` outside `external_validation/`; the fingerprint module only hashes that file and reads no value, so the test now also allows `core/config_fingerprint.py` (one line and a comment in the diff). 1393 tests before, 17 new.

## 4. Effect on the current manifests of PRT, IND and BRA

The manifests on disk have no fingerprint. With the rule of section 2 (resume once and adopt), **nothing is re-executed**: the next run of each
country resumes every `success` phase, logs one warning per phase and writes the fingerprints. Whether that is right depends on whether the
configuration changed after each phase ran. To answer it, `D:/tmp_diag/manifest_effect.py` (read only, nothing written) takes, for each `success`
entry, the config files of the last commit made before its `finished_at`, computes the fingerprint of the phase on them and compares it with the one of the files now:

| Phase | PRT | IND | BRA | Reason |
|---|---|---|---|---|
| data_acquisition | **redo** | **redo** | **redo** | `countries.yaml`, the country's entry: `gadm_dir` was `Portugal`/`India`/`Brazil`, now the ISO code; `land_cover_dir` and `elevation_dir` removed (commit 4317d63, data directory self-contained, 2026-10-14 23:02 -03, after the F1 runs of 2026-10-15 00:55-01:19 UTC) |
| external_inputs | **redo** | **redo** | **redo** | `gcm_ensemble` gained `dt_isolated_native_cell_threshold_k` and changed `gcms` after the run of 2026-10-07 (the phase only checks that files exist; the rerun is a registry and existence check) |
| data_quality_audit, grid_alignment, climate_forcing, hazard_context, climate_maps, siting_layers | valid | valid | valid | configuration read is the same |
| land_eligibility, technical_potential, potential_maps | valid | valid | valid | ran after the last commit that touched what they read (round of 2026-10-16/17) |
| overview | `stale_upstream` | `stale_upstream` | `stale_upstream` | already invalid by lineage, independent of this fix |

Limits of this analysis: the commit is a proxy for the configuration the run used. A run made on uncommitted config files (the manifest records
`dirty`) cannot be seen; and the comparison is by section, so a changed section that the phase reads only in part (as `gcm_ensemble` for
`external_inputs`) counts as a change.

Decision for Douglas: (a) accept the adoption (the analysis says only F1 and `external_inputs` are in doubt, and their outputs are file lists and
a registry, not numbers that feed the potential); or (b) run `python main.py <ISO3> --rerun data_acquisition,external_inputs` once per country,
which re-resolves the layers (and if the registry content changes, F1b, F2a and what consumes them become `stale_upstream` by the content rule). I did not run either: this change does not touch `D:/Douglas/DOUTORADO/database/raw` nor any output.

## 5. Diff

Tracked files (new files: `src/geofrea/core/config_fingerprint.py`, 209 lines, and `tests/unit/test_config_fingerprint.py`, listed above):

```diff
diff --git a/main.py b/main.py
index fdfb0ec..33a7578 100644
--- a/main.py
+++ b/main.py
@@ -64,6 +64,7 @@ import logging
 import re
 import sys
 from collections import Counter
+from dataclasses import replace
 from datetime import datetime
 from pathlib import Path
 
@@ -87,6 +88,7 @@ from geofrea.config_models.land_availability import (
     load_land_availability,
 )
 from geofrea.core.artifact_json import dump_artifact
+from geofrea.core.config_fingerprint import DiskConfigSource, config_fingerprint
 from geofrea.core.config_loader import (
     load_audit_config,
     load_countries,
@@ -179,6 +181,7 @@ SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
 AUDIT_YAML = REPO_ROOT / "config" / "audit.yaml"
 EXPERIMENTS_YAML = REPO_ROOT / "config" / "experiments.yaml"
 TECHNOLOGIES_YAML = REPO_ROOT / "config" / "technologies.yaml"
+PUBLISHED_POTENTIAL_YAML = REPO_ROOT / "config" / "published_potential.yaml"
 POWER_CURVES_DIR = REPO_ROOT / "config" / "turbines"  # reference turbine curves (M-F5-03)
 METHODOLOGY_MD = REPO_ROOT / "docs" / "METHODOLOGY.md"
 
@@ -408,6 +411,7 @@ def _build_phase_specs(
     production: bool = False,
     figures: str = "all",
     max_batch_gb: float | None = None,
+    country_code: str | None = None,
 ) -> list[PhaseSpec]:
     """Registered phases, with their requires/produces artifact contracts.
 
@@ -440,6 +444,9 @@ def _build_phase_specs(
         figures: settings.yaml's `figures` (A-08), closed over by potential_maps.
         max_batch_gb: settings.yaml's `memory.max_batch_gb` (A-10), closed over by lcoe_modeling; the phase raises
             if it is absent (no silent default).
+        country_code: the country of the run; with it every spec carries the fingerprint of the configuration its phase reads
+            (`core.config_fingerprint`), so that the manifest resumes a phase only while that configuration is unchanged.
+            Without it the specs carry none (the graph alone is wanted).
 
     Returns:
         The registered PhaseSpecs.
@@ -1075,6 +1082,23 @@ def _build_phase_specs(
             summarize=lambda out: f"{len(out.figures)} figures and 1 table",
         ),
     ]
+    if country_code is not None:
+        source = DiskConfigSource(
+            {
+                "experiments": EXPERIMENTS_YAML,
+                "parameters": PARAMETERS_JSON,
+                "audit": AUDIT_YAML,
+                "technologies": TECHNOLOGIES_YAML,
+                "settings": SETTINGS_YAML,
+                "countries": COUNTRIES_YAML,
+                "published_potential": PUBLISHED_POTENTIAL_YAML,
+            },
+            POWER_CURVES_DIR,
+        )
+        specs = [
+            replace(spec, config_fingerprint=config_fingerprint(spec.name, country_code, source))
+            for spec in specs
+        ]
     graph.update(phase_graph(specs))
     return specs
 
@@ -1228,6 +1252,7 @@ def _run_geofrea(
             production,
             figures,
             max_batch_gb,
+            country_code,
         )
     )
     ok = all(results[name].status == "success" for name in target_phases)
diff --git a/src/geofrea/core/orchestrator.py b/src/geofrea/core/orchestrator.py
index b03ab03..16da867 100644
--- a/src/geofrea/core/orchestrator.py
+++ b/src/geofrea/core/orchestrator.py
@@ -48,7 +48,10 @@ PhaseStatus = Literal["success", "failed", "skipped_upstream_failed", "stale_ups
 
 _HASH_CHUNK_SIZE = 8 * 1024 * 1024
 _LARGE_FILE_LOG_THRESHOLD_BYTES = 500 * 1024 * 1024
-_MANIFEST_SCHEMA_VERSION = "2.4"
+_MANIFEST_SCHEMA_VERSION = "2.5"
+# 2.5 (METHODOLOGY 15.0.1, A-02): every successful PhaseManifestEntry records `config_fingerprint`, the hash of the configuration the phase
+# read (`core.config_fingerprint`); a phase is resumed only while its current fingerprint equals the recorded one (None for entries
+# written before 2.5: resumed once, with a warning, and the current fingerprint is recorded).
 # 2.4 (METHODOLOGY 14.0.0, A-02): every PhaseManifestEntry records, besides its time stamps, the wall-clock time and the CPU time of the process
 # for the phase (`wall_s`, `cpu_s`, None for entries written before 2.4), so that a phase whose wall time is far above its CPU time is visible.
 # 2.3 (METHODOLOGY 7.0.0, A-02): every PhaseManifestEntry records the METHODOLOGY version it ran under
@@ -59,7 +62,9 @@ _MANIFEST_SCHEMA_VERSION = "2.4"
 # on-disk tag to "2.3" in memory before validating (RunManifest's
 # schema_version is a Literal["2.3"]) rather than running a migration
 # step. Versions before 2.1 still raise LegacyManifestError.
-_READABLE_MANIFEST_SCHEMA_VERSIONS = frozenset({"2.1", "2.2", "2.3", _MANIFEST_SCHEMA_VERSION})
+_READABLE_MANIFEST_SCHEMA_VERSIONS = frozenset(
+    {"2.1", "2.2", "2.3", "2.4", _MANIFEST_SCHEMA_VERSION}
+)
 
 
 def _now_iso() -> str:
@@ -265,6 +270,11 @@ class PhaseManifestEntry(BaseModel):
         methodology_version: The METHODOLOGY version the phase ran (or
             failed, or was skipped) under (A-02). None only for entries
             written before manifest schema 2.3.
+        config_fingerprint: For a "success" entry, the fingerprint of the
+            configuration the phase read (`PhaseSpec.config_fingerprint` at
+            the time it ran). A later run resumes the phase only if the
+            current fingerprint is equal. None for entries written before
+            manifest schema 2.5 and for phases whose spec declares none.
     """
 
     model_config = ConfigDict(extra="forbid")
@@ -281,6 +291,7 @@ class PhaseManifestEntry(BaseModel):
     methodology_version: str | None = None
     wall_s: float | None = None
     cpu_s: float | None = None
+    config_fingerprint: str | None = None
 
 
 class ArtifactEntry(BaseModel):
@@ -327,7 +338,7 @@ class RunManifest(BaseModel):
 
     model_config = ConfigDict(extra="forbid")
 
-    schema_version: Literal["2.4"] = _MANIFEST_SCHEMA_VERSION
+    schema_version: Literal["2.5"] = _MANIFEST_SCHEMA_VERSION
     run_id: str
     dirty: bool
     country_code: str
@@ -418,6 +429,12 @@ class PhaseSpec:
             F1b's audited/not_audited counts, F2a's raster dimensions
             and grid origin. A phase with no `summarize` logs completion
             with elapsed time and artifacts only, no phase-specific line.
+        config_fingerprint: Hash of the configuration the phase reads
+            (`core.config_fingerprint.config_fingerprint`). Recorded in the
+            manifest when the phase succeeds; a phase whose recorded
+            fingerprint differs from this one is executed again instead
+            of resumed. None: the phase is not checked against the
+            configuration (a spec built without a country).
     """
 
     name: str
@@ -427,6 +444,7 @@ class PhaseSpec:
     produces: frozenset[str] = frozenset()
     produces_schema_versions: Mapping[str, str] = field(default_factory=dict)
     summarize: Callable[[BaseModel], str] | None = None
+    config_fingerprint: str | None = None
 
 
 def _validate_and_order(phase_specs: Sequence[PhaseSpec]) -> list[PhaseSpec]:
@@ -627,6 +645,15 @@ class Orchestrator:
             raise ValueError(
                 f"cannot revalidate {spec.name!r}: its manifest entry is {entry.status if entry else 'absent'}, not stale_upstream"
             )
+        if (
+            entry.config_fingerprint is not None
+            and spec.config_fingerprint is not None
+            and entry.config_fingerprint != spec.config_fingerprint
+        ):
+            raise ValueError(
+                f"cannot revalidate {spec.name!r}: the configuration it reads changed since it ran "
+                f"(recorded fingerprint {entry.config_fingerprint[:12]}, now {spec.config_fingerprint[:12]}); rerun it"
+            )
         for key in spec.requires:
             if key not in self.manifest.artifacts:
                 raise UndeclaredArtifactMissingError(
@@ -913,11 +940,36 @@ class Orchestrator:
 
             must_force = spec.name in rerun_set
             existing = self.manifest.phases.get(spec.name)
-            if not must_force and existing is not None and existing.status == "success":
+            config_changed = (
+                existing is not None
+                and existing.status == "success"
+                and existing.config_fingerprint is not None
+                and spec.config_fingerprint is not None
+                and existing.config_fingerprint != spec.config_fingerprint
+            )
+            if (
+                not must_force
+                and not config_changed
+                and existing is not None
+                and existing.status == "success"
+            ):
                 self._check_resume_is_not_stale(spec)
                 for key in spec.produces:
                     self._verify_artifact_integrity(key)
                 self._warn_on_lineage_drift(spec, existing)
+                if existing.config_fingerprint is None and spec.config_fingerprint is not None:
+                    logger.warning(
+                        "Phase '%s' [%s]: the manifest entry predates the configuration fingerprint (schema 2.5); resuming it and "
+                        "recording the current fingerprint %s. A change of configuration made after that run is not detected; "
+                        "name the phase in rerun_phases if it is in doubt.",
+                        spec.name,
+                        self.country_code,
+                        spec.config_fingerprint[:12],
+                    )
+                    existing = existing.model_copy(
+                        update={"config_fingerprint": spec.config_fingerprint}
+                    )
+                    self.manifest.phases[spec.name] = existing
                 try:
                     output = (
                         spec.output_model.model_validate(existing.output)
@@ -950,6 +1002,8 @@ class Orchestrator:
             start_reason = (
                 "named in rerun_phases (forced)"
                 if must_force
+                else f"the configuration it reads changed since it ran (fingerprint {existing.config_fingerprint[:12]} -> {spec.config_fingerprint[:12]})"
+                if config_changed
                 else f"manifest status {existing.status!r}, does not resume"
                 if existing is not None
                 else "no manifest entry yet"
@@ -1111,6 +1165,7 @@ class Orchestrator:
                 methodology_version=self.methodology_version,
                 wall_s=result.wall_s,
                 cpu_s=result.cpu_s,
+                config_fingerprint=spec.config_fingerprint,
             )
             # A re-executed phase replaces its whole artifact set: keys it registered in an earlier run but no
             # longer produces (an output removed from its `produces`) are dropped, or they would stay in the
diff --git a/tests/unit/test_external_validation.py b/tests/unit/test_external_validation.py
index 41beae1..64c4704 100644
--- a/tests/unit/test_external_validation.py
+++ b/tests/unit/test_external_validation.py
@@ -239,7 +239,10 @@ def test_the_shipped_published_file_is_empty_and_only_f7b_reads_it():
         for p in SRC.rglob("*.py")
         if "published_potential" in p.read_text(encoding="utf-8")
     ]
-    assert readers and all(r.startswith("external_validation/") for r in readers)
+    # core/config_fingerprint.py only hashes the file (the manifest resumes F7b while it is unchanged); it reads no value
+    assert readers and all(
+        r.startswith("external_validation/") or r == "core/config_fingerprint.py" for r in readers
+    )
 
 
 def _entry(**changes) -> PublishedEntry:
diff --git a/tests/unit/test_orchestrator.py b/tests/unit/test_orchestrator.py
index 4e09f26..c5ae857 100644
--- a/tests/unit/test_orchestrator.py
+++ b/tests/unit/test_orchestrator.py
@@ -639,7 +639,7 @@ def test_manifest_written_on_success(tmp_path):
     entry = orchestrator.manifest.phases["phase_a"]
     assert entry.status == "success"
     assert entry.output == {"value": 7}
-    assert orchestrator.manifest.schema_version == "2.4"
+    assert orchestrator.manifest.schema_version == "2.5"
 
 
 @pytest.mark.unit
@@ -653,7 +653,7 @@ def test_manifest_records_methodology_version(tmp_path):
     orchestrator.run([ok, bad])
 
     on_disk = json.loads(orchestrator.manifest_path.read_text(encoding="utf-8"))
-    assert on_disk["schema_version"] == "2.4"
+    assert on_disk["schema_version"] == "2.5"
     assert {n: e["methodology_version"] for n, e in on_disk["phases"].items()} == {
         "phase_ok": "test-1.0.0",
         "phase_bad": "test-1.0.0",
@@ -960,6 +960,6 @@ def test_a_manifest_of_schema_2_3_is_readable_and_its_phases_have_no_times(tmp_p
 
     reloaded = _orchestrator(tmp_path, ["phase_a"])
 
-    assert reloaded.manifest.schema_version == "2.4"
+    assert reloaded.manifest.schema_version == "2.5"
     assert reloaded.manifest.phases["phase_a"].wall_s is None
     assert reloaded.manifest.phases["phase_a"].cpu_s is None
```
