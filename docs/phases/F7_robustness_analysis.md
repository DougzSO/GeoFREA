# F7 robustness_analysis

Status: `not_started`
Methodology items: M-F7-01 to M-F7-11, V-03

## Contract

Requires: F6 artifacts and kernel, `potential_<tech>.parquet`, `forcing.parquet`, `hazard_context.parquet`, admin1 boundaries. Produces: `robustness_<tech>.parquet`, hypothesis test tables, PRIM boxes.

## Conformance

| Item | Requirement | Implementation (module:function) | Test | Status |
|---|---|---|---|---|

## Active implementation decisions

Recorded before any code (Douglas's verdicts, 2026-10-08, METHODOLOGY 7.0.0):

- **D-F7-001 — Relative regret and the primary metric (V3; M-F7-02, M-F7-03, V-03).** `r = (LCOE - L*) / L*`. `MR_i` = maximum over climate members of the P90 over parameter samples of `r`. Order: `r` per future `(m, s)`; P90 over samples per member; maximum over members. SR stays secondary. The F7 candidates are the central-set candidates (V1).
- **D-F7-002 — H4 comparison (V4; M-F7-06).** The Jaccard comparison of climate-only versus techno-only futures is primary; the variance decomposition, on relative LCOE, is secondary.
- **D-F7-003 — Feasibility and climate-fragile cells (V9; M-F7-01).** A cell with CF below `CF_min` in the nominal future leaves the F7 set. A cell feasible in the nominal future and infeasible in some member forms the class "climate-fragile", reported separately and not ranked with an infinite MR. `CF_min` is OQ-008. Open point for Douglas: because `gamma` and `eta_loss` are sampled, feasibility is evaluated per future; the text reads "infeasible in at least one future of some member".

## Known issues

None yet.

## History

None.
