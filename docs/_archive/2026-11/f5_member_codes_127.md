# F5: the members of the forcing from the codes, without `astype(str)` (COMMAND 127, item 2; item c of COMMAND 124)

Written for: the author. Branch `f5-memory`, on top of items a, b and d (`docs/_audit/f5_memory_126.md`). `climate_forcing/forcing.py` (so `assert_forcing_usable`) is not changed. IND and BRA were not run.

## What the transient was

`forcing.parquet` stores `member` as a dictionary column (`dictionary<values=string, indices=int8>`, 37 values); `pd.read_parquet` gives a `category` column: 10.6 M int8 codes (10 MB) and 37 strings. `forcing["member"].astype(str)` turns it into a string per row (pandas 3: dtype `str`, 361 MB retained) and, to get there, builds intermediate arrays of 10.6 M elements: on the BRA `forcing.parquet` read alone in a fresh process the step goes from 595 to 1,617 MB (**+1,022 MB**), and 581 MB after. In the F5 run of BRA the process was already at about 1.1 GB, which gives the 2,137 MB (wind) and 1,971 MB (solar) of `f5_peak_measured.md`. The guard repeats it: `assert_forcing_usable` evaluates `forcing["member"].astype(str).isin(members)` over the whole column once per scenario (3 times).

## What changed (`technical_potential/pipeline.py`)

- `_has_string_member_codes`: the fast path applies only when `member` is a categorical of unique strings, with no missing value, and `members` has no repeated name; any other column takes the old path unchanged.
- The unknown-member check reads the names in use from the codes (`_members_in_use`); same set, same message.
- `_assert_usable_by_member`: calls `assert_forcing_usable` once per member on the rows of that member (a view of 1/37 of the rows), so no string column of the whole forcing is made. Every check of the guard is a condition on one (cell, member) and the expected count is a sum over the members, so the guard passes on the whole forcing exactly when it passes on each member. If a member fails, the guard is called again on the whole forcing with the strings, as before, so **the error raised, message and counts, is that of the unchanged code** (tests with six kinds of damage compare the messages).
- `_forcing_by_member`: the group of each member is cut by its code, in order of first appearance (the order of `groupby(sort=False)`), and its `member` column is not kept (nothing reads it: only `delta_rsds`, `dT` and `delta_wind`); `forcing` is released afterwards.

## Equivalence

- Unit tests (`tests/unit/test_f5_member_codes.py`, 19): the factor tables equal those of the string path byte by byte, with the dictionary in another order than the rows and an unused category; first-appearance order; the fallbacks (strings, missing member, non-string categories, repeated name); the guard equal to the whole-forcing guard, same message in six failure cases and the declared wind mask; the guard never receives more than one member's rows; the whole of F5 on the synthetic world with a categorical forcing (dictionary reversed, one unused value): every artifact byte-identical to the string forcing; the member not in `members.yaml` refused with the same message.
- **PRT in a scratch directory** (old = `git archive` of main, new = this branch; same Python 3.11.9, pyarrow 25.0.1, pandas 3.0.6): **71 of 71 files of `outputs/PRT/technical_potential` identical by SHA-256**; the peak of the phase (`peak_wset`) 410 -> 391 MB. The official PRT `forcing.parquet` is categorical, so the new path ran.
- **Synthetic of the size of BRA, not BRA data** (`synth127.py`: 37 members x 286,000 cells, 10.58 M rows, dictionary `member`, float32 factors; the forcing part of `build_technology_potential`, three scenarios, fresh process each): SHA-256 of the 37 factor tables (names, index, three columns) **equal**, same order.

| step (MB) | old: start, peak, after | new: start, peak, after |
|---|---:|---:|
| `astype(str)` | 483, 1,717, 832 | not made |
| guard, per scenario | 834, 1,152, 643 | 615, 663, 422 |
| `by_member` | 641, 897, 646 | 410, 644, 621 |
| **process peak** (`peak_wset`) | **1,717** | **663** |

(The `read_parquet` step peaked at 490 old and 628 new in these two runs: the same call, run-to-run variation of the Arrow reader; it is not the changed code.)

## What is left of the BRA peak, by arithmetic (not measured)

Point of the 2,137 MB (`forcing['member'].astype(str)`, wind): the step no longer exists; the forcing stage adds about 0.25 GB over the 1.1 GB the process had (the synthetic `by_member` step, 644 over 410), so about 1.35 GB. The next highest point of the run, after a, b and d (`f5_memory_126.md`), is the `read_cell_pixels` of the third wind scenario, about 1.40 GB, and the third solar `concat` about 1.25 GB. So **the phase peak falls from 2,307 MB to about 1.4 GB, under 1,536 MB by about 0.13 GB**, with the same assumptions as the table of items a, b and d (the retained memory of the previous scenario is released; the synthetic read difference holds at BRA scale), and this ignores what the new code frees besides (the 361 MB string column and the forcing frame are no longer held for the whole phase). **The official round measured 3,410 MB, and 0.8 GB of it is not located in `f5_peak_measured.md`: this arithmetic does not say where the round peak is, and the margin of 0.13 GB is thin.** A run of F5 alone on BRA, with the per-step marks, is what settles it.

## Blast radius

The fingerprint of the same five phases as before changes (`technical_potential`, `potential_maps`, `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`) and no other; `pipeline.py` imports `ForcingContractError` from `forcing.py`, which was already in the closure. The 13 caches do not change.
