# DECISIONS.md — GeoFREA

Log de decisões arquiteturais e metodológicas do GeoFREA. Append-only: nunca editar ou apagar uma entrada existente — se uma decisão substituir outra, a antiga ganha `Status: Superseded by <data>`, não é removida.

Template de entrada:

## [data] - [nome do módulo]
Tipo: STRUCTURAL_PRESERVE | METHODOLOGY_REVISION
Descrição:
Justificativa (se METHODOLOGY_REVISION):
Referência (literatura/discussão, se aplicável):

---

## [2026-08-19] - protected_areas / IUCN exclusion categories
Tipo: STRUCTURAL_PRESERVE
Descrição: compute_protected_areas() (criteria_builder.py) exclui categorias IUCN Ia, Ib e II (score 0.0), aplicado uniformemente a todas as tecnologias e países, confirmado por investigação de código (único call site, sem condicionamento por tech, flag única protected_as_exclusion sem distinção de categoria). O comportamento é documentado no próprio docstring do código desde o commit inicial. GeoFREA herda este comportamento sem alteração.
Justificativa: decisão metodológica de Douglas — preservação e conservação de Parques Nacionais (categoria IUCN II) e demais áreas de proteção estrita (Ia/Ib), visando evitar desmatamento/conversão de uso do solo para instalação de infraestrutura de energia renovável. Esta lógica é aplicada de forma uniforme a todas as tecnologias (solar, eólica, biomassa), não como regra específica de uma tecnologia. Não há citação externa (WDPA/paper) associada à escolha original da categoria II no código legado — esta é uma decisão própria do pesquisador, registrada explicitamente como tal, e não uma herança de norma externa documentada.
Referência (literatura/discussão, se aplicável): nenhuma referência externa — decisão própria do pesquisador, registrada como tal.
Ação de correção: atualizar docs/memory/03-pipeline.md (ou seu sucessor no GeoFREA) para refletir Ia/Ib/II corretamente, eliminando a divergência com o docstring do código.

---

## [2026-08-19] - biomass CAPEX/OPEX/lifetime fallback values
Tipo: METHODOLOGY_REVISION
Descrição: _SA4_DEFAULTS (sensitivity_analyzer.py) e DEFAULT_LCOE_PARAMS (lcoe_calculator.py) divergiam para biomassa: CAPEX 2500 vs 2720, OPEX 100 vs 109, vida útil 30 vs 20 anos. Douglas confirmou que os valores de DEFAULT_LCOE_PARAMS (CAPEX=2720, OPEX=109, vida útil=20 anos, dr=7%) correspondem à fonte IRENA "Renewable Power Generation Costs in 2024" citada no docstring do módulo. Os valores de _SA4_DEFAULTS (2500/100/30anos) são tratados como o duplicado desatualizado/incorreto, sem fonte própria documentada — mesma classe de bug já corrigida uma vez no histórico do GeoWorld (_irena_defaults, duplicação de fatores de capacidade).
Justificativa (se METHODOLOGY_REVISION): consolidar a Fase 8 (Sensitivity Analysis) na mesma fonte econômica canônica da Fase 5 (LCOE), eliminando uma divergência numérica não documentada e potencialmente distorciva (a diferença de vida útil, 30 vs 20 anos, afeta o resultado de LCOE de forma não-trivial).
Fonte: IRENA, Renewable Power Generation Costs in 2024. Confirmação verbal de Douglas nesta sessão (data: 2026-08-19) — NÃO verificada independentemente por mim nem pelo Claude Code via acesso direto ao PDF/tabela primária, já que nenhum dos dois tem acesso geral à web. Se Douglas checar o documento formalmente depois e encontrar divergência, esta entrada deve ser revisada.
Ação de correção para o GeoFREA: consolidar em UMA única fonte de verdade de parâmetros econômicos por tecnologia (parameters.json, seção lcoe_defaults ou equivalente), eliminando a duplicação entre a Fase LCOE e a Fase Sensitivity Analysis. _SA4_DEFAULTS deixa de existir como constante separada — a análise de sensibilidade deve ler os mesmos valores canônicos usados no cálculo de LCOE principal. Todos os valores entram no schema Pydantic com a fonte IRENA 2024 registrada como metadata/comentário.

---

(fim das decisões registradas até o momento)
