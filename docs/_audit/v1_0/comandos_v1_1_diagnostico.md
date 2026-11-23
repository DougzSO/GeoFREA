# GeoFREA pós-v1.0: nomes das fases e diagnóstico das hipóteses (comandos 199 a 207)

Arquivo de trabalho do Claude Code, no mesmo diretório de `comandos_v1_0_GeoFREA.md`. Valem a seção 0 (como usar), a seção 2 (regras) e o molde de revisão e commit daquele arquivo. Numeração continua do 198.

---

## 1. Leitura do assistente sobre os resultados da v1.0 (2026-11-23)

Base: `auditoria_pipeline_v1_0.md` e `GeoFREA_v1_0_explicado.md`. São hipóteses a testar, não conclusões.

1. **O domínio econômico quase some no Brasil, e o τ decide o H5.** Só 0,07% da capacidade solar e 0,1% da eólica do BRA têm LCOE <= τ. O p10 do LCOE eólico do BRA (63,44) é o dobro do τ (31,95), e o τ foi calibrado com o CF de 53% da planta de referência do IRENA (DEC-077). O H5 sai "meta não atingida na referência" no BRA solar e no IND eólico por causa da calibração do τ, não do clima. O SR provavelmente é zero em quase todas as células desses pares, e o satisficing (M-F7-04) não discrimina nada.
2. **O desenho da incerteza quase não consegue mexer no ranking.** Os parâmetros do LHS que pesam (capex, WACC, O&M, vida útil) são iguais em todas as células de um país, então deslocam o LCOE de todas juntas. Só os termos por célula (conexão, degradação por zona) mudam a ordem. A mudança climática média dos GCMs é espacialmente suave. Com top-k de 10% e tolerância m = k (sair do top 20%), o deslocamento é quase impossível. Isso explica, de uma vez, H1b com V_k = 0, H3 e H4 com D quase zero, e PRIM `no_cases` nos seis pares.
3. **O MR mede sobretudo a distância à melhor célula.** O regret relativo de M-F7-02 é dominado pela diferença de LCOE entre células, que é estável entre futuros. Então o ranking por MR fica quase igual ao ranking por LCOE nominal, e o H3 tende a dar "não suportada" por construção.
4. **A F7b mostra que a elegibilidade exclui onde as usinas estão.** Em média, 74% a 84% da área das usinas de PRT e IND cai em pixel excluído, e quase 100% das usinas têm alguma exclusão. A suspeita principal é a E5: a cobertura do solo (WorldCover) é posterior à construção, então a usina aparece como área construída. Há também E4 (declividade) nas eólicas de PRT, que ficam em cumeada, e E6 (assentamentos) nas eólicas da IND. O enriquecimento no decil de menor custo (3 a 9 vezes) é o ponto positivo.
5. **H2 depende de γ** (4 a 10 de cerca de 20 variantes mudam de veredito) e o O fica perto de γ = 0,30. Isso pede uma leitura cuidadosa, não uma correção.

Consequência para a tese: qualquer mudança de τ, top-k, m, desenho do LHS ou regra de elegibilidade é desvio do pré-registro. A v1.0 fica como resultado pré-registrado, e as alternativas entram como análise exploratória rotulada (ou como `prereg-v2`, se o autor decidir).

---

## 2. Comandos

### COMANDO 199: Versionar o histórico fora do repositório [DONE] (commit 1fb5db5)

