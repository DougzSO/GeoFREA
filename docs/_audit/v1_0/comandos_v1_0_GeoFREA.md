# GeoFREA v1.0: comandos para fechar a pipeline (167 em diante)

Arquivo de trabalho do Claude Code. Fica em `D:\Douglas\DOUTORADO\comandos_v1_0_GeoFREA.md`. Substitui, a partir do COMANDO 167, o `comandos_grupos_4_5_7_v3.md` (que segue como histórico até o 166). As decisões do autor para os comandos 167 a 198 estão em `D:\Douglas\DOUTORADO\decisoes_v1_0_GeoFREA.md` (regra 14 da seção 2).

---

## 0. Como o Code usa este arquivo

1. Ler as seções 1 a 4 inteiras antes do primeiro comando.
2. Executar o primeiro comando cujo título não termina em `[DONE]` e não está marcado `[PULADO]`. Um comando por vez. Ao terminar, parar e relatar ao autor.
3. Ao concluir um comando: acrescentar ` [DONE]` ao título, preencher a linha dele na tabela da seção 4 (commit, data, nota de até 20 palavras) e salvar. Antes da primeira edição de cada dia, copiar o arquivo para `comandos_v1_0_GeoFREA.bakNN_<AAAAMMDD>.md`.
4. Comando condicional cuja condição não se cumpre: marcar ` [PULADO]` com o motivo em uma linha.
5. `PARAR` dentro de um comando significa: encerrar o turno, relatar o motivo e esperar o autor. Não seguir para o próximo comando.
6. Se a saída de um comando contradisser uma premissa de comando seguinte (função que não existe, chave com outro nome, fase que já faz o que o comando pede, número diferente), listar no fim do relatório: comando afetado, premissa, fato encontrado, arquivo. Não reescrever comandos deste arquivo por conta própria.
7. Blocos `Veredito do autor (preencher antes de enviar)`: o texto escrito pelo autor vale como aprovação. Se o bloco estiver vazio ou com marcador de preenchimento pendente, PARAR. Os blocos deste arquivo já vêm preenchidos pelas decisões de `decisoes_v1_0_GeoFREA.md` (regra 14).

---

## 1. Ressalvas e problemas (leitura do assistente, 2026-11-17)

Lidos: resumo do framework, candidatos e execução da limpeza, comandos v3 inteiro, LIMITATIONS, OPEN_QUESTIONS, METHODOLOGY (seções 4 a 12), DECISIONS de DEC-059 a DEC-090 (as entradas anteriores, de setembro, só pelos cabeçalhos). Pontos que mudam o plano:

1. **Definição de v1.0 adotada.** F1 a F8 em produção nos três países, `cross_country_h4`, F7b, `lcoe_maps`, `robustness_maps`, as rodadas de sensibilidade de janela (2071-2100) e de escala (0,1°, V-07), todas as saídas essenciais da seção 10 da METHODOLOGY geradas (exceto a T-R10 e a estatística R_exp do H5b, que ficam "not available" por falta de limiar com fonte, V174b), prova P limpa e tag `v1.0`. O E1 (explorer) fica fora: a OQ-013 manda decidir a pilha depois do F7 e ele não é necessário para a tese. Entra no bloco I como opcional.

2. **OQ-114 é o maior risco técnico.** Pelos números do próprio F5 (cenário central, membro de referência), o CF eólico ponderado por capacidade é 15,6% no BRA (2.712,2 TWh / 1.990,7 GW / 8,76), 17,7% na IND e 26,1% no PRT. A frota brasileira citada no repositório é 38%. Uma diferença desse tamanho no BRA tem cara de erro de modelo ou de definição, não de seleção de sítio. O plano do resumo de passagem ("calibrar por país com correção de viés e declarar como ajuste") conflita com a V-06 da METHODOLOGY: nenhum parâmetro pode ser ajustado a usinas existentes sem divisão espacial treino e teste, e o F7b usa as mesmas usinas, então a validação externa ficaria circular. Por isso o plano aqui é diagnosticar (com uma checagem independente pelo fator de capacidade do próprio Global Wind Atlas) e só corrigir erro com causa física demonstrada por teste. Se não houver erro, vira limitação e os valores absolutos do eólico são apresentados com ressalva; o ranking continua utilizável. Nenhum F6 roda antes desse veredito.

3. **H5b depende da OQ-051 e ela não está no subconjunto pré-registrado.** A M-F7-07 exige que o conjunto de canais de perigo seja fixado "antes de qualquer resultado". Os limiares não entram no digest da tag, então fixá-los depois da tag e antes do primeiro F6 é aceitável, mas tem que ficar registrado como limitação (data e commit posteriores à tag, anteriores a qualquer resultado). O comando 173 proíbe calcular a fração de células expostas antes do veredito, para o limiar não ser escolhido olhando o efeito.

4. **OQ-094: fechar sem eixo novo.** Qualquer chave nova de sensibilidade no `experiments.yaml` ou no `parameters.json` que caia no subconjunto muda o digest, a guarda recusa F6 e F7, e a saída seria uma tag nova (`prereg-v2`), que é um desvio declarado. O comando 175 propõe fechar a OQ-094 com o que o código já faz (τ nas pontas do range no H5, top_k 5 e 20) e sem sensibilidade de cf_min e de q_ref. Se o autor quiser outro desenho, editar o texto antes de enviar, sabendo do custo.

5. **H5 só é testável em 3 de 6 pares** (BRA solar, IND solar, IND eólica). No eólico, só a Índia tem meta, então a síntese do H5 eólico sai "not assessable". Isso está pré-registrado (DEC-082 c) e meta acrescentada agora seria exploratória. Não é para corrigir, é para saber antes de ler o resultado.

6. **A convergência do tamanho de amostra (U-04) é global.** O tamanho adotado é o maior entre países e tecnologias, então o F7 final só roda depois do F6 e da convergência dos três países. A L-239 avisa que os sorteios de tamanhos diferentes são independentes. O custo no BRA é desconhecido; o F5 do BRA levou 410 s no 162F, e o F6 multiplica isso por membros e amostras.

7. **Memória.** F6, convergência, F7, F7b, `cross_country_h4`, mapas e F8 não têm teto medido; pela regra atual valem 1.536 MB com folga de 25%. No BRA é provável que parem por teto. O plano mede PRT e IND primeiro e só então o BRA. O F7b do BRA ainda lê camadas inteiras (OQ-068, cerca de 1,5 GB antes de avaliar a primeira usina) e precisa da leitura por janelas antes da produção (comando 187).

8. **Correção de código depois do primeiro resultado.** Bug de F6 ou F7 achado depois do primeiro resultado de produção pode e deve ser corrigido, mas vira DEC rotulada "post-result correction" e a fase roda de novo nos três países. O subconjunto pré-registrado nunca muda.

9. **Magnitudes que o F7b vai expor.** BRA solar central 16.489,5 GW contra 307 GW de potencial técnico da EPE (cerca de 54 vezes) e 28.519 GW de recurso; BRA eólica 1.990,7 GW contra 143 GW (Amarante, 50 m) e 14.580 GW (Eurek). O F7b só põe lado a lado (M-F7b-03), mas o texto da tese vai precisar explicar a diferença de definição (LUF, densidade, exclusões). Não bloqueia a pipeline.

10. **τ da Índia abaixo do p5 do IRENA (L-245).** O domínio econômico da Índia pode sair pequeno e o H5 pode cair em "target not met at reference". Isso é resultado, não defeito. Não mexer em τ depois de ver.

11. **Revisão da lista "bloqueia a tese" do Code.** OQ-010 está resolvida pelas DEC-063, 070, 075, 080, 083 e 084 e pela configuração do 162 (fecha no comando 168). OQ-057 não bloqueia a pipeline: o F7b mostra as entradas `pending` sem valor; bloqueia o texto. OQ-014, OQ-115 e as marcas `\vfy` são texto. OQ-098 entra no comando 190. Bloqueiam de fato a produção: OQ-114, OQ-051 e OQ-094.

12. **A janela única (comandos 177 e 178) é a última chance barata** de aplicar as edições que mexem em fingerprint de F1 a F5 (itens 3 e 9 da `window_list_131`, OQ-109, restamp da OQ-084, correção eólica se houver). Depois do F6, qualquer uma delas deixa F6 e F7 stale nos três países.

13. **Exclusão de arquivos.** No 166 o Code não conseguiu apagar e moveu para `_to_delete/`. O comando 167 tenta apagar; se o ambiente recusar, junta tudo numa pasta só e a exclusão final é manual.

14. **`database/` (126,4 GB) fica.** Pela M-F1-01 o GeoFREA não lê nada fora de `GEOFREA_DATA_DIR`, mas a pasta provavelmente serve a outros projetos (GEAR, CRAEI). O 167 só mede quanto dela está duplicado em `GeoFREA_data/raw`.

15. **Paralelizar por país não compensa agora.** O BRA domina o tempo e a memória; rodar PRT e IND em paralelo economiza pouco e soma pico de memória. Fica fora.

16. **O que não sei e o comando 169 verifica:** se `--production` recusa algum parâmetro `proxy` ainda em uso (a U-05 cita o O&M eólico de BRA e IND tirado do solar); como a janela 2071-2100 e a escala 0,1° são disparadas; se `figures: all` deixa stale as fases de mapas de F1 a F5; se `sample_size` está no subconjunto; como o código escreve o tamanho adotado da U-04. Os comandos seguintes dependem dessas respostas.

---

## 2. Regras para todos os comandos

