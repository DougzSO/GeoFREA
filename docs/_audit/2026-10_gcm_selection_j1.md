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

**Provenance gap, stated plainly:** the authoritative per-model source named by M-F4-02 (IPCC AR6 Table 7.SM.5,
or Hausfather et al. 2022) could not be retrieved in this session (PMC pages blocked by a CAPTCHA, supplement not
reachable). The values below are Gregory-method TCR from Nijsse et al. 2020 Table 1, which covers only part of the
catalogue. They are for screening orientation and should be checked against AR6 Table 7.SM.5 before the verdict.

| Model | TCR (K) | In 1.4-2.2? | Source |
|---|---|---|---|
| MIROC6 | 1.52 | yes | Nijsse et al. 2020 T1 |
| MRI-ESM2-0 | 1.56 | yes | Nijsse et al. 2020 T1 |
| BCC-CSM2-MR | 1.59 | yes | Nijsse et al. 2020 T1 |
| CNRM-ESM2-1 | 1.92 | yes | Nijsse et al. 2020 T1 |
| CNRM-CM6-1 | 2.08 | yes | Nijsse et al. 2020 T1 |
| CESM2 | 2.08 | yes | Nijsse et al. 2020 T1 |
| IPSL-CM6A-LR | 2.32 | **no (hot)** | Nijsse et al. 2020 T1 |
| UKESM1-0-LL | 2.72 | **no (hot)** | Nijsse et al. 2020 T1 |
| CanESM5 | 2.66 | **no (hot)** | Nijsse et al. 2020 T1 (also fails criterion 1) |
| GFDL-ESM4 | ~1.6 | yes | secondary (web search summary of AR6/Hausfather); not in Nijsse T1 (only GFDL-CM4 is) |
| NorESM2-MM, MPI-ESM1-2-LR, INM-CM4-8, INM-CM5-0, FGOALS-g3, TaiESM1, ACCESS-CM2, others | not retrieved | unknown | needs AR6 Table 7.SM.5 |

Effect of criterion 2 where evidence exists: IPSL-CM6A-LR and UKESM1-0-LL (two of the five ISIMIP3b primary
models) are screened out as hot models; CanESM5 too.

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

GFDL-ESM4 and MIROC6 pass criterion 1; both are inside the TCR likely range (MIROC6 1.52 measured, GFDL-ESM4 ~1.6
from a secondary source). Both stay (S-04).

## Proposal (for verdict, not a decision)

Six candidates to acquire in J-2, all passing criterion 1 and, where a value exists, criterion 2:
**GFDL-ESM4, MIROC6** (fixed), **MRI-ESM2-0** (also has an ISIMIP3b hazard counterpart), **CNRM-CM6-1**,
**CESM2**, **BCC-CSM2-MR**. Final 4-6 chosen after J-2, from the criterion-3 spread over the downloaded set; a
candidate whose AR6 TCR turns out to be outside 1.4-2.2 K is dropped. Hazard-channel coverage follows D-F4-003:
only GFDL-ESM4 and MRI-ESM2-0 would carry both channels (IPSL-CM6A-LR, MPI-ESM1-2-HR and UKESM1-0-LL are not
usable: hot or unavailable); the other members would be resource-only.