```
Objetivo: Pôr no git o histórico que explica as decisões da v1.0, sem dados.
Anexos obrigatórios: D:\Douglas\DOUTORADO\comandos_v1_0_GeoFREA.md, decisoes_v1_0_GeoFREA.md, este arquivo, _notas_geofrea\
Ações:
1. Copiar para docs/_audit/v1_0/: os dois arquivos de comandos, o de decisões e os .md de _notas_geofrea (relatórios de produção, limpeza, prontidão, auditoria, explicado). Não copiar .bak, scripts de rascunho nem dados. Arquivo que já está em docs/_audit (169, 170, 173): não duplicar, citar.
2. docs/_audit/v1_0/README.md: uma linha por arquivo (o que é, comando de origem).
3. Conferir que nenhum arquivo traz segredo ou caminho de chave do .env.
4. Lint, commit "docs(audit): v1.0 command, decision and report history", push e três workflows.
Saída esperada: lista de arquivos e hash.
Critério de conclusão: git show --stat HEAD só em docs/_audit/v1_0/; lint 0; três workflows success.
Modo Code: Compact
```

### COMANDO 200: Nomes das fases [DONE] (commit 2c94752)

```
Objetivo: Dar a cada fase um nome legível e um grupo, num registro único que docs, logs, catálogo de saídas e a futura plataforma leem, mantendo os IDs do código. Nomes aprovados ao enviar.
Anexos obrigatórios: main.py (PhaseSpec), METHODOLOGY 4.1 e 4.2, README, docs/PIPELINE_GUIDE.md
Nomes (id do código | sigla | nome pt | nome en | grupo):
  data_acquisition | F1 | Aquisição de dados | Data acquisition | Dados
  data_quality_audit | F1b | Auditoria dos dados | Data audit | Dados
  external_inputs | - | Registro das entradas climáticas | Climate inputs registry | Clima
  grid_alignment | F2a | Alinhamento à grade | Grid alignment | Território
  siting_layers | F2b | Camadas de restrição e custo | Siting layers | Território
  land_eligibility | F3 | Elegibilidade do solo | Land eligibility | Território
  climate_forcing | F4 | Sinal climático | Climate signal | Clima
  hazard_context | - | Contexto de perigos | Hazard context | Clima
  climate_maps | - | Mapas do clima | Climate maps | Clima
  overview | - | Visão geral do país | Country overview | Território
  technical_potential | F5 | Potencial técnico | Technical potential | Potencial
  potential_maps | - | Mapas de potencial | Potential maps | Potencial
  lcoe_modeling | F6 | Custo nivelado (LCOE) | Levelized cost | Economia
  sample_size_convergence | - | Convergência da amostra | Sample-size convergence | Economia
  lcoe_maps | - | Mapas de custo | Cost maps | Economia
  robustness_analysis | F7 | Robustez e hipóteses | Robustness and hypotheses | Robustez
  robustness_maps | - | Mapas de robustez | Robustness maps | Robustez
  cross_country_h4 | - | Comparação entre países | Cross-country comparison | Robustez
  external_validation | F7b | Validação externa | External validation | Validação
  results_synthesis | F8 | Síntese de resultados | Results synthesis | Síntese
  explorer | E1 | Explorador | Explorer | Plataforma
Ações:
1. Criar config/phases.yaml com a tabela acima (mais a ordem de execução). Conferir que nenhuma fase tem phases.yaml no escopo de fingerprint de configuração (prova P antes e depois: 0 diferenças). Se algum escopo incluir, PARAR.
2. main.py: carregar o registro, validar que cada PhaseSpec tem entrada e vice-versa (teste), e usar o nome pt nas mensagens do --plan e na linha de log de cada fase, sem mudar o id. Não editar módulos de fase.
3. Docs: coluna "Nome" na tabela 4.2 da METHODOLOGY (próximo PATCH; changelog e PROGRESS iguais) e tabela de fases no README e no PIPELINE_GUIDE geradas do phases.yaml por script, para não divergirem.
4. Suíte, synthetic, lint, digest. Commit "feat(core): human-readable phase names registry", push e três workflows.
Saída esperada: diff, prova P, hash.
Critério de conclusão: teste de correspondência registro e PhaseSpec passa; prova P 0; três workflows success.
Modo Code: Automático
```

### COMANDO 200B: Nomes das fases em inglês e pendências do 200 [DONE]

