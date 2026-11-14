# Entries still in `awaiting_content_check_post_77` (COMMAND 118, 2026-11-09)

Written for: the author, to decide which states can be released. Source: `docs/PROGRESS.json` (`countries`), `outputs/<ISO>/deferred_check.json`, `docs/PROGRESS.json` `pending_verifications` PV-77, `docs/CONVENTIONS.md` (the meaning of the state).

The state means: the phase ran, but its artifacts have not been compared with the state before the performance work of COMMANDS 75 to 79 (PV-77).

| Country | Phase | State in PROGRESS | Verdict in `deferred_check.json` (written 2026-11-06) | Run again on 2026-11-09 | Content against 9c2dc3c8 |
|---|---|---|---|---|---|
| BRA | F1b (`data_quality_audit`) | awaiting_content_check_post_77 | EXPLICADO | yes (161 s) | identical |
| BRA | F4 (`climate_forcing`) | awaiting_content_check_post_77 | IDENTICO | yes (111 s) | identical (3 artifacts) |
| IND | F4 (`climate_forcing`) | awaiting_content_check_post_77 | IDENTICO | yes (96 s) | identical (3 artifacts) |

Released by COMMAND 116 (set to `ran_clean`, as the command's item 7 asked): F2b of IND and BRA (see D-F2b-008 of `docs/phases/F2b_siting_layers.md`: 11 of 14 artifacts identical, 3 changed by the distance correction).

Notes for the decision, nothing forced:
- The command text of 118 names **F1b of IND**; in `docs/PROGRESS.json` the F1b of IND is already `ran_clean`, and it is the F1b of **BRA** that is waiting. No other entry is waiting: PRT has none, F1, F2a, F3 and F5 are `ran_clean` everywhere.
- `deferred_check.json` of IND and BRA has `pending: []` and settled verdicts for the three phases above (checked on 2026-11-06); PV-77 stays open in `pending_verifications`. The state in PROGRESS and the verdict in the gate report are therefore out of step; the round of 2026-11-09 did not update that report (OQ-080).
- The round of 2026-11-09 executed the three phases on the current code and their artifacts are identical by hash to the state of 9c2dc3c8, which is the same kind of evidence the check asks for, but against 9c2dc3c8 and not against the state before COMMANDS 75 to 79.
