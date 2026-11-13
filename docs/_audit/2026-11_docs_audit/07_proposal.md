# 07 — Proposta (COMANDO 147-H)

Escrito para: o autor, para decidir. **Nada foi aplicado**: nenhum arquivo de docs, código ou configuração foi alterado; esta pasta continua não rastreada. Todas as contagens vêm de `01` a `06` desta pasta, salvo as duas marcadas "contagem feita agora".

## 1. Achados por gravidade

(a) regra de um doc contradiz o código ou outra regra; (b) número ou citação que não confere; (c) manutenção (obsoleto, repetido, sem ponteiro).

### (a) Bloqueia a implementação: 11 achados

| id | achado | fonte | tamanho |
|---|---|---|---|
| a1 | M-F6-08 diz que IND bay, BRA line e bay "não têm valor (OQ-001)"; `parameters.json` tem os três e OQ-001 está fechada | 05 | 1 regra |
| a2 | M-F6-10 diz que o F6 recusa enquanto um custo do Group 3 não tem valor (OQ-001); `group3_problems` dá 0 problemas nos seis casos | 05 | 1 regra |
| a3 | DECISIONS (13/11) "valores monetários já em USD de 2024" contradiz M-F6-08 e o código (moeda e ano nativos, convertidos no F6) | 05 | 1 entrada |
| a4 | M-F7-02 descreve o quantil `q_ref`; o código só constrói `q_ref = 0` (D-F7-009); OQ-020 e OQ-091 abertas. É limite documentado, mas trava qualquer troca para 0,01 | 05 | 1 regra |
| a5 | DECISIONS #34 mantém a matriz AHP de vento; M-F2a-04 e D-F2a-005 a removem | 03, 04 | 1 entrada |
| a6 | DECISIONS #1 fixa Ia/Ib/II uniforme; M-F2b-06 e `experiments.yaml` usam `all_designated` | 03, 04 | 1 entrada |
| a7 | DECISIONS #11 põe `slope_threshold_deg` por país em `parameters.json`; M-F2b-01 e `schemas.py:463` usam `slope_max_pct` de `land_availability` | 03, 04 | 1 entrada |
| a8 | DECISIONS #2 a #6 (biomassa) contra o escopo S-08, que exclui biomassa | 03 | 5 entradas |
| a9 | CONVENTIONS l. 47, 52 e 74 mandam registrar decisões só nas fases; o DECISIONS.md foi restaurado por decisão do autor | 06 | 3 linhas |
| a10 | CONVENTIONS l. 39 manda `awaiting_content_check_post_77` enquanto PV-77 está aberta; PROGRESS mostra IND e BRA `ran_clean` | 06 | 1 regra de estado |
| a11 | A decisão "τ, CF_min, q_ref e p_k fora do LHS, varridos como sensibilidade" não tem regra: só `p_k` tem sensibilidade em M-F7-07 | 05 | 3 eixos sem regra |

### (b) Bloqueia a tese: 10 achados

| id | achado | fonte | tamanho |
|---|---|---|---|
| b1 | Ponteiros para `docs/_archive/2026-09/DECISIONS.md`, que deixou de existir ao restaurar o arquivo (contagem feita agora por grep): src 53, tests 17, docs/phases 22, docs/_audit 10, config 1, docs 1 | novo | 104 linhas em 45 arquivos |
| b2 | Linhas `pass` dos registros de fase que citam teste inexistente (F5, F6 e outros) | 06 | 15 citações em 11 linhas |
| b3 | Referências mortas em docs ativos (sem DECISIONS, `_audit` e `_archive`): caminhos 153, testes 23, funções 56, links 0 | 02 | 232 |
| b4 | Citações `arquivo:linha` com problema em docs ativos: 4 arquivo ausente, 2 linha fora do arquivo, 38 símbolo não achado | 02 | 44 |
| b5 | OQ-091 (já no remoto) cita `evaluator.py:343` para a guarda V-03; ela está em 341-342 | 05 | 1 linha |
| b6 | `F6_lcoe_modeling.md:24`: "BRA, PRT and IND fail with 32 items each"; hoje são 0 problemas | 05 | 1 linha |
| b7 | Dados de execução dentro de regras: M-F2b-06 (1356 m em PRT e 1922 m em BRA), M-F2a-03 (18%, P95 8 a 15%, 0,78 km, 26,5 milhões de vértices), M-F2a-05 (1/144) | 04 | 3 regras |
| b8 | IDs citados sem definição: 110 (OQ resolvidas e apagadas 68, T 17, L 11, D 9, V 2, M-F 2, S 1) | 02 | 110 IDs |
| b9 | LIMITATIONS: L-025 cita OQ-058 e OQ-060 como pendentes (fora da tabela); L-049 cita `poi_gridfinder_lines`, que não existe em código nem config | 06 | 3 entradas |
| b10 | DECISIONS: 28 entradas com item morto na Referência (legado e `docs/architecture/*`); histórico, não se edita | 03 | 62 itens |

