# Auditoria de fatos — dimensionamento da migração de `DECISIONS.md`/`CONVENTIONS.md`/`PROGRESS.json`

Data: 2026-09-15. Escopo: leitura somente, sem alterações. Objetivo: dimensionar a migração para a nova estrutura de registro. Nenhum commit foi feito.

Anexos consultados: `CLAUDE.md`, `docs/DECISIONS.md` (1571 linhas), `docs/CONVENTIONS.md`, `docs/PROGRESS.json`.

---

## 1. Totais de `DECISIONS.md`

- **Total de linhas**: 1571.
- **Total de entradas**: **58** (59 cabeçalhos `## [data] - ...` menos 1: o primeiro, linha 7, é o template de entrada do próprio arquivo, não uma decisão registrada).

---

## 2. Classificação por fase × tipo

Eixos de classificação (conforme pedido — distintos do campo `Tipo:` do próprio arquivo, que usa STRUCTURAL_PRESERVE/METHODOLOGY_REVISION/VERIFICATION_UPDATE e é tratado à parte na Seção 4):
- **Fase**: F1 (`data_acquisition`+`data_quality_audit`), F2a (`grid_alignment`), F2b (`suitability_criteria`), `core` (schemas/orchestrator/geo_utils compartilhados), `config` (settings.yaml), `CI`, `transversal` (não amarrado a um módulo específico).
- **Tipo**: metodologia (decisão científica/de escopo), implementação (código/wiring/schema novo), bug (correção de comportamento incorreto), desempenho (investigação/correção de performance), dado/fonte (valor, proveniência ou fonte de dado).

| Fase \ Tipo | metodologia | implementação | bug | desempenho | dado/fonte | **Total fase** |
|---|---|---|---|---|---|---|
| F1 | 2 | 10 | 4 | 2 | 5 | **23** |
| F2a | 2 | 2 | 4 | 0 | 0 | **8** |
| F2b | 4 | 2 | 7 | 0 | 0 | **13** |
| core | 1 | 2 | 0 | 0 | 5 | **8** |
| config | 0 | 1 | 0 | 0 | 0 | **1** |
| CI | 0 | 1 | 0 | 0 | 0 | **1** |
| transversal | 2 | 0 | 2 | 0 | 0 | **4** |
| **Total tipo** | **11** | **18** | **17** | **2** | **10** | **58** |

A soma da tabela (58) bate com o total de entradas contado no item 1 — critério de conclusão satisfeito.

### 2.1 Classificação individual (data, título, fase, tipo)

