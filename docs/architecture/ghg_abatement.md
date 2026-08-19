Corresponde à Fase 7 — GHG Abatement do GeoWorld legado.

# GHG Abatement — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/ghg_abatement_calculator.py` (`GHGAbatementCalculator` + funções module-level, 1457 linhas, lidas por completo em 2026-08-19). Cross-referenciado com `docs/memory/04-algorithms.md`, `docs/DECISIONS.md` (D6, escopo elétrico), `docs/TASKS.md`/`docs/archive/backlog-full-2026-08.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito** (escopo estritamente **setor elétrico**, decisão D6 em `DECISIONS.md`): modelar a substituição técnico-econômica de geração térmica fóssil (carvão/gás/óleo) por renováveis, calculando volume de substituição, Custo Marginal de Abatimento (MAC), intensidade de carbono antes/depois, decomposição GHG Protocol (Scope 1/2/3), e alinhamento com metas NDC/net-zero nacionais.

**Inputs**: `plants_df` (usinas térmicas existentes), CSVs zonais das Fases 4/5 (`{ISO3}_{tech}_balanced_zonal.csv`, `{ISO3}_{tech}_lcoe_zonal.csv`), `parameters.json`'s bloco `abatement` por país + `abatement_defaults`, `configs/net_zero_db.json` (baseline nacional de GEE), **dados externos ao vivo**: World Bank API (metadados de região/renda + CO₂ total) e OWID CSV (fallback de CO₂ total) — ver §d.

