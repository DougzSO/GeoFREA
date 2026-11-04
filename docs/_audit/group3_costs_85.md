# Group 3 pending costs: what was found and what was not (COMMAND 85, OQ-001, OQ-065, OQ-066)

Accessed 2026-11-02. Nothing here is estimated: each value has the URL, the date of access and the passage it comes from. Downloaded files are under `GEOFREA_DATA_DIR/external/` (`aneel_bpr/`, `acer/`, `ind_costs/`, `vth/`), never under `database/raw`.

## Table

| Item | Value | Unit | Price year | Source | Status in `parameters.json` |
|---|---|---|---|---|---|
| BRA bay (Entrada de Linha 138 kV, arrangement BPT) | 1,987,188 (range 1,884,382 BS to 2,061,514 BD5) | BRL per bay | 2017 (dominant index 6/2017; items 12/2011 and 5/2007 inside) | ANEEL BPR, dataset `bpr-banco-de-precos-de-referencia-subestacao` (CSV generated 2026-11-01) | `verify`: composition to confirm, see 1 |
| BRA line 138 kV single circuit, per km | not found | BRL/km | n/a | BPR line dataset has components only | `to_be_sourced` (F6 refuses, OQ-001) |
| IND line 220 kV single circuit | 1.10 (1.10 to 1.14) | INR crore/km | 2025 | CTUIL "Indicative Capital Cost of Dedicated Transmission Systems", Table 1 | `sourced` (confirmed) |
| IND bay 220 kV | not found | INR crore/bay | n/a | CTUIL document has no bay; TGTRANSCO 2025-26 cost data not reachable | `to_be_sourced` (F6 refuses, OQ-001) |
| PRT line 150 kV (ACER 220-225 kV, 1 circuit) | 0.362 (0.303 to 0.543) | MEUR/km | 2023 | ACER UIC report 2023, overhead lines table; p. 17 | `sourced` (OQ-066 closed) |
| PRT bay | 2.789 (2.116 to 4.300) | MEUR per substation upgrade | 2023 | ACER UIC report 2023, AC substations 0-5 bays, AIS Updated/Refurbished; p. 40 | `sourced`; unit is per station, see 4 |
| Access road, BRA / IND / PRT | not found (a paved-highway upper bound exists for BRA) | per km | n/a | see 3 | `road_cost_excluded: true` in the three countries; `road_cost_per_km` stays `to_be_sourced` |
| Sensitivity `road_cost_high`, BRA | 2,106,000 (to 3,082,000) | BRL/km | 2016 | DNIT Custos Medios Gerenciais, jan/2016 | `verify`; not the central case |
| V_th (BRA 138, IND 220, PRT 150 kV) | unchanged | kV | n/a | `vth_evidence_85.md` | `verified: false` until Douglas confirms |

## What F6 does now

- **PRT**: no item is missing. With the conversion indices in `GEOFREA_DATA_DIR` F6 can run, with the road not billed and a warning (the LCOE is a lower bound).
- **BRA**: refuses only for `line_cost_per_km` (OQ-001).
- **IND**: refuses only for `bay_cost` (OQ-001).

## 1. BRA: ANEEL BPR

