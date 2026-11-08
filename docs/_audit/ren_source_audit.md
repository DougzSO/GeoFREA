# REN source audit (command after 101)

Read-only audit. Nothing in the pipeline was changed and nothing was committed. Date: 2026-11-08. HEAD `1975a0f`. The only file this audit adds to the repository is this report.

## Part A

### A1. Wind: the "2 % at most" claim against the PRT restrictive ratio of 1.11

The claim in D-F3-029 ("moves wind by 2 % at most") was wrong as written. It came from the central scenario and from the seven-tile aggregate of `slope_dem_test_100.md` (wind central 1.00-1.01, "all 7" 1.00-1.03). The restrictive wind scenario uses the tightest wind slope limit (10 %), where E4 weighs most, and PRT has smooth terrain in the Alentejo, so the FABDEM effect is largest there. The seven-tile test already showed it (PRT wind restrictive 1.06 at pixel level, 1.10 on the 1 degree window); the summary sentence took the central values and the aggregate instead. The 11.1 % of the full round (GLO-30 / FABDEM eligible area 0.90) is consistent with the test. D-F3-029 should say: wind 0.1-2.1 % in the central and permissive scenarios of the three countries, and in the restrictive scenario 11.1 % PRT, 4.2 % BRA, 1.6 % IND. Not corrected here (read-only).

Ratio = eligible area on GLO-30 (Group 6 rules, COMMAND 97) / eligible area on FABDEM (round 9c2dc3c8). GLO-30 sources: reference round 74931e0a (IND, BRA) and the cell tables in `GeoFREA_data/_f3_97_PRT` (PRT: no store reference holds PRT Group 6 on GLO-30). The PRT cell tables sum to the figures of D-F3-029, except permissive solar: 19,527 here against 19,529 written there.

| country | technology | scenario | GLO-30 km2 | FABDEM km2 | ratio GLO-30/FABDEM | FABDEM change % |
|---|---|---|---|---|---|---|
| PRT | wind | restrictive | 18,276 | 20,300 | 0.900 | +11.08 |
| PRT | wind | central | 29,831 | 30,452 | 0.980 | +2.08 |
| PRT | wind | permissive | 35,810 | 36,067 | 0.993 | +0.72 |
| IND | wind | restrictive | 356,541 | 362,215 | 0.984 | +1.59 |
| IND | wind | central | 572,040 | 573,072 | 0.998 | +0.18 |
| IND | wind | permissive | 823,085 | 823,559 | 0.999 | +0.06 |
| BRA | wind | restrictive | 2,150,819 | 2,242,028 | 0.959 | +4.24 |
| BRA | wind | central | 2,640,018 | 2,659,551 | 0.993 | +0.74 |
| BRA | wind | permissive | 2,836,254 | 2,842,441 | 0.998 | +0.22 |

For reference, solar (same sources), restrictive / central / permissive: PRT 0.612 / 0.746 / 0.909, IND 0.807 / 0.895 / 0.973, BRA 0.747 / 0.857 / 0.958.

### A2. `config/memory_budget.json`

Not overwritten. The 942 MB went into its own entry `layers.fabdem_slope` (measured, COMMAND 101 round). `f3_phase.peak_rss_mb` is still 1,438 (BRA, round of 2026-11-04, COMMAND 91; IND 834, PRT 337). Note: the F3 of BRA in the FABDEM round was not re-measured, so 1,438 predates it. No diff needed.

### A3. `scripts/list_expired_expected.py` against reference 9c2dc3c8

Exit code 1 (something can be removed). Every entry of `expected` in `config/deferred_checks.yaml` is expired in the three countries (declared against 74931e0a for IND and BRA, 3a1b06e0 for PRT; the reference is now 9c2dc3c8). Full output:

```
IND: the reference is now 9c2dc3c88f93a3f8a09471877365c136cf3dafa5ce7560dd874a9a1585156c20; these entries were declared against another one and can be removed:
  aligned/slope   (declared against 74931e0a24f0)
  aligned/slope_counts   (declared against 74931e0a24f0)
  aligned_rasters   (declared against 74931e0a24f0)
  capacity_factor_solar   (declared against 74931e0a24f0)
  capacity_factor_wind   (declared against 74931e0a24f0)
  class_flag_wind__central   (declared against 74931e0a24f0)
  class_flag_wind__permissive   (declared against 74931e0a24f0)
  class_flag_wind__restrictive   (declared against 74931e0a24f0)
  climate_maps   (declared against 74931e0a24f0)
  eligibility/admin1_units   (declared against 74931e0a24f0)
  eligibility/candidate_stability_solar   (declared against 74931e0a24f0)
  eligibility/candidate_stability_wind   (declared against 74931e0a24f0)
  eligibility/candidates_solar__central   (declared against 74931e0a24f0)
  eligibility/candidates_solar__permissive   (declared against 74931e0a24f0)
  eligibility/candidates_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/candidates_wind__central   (declared against 74931e0a24f0)
  eligibility/candidates_wind__permissive   (declared against 74931e0a24f0)
  eligibility/candidates_wind__restrictive   (declared against 74931e0a24f0)
  eligibility/cells_0p1deg_solar   (declared against 74931e0a24f0)
  eligibility/cells_0p1deg_wind   (declared against 74931e0a24f0)
  eligibility/cells_solar__central   (declared against 74931e0a24f0)
  eligibility/cells_solar__permissive   (declared against 74931e0a24f0)
  eligibility/cells_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/cells_wind__central   (declared against 74931e0a24f0)
  eligibility/cells_wind__permissive   (declared against 74931e0a24f0)
  eligibility/cells_wind__restrictive   (declared against 74931e0a24f0)
  eligibility/dominant_exclusion_solar   (declared against 74931e0a24f0)
  eligibility/dominant_exclusion_wind   (declared against 74931e0a24f0)
  eligibility/eligible_area_km2_solar   (declared against 74931e0a24f0)
  eligibility/eligible_area_km2_wind   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar__permissive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind__permissive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind__restrictive   (declared against 74931e0a24f0)
  ensemble_solar__central   (declared against 74931e0a24f0)
  ensemble_solar__permissive   (declared against 74931e0a24f0)
  ensemble_solar__restrictive   (declared against 74931e0a24f0)
  ensemble_wind__central   (declared against 74931e0a24f0)
  ensemble_wind__permissive   (declared against 74931e0a24f0)
  ensemble_wind__restrictive   (declared against 74931e0a24f0)
  forcing   (declared against 74931e0a24f0)
  forcing_masked   (declared against 74931e0a24f0)
  hazard_context   (declared against 74931e0a24f0)
  land_eligibility   (declared against 74931e0a24f0)
  members   (declared against 74931e0a24f0)
  overview   (declared against 74931e0a24f0)
  potential_aggregates_solar   (declared against 74931e0a24f0)
  potential_aggregates_wind   (declared against 74931e0a24f0)
  potential_density_solar   (declared against 74931e0a24f0)
  potential_density_wind   (declared against 74931e0a24f0)
  potential_maps   (declared against 74931e0a24f0)
  potential_solar__central   (declared against 74931e0a24f0)
  potential_solar__permissive   (declared against 74931e0a24f0)
  potential_solar__restrictive   (declared against 74931e0a24f0)
  potential_wind__central   (declared against 74931e0a24f0)
  potential_wind__permissive   (declared against 74931e0a24f0)
  potential_wind__restrictive   (declared against 74931e0a24f0)
  technical_potential   (declared against 74931e0a24f0)
BRA: the reference is now 9c2dc3c88f93a3f8a09471877365c136cf3dafa5ce7560dd874a9a1585156c20; these entries were declared against another one and can be removed:
  aligned/slope   (declared against 74931e0a24f0)
  aligned/slope_counts   (declared against 74931e0a24f0)
  aligned_rasters   (declared against 74931e0a24f0)
  capacity_factor_solar   (declared against 74931e0a24f0)
  capacity_factor_wind   (declared against 74931e0a24f0)
  class_flag_wind__central   (declared against 74931e0a24f0)
  class_flag_wind__permissive   (declared against 74931e0a24f0)
  class_flag_wind__restrictive   (declared against 74931e0a24f0)
  climate_maps   (declared against 74931e0a24f0)
  eligibility/admin1_units   (declared against 74931e0a24f0)
  eligibility/candidate_stability_solar   (declared against 74931e0a24f0)
  eligibility/candidate_stability_wind   (declared against 74931e0a24f0)
  eligibility/candidates_solar__central   (declared against 74931e0a24f0)
  eligibility/candidates_solar__permissive   (declared against 74931e0a24f0)
  eligibility/candidates_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/candidates_wind__central   (declared against 74931e0a24f0)
  eligibility/candidates_wind__permissive   (declared against 74931e0a24f0)
  eligibility/candidates_wind__restrictive   (declared against 74931e0a24f0)
  eligibility/cells_0p1deg_solar   (declared against 74931e0a24f0)
  eligibility/cells_0p1deg_wind   (declared against 74931e0a24f0)
  eligibility/cells_solar__central   (declared against 74931e0a24f0)
  eligibility/cells_solar__permissive   (declared against 74931e0a24f0)
  eligibility/cells_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/cells_wind__central   (declared against 74931e0a24f0)
  eligibility/cells_wind__permissive   (declared against 74931e0a24f0)
  eligibility/cells_wind__restrictive   (declared against 74931e0a24f0)
  eligibility/dominant_exclusion_solar   (declared against 74931e0a24f0)
  eligibility/dominant_exclusion_wind   (declared against 74931e0a24f0)
  eligibility/eligible_area_km2_solar   (declared against 74931e0a24f0)
  eligibility/eligible_area_km2_wind   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar__permissive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_solar__restrictive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind__permissive   (declared against 74931e0a24f0)
  eligibility/eligible_fraction_wind__restrictive   (declared against 74931e0a24f0)
  ensemble_solar__central   (declared against 74931e0a24f0)
  ensemble_solar__permissive   (declared against 74931e0a24f0)
  ensemble_solar__restrictive   (declared against 74931e0a24f0)
  ensemble_wind__central   (declared against 74931e0a24f0)
  ensemble_wind__permissive   (declared against 74931e0a24f0)
  ensemble_wind__restrictive   (declared against 74931e0a24f0)
  forcing   (declared against 74931e0a24f0)
  forcing_masked   (declared against 74931e0a24f0)
  hazard_context   (declared against 74931e0a24f0)
  land_eligibility   (declared against 74931e0a24f0)
  members   (declared against 74931e0a24f0)
  overview   (declared against 74931e0a24f0)
  potential_aggregates_solar   (declared against 74931e0a24f0)
  potential_aggregates_wind   (declared against 74931e0a24f0)
  potential_density_solar   (declared against 74931e0a24f0)
  potential_density_wind   (declared against 74931e0a24f0)
  potential_maps   (declared against 74931e0a24f0)
  potential_solar__central   (declared against 74931e0a24f0)
  potential_solar__permissive   (declared against 74931e0a24f0)
  potential_solar__restrictive   (declared against 74931e0a24f0)
  potential_wind__central   (declared against 74931e0a24f0)
  potential_wind__permissive   (declared against 74931e0a24f0)
  potential_wind__restrictive   (declared against 74931e0a24f0)
  technical_potential   (declared against 74931e0a24f0)
PRT: the reference is now 9c2dc3c88f93a3f8a09471877365c136cf3dafa5ce7560dd874a9a1585156c20; these entries were declared against another one and can be removed:
  aligned/slope   (declared against 3a1b06e04c67)
  aligned/slope_counts   (declared against 3a1b06e04c67)
  aligned_rasters   (declared against 3a1b06e04c67)
  capacity_factor_solar   (declared against 3a1b06e04c67)
  capacity_factor_wind   (declared against 3a1b06e04c67)
  class_flag_wind__central   (declared against 3a1b06e04c67)
  class_flag_wind__permissive   (declared against 3a1b06e04c67)
  class_flag_wind__restrictive   (declared against 3a1b06e04c67)
  climate_maps   (declared against 3a1b06e04c67)
  eligibility/admin1_units   (declared against 3a1b06e04c67)
  eligibility/candidate_stability_solar   (declared against 3a1b06e04c67)
  eligibility/candidate_stability_wind   (declared against 3a1b06e04c67)
  eligibility/candidates_solar__central   (declared against 3a1b06e04c67)
  eligibility/candidates_solar__permissive   (declared against 3a1b06e04c67)
  eligibility/candidates_solar__restrictive   (declared against 3a1b06e04c67)
  eligibility/candidates_wind__central   (declared against 3a1b06e04c67)
  eligibility/candidates_wind__permissive   (declared against 3a1b06e04c67)
  eligibility/candidates_wind__restrictive   (declared against 3a1b06e04c67)
  eligibility/cells_0p1deg_solar   (declared against 3a1b06e04c67)
  eligibility/cells_0p1deg_wind   (declared against 3a1b06e04c67)
  eligibility/cells_solar__central   (declared against 3a1b06e04c67)
  eligibility/cells_solar__permissive   (declared against 3a1b06e04c67)
  eligibility/cells_solar__restrictive   (declared against 3a1b06e04c67)
  eligibility/cells_wind__central   (declared against 3a1b06e04c67)
  eligibility/cells_wind__permissive   (declared against 3a1b06e04c67)
  eligibility/cells_wind__restrictive   (declared against 3a1b06e04c67)
  eligibility/dominant_exclusion_solar   (declared against 3a1b06e04c67)
  eligibility/dominant_exclusion_wind   (declared against 3a1b06e04c67)
  eligibility/eligible_area_km2_solar   (declared against 3a1b06e04c67)
  eligibility/eligible_area_km2_wind   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_solar   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_solar__permissive   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_solar__restrictive   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_wind   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_wind__permissive   (declared against 3a1b06e04c67)
  eligibility/eligible_fraction_wind__restrictive   (declared against 3a1b06e04c67)
  ensemble_solar__central   (declared against 3a1b06e04c67)
  ensemble_solar__permissive   (declared against 3a1b06e04c67)
  ensemble_solar__restrictive   (declared against 3a1b06e04c67)
  ensemble_wind__central   (declared against 3a1b06e04c67)
  ensemble_wind__permissive   (declared against 3a1b06e04c67)
  ensemble_wind__restrictive   (declared against 3a1b06e04c67)
  forcing   (declared against 3a1b06e04c67)
  forcing_masked   (declared against 3a1b06e04c67)
  hazard_context   (declared against 3a1b06e04c67)
  land_eligibility   (declared against 3a1b06e04c67)
  members   (declared against 3a1b06e04c67)
  overview   (declared against 3a1b06e04c67)
  potential_aggregates_solar   (declared against 3a1b06e04c67)
  potential_aggregates_wind   (declared against 3a1b06e04c67)
  potential_density_solar   (declared against 3a1b06e04c67)
  potential_density_wind   (declared against 3a1b06e04c67)
  potential_maps   (declared against 3a1b06e04c67)
  potential_solar__central   (declared against 3a1b06e04c67)
  potential_solar__permissive   (declared against 3a1b06e04c67)
  potential_solar__restrictive   (declared against 3a1b06e04c67)
  potential_wind__central   (declared against 3a1b06e04c67)
  potential_wind__permissive   (declared against 3a1b06e04c67)
  potential_wind__restrictive   (declared against 3a1b06e04c67)
  technical_potential   (declared against 3a1b06e04c67)
```