| Data | Título | Fase | Tipo |
|---|---|---|---|
| 2026-08-19 | protected_areas / IUCN exclusion categories | F2b | metodologia |
| 2026-08-19 | biomass CAPEX/OPEX/lifetime fallback values | core | dado/fonte |
| 2026-08-20 | biomass CAPEX/OPEX/lifetime — verificação da fonte primária | core | dado/fonte |
| 2026-08-20 | biomass parameters restructure (IRENA 2025) | core | dado/fonte |
| 2026-08-20 | biomass discount_rate e discount_rate_increment — resolução das pendências | core | dado/fonte |
| 2026-08-20 | discount_rate architecture fix | core | implementação |
| 2026-08-20 | solar and wind parameters populated (IRENA 2024/2025) | core | dado/fonte |
| 2026-08-20 | settings.yaml phase toggles | config | implementação |
| 2026-08-20 | Transport Decarbonisation phase - exclusão permanente | transversal | metodologia |
| 2026-08-20 | orchestrator + data_quality_audit phase | core | implementação |
| 2026-08-20 | slope_threshold_deg movido para parameters.json | core | metodologia |
| 2026-08-24 | data_acquisition skeleton | F1 | implementação |
| 2026-08-24 | protected (WDPA): decisão de onde entra no GeoFREA fica pendente | F1 | metodologia |
| 2026-08-24 | vector layer audit depth | F1 | implementação |
| 2026-08-24 | path/paths source-of-truth consolidation | F1 | bug |
| 2026-08-24 | IUCN category normalization fix | F1 | bug |
| 2026-08-24 | AuditSummary refactor to layer-keyed dict | F1 | implementação |
| 2026-08-25 | real fetchers for power_plants/wind/lakes/rivers | F1 | implementação |
| 2026-08-25 | data_acquisition activation | F1 | implementação |
| 2026-08-25 | solar (Global Solar Atlas): padrão de URL per-country decifrado | F1 | dado/fonte |
| 2026-08-25 | seismic: fonte identificada (GEM Global Seismic Hazard Map v2023.1) | F1 | dado/fonte |
| 2026-08-25 | seismic: fetch automatizado descartado por restrição de licença | F1 | metodologia |
| 2026-08-25 | solar: unidade do PVOUT — arquivo já em uso confere | F1 | dado/fonte |
| 2026-08-25 | biomassa como mitigação de CO2 para transporte e curtailment — roadmap | transversal | metodologia |
| 2026-08-25 | clip_vector_to_country() exact-intersection bottleneck (STRtree+simplify+threading) | F1 | desempenho |
| 2026-08-26 | country_gdf=None + clip=True: incidente de quase-OOM + guarda | F1 | bug |
| 2026-08-26 | real fetcher for borders/admin1 (GADM 4.1) | F1 | implementação |
| 2026-09-08 | wire das 5 camadas restantes, Fase 1 (elevation/population/grid/land_cover) | F1 | implementação |
| 2026-09-08 | wire das 5 camadas restantes, Fase 2 (roads/GRIP4) | F1 | implementação |
| 2026-09-08 | `infrastructure/grid/grid.gpkg`: pendência de decisão, NÃO aplicada | F1 | dado/fonte |
| 2026-09-08 | grid_alignment (Fase 2a) portado do legado | F2a | implementação |
| 2026-09-08 | grid_alignment orchestrator wiring | F2a | implementação |
| 2026-09-09 | Passo 6: validação real PRT/BRA + correção do mismatch de land_cover | F2a | bug |
| 2026-09-09 | Passo 4: os 4 veredictos metodológicos de grid_alignment | F2a | metodologia |
| 2026-09-10 | compute_solar_resource guards NODATA_FLOAT sob solar_pvout_weight | F2b | bug |
| 2026-09-10 | terrain_score denominator is per-country | F2b | bug |
| 2026-09-10 | compute_biomass_resource exclui land_cover==255 explicitamente | F2b | bug |
| 2026-09-10 | pacote 4 fecha os 14 critérios; protected_areas sem paridade bit-exata | F2b | implementação |
| 2026-09-11 | suitability_builder (Fase 3): mecanismo do buffer de segurança de rio | F2b | metodologia |
| 2026-09-11 | data_acquisition: solar (PVOUT) ganha resolver local | F1 | implementação |
| 2026-09-11 | grid_alignment: derivação de slope do DEM (método e ordem) | F2a | metodologia |
| 2026-09-11 | grid_alignment: slope não herda contaminação de nodata | F2a | bug |
| 2026-09-11 | suitability_criteria: protected_areas distingue WDPA ausente de corrompido | F2b | metodologia |
| 2026-09-11 | grid_alignment: reproject_to_grid sanitiza NaN literal antes do warp | F2a | bug |
| 2026-09-11 | suitability_criteria: TRI (terrain_score) não herda contaminação | F2b | bug |
| 2026-09-11 | grid_alignment: mosaic_land_cover fail-loud em tile corrompido | F2a | bug |
| 2026-09-11 | data_acquisition: fetch_status quebrava resume a partir de manifest.json | F1 | bug |
| 2026-09-11 | slope não herda contaminação de nodata: correção de escopo (PRT vs BRA) | F2a | bug |
| 2026-09-11 | data_acquisition: protected_planet API activation | F1 | implementação |
| 2026-09-11 | protected_areas: repara geometria WDPA inválida antes do clip | F2b | bug |
| 2026-09-14 | cartografia D7 (plot_criterion_map): ajustes visuais | F2b | implementação |
| 2026-09-14 | compass rose fix + backlog: mapa de densidade agregada | F2b | bug |
| 2026-09-14 | grid (data_acquisition): verificação de estado, sem mudança de decisão | F1 | dado/fonte |
| 2026-09-14 | rivers/roads BRA (1.8x produção vs isolado): investigação parcial | F1 | desempenho |
| 2026-09-14 | regression fixtures storage: GitHub Release + CI skip→fail | CI | implementação |
| 2026-09-14 | pop_suitability: divergência CI-only, causa raiz confirmada (ruído sub-ULP) | F2b | bug |
| 2026-09-14 | addendum de rotulagem: Justificativa ausente (protected_areas ausente/corrompido) | transversal | bug |
| 2026-09-14 | addendum de rotulagem: Justificativa ausente (mosaic_land_cover fail-loud) | transversal | bug |

---

## 3. Entradas supersedidas

`DECISIONS.md` nunca usa, em nenhuma das 58 entradas, o marcador formal `Status: Superseded by <data>` prescrito pelo próprio template do arquivo (linha 3: "se uma decisão substituir outra, a antiga ganha `Status: Superseded by <data>`, não é removida") — busca direta (`grep -i "superseded"`) confirma zero ocorrências fora do próprio texto do template. Ou seja, **nenhuma supersessão está marcada formalmente no arquivo**. Abaixo, supersessões e restrições de escopo identificadas por leitura de conteúdo (não pelo marcador, que não existe):

