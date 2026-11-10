# Fingerprint algorithm independent of the Python version (COMMAND 120, closed by COMMAND 121)

Resolves OQ-077. Record of the proof on the final code. Branch `ast-normalize`, base `756db00`.

## What changed

`core/code_fingerprint.py` and `core/function_fingerprint.py` hash `ast.dump` of the normalised tree. Python 3.12 writes `type_params=[]` in every function and class definition, so the same source had another digest outside 3.11. `canonical_dump` writes the text of the 3.11 `ast.dump` on any version, and a statement without a name at the end of each module puts it in the place of `ast` in that module's namespace (the definitions the fingerprints read were not edited). `FINGERPRINT_ALGO_VERSION = 1` adds nothing to the hash.

## Proof (COMMAND 121, item 2)

Method: `closure_fingerprint(PHASE_CODE_ROOTS[phase])` for the 19 phases and `function_fingerprint(CACHE_FUNCTION_ENTRIES[key])` for the 13 caches, computed on two trees and two interpreters, with `GEOFREA_DATA_DIR` unset (no digest store): the base tree (`git archive 756db00 src`, former algorithm) and the final working tree (algorithm 1), on CPython 3.11.9 and 3.12.10. First 8 hex digits shown; the comparison was made on the 64.

| kind | name | base 3.11 | base 3.12 | final 3.11 | final 3.12 | final 3.11 = base 3.11 | final 3.12 = final 3.11 |
|---|---|---|---|---|---|---|---|
| phase | climate_forcing | 7c96af81 | 6bc3b578 | 7c96af81 | 7c96af81 | yes | yes |
| phase | climate_maps | cdfa65e1 | 1cebe221 | cdfa65e1 | cdfa65e1 | yes | yes |
| phase | data_acquisition | 7e8abaff | 507d991b | 7e8abaff | 7e8abaff | yes | yes |
| phase | data_quality_audit | c1819a7b | 464244bb | c1819a7b | c1819a7b | yes | yes |
| phase | external_inputs | d62d0c33 | dc089370 | d62d0c33 | d62d0c33 | yes | yes |
| phase | external_validation | e46e4d9b | 3fa28b1e | e46e4d9b | e46e4d9b | yes | yes |
| phase | grid_alignment | aa3ea919 | f96ddcc4 | aa3ea919 | aa3ea919 | yes | yes |
| phase | hazard_context | cdfa65e1 | 1cebe221 | cdfa65e1 | cdfa65e1 | yes | yes |
| phase | land_eligibility | 20835176 | e10be488 | 20835176 | 20835176 | yes | yes |
| phase | lcoe_maps | 77408d54 | c737aebd | 77408d54 | 77408d54 | yes | yes |
| phase | lcoe_modeling | 77933722 | ebcc77c8 | 77933722 | 77933722 | yes | yes |
| phase | overview | bc0ba154 | 068067c5 | bc0ba154 | bc0ba154 | yes | yes |
| phase | potential_maps | 6a640565 | 662555ae | 6a640565 | 6a640565 | yes | yes |
| phase | results_synthesis | e910d203 | ce13b291 | e910d203 | e910d203 | yes | yes |
| phase | robustness_analysis | d575fe97 | 8bbc93c5 | d575fe97 | d575fe97 | yes | yes |
| phase | robustness_maps | a3b88996 | 4365343e | a3b88996 | a3b88996 | yes | yes |
| phase | sample_size_convergence | f5179f8c | 9c0cc2d7 | f5179f8c | f5179f8c | yes | yes |
| phase | siting_layers | 3f2beadf | b8a94e39 | 3f2beadf | 3f2beadf | yes | yes |
| phase | technical_potential | 80d5cee8 | e38888ba | 80d5cee8 | 80d5cee8 | yes | yes |
| cache | aligned_layer.fabdem_slope | f07ca25e | ab93e419 | f07ca25e | f07ca25e | yes | yes |
| cache | aligned_layer.glo30 | da77f0af | 7248fed1 | da77f0af | da77f0af | yes | yes |
| cache | aligned_layer.grid | b5e0e13c | 58bd809b | b5e0e13c | b5e0e13c | yes | yes |
| cache | aligned_layer.lakes | ecd9c417 | d593181b | ecd9c417 | ecd9c417 | yes | yes |
| cache | aligned_layer.land_cover | aade99b9 | e1b86f5c | aade99b9 | aade99b9 | yes | yes |
| cache | aligned_layer.land_cover_counts | 2241b22e | 0515c04b | 2241b22e | 2241b22e | yes | yes |
| cache | aligned_layer.poi | 7e433514 | 7742db88 | 7e433514 | 7e433514 | yes | yes |
| cache | aligned_layer.population | c7d15711 | 85eb9530 | c7d15711 | c7d15711 | yes | yes |
| cache | aligned_layer.rivers | f35d99ad | 5cd432ff | f35d99ad | f35d99ad | yes | yes |
| cache | aligned_layer.roads | e0f6e026 | e88925ef | e0f6e026 | e0f6e026 | yes | yes |
| cache | aligned_layer.settlements | e723c589 | be03eb15 | e723c589 | e723c589 | yes | yes |
| cache | aligned_layer.solar | 43f57203 | 38e94340 | 43f57203 | 43f57203 | yes | yes |
| cache | aligned_layer.wind | c1cbc74f | 4619cc36 | c1cbc74f | c1cbc74f | yes | yes |

