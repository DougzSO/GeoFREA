# 2026-09 embedded-value sweep (COMMAND ADJ-6)

**Scope constraint:** this sweep covers ONLY `src/geofrea/data_acquisition/` and
`src/geofrea/data_quality_audit/`, plus `main.py`'s references to those two modules.
`src/geofrea/suitability_criteria/` is owned by Stage H (deletes/rebuilds it) and
`src/geofrea/core/` is not yet in scope — neither is swept here. A later sweep should start
at this boundary.

Method: every module-level constant, inline numeric literal, and hardcoded string/list in
the scoped directories was located (`grep` sweep + targeted reads), then run through the
four-kind filter in order. Kind-(a) implementation constants are **not** listed in the table
below (per the command's instruction) — they are grouped as one line each in the two phase
records (`docs/phases/F1_data_acquisition.md`, `docs/phases/F1b_data_quality_audit.md`,
"Embedded-value sweep" sections).

---

## 1. Classification table (kind b/c/d only — 15 rows, under the 30-row stop)

| file:line | value | kind | destination | move-now? | reason/blocker |
|---|---|---|---|---|---|
| `data_acquisition/phase.py:261` | `_HASH_BUDGET_S = 60.0` | b (operational: budget/timeout) | `settings.yaml` | no | `settings.yaml` has no hashing/network section; nothing to move into |
| `data_acquisition/phase.py:263` | `_HASH_CHUNK_BYTES = 1 << 20` (1 MiB) | b (chunk size) | `settings.yaml` | no | same — no existing key |
| `data_acquisition/fetchers/gadm.py:62` | `_HASH_CHUNK_SIZE = 8 * 1024 * 1024` (8 MiB) | b (chunk size) | `settings.yaml` | no | same — no existing key; also inconsistent with `phase.py`'s 1 MiB (not unified, noted for whoever adds the section) |
| `data_acquisition/fetchers/gadm.py:211` | `timeout=120` | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/hydrosheds.py:216` | `timeout=300` (HydroLAKES) | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/hydrosheds.py:247` | `timeout=180` (HydroRIVERS tile) | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/power_plants.py:74` | `timeout=60` | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/protected_planet.py:128` | `timeout=60` | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/wind.py:126` | `timeout=60` | b (timeout) | `settings.yaml` | no | no existing key |
| `data_acquisition/fetchers/wind.py:180` | `timeout=60` | b (timeout) | `settings.yaml` | no | no existing key |
| `data_quality_audit/raster_inspection.py:51` | `_CHUNK_ROWS = 4_000` | b (chunk size) | `settings.yaml` | no | no existing `memory`/windowed-read section |
| `data_quality_audit/raster_inspection.py:72` | `_WINDOWED_READ_MAX_BYTES = 1_500_000_000` | b (batch/memory ceiling) | `settings.yaml` (conceptually A-10's `memory.max_batch_gb`) | no | no `memory` section exists yet — F6/F7 (A-10's real owners) are `not_started` |
| `data_quality_audit/audit.py:72` | `_TECHNOLOGIES = ("solar", "wind")` | c (technology mapping) | `config/technologies.yaml` | no | `technologies.yaml` has no loader (see action 4's spec below); named explicitly per the command, not grouped |
| `data_acquisition/local_layers.py:182` | `_MIN_OVERLAP_DEG2 = 1e-6` (deg²) | d (methodological threshold, no source) | `config/parameters.json` (Tier 3, if it stays a config value at all) | no | no citable source — **OQ-033 opened**, not moved |
| — | (no additional kind-d value found with a source cited only informally — `GWA_HEIGHTS_M`/`_DEFAULT_HEIGHT_M` are already explicitly cited to M-F1-03 in their own code comments, so they are treated as kind-a implementation constants, not table rows) | — | — | — | — |

**Table is 15 rows — well under the 30-row stop, so the sweep continued to completion
without pausing for confirmation.**

---

## 2. Named items from prior sessions (action 2)

| Item | In scope? | Verdict |
|---|---|---|
| `audit.py:72` `_TECHNOLOGIES` tuple | Yes (`data_quality_audit`) | Confirmed kind c. Does **not** move now — moves only once `config/technologies.yaml` has a loader (spec below). Owned by whichever milestone writes that loader (`docs/phases/core.md`'s A-04/Section-9 rows, ADJ-5). |
| AHP random index + consistency threshold, `core/constants.py::AHP_RANDOM_INDEX` | **Out of scope this sweep** (`core/`) | Confirmed present, unchanged, not touched — matches `docs/_audit/2026-09_repo_cleanup.md` action 3 and `docs/_audit/2026-09_conformance_check.md`'s M-F2a-04 row. |
| Thresholds inside `suitability_criteria/` (e.g. `terrain_tri_weight`, percentile bounds) | **Out of scope this sweep** (owned by Stage H) | Confirmed present, unchanged, not touched — matches the H-2 retirement list in `docs/phases/F2b_siting_layers.md`. |

---

## 3. Moves performed (action 3)

**None.** Every kind-b/c/d candidate in the table above lacks either (a) an unambiguous
destination with an existing loader, or (b) a citable source (for the one kind-d item). Per
the command: "Do not move a scientific value whose source is unknown" and "operational
settings whose key already exists in settings.yaml with a loader" — no candidate satisfied
both conditions. No diff to show; no test added (there is nothing to assert the presence of
that wasn't already there).

---

## 4. `config/technologies.yaml` loader spec (action 4 — not implemented, spec only)

Based on the file's current actual shape (`config/technologies.yaml`, both `solar` and `wind`
blocks read directly):

```python
class TechnologyEntry(BaseModel):
    """One technology's registry entry (METHODOLOGY A-04)."""
    model_config = ConfigDict(extra="forbid")

    resource_layers: list[str]          # M-F2b-03 layer names, e.g. ["pvout"] or
                                         # ["weibull_a_100", "weibull_k_100", "air_density_100", ...]
    cf_model: str                       # M-F5-02/M-F5-03 model selector, e.g.
                                         # "pvout_with_temperature" | "weibull_with_air_density"
    exclusions: list[Literal[
        "protected", "water", "riparian", "slope", "land_cover", "population"
    ]]                                   # M-F2b-01 E1-E6 subset this technology applies
    cost_drivers: list[Literal["grid_connection", "site_access"]]  # M-F6-01
    uncertain_parameters: list[str]      # U-03 keys; each MUST exist in
                                         # config/parameters.json's per-country technology
                                         # block AND have a non-null range in
                                         # experiments.yaml.uncertain_parameters
    iec_class_rule: str | None = None    # OQ-005, wind-only in principle — present under
                                         # `solar:` in the file today, which looks like a
                                         # misplaced field (IEC turbine classes are a wind
                                         # concept, M-F5-03); flagged here, not corrected —
                                         # out of this sweep's "no src/config edits beyond
                                         # approved moves" scope.
    hub_heights: dict[str, float | None] = {}  # OQ-019, wind-only; ISO3 -> height_m

class TechnologiesFile(RootModel[dict[str, TechnologyEntry]]):
    """config/technologies.yaml as a whole: technology name -> TechnologyEntry."""
```

```python
def load_technologies(path: Path) -> TechnologiesFile:
    """Load and validate config/technologies.yaml (METHODOLOGY A-04)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TechnologiesFile.model_validate(raw)
```

Validation the loader (or a cross-file check called after loading both files) would need,
beyond per-entry schema validation:
- Every `uncertain_parameters` entry exists in `config/experiments.yaml`'s
  `uncertain_parameters` map with a non-null range (U-03/U-05 cross-check) — currently
  impossible to enforce since `experiments.yaml` also has no loader.
- `settings.yaml`'s `run.technologies` entries are all keys of the loaded
  `TechnologiesFile` (the comment in `settings.yaml:39` already claims this validation
  happens "at config load" — it does not, since nothing loads `technologies.yaml`).
- `data_quality_audit/audit.py`'s `_TECHNOLOGIES` tuple would be replaced by
  `tuple(loaded_technologies.root.keys())`, removing the hardcoded duplicate.

Not written here — this is a spec only, per the command's instruction.

---

## 5. Values staying in code (action 5, grouped)

See each phase record's own "Embedded-value sweep" section for the itemized list of kind-b/c/d
candidates (all "not moved," above) plus the grouped one-liner for kind-a implementation
constants:

- `docs/phases/F1_data_acquisition.md`: ~30 implementation constants across
  `data_acquisition/` and `fetchers/*.py` — URL templates, a pinned commit SHA, the GWA
  product/height vocabulary (already M-F1-03-cited), filename regexes/globs, and internal
  dispatch/registry dicts — correct location, one grouped line.
- `docs/phases/F1b_data_quality_audit.md`: ~10 implementation constants across
  `data_quality_audit/` — internal bookkeeping dicts, a defensive WDPA column-name list, a
  sentinel default — correct location, one grouped line.

---

## 6. New OQs (action 6)

**OQ-033** (`docs/OPEN_QUESTIONS.md`): `local_layers.py::_MIN_OVERLAP_DEG2 = 1e-6` (deg²,
land-cover tile inclusion threshold) has no citable source — author-chosen numerical
tolerance, not literature-backed. Affects which land-cover tiles enter every country's
mosaic (confirmed live effect: it is what lets BRA's `N03W051` sliver reach Douglas's manual
judgment-call exclusion instead of being auto-excluded). Resolution protocol: Douglas decides
whether it stays a plain engineering tolerance or becomes a Tier 3 `parameters.json` value
per U-07.

No other kind-d value in the scoped directories lacked a source — `GWA_HEIGHTS_M` and
`_DEFAULT_HEIGHT_M` (both `fetchers/wind.py`) are already cited to METHODOLOGY M-F1-03 in
their own code comments, so no OQ was needed for either.

---

## Summary

| Category | Count |
|---|---|
| Kind-b/c/d candidates found (table rows) | 15 |
| Moved now | 0 |
| New tests added | 0 (nothing moved) |
| Kind-a implementation constants (grouped) | ~40 across both modules |
| New OQs opened | 1 (OQ-033) |
| Named prior-session items confirmed, out of scope, untouched | 2 (AHP in `core/`, thresholds in `suitability_criteria/`) |
| `technologies.yaml` loader spec | written (this document, section 4), not implemented |
