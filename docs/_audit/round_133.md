# Round 133: the clean round after the merge of window-132 (2026-11-12)

Written for: the author, to read the result of the single window of recomputation (COMMAND 133). The reference 1d34ab23 was **not** moved: the publication of the reference was switched off for the process of the round (a driver outside the repository that replaces `ReferenceStore.publish` by a no-op; OQ-080), and `references/latest.json` still names 1d34ab23 for the three countries.

## Duration, peak and excess over the cap, by phase and country

Official orchestrator (`main.py`), `GEOFREA_MEMORY_CAPS` on (not set), order PRT, IND, BRA; the default phases first, then `--phases technical_potential,potential_maps` (the F5 phases are not in `target_phases`). Every phase ended `success`; no phase reached its hard limit; `peak_over_cap` is empty everywhere (no peak went past its cap).

| phase | cap MB | PRT s / MB | IND s / MB | BRA s / MB |
|---|---:|---|---|---|
| data_acquisition | 1024 | 9.4 / 325 | 680.9 / 929 | 169.0 / 798 |
| grid_alignment | 576 | 3.7 / 289 | 41.6 / 280 | 16.7 / 346 |
| climate_forcing | 768 | 105.4 / 307 | 136.3 / 311 | 159.5 / 580 |
| climate_maps | 2944 | 29.5 / 670 | 85.0 / 1457 | 91.1 / 2551 |
| hazard_context | 3520 | 34.1 / 759 | 110.8 / 1619 | 275.4 / 1601 |
| land_eligibility | 1856 | 16.8 / 418 | 275.5 / 697 | 943.1 / 877 |
| technical_potential | 1984 | 20.5 / 418 | 90.1 / 1061 | 266.9 / 1482 |
| potential_maps | 2112 | 11.3 / 675 | 26.6 / 1543 | 70.3 / 1806 |
| overview | 2560 | 15.2 / 888 | 36.8 / 1357 | 49.8 / 1186 |

The closest to a cap: BRA `climate_maps` 2,551 MB of 2,944 (87%); BRA `potential_maps` 1,806 of 2,112 (86%); IND `potential_maps` 1,543 of 2,112; BRA `technical_potential` 1,482 of 1,984. The phases ran in one process per country and per group of phases, as in the measurements the caps come from; a full BRA chain in one process was not tried.

## Fingerprints moved, by phase (manifest, before and after the round)

| phase | code fingerprint before -> after (same in PRT, IND, BRA) | config fingerprint before -> after |
|---|---|---|
| data_acquisition | 7e8abaff9277 -> 93e7fcf003b1 | 632e1ba7a37f (unchanged); 9a1554e3b8d4 (unchanged); eaba30cca2ec (unchanged) |
| data_quality_audit | c1819a7b8d3f (unchanged) | 35a5f3a4b4e7 (unchanged) |
| external_inputs | d62d0c3340fb (unchanged) | 62267c2d2dd0 (unchanged) |
| grid_alignment | aa3ea9199737 -> 7e0698c612c0 | 5505e7740fb8 (unchanged); 6c31df31a8e0 (unchanged); f78b188a5f00 (unchanged) |
| climate_forcing | 7c96af81cfb7 -> b6607b24c275 | 62267c2d2dd0 (unchanged) |
| climate_maps | cdfa65e1a83f -> f5164c8415bd | 0e091b394340 (unchanged) |
| hazard_context | cdfa65e1a83f -> f5164c8415bd | d4e127b640f0 (unchanged) |
| siting_layers | 3f2beadf87a9 (unchanged) | 44136fa355b3 (unchanged) |
| land_eligibility | 2083517697f2 -> 44726ec374ea | 74bf1d4fa773 -> 5c032caf6df7; b2dc54e7e12e -> 246d6cfcffd1; cde868d2d614 -> 8d3b7c185243 |
| technical_potential | de48060d79be -> 38cb5700395e | 0144db1cb058 -> 03bb2e18dd43; 4ed3002d4975 -> 3b7c6682bced; d78bd4fd406e -> ede348840dca |
| potential_maps | 64972e86f269 -> 88e935618489 | 24b6519fd292 (unchanged); 802eb2d6d748 (unchanged); d28cdb4aa4be (unchanged) |
| overview | bc0ba1544283 (unchanged) | 0e091b394340 (unchanged) |


