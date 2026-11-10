# Stored cache keys against recomputed keys (COMMANDS 123 and 124; closes OQ-081)

Written for: the author. Read-only: no official output, sidecar or manifest was changed (hashes of the three manifests, of `references/latest.json` and of every `.cachekey` and `.key` file identical before and after).

## Method

The real `main.py` of the tree of `ast-normalize` (new algorithm, `core/code_fingerprint.py` COMMAND 120) ran for each country on a scratch data directory (a copy of `outputs/<ISO>` and `interim/<ISO>`, `raw` and `external` as read-only junctions, removed afterwards), under a wrapper outside the repository that replaces in memory the comparison functions by recorders: `grid_alignment.alignment.cache_is_current` and `core.geo_utils.clip_cache_is_current` (and the name imported by `data_quality_audit.vector_inspection`). Each call writes the key the code recomputes and the content of the sidecar on disk, and lets the run go on. Three sources of keys:

- **Aligned layers (`.cachekey`)**: every call of `cache_is_current` of F2a, with its real inputs (the phase computes the key from the hashes of the inputs and the configuration).
- **F1b clips (`.key`, `interim/<ISO>/data_quality_audit`)**: every call of `clip_cache_is_current` of the audit, in the real F1b run.
- **F2a and F3 clips (`.key`, `interim/<ISO>/grid_alignment` and `.../land_eligibility`)**: F2a builds the clip in a child process and F3 reads it only when its shares have to be built (they were cached), so neither calls the comparison in a normal round. The key was recomputed with the same function the phases use (`geo_utils.clip_cache_key`), called with the source file and the country polygon that the phase holds (captured at the entry of `run_grid_alignment_phase` and `prepare_stripe_inputs`), and compared with the sidecar. The rest of the phase was not run for F3.

Control: the same harness on the tree of `756db00` (the code before COMMAND 120, the former algorithm; byte-identical `src` to the then `main`), PRT only.

## Result by country (new algorithm)

| | aligned layers | F1b clips | F2a clips | F3 clips | total | equal | different |
|---|---|---|---|---|---|---:|---:|
| PRT | 25 of 25 equal | 4 of 4 | 0 of 3 | 0 of 3 | 35 | 29 | 6 |
| IND | 26 of 26 equal | 4 of 4 | 0 of 3 | 0 of 3 | 36 | 30 | 6 |
| BRA | 25 of 25 equal | 4 of 4 | 0 of 3 | 0 of 3 | 35 | 29 | 6 |

- Every key of every aligned layer that the phase computes (25, 26 and 25) is equal to its sidecar, and every F1b clip key (4 per country) too. This is the proof that the new fingerprint algorithm invalidates no cache.
- **Control, PRT:** the former tree gives the same recomputed key and the same verdict as the new one in all 32 comparisons of the F1b and F2a run (29 equal, 3 different) and in the 3 of F3 (3 different, with the same keys). The difference does not come from the algorithm.

## The 6 clip sidecars per country that are different

`interim/<ISO>/grid_alignment/{roads,lakes,rivers}_clipped.key` (F2a) and `interim/<ISO>/land_eligibility/{lakes,protected,rivers}_clipped.key` (F3), all written on 2026-10-28 (19:50 to 19:55); the sidecars of the F1b copies were written on 2026-10-29 (20:24). In all 18 cases (3 countries x 6) the recomputed key is exactly the key of the F1b copy of the same layer, and the stored one is another.

**Why (history, read-only).** `clip_cache_key` itself was last changed on 2026-10-20 (`5be8f65`, the code of the cache enters the key). Its inputs are the source file hash, the country polygon and `cache_code("clip")`, the closure fingerprint of the clip code. That last one is what changed, in four commits of 2026-10-29 (the closure of the clip code reaches `core/geo_utils.py` and the modules it imports; measured: the value of `cache_code("clip")` at each commit):

| commit | date | clip code (first 8 hex) |
|---|---|---|
| `5be8f65` | 10-20 22:43 | `a17da307` |
| `428adec` (last of 10-28, 19:29) | 10-28 | `a17da307` |
| `78631b9` clip: keep the lines the polygon covers | 10-29 11:27 | `8fff6f0a` |
| `bf9d839` clip: F2a and F3 read the audit's clip | 10-29 11:47 | `0add6dfa` |
| `0790100` territory kept between runs | 10-29 11:53 | `a905361f` |
| `e7b8da8` digest of each source file kept | 10-29 11:55 | `a905361f` |
| `e34198e` restrict the covered-line shortcut | 10-29 19:50 | `af20a194` (and since, up to `756db00` and now) |

**It explains the stored keys.** On PRT, replacing only the `code` field of the key by `a17da307bff42f9235f44b58f594211da7b208864248eb45ef9fb4ef5b515e40` and leaving the rest as the code computes it, the 6 stored keys (F2a roads, lakes, rivers; F3 lakes, protected, rivers) are reproduced exactly, character by character. So the source files and the polygon did not change: the sidecars were written under the code of 2026-10-28 and the code changed afterwards. They are not hits of any key, and `current_clip_cache` (`core/geo_utils.py`) reads the F1b copy, which carries the current key: nothing is recomputed because of them.

## What was not checked

- **`slope_aligned` and `slope_counts_aligned` (GLO30, 2026-11-06), 2 layers per country** with their `.cachekey` and `.cachekey.before_adopt`: not checked. The configuration with FABDEM tiles does not compute their key (`grid_alignment/alignment.py`, `use_fabdem`), the manifest registers `aligned/slope` and `aligned/slope_counts` as the `_fabdem_` files, and the code does not read them. No effect on results found; their keys were not compared.
- The reproduction of the divergence with the clip code of 2026-10-28 and the control with the former tree were made on PRT only; IND and BRA show the same pattern (same 6 files, recomputed key equal to the F1b copy) but were not reproduced with the old code.
- The clip keys of F2a and F3 come from a direct call of `clip_cache_key` with the inputs of the phase, not from the builders of those phases.
- Python 3.11 only for this check (3.12 was proved on the fingerprints, `docs/_audit/fingerprint_algo_120.md`).

Follow-up: OQ-083 (what to do with the obsolete sidecars).