```
Objetivo: Deixar o registro, o plano e os logs só em inglês, e fechar duas pendências do 200. Aprovado ao enviar.
Ações:
1. config/phases.yaml: remover o campo do nome em português e usar o name_en no --plan e nos logs. Grupos também em inglês: Data, Territory, Climate, Potential, Economics, Robustness, Validation, Synthesis, Platform. Atualizar phase_registry.py, os testes e as tabelas geradas (render_phase_tables.py --check).
2. sample_size_convergence aparece como execute em 0,05° por causa do 86fabd8: rodar de novo só essa fase nos três países (--real-run, --phases sample_size_convergence) e conferir que o tamanho adotado e o 1 - Jaccard por par saem iguais aos do D-F6-032. Diferença: PARAR. Depois disso, a prova P em 0,05° tem de dar 0 execute.
3. docs/_audit/v1_0/: atualizar a cópia de comandos_v1_1_diagnostico.md para a versão atual, com os [DONE].
4. Suíte, lint, digest, prova P nas duas escalas. Commit "chore: English phase names; rerun sample_size_convergence; refresh audit copy", push e três workflows.
Critério de conclusão: nenhum texto em português em phases.yaml, no --plan e nos logs; prova P 0 execute nas duas escalas; três workflows success. Marcar 200B [DONE].
Modo Code: Compact
```

### COMANDO 201: Diagnóstico D1, τ e domínio econômico (somente leitura) [DONE]

```
Objetivo: Medir quanto do H5 e do SR é decidido pela calibração do τ, e se o τ e o LCOE das células estão na mesma base.
Anexos obrigatórios: seção 1 deste arquivo (itens 1 e 3), M-F7-04, M-F7-12, M-F7-17, DEC-077, DEC-085, L-245, L-247, config/irena_reference.yaml, scripts/calibrate_tau_irena.py, artefatos de F5, F6 e F7 da v1.0
Ações (por país e tecnologia, janela core, cenário central, m0; scripts em _notas_geofrea/diagnostico_v1_0/, nada gravado em outputs/):
1. CF da planta de referência do τ contra a distribuição do CF das células: em que percentil das células ele cai; fração de células com CF >= ele.
2. Decomposição do LCOE nominal: planta de referência do τ contra as células do decil 1, mediana e decil 10 em capex, O&M, conexão, degradação e energia. Dizer quanto da diferença entre o p10 das células e o τ vem de cada termo.
3. SR: distribuição (fração com SR = 0, SR = 1, quartis) e correlação de Spearman entre SR e MR.
4. Curva descritiva da fração de capacidade com LCOE <= x, para x de 20 a 200 USD/MWh; marcar o τ primário, as pontas do range registrado e o LCOE publicado do IRENA. Só descrever: nenhum valor novo de τ é proposto.
5. H5: para IND solar, IND eólica e BRA solar, de onde vem E_0 (células e energia do domínio) e qual τ daria H_0 = 0. Descritivo.
Saída esperada: relatório _notas_geofrea/diagnostico_v1_0/D1_tau.md com tabelas e figuras.
Critério de conclusão: itens 1 a 5 nos seis pares; todo número com origem; git status limpo; manifestos iguais ao início.
Modo Code: Automático
```

### COMANDO 202: Diagnóstico D2, o que move (ou não) o ranking (somente leitura) [DONE]