The config fingerprints are per country (three values in a row). `land_eligibility` and `technical_potential` changed by the DC note of `parameters.json` (OQ-079); the other phases did not change configuration.

## data_acquisition before and after

Before (manifest of the round of COMMAND 116): IND 422.5 s, BRA 271.5 s, PRT 18.6 s. After, in the round: IND 680.9 s, BRA 169.0 s, PRT 9.4 s. The IND figure includes the **one-time rebuild of the 12 completed GWA mosaics** (about 46 s each, about 550 s in all): the edit of `fetchers/wind.py` changes the key of the cache `gwa_mask_mosaic`. BRA and PRT have no completed mosaic and show the gain of the change by itself (BRA 271.5 to 169.0 s, PRT 18.6 to 9.4 s).

## Comparison with the reference 1d34ab23

314 artifacts (the artifacts of the manifests of the reference), by value: **254 bytes identical, 60 values identical (Arrow type or writer differ), 0 values different**; per country PRT 84+20, IND 86+20, BRA 84+20. The 20 per country are `forcing`, `forcing_masked`, `hazard_context` (F4) and the 17 tables of F5 (`potential_*`, `class_flag_wind__*`, `ensemble_*`). The files of the reference are not kept for tables (`reference_store` keeps JSON and the rasters of two phases): the copy compared is the file that was on disk before the round, copied beforehand to `work/ref133_snapshot` and checked against the reference by hash: the 15 tables of F5 other than the two aggregates still carry the content hash of the reference; `potential_aggregates_solar` and `potential_aggregates_wind` do not (they were rewritten after the reference, OQ-084), so for those two the comparison is against the file of the day before the round, not against the reference itself. The F4 files (`forcing`, `forcing_masked`, `hazard_context`) have values identical; `forcing_masked` changed its content hash because pandas 3 writes `string` where the reference has `large_string` (same rows: 0 in IND, 42,947 in BRA).

Steady state, measured apart (the phase run in-process on a scratch data directory with links to `raw` and `external`, no hash memo, mosaics already rebuilt, nothing else running; the manifests untouched): **IND `data_acquisition` 214.0 s, against 422.5 s before** (-49%). Of the 681 s of the round, about 550 s were the one-time mosaic rebuild. The proof of equality of the coverage percentages (`mask_coverage_pct`, bit for bit, `main` against the branch): 24 files of IND (12 own, 12 completed) and 12 of BRA identical; time of those calls alone 434.6 to 132.7 s (IND) and 302.4 to 146.1 s (BRA).

## Integrity and manifests

`check_manifests --bytes`: PRT 105, IND 107, BRA 105 artifacts, all VALID. `verify_cache_integrity` without `--dry-run` (report `logs/integrity/integrity_20261112_143148.md`): PRT {ok: 114}, IND {ok: 140}, BRA {ok: 115}; no key invalidated. The manifests have schema 2.11, run_id 6ec04875 (the three countries), 12 phases `success`, none `stale_upstream`.

## Deferred content checks (`awaiting_content_check_post_77`), verdicts

Against the manifest of the state before COMMAND 77 (`unattended/20261029_135838/manifest_before.json`, content hashes only), and the reference 1d34ab23:

- **F4 of IND and of BRA: settled.** `forcing`, `hazard_context` and `climate_maps` IDENTICO to the state before 77. `forcing_masked`: the hash differs, but the reference 1d34ab23 has the hash of the state before 77 and the file now equals the reference in value (pandas 3 writes `string` where `large_string` was written; 0 rows in IND, 42,947 in BRA): EQUIVALENTE. (COMMAND 133.)
- **F1b of IND**: `ran_clean` already.
- **F1b of BRA: not confirmed (COMMAND 134, read only).** The `audit_report` before COMMAND 77 (`json:b47dc49da582...`) is on no disk: only its hash is in `manifest_before.json`. The oldest copy that exists is in the reference round 27c9336b (accepted 2026-11-04, methodology 16.2.0, `json:3cb93e488da1...`). Against the current file (`json:d7a35c784679...`) the keys that differ are `slope_threshold_check/solar/threshold_deg` (10.0 to 1.7183580016554572) and `slope_threshold_check/wind/threshold_deg` (10.2 to 5.710593137499643); `geometry_types` does not differ in that pair (the NaN `nodata` entries compare unequal as floats only). The difference is therefore **not** only the `geometry_types` counts, and the comparison with the state before 77 itself cannot be made. Consequence: F1b of BRA stays `awaiting_content_check_post_77` in `PROGRESS.json` and BRA stays in `config/deferred_checks.yaml`; IND was removed from it.

