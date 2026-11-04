# Members per cell and technology, and the wind members that BRA lacks (COMMAND 95, item 1)

Source: `forcing.parquet`, `forcing_masked.parquet` and `members.yaml` of F4 in the three countries, and the F5 potential tables, as they are on disk after the round of 2026-11-04 (`scratchpad/members_map.py`). The ensemble has 37 members: `m0` (reference climatology) and 6 GCMs x 3 scenarios x 2 windows.

## How many members each cell has

| Country | Cells | Solar (rsds, tas) | Wind |
|---|---|---|---|
| PRT | 3,939 | 37 in every cell | **31 in every cell** |
| IND | 112,948 | 37 in every cell | **31 in every cell** |
| BRA | 286,043 | 37 in every cell | 31 in 256,648 cells (89.7%); 30 in 20,057; 29 in 6,753; 28 in 1,542; 27 in 667; 26 in 166; 25 in 210 |

The wind candidate cells of BRA (F3 central, 181,306): 31 members in 173,870, 30 in 6,471, 29 in 882, 28 in 81, 27 in 2 (the same as the F5 table `potential_wind__central`: 7,436 cells, 4.1%, have fewer than 31).

## What is missing, and why: two causes, both rules of the methodology and neither a failure

1. **MIROC6 has no wind member, in the three countries (6 of 37; 31 of 37 remain).** Decision D-F4-021 (V-B1, 2026-10-14, METHODOLOGY M-F4-02 item 6): the 1995-2014 mean 10 m wind of MIROC6 over Brazil is below 0.5 m/s in 50.3% of its native land cells. `members.yaml` declares `resource_wind: false` and `wind_channel_exception: true` for its six members. This is why wind is 31 everywhere and not 37.
2. **BRA only: 42,947 cell-members of 7 members are masked** because `delta_wind` is above the upper bound of `wind_factor_valid_range` (0.5 to 1.5), METHODOLOGY M-F4-07 (OQ-042 option C, Douglas's verdict). They are listed in `forcing_masked.parquet`, their `delta_wind` is NaN in `forcing.parquet` and so they are absent from the wind potential. All the masked values are above 1.5 (1.5000 to 1.863, median 1.547); none is below 0.5. PRT and IND have no masked cell-member (their `delta_wind` of the members that have wind stays in 0.93 to 1.05 in PRT and 0.60 to 1.13 in IND; BRA reaches 0.81 to 1.86).

| Member (BRA) | Cells where it is missing | Largest `delta_wind` |
|---|---|---|
| IPSL-CM6A-LR SSP5-8.5 2071-2100 | 17,802 | 1.630 |
| GFDL-ESM4 SSP5-8.5 2071-2100 | 12,230 | 1.863 |
| GFDL-ESM4 SSP3-7.0 2071-2100 | 9,447 | 1.805 |
| GFDL-ESM4 SSP5-8.5 2041-2070 | 1,285 | 1.604 |
| GFDL-ESM4 SSP1-2.6 2071-2100 | 1,164 | 1.609 |
| GFDL-ESM4 SSP3-7.0 2041-2070 | 778 | 1.586 |
| GFDL-ESM4 SSP1-2.6 2041-2070 | 241 | 1.546 |

(The counts are the same as those of 2026-10-07 in D-F4-018: 25,145 for GFDL-ESM4 and 17,802 for IPSL-CM6A-LR; the MIROC6 part, 103,864, left with D-F4-021.)

## Where

`bra_wind_members_map.png`: 29,395 cells (10.3% of BRA) lose 1 to 6 members, in four blocks with sharp edges, all of them in the Amazon basin or its borders, plus one small block in Minas Gerais: the western Amazon near 69 W, 0 to 6 S (up to 6 members missing); the central Amazon, 52 to 58 W, 3 to 8 S (2 to 3 members); the north, near the border with Guyana and Suriname; and about 45 W, 17 to 19 S. The densest 5-degree box is 5 to 0 S, 60 to 55 W (8,631 cells). A block is a patch of the native grid of the GCM smoothed by the 3 x 3 neighbourhood (D-F4-014), not a ragged coastal edge: it is a model signal and not a missing value.

Candidate cells that lose members are low-wind cells: their mean capacity factor is 0.074 against 0.159 in the cells with 31 members; they hold **1.86% of the BRA wind capacity (30.6 of 1,643.5 GW) and 1.26% of the energy (32.3 of 2,574.4 TWh)** of the central scenario. *Correction (2026-11-04, real F5 run, COMMAND 97): measured in the reference member `m0`, the energy of these cells is 25.5 of 2,300.3 TWh/yr (1.11%); the 7,436 cells and the 30.6 GW agree.*

## Cause, against the four that were asked about

| Cause | Verdict |
|---|---|
| Grid of the GCM | Not the missing data: the blocks follow the native grid of GFDL-ESM4 and IPSL-CM6A-LR smoothed by the neighbourhood, but every cell has a value for every member; what is removed is the value, by rule |
| Coastal mask | No: the blocks are inland (the coast is not where the members are missing) |
| Absent value | No for the GCMs kept: `delta_wind` was computed in every cell and is masked afterwards (the values are in `forcing_masked.parquet`). Yes for MIROC6, by decision D-F4-021 |
| Failure of `climate_forcing` | No: the same counts as on 2026-10-07 (D-F4-018), and `forcing.parquet` has all 37 x 286,043 = 10,583,591 cell-member rows, with `delta_wind` NaN for the 6 x 286,043 of MIROC6 and the 42,947 masked ones (1,759,205 in all) |

So there is nothing to correct in the code. The open point is a rule of the analysis, below.

## Rules to choose from (not decided here)

The members of a cell are the futures that F6 and F7 aggregate (the quantiles, the ranking of futures, the robustness). A cell with 27 to 30 members is not compared like with like with a cell with 31.

- **A. Complete ensemble: a cell is analysed for wind only if it has all 31 members.** Removes 7,436 of the 181,306 BRA candidates (4.1%; 1.86% of the capacity) and nothing in PRT and IND. Simple, and the cell-level statistics are all on the same 31 futures. Cost: a hole in the Amazon of the BRA wind maps, and the cells with the most extreme wind change are the ones that go (a selection on the outcome).
- **B. Common ensemble in F7: the same members in every cell of every country.** The 7 members that miss cells are GFDL-ESM4 (6) and IPSL-CM6A-LR (1) in their later windows and higher scenarios, so dropping them everywhere leaves 24 wind members (m0 plus 23). Every cell and country is then on the same futures, nothing is removed, and the comparison between countries is clean. Cost: the highest-forcing futures of two GCMs disappear from PRT and IND, where they are valid, and the GCM balance changes (all 6 GFDL-ESM4 members would go, and with them one of the five GCMs that have wind).
- **C. Keep as it is and report with and without (the plan of OQ-043):** the cell keeps its available members, and F7 reports the result also with the complete-ensemble cells only (A) so the effect is shown. Nothing is lost, the cost is the unequal count that this note is about.
- **D. Move the bound of `wind_factor_valid_range`.** It has no source (OQ-043): measured with MIROC6 still in the ensemble (D-F4-018), BRA masked 1.0% of cell-members at 0.4 to 1.6 against 1.43% at 0.5 to 1.5. It changes the result, needs Douglas's verdict, and would not remove MIROC6.

Recommendation, for the author to take or leave: **B for the comparison between countries (F7) and C for the BRA maps**, because B is the only one that makes every country the same experiment, and its cost (24 of 31 members) can be reported with the effect of the dropped members measured on PRT and IND, where they exist. A is the simplest if F7 only needs a clean subset of BRA. No code or configuration was changed.
