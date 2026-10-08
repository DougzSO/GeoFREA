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
- **D-F7-003 — Feasibility and climate-fragile cells (V9; verdict B of 2026-10-08; M-F7-01, M-F7-02).** A cell with CF below `CF_min` in the nominal future `(m0, s0)` leaves the F7 set. Climate-fragile = feasible in `(m0, s0)` and `CF(m, s0) < CF_min` in at least one member `m`: feasibility that defines the class is evaluated at the nominal parameters `s0` of each member. It is reported separately and not ranked with an infinite MR. Infeasibility that comes only from the parameter samples does not create the class and gives no infinite regret: within the P90 over samples, an infeasible sample receives the regret of the feasible cell with the highest LCOE in that future (finite worst case). `CF_min` is OQ-008.
- **D-F7-004 — One threshold for satisficing and economic potential (verdict A of 2026-10-08, METHODOLOGY 7.0.1).** OQ-052 (cost threshold of economic potential, T-R12, H5) is merged into OQ-008: the LCOE threshold below which potential counts as economic is the satisficing threshold `tau` of M-F7-04, per country and technology.

## Known issues

None yet.

## History

None.