Conferência numérica: 78 constantes de regra contra o valor vivo (32 em F1 a F5, 46 em F6 a F8), **uma** diverge (a1). Não há divergência de número entre as regras e a config além dela.

### (c) Manutenção: 15 achados

| id | achado | fonte | tamanho |
|---|---|---|---|
| c1 | docs/: 60 arquivos sem referência de entrada e 62 só por nome | 01 | 122 de 277 |
| c2 | `_audit`/`_archive`: 57 nunca citados, 42 só por nome, 19 só por outros registros; candidatos a ponteiro 75 (corte A) e 24 (corte B) | 06 | 99 arquivos, 16.647 linhas |
| c3 | IDs definidos mais de uma vez: 36 (D 16, R71/R73 19, A 1); "recorded once" de CONVENTIONS | 02 | 36 |
| c4 | IDs definidos e nunca citados: 127 (D 72, L 40, R71 13, OQ 2) | 02 | 127 |
| c5 | Numeração: 62 de 364 bullets D-* fora do formato; D-F7-031 e 032 faltam; 123 números de L nunca usados; 4 L fora de ordem | 02, 06 | 191 |
| c6 | DECISIONS.md: 65 de 66 entradas sem `D-*`; 355 D-* só nas fases; 16 entradas sem um campo (Justificativa 13, Referência 3, Descrição 2); 5 com Tipo fora do padrão | 03 | 66 entradas |
| c7 | Registros de fase: histórico 136 e problemas conhecidos 74 linhas com estado; 4 formatos de tabela de conformidade; 26 linhas sem teste resolvível | 06 | 11 arquivos |
| c8 | OPEN_QUESTIONS: 6 de 26 status fora do vocabulário, texto livre em Blocks, 5 OQ a 59 dias sem alteração, OQ-008 sem a decisão do IRENA | 06 | 26 linhas |
| c9 | PROGRESS: `last_updated` 2026-11-12, sem lista de comandos, ZZZ sem manifesto | 06 | 1 arquivo |
| c10 | LIMITATIONS: 35 de 111 sem fase, regra ou OQ de origem; seção *Tier 3 values* com outras colunas | 06 | 111 linhas |
| c11 | CONVENTIONS: l. 7 (inglês), l. 46 (estado em comentário), l. 198 (xdist), exemplo CRAEI com caminho inexistente | 06 | 4 linhas |
| c12 | Código sem regra M-*: 66 funções grandes em F1 a F5 (36 sem nenhum ID); lista de F6 a F8 em `05b` | 04, 05 | 66+ |
| c13 | 16 regras de F1 a F5 sem teste direto (M-F6 a M-F8: nenhuma) | 04, 05 | 16 |
| c14 | Referências mortas em `_audit`, `_archive` e DECISIONS: caminhos 702, 225 e 113 | 02 | 1.040+ |
| c15 | Afirmações que dependem de dado: 23 acertos sem data na varredura de F1 a F5 (a maioria falso positivo) | 04 | 23 |

**Total: 11 + 10 + 15 = 36 achados.** Os de maior efeito prático são a3, a4, a9, b1 e b2.

## 2. Estrutura final proposta de docs/

Regra: **um lugar por tipo de informação**; os outros só apontam por ID.