- URL: https://dadosabertos.aneel.gov.br/dataset/bpr-banco-de-precos-de-referencia-subestacao and https://dadosabertos.aneel.gov.br/dataset/bpr-banco-de-precos-de-referencia-linha-de-transmissao (29 CSV of the line dataset and 4 of the substation dataset downloaded; list in `external/aneel_bpr/urls.txt`). Field dictionary (24-10-2024): "O Banco de Precos de Referencia da ANEEL e composto por unidades modulares de itens e equipamentos de subestacoes e linhas de transmissao" and the substation modules are "Modulo de Infraestrutura, Modulo de Manobra e Modulo de Equipamento".
- Module: `SigTipoModuloManobra = EL`, `NomTipoTensao = 138`, `DscTipoArranjo = BPT`: 45 rows. Sum of price x quantity: UAR items 1,389,043 + COM items 396,376 = 1,785,418 BRL. Infrastructure of switching (`item-infraestrutura-manobra.csv`, 138 kV, block of 9 items repeated once per arrangement): 201,770. Total BPT 1,987,188. Reproduce with `scripts/derive_bra_bay_cost_bpr.py` (result in `el138_modules.json`).
- Reference index: each item carries `IndiceReferencia`. For BPT: 6/2017 (29 items), 5/2017 (7), 12/2011 (8, the COM items), 5/2007 (1, quantity zero). `parameters.json` records 2017, the dominant index; it is not one date. The dataset gives no later correction index, so the BRL value is not brought to 2024 by the BPR itself; F6 uses the World Bank deflator of Brazil from 2017.
- Reading to confirm (why `verify`): that a bay is the sum of the UAR equipment, the COM minor components and the infrastructure module. Support: ANEEL's PRORET submodule 9.1 defines COM as minor components tied to the main equipment, and PRORET 9.7 adds a switching infrastructure module (MIM) to each new switching module (https://www2.aneel.gov.br/cedoc/aren2016754_Proret_Submod_9_1_V1.pdf and https://www2.aneel.gov.br/cedoc/aren2020880_Proret_Submod_9_7_V2.pdf; found by search, not read in full). Douglas can confirm with bpr@aneel.gov.br.
- Line per km, not found: the line dataset is a set of components (cable per km by region, steel structures by type, foundations, insulators, clearing). It has no table with the total per km of a 138 kV single-circuit line. Building one means choosing tower type, foundation, conductor and terrain, which are assumptions, so it was not built. The BRA line stays `to_be_sourced`. A web search for a published R$/km at 138 kV found only a 500 kV example and an environmental study with a total without length; none is usable.

## 2. IND: CTUIL and TGTRANSCO