1) Não executar main, orquestrador nem fases em `GeoFREA_data` real, salvo comando que peça.
2) Reproduzir falha de teste só com fixture em diretório temporário.
3) Antes de comando que toque nos dados, instantâneo dos manifestos em `GeoFREA_data/_snapshots/<AAAAMMDD>_pre<comando>/` com SHA256SUMS.txt.
4) Se uma regra for violada, relatar no início da saída.
5) Pré-registro: a tag `prereg-v1` (objeto 685a29cc…, commit ccf764f) não é movida, apagada nem recriada. Depois de qualquer edição em `config/`, rodar `python scripts/preregistration_digest.py`; agregado diferente de `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235`: PARAR e reverter a edição.
6) Antes de qualquer commit: suíte `tests/unit` completa, `python scripts/lint_docs.py`, prova P (0 diferenças, ou só o stale que o comando declara como esperado) e digest. Depois do push: Regression, Unit tests and lint e Synthetic fixture (ZZZ) em success no HEAD.
7) Rodada em dado real: registrar por fase e país `wall_s`, `cpu_s`, `peak_rss_mb`, `memory_cap_mb`, `peak_over_cap` e, nas fases F6 em diante, `preregistration.digest_live` e `digest_tag` (têm de ser iguais). Falha de fase: PARAR com a mensagem de erro, sem corrigir no mesmo comando.
8) Correção de código de F6 em diante depois do primeiro resultado de produção de qualquer país: DEC nova rotulada "post-result correction", fase reexecutada nos três países.
9) Registros do repositório em inglês (DEC append-only, METHODOLOGY com PATCH, changelog e `methodology_version` do PROGRESS iguais). Relatórios ao autor em português.
10) Decisão sem fonte vira "aberto, aguardando veredito do autor". Nenhum valor assumido.
11) Dados externos por código, com manifesto (URL, data de acesso, SHA-256, tamanho) e busca de fonte oficial alternativa se a URL falhar.
12) Relatórios fora do repositório vão para `D:\Douglas\DOUTORADO\_notas_geofrea\`.
13) Aprovação e commit em comandos separados quando o diff não é conhecido de antemão. Texto literal escrito no comando é aprovado pelo autor ao enviar e pode ser commitado no mesmo comando.
14) As decisões de decisoes_v1_0_GeoFREA.md valem como veredito do autor (aprovado em 2026-11-17). Decisão condicional aplica-se só ao caso que descreve; caso não coberto: PARAR.

---

## 3. Ordem e dependências

| Bloco | Comandos | Depende de |
|---|---|---|
| A. Limpeza e consistência | 166Z, 166Y, 167, 168 | 166 |
| B. Auditoria de prontidão | 169 | 168 |
| C. Decisões que bloqueiam a produção | 170, 171, 172 (só ramo A), 173, 174, 175 | 169 |
| D. Trava e janela única | 176, 177, 178 | C |
| E. F6 e convergência | 179, 180, 181, 182 | 178 |
| F. F7 e H4 | 183, 184, 185, 186 | 182 |
| G. Validação, mapas, sensibilidades, síntese | 187, 188, 189, 190 | 186 |
| H. Auditoria final e congelamento | 191, 192R, 192 | 190 |
| H2. Pós-congelamento | 196, 197, 198 | 192 |
| I. Fora da v1.0 | 193, 194, 195 [PULADO] | 192 |

Ordem final de execução (seção 4 de `decisoes_v1_0_GeoFREA.md`, com o 166Z e o 166Y): 166Z, 166Y, 167, 168, 169, 170, 171, 172 (só ramo A), 172R, 172C, 173, 174, 175, 176, 176R, 176C, 177 (itens 3 e 9 e o teto de 4000, V177b), 177R, 177C, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 187R, 187C, 188, 189, 190, 191, 192R, 192, 196, 197, 198. Os comandos 193, 194 e 195 ficam [PULADO].

---

## 4. Registro de execução

| Comando | Status | Commit | Data | Nota |
|---|---|---|---|---|
| 166Z | DONE | sem commit | 2026-11-17 | Decisões incorporadas: regra 14, vereditos, 197 e 198, ordem final. |
| 166Y | DONE | sem commit | 2026-11-17 | V182b, V174b, V177b, V196b fixados; textos de 167, 174, 177, 182 e 196 ajustados. |
| 167 | DONE | sem commit | 2026-11-17 | D1, D3 a D6, D9 feitos; D2 sem função de poda (executada pelo 196, V196b); libera ~1,27 GB. |
| 168 | DONE | 7b4da4b | 2026-11-17 | OQ-010 fechada; CONVENTIONS sem status awaiting; PROGRESS e PV-77 já estavam alinhados (sem edição). |
| 169 | DONE | sem commit | 2026-11-17 | Sem teto de convergência (null); 1b do 177 não se aplica; grupo5.tex sem θ; sem --plan/--real-run. |
| 170 | DONE | sem commit | 2026-11-17 | F5 reproduz GWA IEC3 (g 0,97 a 1,00); nas usinas F5 é 1,12 (BRA) e 1,14 (PRT) vezes a frota; ramo B provável. |
| 171 | DONE | 0d032e8 | 2026-11-17 | DEC-091, ramo B; OQ-114 fechada; L-249. Sem mudança de código nem de digest. |
| 172 (só ramo A) / 172R / 172C | [PULADO] |  | 2026-11-18 | ramo B no 171 (DEC-091); sem correção do modelo eólico. |
| 173 | DONE | sem commit | 2026-11-18 | Nenhum canal com limiar com fonte; ERA5 diário ausente, V-83 só contra W5E5 (diferença mediana dentro de ±5 dias). |
| 174 | DONE | 1f15ddb | 2026-11-18 | DEC-093, L-250, M-F7-07 19.4.13; OQ-051 e OQ-115 fechadas; 3 relatórios em docs/_audit. rx5day em hazard_indicators vai ao 177. |
| 175 | DONE | 48fa500 | 2026-11-18 | DEC-094 e M-F7-21 (19.4.14); OQ-094 e OQ-008 fechadas; nenhuma chave nova, digest idêntico. |
| 176 / 176R / 176C | DONE | a8dbd2c | 2026-11-18 | --real-run e --plan; 23 testes novos; unit 2579 passed; synthetic 129 passed; prova P 0; digest idêntico |
| 177 (itens 3 e 9 e teto 4000) / 177R / 177C | DONE | abdf210 | 2026-11-18 | Teto 4000, rx5day_mm em hazard_indicators, notas de parameters.json repontadas; janela única de edições |
| 178 | DONE | c934d71 | 2026-11-18 | Recomputação de F1 a F5 na janela única e restamp parquet2; referência publicada |
| 179 | DONE | sem commit | 2026-11-18 | PRT F6 e convergência; digests iguais; tolerância 0,005 aceita pelo autor |
| 180 | DONE | sem commit | 2026-11-18 | IND F6 e convergência; digests iguais; regra de memória não aplicada |
| 181 | DONE | 21449a5 | 2026-11-18 | BRA F6 e convergência (janela longa); max_batch_gb reduzido a 0,5 |
| 182 | DONE | 86fabd8 | 2026-11-18 | Tamanho de amostra adotado 4000 (U-04, teto V182b); PRT solar sem convergência (L-252) |
| 183 | DONE | 3fcdfbe | 2026-11-18 | PRT F7; primeira rodada falhou pela L-253, corrigida (DEC-095); success com digests iguais |
| 184 | DONE | sem commit | 2026-11-18 | IND F7 (robustness_analysis) success; digests iguais; registrado no progress de 2549eb0 |
| 185 | DONE | ed38b29 | 2026-11-19 | BRA F7 (janela longa) com limites desligados; pico 3.174 MB; teto medido registrado |
| 186 | DONE | 2549eb0 | 2026-11-19 | cross_country_h4 e PROGRESS de F6 e F7 (a rodada de 0,05° foi refeita pelo 191A) |
| 187 / 187R / 187C | DONE | b361b96 | 2026-11-20 | F7b por janelas de linhas, bit-idêntico; OQ-068 fechada; pico do BRA 1.072 MB |
| 188 | DONE | f887e55 | 2026-11-22 | external_validation, lcoe_maps e robustness_maps nos 3 países; tetos medidos de F6 a F7b |
| 188A | DONE | c7af733 | 2026-11-22 | F7b deixa de fora as células sem LCOE (L-253, D-F7b-009); teto de external_validation 3.904 MB |
| 189 | DONE | c7685f0 | 2026-11-22 | Janela 2071-2100 já no F7; escala 0,1° rodou F3 a F7 nos 3 países; H1 a H3 iguais |
| 189A | DONE | 3af7ce5 | 2026-11-22 | V-03 sem violação em 24 conjuntos; digests iguais; --production só audita |
| 190 / 190A / 190B / 190C | DONE | 0bc6a64 e c632831 | 2026-11-22 | Resumos por escala (D-core-055); F8 nos 3 países; teto 3.520 MB (V179c, L-254); LaTeX compila; OQ-098 fechada |
| 191 / 191A | DONE | fa090bb | 2026-11-23 | cross_country_h4 com 3 países nas 2 escalas (D-core-056); p_k² na F8 (DEC-096); DEC-095; auditoria reexecutada, lista toda sim salvo a tag v1.0 |
| 191B | DONE | d531ae5 | 2026-11-23 | DEC-097: reclassifica a DEC-095 (3fcdfbe é pré-resultado) |
| 192R | DONE | d531ae5 | 2026-11-23 | aprovado (V192R): lista do 191 toda sim (a tag v1.0 é produto do 192); V-03 sem violação |
| 192 | DONE | 107d1b8 (tag v1.0 = c0b7f5e) | 2026-11-23 | README Reproduzir a v1.0; MS-9 a MS-11 done; referência 8d5275d9… publicada (7 fases novas); tag anotada no remoto |
| 196 | DONE | 55694fd | 2026-11-23 | ReferenceStore.prune + scripts/prune_references.py; simulação e poda real: 29 rodadas e 110 objetos fora, 1,33 GiB liberados (references 3,5 G -> 2,2 G); latest.json e a referência 8d5275d9… intactos |
| 197 | DONE | 4a572fc | 2026-11-23 | limpeza: 11 itens D arquivados, 546 X apagados (32 MB), 25 __pycache__; o grosso (cache 6,6 GB, interim 3,8 GB, outputs) é M ou R; relatório limpeza_pos_v1_0_197.md |
| 198 | DONE | sem commit | 2026-11-23 | _notas_geofrea/GeoFREA_v1_0_explicado.md (11 seções); conferência com conferir198.py: 461 números por valor, 0 sem origem |
| 193 | [PULADO] |  | 2026-11-17 | pós-v1.0 (decisoes V193-V195) |
| 194 | [PULADO] |  | 2026-11-17 | pós-v1.0 (decisoes V193-V195) |
| 195 | [PULADO] |  | 2026-11-17 | pós-v1.0 (decisoes V193-V195) |

---

## Bloco A. Limpeza e consistência

### COMANDO 166Y: Fixar os pontos em aberto do 166Z e ajustar os textos dos comandos [DONE]

Concluído em 2026-11-17: V182b (teto 4000), V174b (H5b e T-R10 "not available"), V177b (só os itens 3 e 9) e V196b (196 após o 192) na seção 5 de `decisoes_v1_0_GeoFREA.md`; textos dos comandos 167, 174, 177, 182 e 196 ajustados. Backups: `comandos_v1_0_GeoFREA.bak02_20261117.md` e `decisoes_v1_0_GeoFREA.bak02_20261117.md`. Repositório e dados não tocados.

### COMANDO 166Z: Incorporar o arquivo de decisões ao arquivo de comandos [DONE]

Concluído em 2026-11-17: regra 14 na seção 2, vereditos e decisões Vnnn copiados nos comandos, COMANDOS 197 e 198 inseridos no bloco H2, 193 a 195 [PULADO], 196 movido para o bloco H2, seções 3 e 4 atualizadas. Backup: `comandos_v1_0_GeoFREA.bak01_20261117.md`. Repositório e dados não tocados.

### COMANDO 167: Limpeza final de GeoFREA_data, do repositório e de D:\Douglas\DOUTORADO [DONE]

Decisão: ver V167 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Liberar espaço antes das rodadas longas sem tocar em entrada ou saída de fase válida, e deixar a raiz do doutorado só com o que está em uso.
Anexos obrigatórios: GeoFREA_limpeza_candidatos_20261117.md, GeoFREA_limpeza_executada_20261117.md, GeoFREA_data/_to_delete/MOVED.json
Veredito do autor (V167: valem os padrões D1 a D9 como escritos abaixo; D3: apagar se a busca do item 4 não achar referência):
  D1 GeoFREA_data/_to_delete/ (158 arquivos, 129,6 MB): APAGAR
  D2 GeoFREA_data/references/: pendente: sem função de poda; executada pelo 196 (V196b)
  D3 D:\Douglas\DOUTORADO\_quarantine_20261030\ (1,11 GB): APAGAR se a checagem do item 4 não achar referência; senão MANTER
  D4 backups bak1 a bak12 de comandos_grupos_4_5_7_v3.md e comandos_grupos_4_5_7_v2.md: APAGAR (ficam o v3 vigente e o bak13)
  D5 no repositório: .mypy_cache, .pytest_cache, .ruff_cache e __pycache__ fora de .venv: APAGAR
  D6 GeoFREA_data/work/ (vazia): APAGAR
  D7 database/, geoworld_framework/, other/, shared-data-sources/: MANTER (só inventário)
  D8 os INCERTO restantes da 165A (relatórios antigos de audit, unattended, logs, slope counts, sensitivity_above3000m, solar_basis, epe_r1, archive/, comparison/, fixtures/, docs/_audit, scripts de uso pontual): MANTER
  D9 relatórios soltos na raiz (GeoFREA_resumo_*.md, GeoFREA_limpeza_*.md e outros .md de relatório do Code): MOVER para D:\Douglas\DOUTORADO\_notas_geofrea\
Ações:
1. Instantâneo dos manifestos (regra 3). Espaço livre de D: antes.
2. Teste de exclusão: criar e apagar um arquivo vazio em GeoFREA_data/. Se o ambiente recusar a exclusão, não insistir por outra via: todos os itens APAGAR deste comando vão para D:\Douglas\DOUTORADO\_to_delete_20261117\ com a estrutura relativa preservada e um MOVED.json (origem, destino, tamanho), e a exclusão final fica para o autor.
3. D2: localizar em core/reference_store.py (ou onde estiver) a função de poda. Se existir, rodar em modo de simulação, mostrar o que sairia e quanto libera, e então executar. Se não existir, não apagar nada de references/ à mão: relatar e marcar o item como pendente de implementação (COMANDO 196).
4. D3: buscar a string "_quarantine_20261030" e os nomes de arquivo de nível superior da pasta em todo o repositório (código, config, docs, testes, scripts) e em raw/_shared_origin/manifest.json. Qualquer ocorrência: MANTER e listar.
5. D7, somente leitura: para database/, contar quantos arquivos e GB têm cópia em GeoFREA_data/raw segundo raw/_shared_origin/manifest.json (comparar caminho de origem e tamanho; não calcular hash dos 126 GB). Para geoworld_framework/, other/ e shared-data-sources/, listar subpastas de primeiro nível com tamanho e data.
6. Aplicar D1, D4, D5, D6 e D9. Para cada item, conferir antes que existe e que nenhum manifesto o cita.
7. Verificação: os três manifest.json iguais ao instantâneo (SHA-256); prova P com 0 diferenças; git status limpo.
8. Espaço livre de D: depois.
Saída esperada: tabela por item (decisão, feito ou não, tamanho, destino), inventário do item 5, espaço antes e depois. Relatório em _notas_geofrea/limpeza_167.md.
Critério de conclusão: manifestos com o mesmo SHA-256 do instantâneo; prova P 0; git status limpo; cada D1 a D9 com estado explícito.
Modo Code: Automático
```

