# GeoFREA v1.0: decisões do autor para os comandos 167 a 198

Arquivo complementar de `comandos_v1_0_GeoFREA.md`. Fica no mesmo diretório (`D:\Douglas\DOUTORADO\`).

**Estado:** aprovado pelo autor (Douglas) em 2026-11-17 ao entregar este arquivo ao Code. Cada decisão abaixo vale como o "Veredito do autor" do comando correspondente. Uma decisão condicional vale só para o caso que ela descreve. Caso fora do que ela cobre: PARAR, como manda a seção 0 do arquivo de comandos.

**Regras de leitura para o Code**
1. A decisão `Vnnn` corresponde ao COMANDO nnn.
2. Um valor numérico vindo daqui entra no repositório com a fonte citada aqui. Valor sem fonte aqui não entra.
3. Uma regra condicional é aplicada mecanicamente sobre os números que o próprio comando produziu. Na DEC, registrar qual ramo foi aplicado e com quais números.
4. Registros do repositório em inglês; os textos de DEC abaixo já estão em inglês quando são literais.

---

## 1. Fatos pesquisados que as decisões usam (2026-11-17)

| Item | Fato | Fonte |
|---|---|---|
| F1. Capacity factor do Global Wind Atlas | O GWA v3 publica camadas de capacity factor para três turbinas de referência, uma por classe IEC (IEC1, IEC2, IEC3), todas com cubo a 100 m e rotores de 112, 126 e 136 m; resolução de 250 m; GeoTIFF por país; licença CC BY 4.0. Se o CF do GWA já desconta perdas (esteira, disponibilidade, elétricas) não foi confirmado nesta pesquisa: o 170 lê a documentação do GWA e informa. | DTU / Banco Mundial, Global Wind Atlas 3 (https://globalwindatlas.info/download/gis-files; https://data.dtu.dk/articles/Global_Wind_Atlas_v3/9420803); pacote R `globalwindatlas` (https://energyrt.github.io/globalwindatlas/), que baixa `<ISO3>_capacity_factor_IEC<n>.tif` |
| F2. Faixa de temperatura de operação de turbina | A IEC 61400-1 (Ed. 4, 2019, subcláusula 6.4.2) fixa como condição ambiental normal de projeto a faixa de -10 °C a +40 °C. A Interpretation Sheet 1 (2025) esclarece que a norma não exige potência nominal a +40 °C. É a âncora física do limiar de 40 °C para o eólico (L-230). | IEC 61400-1:2019/ISH1:2025 (prévia em https://www.vde-verlag.de/iec-normen/preview-pdf/info_iec61400-1{ed4.1}en.pdf) |
| F3. Definição do Rx5day | Índice ETCCDI: máximo anual (ou mensal) da precipitação acumulada em 5 dias consecutivos, em mm. | ZHANG, X. et al. Indices for monitoring changes in extremes based on daily temperature and precipitation data. **WIREs Climate Change**, v. 2, n. 6, p. 851-870, 2011; lista ETCCDI (https://etccdi.pacificclimate.org/list_27_indices.shtml) |
| F4. CF de frota já no repositório | PRT eólica 27,4% (frota ligada, 2023, REN) e PRT solar 17,2% confirmados no 161Q; BRA eólica 38% média nacional (ABEEólica, Boletim Anual 2025, p. 8; DEC-088 b). IND: nenhum CF de frota confirmado; o 22% de tab:g4-cf é piso regulatório da CERC a 100 m, não média de frota. | Registro do 161Q; DEC-088 |
| F5. O&M do IRENA por par | `config/irena_reference.yaml` já tem o O&M do IRENA 2024 dos seis pares (o `calibrate_tau_irena.py` rodou os seis no 159 com ele). | DEC-076, DEC-078, COMANDO 159 |

Consequência do F1 para a OQ-114: a turbina do GWA (100 m, rotor de 112 a 136 m) é menor que a turbina típica instalada no Nordeste brasileiro nos últimos anos (cubos e rotores maiores, potência específica menor). Parte da diferença para a frota de 38% pode ser definição de turbina, não erro. Por isso a regra do V171 compara primeiro o F5 com o GWA na mesma classe (mesma definição) e só depois com a frota.

---

## 2. Decisões por comando

### V167. Limpeza
Valem os padrões D1 a D9 como escritos no comando. D3: apagar se a busca do item 4 não achar referência.

### V170. Diagnóstico da OQ-114
Sem decisão: comando somente leitura. Acréscimo ao item 4: baixar as três classes (IEC1, IEC2, IEC3) dos três países pela fonte do F1, com manifesto; se o download por país falhar, tentar a camada global da mesma fonte e recortar.

### V171. Veredito da OQ-114 (regra aplicada pelo Code sobre os números do 170)
Definições, por país, nas células com usina e nas 15 células amostradas:
- `g = CF_F5 / (CF_GWA × eta_loss)`, com `CF_GWA` da classe IEC que o F5 atribui à célula e `eta_loss` a retenção que o F5 aplica, para os dois ficarem na mesma base de perdas. Se a documentação do GWA disser que o CF dele já desconta perdas, usar `eta_loss = 1` na fórmula e registrar.
- `p = CF_F5 nas células com usina (ponderado pela capacidade) / CF de frota` (só onde há frota com fonte, F4).

Ramos, na ordem:
1. **A (erro de modelo):** a cadeia do item 5 do 170 mostra um passo com defeito identificável (unidade, altura, densidade do ar, normalização da curva, cut-in ou cut-out, pdf de Weibull, média que inclui pixel inelegível) e corrigir esse passo, numa reprodução fora do repositório, leva a mediana de `g` para dentro de [0,85; 1,15]. Segue para o 172 com essa causa.
2. **B (definição explicada):** a mediana de `g` já está em [0,85; 1,15] em todos os países. A diferença para a frota é então atribuída a turbina e cubo maiores na frota real que na turbina de referência da classe IEC (F1), à localização da usina dentro da célula e à base de curtailment. OQ-114 fecha como limitação.
3. **C (não explicada):** nenhum dos dois. OQ-114 fecha como limitação; os valores absolutos do eólico (GW e TWh) saem na tese com ressalva explícita e a leitura principal do eólico é o ranking.

Proibido em qualquer ramo: ajustar `eta_loss`, a curva de potência ou qualquer parâmetro aos dados de frota ou ao GWA (V-06). O GWA é checagem independente, não alvo de ajuste.

Texto da DEC (inglês, completar com os números e o ramo):
"DEC-nnn: Verdict on the wind cell CF (closes OQ-114 unless branch A). Date: <data>. Decided by the author through the rule of decisoes_v1_0_GeoFREA.md V171. Branch applied: <A|B|C>. Median g (F5 over GWA times eta_loss, same IEC class) BRA <x>, IND <x>, PRT <x>; p (F5 at plant cells over the fleet CF) BRA <x>, PRT <x>, IND not available (no sourced fleet CF). No parameter is fitted to the fleet or to the GWA (V-06)."

### V172. Correção eólica
Executar só no ramo A. A correção é a do passo identificado no 170; nada além dele.

### V173. Limiares
Sem decisão: comando somente leitura. Acréscimo: a comparação V-83 usa as células candidatas do cenário central (eólico e solar separados) e dá também a mediana do ERA5 por país.

### V174. Canais do H5b e OQ-115 (regra aplicada pelo Code sobre a tabela do 173)
Por canal:
- **gust_mean_annual_max_ms:** EXCLUÍDO (contexto, DEC-065).
- **Regra T1 (entra):** o grupo5.tex dá um limiar θ para o indicador, com fonte citada (chave do .bib e página), de qualquer tier. O limiar entra com o valor, a unidade, a fonte e o tier do grupo5.tex. Tier 3 entra declarado na L do item 4 do 174 (exposição não é perda, M-F7-07).
- **Regra T2 (fica fora):** sem θ no grupo5.tex, ou θ sem fonte citada: EXCLUÍDO e declarado.
- **Regra de calor (tx35_days, tx40_days), além da T1:** o canal só entra se a V-83 passar: a mediana, nas células candidatas, da diferença entre a contagem de referência do ISIMIP3b e a do ERA5 (1995-2014) está dentro de ±5 dias por ano e, quando a mediana do ERA5 for de pelo menos 4 dias por ano, dentro de ±25% dela. Falhou: EXCLUÍDO, com os números na DEC. Esse critério é julgamento do autor, Tier 3, declarado na mesma L.
- **tx40_days no eólico:** citar, além da fonte do grupo5.tex, a IEC 61400-1 (F2) como âncora física dos 40 °C.
- **rx5day_mm:** a definição entra em `hazard_indicators` como o índice Rx5day do ETCCDI (F3, Zhang et al. 2011), anual. O limiar segue T1 ou T2.
- **OQ-115:** a coluna de tier de tab:g5-ind mostra o tier do limiar; a definição do indicador ganha coluna ou nota própria com a sua fonte (ETCCDI para rx5day).
- Se todos os canais ficarem fora: H5b é "not available" na v1.0, registrado na DEC como resultado do procedimento.
- Proibido calcular fração exposta antes de gravar o veredito (item 3 do 173).

### V175. OQ-094
Texto da DEC aprovado como está no comando.

### V176. Trava
Aprovado. Nome da opção: `--real-run`.

### V177. Janela única
Aprovado como está, com um item a mais (177, item 1b), aplicado só se o item 2 do 169 mostrou que `--production` recusa o O&M eólico de BRA ou IND por `proxy: true` (U-05, OQ-016):
- substituir o `opex_fixed_frac` eólico do par pelo O&M do IRENA 2024 que está em `config/irena_reference.yaml` para o mesmo par, convertido para fração do capex central do mesmo país e tecnologia exatamente como o `scripts/calibrate_tau_irena.py` converte (reusar a função, não reescrever a conta);
- `proxy: false`, fonte e página do IRENA copiadas do yaml, tier do yaml;
- motivo, para a DEC: o F6 passa a usar o mesmo O&M da calibração do τ, o que remove uma diferença de base entre o τ e o LCOE das células;
- digest idêntico (a chave não está no subconjunto); se mudar, PARAR;
- registrar DEC, fechar a OQ-016 se ela ainda existir e atualizar a U-05 só se ela citar esse proxy como exemplo vigente.
Qualquer outro item que o `--production` recuse e que não esteja aqui: PARAR.

### V179, V180, V181. Produção do F6
- `--production` recusando algo não coberto pelo V177: PARAR.
- Memória (180, item 2, e 181): se o pico estimado do BRA de uma fase passar de 1,25 vez o teto dela, gravar em `config/memory_budget.json` o teto da fase como ceil(1,25 × pico estimado), arredondado para cima a 64 MB, limitado à memória física da máquina menos 4 GB. Se o limite físico não comportar, reduzir `memory.max_batch_gb` à metade (repetir enquanto preciso, até 4 vezes) e aceitar que lcoe_modeling de PRT e IND fique stale e rode de novo. Registrar como D-F6 com os números. Depois de 4 reduções sem caber: PARAR.

### V182. Tamanho de amostra
Se algum par não convergir até o maior tamanho que o código testa: adotar o maior tamanho testado, registrar L nova ("U-04 not met for <pares>; adopted the largest tested size, <N>; 1 - Jaccard at that size <valores>") e seguir, sem PARAR.

### V185. BRA F7
Mesma regra de memória do V179 a V181.

### V187. F7b por janelas
Aprovado.

### V189. Sensibilidades
- Janela 2071-2100: obrigatória na v1.0.
- Escala 0,1°: rodar se o código suportar F6 e F7 nessa escala sem mudança. Se não suportar, não implementar na v1.0: registrar L nova ("V-07 scale check not run for F6 and F7 in v1.0") e as linhas de 0,1° da T-R6 saem "not available"; a implementação vai para depois da v1.0.

### V190. Figuras da F8
- Se as figuras da tese (T-*) não dependem de `settings.figures`, manter `summary`.
- Se dependem e a troca para `all` deixa stale só fases de mapas (overview, climate_maps, potential_maps, lcoe_maps, robustness_maps), trocar para `all` e regenerar essas fases.
- Se deixar stale alguma fase que não seja de mapa: manter `summary` e PARAR.

### V192R. Congelamento
Aprovado automaticamente se a lista de conferência do item 8 do 191 vier toda "sim" e não houver violação de V-03. Qualquer "não": PARAR.

### V193, V194, V195. Opcionais
Fora da v1.0: marcar [PULADO] com o motivo "pós-v1.0 (decisoes V193-V195)". O E1 não entra na v1.0.

### V196. Poda das referências
Executar só se o 167 não achou função de poda. A ordem passa a ser 192, depois 196, depois 197. A execução real da poda, depois da simulação, fica aprovada aqui (mantém `latest.json`, a referência publicada no 192 e nada mais).

---

## 3. Comandos novos para anexar ao arquivo de comandos

Entram depois do COMANDO 192 (e do 196, se ele rodar), antes do bloco I.

### COMANDO 197: Limpeza pós-v1.0 (resultados antigos, obsoletos e temporários)

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

### COMANDO 198: Resumo explicativo do GeoFREA v1.0

```
Objetivo: Um documento didático para o autor entender o framework de ponta a ponta, com os resultados da v1.0, as contribuições, os pontos positivos, os gargalos, os gaps e os pontos negativos.
Anexos obrigatórios: METHODOLOGY (seções 1 a 12), relatório do 191 (auditoria_pipeline_v1_0.md), LIMITATIONS, OPEN_QUESTIONS, DECISIONS (DEC-059 em diante), hypothesis_profiles e tabelas do F7, F7b e F8, relatórios de _notas_geofrea/
Ações:
1. Escrever D:\Douglas\DOUTORADO\_notas_geofrea\GeoFREA_v1_0_explicado.md, em português, com estas seções e nesta ordem:
   1. O que o GeoFREA responde: a pergunta central (RQ0) em até 3 frases e as RQ1 a RQ5 em uma linha cada.
   2. Como funciona: um diagrama do fluxo (Mermaid) e cada fase em 2 a 3 frases (o que entra, o que faz, o que sai), na ordem de execução.
   3. Conceitos em linguagem simples: potencial técnico, cenários de solo, membro climático (GCM e SSP), LCOE, τ, cf_min, LHS, futuro (membro e amostra), regret e MR, satisficing e SR, top-k, PRIM, pré-registro. Cada um com uma frase de definição e um exemplo numérico tirado da v1.0.
   4. Dados e premissas: tabela com cada entrada principal (fonte, ano, resolução, tier) e as premissas que mais pesam no resultado (τ, WACC, LUF e densidade, eta_loss, limiares do H5b), com a DEC de cada uma.
   5. Resultados da v1.0, por país e tecnologia: potencial nos três cenários de solo, LCOE nominal (p10, p50, p90), potencial abaixo de τ, H1 a H5 (estatística, referência, veredito e uma frase do que o veredito quer dizer), H4 por tecnologia, caixa do PRIM, F7b, sensibilidades (2071-2100, escala, top_k 5 e 20, pontas de τ). Todo número com o caminho do artefato.
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

## 4. Ordem final de execução

167, 168, 169, 170, 171, 172 (só ramo A), 172R, 172C, 173, 174, 175, 176, 176R, 176C, 177 (com o item 1b do V177, se couber), 177R, 177C, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 187R, 187C, 188, 189, 190, 191, 192R, 192, 196 (só se o 167 não achou a poda), 197, 198. Os comandos 193, 194 e 195 ficam [PULADO].

---

## 5. Respostas de 2026-11-17 (pós-166Z)

V182b. sampler.max_size_for_convergence = 4000 (sequência 500, 1000, 2000, 4000). Julgamento do autor, Tier 3, declarado em L nova. Gravação na configuração: no COMANDO 177 (janela única), antes do 179. Se o digest do pré-registro mudar ao gravar: PARAR e reverter.
V174b. Nenhum canal tem limiar com fonte no grupo5.tex. H5b e T-R10 ficam "not available" na v1.0, registrados como resultado do procedimento (DEC e L nova); hazard_thresholds continua null em todos os canais, cada um com nota "excluded from H5b by DEC-nnn"; OQ-051 fecha com ponteiro; limiar acrescentado depois da v1.0 é análise exploratória rotulada. OQ-115: a coluna de tier da tab:g5-ind mostra o tier da definição do indicador; rx5day ganha definição em hazard_indicators como o Rx5day do ETCCDI, anual (ZHANG, X. et al. Indices for monitoring changes in extremes based on daily temperature and precipitation data. WIREs Climate Change, v. 2, n. 6, p. 851-870, 2011); acrescentar a entrada ao .bib se não existir. grupo5.tex: ajustar a tab:g5-ind e acrescentar uma frase dizendo que nenhum limiar de exposição com fonte foi registrado e que H5b não é avaliado na v1.0.
V177b. A janela única aplica só os itens 3 e 9 da window_list_131. Os demais itens ficam fora e são listados no relatório do 177. O item 1b do V177 não se aplica (o O&M eólico de BRA e IND já vem do IRENA, proxy false; achado do 169).
V196b. A condição do 196 se cumpriu (não há função de poda; D2 do 167 pendente). O 196 roda depois do 192 e antes do 197.
V179c (2026-11-22): o limite "memória física menos 4 GB" de V179-V181 e do item 2 do 190B é substituído por: a fase é aceita se concluir com os limites desligados (GEOFREA_MEMORY_CAPS=0) sem erro de memória do sistema operacional; o teto é sempre o da regra da A-02 sobre o maior pico medido. A máquina tem cerca de 6.066 MB de RAM física; no BRA, robustness_analysis, external_validation e results_synthesis passam do teto e rodam com os limites desligados.
