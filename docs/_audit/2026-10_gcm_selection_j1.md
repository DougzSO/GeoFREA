# J-1 — GCM selection (M-F4-02), evidence for OQ-009

Date: 2026-10-06. Status: **awaiting verdict** (nothing acquired, `members.yaml` not written).
Inputs: CDS catalogue constraints for `projections-cmip6` (public, read 2026-10-06), the on-disk CMIP6 crops
for GFDL-ESM4 and MIROC6 (F3-2), Nijsse et al. 2020 (ESD 11, 737) Table 1 for TCR.

## Criterion 1 — availability (resource channel)

Scope note: the resource channel needs `rsds`, `tas`, `sfcWind` monthly (M-F1-04, D-F4-001). `tasmax`/`pr` daily
belong to the hazard channel, which is ISIMIP3b (copied, OQ-036), so they are **not** a CDS availability
requirement (the J-1 command text in the playbook listed them; D-F4-001 supersedes it).

Test: for each of the 58 CDS models, all of `historical` 1995-2014 and `ssp1_2_6`, `ssp3_7_0`, `ssp5_8_5`
2041-2100 listed in the constraints for all three variables. Result: **22 of 58 pass**:

access_cm2, awi_cm_1_1_mr, bcc_csm2_mr, canesm5_canoe, cesm2, cmcc_cm2_sr5, cnrm_cm6_1, cnrm_cm6_1_hr,
cnrm_esm2_1, fgoals_f3_l, fgoals_g3, gfdl_esm4, inm_cm4_8, inm_cm5_0, ipsl_cm6a_lr, miroc6, miroc_es2l,
mpi_esm1_2_lr, mri_esm2_0, noresm2_mm, taiesm1, ukesm1_0_ll.

Notable absences: `mpi_esm1_2_hr` (an ISIMIP3b primary model) and `canesm5` do not pass on the CDS for this set.
Limitation: the CDS constraints do not expose the variant label, so the "one common realization" part of the
criterion can only be verified at download (the F3-2 acquisition already records and checks `realization`);
GFDL-ESM4 and MIROC6 are `r1i1p1f1` for every variable/experiment.

## Criterion 2 — TCR against the AR6 likely range (1.4-2.2 K)