### COMANDO 168: Corrigir inconsistências simples dos registros [DONE]

```
Objetivo: Alinhar OPEN_QUESTIONS, PROGRESS e CONVENTIONS ao que as DEC já decidiram, antes da auditoria de prontidão. Os textos são definidos pelas DEC citadas e ficam aprovados ao enviar.
Anexos obrigatórios: DEC-063, DEC-068, DEC-069, DEC-070, DEC-075, DEC-080, DEC-083, DEC-084, OQ-010, docs/PROGRESS.json, docs/CONVENTIONS.md, config/experiments.yaml (national_targets)
Ações:
1. Conferir em config/experiments.yaml: BRA solar 90 GW (alternativa 27), 2050; IND solar 447 GW e eólica 138 GW, 2035; BRA eólica, PRT solar e PRT eólica com status no_target. Divergência: PARAR.
2. docs/OPEN_QUESTIONS.md: fechar a OQ-010 com uma linha na nota "Recently resolved", em inglês: "OQ-010 (national expansion targets) closed <data>: the targets are registered in the pre-registered subset (DEC-063, DEC-070, DEC-075, DEC-080, DEC-083, DEC-084; COMMAND 162), and the pairs without a referenced value carry status no_target (M-F7-15)." Remover a linha da tabela.
3. docs/PROGRESS.json: o item PV-77 de IND e BRA passa a fechado, citando DEC-068. Se algum teste valida a forma desse campo, ajustar só o valor permitido pelo teste; se o teste impedir, PARAR.
4. docs/CONVENTIONS.md: nas linhas que mandam o país ficar em awaiting_content_check_post_77 e nas que dizem que a decisão fica só no registro da fase (DEC-068 e DEC-069 citam l. 39, 47, 52 e 74; localizar pelo texto, não pelo número), reescrever para o estado atual: decisões do autor em docs/DECISIONS.md (DEC-nnn), decisões de implementação em docs/phases (D-*), PV-77 fechada (DEC-068). Mostrar o diff. Não mudar mais nada do arquivo.
5. Conferir em docs/PROGRESS.json se o estado de F1 a F5 e das fases de apoio dos três países bate com os manifestos (success). Divergência: listar, não corrigir.
6. Lint de docs, suíte unitária, prova P, digest (regra 5).
7. Commitar só OPEN_QUESTIONS.md, PROGRESS.json e CONVENTIONS.md, mensagem "docs: close OQ-010 and align PROGRESS and CONVENTIONS with DEC-068 and DEC-069". Push e três workflows.
Saída esperada: diff, hash, workflows, lista do item 5.
Critério de conclusão: git show --stat HEAD só com os três arquivos; lint 0; suíte sem falha; digest idêntico; HEAD igual a origin/main; três workflows success.
Modo Code: Compact
```

---

## Bloco B. Auditoria de prontidão

### COMANDO 169: Prontidão de F6 a F8 (somente leitura) [DONE]

```
Objetivo: Saber, antes de qualquer decisão ou rodada, o que o código faz de F6 a F8, quanto deve custar e o que impede a produção; e validar as premissas dos comandos 170 a 192 deste arquivo.
Anexos obrigatórios: METHODOLOGY seções 4 a 12, este arquivo inteiro, manifestos de PRT, IND e BRA, config/memory_budget.json, config/settings.yaml, config/experiments.yaml, config/parameters.json
Ações:
1. Mundo sintético: rodar `pytest tests/synthetic -m synthetic` em diretório temporário e listar as fases que executam de ponta a ponta (esperado: até results_synthesis, incluindo sample_size_convergence, robustness_analysis, cross_country_h4, external_validation, lcoe_maps, robustness_maps). Fase que não roda no ZZZ: listar (A-06 exige).
2. Auditoria de produção sem rodar fase: chamar a função de auditoria de parâmetros que `--production` usa (production.audit_parameters ou equivalente) para PRT, IND e BRA, e listar o que seria recusado (proxy true, parâmetro incerto sem faixa, valor nulo) e o que só gera aviso (Tier 3). Dizer se o O&M eólico de BRA e IND ainda é proxy (U-05, OQ-016).
3. Linha de comando: listar as opções de main.py; dizer como rodar só lcoe_modeling e sample_size_convergence; se existe modo de plano (listar fases que executariam, sem executar); como a guarda do pré-registro é ligada; o que main faz hoje para impedir rodada real acidental (L-244).
4. Tamanho e tempo: rodar scripts/size_f5_to_f8.py (ou ler o que ele calcula) e dar, por país e tecnologia, células do conjunto F7, membros da janela principal e da de sensibilidade, tamanho de amostra configurado e número de futuros. Estimar o tempo de F6, convergência e F7 por país a partir do wall_s do F5 e da complexidade do código; dizer a base da estimativa.
5. Memória: phase_caps de config/memory_budget.json para lcoe_modeling, sample_size_convergence, robustness_analysis, cross_country_h4, external_validation, lcoe_maps, robustness_maps e results_synthesis; o teto que vale para fase sem medição; memory.max_batch_gb e como F6 e F7 o usam (A-10); o que GEOFREA_MEMORY_CAPS faz. Espaço livre em D:.
6. U-04: tamanhos testados, regra de parada, limite máximo, onde o tamanho adotado é escrito (automático na configuração, no manifesto ou manual), se `sample_size` (ou o nome real) está no subconjunto pré-registrado e no escopo de fingerprint de quais fases.
7. Sensibilidades: para cada sensibilidade da M-F7-07 (H1 a H5) e da M-F7-08, dizer se o código a calcula, em qual símbolo, e se roda dentro do robustness_analysis ou exige outra invocação. Em particular: τ nas pontas do range no H5; SR com τ primário apenas ou também com as pontas; top_k 5 e 20; janela 2071-2100 (como é disparada); escala 0,1° (--scale 0p1deg cobre F3 a F7?); sem o GCM da exceção de TCR.
8. Figuras: quais fases leem settings.figures no escopo de fingerprint; mudar para all deixa quais fases stale; existe sobreposição por linha de comando.
9. Limiares de perigo: valor atual de hazard_thresholds em experiments.yaml por canal; tabela de limiares de docs/thesis/methods/grupo5.tex (valor, unidade, fonte com chave do .bib, tier, marca de verificação); se hazard_thresholds está no subconjunto pré-registrado; quais fases leem hazard_thresholds no escopo de fingerprint; se a comparação V-83 (contagens de referência do ISIMIP3b contra máxima diária do ERA5 ou W5E5, 1995-2014) já foi feita e onde está.
10. OQ-114, só disponibilidade: usinas eólicas do GEM por país (número, capacidade, com coordenada e status operacional); se raw/gwa tem camadas de capacity factor do GWA; valores de CF de frota já baixados no 161Q (arquivo, página, base, período).
11. F7b: estado da OQ-068 no código (external_validation ainda chama prepare_shared_layers?); pico estimado no BRA.
12. F8: para cada saída da seção 10 da METHODOLOGY (T-M1 a T-O3), o script ou função que a produz, ou "não implementado".
13. window_list_131: transcrever todos os itens com estado; dizer quais estão marcados para a próxima rodada completa ou janela única.
14. Premissas deste arquivo: para cada comando de 170 a 192, dizer "premissas confirmadas" ou listar premissa, fato e arquivo (regra 6 da seção 0).
15. Não alterar arquivo rastreado; nenhuma fase em dado real.
Saída esperada: relatório em _notas_geofrea/prontidao_169.md, uma seção por item.
Critério de conclusão: os 15 itens com resposta explícita (valor, símbolo, caminho ou "não encontrado"); git status igual ao do início; manifestos com o SHA-256 do início.
Modo Code: Automático
```

Se o item 14 listar contradição, o autor leva o relatório ao chat de planejamento antes do 170.

---

## Bloco C. Decisões que bloqueiam a produção

### COMANDO 170: OQ-114, diagnóstico do CF eólico das células (somente leitura) [DONE]