### A4. Full suite at HEAD 1975a0f, nothing in parallel

`python -m pytest -q -p no:cacheprovider`: **2379 passed, 0 failed, 0 skipped** (1,959 warnings), 2,333 s (38 min 53 s). `git status` afterwards: only the untracked `docs/thesis/cap1_introduction.tex` (not to be committed) and this report.

## Part B: REN source (updated 2026-11-08, after the per-concelho attempt)

Working folder: `GeoFREA_data\work\ren_probe\` (holds only `log.jsonl`; no REN feature was obtained). The probe script lives outside the repository. Limits used: 180 s per request, 3 attempts with waits of 20 and 60 s, 90 min total.

### B0. Peak memory of the F3 of BRA in round 9c2dc3c8

**1,243 MB** (phase `land_eligibility`, 578 s, `outputs/BRA/unattended_check.json`, round started 2026-11-06 20:07; the unattended runner's per-phase peak, not a per-process guard log). The earlier 1,438 MB of `memory_budget.json` is the COMMAND 91 measurement. `memory_budget.json` was not edited.

### B5. Official source

| item | value |
|---|---|
| publisher | Direcao-Geral do Territorio (DGT), SNIT/SRUP |
| national WFS | `https://servicos.dgterritorio.pt/SDISNITWFSSRUP_REN_PT1/WFService.aspx`, layers `gmgml:REN_Nacional` (polygons) and `gmgml:Linhas_de_Agua`; CRS EPSG:3763 (also 4326, 4258, 3857); `updateSequence=45` |
| regional WFS (same record) | `.../SDISNITWFSSRUP_REN_NORTE`, `_CENTRO`, `_LVT`, `_ALENTEJO`, `_ALGARVE` `/WFService.aspx`; WMS: `.../SDISNITWMSSRUP_REN_PT1/WMService.aspx` |
| SNIG record | "SRUP - Reserva Ecologica Nacional", id `ad95b02a-fbd2-4b8e-89b6-f699a9ff3c0d`, read through the SNIG CSW (`https://snig.dgterritorio.gov.pt/rndg/srv/por/csw`, GetRecordById, ISO 19139) |
| attributes | ID, SERVIDAO, REGIAO, DTCC, CONCELHO, TIPOLOGIA, DINAMICA, DESIGNACAO, ORIGEM_REN, DEPOSITO, LEI_TIPO, SERV_LEI, SERV_DR, SERV_HIPERLINK, TUTELA, GEOMETRIA_AUTOR, GEOMETRIA_RIGOR, GEOMETRIA_DATA, AREA_HA, IDESTADO |

