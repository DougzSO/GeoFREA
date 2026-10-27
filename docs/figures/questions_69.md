# Figures for the questions of the thesis (COMMAND 69)

Written for Douglas. Spec v2 T-15, items 1 to 4; item 5 (external validation) waits for F7b and the version of item 1 against the LCOE waits for F6. The rules and the reading of each figure are in `docs/figures/style_guide.md` (section COMMAND 69); the record of the decision is D-F5-034.

## What the pipeline now draws

Per country, in `outputs/<ISO3>/technical_potential/figures/`, by the phase `potential_maps` (`figures: all`), registered as its artifacts and marked `status = thesis` in the PNG:

| Item | Files per country | Count |
|---|---|---|
| 1 Supply curves against the capacity factor | `<ISO3>_F5_supply-curve-{capacity,energy}_<tech>_land-scenarios_ref.png` | 4 |
| 3 Interval of land availability | `<ISO3>_F5_land-availability_land-scenarios_ref.png` | 1 |
| 4 Change by SSP and window, map | `<ISO3>_F5_change-capacity-factor_<tech>_central_ssp-window.png` | 2 |
| 4 Change by SSP and window, total | `<ISO3>_F5_change-energy_central_ssp-window.png` | 1 |

Across the countries, in `outputs/comparison/figures/`, drawn by `main.py` after the countries of a run (item 2): `ALL_F5_comparison_<tech>_land-scenarios_ref.png` and `ALL_F5_supply-curve-per-area_<tech>_land-scenarios_ref.png`, 4 files for the two technologies. The comparison reads the tables of every country that has them; one country alone draws nothing.

The folder of F5 of each country now has 22 PNG files (14 of COMMAND 68 and the 8 new ones), and `potential_maps` registers 27 artifacts.

## How it was run

`main.py <ISO3> --phases potential_maps` for PRT, IND and BRA, one at a time. The content hashes of the manifest (D-core-042; the file of byte hashes `run_real_hashes.json` was removed on 2026-10-27) are unchanged after the three runs (no number was touched). Time of the phase `potential_maps` in the last run: PRT 88 s, IND 264 s, BRA 313 s.

## What the first figures show (PRT, read from the figures)

- Wind in PRT: the cumulative capacity is 2.9 GW in the restrictive, 21.0 GW in the central and 75.2 GW in the permissive land scenario; the three curves rise between the capacity factors 0.4 and 0.2, so the land scenario changes the total much more than any cut of the capacity factor would.
- The change of the national energy by SSP and window has the opposite sign for the two technologies in PRT (wind falls, solar rises) and a range between GCMs that crosses zero in most scenarios of wind: the dots of the map mark the cells where fewer than 2/3 of the GCMs agree on the sign.
- The comparison puts BRA, PRT and IND on the same axes, per area of the cells of the country, with the same capacity-factor axis.

Other numbers are in the figures and in the legend of each curve; none of them was changed or recomputed by this work.

## Limits

- The comparison uses the central land scenario for the change of the energy; the other scenarios are not drawn there.
- The map of the change is of the capacity factor (equal to the change of the energy of a cell); a map of the change of the capacity in MW does not exist because capacity does not depend on the climate member.
- The `ALL` code in the name of a comparison is a convention of the file name (the code of three countries); the metadata lists the countries.