1. **Supersessão de valor confirmada**: entrada `2026-08-19 - biomass CAPEX/OPEX/lifetime fallback values` (fixa CAPEX biomassa = 2720 USD/kW, fonte IRENA 2024) e sua verificação `2026-08-20 - biomass CAPEX/OPEX/lifetime — verificação da fonte primária` (confirma 2720 contra a fonte) são **supersedidas em valor** pela entrada `2026-08-20 - biomass parameters restructure (IRENA 2025)`, que registra explicitamente: "o valor 2720 carregado na entrada de 2026-08-19 foi confirmado pelo próprio Douglas em 2026-08-20 como incorreto/desatualizado em si" e fixa CAPEX = 3606 USD/kW. As duas entradas antigas permanecem no arquivo (append-only) e continuam válidas quanto ao seu ponto metodológico (consolidar Fase 8/Sensitivity na mesma fonte econômica da Fase 5/LCOE) — só o número numérico específico (2720) é que foi substituído por um posterior (3606).
2. **Restrição de escopo (não supersessão plena)**: `2026-09-11 - grid_alignment: slope não herda contaminação de nodata (correção de integridade)` tem seu alcance corrigido, no mesmo dia, por `2026-09-11 - slope não herda contaminação de nodata: correção de escopo (PRT vs BRA)` — marcada `VERIFICATION_UPDATE (addendum)`, não substitui a correção em si, só restringe/corrige a descrição de qual país(es) era afetado.
3. **Addenda de rotulagem, não supersessão de conteúdo**: as duas entradas `2026-09-14 - addendum de rotulagem: Justificativa ausente em "..."` referenciam, respectivamente, `2026-09-11 - suitability_criteria: protected_areas distingue WDPA ausente de WDPA corrompido` e `2026-09-11 - grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país` — ambas declaram explicitamente "não altera a decisão original", apenas apontam a ausência do rótulo formal `Justificativa:` exigido pelo template. Não são supersessões.

Nenhuma outra entrada das 58 contém linguagem de reversão/substituição de uma decisão anterior além dos três casos acima.

---

## 4. Entradas ainda válidas com justificativa metodológica (Tipo = METHODOLOGY_REVISION, puro ou combinado)

Uma linha por entrada — usa o campo `Tipo:` do próprio arquivo (não o eixo "tipo" da Seção 2), pois é o vocabulário que a Seção 4 do enunciado pede. **26 das 58 entradas** carregam `METHODOLOGY_REVISION` (isolado ou combinado com `STRUCTURAL_PRESERVE`/`VERIFICATION_UPDATE`) e uma `Justificativa` preenchida com conteúdo real (não `n/a`):