- Line: https://www.ctuil.in/uploads/assets/176633158052Indicative Capital Cost.docx (Dec 2025 by the file stamp; document "Indicative Capital Cost of Dedicated Transmission Systems", notified under Regulation 5.11(g) of the CERC GNA Regulations 2022). Table 1: "220 kV S/c | Single Moose | 4 | 1.10" and "Single AL59 Zebra | 5 | 1.14", "Total Capital Cost/km including applicable T&D and excluding RoW (in Crore)". Text: "Route-length cost (Rs Cr/km) includes towers, foundations, conductors, fittings, erection, OPGW, logistics and contingency excluding RoW." This confirms the value already in `parameters.json`.
- Bay: the document has line costs (Table 1) and reactive-power equipment (Table 2) only; no bay. The TGTRANSCO document (https://www.tgtransco.com/it_uploads/2025-26_Costdata.pdf, approved 13.11.2025 and in force from 02.12.2025 according to a search result) could not be opened: the host timed out from this machine and the fetch tool failed. The IND bay stays `to_be_sourced`.
- Candidate, not used: CERC GNA Regulations 2022, Regulation 8.2(a), the Conn-BG2 bank guarantee per terminal bay: "132 kV Rs. 2 crore; 220/230 kV Rs. 3 crore; 400 kV Rs. 6 crore; 765 kV Rs. 12 crore" (https://thc.nic.in, Regulations 2022, p. 10, read by OCR of the scanned PDF). It is a security amount the applicant posts, not a capital cost, so it was not entered. If Douglas accepts it as a proxy it would be a 3 crore bay (2022 notification).
- Not usable either: a CTUIL OM with "single 220 kV line bay ... Total Estimated Cost Rs 5.94 crore" (search result, includes other works).

## 3. Access road

- ROCKS (World Bank): https://datacatalog.worldbank.org/search/dataset/0065670/road-costs-knowledge-system-rocks, CC BY 4.0, file `ROCKS Version 2.3.zip`, "last updated in 2008". Low and middle income countries only (Portugal is not covered), prices of 1990s-2000s: not downloaded as a source because it cannot serve the three countries and its dates are far from 2024.
- DNIT Custos Medios Gerenciais, base SICRO 2 jan/2016 (https://www.gov.br/dnit/pt-br/assuntos/planejamento-e-pesquisa/custos-referenciais/custo-medio-gerencial/ANEXOIXCUSTOMDIOGERENCIALJANEIRO2016N10.pdf; local copy `external/dnit/cmg_2016-01.pdf`): "IMPLANTACAO/PAVIMENTACAO (P.Simples) Faixa 3,6m e Acost. 2,5m: R$ 3.082.000,00 / km"; "Faixa 3,6m e Acost. 1,0m (ate Classe III): R$ 2.106.000,00 / km". The pairing of values and descriptions was checked in the PDF. It is a paved national highway benchmark from 2016, not a plant access road: kept only as the sensitivity `road_cost_high` for BRA.
- PMGSY (India): no official unit cost found. Indirect figures only (a state average of Rs 43.34 lakh/km in a Tamil Nadu order of unstated date; a quotient of sanction over length, which is arithmetic and not a published unit cost). Not entered.
- Portugal: nothing found.
- Result: no source serves the three countries on one basis, so `c_road` stays `null` and the central scenario is `road_cost_excluded` (road term zero, the LCOE is a lower bound, F6 logs a warning and the provenance records it). `road_cost_high` is defined for BRA only; IND and PRT have none.

## 4. PRT: ACER

- Report: https://www.acer.europa.eu/Reports/UIC_report_2023.pdf (local copy `external/acer/UIC_report_2023.pdf`, 81 pages; also https://www.acer.europa.eu/sites/default/files/documents/Publications/UIC_report_2023.pdf).
- Price year, p. 17, "Treatment of inflation": "all nominal values of the investments were adjusted for inflation, with 2023 as the base year". `price_year = 2023` for both items; OQ-066 is closed.
- Line, p. 31: "220 - 225 kV 1 circuit: mean 411 887, interquartile range 303 301 - 542 906, median 362 180, 7 assets, 2015-2021" (EUR/km). Matches `parameters.json`.
- Bay, p. 40: "AIS Updated / Refurbished: mean 3 401 125, interquartile range 2 116 075 - 4 300 494, median 2 789 344, 28 assets, 2014 - 2021", in the table of "AC substations with 0-5 bays", figure caption "million EUR/station". The indicator is per substation upgrade, not per bay. It was already read as the works at the receiving substation; the note in `parameters.json` says so. Flagged for Douglas: a per-bay figure would be lower.

## 5. V_th

See `docs/_audit/vth_evidence_85.md`. `verified` stays false.

## Update of COMMAND 86 (2026-11-02): decisions applied

| Item | Value | Unit | Price year | Source | Status |
|---|---|---|---|---|---|
| BRA line 138 kV | 598,332 (Q1 569,999; Q3 713,726) | BRL/km | 2024 (deflated) | median of 7 ANEEL modular costs applied in three EPE R1 studies, `bra_line_138_86.md` | `sourced`, Tier 2 |
| IND bay 220 kV | 3 (range 1.5 to 6) | INR crore | 2022 | CERC GNA Regulations 2022, Reg. 8.2(a), Conn-BG2 per 220/230 kV terminal bay | `proxy`, Tier 3: a bank guarantee, not a capital cost; the range is the author's |
| PRT bay | 2.789 (2.116 to 4.300) | MEUR per substation | 2023 | ACER UIC 2023 (kept), described as "connection works at receiving substation (ACER, per substation)" | `sourced` |
| Road, 3 countries | none; `road_cost_excluded` central | | | `road_distance_86.md`: median D_road 0.8 to 2.4 km, P90 2.4 to 9.0 km, 0 to 0.8 % of the eligible area beyond 30 km | scenario |
| `road_cost_high`, 3 countries | 631,096 (high 923,570) USD/km for IND and PRT; R$ 2,106,000 (high 3,082,000), 2016, for BRA | | 2024 USD / 2016 BRL | DNIT jan/2016 converted with the Brazilian deflator and the 2024 exchange rate | `proxy`, upper bound, Tier 3 for IND and PRT |
| V_th, 3 countries | 138, 220, 150 kV | | | `vth_evidence_85.md` (REN technical data 2024 added) | `author_choice` |
| Sensitivity `poi_ind_132kv` | IND 132 kV | | | CERC GNA Reg. 8.2(a) | layer `poi_sensitivity` of F2a |
| `conversion_indices.json` | BRA, IND, PRT: GDP deflator 2015-2025 and 2024 exchange rate | | | World Bank NY.GDP.DEFL.ZS and PA.NUS.FCRF, written by `scripts/fetch_conversion_indices.py` | all the years that the costs above need are present |

F6 now accepts the three countries in the validator (`group3_problems` returns nothing for BRA, IND and PRT, with solar and wind), without running. The proxy and provisional statuses do not stop F6; they are listed in LIMITATIONS (L-056, L-217, L-218).