**Outputs**: `serializable_result` (dict único, retornado por `run()` **e** persistido manualmente — ver §d) com MAC, CO₂ evitado, valor econômico, intensidade de carbono antes/depois, cobertura de NDC; 5 PNGs (mapas, curva MACC, curvas de substituição, intensidade de carbono, net-zero); relatório de texto (bespoke, não usa `build_phase_report()` — mesma observação que a Fase 6's `_build_integrated_summary_section`).

---

## b. Fórmulas e localização exata

| # | Fórmula | Linha |
|---|---|---|
| 1 | **Geração térmica**: `gen_gwh = capacidade_mw × CF × 8760 / 1000`; `CO2 = gen_gwh × EF` | `_thermal_row()`, L211-223 |
| 2 | **Volume de substituição** (semântica v2.4, documentada no docstring do módulo L11-25): `renewable_gap = penetration_target − existing_renewable_share`; se `gap ≤ 0`: `subst_gwh = total_th_gwh × _MIN_TECH_SUBSTITUTION` (0.05); senão `gwh_to_add = grid_total_gwh × gap`, `subst_gwh = min(gwh_to_add, total_th_gwh, renew_total_gwh)`; se `grid_total_gwh` não configurado: modo legado `subst_gwh = min(total_th_gwh, renew_total_gwh) × penetration` | `_derive_subst_gwh()`, L226-268 |
| 3 | **LRMC** (custo marginal de longo prazo, com carbono): `lrmc = fuel_mc + EF × carbon_price / 1000` | `calc_macc()`, L297 |
| 4 | **MAC por tecnologia**: `mac = (LCOE − SRMC_médio) / EF_médio × 1000` [USD/tCO₂e] | `calc_macc()`, L306 |
| 5 | **Despacho por ordem de mérito**: renováveis construídas em ordem crescente de MAC (mais barato primeiro); térmicas deslocadas em ordem decrescente de EF (mais suja primeiro) | `calc_macc()`, L329-349 |
| 6 | **MAC global** = `(LCOE_médio_renovável − SRMC_médio) / EF_médio × 1000` | `calc_macc()`, L358 |
| 7 | **Economia operacional** = `max(0, (SRMC−LCOE) × subst_gwh × 1000 / 1e9)` [Bi USD]; **valor do carbono** = `CO2_evitado × 1e6 × carbon_price / 1e9` [Bi USD] | `calc_macc()`, L360-361 |
| 8 | **Intensidade de carbono da rede completa (antes)**: inclui renováveis existentes com `EXISTING_RENEW_LIFECYCLE_G=24.0` gCO₂/kWh (mediana de reservatório hidrelétrico, IPCC AR6) — `ci_before = (CO2_térmico + CO2_renovável_existente) / (geração_térmica + geração_renovável_existente)` | `calc_carbon_intensity()`, L393-475 |
| 9 | **Decomposição GHG Protocol** (Scope 1 = térmico residual; Scope 2 = renovável novo × CI pós-transição; Scope 3 = ciclo de vida das renováveis novas) | `calc_carbon_footprint()`, L478-512 |
| 10 | **Alinhamento NDC**: `target_ndc_mt = base_mt × (1 − ndc_pct/100)`; `coverage_pct = net_avoided / current_gap_mt × 100` | `calc_net_zero()`, L531-644 |

Unidades: geração em GWh/TWh, emissões em MtCO₂e (ou ktCO₂e), custos em USD/MWh (LCOE/SRMC/LRMC) e USD/tCO₂e (MAC/preço de carbono), intensidade de carbono em gCO₂/kWh.

---

## c. Parâmetros hardcoded

### Tabelas de fallback Tier (intencionais, documentadas)
| # | Local | Valor | Uso |
|---|---|---|---|
| 1 | `GLOBAL_THERMAL_FALLBACK` (L99-103) | `coal: EF=820, CF=0.55, SRMC=35`; `gas: EF=490, CF=0.45, SRMC=48`; `oil: EF=750, CF=0.35, SRMC=90` | Fallback se `parameters.json`/região/renda não especificarem |
| 2 | `GLOBAL_RENEW_LIFECYCLE_FALLBACK` (L105-109) | `solar=48, wind=11, biomass=230` gCO₂/kWh | Fallback de EF de ciclo de vida |
| 3 | `EXISTING_RENEW_LIFECYCLE_G=24.0` (L114) | Mediana IPCC AR6 (reservatório hidrelétrico) | Assume que a maioria das redes com alta participação renovável existente é dominada por hidrelétrica — **premissa não verificada por país** |
| 4 | `_LCOE_FALLBACK` (L117-121) | `solar=50, wind=65, biomass=60` USD/MWh | Fallback se CSV zonal da Fase 5 ausente |
| 5 | `GLOBAL_RENEWABLE_CF_FALLBACK` (L123-127) | `solar=0.20, wind=0.30, biomass=0.75` | Fallback de CF renovável |
| 6 | `_MIN_TECH_SUBSTITUTION=0.05` (L144) | Piso técnico de substituição quando meta já atingida | Citado como candidato fora de escopo em `TASKS.md`'s nota de escopo do Invariant Validation Project |
| 7 | Defaults finais de `_get_param()` (L972, L979, L988, L995) | `carbon_price=80.0`, `penetration=0.60`, `existing_renewable_share=0.0`, `grid_total_gwh=0.0` | Último nível da cascata país→grid_mix→região→renda→global→default |
| 8 | Benchmarks de intensidade de carbono (L472-474) | `EU=295, mundial=459, net-zero=24` gCO₂/kWh | Só para exibição no relatório |

### Achado novo (não em `TASKS.md`)
`_fetch_world_bank_total_co2_mt()` usa `timeout=_HTTP_TIMEOUT` (10s, L1126), mas `_fetch_owid_total_co2_mt()` usa `timeout=30` **hardcoded inline** (L1141), ignorando a constante `_HTTP_TIMEOUT` — inconsistência menor, não documentada em nenhum item existente.

---

## d. Cross-check de BLOCKERs já resolvidos

| Item | Confirmado presente? | Evidência |
|---|---|---|
| **BLOCKER-014** (fetch ao vivo da OWID quebra determinismo bit-a-bit) | **Confirmado ainda ABERTO** | `_fetch_owid_total_co2_mt()` (L1137-1159) ainda baixa `https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv` — branch `master`, sem pin de commit/versão, exatamente como descrito no BLOCKER. **Achado adicional não documentado**: o código agora tenta **primeiro** a API do World Bank (`_fetch_world_bank_total_co2_mt()`, L1123-1135) e só cai para OWID se o World Bank falhar (`_fetch_net_zero_data()`, L1207-1222) — essa dependência adicional (World Bank API) tem o **mesmo problema de não-determinismo** que BLOCKER-014 descreve para a OWID (dado externo variável no tempo, sem snapshot/pin), mas não está mencionada no texto original do BLOCKER-014. Vale atualizar o item para cobrir ambas as fontes. |
| **Dupla persistência de artefatos** (`ghg_abatement_calculator.py:912,920` — "unconfirmed whether data loss occurs", Parte 4a de `archive/00-project-state-and-reorg-plan.md`) | **Verificado nesta auditoria: dupla persistência confirmada, mas estruturalmente IMPOSSÍVEL de perder dado** | `serializable_result` (L871-905) é a **mesma variável** passada para `artifact_mgr.save_result()` (L912, persistência manual) e retornada por `run()` (L931, persistida automaticamente pelo orquestrador). Como as duas escritas salvam literalmente o mesmo objeto Python, não há como a segunda escrita descartar campos que a primeira tinha — ao contrário do padrão que causou BLOCKER-011 em `results_writer.py` (lá, os dois dicts persistidos eram **objetos diferentes** com conteúdos diferentes). Isso resolve a verificação recomendada em `archive/00-project-state-and-reorg-plan.md` §4a para o caso do Abatement — pode ser rebaixado para limpeza de I/O redundante, não é um BLOCKER de perda de dado. |
| D6 (escopo setor elétrico) | **Sim** | Docstring do módulo (L6) declara "SCOPE: ELECTRICITY TRANSITION (Electricity Generation Sector ONLY)" explicitamente; `calc_net_zero()` distingue claramente `fossil_thermal_mt` (setor modelado) de `current_total_mt` (todos os setores, contexto). |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **`EXISTING_RENEW_LIFECYCLE_G=24.0` assume que a mix renovável existente é dominada por hidrelétrica** (comentário no código, L112-113) — mas isso não é verificado por país. Um país com mix renovável existente dominado por solar/eólica (não hidro) teria uma intensidade de carbono "antes" real diferente (mais próxima de 11-48 gCO₂/kWh, não 24). **Pergunta**: essa premissa deveria ser parametrizada por país (ex. usando a composição real do `grid_mix_dominant` já presente em `parameters.json`) no GeoFREA?
2. **Duas fontes de dados externos ao vivo (World Bank API + OWID CSV), nenhuma pinada/versionada** — ambas quebram reprodutibilidade bit-a-bit entre execuções em dias diferentes (BLOCKER-014 documenta isso só para OWID; o World Bank tem o mesmo problema). **Pergunta**: no GeoFREA, esses dados deveriam ser baixados uma vez e versionados como snapshot (`configs/`), com atualização deliberada, em vez de buscados a cada execução?
3. **Cascata de fallback de parâmetros é profunda e complexa** (`_get_param()`, até 6 níveis: país→grid_mix→região→renda→global→default hardcoded) — **não há log ou campo persistido indicando qual nível da cascata foi efetivamente usado** para cada parâmetro em cada execução. **Pergunta**: vale adicionar rastreabilidade de proveniência (qual fonte forneceu cada valor) ao contrato de saída da fase no GeoFREA, similar ao que falta em `mask_source` na Fase 5 (ver `lcoe_modeling.md` §e.1)?
4. **Timeout inconsistente** (`_HTTP_TIMEOUT=10` vs. `30` hardcoded para OWID) — achado novo, sem BLOCKER associado. Provavelmente inofensivo, mas vale padronizar no GeoFREA.
