# 06 — Demais registros: phases, OPEN_QUESTIONS, PROGRESS, LIMITATIONS, CONVENTIONS, _audit e _archive (COMANDO 147-G)

Gerado por script (`others_audit.py`, `phase_tests.py`) e por leitura dirigida; somente leitura. Nenhum arquivo de docs ou código foi alterado. Pasta mantida não rastreada até o 147-H. Data de referência: 2026-11-13; "mais de 60 dias" = antes de 2026-09-14.

## 1. docs/phases/*.md

Método: cada linha não vazia vai para o tipo da seção `##` onde está (Contract e Conformance = operacional; Active implementation decisions = log D-*; History; Known issues; qualquer outra seção, e os relatórios das subpastas, = outro). *Repete* = pelo menos 60% das sequências de 8 palavras da linha (linhas de 12 palavras ou mais) aparecem em `METHODOLOGY.md` ou `DECISIONS.md`. É uma medida de texto repetido, não de decisão duplicada.

| arquivo | linhas não vazias | operacional | log D-* | histórico | problemas conhecidos | outro | linhas que repetem METHODOLOGY ou DECISIONS |
|---|---|---|---|---|---|---|---|
| E1_explorer.md | 13 | 3 | 1 | 1 | 1 | 2 | 0 |
| E5b.md | 51 | 5 | 0 | 4 | 0 | 37 | 0 |
| F1_data_acquisition.md | 193 | 11 | 93 | 5 | 12 | 65 | 0 |
| F1b_data_quality_audit.md | 82 | 10 | 19 | 9 | 8 | 30 | 0 |
| F2a_grid_alignment.md | 79 | 14 | 43 | 7 | 8 | 2 | 0 |
| F2b_siting_layers.md | 53 | 17 | 11 | 2 | 16 | 2 | 0 |
| F3_land_eligibility.md | 84 | 12 | 47 | 14 | 4 | 2 | 0 |
| F4_climate_forcing.md | 48 | 9 | 27 | 4 | 1 | 2 | 0 |
| F5/audit_groups1-2.md | 177 | 0 | 0 | 0 | 0 | 171 | 0 |
| F5/audit_potential_65.md | 279 | 0 | 0 | 0 | 0 | 270 | 0 |
| F5/fix_round_46.md | 100 | 0 | 0 | 0 | 0 | 95 | 0 |
| F5/groups1-2_implementation_report.md | 87 | 0 | 0 | 0 | 0 | 77 | 0 |
| F5/oq053_report.md | 92 | 0 | 0 | 0 | 0 | 85 | 0 |
| F5/potential_maps_absolute.md | 77 | 0 | 0 | 0 | 0 | 69 | 0 |
| F5/potential_maps_v2.md | 70 | 0 | 0 | 0 | 0 | 61 | 0 |
| F5/run_report_real.md | 242 | 0 | 0 | 0 | 0 | 235 | 0 |
| F5/wind_cf_pixel_74.md | 68 | 0 | 0 | 0 | 0 | 62 | 0 |
| F5_technical_potential.md | 92 | 22 | 34 | 25 | 4 | 2 | 0 |
| F6_lcoe_modeling.md | 79 | 27 | 28 | 13 | 4 | 2 | 0 |
| F7_robustness_analysis.md | 115 | 29 | 61 | 16 | 2 | 2 | 0 |
| F7b_external_validation.md | 31 | 11 | 7 | 3 | 3 | 2 | 0 |
| F8_results_synthesis.md | 60 | 18 | 25 | 7 | 3 | 2 | 0 |
| core.md | 151 | 31 | 77 | 26 | 8 | 3 | 0 |
| core/coverage_alignment_54.md | 95 | 0 | 0 | 0 | 0 | 91 | 0 |
| core/geometry_dem_55.md | 208 | 0 | 0 | 0 | 0 | 201 | 0 |
| core/manifest_config_fix.md | 364 | 0 | 0 | 0 | 0 | 359 | 0 |
| core/resume_integrity_58.md | 117 | 0 | 0 | 0 | 0 | 108 | 0 |
| core/revalidation_52.md | 62 | 0 | 0 | 0 | 0 | 59 | 0 |