Decisão: ver V170 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Saber se a distância entre o CF eólico do F5 e o CF da frota é erro de modelo, diferença de definição ou não explicada, sem ajustar nada às usinas (V-06).
Anexos obrigatórios: saída do COMANDO 169 (item 10), OQ-114, L-028, L-032, L-033, M-F5-03, D-F5-001 a D-F5-041 relevantes, config/technologies.yaml, tab:g4-cf, saídas do 161Q
Ações:
1. Por país, cenário central, membro de referência: percentis 10, 50 e 90 do CF eólico das células candidatas, CF ponderado por capacidade, e o CF ponderado das células do decil superior.
2. Usinas do GEM em operação: casar cada usina com a célula de 0,05° que a contém; CF do F5 ponderado pela capacidade da usina; número de usinas e capacidade casada; usinas em célula não candidata (contar e dizer a exclusão dominante).
3. CF de frota com fonte: usar os valores do 161Q (BRA ABEEólica 2025, PRT REN 2023, IND) com base (bruto ou líquido de curtailment), período e página. Faltando, buscar por código com manifesto (regra 11).
4. Checagem independente: baixar por código, com manifesto, as camadas de capacity factor do Global Wind Atlas (classes IEC 1, 2 e 3, 100 m) dos três países, se existirem. Calcular, nas mesmas células (média ponderada pela área elegível) e com a classe IEC que o F5 atribui, o CF do GWA. Se o produto não existir ou falhar, registrar e seguir.
   Acréscimo (V170): baixar as três classes (IEC1, IEC2, IEC3) dos três países pela fonte do F1 (DTU / Banco Mundial, Global Wind Atlas 3, https://globalwindatlas.info/download/gis-files; camadas `<ISO3>_capacity_factor_IEC<n>.tif`, 100 m, 250 m, CC BY 4.0), com manifesto; se o download por país falhar, tentar a camada global da mesma fonte e recortar. Ler a documentação do GWA e informar se o CF dele já desconta perdas (esteira, disponibilidade, elétricas).
5. Cadeia do F5 em 15 células por país (5 em células com usina, 5 no decil superior, 5 na mediana): A e k na altura do cubo, correção de densidade do ar, id e classe da curva de potência, CF bruto pela integral de Weibull, eta_loss e CF final. Comparar o CF bruto com o do GWA. Conferir unidades, altura (100 contra 150 m), normalização pela potência nominal, cut-in e cut-out, e se a média da célula inclui pixels de recurso baixo.
6. Rodar os testes V-02 da integral de Weibull e dizer se cobrem o caso real (classe e altura usadas em produção).
7. Não mudar código, configuração nem parâmetro. Não ajustar nada às usinas.
Saída esperada: tabela por país (F5 nas usinas, F5 decil superior, GWA nas mesmas células, frota com base) e lista de hipóteses para a diferença, cada uma com evidência e magnitude, classificada como (A) erro de modelo com causa física, (B) diferença de definição explicada, (C) não explicada. Relatório em _notas_geofrea/oq114_170.md. PARAR para o veredito.
Critério de conclusão: todo número com caminho; manifesto com hash para cada download; git status sem arquivo rastreado alterado (scripts novos ficam não rastreados e listados).
Modo Code: Automático
```

### COMANDO 171: Registrar o veredito da OQ-114 [DONE]

Decisão: ver V171 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Fixar, antes de qualquer F6, como o eólico entra na v1.0.
Anexos obrigatórios: saída do COMANDO 170, OQ-114, DEC-088, L-028, L-032
Veredito do autor (V171): aplicar a regra de V171 sobre os números do comando anterior (170). Não há texto livre do autor.
  Definições, por país, nas células com usina e nas 15 células amostradas:
  - `g = CF_F5 / (CF_GWA × eta_loss)`, com `CF_GWA` da classe IEC que o F5 atribui à célula e `eta_loss` a retenção que o F5 aplica, para os dois ficarem na mesma base de perdas. Se a documentação do GWA disser que o CF dele já desconta perdas, usar `eta_loss = 1` na fórmula e registrar.
  - `p = CF_F5 nas células com usina (ponderado pela capacidade) / CF de frota` (só onde há frota com fonte, F4 de decisoes_v1_0_GeoFREA.md).
  Ramos, na ordem:
  1. A (erro de modelo): a cadeia do item 5 do 170 mostra um passo com defeito identificável (unidade, altura, densidade do ar, normalização da curva, cut-in ou cut-out, pdf de Weibull, média que inclui pixel inelegível) e corrigir esse passo, numa reprodução fora do repositório, leva a mediana de `g` para dentro de [0,85; 1,15]. Segue para o 172 com essa causa.
  2. B (definição explicada): a mediana de `g` já está em [0,85; 1,15] em todos os países. A diferença para a frota é então atribuída a turbina e cubo maiores na frota real que na turbina de referência da classe IEC (F1), à localização da usina dentro da célula e à base de curtailment. OQ-114 fecha como limitação.
  3. C (não explicada): nenhum dos dois. OQ-114 fecha como limitação; os valores absolutos do eólico (GW e TWh) saem na tese com ressalva explícita e a leitura principal do eólico é o ranking.
  Proibido em qualquer ramo: ajustar `eta_loss`, a curva de potência ou qualquer parâmetro aos dados de frota ou ao GWA (V-06). O GWA é checagem independente, não alvo de ajuste.
  Texto da DEC (inglês, completar com os números e o ramo):
  "DEC-nnn: Verdict on the wind cell CF (closes OQ-114 unless branch A). Date: <data>. Decided by the author through the rule of decisoes_v1_0_GeoFREA.md V171. Branch applied: <A|B|C>. Median g (F5 over GWA times eta_loss, same IEC class) BRA <x>, IND <x>, PRT <x>; p (F5 at plant cells over the fleet CF) BRA <x>, PRT <x>, IND not available (no sourced fleet CF). No parameter is fitted to the fleet or to the GWA (V-06)."
Ações:
1. Registrar DEC nova (próximo número livre, inglês) com o texto da DEC do bloco acima, completado com o ramo aplicado e os números do 170 (na DEC, registrar qual ramo foi aplicado e com quais números), e as referências.
2. Ramo B ou C: fechar a OQ-114 com ponteiro para a DEC; LIMITATIONS com o próximo L livre descrevendo a diferença medida por país e o que fica sem explicação; atualizar L-028 e L-032 só por remissão à L nova. Ramo A: manter a OQ-114 aberta até o 172C.
3. Lint, suíte, prova P, digest. Commitar DECISIONS.md, OPEN_QUESTIONS.md e LIMITATIONS.md, mensagem "docs: record the wind CF verdict (OQ-114)". Push e workflows.
Saída esperada: hash e workflows.
Critério de conclusão: git show --stat HEAD só com os arquivos citados; digest idêntico; três workflows success.
Modo Code: Compact
```

### COMANDO 172 (condicional: só se o 171 aplicou o ramo A): Corrigir o modelo eólico do F5 [PULADO]

Decisão: ver V172 de decisoes_v1_0_GeoFREA.md
Motivo: o 171 aplicou o ramo B (DEC-091), não o A; nenhum passo do F5 eólico tem defeito (V172). Os COMANDOS 172R e 172C também ficam [PULADO].

```
Objetivo: Corrigir a causa física da OQ-114 com teste que falha antes e passa depois, sem recomputar dados ainda.
Anexos obrigatórios: DEC do COMANDO 171, saída do COMANDO 170, módulos do F5 eólico
Ações:
1. Escrever o teste que reproduz o erro (fixture em diretório temporário). Rodar e mostrar a falha.
2. Corrigir só o passo identificado no 170, nada além dele (V172). Rodar o teste, a suíte unitária e `pytest tests/synthetic -m synthetic`.
3. Registrar D-F5 novo em docs/phases/F5_technical_potential.md e a regra M- correspondente na METHODOLOGY (próximo PATCH livre; changelog e PROGRESS iguais), com fonte em ABNT se a correção usar valor externo; se faltar campo da referência, PARAR.
4. Prova P em modo leitura: listar as fases que ficam stale por fingerprint de código (esperado: technical_potential, potential_maps e consumidores) e confirmar que nenhuma fase de F1 a F4 muda.
5. Digest idêntico. Não recomputar dados. Não commitar.
Saída esperada: diff, saída dos testes, lista de stale.
Critério de conclusão: teste novo falha antes e passa depois; suíte e synthetic passam; digest idêntico; stale só nas fases esperadas.
Modo Code: Automático
```

COMANDOS 172R e 172C [PULADO] (ramo B no 171): o texto abaixo só valeria no ramo A. Molde do fim do arquivo. No 172C, fechar a OQ-114 com ponteiro para a DEC do 171 e o D-F5 do 172.

### COMANDO 173: OQ-051, comparação V-83 e tabela de limiares (somente leitura) [DONE]

Decisão: ver V173 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Reunir o que o autor precisa para fixar os canais do H5b antes de qualquer resultado.
Anexos obrigatórios: saída do COMANDO 169 (item 9), OQ-051, OQ-115, DEC-065, M-F7-07 (H5b), grupo5.tex, L-229 a L-232
Ações:
1. Tabela por canal (tx35_days, tx40_days, rx5day_mm, wet_p95_exceed_freq, gust_mean_annual_max_ms): limiar proposto no grupo5.tex, unidade, fonte (chave do .bib e página), tier, marca de verificação, valor em experiments.yaml, definição do indicador em hazard_indicators (rx5day: dizer se tem).
2. V-83, se ainda não feita: para 1995-2014, por país, comparar as contagens anuais médias de dias acima de 35 e de 40 °C do ISIMIP3b (referência) com as do ERA5 e as do W5E5 nas mesmas células; dar mediana e percentis 10 e 90 da diferença e a fração de células com diferença acima de 5 dias por ano. Dizer que o W5E5 é o alvo da correção de viés do ISIMIP3b e por isso é concordante por construção; o ERA5 é a comparação independente.
3. Não calcular a fração de células ou de energia exposta a nenhum limiar: o limiar tem de vir da fonte, não do efeito.
   Acréscimo (V173) ao item 2: a comparação V-83 usa as células candidatas do cenário central (eólico e solar separados) e dá também a mediana do ERA5 por país.
4. Não alterar arquivo rastreado.
Saída esperada: tabela do item 1, resultado do item 2, relatório em _notas_geofrea/oq051_173.md. PARAR para o veredito.
Critério de conclusão: cinco canais com linha completa ou "não encontrado"; git status sem alteração rastreada.
Modo Code: Automático
```

### COMANDO 174: Registrar a ausência de limiar do H5b e fechar a OQ-051 e a OQ-115 [DONE]

Decisão: ver V174 e V174b de decisoes_v1_0_GeoFREA.md (a V174b prevalece: nenhum canal tem limiar com fonte)

```
Objetivo: Fixar, antes do primeiro F6, que o conjunto de canais do H5b da v1.0 é vazio, como a M-F7-07 exige que o conjunto seja fixado antes de qualquer resultado.
Anexos obrigatórios: saída do COMANDO 173, OQ-051, OQ-115, DEC-065, grupo5.tex
Veredito do autor (V174b): nenhum canal tem limiar com fonte no grupo5.tex.
  | Canal | Limiar | Situação |
  | tx35_days | null | excluded from H5b by DEC-nnn |
  | tx40_days | null | excluded from H5b by DEC-nnn |
  | rx5day_mm | null | excluded from H5b by DEC-nnn |
  | wet_p95_exceed_freq | null | excluded from H5b by DEC-nnn |
  | gust_mean_annual_max_ms | null | excluded from H5b by DEC-nnn (contexto, DEC-065) |
  H5b e T-R10 ficam "not available" na v1.0, registrados como resultado do procedimento (DEC e L nova). OQ-051 fecha com ponteiro. Limiar acrescentado depois da v1.0 é análise exploratória rotulada.
  OQ-115: a coluna de tier da tab:g5-ind mostra o tier da definição do indicador; rx5day ganha definição em hazard_indicators como o Rx5day do ETCCDI, anual (ZHANG, X. et al. Indices for monitoring changes in extremes based on daily temperature and precipitation data. WIREs Climate Change, v. 2, n. 6, p. 851-870, 2011); acrescentar a entrada ao .bib se não existir.
  grupo5.tex: ajustar a tab:g5-ind e acrescentar uma frase dizendo que nenhum limiar de exposição com fonte foi registrado e que H5b não é avaliado na v1.0.
  Proibido calcular fração exposta antes de gravar o veredito (item 3 do 173).
Ações:
1. config/experiments.yaml: `hazard_thresholds` continua `threshold: null` nos cinco canais, cada um com a nota "excluded from H5b by DEC-nnn" (nenhum valor de limiar, fonte ou tier inventado). `hazard_indicators`: acrescentar `rx5day_mm` com a definição do índice Rx5day do ETCCDI (máximo anual da precipitação acumulada em 5 dias consecutivos, mm), fonte Zhang et al. (2011). Se o esquema de `hazard_indicators` recusar a chave: PARAR.
2. Digest: se mudar, PARAR e reverter.
3. DEC nova (inglês) com a tabela acima, a data, o commit da tag prereg-v1 e a frase: "The hazard channel set of H5b is fixed after the pre-registration tag and before any F6 or F7 result." Registrar que nenhum canal tem limiar com fonte no grupo5.tex (V174b) e que H5b e T-R10 ficam "not available" na v1.0 como resultado do procedimento.
4. LIMITATIONS, próximo L livre: nenhum limiar de exposição com fonte foi registrado; H5b e T-R10 não são avaliados na v1.0; canais excluídos (os cinco); limiar acrescentado depois da v1.0 é análise exploratória rotulada.
5. METHODOLOGY, próximo PATCH livre: na M-F7-07 (H5b), o conjunto de canais da v1.0 é vazio, com a DEC. OQ-051 e OQ-115 fechadas com ponteiro. grupo5.tex: ajustar a tab:g5-ind (coluna de tier = tier da definição), a definição do rx5day e a frase da ausência de limiar; .bib: entrada Zhang et al. (2011) se não existir; mostrar o diff.
6. Listar as fases com manifesto que ficam stale por essas chaves (esperado: hazard_context dos três países, por `hazard_indicators`; recomputadas no 178).
7. Lint, suíte, prova P (stale só do item 6), digest. Commitar experiments.yaml, DECISIONS, OPEN_QUESTIONS, LIMITATIONS, METHODOLOGY, PROGRESS, grupo5.tex e o .bib, mensagem "feat(config): record that no H5b hazard channel has a sourced threshold (OQ-051, OQ-115)". Push e workflows.
Saída esperada: diff, lista de stale, hash, workflows.
Critério de conclusão: git show --stat HEAD só com os arquivos citados; digest idêntico; versão da METHODOLOGY igual nos três lugares; três workflows success.
Modo Code: Compact
```

### COMANDO 175: Fechar a OQ-094 sem eixo novo [DONE]

Decisão: ver V175 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Definir as sensibilidades de τ, cf_min, q_ref e top_k da v1.0 com o que o código já calcula, sem mudar o subconjunto pré-registrado. O texto da DEC é aprovado ao enviar; se o autor discordar, editar antes.
Anexos obrigatórios: saída do COMANDO 169 (item 7), DEC-061, DEC-074, DEC-085, DEC-088, DEC-089, DEC-090, OQ-008, OQ-020, OQ-094, M-F7-04, M-F7-07
Ações:
1. Conferir com o item 7 do 169: (i) H5 avalia τ nas duas pontas do range registrado; (ii) top_k 5 e 20 em H1 a H4; (iii) SR usa só o τ primário. Se (i) ou (ii) não for verdade, PARAR. Se (iii) for falso, ajustar a frase a) ao que o código faz e mostrar.
2. Registrar DEC nova (próximo número livre):

DEC-nnn: Sensitivity axes of tau, cf_min, q_ref and top_k in v1.0 (closes OQ-094)
Date: <data>. Decided by the author.
a) tau: the sensitivity is the two ends of the registered range (tau_min, tau_max), evaluated in H5 as implemented (DEC-090 a). Satisficing robustness SR uses the primary tau.
b) top_k: 5 and 20 percent beside the primary 10 (DEC-085 d), in H1 to H4 as M-F7-07 states.
c) cf_min: no sensitivity in the primary analysis. The solar floor of 0.115 excludes 0 cells in PRT and BRA and 127 of 93,701 in IND (DEC-089 b), so a sweep would not change the candidate set materially. A wind floor is post hoc, after OQ-114 (DEC-088 b).
d) q_ref: no sensitivity; q_ref = 0 (DEC-074). OQ-020 stays an optional exploratory analysis outside v1.0.
e) No configuration key is created; the pre-registered digest does not change.
Substitui: nenhuma decisão; completes DEC-061 (the sweep it announced is the one above).

3. METHODOLOGY, próximo PATCH livre: nova regra M-F7 com o conteúdo da DEC, citando-a. OPEN_QUESTIONS: fechar a OQ-094 e a OQ-008 (todas as partes resolvidas: DEC-085, DEC-088, DEC-089, DEC-090, DEC-083, DEC-084 e esta) com ponteiro.
4. Lint, suíte, prova P, digest. Commitar DECISIONS, OPEN_QUESTIONS, METHODOLOGY e PROGRESS, mensagem "docs: close OQ-094 and OQ-008 (sensitivity axes of v1.0)". Push e workflows.
Saída esperada: hash, workflows, digest.
Critério de conclusão: git show --stat HEAD só com os quatro arquivos; digest idêntico; versão igual nos três lugares; três workflows success.
Modo Code: Compact
```

---

## Bloco D. Trava e janela única

### COMANDO 176: Trava contra rodada real acidental e modo de plano [DONE] (sem commit; aguarda 176R e 176C)

Decisão: ver V176 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Impedir que F6 em diante rode em país real sem pedido explícito (o incidente do 162B) e permitir ver o que uma invocação faria antes de rodar.
Anexos obrigatórios: saída do COMANDO 169 (item 3), L-244, main.py, scripts/run_unattended.ps1
Ações:
1. Se o 169 mostrou que a trava já existe, marcar o comando [PULADO] e seguir para o 177.
2. main.py: recusar executar lcoe_modeling, sample_size_convergence, robustness_analysis, cross_country_h4, external_validation, lcoe_maps, robustness_maps e results_synthesis num país não sintético sem a opção `--real-run`. A mensagem lista as fases recusadas. A guarda do pré-registro continua valendo com a opção.
3. Se o modo de plano não existir: `--plan` imprime, por país, as fases que executariam, as retomadas do manifesto e as stale, com o motivo, sem executar e sem escrever manifesto.
4. run_unattended.ps1: repassar `--real-run` quando a invocação pedir F6 em diante.
5. Testes: sem a opção, recusa; com a opção, a guarda roda; país sintético não exige a opção; `--plan` não escreve nada.
6. Confirmar que main.py não entra em nenhum fingerprint: prova P com 0 diferenças. Digest idêntico.
7. Atualizar L-244 (uma frase: a trava de main.py cobre a rodada acidental; as lacunas da guarda seguem) e a seção de execução do docs/PIPELINE_GUIDE.md e do README.
8. Não commitar.
Saída esperada: diff e testes.
Critério de conclusão: testes do item 5 passam; suíte e synthetic passam; prova P 0; digest idêntico.
Modo Code: Automático
```

COMANDOS 176R e 176C: seguir o molde.

### COMANDO 177: Janela única, edições que mexem em fingerprint de F1 a F5 [DONE] (sem commit; aguarda 177R e 177C)

Decisão: ver V177 e V177b de decisoes_v1_0_GeoFREA.md

```
Objetivo: Aplicar de uma vez, antes do F6, as edições adiadas para a próxima rodada completa, para que a recomputação aconteça uma vez só.
Anexos obrigatórios: saída do COMANDO 169 (item 13), docs/_audit/window_list_131.md, OQ-084, OQ-109, diff do 172 se houver
Ações:
1. Aplicar só os itens 3 e 9 da window_list_131 (V177b), exatamente como a lista descreve; listar os demais itens com o motivo de ficarem fora. Item que dependa de recomputação de ERA5 (OQ-078) fica fora.
1b. Não se aplica (V177b): o O&M eólico de BRA e IND já vem do IRENA 2024, com proxy false (achado do 169).
1c. Gravar `sampler.max_size_for_convergence = 4000` em config/experiments.yaml com a fonte "author judgment, Tier 3" (sequência 500, 1000, 2000, 4000) e acrescentar a L nova (V182b): "U-04 ceiling of 4000 is the author's judgment, Tier 3". Digest idêntico; se mudar, PARAR e reverter.
1d. Acrescentar o modelo do `rx5day_mm` em `HazardIndicators` (src/geofrea/core/config_schemas.py) e a chave `rx5day_mm` em `hazard_indicators` de config/experiments.yaml (índice Rx5day do ETCCDI, anual; Zhang et al., 2011; DEC-093), com teste que falha antes e passa depois. O stale esperado é `hazard_context` nos três países, recomputada no 178. Qualquer outra fase que fique stale: PARAR. Digest idêntico.
2. OQ-109: fechar com o texto "OQ-109 closed <data>: the note-only change is accepted with the recomputation of the single window (COMMANDS 177 and 178); no rebaseline proof is added." (aprovado ao enviar).
3. OQ-084: não restampar agora; o restamp para parquet2 é feito no 178 depois da rodada, como a decisão de 2026-11-12 manda.
4. Prova P em modo leitura: listar, por país, as fases stale e o motivo (config, código, upstream). Somar o wall_s registrado dessas fases para estimar a duração do 178.
5. Digest idêntico. Não recomputar. Não commitar.
Saída esperada: diff, tabela de stale por país com motivo e a estimativa de duração.
Critério de conclusão: só fases com motivo explicado pelos itens 1, 1c e 1d ou 174 aparecem stale (esperado: hazard_context); digest idêntico; suíte passa.
Modo Code: Compact
```

COMANDOS 177R e 177C: seguir o molde. No 177C, a OQ-109 fecha no mesmo commit.

### COMANDO 178: Recomputar as fases stale de F1 a F5 e publicar a referência [DONE] (commit c934d71)

```
Objetivo: Deixar F1 a F5 limpos nos três países com todas as edições da janela, antes do F6.
Anexos obrigatórios: saída do COMANDO 177, lista de stale, baseline GeoFREA_data/_baselines/prereg_162F_baseline_20261117.json
Ações:
1. Instantâneo (regra 3). Rodar `--plan` (se existir) e conferir que só as fases do 177 executariam.
2. Recomputar as fases stale em PRT, depois IND, depois BRA. Registrar a regra 7.
3. Comparar o content_sha256 de cada artefato com o anterior: fase que mudou só por nota tem de ter conteúdo idêntico; diferença só é aceita onde o 172 ou o 174 a explicam. Qualquer outra diferença: PARAR.
4. Se o 172 rodou: imprimir de novo, para o eólico, os percentis do CF e o CF nas células com usina, no formato do 170.
5. OQ-084: restampar as entradas parquet: restantes para parquet2: com scripts/restamp_parquet2.py, com a prova por entrada; fechar a OQ-084 com ponteiro.
6. Publicar a referência com `python main.py --publish-reference` (ou scripts/publish_reference.py) para os três países. Recusa do portão: PARAR com o relatório.
7. Prova P: nenhuma fase stale de F1 a F5 nos três países. Digest idêntico.
8. Commitar OPEN_QUESTIONS e PROGRESS (e o que o restamp versionar), mensagem "chore(data): single-window recomputation of F1 to F5 and parquet2 restamp". Push e workflows.
Saída esperada: tabela por fase e país (wall_s, peak, conteúdo igual ou diferente com motivo), id da referência publicada, hash.
Critério de conclusão: prova P limpa nos três países; referência publicada; digest idêntico; três workflows success.
Modo Code: Automático
```

---

## Bloco E. F6 e convergência

### COMANDO 179: Produção do PRT, lcoe_modeling e sample_size_convergence [DONE] (sem commit; item 4 com tolerância 0,005, aceita pelo autor)

Decisão: ver V179 (grupo V179, V180, V181) de decisoes_v1_0_GeoFREA.md

```
Objetivo: Primeira produção de F6 no menor país, para medir custo e sanidade antes de IND e BRA.
Anexos obrigatórios: saídas dos COMANDOS 169 e 178, M-F6-01 a M-F6-12, U-04, config/irena_reference.yaml, scripts/calibrate_tau_irena.py
Ações:
1. Instantâneo. `--plan` para PRT com as duas fases.
2. Rodar `python main.py PRT --phases lcoe_modeling,sample_size_convergence --real-run --production` (ajustar as opções ao que o 169 mostrou). Se `--production` recusar parâmetro não coberto pelo item 1b do 177 (V179), PARAR com a lista. Regra 7.
3. Sanidade do F6, por tecnologia: células com LCOE contra candidatas; excluídas por motivo (distância ausente, zona térmica ausente); fração e capacidade com long_distance; contagem de valores não finitos; percentis 5, 50 e 95 do LCOE nominal; fração de células e de capacidade com LCOE nominal <= τ primário; road_cost_excluded registrado na proveniência.
4. Consistência do kernel: rodar o kernel do F6 na célula de referência do calibrate_tau_irena.py para PRT e conferir que reproduz o τ primário (54,53 e 49,64) com tolerância 1e-6.
5. Convergência: tamanhos, 1 - Jaccard de cada par consecutivo, tamanho que a regra da U-04 daria para PRT, tempo por tamanho.
6. Não alterar código nem configuração. Falha: PARAR (regra 7).
Saída esperada: relatório em _notas_geofrea/producao_PRT_179.md com os itens 2 a 5.
Critério de conclusão: as duas fases com success no manifesto do PRT; digest_live igual a digest_tag; kernel reproduz τ na tolerância; itens 3 e 5 completos.
Modo Code: Automático
```

### COMANDO 180: Produção da IND, lcoe_modeling e sample_size_convergence [DONE] (sem commit; regra de memória não aplicada)

Decisão: ver V180 (grupo V179, V180, V181) de decisoes_v1_0_GeoFREA.md

```
Objetivo: Repetir o 179 na Índia e obter a segunda medida de custo para estimar o BRA.
Anexos obrigatórios: saída do COMANDO 179
Ações:
1. Itens 1 a 6 do COMANDO 179 com IND (τ de referência 28,26 e 36,43).
2. Estimar o wall_s e o pico do BRA para as duas fases por proporção de células e futuros, com PRT e IND; comparar com o teto que vale para essas fases. Regra de memória (V179 a V181): se o pico estimado do BRA de uma fase passar de 1,25 vez o teto dela, gravar em `config/memory_budget.json` o teto da fase como ceil(1,25 × pico estimado), arredondado para cima a 64 MB, limitado à memória física da máquina menos 4 GB. Se o limite físico não comportar, reduzir `memory.max_batch_gb` à metade (repetir enquanto preciso, até 4 vezes) e aceitar que lcoe_modeling de PRT e IND fique stale e rode de novo. Registrar como D-F6 com os números. Depois de 4 reduções sem caber: PARAR.
Saída esperada: relatório em _notas_geofrea/producao_IND_180.md, a estimativa do BRA e o D-F6 de memória se a regra foi aplicada.
Critério de conclusão: as duas fases com success na IND; digests iguais; estimativa do BRA com a base declarada.
Modo Code: Automático
```

Se a estimativa do 180 pedir mudança de teto ou de lote, aplica-se a regra de memória do item 2 do 180 (V179 a V181), sem decisão do autor; só depois de 4 reduções sem caber: PARAR.

### COMANDO 181: Produção do BRA, lcoe_modeling e sample_size_convergence (janela longa) [DONE] (sem commit; max_batch_gb 0,5 pendente de commit)

Decisão: ver V181 (grupo V179, V180, V181) de decisoes_v1_0_GeoFREA.md

```
Objetivo: Completar F6 e convergência nos três países.
Anexos obrigatórios: saídas dos COMANDOS 179 e 180, D-F6 de memória do 180 se a regra foi aplicada
Ações:
1. Instantâneo. Avisar o autor da duração estimada antes de começar.
1b. Memória (V181): se o 180 já aplicou a regra de memória, conferir `config/memory_budget.json`; senão, aplicar a regra do item 2 do 180 (V179 a V181) ao pico estimado do BRA de cada fase, antes de rodar.
2. Rodar pelo scripts/run_unattended.ps1 (ou pelo main, se o 169 indicar) com `--real-run --production`. Acompanhar e registrar a regra 7.
3. Parada por teto de memória: PARAR com o pico, o teto e a fase.
4. Itens 3 e 5 do COMANDO 179 para o BRA (τ de referência 43,97 e 31,95 no item 4).
Saída esperada: relatório em _notas_geofrea/producao_BRA_181.md.
Critério de conclusão: as duas fases com success no BRA; digests iguais.
Modo Code: Automático
```

### COMANDO 182: Tamanho de amostra adotado (U-04) [DONE] (commit 86fabd8)

Decisão: ver V182 e V182b de decisoes_v1_0_GeoFREA.md

```
Objetivo: Aplicar a regra mecânica da U-04 sobre os três países e fixar o tamanho do F6 final.
Anexos obrigatórios: saídas dos COMANDOS 179 a 181, U-04, L-239, saída do 169 (item 6)
Ações:
1. Por país e tecnologia: primeiro par consecutivo com 1 - Jaccard < 0,01 e o maior tamanho desse par. Tamanho adotado = o maior entre os seis. Se algum par não convergir até sampler.max_size_for_convergence = 4000 (V182b), aplicar a regra do V182: adotar o maior tamanho testado, registrar L nova ("U-04 not met for <pares>; adopted the largest tested size, <N>; 1 - Jaccard at that size <valores>") e seguir, sem PARAR.
2. Comparar com o tamanho configurado hoje.
3. Igual: registrar D-F6 novo em docs/phases/F6_lcoe_modeling.md com a tabela do item 1 e o valor; nada muda na configuração.
4. Diferente: se a chave estiver no subconjunto pré-registrado, PARAR (mudaria o digest). Se não estiver, alterar a configuração, registrar o D-F6 e listar as fases que ficam stale (esperado: lcoe_modeling dos três países e o que mais o 169 apontou).
5. Lint, suíte, prova P (stale do item 4 apenas), digest. Commitar só os arquivos tocados, mensagem "feat(f6): adopt the converged sample size (U-04)". Push e workflows.
Saída esperada: tabela do item 1, valor adotado, stale, hash.
Critério de conclusão: valor adotado registrado no D-F6; digest idêntico; três workflows success.
Modo Code: Compact
```

---

## Bloco F. F7 e H4

### COMANDO 183: Produção do PRT, robustness_analysis [DONE] (commit 3fcdfbe)

```
Objetivo: Primeiro F7 de produção, com as invariantes conferidas antes de ler resultado.
Anexos obrigatórios: saída do COMANDO 182, M-F7-01 a M-F7-11, V-03
Ações:
1. Instantâneo. `--plan`. Rodar `python main.py PRT --phases lcoe_modeling,robustness_analysis --real-run --production` (o F6 roda de novo só se o 182 o deixou stale). Regra 7.
2. Invariantes V-03 sobre as tabelas: r >= 0; MR >= 0; ao menos uma célula viável com r = 0 por futuro; 0 <= SR <= 1; ranqueadas mais climate-fragile = conjunto F7; nenhuma ranqueada com MR infinito.
3. Contagens: conjunto F7, ranqueadas, climate-fragile, climate-data-invalid, incomplete-ensemble; k de cada top_k; top_k_truncated.
4. Tabelas da M-F7-11 presentes; para H1 a H5, imprimir estatística primária, referência e veredito (H5 do PRT: esperado "not testable", no_target); H5b (R_exp) e T-R10: "not available" na v1.0 (V174b), não é violação nem falha; PRIM: status e caixa escolhida.
5. Não interpretar nem alterar nada. Falha de invariante: PARAR.
Saída esperada: relatório em _notas_geofrea/producao_PRT_183.md.
Critério de conclusão: robustness_analysis success; digests iguais; V-03 sem violação; tabelas da M-F7-11 presentes.
Modo Code: Automático
```

### COMANDO 184: Produção da IND, robustness_analysis [DONE] (sem commit)

```
Objetivo: F7 da Índia.
Anexos obrigatórios: saída do COMANDO 183
Ações:
1. Itens 1 a 5 do COMANDO 183 com IND. No item 4, H5 é testável nos dois pares (447 GW e 138 GW, 2035); H5b (R_exp) "not available" (V174b).
2. Estimar wall_s e pico do F7 no BRA, como no 180.
Saída esperada: relatório em _notas_geofrea/producao_IND_184.md e estimativa do BRA.
Critério de conclusão: como no 183, para a IND.
Modo Code: Automático
```

### COMANDO 185: Produção do BRA, robustness_analysis (janela longa) [DONE]

Decisão: ver V185 de decisoes_v1_0_GeoFREA.md

```
Objetivo: F7 do Brasil.
Anexos obrigatórios: saídas dos COMANDOS 183 e 184
Ações:
1. Itens 1 a 5 do COMANDO 183 com BRA, pelo run_unattended se o 169 indicar. H5 testável só no solar (90 GW, 2050).
1b. Memória (V185): mesma regra de memória do V179 a V181 (item 2 do 180), aplicada ao pico estimado do BRA no F7 (estimativa do 184), antes de rodar.
2. Parada por teto: PARAR com pico, teto e fase.
Saída esperada: relatório em _notas_geofrea/producao_BRA_185.md.
Critério de conclusão: como no 183, para o BRA.
Modo Code: Automático
```

### COMANDO 186: cross_country_h4 [DONE]

```
Objetivo: Veredito do H4 por tecnologia a partir dos perfis dos três países.
Anexos obrigatórios: saídas dos COMANDOS 183 a 185, M-F7-07 (H4)
Ações:
1. Rodar a fase cross_country_h4 (como o 169 indicou). Regra 7.
2. Conferir: h4_verdict de solar e de eólica; perfis por país iguais aos h4_country de cada manifesto; contagem por perfil; manifesto próprio em outputs/cross_country/.
3. Commitar só PROGRESS.json com o estado de F6, convergência, F7 e cross_country_h4, mensagem "docs(progress): F6 and F7 production done". Push e workflows.
Saída esperada: tabela do veredito por tecnologia e hash.
Critério de conclusão: fase success; perfis iguais aos dos países; três workflows success.
Modo Code: Compact
```

---

## Bloco G. Validação, mapas, sensibilidades e síntese

### COMANDO 187: F7b por janelas de linhas (OQ-068) [DONE] (187R aprovado; 187C commit)

Decisão: ver V187 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Fazer o F7b do BRA caber no teto de memória antes da produção, com resultado idêntico ao da versão de grade inteira.
Anexos obrigatórios: OQ-068, saída do 169 (item 11), land_eligibility/windows.py, external_validation/pipeline.py, docs/_audit/f3_memory_90.md
Ações:
1. Se o 169 mostrou que o F7b já lê por janelas, marcar [PULADO].
2. Avaliar os pixels das usinas pelas janelas de linhas do F3 (StripeInputs, ScenarioStripes) ou só pelas janelas em torno das usinas; manter as funções de grade inteira como oráculo dos testes.
3. Testes de equivalência com tolerância 0 no ZZZ e numa fixture com usinas em várias faixas; medir o pico no estilo de scratchpad/f3_profile2.py e informar.
4. Suíte, synthetic, prova P (só external_validation pode mudar de fingerprint de código; não há manifesto real dela ainda), digest. Não commitar.
Saída esperada: diff, testes, pico medido.
Critério de conclusão: equivalência exata; suíte e synthetic passam; nenhuma fase com manifesto real fica stale.
Modo Code: Automático
```

COMANDOS 187R e 187C: seguir o molde. No 187C, a OQ-068 fecha com ponteiro.

### COMANDO 188: Produção de external_validation, lcoe_maps e robustness_maps [DONE] (completo pelo 188A, commit c7af733 e f887e55)

```
Objetivo: Completar as fases de validação e de mapas nos três países e fixar os tetos de memória medidos.
Anexos obrigatórios: saídas dos COMANDOS 179 a 187, M-F7b-01 a M-F7b-04, config/published_potential.yaml, config/memory_budget.json
Ações:
1. Instantâneo. Rodar as três fases em PRT, IND e BRA, nessa ordem. Regra 7.
2. F7b: tabela M-F7b-01 por restrição; razão de enriquecimento M-F7b-02; tabela M-F7b-03 com as 4 entradas registered e as 9 pending sem valor nem razão; conferir que nenhum número é calculado com entrada pending.
3. Mapas: contagem de arquivos por fase e país contra a lista da seção 11; cada COG abre e tem CRS EPSG:4326.
4. Tetos: com os picos medidos no BRA (179 a 188), aplicar a regra da A-02 (ceil de 1,25 vez o pico, arredondado para cima a 64 MB) a cada fase nova em config/memory_budget.json. Conferir que o arquivo não entra em fingerprint (prova P 0).
5. Commitar memory_budget.json e PROGRESS.json, mensagem "chore(memory): caps measured for F6 to F7b". Push e workflows.
Saída esperada: tabelas do F7b por país, contagem de mapas, tabela de tetos, hash.
Critério de conclusão: três fases success nos três países; nenhuma razão com entrada pending; prova P 0; três workflows success.
Modo Code: Automático
```

### COMANDO 188A: Células sem LCOE no F7b (mesma regra da L-253) e retomada do 188 [DONE]

Decisão do autor: tirar do enrichment do F7b as células sem LCOE do F6 (solar PRT 1, IND 84, BRA 520; D-F7b-009); teto de external_validation elevado (BRA 3.093 MB, teto 3.904 MB). Commits c7af733 e f887e55; três workflows success.

### COMANDO 189: Rodadas de sensibilidade de janela (2071-2100) e de escala (0,1°) [DONE] (commit c7685f0)

Decisão: ver V189 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Produzir as linhas de sensibilidade da T-R6 (janela 2071-2100 e escala 0,1°, V-07) que a F8 lê quando existem.
Anexos obrigatórios: saída do 169 (item 7), M-F3-06, V-07, M-F7-07
Ações:
1. Janela 2071-2100: obrigatória na v1.0 (V189). Se o 169 mostrou que a janela 2071-2100 já sai dentro do robustness_analysis, só conferir que as tabelas existem e pular para o item 3.
2. Senão, rodar a janela de sensibilidade como o 169 indicou, nos três países. Regra 7.
3. Escala: `python main.py <ISO> --scale 0p1deg` de F3 a F7, PRT, IND e BRA, com `--real-run`. Manifestos manifest__0p1deg.json. Escala 0,1° (V189): rodar se o código suportar F6 e F7 nessa escala sem mudança. Se não suportar, não implementar na v1.0 e não PARAR: registrar L nova ("V-07 scale check not run for F6 and F7 in v1.0"), as linhas de 0,1° da T-R6 saem "not available" e a implementação vai para depois da v1.0.
4. Se a escala rodou, conferir V-03 nas saídas de escala e listar, por país e tecnologia, as estatísticas de H1 a H3 lado a lado com a escala de 0,05°.
5. Commitar só PROGRESS.json. Push e workflows.
Saída esperada: tabela lado a lado, wall_s e picos.
Critério de conclusão: rodadas success (janela 2071-2100 sempre; escala 0,1° se suportada, senão a L nova registrada); manifestos de escala gravados quando rodou; digests iguais em toda entrada de F6 e F7.
Modo Code: Automático
```

### COMANDO 189A: Fechar V-03, digest e --production nas rodadas de 0,1° [DONE] (commit 3af7ce5)

V-03 sem violação nas tabelas de 0,05° e 0,1° (24 conjuntos); digest_live igual a digest_tag nos seis manifestos; `--production` só audita e recusa (`core.production.audit_parameters`, `enforce_production`), nada rodou de novo. Três workflows success.

### COMANDO 190A: Separar os JSON-resumo por escala e recuperar os de 0,05° [DONE] (commit 0bc6a64)

Causa em `main._register_json_artifact` (D-core-055). 16 resumos de 0,05° recuperados com o sha256 registrado (7 de references/objects, 9 de phases.<fase>.output), nenhum rerun; resumos de 0,1° em `artifacts__0p1deg`; zero divergência nos seis manifestos; três workflows success.

### COMANDO 190B: Teto medido para results_synthesis e conclusão do 190 [DONE] (commit c632831)

BRA com os limites desligados: pico 2.814 MB; teto 3.520 MB em config/memory_budget.json. Parou no item 2 (limite de física menos 4 GB), substituído pela V179c no 190C.

### COMANDO 190C: Corrigir a regra de memória (V179-V181) e concluir o 190B [DONE] (commit c632831)

V179c nas decisões; L-254; teto de 3.520 MB; tabela das T-* e perfis conferidos (docs/_audit/2026-11_f8_thesis_build_190.md); 105 tabelas e 45 figuras compilam (0 erros, 0 referências indefinidas); OQ-098 fechada; três workflows success.

### COMANDO 190: results_synthesis com as saídas da tese e compilação do LaTeX (OQ-098) [DONE] (commit c632831)

Decisão: ver V190 de decisoes_v1_0_GeoFREA.md

```
Objetivo: Gerar todas as saídas essenciais da seção 10 da METHODOLOGY e provar que as tabelas e figuras compilam.
Anexos obrigatórios: saída do 169 (itens 8 e 12), M-F8-01 a M-F8-03, seção 10 da METHODOLOGY
Ações:
1. Figuras completas: usar a sobreposição por linha de comando se existir. Regra (V190): se as figuras da tese (T-*) não dependem de `settings.figures`, manter `summary`. Se dependem e a troca para `all` deixa stale só fases de mapas (overview, climate_maps, potential_maps, lcoe_maps, robustness_maps), trocar para `all` e regenerar essas fases. Se deixar stale alguma fase que não seja de mapa: manter `summary` e PARAR.
2. Rodar results_synthesis para PRT, IND e BRA com `--real-run`. Regra 7.
3. Para cada T-* essencial (T-M1 a T-R12 e T-O3): caminho, hash e "gerado", "not available (V174b)" ou "faltando". "Not available (V174b)" só vale para a T-R10 e para a linha R_exp da T-R6; qualquer outra T-* faltando: PARAR com a lista.
4. hypothesis_profiles: conferir schema_version, um registro por país e tecnologia, e os rótulos consistent, context-dependent ou not assessable da M-F8-03.
5. Compilar as tabelas .tex e incluir as figuras PDF num documento de teste com o motor TeX local (como no 165); zero erro, zero referência indefinida. Fechar a OQ-098 com ponteiro.
6. Commitar OPEN_QUESTIONS e PROGRESS, mensagem "feat(f8): thesis outputs generated and compiled (OQ-098)". Push e workflows.
Saída esperada: tabela do item 3, log da compilação, hash.
Critério de conclusão: todas as T-* essenciais geradas (T-R10 "not available", V174b); compilação sem erro; três workflows success.
Modo Code: Automático
```

---

## Bloco H. Auditoria final e congelamento

### COMANDO 191: Auditoria final da pipeline v1.0 (somente leitura) [DONE]

```
Objetivo: Produzir o relatório que o autor leva ao chat de planejamento para conferir se o plano foi cumprido.
Anexos obrigatórios: este arquivo com a seção 4 preenchida, manifestos dos três países, de cross_country e de escala, relatórios de _notas_geofrea/
Ações:
1. Estado: por país e fase (F1 a F8 e apoio), status, finished_at, wall_s, cpu_s, peak_rss_mb, memory_cap_mb; prova P sem stale; manifestos de escala.
2. Pré-registro: digest_live igual a digest_tag em toda entrada de lcoe_modeling, sample_size_convergence e robustness_analysis; tag prereg-v1 em ccf764f no remoto.
3. Repositório: HEAD igual a origin/main; três workflows success; suíte unitária e synthetic; lint.
4. Saídas da tese: tabela T-* com caminho e hash.
5. Resultados, só números lidos dos artefatos, sem interpretar: por país e tecnologia, potencial (GW, TWh) nos três cenários de solo, LCOE nominal p50, fração de capacidade com LCOE <= τ, tamanho do conjunto F7 e k, H1 (C_k, V_k, p_k², veredito), H2 (O, O_ref, veredito), H3 (D, D_ref, Pi, B, veredito), H4 (D_clim, D_tec, rho, perfil) e veredito do H4 por tecnologia, H5 (E_0, G, H_0, R_loss, R_exp, veredito; R_exp "not available" por V174b), PRIM (status, densidade, cobertura), F7b (resumo das três tabelas).
6. Desvios: toda DEC posterior à tag prereg-v1, com rótulo (pré-resultado ou post-result correction).
7. Pendências: OQs abertas, classificadas em "bloqueia o texto da tese", "não bloqueia" e "depois da v1.0", com uma linha de motivo cada; marcas \vfy, % verify e % open dos .tex; entradas % verify e % agent do .bib.
8. Lista de conferência da v1.0 (seção 1, item 1) com sim ou não por critério.
9. Não alterar nada.
Saída esperada: D:\Douglas\DOUTORADO\_notas_geofrea\auditoria_pipeline_v1_0.md.
Critério de conclusão: os 9 itens preenchidos; todo número com caminho de origem; git status e manifestos iguais ao início.
Modo Code: Automático
```

### COMANDO 191A: Corrigir o cross_country de vez, reconstruir as saídas e fechar as pendências do 191 [DONE] (commit fa090bb)

Causa e correção em D-core-056 (`main.h4_countries`, `main.require_h4_inputs`, guarda da F8); p_k² na F8 (DEC-096, METHODOLOGY 19.4.15); DEC-095; seção 4 e PROGRESS preenchidos; auditoria reexecutada. O COMANDO 188B não existe em nenhum registro (arquivo de comandos, decisões, código, testes, git): a exigência final do item 2 foi implementada e testada. Três workflows success.

### COMANDO 191B: Reclassificar a DEC-095 [DONE]

DEC-097 registrada (Substitui: o rótulo da DEC-095); item 6 de auditoria_pipeline_v1_0.md atualizado.

### COMANDO 192R: Aprovação do congelamento [DONE]

Decisão: ver V192R de decisoes_v1_0_GeoFREA.md

```
Objetivo: O autor aprova a v1.0 com base no relatório do 191.
Anexos obrigatórios: saída do COMANDO 191
Ações:
1. Resumo em até 10 linhas: critérios atendidos, critérios não atendidos, desvios.
2. Aprovação automática (V192R) se a lista de conferência do item 8 do 191 vier toda "sim" (a T-R10 e o R_exp "not available" por V174b contam como "sim") e não houver violação de V-03; registrar "aprovado (V192R)" na seção 4. Qualquer "não": PARAR e aguardar o autor; critério não atendido sem aprovação explícita do autor: não congelar.
Saída esperada: aprovação ou lista de correções.
Critério de conclusão: estado "aprovado" registrado na seção 4.
Modo Code: Compact
```

### COMANDO 192: Congelar a v1.0 [DONE] (commit 107d1b8; tag v1.0)

```
Objetivo: Marcar o estado reprodutível dos resultados da tese.
Anexos obrigatórios: aprovação do 192R, saída do 191
Ações:
1. README: seção "Reproduzir a v1.0" com os comandos exatos usados (179 a 190), a ordem e o tempo medido por país. PROGRESS: marcos MS-9, MS-10 e MS-11 (F8; E1 fora, OQ-013) com o estado. Lint, suíte, prova P, digest. Commit "docs: v1.0 reproduction notes", push, workflows.
2. Publicar a referência dos três países com as fases novas (--publish-reference, com --allow-without-reference só para as fases que nunca tiveram referência).
3. Tag anotada `v1.0` no HEAD com mensagem: digest do pré-registro (agregado e por país), SHA-256 dos manifestos de PRT, IND, BRA, cross_country e de escala, id da referência publicada, versão da METHODOLOGY. `git push origin v1.0`. Não mover depois.
4. Conferir `git ls-remote --tags origin v1.0`.
Saída esperada: hash do commit, da tag e id da referência.
Critério de conclusão: tag no remoto apontando para o HEAD; três workflows success no HEAD; mensagem da tag com os hashes do item 3.
Modo Code: Compact
```

---

## Bloco H2. Pós-congelamento

### COMANDO 196: Poda das referências antigas (condição cumprida, V196b) [DONE] (commit 55694fd)

Decisão: ver V196 e V196b de decisoes_v1_0_GeoFREA.md

```
Objetivo: Recuperar os 1,42 GB das rodadas e sementes antigas pelo próprio store, depois do congelamento.
Anexos obrigatórios: saída do 167 (item 3), saída do 192 (referência publicada), core/reference_store.py
Ações:
0. Condição cumprida (V196b): não há função de poda e a D2 do 167 está pendente. Roda depois do 192 e antes do 197.
1. Implementar a poda no store: mantém latest.json, a referência publicada no 192 e nada mais; remove as outras pastas de rodada e os objetos sem nenhum hard link restante; modo de simulação obrigatório antes.
2. Testes com store temporário.
3. Instantâneo (regra 3). Simulação no store real: listar o que sairia e quanto libera. Depois da simulação, executar a poda real (aprovada em V196), mantendo latest.json, a referência publicada no 192 e nada mais.
4. Verificação: manifestos com o SHA-256 do instantâneo; prova P limpa; digest idêntico; a referência do 192 intacta. Suíte, lint, commitar só os arquivos da poda, mensagem "feat(references): prune old reference rounds", push e três workflows.
Saída esperada: diff, testes, lista da simulação, espaço recuperado, hash.
Critério de conclusão: testes passam; poda real executada depois da simulação; latest.json e a referência do 192 intactos; manifestos iguais ao instantâneo; três workflows success.
Modo Code: Automático
```

### COMANDO 197: Limpeza pós-v1.0 (resultados antigos, obsoletos e temporários) [DONE] (commit 4a572fc)

Decisão: ver a seção 3 de decisoes_v1_0_GeoFREA.md (comando novo)

```
Objetivo: Deixar em GeoFREA_data e no repositório só o que a v1.0 usa ou o que os documentos citam como histórico, com o espaço recuperado medido.
Anexos obrigatórios: saídas dos COMANDOS 167, 191 e 192, manifestos da v1.0 (três países, cross_country e escala), references/latest.json
Ações:
1. Instantâneo (regra 3). Espaço livre de D: antes.
2. Classificar todo arquivo de GeoFREA_data/outputs, logs, interim, cache, _snapshots, references e archive em: (M) citado por algum manifesto da v1.0 ou pela referência publicada no 192; (D) citado só por documento do repositório (docs/, inclusive _audit); (R) regenerável e lido por código (caches de interim/ e cache/ com chave válida); (X) nada disso.
3. Aplicar:
   - M e R: manter.
   - D: mover para GeoFREA_data/archive/pre_v1_0/ com a estrutura relativa e um MOVED.json, e atualizar os caminhos nos documentos que os citam (só o caminho; mostrar o diff).
   - X: apagar. Inclui saídas de rodadas anteriores à v1.0 que nenhum manifesto cita, pastas unattended/ de rodadas antigas (manter o resumo que core/deferred_check.py lê), logs cujo run_id não está em manifesto da v1.0 nem em references/, todo *.tmp, *.before_*, __pycache__ fora de .venv, scratchpad/ do repositório, pastas _to_delete*.
   - _snapshots/: manter o instantâneo do 178 e o último; apagar os demais.
   - Exceções que ficam mesmo sem citação: technical_potential/sensitivity_150m/ (D-F5-027) e external/ inteiro (entradas).
4. Se o ambiente recusar exclusão: mover tudo que é X para D:\Douglas\DOUTORADO\_to_delete_pos_v1_0\ com MOVED.json e listar para exclusão manual.
5. Verificação: os manifestos da v1.0 com o SHA-256 do instantâneo; prova P sem stale; `python main.py --plan` (ou equivalente) sem fase a executar nos três países; digest idêntico.
6. Se o item 3 mudou documentos: lint, suíte, commit "chore: post-v1.0 cleanup and archive paths", push e workflows. A tag v1.0 não muda.
Saída esperada: tabela por classe (itens, GB), espaço antes e depois, relatório em _notas_geofrea/limpeza_pos_v1_0_197.md.
Critério de conclusão: manifestos iguais ao instantâneo; prova P limpa; nenhum arquivo M ou R tocado; tag v1.0 inalterada.
Modo Code: Automático
```

### COMANDO 198: Resumo explicativo do GeoFREA v1.0 [DONE] (sem commit)

Decisão: ver a seção 3 de decisoes_v1_0_GeoFREA.md (comando novo)

```
Objetivo: Um documento didático para o autor entender o framework de ponta a ponta, com os resultados da v1.0, as contribuições, os pontos positivos, os gargalos, os gaps e os pontos negativos.
Anexos obrigatórios: METHODOLOGY (seções 1 a 12), relatório do 191 (auditoria_pipeline_v1_0.md), LIMITATIONS, OPEN_QUESTIONS, DECISIONS (DEC-059 em diante), hypothesis_profiles e tabelas do F7, F7b e F8, relatórios de _notas_geofrea/
Ações:
1. Escrever D:\Douglas\DOUTORADO\_notas_geofrea\GeoFREA_v1_0_explicado.md, em português, com estas seções e nesta ordem:
   1. O que o GeoFREA responde: a pergunta central (RQ0) em até 3 frases e as RQ1 a RQ5 em uma linha cada.
   2. Como funciona: um diagrama do fluxo (Mermaid) e cada fase em 2 a 3 frases (o que entra, o que faz, o que sai), na ordem de execução.
   3. Conceitos em linguagem simples: potencial técnico, cenários de solo, membro climático (GCM e SSP), LCOE, τ, cf_min, LHS, futuro (membro e amostra), regret e MR, satisficing e SR, top-k, PRIM, pré-registro. Cada um com uma frase de definição e um exemplo numérico tirado da v1.0.
   4. Dados e premissas: tabela com cada entrada principal (fonte, ano, resolução, tier) e as premissas que mais pesam no resultado (τ, WACC, LUF e densidade, eta_loss, limiares do H5b: nenhum registrado, V174b), com a DEC de cada uma.
   5. Resultados da v1.0, por país e tecnologia: potencial nos três cenários de solo, LCOE nominal (p10, p50, p90), potencial abaixo de τ, H1 a H5 (H5b e T-R10 "not available", V174b; estatística, referência, veredito e uma frase do que o veredito quer dizer), H4 por tecnologia, caixa do PRIM, F7b, sensibilidades (2071-2100, escala, top_k 5 e 20, pontas de τ). Todo número com o caminho do artefato.
   6. O que os resultados dizem: leitura factual dos vereditos, separando o que se repete entre países do que depende do contexto (rótulos da M-F8-03). Sem extrapolar além do que os artefatos mostram.
   7. Contribuições: as declaradas na METHODOLOGY 1.4, cada uma ligada ao resultado da v1.0 que a sustenta ou à razão de ainda não sustentar.
   8. Pontos positivos da pipeline: reprodutibilidade (manifestos, fingerprints, referência), pré-registro e guarda, separação de incertezas (clima discreto, LHS, solo como faixa), testes e mundo sintético, rastreabilidade das decisões. Cada um com o mecanismo concreto.
   9. Gargalos: tempo e memória medidos por fase e país (do 191), dependência de dados e de rede, fases mais caras.
   10. Gaps e pontos negativos: limitações que mais afetam a leitura (CF eólico, OQ-114 e a DEC dela; τ abaixo do p5 do IRENA na Índia, L-245; escopo das metas, L-246; H5 testável em 3 de 6 pares; valores Tier 3, L-248; magnitudes contra os potenciais publicados; exposição sem perda, DEC-065; o que ficou "not available"), as OQs abertas e o que ficou para depois da v1.0.
   11. Próximos passos: até 8 itens, em ordem de impacto na tese.
2. Regras do texto: frases completas, sem jargão corporativo, sem travessão, sem emoji, sem número que não venha de artefato ou de documento do repositório (citar o caminho ou a DEC, L, M-), e "não disponível" quando o dado não existir. Tamanho alvo: 8 a 15 páginas.
3. Conferência: um script que extrai todos os números do texto e confere cada um contra o artefato ou documento citado; listar os que não batem e corrigi-los antes de entregar.
4. Não alterar nada no repositório.
Saída esperada: o arquivo do item 1 e a saída da conferência do item 3.
Critério de conclusão: as 11 seções presentes; a conferência do item 3 com 0 número sem origem; git status limpo.
Modo Code: Automático
```

---

## Bloco I. Fora da v1.0 (193 a 195, [PULADO])

### COMANDO 193: Proposta do E1 explorer (somente leitura) [PULADO]

Decisão: ver V193, V194, V195 de decisoes_v1_0_GeoFREA.md
Motivo: pós-v1.0 (decisoes V193-V195). O E1 não entra na v1.0.

```
Objetivo: Decidir a OQ-013 com os artefatos do F7 já existentes.
Anexos obrigatórios: M-E1-01, OQ-013, OQ-072 (licenças: FABDEM NC e atribuição OSM), lista de artefatos de F5 a F8
Ações:
1. Propor um pacote estático pré-calculado (sem servidor): formato dos dados por país, tecnologia, janela, SSP, GCM e cenário de solo, tamanho estimado, biblioteca de mapa e hospedagem.
2. Dizer o que da OQ-072 impede publicar (camadas derivadas do FABDEM e da REN, atribuição OSM).
3. Não escrever código.
Saída esperada: proposta em _notas_geofrea/e1_193.md. PARAR para o veredito.
Critério de conclusão: tamanho estimado e bloqueios de licença listados.
Modo Code: Compact
```

### COMANDO 194: CI que compila o LaTeX e conta as marcas de verificação [PULADO]

Decisão: ver V193, V194, V195 de decisoes_v1_0_GeoFREA.md
Motivo: pós-v1.0 (decisoes V193-V195). O E1 não entra na v1.0.

```
Objetivo: Evitar regressão de compilação e mostrar a contagem de \vfy, % verify e % open a cada push.
Anexos obrigatórios: saída do 190, docs/thesis/
Ações:
1. Workflow novo com instalação mínima de TeX que compila as tabelas da F8 (com dados do ZZZ) e os três .tex dos grupos com o .bib; falha em referência ou citação indefinida.
2. Script que conta as marcas por arquivo e publica no resumo do job, sem falhar por contagem.
3. Rodar no remoto e conferir o tempo do job.
Saída esperada: workflow, script, hash.
Critério de conclusão: job verde no HEAD; contagem igual à do 191.
Modo Code: Automático
```

### COMANDO 195: OQ-064, sensibilidade à resolução de 0,025° [PULADO]

Decisão: ver V193, V194, V195 de decisoes_v1_0_GeoFREA.md
Motivo: pós-v1.0 (decisoes V193-V195). O E1 não entra na v1.0.

```
Objetivo: Medir se totais, curvas de oferta por faixa de CF e ranking mudam com célula mais fina.
Anexos obrigatórios: OQ-064, saída do 189 (escala 0,1°)
Ações:
1. Rodar F2a a F7 em PRT e IND a 0,025° (scale.cell_deg), com --real-run.
2. Comparar com 0,05° e 0,1°: totais nacionais, curvas de oferta por faixa de CF e H1 a H3.
3. Registrar a dispersão como limitação ou PARAR para o autor decidir outra célula.
Saída esperada: tabela das três escalas.
Critério de conclusão: rodadas success; tabela com as três escalas.
Modo Code: Automático
```

---

## Fica com o autor (sem comando)

- OQ-057: conferir fonte, valor, definição e tier das 13 entradas de config/published_potential.yaml e o ano do atlas NIWE; as 9 pending só viram registered depois disso (o F7b roda com elas pending).
- Marcas dos .tex (grupo4 5 `\vfy` e 7 `% verify`; grupo5 8 `% verify` e 1 `% open`, que o 174 pode reduzir; grupo7 5 `\vfy` e 3 `% verify`) e do .bib (23 `% verify`, 6 `% agent`, 5 anos vazios, autor da ABEEólica).
- PATCH de referências ABNT online: URLs do IRENA 2025 e do PNE 2050 e data de acesso do IRENA 2024.
- PRT 2025 em tab:g4-tau (57 e 53): confirmar na edição completa ou trocar por "n/a".
- OQ-014 (justificativa de literatura do regret com satisficing e PRIM).
- OQ-072 (licenças FABDEM, REN e atribuição OSM) antes de qualquer publicação.
- Preâmbulo real da tese (url ou hyperref).
- OQ-020 (q_ref 0,01) só como análise exploratória rotulada, depois da v1.0.

---

## Molde de revisão e commit (para 172, 176, 177 e 187)

```
COMANDO nR: Revisão (aprovação, sem commit)
Objetivo: O autor aprova o diff do comando n.
Ações: 1. Resumo do diff em até 8 linhas, saída dos testes, prova P e digest. 2. Aguardar aprovação.
Critério de conclusão: estado "aprovado" registrado na seção 4.
Modo Code: Compact

COMANDO nC: Commit
Objetivo: Commit separado da aprovação.
Ações: 1. Suíte, lint, prova P e digest de novo. 2. Commitar só os arquivos do comando aprovado, com mensagem própria. 3. Push e três workflows.
Critério de conclusão: git show --stat HEAD só com esses arquivos; HEAD igual a origin/main; três workflows success; digest idêntico.
Modo Code: Compact
```