- `2026-08-19` biomass CAPEX/OPEX/lifetime fallback values — consolidar Fase 8 na mesma fonte econômica da Fase 5, eliminando divergência de vida útil (30 vs 20 anos) (valor numérico específico depois supersedido, ver Seção 3).
- `2026-08-20` biomass parameters restructure (IRENA 2025) — atualizar para a edição mais recente da fonte primária e diferenciar `capacity_factor` por país pela primeira vez.
- `2026-08-20` discount_rate architecture fix — mover `discount_rate` de nível-país para nível-tecnologia, pois a IRENA retorna taxas genuinamente diferentes por tecnologia para o mesmo país.
- `2026-08-20` solar and wind parameters populated (IRENA 2024/2025) — popular os domínios solar/eólica era pré-requisito para a Fase 2b avançar além de biomassa.
- `2026-08-20` orchestrator + data_quality_audit phase — consolidar toda orquestração num mecanismo único, testável, com contrato de saída tipado e resumabilidade real.
- `2026-08-20` slope_threshold_deg movido para parameters.json — o fallback único de 15° do legado não tinha fonte e ignorava que cada tecnologia tem tolerância de terreno fisicamente distinta.
- `2026-08-24` data_acquisition skeleton — estabelecer o contrato de aquisição antes de implementar fetch real, evitando crescimento ad hoc.
- `2026-08-24` vector layer audit depth — a auditoria de dados deve reportar profundidade equivalente para todo dado bruto, não só rasters.
- `2026-08-24` path/paths source-of-truth consolidation — eliminar uma classe de bug estrutural (duas fontes de verdade para o mesmo fato) antes do fetch real existir.
- `2026-08-24` IUCN category normalization fix — sem normalização de case, o breakdown por categoria fragmentaria incorretamente dados WDPA reais.
- `2026-08-24` AuditSummary refactor to layer-keyed dict — fecha pendência registrada em `PROGRESS.json`; união discriminada evita duplicar detalhe já disponível em `AuditResult`.
- `2026-08-25` real fetchers for power_plants/wind/lakes/rivers — substituir esqueleto por fetch real, base para ativar `data_acquisition`.
- `2026-08-25` data_acquisition activation — remover `UnwiredPhasesError`, já que agora `data_quality_audit` é genuinamente alimentado por `data_acquisition`.
- `2026-08-25` seismic: fetch automatizado descartado por restrição de licença — fonte identificada (GEM) é CC BY-NC-SA (não-comercial), decisão de não automatizar por restrição de licença, não por falta de caminho técnico.
- `2026-08-25` biomassa como mitigação de CO2 para transporte e curtailment (roadmap) — registra ideias distintas da fase Transport Decarbonisation excluída, sem desenho metodológico ainda.
- `2026-08-25` clip_vector_to_country() exact-intersection bottleneck — STRtree+simplify+threading necessários para viabilizar clip de país geometricamente grande/complexo (Brasil) em tempo hábil.
- `2026-08-26` country_gdf=None + clip=True incidente — guarda `ClipRequiresCountryGdfError` necessária para nunca cair silenciosamente no caminho sem clip que quase esgotou a RAM.
- `2026-08-26` real fetcher for borders/admin1 (GADM 4.1) — fecha a dependência que bloqueava `country_gdf` real em produção.
- `2026-09-08` wire das 5 camadas restantes, Fase 1 — resolver localmente as camadas restantes a partir do banco já disponível, sem inventar fetch novo.
- `2026-09-08` wire das 5 camadas restantes, Fase 2 (roads/GRIP4) — GRIP4 substitui OSM por país como fonte de roads, um único arquivo regional recortado a jusante.
- `2026-09-08` grid_alignment (Fase 2a) portado do legado — preserva a lógica científica validada do legado (STRUCTURAL_PRESERVE) onde aplicável, com revisões pontuais justificadas (METHODOLOGY_REVISION nos itens específicos).
- `2026-09-09` Passo 4: os 4 veredictos metodológicos de grid_alignment — Bowring centralizado, raio de busca unificado (100km), resolução fixa 0.01° (não "adaptive"), matriz AHP de vento mantida como está.
- `2026-09-10` compute_solar_resource guards NODATA_FLOAT sob solar_pvout_weight — o legado multiplicava até o sentinela NODATA por qualquer peso≠1.0, corrompendo pixels inválidos.
- `2026-09-11` suitability_builder (Fase 3): mecanismo do buffer de segurança de rio — esclarece que o setback ripário é produzido na Fase 2b e promovido a exclusão rígida só na Fase 3.
- `2026-09-11` suitability_criteria: protected_areas distingue WDPA ausente de corrompido — fail-loud para falha de integridade de arquivo presente, `assumed_free` preservado só para ausência genuína.
- `2026-09-11` suitability_criteria: TRI (terrain_score) não herda contaminação de NaN/nodata — mesma classe da correção de nodata do slope, garante que um pixel válido adjacente a um nodata não recebe um TRI corrompido.
- `2026-09-11` grid_alignment: mosaic_land_cover fail-loud em tile corrompido — mesmo precedente do WDPA: falha de integridade em arquivo presente não deve ser silenciosamente absorvida.

---

## 5. `CONVENTIONS.md` — regras ativas (uma linha cada)