Totais: 3169 linhas em 28 arquivos; operacional 219, log D-* 473, histórico 136, problemas conhecidos 74, outro 2098; linhas repetidas 0 ({}).

Sensibilidade do limiar: de 1818 linhas com 12 palavras ou mais, **0** repetem a partir de 60%, **6** a partir de 30% (por tipo: {'log de decisões D-*': 2, 'outro (cabeçalho, relatório ou auditoria)': 4}) e **21** a partir de 15%. Ou seja: o texto dos registros de fase quase não copia METHODOLOGY nem DECISIONS; a repetição é de ideia (as mesmas regras citadas por ID), não de frase.

**Tensão com CONVENTIONS.md linha 47** ("phase records record decisions, their reasons and their tests, not the current status of the phase"): as seções *History* e *Known issues* existem em 13 dos 14 registros principais e guardam datas e estado; a regra do arquivo não os cobre. Conto: histórico 136 linhas e problemas conhecidos 74.

### Linhas da tabela de verificação

Linhas com coluna de status em `docs/phases/**`: **125** (`pass` 103, `n/a` 20, `partial` 2). Linhas cuja coluna de testes não cita nenhum teste resolvível: **26**. Linhas com pelo menos uma citação a teste que **não existe mais**: **11** (15 citações).

Citações mortas (até 10; todas no arquivo e na linha do registro de fase):

| onde | citado | problema |
|---|---|---|
| F5_technical_potential.md:21 | test_class_follows_the_mean_speed_with_the_last_class_unbounded | nome de teste não existe |
| F5_technical_potential.md:21 | test_class_rule_rejects_malformed_rules | nome de teste não existe |
| F5_technical_potential.md:21 | test_registry_rule_and_curves_must_name_the_same_classes | nome de teste não existe |
| F5_technical_potential.md:23 | test_declared_masked_cell_member_has_no_row_and_is_counted | nome de teste não existe |
| F5_technical_potential.md:23 | test_wind_factor_out_of_range_in_a_candidate_cell_raises | nome de teste não existe |
| F5_technical_potential.md:26 | test_real_countries_fail_loud_listing_the_missing_parameters_and_write_nothing | nome de teste não existe |
| F6_lcoe_modeling.md:24 | test_real_countries_fail_loud_listing_the_missing_parameters_ranges_and_price_years | nome de teste não existe |
| F6_lcoe_modeling.md:27 | test_lcoe_convergence.py | arquivo de teste não existe |
| F6_lcoe_modeling.md:29 | test_main.py::test_lcoe_modeling_reads_the_central_potential_forcing_and_members_and_produces_three_tables_per_technology | teste não existe no arquivo |
| F6_lcoe_modeling.md:31 | test_lcoe_convergence.py::test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_first_pair_that_agrees | arquivo de teste não existe |

**Testes citados, executados** (`pytest` com os 175 alvos: 33 arquivos inteiros e 142 funções citadas, sem filtro de marcador, `GEOFREA_DATA_DIR` em diretório de rascunho): 683 passed, 196 warnings in 955.01s (0:15:55); falhas: 0; erros: 0.


Limite: as linhas `pass` das tabelas cujo teste não foi citado por nome (por exemplo `same files`, `see D-...`) não foram executadas por este script; as linhas `n/a` são relatórios de auditoria sem teste.

## 2. OPEN_QUESTIONS.md

Tabela: 26 linhas; cabeçalho de 6 colunas. Classe do status (pelo começo do texto da célula): {'open': 22, 'parcialmente resolvida': 1, 'fechada ou resolvida': 3}. O texto do arquivo diz que o status é `open`, `research_in_progress` ou `awaiting_verdict`, e que a pergunta resolvida é apagada; **6 de 26 células de status não são um desses três valores exatos** e **2** têm texto livre de mais de 30 caracteres (ex.: OQ-068 «open, restricted to F7b; with the implementation of Group 7»; OQ-069 «resolved 2026-11-04 (COMMAND 96): rule A applied only to F7,»).

**Colunas inconsistentes:** linhas com número de colunas diferente do cabeçalho (6): nenhuma.