```
Objetivo: Testar se o desenho da incerteza consegue deslocar o ranking, separando o efeito de célula, de clima e de parâmetros.
Anexos obrigatórios: seção 1 (itens 2 e 3), M-F6-01, M-F6-02, U-03, M-F7-02 a M-F7-08, artefatos de F4, F5, F6 e F7 da v1.0
Ações (scripts fora de outputs/; para IND e BRA, amostra aleatória de 20.000 células com semente registrada; PRT inteiro):
1. Classificar cada parâmetro do LHS em "uniforme no país" ou "varia por célula" (pelo código do kernel) e dizer quais termos do LCOE podem mudar a ordem entre células.
2. Variância do LCOE: parcela entre células contra parcela entre futuros, com o LCOE nominal por membro (eixo clima) e, recalculando o kernel do F6 com 200 sorteios do design gravado (eixo parâmetros). Kernel importado, sem rodar fase.
3. Correlação de postos: Spearman e sobreposição do top-k entre o ranking nominal e o de cada membro, e entre o nominal e o de cada sorteio. Mínimo, mediana e máximo.
4. Deslocamento das células do top-k nominal: distribuição do pior posto alcançado entre futuros, em múltiplos de k. Mostrar quão longe ficam do limiar k + m = 2k.
5. Sinal climático: mudança do CF por membro (mediana e desvio padrão espacial) nas células candidatas.
6. MR contra LCOE nominal: Spearman e quanto do MR é explicado pela distância nominal à melhor célula (regressão simples, R²).
7. Descritivo extra, rotulado exploratório: o V_k, o D e o rho recalculados com top-k 1% e m = k/2, só para ver se o desenho tem sensibilidade. Não substitui nada.
Saída esperada: _notas_geofrea/diagnostico_v1_0/D2_ranking.md.
Critério de conclusão: itens 1 a 7 nos seis pares; git status limpo; manifestos iguais.
Modo Code: Automático
```

### COMANDO 203: Diagnóstico D3, H2 e a sensibilidade a γ (somente leitura) [DONE]

```
Objetivo: Entender o que produz o O do H2 e por que o veredito muda com γ.
Anexos obrigatórios: M-F7-07 (H2), h2_summary e h2_regions dos três países, T-R4
Ações:
1. Por par: O, O_ref, número de Admin1 com célula ranqueada, distribuição de capacidade entre regiões, Δz, D_TV e o perfil de decisão por γ.
2. Quantas regiões a seleção regional usa até T e quanto da capacidade da seleção por célula fica nessas regiões.
3. Dizer se O está sendo puxado por poucas regiões grandes (concentração; índice de Herfindahl da capacidade por região).
Saída esperada: _notas_geofrea/diagnostico_v1_0/D3_h2.md.
Critério de conclusão: itens 1 a 3 nos seis pares; git status limpo.
Modo Code: Compact
```

### COMANDO 204: Diagnóstico D4, exclusões nas usinas existentes (somente leitura)

```
Objetivo: Saber se as exclusões que atingem as usinas existentes são do modelo ou são efeito do dado (a usina alterando o próprio pixel).
Anexos obrigatórios: seção 1 (item 4), M-F7b-01, M-F2b-01, M-F2a-06, M-F2a-11, tabelas exclusion_shares, GEM trackers, config/experiments.yaml (land_availability)
Ações:
1. E5: classe do WorldCover nos pixels das usinas, por país e tecnologia; fração em "built-up" ou "bare"; cruzar com o ano de entrada em operação do GEM contra o ano do WorldCover usado. Usinas que entraram antes do mapa e caem em classe excluída são o indício.
2. E4: distribuição da declividade nos pixels das usinas eólicas e solares contra o limite de cada cenário de solo; fração acima do limite central.
3. E6: classe do GHS-SMOD e distância ao assentamento nas usinas, sobretudo eólica da IND.
4. E1: tipo de designação WDPA nas usinas que caem em área protegida.
5. Para cada restrição, dizer: (a) artefato do dado posterior à usina, (b) limite mais estrito que a prática, (c) exclusão legítima (usina antiga em área hoje restrita). Só classificar, sem propor valor novo.
Saída esperada: _notas_geofrea/diagnostico_v1_0/D4_exclusoes.md.
Critério de conclusão: itens 1 a 5 nos seis pares; git status limpo.
Modo Code: Automático
```

### COMANDO 205: Diagnóstico D5, caudas, convergência e células extremas (somente leitura)