1. **Idioma**: todo código-fonte, comentários, docstrings, nomes e mensagens de commit devem estar em inglês.
2. **Docstrings**: estilo Google, cobrindo propósito/`Args`/`Returns`; função geoespacial sem unidade/CRS documentados é considerada incompleta.
3. **Parâmetros**: todo parâmetro novo vai para `config/parameters.json` (científico/tecnológico) ou `config/settings.yaml` (operacional/infraestrutura), validado via schema Pydantic em `src/geofrea/core/` — proibido hardcode em módulos de processamento (política de projeto, não estilo).
4. **Metadado de verificação de parâmetro**: toda entrada-folha de `parameters.json` carrega bloco padrão `value`/`source`/`verified`/`verified_by`/`verified_date`/`verification_method`; um parâmetro `verified: false` não bloqueia uso, mas o metadado deve existir e ser testável.
5. **Tipagem de decisão** (`STRUCTURAL_PRESERVE`/`METHODOLOGY_REVISION`/`VERIFICATION_UPDATE`): toda decisão que preserva ou altera comportamento científico/estrutural do legado deve virar entrada em `DECISIONS.md` (append-only) com um destes três tipos; um `Tipo:` pode combinar um tipo canônico com qualificador entre parênteses, ou dois tipos com `|` quando a entrada cobre mudanças de naturezas diferentes.
6. **Tolerâncias de regressão** (`rtol`, limiares pixel-exatos) são definidas em `CLAUDE.md`, não em `CONVENTIONS.md`.
7. **Rastreabilidade de código**: código que implementa uma decisão registrada deve referenciá-la (ex. `# See DECISIONS.md 2026-08-19 - ...`).
8. **Numeração de fases**: 9 módulos agrupados em 8 fases numeradas (`2a`/`2b` distintas); nunca escrever "Fase 2" sem sufixo.
9. **Exclusão da Transport Decarbonisation** (Fase 9 legada): permanentemente excluída, sem número de fase GeoFREA — decisão deliberada de escopo, não lacuna.
10. **`fase_legado` em `PROGRESS.json`** é metadado de proveniência (mapeia `grid_alignment` e `suitability_criteria` ambos para o legado `2`), não o número de fase do GeoFREA.
11. **Status de módulo em `PROGRESS.json`**: um dos três valores `construido`/`documentado_nao_construido`/`parcialmente_implementado`; um módulo `construido` pode depender de um módulo Fase 1 só `parcialmente_implementado` sem isso ser, por si, um erro.
12. **Numeração de marco de projeto** (`fase_atual`): eixo separado da numeração de fase do pipeline — `0` (auditoria do legado completa), `0.5` (baseline regenerado), depois o rótulo de fase do módulo em construção.
13. **Addenda em `DECISIONS.md`**: quando uma decisão foi parcialmente superada por um addendum posterior (não substituída por completo), código que a referencia deve citar a data do addendum, não da entrada original, mantendo o nome da entrada original entre parênteses para rastreabilidade.

---

## 6. `PROGRESS.json` — schema de campos

Estrutura observada no arquivo atual (não um JSON Schema formal — o arquivo não declara um; campos inferidos por inspeção direta):

| Campo (caminho) | Tipo | Descrição |
|---|---|---|
| `fase_atual` | string | Marco de reconstrução do projeto (`"0"`, `"0.5"`, ou rótulo de fase do pipeline em construção, ex. `"2b"`) — eixo separado da numeração de fase do pipeline. |
| `ultima_atualizacao` | string (data ISO) | Data da última atualização do arquivo. |
| `contradicoes_pendentes` | array de objeto | Cada item: `id` (string, slug), `descricao` (string), `referencia` (string, aponta para `docs/DECISIONS.md`/`docs/architecture/*.md`), `status` (string: `"resolvido"`, `"resolvido_ver_decisions_md"`, ou pendente). |
| `baseline` | objeto, chaveado por código de país (`"PRT"`, `"BRA"`) | Cada valor: `status` (string), `commit` (string, SHA do legado), `observacao` (string). |
| `modulos` | array de objeto | Cada item: `nome` (string, nome do pacote `src/geofrea/<nome>/`), `fase_legado` (int ou `null`), `status` (string: `"construido"` \| `"documentado_nao_construido"` \| `"parcialmente_implementado"`), `observacao` (string, narrativa longa), `referencia` (string, opcional — aponta para entradas de `DECISIONS.md`), `regression_ci` (string, opcional — presente só em `suitability_criteria` nesta versão do arquivo). |
| `excluded_modules` | array de objeto | Cada item: `nome`, `fase_legado`, `status` (ex. `"excluido_permanente"`), `referencia`. |
| `modulos_extra` | array | Vazio no estado atual — reservado para módulos fora do mapeamento `modulos`/`excluded_modules`. |
| `modulos_futuros_backlog` | array de objeto | Cada item: `id` (string, slug), `titulo` (string), `estagio` (string, ex. `"ideia_registrada"`), `observacao` (string), `referencia` (string). |

Não há um arquivo `.schema.json` associado nem validação Pydantic para `PROGRESS.json` no código-fonte (distinto de `parameters.json`/`settings.yaml`, que são validados via `core/schemas.py`) — confirmado por ausência de qualquer `ProgressFile`/schema equivalente em `src/geofrea/core/schemas.py` nesta auditoria.

---

**Critério de conclusão**: tabela fase × tipo (Seção 2) soma 58, igual ao total de entradas contado no item 2 (Seção 1) ✓. Único arquivo criado é este (`docs/_audit/2026-09_records.md`); nenhum arquivo de `docs/DECISIONS.md`, `docs/CONVENTIONS.md` ou `docs/PROGRESS.json` foi modificado.