Valores da coluna Blocks: {'F5, F6': 1, 'F7': 9, 'E1': 1, 'Thesis Ch. 2': 1, 'F5': 1, 'F4, F7': 1, 'F7b': 2, 'F2a to F5, thesis limitations': 1, 'Synthetic world (ZZZ2)': 1, 'F2a, thesis, any publication or platform': 1, 'F1, CI (ERA5 fetcher)': 1, 'Library versions of a run (partly resolved 2026-11-10, COMMAND 128)': 1, 'F6': 2, 'F5, F7': 1, '(closed 2026-11-10, COMMAND 128) Two phases read configuration their scope did not name': 1, 'F6, F7': 1}. Valores da coluna Owner: {'Douglas': 26}.

**Abertas sem movimento há mais de 60 dias** (data do último commit que alterou a linha da própria OQ em `OPEN_QUESTIONS.md`; citações em outros arquivos não contam como movimento): **0** de 23 abertas ou parcialmente resolvidas.


Perto do limite (45 a 60 dias sem alteração da linha): **5**: OQ-007 (59 dias, 2026-09-15); OQ-013 (59 dias, 2026-09-15); OQ-014 (59 dias, 2026-09-15); OQ-020 (59 dias, 2026-09-15); OQ-021 (59 dias, 2026-09-15). Dessas, 5 têm 2026-09-15 como última alteração (o commit de adoção dos registros), isto é, o texto não mudou desde então.


Datas de última alteração por OQ (todas): OQ-007 2026-09-15; OQ-008 2026-10-08; OQ-010 2026-10-14; OQ-013 2026-09-15; OQ-014 2026-09-15; OQ-020 2026-09-15; OQ-021 2026-09-15; OQ-043 2026-10-27; OQ-051 2026-10-27; OQ-057 2026-10-09; OQ-064 2026-10-26; OQ-068 2026-11-12; OQ-071 2026-11-12; OQ-072 2026-11-12; OQ-078 2026-11-12; OQ-084 2026-11-12; OQ-001 2026-11-13; OQ-069 2026-11-13; OQ-085 2026-11-10; OQ-087 2026-11-13; OQ-088 2026-11-13; OQ-089 2026-11-13; OQ-090 2026-11-13; OQ-091 2026-11-13; OQ-092 2026-11-13; OQ-093 2026-11-13.

**OQ que se sobrepõem** (Jaccard de palavras de 6 letras ou mais, IDs e símbolos entre crases, na pergunta e no protocolo): 3 pares com índice de 0,20 ou mais (até 10 abaixo). OQ-087 a OQ-093 foram escritas em 13/11 citando OQ-008, OQ-010 e OQ-020 como relacionadas; a sobreposição com essas é por construção.

| índice | OQ | OQ | termos comuns |
|---|---|---|---|
| 0.33 | OQ-087 | OQ-088 | OQ-008, `tau`, author, oq-008. |
| 0.25 | OQ-087 | OQ-090 | OQ-008, author, primary, related |
| 0.22 | OQ-088 | OQ-090 | OQ-008, author, related, verdict |

**Status contra DECISIONS.md e código (itens 2d do 147-C):** o `02` mostrou 1 `closed` citado com palavra de pendência (OQ-085 em `general_audit_130.md`), 48 não `closed` citados com palavra de resolução e 104 OQ fora da tabela citadas como pendentes (candidatos por palavra-chave, não confirmados). Verifiquei à mão três: 
OQ-008 (aberta) e a decisão de 13/11 "τ ancorado no IRENA": a OQ pede ancorar τ em preços de leilão ou benchmark e a decisão fixa o IRENA (D1, opção b); a OQ não foi atualizada com a decisão (o texto da OQ-008 segue com o protocolo antigo); OQ-010 (metas): a decisão de 13/11 fixa o horizonte mais distante, sem extrapolar; a OQ-010 está presente na tabela? sim; OQ-020 e o código: `decision.py:68-77` recusa `q_ref != 0` e nomeia OQ-020; o status `open` e o código batem.

## 3. PROGRESS.json

**Existe hoje:** `docs/PROGRESS.json` (schema 2.0, `methodology_version` 19.4.0, `last_updated` 2026-11-12, marco atual MS-6); o de 2026-09 está em `docs/_archive/2026-09/PROGRESS.json` (114 linhas, 9 módulos do legado). O último commit que o toca: 2026-11-12.

