# CLAUDE.md — GeoFREA

## Projeto e propósito

GeoFREA é a reconstrução do zero do **GeoWorld Framework**, um pipeline geoespacial de 9 módulos organizados em 8 fases numeradas — **Fase 1** (`data_acquisition` + `data_quality_audit`) → **Fase 2a** (`grid_alignment`) → **Fase 2b** (`suitability_criteria`) → **Fase 3** (`suitability_builder`) → **Fase 4** (`potential_analysis`) → **Fase 5** (`lcoe_modeling`) → **Fase 6** (`results_synthesis`) → **Fase 7** (`ghg_abatement`) → **Fase 8** (`sensitivity_analysis`) — para análise de aptidão de sítios de energia renovável (solar/wind/biomass), desenvolvido como parte da pesquisa de doutorado de Douglas na UFMG.

A numeração canônica das fases é definida em `docs/CONVENTIONS.md` § "Phase numbering". Nunca escrever "Fase 2" sem sufixo: `grid_alignment` é **2a** e `suitability_criteria` é **2b**, fases distintas. O campo `fase_legado` em `docs/PROGRESS.json` (que mapeia ambos para o legado `2`) é metadado de proveniência, não o número de fase do GeoFREA.

O objetivo não é portar o código legado linha a linha, mas reconstruir a lógica científica com uma arquitetura limpa, corrigindo problemas estruturais já identificados no legado (ver `docs/architecture/module-mapping.md`) e preservando (ou revisando deliberadamente, com justificativa) o comportamento científico validado.

## `GEOWORLD_BASELINE_DIR` — fonte read-only

A variável de ambiente `GEOWORLD_BASELINE_DIR` (definida em `.env`) aponta para o repositório `geoworld_framework/`, irmão de `GeoFREA/` no disco. Esse diretório é a referência legada e **é estritamente read-only**:

- Nunca escrever, editar ou apagar nenhum arquivo dentro de `$GEOWORLD_BASELINE_DIR`, mesmo sem proteção de sistema de arquivos.
- Usar esse diretório apenas para consulta: leitura de código-fonte, documentação (`docs/`), e outputs de baseline (`outputs_baseline/`) para geração de checksums/comparações de regressão.
- Qualquer necessidade de "corrigir" algo no legado deve virar uma nota em `docs/architecture/` ou uma entrada em `DECISIONS.md` do GeoFREA — nunca uma edição no próprio `geoworld_framework/`.

## Início e fim de sessão

- **No início de toda sessão**, ler `docs/PROGRESS.json` antes de qualquer outra ação, para determinar o que já foi feito e o que falta antes de propor próximos passos.
- **Ao final de toda sessão que alterar código ou documentos de arquitetura**, atualizar `docs/PROGRESS.json` (campos `fase_atual`, `ultima_atualizacao`, status dos módulos afetados, contradições resolvidas/novas) antes de encerrar.
  - `fase_atual` usa a numeração de **marcos de reconstrução do projeto** (`0`, `0.5`, depois o rótulo de fase do pipeline do módulo em construção), que é um eixo separado dos números de fase do pipeline. A convenção completa está em `docs/CONVENTIONS.md` § "Phase numbering" → "Project-milestone numbering".

## Convenções do projeto

### STRUCTURAL_PRESERVE vs. METHODOLOGY_REVISION

Toda decisão que preserva ou altera o comportamento científico/estrutural do legado deve ser registrada em `docs/DECISIONS.md` (append-only, nunca editar/apagar entrada existente), usando um dos dois tipos:

- **STRUCTURAL_PRESERVE**: a lógica do legado é mantida como está (mesmo que imperfeita), porque alterá-la mudaria resultados científicos já validados sem justificativa nova.
- **METHODOLOGY_REVISION**: a lógica do legado é deliberadamente alterada. Exige `Justificativa` e, quando aplicável, `Referência` (literatura ou discussão) no registro.

### Tolerância de regressão por tipo de variável

Ao comparar outputs do GeoFREA com os baselines do legado (`docs/architecture/baseline-manifest.md`):

- **Determinístico** (fórmulas fechadas, sem componente estocástico): `rtol` entre `1e-4` e `1e-3`.
- **Econômico/técnico** (ex. LCOE, CAPEX/OPEX, fatores de capacidade): tolerância de até **5%**; qualquer divergência acima de **0.5%** exige entrada obrigatória em `DECISIONS.md` explicando a causa.
- **Decisões binárias** (ex. inclusão/exclusão de pixel, aprovação/reprovação de critério): **100% de paridade**, salvo `METHODOLOGY_REVISION` documentada explicitamente.

### Concorrência

Antes de escrever em qualquer arquivo compartilhado (documentos de arquitetura, `DECISIONS.md`, `PROGRESS.json`), verificar a existência de `.session-lock` na raiz do projeto. Se existir, tratar como sessão concorrente em andamento e não sobrescrever sem coordenação.