Totals: phases 19/19 and caches 13/13 keep the value they had on 3.11 (final 3.11 = base 3.11), and 19/19 and 13/13 are equal between 3.12 and 3.11 on the final code. On the base tree no one of the 32 was equal between 3.11 and 3.12 (0/19, 0/13): the divergence that OQ-077 described, and its removal.

## The 33 manifest entries (and why it is not a 33rd fingerprint)

32 fingerprints are computed (19 + 13). The number 33 of the earlier check is a count of manifest entries, not of fingerprints: the manifests of PRT, IND and BRA (round 1d34ab23) hold 12 phase entries each; the 11 with status `success` (all but `overview`, `stale_upstream`, which is not counted) have a recorded `code_fingerprint`, so 3 x 11 = 33 entries, over 11 distinct phases of the 19. Each recorded value was compared with the fingerprint of the same phase: **33/33 equal on 3.11 and 33/33 equal on 3.12** with the final code. The other 8 phases have no successful entry with a code fingerprint in these manifests, and the 13 cache fingerprints are not stored in the manifests; they are checked against each other and against the base tree above.

## Standard `ast.dump` left intact (item 3)

`tests/unit/test_fingerprint_algorithm.py`: `test_the_stdlib_ast_dump_is_intact_after_the_two_modules_are_imported` (the `ast` module in `sys.modules` is the stdlib's, its `dump` is neither `canonical_dump` nor changed, and it writes `type_params=[]` exactly when the interpreter is 3.12 or later) and `test_a_fresh_interpreter_gives_the_same_stdlib_dump_before_and_after_the_import_of_the_two_modules` (a clean `-I` interpreter keeps the same `ast.dump` object and output after importing both modules).

## Python versions tested (item 4)

Tested: 3.11.9 (development machine) and 3.12.10 (embeddable build, proof above); the unit job of CI covers 3.11 and 3.12 (`.github/workflows/unit.yml`). **3.13 was not tested.** `requires-python` is `>=3.11`, so 3.13 is allowed but unverified: its stdlib `ast.dump` also omits empty and `None` fields and its node classes may differ, and `canonical_dump` was written and checked only against the 3.11 and 3.12 shapes of the tree. The test that compares `canonical_dump` with the stdlib text is skipped on 3.13 and later for that reason. Before running the pipeline on 3.13 the proof above has to be repeated there; if a fingerprint differs, the fix is in `canonical_dump`, never a new `FINGERPRINT_ALGO_VERSION` (that one changes every fingerprint).