### B5b. Licence and date (B5 of this command: obtained from the SNIG record)

- **Licence:** "regime de dados abertos, ao abrigo da licenca Creative Commons Attribution 4.0 International (CC BY 4.0)": reuse, adaptation and reproduction allowed with attribution to DGT and the licence. The same constraint text adds that SNIT information is for consultation and viewing, its commercialisation is prohibited, and printouts are not for administrative procedures unless the responsible authority allows it; incorporation in published documents must cite the associated legal acts. The wording "commercialisation is prohibited" sits beside CC BY 4.0 in the same field and is not reconciled by DGT; it is relevant to the commercial-platform question of OQ-072 and is for the author to read. Access constraint code: `otherRestrictions`.
- **Dates in the record:** series creation 2021-01-04 and 2021-03-22; publication 2008-06-01 and 2021-03-11; metadata date stamp 2026-06-22. Maintenance frequency: not given. These are series dates, not the date of the content of each concelho (`GEOMETRIA_DATA`, unreadable below). The currency of the vector is therefore **not obtained**.
- DGT's own SRUP overlay tool warns that the vector data do not replace the image delimitations published in the Diario da Republica (search result, not fetched).

### B2, B3. Per-concelho download: nothing obtained

| step | attempts | result |
|---|---|---|
| `resultType=hits` for the whole layer | 3 x 180 s | timeout (log 17:16) |
| `GetPropertyValue CONCELHO` (distinct values) | 3 x 180 s | timeout (log 17:27) |
| capabilities of the national service, the five regional services and the WMS | 1 x 40-60 s each | no answer from 17:28 on, although the national capabilities answered at the start of the session |
| availability check of the national capabilities, every 150 s | 8 checks, 17:29-17:51 | HTTP 000 (no connection) in all of them |