## F5 tables: hash kind (item 6e of COMMAND 133, restamped in COMMAND 134)

The two aggregates (`potential_aggregates_solar`, `potential_aggregates_wind`) came out of the round with `parquet:`, not `parquet2:`, in the three countries: the orchestrator keeps the kind of an existing entry (OQ-084). In COMMAND 134 the six entries were restamped by `scripts/restamp_parquet2.py` (dry run by default, fails closed): for each one the bytes of the file are the registered ones, its `parquet:` hash is the recorded one, its value equals that of the file of the same path in `work/ref133_snapshot` (the Arrow type ignored), and the new hash is `parquet2:` of the file (111 rows x 12 columns the solar tables, 93 x 12 the wind tables; the digest of the two kinds is the same for these tables, only the kind prefix changes). The proof is in `hash_restamps` of each manifest (schema 2.12). After it: `check_manifests --bytes` VALID (PRT 105, IND 107, BRA 105 artifacts), 12 phases `success` and none `stale_upstream` in each country.

## The deferred gate against 1d34ab23 (COMMAND 134, read only)

The gate run on the manifests as they are (reference `latest` = 1d34ab23, IND included with the yaml as it was): `data_acquisition`, `data_quality_audit`, `grid_alignment`, `siting_layers`, `land_eligibility`, `external_inputs`, `hazard_context`, `climate_maps`, `potential_maps` IDENTICO; `technical_potential` EXPLICADO (the DC note moved its configuration); `overview` SEM_REFERENCIA (the reference did not keep it, it was `stale_upstream`); **`climate_forcing` DIFERENTE in the three countries**, by one artifact, `forcing_masked`, whose `parquet:` content hash moved because the Arrow type of its two string columns is `string` now and was `large_string` (same values, compared by value in COMMAND 133). A DIFERENTE phase makes the store refuse the round (`publish_state`), so the new reference was **not** published.

## COMMAND 135: expected pins, F1b of BRA, publication

- **Gate before and after.** Against 1d34ab23 with `forcing_masked` declared in `expected` (pinned to 1d34ab23): in PRT, IND and BRA `climate_forcing` EXPLICADO_REVISAR, `technical_potential` EXPLICADO, `overview` SEM_REFERENCIA, the other nine phases IDENTICO, no DIFERENTE. After the publication, against 6ec04875: the 12 phases IDENTICO in the three countries; the three pins expired by construction (`scripts/list_expired_expected.py`) and were removed.
- **F1b of BRA explained.** Commit 9dd49df (2026-11-05, COMMAND 97, Group 6) replaced `slope_max_deg` by `slope_max_pct` in `config/experiments.yaml` (solar 3 %, wind 10 %); the F1b of BRA ran on 2026-11-06 11:30. `strictest_slope_max_deg` then gives atan(0.03) = 1.7183580016554572 deg for solar and atan(0.10) = 5.710593137499643 deg for wind, the two values of `slope_threshold_check` of the current `audit_report`, to the last digit; before it they were 10.0 and 10.2. `PROGRESS.json`: F1b of BRA `ran_clean`; BRA and IND left `config/deferred_checks.yaml` after the publication (the gate of each had to be part of the evidence).
- **Publication (by hand, after the comparison).** Round 6ec04875eac770b69a8978c65cd4f8a53969c9cbed57b8a17b39c77ae86b6bbb of PRT (53 files), IND (55) and BRA (53), `scripts/publish_reference.py`; 1d34ab23 is kept; `references/latest.json` names the new round for the three countries (OQ-080).
