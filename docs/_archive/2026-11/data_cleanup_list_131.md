# What `GeoFREA_data` holds that no current manifest references (COMMAND 131, item 8)

Written for: the author, to decide what to delete. **Nothing was deleted, moved or changed**; the sizes and dates come from the file system (`os.stat`, hard links counted once), and "referenced" was checked by searching the paths and the directory names in the four current manifests (`outputs/{PRT,IND,BRA,ZZZ}/manifest.json`): none of the directories below appears in them. Never listed, by instruction: `raw`, `external`, `outputs` and the scratchpad with the backups of the manifests. Sizes in GB are 2^30 bytes. Measured on 2026-11-12 on `D:\Douglas\DOUTORADO\GeoFREA_data`.

The rule of category (ii) was applied as written: a backup is listed there only when its hash is recorded in `docs/_audit`. Where it is not, the item is listed apart ("outside the rule of (ii)") so the decision is yours and not hidden.

## (i) Drafts and `work` directories

| path | size | files | newest file | why it is not referenced | where the audit mentions it |
|---|---:|---:|---|---|---|
| `work/pre116` | 5.164 GB | 1,164 | 2026-11-06 | the state of the three countries before the exact geodesic distances (COMMAND 116); the comparison base of COMMAND 118 | `compare_9c2dc3c8_vs_1d34ab23.md`, `f3_peak_118.md`: the conclusions are written there; the data is needed only to repeat the comparison |
| `work/snapshot_129` | 1.886 GB | 215 | 2026-11-10 | the hash snapshot of F5 and `potential_maps` taken by COMMAND 129 before the rerun; the comparison is done and reported | `general_audit_130.md` only (made by this session; kept at the end of COMMAND 129) |
| `_f3_new_BRA` | 1.526 GB | 54 | 2026-11-03 | draft of F3 of BRA (COMMAND 89/90) | `f3_memory_90.md` |
| `_f3_cold_BRA` | 1.487 GB | 51 | 2026-11-04 | cold F3 round of BRA, draft | `general_audit_130.md` only |
| `_f3_97_BRA` | 1.198 GB | 48 | 2026-11-05 | F3 of BRA of COMMAND 97 (Group 6), draft | `ren_source_audit.md` |
| `_f3_profile_BRA` | 0.727 GB | 37 | 2026-11-03 | profile harness output of F3 of BRA | `general_audit_130.md` only |
| `work/val117_BRA` | 0.038 GB | 2 | 2026-11-09 | validation scratch of COMMAND 117 | `general_audit_130.md` only |
| `_f3_97_PRT` | 0.017 GB | 48 | 2026-11-05 | F3 of PRT of COMMAND 97, draft | `ren_source_audit.md` |
| `work/ren_probe` | under 1 MB | 1 | 2026-11-08 | probe of the renewable-capacity source | `ren_source_audit.md` |
| **total (i)** | **12.043 GB** | | | | without `snapshot_129`: 10.157 GB |

## (ii) Backups older than the current round whose hash is in `docs/_audit`

The current round is `1d34ab23` (`references/latest.json`). The only earlier round whose full SHA-256 is written in `docs/_audit` is `9c2dc3c8...` (3 occurrences in `ren_source_audit.md`; `compare_9c2dc3c8_vs_1d34ab23.md` names it by its first 8 characters and records no 64-character hash).

| path | apparent size | bytes not shared with the current round | note |
|---|---:|---:|---|
| `references/9c2dc3c88f93a3f8a09471877365c136cf3dafa5ce7560dd874a9a1585156c20` | 1,961 MB | about 1 MB (the rest are hard links to files the other rounds and `objects/` keep) | removing the folder frees almost nothing; it is also the reference of an earlier gate comparison (OQ-080), so it is listed and not recommended |

**Outside the rule of (ii), for information (hash not recorded in `docs/_audit`, so not offered as removable):**

| path | size | note |
|---|---:|---|
| `backup_before_89` | 1.978 GB (214 files; `BRA`, `BRA_elig`, `BRA_siting`, `IND`, `IND_elig`, `IND_siting`) | outputs of 2026-10-28 to 11-02, before the cold round of COMMAND 89; cited by name in `f3_memory_90.md` and `ind_population_effect_89.md` as the "before" of an equality statement |
| `backup_before_91` | 0.619 GB (84 files; `BRA_elig`) | outputs of F3 of BRA before COMMAND 91 |
| the other six rounds of `references/` (`27c9336b`, `3a1b06e0`, `74931e0a`, `864efbcb`, `8f55f3e7`, `f392f2c4`) | 601 MB not shared with the current round, together with `9c2dc3c8` | named by 8 characters in four audit files (or in none); `3a1b06e0` is a 20 MB set |

## (iii) Sidecars of OQ-083

Checked: no manifest registers any of them (`aligned/slope` and `aligned/slope_counts` point to the `_fabdem_` files).

| group | files | size | note |
|---|---:|---:|---|
| clip keys `interim/<ISO>/grid_alignment/{roads,lakes,rivers}_clipped.key` and `interim/<ISO>/land_eligibility/{lakes,protected,rivers}_clipped.key` | 18 (6 per country) | 1,152 bytes | written 2026-10-22 (BRA), 2026-10-28 (PRT) and 2026-10-28/29 (IND) under the clip code `a17da307`; the current one is `af20a194`, so no run finds them current (`cache_keys_123.md`); not read by `src` |
| GLO30 slope layers `outputs/<ISO>/grid_alignment/artifacts/<ISO>_slope_aligned.tif` and `<ISO>_slope_counts_aligned.tif`, each with `.cachekey` and `.cachekey.before_adopt` | 24 (12 rasters and 12 sidecars) | 0.373 GB (BRA 43.0 + 247.2 MB, IND 17.3 + 88.1 MB, PRT 0.6 + 4.0 MB) | GLO30 of 2026-11-06, replaced by the FABDEM layers; not built or read while the FABDEM tiles exist. They sit under `outputs/`, so deleting them is the one item of this list inside `outputs`: it is listed because OQ-083 names it, and nothing else of `outputs/` is |

OQ-083 also asks that, if the files are removed, `scripts/verify_cache_integrity.py` and the reference store be checked afterwards.

## Totals

| | size |
|---|---:|
| (i) drafts and `work` | 12.043 GB (10.157 GB without `snapshot_129`) |
| (ii) by the rule | about 1 MB |
| outside the rule of (ii): `backup_before_89` and `backup_before_91` | 2.597 GB |
| (iii) | 0.373 GB |
| **Sum of (i), (iii) and the two backups** | **15.013 GB** (12.043 + 2.597 + 0.373) |