**Países reais contra os manifestos** (`outputs/<ISO3>/manifest.json`): 0 divergências em 30 pares país-fase (F1 a F5 `ran_clean` com status `success` nos três; F6, F7 e F7b `not_run` e ausentes do manifesto). ZZZ: PROGRESS tem estados (`ran_clean`, `ran_with_issues`), mas `outputs/ZZZ` não existe (o mundo sintético roda em teste e CI).

**Fases contra os registros de fase** (status de PROGRESS e a coluna de status das tabelas de conformidade, `docs/phases`):

**Forma das tabelas de conformidade** (seção `## Conformance` de cada registro de fase): 4 cabeçalhos diferentes em 11 arquivos.

| arquivo | linhas | colunas | status das linhas |
|---|---|---|---|
| F1_data_acquisition.md | 8 | Item / Requirement / Current state / Status | {'pass': 7, 'partial': 1} |
| F1b_data_quality_audit.md | 7 | Item / Requirement / Current state / Status | {'pass': 6, 'partial': 1} |
| F2a_grid_alignment.md | 11 | Item / Requirement / Current state / Status | {'built,': 2, 'pass': 7, 'built': 2} |
| F2b_siting_layers.md | 13 | Current criterion / Rebuild role / Status | {'reuse': 2, 'reuse,': 1, 'rework': 3, 'new': 1, 'built': 4, 'remove': 2} |
| F4_climate_forcing.md | 6 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 5, 'partial': 1} |
| F5_technical_potential.md | 19 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 19} |
| F6_lcoe_modeling.md | 24 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 21, 'built;': 2, 'built': 1} |
| F7_robustness_analysis.md | 26 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 25, 'implemented,': 1} |
| F7b_external_validation.md | 8 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 8} |
| F8_results_synthesis.md | 15 | Item / Requirement / Implementation (module:function) / Test / Status | {'pass': 15} |
| core.md | 28 | Item / Requirement / Current state (from `docs/_audit/2026-09_F1-F2b.md` section 8) / Status | {'pass': 25, 'partial': 3} |

Os registros F1, F1b e F2a usam a coluna *Current state* e não têm coluna de teste: o estado está dentro do registro de fase, ao contrário do que CONVENTIONS.md linhas 31 e 47 mandam. Só os registros com a coluna *Test* entram nas linhas de verificação testáveis acima.

| fase | status em PROGRESS | status das linhas da tabela do registro de fase | observação |
|---|---|---|---|
| core | built_pending_conformance | {'pass': 25, 'partial': 3} |  |
| F1 | built_pending_conformance | {'pass': 7, 'partial': 1} |  |
| F1b | built_pending_conformance | {'pass': 6, 'partial': 1} |  |
| F2a | conformant | {'built,': 2, 'pass': 7, 'built': 2} |  |
| F2b | ran_clean | {'reuse': 2, 'reuse,': 1, 'rework': 3, 'new': 1, 'built': 4, 'remove': 2} |  |
| F3 | built_pending_conformance | {'pass': 9} | a tabela não tem `partial` ou `fail`, mas o PROGRESS diz `built_pending_conformance` |
| F4 | built_pending_conformance | {'pass': 5, 'partial': 1} |  |
| F5 | conformant | {'pass': 19} |  |
| F6 | conformant | {'pass': 21, 'built;': 2, 'built': 1} |  |
| F7 | conformant | {'pass': 25, 'implemented,': 1} |  |
| F7b | conformant | {'pass': 8} |  |
| F8 | conformant | {'pass': 15} |  |
| E1 | not_started | — |  |

**Comandos:** PROGRESS não tem lista de comandos; cita 21 números, o maior é COMMAND 135. O último commit que toca PROGRESS é de 2026-11-12; os commits de 2026-11-13 (COMMAND 139 e as OQ-001, OQ-069 e OQ-085 movidas para resolvidas; a restauração do DECISIONS.md; OQ-087 a OQ-093; L-224 a L-236; o ajuste do teste) são posteriores a ele. PROGRESS só aponta para `OPEN_QUESTIONS.md` e `LIMITATIONS.md` e não copia o estado delas, então esses commits não deixam divergência de conteúdo, mas o `last_updated` ficou em 2026-11-12.