| tipo | lugar único | ID | observação |
|---|---|---|---|
| regra de método | `METHODOLOGY.md` | `M-F*-nn`, `A-`, `U-`, `V-`, `S-`, `T-` | sem dado de execução; dado entra como "valor de data X" com ponteiro |
| decisão do autor | `DECISIONS.md` (só acréscimo) | `DEC-AAAA-MM-DD-nn` | cada entrada traz `Fase:` e, se houver, `Implementa: D-…` |
| decisão de implementação | `docs/phases/<fase>.md`, seção *Active implementation decisions* | `D-<fase>-nnn` | não se copia para o DECISIONS |
| pergunta aberta | `OPEN_QUESTIONS.md` | `OQ-nnn`, nunca reutilizado (próximo: OQ-094) | status só `open`, `research_in_progress`, `awaiting_verdict`; resolvida sai e deixa ponteiro no DECISIONS ou na fase |
| limitação | `LIMITATIONS.md` | `L-nnn` (próximo: L-237) | uma tabela com colunas fixas; origem obrigatória |
| estado | `PROGRESS.json` | — | o bloco `countries` gerado dos manifestos; os registros de fase perdem *History* e *Known issues* |
| convenção | `CONVENTIONS.md` | — | atualizado conforme o item 5 |
| contrato e testes de fase | `docs/phases/<fase>.md`, *Contract* e *Conformance* (colunas fixas com *Test*) | — | o resto sai |
| auditoria | `docs/_audit/` com `INDEX.md` gerado | por nome de arquivo | só entram aqui o que o METHODOLOGY ou uma fase cita |
| arquivo morto | `docs/_archive/<AAAA-MM>/` | — | só o que não é citado por código |

Destino por pasta ou arquivo:

| o que | destino | contagem |
|---|---|---|
| METHODOLOGY, DECISIONS, OPEN_QUESTIONS, LIMITATIONS, CONVENTIONS, PROGRESS, PIPELINE_GUIDE, PROJECT_SUMMARY | ficam | 8 arquivos |
| `docs/phases/*.md` (14 principais) | ficam, reduzidos a Contract, Conformance e D-* | 14 arquivos |
| `docs/phases/F5/`, `docs/phases/core/` (relatórios) | juntam-se ao `_audit`; o registro de fase aponta para eles | 14 relatórios |
| `docs/thesis/`, `docs/data/`, `docs/figures/` | ficam | 20 + 2 + 26 |
| `docs/_audit/` | ficam os 33 citados por código ou raiz e os citados por docs ativos; o resto vira linha em `INDEX.md` e vai para `_archive/2026-11/` | 75 (corte A) + 24 (corte B) |
| `docs/_archive/2026-09/` | ficam os 4 citados por código; os demais viram ponteiro | 16 arquivos |

## 3. ID estável do DECISIONS.md, índice e migração das D-Fx

- **ID:** `DEC-AAAA-MM-DD-nn`, `nn` = ordem no dia. Cabeçalho novo: `## [2026-11-13] DEC-2026-11-13-02 - nome`. As 58 entradas antigas **não são editadas**: o ID delas é atribuído pelo índice, na ordem do arquivo dentro de cada data.
- **Campos novos só nas entradas novas:** `Fase:`, `Implementa:` (IDs `D-…`), `Substitui:` (ID `DEC-…` e uma frase), `Estado:` (vigente, superada por, pendente com OQ, fato).
- **Estado das antigas:** em `docs/decisions_status.csv` (colunas `id, estado, superada_por, fonte`), nunca na entrada. Ponto de partida: os 14 achados do item 3 do `03` e os a5 a a8 acima.
- **Índice gerado:** `docs/DECISIONS_INDEX.md` por `scripts/build_decisions_index.py`, nunca editado à mão. Tabelas por fase, por tema (OQ e símbolos em comum) e por estado; inclui os 356 `D-*` das fases, com arquivo e linha, para o leitor ver as duas camadas num lugar.
- **Migração das D-Fx:** o texto **não se move**. Os `D-*` ficam nas fases com o mesmo ID (já são estáveis e citados em centenas de linhas de docs, código e testes). Uma decisão que o autor tomou ganha uma entrada `DEC-` com `Implementa: D-…`; o `D-*` não é renumerado nem copiado. As 16 definições duplicadas viram texto de continuação da primeira (sem mudar o ID).
- **Superação sem editar a antiga:** a entrada nova traz `Substitui:`; o CSV marca a antiga como "superada por". Um teste falha se `Substitui:` citar ID inexistente.