```
Objetivo: Conferir os sinais fora do padrão que não entram em D1 a D4.
Anexos obrigatórios: L-252, L-253, artefatos de F5, F6 e F7
Ações:
1. Eólica do BRA: células com LCOE > 200 USD/MWh (contagem, capacidade, CF, onde ficam); dizer se entram no conjunto F7 e se afetam L*, MR ou SR.
2. PRT solar, L-252: 1 - Jaccard por tamanho de amostra e quantas células trocam de lugar no top-k entre 2000 e 4000.
3. As 5 células de menor LCOE nominal de cada par: CF, distância, zona, custo de conexão. Conferir se alguma é artefato (distância zero suspeita, CF fora da faixa física, borda de máscara).
Saída esperada: _notas_geofrea/diagnostico_v1_0/D5_caudas.md.
Critério de conclusão: itens 1 a 3; git status limpo.
Modo Code: Compact
```

### COMANDO 206: Síntese do diagnóstico (somente leitura)

```
Objetivo: Juntar D1 a D5 numa classificação que permita decidir o que fazer na tese.
Anexos obrigatórios: relatórios D1 a D5
Ações:
1. Para cada achado: classe (A) defeito de código, (B) propriedade do desenho a declarar, (C) escolha de calibração ou de limiar a rever, (D) efeito do dado de entrada; evidência; hipóteses afetadas.
2. Para cada achado (C) ou (D): o que mudaria, quais fases rodariam de novo, custo estimado em horas e se toca o subconjunto pré-registrado.
3. Não propor valores novos nem mudar nada.
Saída esperada: _notas_geofrea/diagnostico_v1_0/D0_sintese.md. PARAR: o autor leva D0 ao chat de planejamento.
Critério de conclusão: todos os achados classificados; git status limpo.
Modo Code: Compact
```

### COMANDO 207: Commit dos relatórios de diagnóstico

```
Objetivo: Versionar D0 a D5 e os scripts de diagnóstico.
Ações:
1. Copiar os relatórios para docs/_audit/diagnostico_v1_0/ e os scripts para scripts/diagnostics/ (sem dados, sem figuras pesadas acima de 2 MB).
2. Lint, suíte (os scripts não podem quebrar o import DAG), commit "docs(audit): v1.0 hypothesis diagnostics", push e três workflows.
Critério de conclusão: três workflows success.
Modo Code: Compact
```

---

## 3. Registro de execução

| Comando | Estado | Commit | Data | Nota |
|---|---|---|---|---|
| 199 | DONE | 1fb5db5 | 2026-11-23 | 16 arquivos + README em docs/_audit/v1_0; sem segredos; unit 2613 passed; digest idêntico; 3 workflows success. |
| 200 | DONE | 2c94752 | 2026-11-23 | config/phases.yaml, phase_registry, plano e log com nome pt; METHODOLOGY 19.4.16; unit+synthetic+regression 2760 passed; digest idêntico. |
| 201 | DONE | sem commit | 2026-11-23 | D1_tau.md em _notas_geofrea/diagnostico_v1_0; kernel reproduz o F6 (diferença 0); manifestos 8 de 8 iguais; git limpo. |
| 202 | DONE | sem commit | 2026-11-23 | D2_ranking.md; sorteios e F7 (V_k, D, k) reproduzidos; amostra 20.000 (semente 202); manifestos 8 de 8 iguais; git limpo. |
| 203 | DONE | sem commit | 2026-11-23 | D3_h2.md; O, D_TV, Δz e T recalculados batem com o F7; manifestos 8 de 8 iguais; git limpo. |
| 200B | DONE | ver commit abaixo | 2026-11-23 | Registro só em inglês; sample_size_convergence refeita nos 3 países, tabelas idênticas às do D-F6-032; prova P 0 execute em 0,05° e em 0,1° (4 fases). |