**Marcos:** MS-6 "Parameter research (OQ-001 to OQ-023)" está `in_progress`; das OQ-001 a OQ-023, as que ainda estão na tabela: OQ-001, OQ-007, OQ-008, OQ-010, OQ-013, OQ-014, OQ-020, OQ-021. MS-7 a MS-11 estão `in_progress` e E1 `not_started`.

**Versão:** PROGRESS diz METHODOLOGY 19.4.0 e `METHODOLOGY.md` diz 19.4.0: iguais. Os manifestos guardam a versão por fase (`data_acquisition` 19.1.0, `data_quality_audit` 17.0.0, `grid_alignment` 19.1.0 em PRT), diferente do cabeçalho; não há erro, é a versão em que a fase rodou.

**PV-77** (pendência de verificação, IND e BRA): aberta em PROGRESS; CONVENTIONS.md linha 39 manda os países ficarem em `awaiting_content_check_post_77` enquanto a verificação está aberta, mas PROGRESS mostra IND e BRA F1 a F5 `ran_clean`. Isto é uma contradição entre as duas regras de estado (ver item 5).

## 4. LIMITATIONS.md

Tabelas: 111 linhas em 4 seções ({'Method limitations': 72, 'Scope boundaries': 5, 'Tier 3 values': 21, 'Limitations specific to Groups 4, 5 and 7': 13}). Colunas por linha por seção: {'Limitations specific to Groups 4, 5 and 7': [5], 'Scope boundaries': [2], 'Tier 3 values': [5], 'Method limitations': [5]}. As seções *Method limitations* e *Limitations specific to Groups 4, 5 and 7* têm o cabeçalho `ID | Statement | Affects | Why accepted | Thesis section`; a *Tier 3 values* tem outro conjunto de colunas (parâmetro, valor, justificativa, onde).

**Entradas repetidas** (Jaccard de palavras de 5 letras ou mais do enunciado, 0,50 ou mais): **0** pares.

**Sem fase, regra ou OQ de origem na própria linha** (nenhum de M-F*, D-*, OQ-*, U-, A-, V-, S-, T-, nem F1 a F8 em nenhuma coluna): **35** de 111: L-034, L-035, L-101, L-102, L-103, L-104, L-105, L-203, L-206, L-207 ....

**Entradas que citam entre crases um nome que não existe hoje em config, src, scripts nem tests** (candidatas a contradição ou a texto velho): **1**: L-049 (poi_gridfinder_lines).

**Entradas que citam como pendente uma OQ que não está mais na tabela** (candidatas por palavra-chave): 2: L-025→OQ-058; L-025→OQ-060.

Conferência de duas entradas por leitura:

| entrada | afirmação | resultado |
|---|---|---|
| L-033 | o F6 não modela curtailment | confere com `METHODOLOGY` (F6 sem curtailment) |
| L-019 | `distance_cap_km` provisório (100 km), sem fonte | confere com `settings.yaml distance_cap_km: 100.0` |

Não li as 111 entradas uma a uma contra o código; a lista de nomes inexistentes é só candidata.

## 5. CONVENTIONS.md (198 linhas)

Cada item abaixo foi conferido com um arquivo, uma contagem ou um comando (campo *evidência*).