## 4. Lint de docs

`scripts/lint_docs.py` mais `tests/unit/test_docs_lint.py`; passo novo em `.github/workflows/unit.yml` (só no job do Python 3.12, depois do `ruff`): `python scripts/lint_docs.py --strict`. O corpus cabe na memória; a medição deste trabalho levou 10 a 20 s.

| verificação | o que checa | o que teria pegado nesta auditoria |
|---|---|---|
| IDs | todo ID citado em doc ativo está definido; nenhum definido duas vezes; `OQ`/`L` nunca reutilizados (lista `docs/_ids_retired.txt`); `DEC-` único e na ordem | c3, c5, b8 |
| links e caminhos | links relativos e caminhos entre crases em docs ativos existem; ponteiro para arquivo movido falha | b1, b3 |
| testes | todo `test_*` e `arquivo::nome` citado em tabela de fase existe | b2 |
| linhas | `arquivo:linha` em doc ativo: a linha existe e o símbolo entre crases está a até 5 linhas | b4, b5 |
| constantes | `docs/_constants.yaml` liga cada número de regra a uma chave de config ou constante de código e compara (as 78 conferências deste trabalho são a semente) | a1 |
| vocabulário | status de OQ, colunas de LIMITATIONS e de *Conformance*, campos obrigatórios de entrada nova do DECISIONS | c6, c7, c8, c10 |
| estado | `PROGRESS.json` `countries` contra o manifesto, quando há `GEOFREA_DATA_DIR` (pulado no CI) | c9 |
| OQ fechada citada como pendente | palavra-chave nas linhas que citam uma OQ fora da tabela, só como aviso | a2, b9 |

- **Exceções:** `DECISIONS.md`, `docs/_audit/` e `docs/_archive/` são históricos: só valem as verificações de ID e de formato de entrada nova.
- **Linha de base:** um `docs/_lint_baseline.json` guarda as violações de hoje (por exemplo, b3 com 232) e o lint só falha se o número **subir** ou se uma verificação nova aparecer; cada lote da seção 5 baixa a linha de base.

## 5. Lotes de correção

Nenhum lote mexe em linha antiga do DECISIONS.md. Só os lotes 2 e 12 escrevem no DECISIONS.md e o fazem por acréscimo. "Precisa de autorização" quer dizer que a regra do arquivo exige o autor (METHODOLOGY, protocolo de mudança 0.1) ou que altera linha antiga de outro registro.