Without the list of CONCELHO values from the service, and with the whole `servicos.dgterritorio.pt` host not answering, no per-concelho request or 0.25 degree tile was sent: it would only repeat the same timeouts. In the earlier session, requests that matched features also failed (timeouts and HTTP 502) while one that matched nothing answered in 12 s, so the service already failed on any payload before it stopped answering altogether. The host `www.dgterritorio.gov.pt` still answered (HTTP 302), so the problem is the services host, or a block of this IP after the retries; the report cannot tell which.

### B4. Other official channels

- **SNIG CSW** (works): the metadata record above, and 249 other records whose title contains "Reserva Ecologica Nacional" (municipal PDM charts, "Carta da Reserva Ecologica Nacional - <concelho>" and similar). Those are other products, not downloaded.
- **dados.gov.pt:** a web search found no national REN dataset (only a Cascais PDM REN layer); not confirmed by browsing the portal.
- **DGT download service / SNIT SRUP page:** the record lists the WFS and WMS above and no file download URL. The DGT PDF "Manual WFS" and `snit-mais.dgterritorio.gov.pt/PortalSobreposicoes` exist but were not queried for a bulk file.
- Regional bodies (CCDR Centro via IDECENTRO) publish REN maps regionally: not official national archive of this record, not used.

### B6, B7. Coverage, area, IDESTADO, overlap: not measured