| regra de CONVENTIONS.md | o que a prática atual mostra | evidência |
|---|---|---|
| l. 47 e l. 52: decisão registrada uma vez, no registro da fase; `Phase records record decisions` | o DECISIONS.md voltou a ser um registro de decisões (decisão do autor de 13/11/2026: "DECISIONS registra as decisões tomadas") | dois lugares: `docs/DECISIONS.md` (66 entradas, sem IDs) e `docs/phases/**` (D-*) |
| l. 74: "Implementation decisions are cited as `See docs/phases/F5_technical_potential.md D-F5-003.`" | o formato continua válido para as decisões de implementação; as decisões do autor no DECISIONS.md não têm ID para citar | 03: 65 de 66 entradas sem `D-*` |
| l. 52: "A decision is recorded once" | 16 IDs `D-*` têm mais de uma definição em `docs/phases` (ex.: D-F1-016 em duas linhas de F1) | 02, tabela 2b |
| l. 52: "IDs rise in the order of the file" e `- **D-<phase>-<n> — Title (date, command).**` | 302 de 364 bullets `- **D-` seguem o padrão com título e parênteses; 62 não; D-F7-031 e D-F7-032 faltam na série (D-F7 vai a 64) | 02, tabela 5 e contagem por script |
| l. 31 e l. 43 a 48: o estado vive só em PROGRESS.json; registros de fase sem estado | as seções *History* e *Known issues* dos registros de fase guardam datas e problemas; `test_status_lives_only_in_progress` cobre a Seção 12 do METHODOLOGY e os comentários de `config/*.yaml`, não os registros de fase | item 1 (contagens de History e Known issues) |
| l. 46: "Comments in config/*.yaml ... do not assert state" | comentários de `experiments.yaml` dizem "Null until the author sources them" (linha 418) e "All null until OQ-051 closes" (linha 433); o teste usa uma lista de termos (`not started`, `state as of`, ...) e passa | grep em `config/*.yaml` e `tests/unit/test_status_lives_only_in_progress.py` |
| l. 39: com um check de conteúdo aberto, o país fica em `awaiting_content_check_post_77` | PV-77 está aberta em PROGRESS (IND, BRA) e IND e BRA F1 a F5 estão `ran_clean` | item 3 |
| l. 7: "US English for code ... documentation, and commit messages" | 2 dos 12 últimos commits têm mensagem em português (58b5b11 e 41f1a81); todas as entradas novas do DECISIONS.md e os relatórios de auditoria de 13/11 estão em português; o DECISIONS.md antigo também (agosto e setembro) | `git log` e `docs/DECISIONS.md` |
| l. 198: "pytest-xdist with 2 workers ... is not the default" | `.github/workflows/unit.yml` roda `-n 3` (COMMAND 131: 24 min contra 46) em toda push; o texto da regra fala de `-n 2` medido em 22:47 contra 26:41 e diz que não é o padrão | `unit.yml` e linha 198 |
| l. 194 e 198: `ruff` limpo antes de commit; a suíte inteira é o único portão | `ruff check` passa; `ruff format --check` acusaria `tests/unit/test_parameter_contract.py`, mas o CI só roda `ruff check`. A regra diz "ruff clean" sem dizer se inclui o `format` | execução local de ruff (147-A2) |
| l. 117: `MIN_AVAILABLE_GB` 1,5 e saída 75 | `core/memory_guard.py:26: MIN_AVAILABLE_GB = 1.5`: confere | grep |
| l. 121: `keep_awake` schema `false`, arquivo `true` | `schemas.py:736 keep_awake: bool = False` e `settings.yaml:128 keep_awake: true`: confere | grep |
| l. 146 e 150: título "Run legibility (COMMAND ADJ-7)" | o título cita COMMAND (rótulo de comando); as regras são de prática, não de data: é o tipo de texto que `l. 46` pede para não ter estado; não é contradição de comportamento | leitura |
| l. 175 a 190: exemplo de cabeçalho CRAEI cita `src/craei/acquire/auxiliary.py:57` e commit baae881… | o caminho `src/craei/acquire/auxiliary.py` não existe no repositório (é do repositório de referência, "read-only"); a linha `:57` não é verificável aqui | 02, item 3 (caminho morto em docs ativos) |

Regras que conferi e **não** contradizem a prática: nomes de módulos e registros (l. 11 a 25: os 13 arquivos de `docs/phases` e os 13 pacotes existem), `scripts/find_decision.py` e `scripts/affected_tests.py` (existem), `mapstyle.figure_filename` (existe), `scripts/run_unattended.ps1` (existe).

## 6. docs/_audit/ e docs/_archive/

Arquivos rastreados: 190 (174 em `_audit`, 16 em `_archive`). Referência por caminho, em docs, src, tests, scripts, config, workflows e arquivos da raiz (`README.md`, `CLAUDE.md`, `pyproject.toml`, `main.py`); nome só = só o nome do arquivo aparece.