Source: IPCC AR6 WGI, Table 7.SM.5 (CMIP6 TCR from Schlund et al. 2020, Meehl et al. 2020, Zelinka et al. 2020),
supplied by Douglas in `D:\Douglas\DOUTORADO\AR6.md` on 2026-10-06 (this replaces the earlier Nijsse et al. 2020
screening, which covered only part of the models). Range used: 1.4-2.2 K, the AR6 *likely* TCR range. AR6 WGI Chapter 7 assesses TCR at a best estimate of 1.8 K, likely range 1.4-2.2 K, very likely 1.2-2.4 K, and Hausfather et al. (2022) screen CMIP6 models on the *likely* range. Confirmed on 2026-10-06 through secondary sources reporting those AR6 numbers (Hausfather et al. 2022 as cited in Carbon Brief's guest post and in the Journal of Climate 2024 hot-model study); the IPCC page itself returned HTTP 403 and the primary Chapter 7 text was not read, so the exact AR6 section number is unverified.

Models that pass criterion 1 (22), with Table 7.SM.5 TCR:

| Model | TCR (K) | Verdict (1.4-2.2) |
|---|---|---|
| FGOALS-g3 | 1.54 | pass |
| MIROC-ES2L | 1.55 | pass |
| MIROC6 | 1.55 | pass |
| MRI-ESM2-0 | 1.64 | pass |
| BCC-CSM2-MR | 1.72 | pass |
| MPI-ESM1-2-LR | 1.84 | pass |
| CNRM-ESM2-1 | 1.86 | pass |
| FGOALS-f3-L | 1.94 | pass |
| CESM2 | 2.06 | pass |
| AWI-CM-1-1-MR | 2.06 | pass |
| CMCC-CM2-SR5 | 2.09 | pass |
| ACCESS-CM2 | 2.10 | pass |
| CNRM-CM6-1 | 2.14 | pass |
| IPSL-CM6A-LR | 2.32 | **out (hot)**; inside the AR6 *very likely* 1.2-2.4 |
| TaiESM1 | 2.34 | **out (hot)**; inside 1.2-2.4 |
| CNRM-CM6-1-HR | 2.48 | **out (hot)** |
| UKESM1-0-LL | 2.79 | **out (hot)** |
| INM-CM4-8 | 1.33 | **out (cold)**; inside 1.2-2.4 |
| NorESM2-MM | 1.33 | **out (cold)**; inside 1.2-2.4 |
| GFDL-ESM4 | **NA** | not assessable: Table 7.SM.5 has no ECS or TCR for GFDL-ESM4 (only a feedback decomposition) |
| INM-CM5-0 | NA | not assessable (TCR NA) |
| CanESM5-CanOE | not in table | not assessable (parent CanESM5: 2.74, hot) |

Consequences:
- 13 models pass criteria 1 and 2 outright; 6 are screened out (CNRM-CM6-1-HR, INM-CM4-8, IPSL-CM6A-LR, NorESM2-MM,
  TaiESM1, UKESM1-0-LL); 3 cannot be screened for lack of a TCR (GFDL-ESM4, INM-CM5-0, CanESM5-CanOE).
- **GFDL-ESM4 has no TCR in the AR6 table.** S-04 requires it unless it fails criterion 1 or 2; it passes 1 and cannot
  be failed on 2, so it stays (criterion 4). An earlier "~1.6 K" figure came from a secondary web summary and is not
  supported by the table; it should not be quoted.
- IPSL-CM6A-LR (an ISIMIP3b model, so the only way to a third dual-channel member besides GFDL-ESM4 and MRI-ESM2-0)
  fails the *likely* range by 0.12 K but passes the *very likely* range. It is acquired as a borderline candidate; keeping
  it is a methodological call for Douglas (a narrower range is what M-F4-02 asks for).

## Criterion 3 — change-factor spread (only partly computable now)

Only GFDL-ESM4 and MIROC6 are on disk, so the spread across a candidate set cannot be computed without
acquiring more data (this command does not acquire; acquisition is J-2, which in turn waits for this verdict).
Diagnostic for the two models, SSP3-7.0, 2041-2070 against 1995-2014, M-F4-03 formulas, mean over in-polygon
cells (unweighted), PRT mainland-only crop:

| Country | Model | delta_rsds | delta_wind | dT (K) |
|---|---|---|---|---|
| BRA | GFDL-ESM4 | 1.0047 | 1.0745 | 1.710 |
| BRA | MIROC6 | 1.0142 | 1.0744 | 1.568 |
| PRT | GFDL-ESM4 | 1.0163 | 0.9871 | 1.473 |
| PRT | MIROC6 | 1.0369 | 0.9734 | 1.340 |
| IND | GFDL-ESM4 | 0.9369 | 0.9839 | 1.267 |
| IND | MIROC6 | 0.9695 | 1.0275 | 1.154 |

These are selection diagnostics, not F4's production change factors (no bilinear interpolation, no area weighting).
The BRA `delta_wind` of +7.4/+7.5% in both models is large for a near-surface wind change and should be checked
when the production change factors are built (J-3).

## Criterion 4 — mandatory models

MIROC6 (TCR 1.55) passes 1 and 2. GFDL-ESM4 passes 1 and has no TCR to screen on (see above). Both stay (S-04).

## Proposal and what was done (for verdict, not a decision)

Douglas agreed (2026-10-06) to acquire every model that can contribute to the methodology. J-2's acquisition was
launched for GFDL-ESM4 and MIROC6 (already on disk) plus the 12 models that pass criteria 1 and 2 (MRI-ESM2-0,
CNRM-CM6-1, CESM2, BCC-CSM2-MR, ACCESS-CM2, AWI-CM-1-1-MR, CMCC-CM2-SR5, CNRM-ESM2-1, FGOALS-f3-L, FGOALS-g3,
MIROC-ES2L, MPI-ESM1-2-LR) and IPSL-CM6A-LR as a borderline. The final 4-6 members are chosen from the criterion-3
spread over that downloaded set, in a follow-up step that still needs Douglas's verdict. Hazard-channel coverage
follows D-F4-003: only GFDL-ESM4, MRI-ESM2-0 and (if kept) IPSL-CM6A-LR have an ISIMIP3b counterpart; MPI-ESM1-2-HR,
the ISIMIP3b model, is not available on the CDS for this variable set (MPI-ESM1-2-LR is its sibling).
