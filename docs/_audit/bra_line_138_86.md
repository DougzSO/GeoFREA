# BRA: cost per km of a 138 kV single-circuit line (COMMAND 86, OQ-001)

Accessed 2026-11-02. Local copies under `GEOFREA_DATA_DIR/external/epe_r1/`.

## Source and why it is not the Resolucoes Autorizativas

The ANEEL authorizing resolutions (www2.aneel.gov.br/cedoc/rea*.pdf) answer HTTP 403 to every download from this machine, from `curl` and from the fetch tool, and the search results for the 138 kV lines in them were declarations of public utility for easements, without investment. They were not used and no workaround was attempted.

The EPE transmission studies (Relatorio R1) carry, for each line of an alternative, the **ANEEL modular cost per km** of its configuration (the BPR value, "Custos Modulares da ANEEL"), the extension in km and the total. The tables list "Circuito Simples 138 kV, 1 x <conductor>, N km, year, km, quantity, unit cost (R$ x 1,000 per km), total". These are reference costs applied by the planner, not as-built investments.

## The seven cases (single conductor, 138 kV, single circuit)

| # | Study (EPE) | Conductor | Unit cost (R$ thousand/km) | Price base | Page | Deflated to 2024 BRL (R$/km) |
|---|---|---|---|---|---|---|
| 1 | EPE-DEE-RE-043/2023 (Barra, Vale do Sao Francisco) | 1 x 336.4 MCM Linnet | 542.60 | Mar/2023 | 62 | 564,736 |
| 2 | EPE-DEE-RE-043/2023 | 1 x 636 MCM Grosbeak | 658.24 | Mar/2023 | 62 | 685,094 |
| 3 | EPE-DEE-RE-043/2023 | 1 x 954 MCM Rail | 713.26 | Mar/2023 | 58 | 742,359 |
| 4 | EPE-DEE-RE-039/2019 (RMPOA, volume 2) | 1 x 336.4 MCM Linnet | 360.95 | Jun/2017 | 225 | 562,248 |
| 5 | EPE-DEE-RE-039/2019 (RMPOA, volume 2) | 1 x 477 MCM Hawk | 502.07 | Jun/2017 | 228 | 782,070 |
| 6 | EPE-DEE-RE-075/2019 (Cuiaba) | 1 x 336.4 MCM Linnet | 402.20 | May/2019 (inferred) | 81 | 575,261 |
| 7 | EPE-DEE-RE-075/2019 (Cuiaba) | 1 x 556.5 MCM Dove | 418.33 | May/2019 (inferred) | 85 | 598,332 |

- **Price bases.** RE-043/2023 states "Base de Referencia de Precos ANEEL - marco/2023" (p. 26); RMPOA cites "CUSTOS MODULARES DA ANEEL - JUNHO DE 2017" (p. 371) and "banco de Custos ANEEL/2017" (p. 185). The Cuiaba study cites both June 2017 (its investment sheets) and "Atualizacao dos Valores para a Data-Base Maio de 2019" (reference [6]); its cost tables carry Linnet at 402.20, 11.4 % above the 360.95 of June 2017 for the same conductor, so May 2019 is inferred for cases 6 and 7. This is the one date that is not stated for the table itself.
- **Deflation.** Each value is multiplied by the World Bank GDP deflator of Brazil of 2024 over that of the base year (2017: 163.42; 2019: 177.98; 2023: 244.58; 2024: 254.56; `external/world_bank/conversion_indices.json`). The three Linnet cases, from three price dates, land within 2.3 % of each other (562,248, 564,736 and 575,261), which supports the deflation.
- **Statistics (N = 7, above the minimum of 5).** Median R$ 598,332/km (2024) = about USD 111,000/km at 5.389 BRL/USD; Q1 R$ 569,999; Q3 R$ 713,726. These go to `connection.line_cost_per_km` of BRA (value, low, high), price year 2024, Tier 2, status `sourced`.
- **Not used.** The ESMAP fallback (110 to 161 kV single, 0.304 MUSD 2010/km, Tier 3, provisional) was not needed: N was at least 5.
- **Left out.** Twin-conductor lines (2 x 795 MCM Tern, 584.16 in the Niteroi study) and double-circuit lines, because the line of a plant connection is a single conductor; the Niteroi value would be one more case at 2 x 795 MCM.
