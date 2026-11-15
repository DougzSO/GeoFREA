# IRENA reference values for the calibration of tau (report 11)

Written for: the author. Reference values registered before COMMANDS 158 to 162 use them. The author checked the values below against the IRENA documents on 15/11/2026. The table is copied literally from the command; abbreviations are those of the author (TIC = total installed cost in USD/kW; CF = capacity factor; O&M in USD/kW/yr; LCOE in USD/MWh; p5 and p95 in parentheses; CA = alternating current). The decisions that use them are DEC-075 to DEC-080 in `docs/DECISIONS.md`; nothing here is written to `config/`.

```
EDICAO irena_rpgc_2024 (Renewable power generation costs in 2024, publ. jul/2025, USD reais de 2024, vida util 25 anos, capacidade e CF em base CA)
Solar BRA: TIC 724 (p5 503, p95 1152); CF 20%; O&M 10,95 (nao-OCDE); LCOE 48 (36/77)
Solar IND: TIC 525 (415/831); CF 18%; O&M 10,95; LCOE 38 (32/59)
Solar Europa (proxy PRT): TIC 779 (524/1312); CF 15% (media UE, Fig 1.4); O&M 20,73 (OCDE); LCOE 60 (41/103)
Eolica BRA: TIC 1307 (1015/1628); CF 53% (Fig 1.4/1.15; Tab 2.2 traz 56%); O&M 29; LCOE 30 (24/37)
Eolica IND: TIC 1110 (984/1270); CF 29% (Fig 1.4/1.15; Tab 2.2 traz 39%); O&M 23; LCOE 48 (43/53)
Eolica Europa (proxy PRT): TIC 1659 (1211/2232); CF 34% (25/43); O&M 45 (outros OCDE, Tab A3; Espanha 29); LCOE 51 (34/75)
EDICAO irena_rpgc_2025 (Renewable power generation costs in 2025, publ. 2026, USD de 2025, so LCOE nacional, Fig S3)
Solar: BRA 37, IND 35, global 44. Eolica: BRA 31, IND 43, global 33.
WACC real pos-impostos: regional 2024 (Fig 1.13, solar/eolica): Am. Sul 7,7/7,7; Europa 4,2/3,7; Asia 4,0/3,8. Pais 2021 (IRENA 2023, apendice, Fig A1), verified true: BRA 6,30/4,90; IND 5,90/5,90; PRT 4,20/3,20.
```

Where these values go: DEC-076 makes the 2024 edition the primary base of the calibration and the 2025 edition a secondary check only (converted with `to_usd_2024`, DEC-071); DEC-077 and DEC-078 say which capacity factor and which O&M are primary; DEC-079 says that TIC and CF are on an AC basis while F6 works on DC capacity (D-F6-028), which stays open in OQ-105. The question that these values raise about the WACC ranges of DEC-072 is OQ-104.