No feature was read. Not measured, with no estimate: municipalities with REN against the CAOP list (CAOP not fetched, there is no vector to compare), municipalities without a feature, whether `IDESTADO` separates included from excluded REN areas, dissolved REN area and share of mainland territory, overlap with the PRT restrictive eligible area (solar 7,113 km2, wind 20,300 km2). Obtained: none; missing: all concelhos (list of names unavailable from the service).

### B8. Open decision, awaiting the author's verdict

The REN vector could not be audited. Options, none decided or implemented:

1. Retry the per-concelho download when the DGT services host answers again (the script and limits are ready; the unit of resume is the concelho).
2. Ask DGT for a bulk copy (the record points to `https://www.dgterritorio.gov.pt` for contact), then audit it.
3. Use a partial vector with the limitation declared, if coverage turns out incomplete.
4. Exclude the REN from the PRT restrictive scenario and declare it in the text.

Before 1 or 2 is chosen, the licence question above (CC BY 4.0 together with "commercialisation prohibited") bears on any use of the REN in a commercial platform.

Until then the PRT restrictive eligible area is not reduced by the REN. No pipeline code, configuration or decision record was changed.

## Part C: stage 1 of COMMAND 104 (one more attempt, verdict of the author)

Path followed: **B (REN unavailable)**. The author's verdict: one more attempt; if the REN does not come complete, exclude it from the PRT restrictive scenario and declare it; a partial vector is discarded.

| step | time (2026-11-08) | result |
|---|---|---|
| GetCapabilities of the national WFS | 18:02 | HTTP 200 in 10.7 s |
| `resultType=hits`, `gmgml:REN_Nacional`, attempt 1 of 3 (120 s) | 18:02-18:04 | timeout, 0 bytes (HTTP 000) |
| attempt 2 of 3, after 10 min | 18:16 | timeout at 120 s, 0 bytes |
| attempt 3 of 3, after 10 min | 18:28 | timeout at 120 s, 0 bytes |

The global count did not answer in three attempts, so the per-concelho acquisition (item 2) and the CAOP comparison (item 3) were not started: no REN file was written (`GeoFREA_data\work\ren_probe\` holds only the log of the earlier session), nothing in `database\raw`. Not measured: REN area, share of mainland, IDESTADO, overlap with the PRT restrictive eligible area (PV 7,113 km2, wind 20,300 km2).

Records written for path B: D-F3-030 (`docs/phases/F3_land_eligibility.md`), L-065 (`docs/LIMITATIONS.md`), METHODOLOGY 18.0.1 (PATCH: a scope exclusion is recorded, no result definition changes, because the REN was never applied). Corrections of path-independent records: D-F3-029 (wind in the restrictive scenario; permissive PRT solar 19,527 km2), the 180 expired `expected` entries removed (`scripts/list_expired_expected.py` exits 0), `memory_budget.json` (`f3_phase_fabdem_round` 1,243 MB beside the 1,438 MB of `f3_phase`), OQ-072 widened (FABDEM CC BY-NC-SA 4.0; REN CC BY 4.0 with the commercialisation clause). Open items A1-A3 of Part A are closed by these records.