| categoria | arquivos | em _audit | em _archive |
|---|---|---|---|
| citado como fonte ativa (código, doc ativo ou raiz) | 72 | 68 | 4 |
| nunca citado | 57 | 57 | 0 |
| citado só por nome | 42 | 39 | 3 |
| citado só por outros _audit/_archive | 19 | 10 | 9 |

**Nunca citados** (até 10): _audit/2026-10_data_diagnostics_scripts/era5_heat_days.py, _audit/2026-10_land_availability_ranges_design.md, _audit/closing_131.md, _audit/f5_member_codes_127.md, _audit/group3_stats_139.md, _audit/group6_decomposition/BRA.csv, _audit/group6_decomposition/BRA.md, _audit/group6_decomposition/IND.csv, _audit/group6_decomposition/IND.md, _audit/group6_decomposition/PRT.csv ....

**Ainda citados como fonte por código ou pela raiz:** 33 arquivos; os mais citados (até 10): _audit/group6_audit_97.md (código 4, doc ativo 4); _audit/2026-10_data_diagnostics.md (código 3, doc ativo 4); _audit/memory_budget_88.md (código 3, doc ativo 4); _audit/performance_75.md (código 3, doc ativo 4); _audit/slope_dem_test_100.md (código 1, doc ativo 5); _audit/group3_costs_85.md (código 1, doc ativo 4); _audit/poi_counts_84.md (código 1, doc ativo 4); _archive/2026-09/architecture/data_quality_audit.md (código 4, doc ativo 0); _audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py (código 2, doc ativo 2); _audit/f3_memory_90.md (código 1, doc ativo 3).

**Citados só por docs ativos (sem código):** 39; exemplos: _audit/2026-09_F1-F2b.md, _audit/2026-09_conformance_check.md, _audit/2026-09_craei_climate_reuse.md, _audit/2026-09_data_coverage.md, _audit/2026-09_data_state_pre_G.md, _audit/2026-09_geofrea_data_inventory.md, _audit/2026-09_legacy_F3-F8.md, _audit/2026-09_parameters.md, _audit/2026-09_records.md, _audit/2026-09_repo_cleanup.md.

**Arquivados citados por código ou doc ativo** (4 de 16): _archive/2026-09/architecture/baseline-manifest.md (código 2, doc ativo 0, raiz 0); _archive/2026-09/architecture/data_quality_audit.md (código 4, doc ativo 0, raiz 0); _archive/2026-09/architecture/grid_alignment.md (código 1, doc ativo 0, raiz 0); _archive/2026-09/architecture/module-mapping.md (código 1, doc ativo 0, raiz 0).

**Substituíveis por um ponteiro** (critério do script, sem filtro de idade porque o repositório só tem registros desde 2026-09-15: em `_audit`, nome datado ou de rodada, medida ou relatório, sem citação por código nem pela raiz, 100 linhas ou mais ou arquivo de dados). Dois cortes: (A) também **sem** citação por docs ativos: **75** arquivos, 10,051 linhas; (B) citados por docs ativos mas não por código nem raiz: **24** arquivos, 6,596 linhas. O ponteiro seria uma linha em um índice de `docs/_audit/` com o commit onde o arquivo está. Exemplos do corte A (até 10, os maiores): _audit/general_audit_130.md, _audit/2026-10_data_diagnostics_scripts/altitude_k.py, _audit/proofs_75_77/polygon_fastpath_equivalence_item3_PRT.json, _audit/2026-10_data_diagnostics_scripts/b1_reference.py, _audit/2026-09_raw_data_inventory.md, _audit/2026-09_pipeline_provenance_map.md, _audit/profile_76_tables/bench/q1b/vecb_BRA_rivers.json, _audit/profile_76_tables/bench/q1b/vecb_BRA_roads.json, _audit/profile_76_tables/bench/q1b/vecb_IND_rivers.json, _audit/profile_76_tables/bench/q1b/vecb_IND_roads.json.

Limite: o critério é de citação, não de conteúdo; um relatório pode ser a única fonte de um número que o METHODOLOGY cita por data (o corte B é o de maior risco). Nenhum arquivo foi movido ou apagado.

Lista completa com contagens por tipo de quem cita: `06b_audit_archive_refs.tsv`.