| lote | tipo e arquivos | o que muda | linhas | risco | linha antiga do DECISIONS? | cobre |
|---|---|---|---|---|---|---|
| 1 | lint (novos): `scripts/lint_docs.py`, `tests/unit/test_docs_lint.py`, `docs/_constants.yaml`, `docs/_lint_baseline.json`, passo no `unit.yml` | cria o portão com linha de base; nenhum doc é corrigido | cerca de 500 novas | baixo (CI +10 a 20 s) | não | todos, a prevenir |
| 2 | DECISIONS.md, só acréscimo | 7 entradas novas: remoção do AHP, `all_designated`, fonte do declive, biomassa fora do escopo, baseline de regressão aposentado, `target_phases`, e a retificação da moeda (a3) | 70 a 90 | baixo | **não** (só acréscimo) | a3, a5, a6, a7, a8 |
| 3 | METHODOLOGY (precisa de autorização; bump PATCH e linha no changelog) | M-F6-08, M-F6-10 (OQ-001), dados de execução de M-F2a-03, M-F2a-05 e M-F2b-06 trocados por "valor de data X" | cerca de 8 | baixo | não | a1, a2, b7 |
| 4 | OPEN_QUESTIONS e LIMITATIONS (altera linhas antigas: precisa de autorização) | OQ-091 (linha da guarda), OQ-008 (decisão do IRENA), uma OQ nova para os eixos de sensibilidade (a11), 6 status no vocabulário; L-025, L-049 | cerca de 12 | baixo | não | a11, b5, b9, c8 |
| 5 | CONVENTIONS (precisa de autorização) | l. 47, 52, 74 (DECISIONS e fases), l. 39 (PV-77), l. 46, l. 198, l. 7, exemplo CRAEI | cerca de 14 | baixo | não | a9, a10, c11 |
| 6 | ponteiros do arquivo de DECISIONS: `src` 53, `tests` 17, `config` 1, `docs/phases` 22, `docs` 1 | troca `docs/_archive/2026-09/DECISIONS.md` por `docs/DECISIONS.md` em comentários, docstrings e docs (mecânico) | 94 linhas (até 45 arquivos) | baixo: o fingerprint do código ignora comentários e docstring (`code_fingerprint.py`), o YAML não muda no parse; rodar a suíte | não | b1 |
| 7 | `docs/phases/*.md`, citações de teste | trocar 15 citações por testes que existem; rodar cada um | cerca de 11 linhas | médio (achar o substituto certo; o teste novo pode não cobrir a mesma linha) | não | b2, b6 |
| 8 | `docs/phases/*.md`, IDs | 16 definições duplicadas viram continuação; 62 bullets D-* no formato; D-F7-031 e 032 registradas como "não usado" | cerca de 80 | baixo | não | c3, c5 |
| 9 | docs ativos, referências mortas e linhas citadas | 232 referências mortas (caminho 153, teste 23, função 56) e 44 citações de linha, por arquivo conforme `02b_dead_refs_full.tsv` | cerca de 280 | médio (pode tocar METHODOLOGY: fatia à parte com autorização) | não | b3, b4 |
| 10 | `docs/phases/*.md` e PROGRESS | tabela de *Conformance* uniforme (F1, F1b, F2a, F2b, core); *History* e *Known issues* saem dos registros de fase; `countries` de PROGRESS gerado dos manifestos; `last_updated`; decidir PV-77 | cerca de 250 movidas e 60 linhas de tabela | **alto** (decisão de estrutura; precisa de autorização) | não | a10, c7, c9 |
| 11 | LIMITATIONS (altera linhas antigas: precisa de autorização) | origem em 35 linhas; colunas da seção *Tier 3 values* | cerca de 45 | baixo | não | c10 |
| 12 | DECISIONS (acréscimo) e novos: `DECISIONS_INDEX.md`, `decisions_status.csv`, `build_decisions_index.py` | índice e estados gerados; sem `DEC-` retroativo no arquivo | cerca de 300 novas | baixo | **não** | c6 |
| 13 | `_audit` e `_archive` | `INDEX.md` gerado; mover 99 arquivos (16.647 linhas) com `git mv`, conteúdo intacto; corrigir os ponteiros dos 24 do corte B | 99 arquivos movidos | médio (os 24 arquivos do corte B são citados por docs ativos) | não | c1, c2, c14 |
| 14 | código, só relatório | decidir o que fazer com as 66 funções sem regra M-* (documentar a regra ou citar a decisão); nenhuma alteração de código sem aprovação | sem edição | — | não | c12, c13 |

Ordem sugerida: **1** (portão com linha de base), **6** (os ponteiros que a restauração quebrou), **2**, **3**, **4**, **5**, depois **7 a 9** e **11** (cada um baixa a linha de base), e por último **10**, **12** e **13**, que mudam a estrutura.

## 6. O que o autor decide

1. A estrutura da seção 2, em especial: os `D-*` ficam nas fases e o DECISIONS tem `DEC-` com `Implementa:` (seção 3).
2. Os lotes que precisam de autorização por tocar METHODOLOGY (3, parte do 9), CONVENTIONS (5), linhas antigas de OPEN_QUESTIONS e LIMITATIONS (4, 11) e a estrutura dos registros de fase (10).
3. O que fazer com a3: o código converte moeda, a decisão de 13/11 diz que a configuração já está em USD de 2024. Uma das duas muda (lote 2 registra a retificação; só o autor escolhe qual).
4. Limites desta auditoria: as 111 entradas de LIMITATIONS e as 58 antigas do DECISIONS não foram lidas uma a uma contra o código; a classificação por tipo de entrada (`03`, item 4) é por palavra-chave; as contagens de F6 a F8 sem M-* estão em `05b` e não foram somadas aqui.
