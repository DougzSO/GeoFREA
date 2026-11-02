# Evidence for the voltage thresholds V_th of the point of interconnection (COMMAND 85, OQ-065)

Accessed 2026-11-02. `verified: false` stays in `parameters.json` for the three values until Douglas confirms. Files are under `GEOFREA_DATA_DIR/external/vth/`.

| Country | V_th in the model | What the sources say | Clause | Gap |
|---|---|---|---|---|
| IND | 220 kV, 50 MW | The 50 MW limit is in the CERC GNA Regulations 2022. No clause fixes 220 kV as a minimum voltage. | Reg. 4.1(a) and (b), Reg. 8.2(a) | the 220 kV choice is not stated by the regulation |
| BRA | 138 kV | ONS Submódulo 3.1 sets minimum technical requirements for generation connected to the distributor's facilities "em nivel de tensao superior a 69 kV". No clause names 138 kV. | ONS PR Submódulo 3.1, item 1.7 | PRODIST Módulo 3 not read (the download returned HTTP 403); the Rede Básica rule (230 kV and above) is not quoted from a primary text |
| PRT | 150 kV | REN holds the concession of the transmission network at 150, 220 and 400 kV. | secondary sources only | the Regulamento da Rede de Transporte (Portaria 596/2010) was not read in full |

## IND: CERC GNA Regulations 2022

- Source: CERC (Connectivity and General Network Access to the inter-State Transmission System) Regulations, 2022, notified 7 June 2022. Copy read: https://thc.nic.in/Central Governmental Regulations/Central electricity Regulatory Commission (Connectivity and general network Access to the inter State Transmission System) Reguations,2022.pdf (scanned PDF, 44 pages; read by OCR of the page images).
- Regulation 4.1 (p. 7): "(a) Generating station(s), including REGS(s), with or without ESS, with an installed capacity of 50 MW and above individually or with an aggregate installed capacity of 50 MW and above through a Lead Generator or a Lead ESS; (b) Captive generating plant with capacity for injection to ISTS of 50 MW and above". The next paragraph allows an entity with Connectivity to apply for an enhancement "of less than 50 MW subject to available capacity in transmission system". This supports the 50 MW limit.
- Regulation 8.2(a) (p. 10), the table of Conn-BG2 per terminal bay lists the voltage levels of allocated terminal bays: 132 kV, 220/230 kV, 400 kV, 765 kV. So ISTS terminal bays exist at 132 kV, below the 220 kV of the model. The regulation therefore does not support 220 kV as a floor; it is the author's choice for a plant of about 100 MW (Tier 2) and a lower value (132 kV) would be compatible with the text.
- The CTUIL document "Indicative Capital Cost of Dedicated Transmission Systems" prices dedicated lines at 220 kV and 400 kV for generation (Table 1), which is consistent with 220 kV as the lowest voltage of the dedicated systems it covers.

## BRA: ONS and ANEEL

- ONS Procedimentos de Rede, Submódulo 3.1 "Acesso às instalações de transmissão": https://www.ons.org.br//ProcedimentosDeRede/M%C3%B3dulo%203/Subm%C3%B3dulo%203.1/Subm%C3%B3dulo%203.1.pdf (8 pages). Item 1.7: "No que tange a conexao de centrais geradoras as instalacoes sob responsabilidade de distribuidora em nivel de tensao superior a 69 kV, este modulo trata de requisitos tecnicos minimos a serem atendidos por esses acessantes." Items 3(d) and 3(i) repeat "nivel de tensao superior a 69 kV". So the ONS procedures cover connections above 69 kV, which includes 138 kV; they do not name 138 kV as a threshold.
- ONS Submódulo 2.1 (Rev. 2024.07, https://proxyportais.ons.org.br/... Submódulo 2.1-DF_2024.07.pdf, found by search; the older Rev. 2.0 URL returned an HTML page, not the PDF): the Rede Básica is defined by ANEEL regulation, with 230 kV and above in the lists of facilities (converters and transformers "com tensao igual ou superior a 230 kV"). Not quoted from a primary text.
- PRODIST Módulo 3 (https://www2.aneel.gov.br/cedoc/aren2021956_prodist_modulo_3_v8.pdf): the download returned HTTP 403. Search results say the module covers access to the distribution system and gives no 138 kV limit in the passages found; this is not evidence.
- Pending for Douglas: the clause that defines the Rede Básica (REN ANEEL 67/2004 and later) and the PRODIST text that treats 138 kV as distribution (DIT), to decide whether 138 kV is the right floor or 230 kV (Rede Básica).

## PRT: REN

- https://www.ren.pt/en-gb/activity/electricity and the REN institutional brochure (https://ren.pt:443/media/qa1ltcyu/a-rede-de-todas-as-redes-brochura-institucional.pdf): REN holds the concession of transmission at 150, 220 and 400 kV (search-result summary, not read in the PDF). Portaria 596/2010 (https://diariodarepublica.pt/dr/detalhe/portaria/596-2010-334076) approves the Regulamento da Rede de Transporte; its nominal MAT voltages are listed as 130, 150, 220 and 400 kV (search-result summary).
- This supports 150 kV as the lowest voltage of the transmission network for PRT, with 130 kV in the regulation text for one line. Not read in the primary documents.

## Addendum (COMMAND 86): REN technical data 2024 and the status `author_choice`

- `ren-dados-tecnicos-2024.pdf` (https://www.ren.pt/media/al3n1imk/ren-dados-tecnicos-2024.pdf, 23 pages; local copy `external/vth/ren_dados_tecnicos_2024.pdf`), p. 8, "Comprimento das linhas (km) / Length of Lines (km)", end of 2024: 400 kV 3,242 km; 220 kV 3,886 km; 150 kV 2,533 km; total 9,661 km (2023: 3,080, 3,849 and 2,481). The chart of the same page has the series "Linhas 150 kV", "Linhas 220 kV" and "Linhas 400 kV"; p. 9 is the map "Rede Nacional de Transporte, Rede de Muito Alta Tensao 2024" with the legend "Linha 400 kV, Linha 220 kV, Linha 150 kV". The national transmission grid has three voltage levels and 150 kV is the lowest, which is the PRT threshold.
- The three thresholds now carry `status: author_choice` in `config/parameters.json` with the clauses above in their `note`; none of the sources fixes the number, so it is the author's choice (Tier 2). A sensitivity layer for IND at 132 kV (`poi_sensitivity`, `connection.poi_sensitivity_threshold_kv`) is built in the same F2a pass, because Reg. 8.2(a) of the CERC GNA lists 132 kV terminal bays.
