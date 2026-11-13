# 05 — METHODOLOGY.md contra o código, F6 a F8 (COMANDO 147-F)

Gerado por script (`meth_map2.py`, `meth_report2.py`) e por conferências dirigidas; somente leitura. Nenhum arquivo de docs ou código foi alterado. Mesmo formato do `04`. Pasta mantida não rastreada até o 147-H.

Escopo: **28 regras**: `M-F6-*` (10), `M-F7-*` (11), `M-F7b-*` (4), `M-F8-*` (3). O Section 10 (tabelas e figuras T-*) e `A-*` não entram. Ligação regra, código e teste como no `04` (evidência textual: o ID no docstring ou na tabela de conformidade da fase; o ID ou o nome do teste citado). A coluna *execução real* diz se a regra já rodou em PRT, IND ou BRA: o item 3 mostra a evidência.

## Contagem por estado

| estado | regras |
|---|---|
| divergente | 1 |
| ok | 26 |
| sem código | 1 |

Conferências numéricas: 46; divergentes: **1**.

## 1. Uma linha por regra

| regra | linha | resumo (até 12 palavras) | arquivo:função | como achei | teste | indireto | estado | execução real |
|---|---|---|---|---|---|---|---|---|
| M-F6-01 | 282 | LCOE kernel, vectorized over cells, for member m and parameter vector theta: | core/schemas.py:_TechnologyEconomicParams | docstring (12) | kernel.py::<module> (+3) | 15 | ok (tabela cita código que existe) | não |
| M-F6-02 | 289 | Parameter samples s drawn by Latin hypercube over the uncertain parameters declared | core/config_schemas.py:SamplerConfig | docstring (10) | test_lcoe_sampling.py::<module> | 11 | ok (tabela cita código que existe) | não |
| M-F6-03 | 290 | If a C3 loss function passes OQ-007, it enters as an OPEX | — | — | — | 0 | sem código (condicional: só vale se uma função de perda C3 passar OQ-007 (OQ-007 aberta); nada a implementar hoje) | não |
| M-F6-04 | 291 | Streaming: per member, cells are processed in blocks with all samples of | lcoe_modeling/pipeline.py:iter_member_summaries | docstring (7) | test_lcoe_pipeline.py::test_summary_equals_numpy_on_the_full_block (+2) | 2 | ok (tabela cita código que existe) | não |
| M-F6-05 | 292 | The kernel is a pure function importable by F7. | lcoe_modeling/kernel.py:lcoe_block | docstring (3) | test_lcoe_kernel.py::<module> (+1) | 8 | ok (tabela cita código que existe) | não |
| M-F6-06 | 293 | Outputs: lcoe_summary_<tech>.parquet, design_matrix_<tech>.parquet, supply curves per member at nominal parameters, and lcoe_nominal_<tech>__<scenario>.parquet | lcoe_modeling/pipeline.py:build_scenario_nominal | docstring (8) | test_lcoe_pipeline.py::<module> | 2 | ok (tabela cita código que existe) | não |
| M-F6-07 | 295 | Technology vintage and cost parameters. The reference commissioning year is t_ref = | config/parameters.json; lcoe_modeling/inputs.py:resolve_technology_costs | tema: parâmetros de custo por tecnologia (sem o ID em docstring) | test_groups12_parameters.py::<module> | 0 | ok | não |
| M-F6-08 | 297 | External connection cost (Group 3). The plant capital cost covers everything inside | lcoe_modeling/connection.py:group3_problems | docstring (3) | test_lcoe_kernel.py::test_the_external_connection_cost_follows_the_analytic_formula_per_megawatt (+1) | 1 | divergente (o texto diz que IND bay, BRA line e bay não têm valor (OQ-001); `parameters.json` tem os três e OQ-001 está fechada) | não |
| M-F6-09 | 298 | Degradation (Group 3). Energy declines geometrically (M-F6-01). The rate of a cell | core/pv_zones.py:classify_zone | docstring (5) | test_lcoe_kernel.py::test_degradation_follows_the_closed_form_and_the_weight_moves_it_between_the_bounds_of_each_cell (+1) | 1 | ok (tabela cita código que existe) | não |
| M-F6-10 | 299 | Losses, failure rules and sensitivities (Group 3). Transmission losses are not modelled | lcoe_modeling/inputs.py:read_member_inputs | tabela da fase | test_lcoe_kernel.py::test_transmission_losses_scale_the_energy_by_one_minus_alpha_l_grid_with_a_floor_at_zero (+2) | 7 | ok (tabela cita código que existe) | não |
| M-F7-01 | 305 | Feasibility.** feasible(i, f) = CF_i,m >= CF_min[tech] (OQ-008), evaluated on the capacity | lcoe_modeling/kernel.py:lcoe_block | docstring (10) | test_f7_parameters.py::<module> (+2) | 8 | ok (tabela cita código que existe) | não |
| M-F7-02 | 306 | Relative regret.** L*_f = the q_ref quantile of LCOE over the feasible | robustness_analysis/decision.py:regret_quantile | docstring (5) | test_robustness_convergence.py::<module> (+1) | 2 | ok (tabela cita código que existe) | não |
| M-F7-03 | 307 | Primary metric.** MR_i = max over members m of ( P90 over | robustness_analysis/evaluator.py:evaluate | docstring (2) | test_zzz_end_to_end.py::test_f7_max_regret_of_a_cell_is_recomputed_by_hand_from_the_pipeline_tables (+1) | 5 | ok (tabela cita código que existe) | não |
| M-F7-04 | 308 | Satisficing robustness.** SR_i = share of the draws s >= 1 (over | robustness_analysis/evaluator.py:evaluate | docstring (2) | test_f7_parameters.py::<module> (+1) | 5 | ok (tabela cita código que existe) | não |
| M-F7-05 | 309 | Rankings.** Nominal rank by LCOE_i,f0 over the F7 set; robust rank by | robustness_analysis/assemble.py:compute_rankings | docstring (16) | test_f7_parameters.py::<module> (+1) | 2 | ok (tabela cita código que existe) | não |
| M-F7-06 | 310 | Axis comparison (H4).** Per country and technology, over the ranked set I. | robustness_analysis/assemble.py:compute_rankings | docstring (6) | test_h4_axis_dominance.py::<module> (+1) | 2 | ok (tabela cita código que existe) | não |
| M-F7-07 | 311 | Hypothesis tests.** | core/config_schemas.py:HypothesisRule | docstring (42) | test_cross_country.py::<module> (+8) | 11 | ok (tabela cita código que existe) | não |
| M-F7-08 | 345 | Scenario discovery.** PRIM, per country and technology, in the core window (text | core/config_schemas.py:PrimSensitivity | docstring (16) | test_f7_parameters.py::<module> (+5) | 11 | ok (tabela cita código que existe) | não |
| M-F7-09 | 346 | Method agreement.** Kendall correlation between MR and SR rankings, supporting the RQ4 | robustness_analysis/hypotheses.py:agreement | docstring (1) | test_the_kendall_statistic_equals_scipy_on_the_ranked_cells_and_counts_the_tied_pairs | 1 | ok (tabela cita código que existe) | não |
| M-F7-10 | 347 | Streaming.** One future at a time, vectorized over cells, updating running maxima | robustness_analysis/evaluator.py:evaluate | docstring (5) | test_the_peak_memory_of_the_evaluation_stays_near_the_block_budget (+1) | 5 | ok (tabela cita código que existe) | não |
| M-F7-11 | 348 | Outputs: robustness_<tech>.parquet (per cell: nominal LCOE and rank, MR, SR, climate-fragile flag | robustness_analysis/assemble.py:robustness_frame | docstring (7) | test_robustness_pipeline.py::<module> | 2 | ok (tabela cita código que existe) | não |
| M-F7b-01 | 352 | Share of existing plant capacity (GEM trackers) located in excluded pixels, per | core/config_schemas.py:ExternalValidationConfig | docstring (8) | test_external_validation.py::<module> | 11 | ok (tabela cita código que existe) | não |
| M-F7b-02 | 353 | Enrichment ratio: share of existing capacity in the lowest nominal-LCOE deciles divided | external_validation/enrichment.py:enrichment_rows | docstring (4) | test_external_validation.py (+1) | 1 | ok (tabela cita código que existe) | não |
| M-F7b-03 | 354 | Comparison of national technical potential with published estimates, as a table with | core/config_schemas.py:ExternalValidationConfig | docstring (4) | test_the_comparison_puts_the_estimate_beside_f5_at_the_reference_member_and_computes_nothing_from_it (+1) | 11 | ok (tabela cita código que existe) | não |
| M-F7b-04 | 355 | Existing plants reflect past auctions, policy, and grid access. Results are plausibility | external_validation/pipeline.py:build_external_validation | docstring (2) | test_zzz_end_to_end.py::test_f8_shows_the_empty_published_comparison_as_empty_and_says_why (+1) | 1 | ok (tabela cita código que existe) | não |
| M-F8-01 | 359 | F8 reads persisted artifacts and never recomputes a scientific quantity. | results_synthesis/runner.py:build_thesis | docstring (10) | test_results_synthesis.py::<module> | 2 | ok (a tabela cita `inputs.py:ArtifactReader`; a classe está em core/artifact_reader.py e é reexportada por results_synthesis/inputs.py (confere)) | não |
| M-F8-02 | 360 | F8 produces every output of Section 10 into outputs/thesis/, with a fixed | core/config_schemas.py:ThesisFiguresConfig | docstring (6) | test_results_synthesis.py::<module> | 11 | ok (tabela cita código que existe) | não |
| M-F8-03 | 361 | Cross-country synthesis (T-R8).** Text in docs/thesis/methods/synthesis_and_scenario_discovery.tex. The synthesis reports what was observed | core/config_schemas.py:SynthesisConfig | docstring (4) | test_synthesis.py::<module> | 11 | ok | não |

**Sem código (1):** M-F6-03 (condicional: só vale se uma função de perda C3 passar OQ-007 (OQ-007 aberta); nada a implementar hoje).
**Sem teste direto (0):** nenhuma.
**Divergente (1):** M-F6-08 (o texto diz que IND bay, BRA line e bay não têm valor (OQ-001); `parameters.json` tem os três e OQ-001 está fechada).

Casos em que a ligação é pelo docstring do módulo (`<module>`): a regra tem mais de um implementador; a coluna mostra o primeiro símbolo achado.

## 2. Números das regras contra config e código

Leitura do valor vivo em `config/*` e nas constantes do código (não de memória). Fora desta tabela estão os números que são dado de execução, literatura ou data.

| regra | o que o texto diz | onde está | valor lido | resultado |
|---|---|---|---|---|
| M-F6-07 | t_ref = 2024 (commissioning_year) | parameters.json technologies.*.commissioning_year | 2024 | bate |
| M-F6-07 | vida útil inteira uniforme de 25 a 30, central 30 | parameters.json lifetime_years | discrete_uniform 25.0-30.0, central 30 | bate |
| M-F6-07 | capex amostrado em [P5, 2*média - P5] | parameters.json capex_usd_per_kw.range (PRT, BRA, IND, ZZZ pulados se sem faixa) | máximo = 2*valor - mínimo em todos | bate |
| M-F6-07 | O&M variável zero | parameters.json opex_var_usd_per_mwh | 0.0 | bate |
| M-F6-07 | WACC com faixa uniforme de ±1 ponto percentual | parameters.json discount_rate.range | {'PRT': (0.032, 0.052), 'BRA': (0.067, 0.087), 'IND': (0.03, 0.05)} | bate |
| M-F6-08 | P_ref = 100 MW | parameters.json connection.reference_project_mw | 100.0 | bate |
| M-F6-08 | tortuosity_grid U[1,2; 1,3], central 1,25 | parameters.json connection.tortuosity_grid | 1.2-1.3, central 1.25 | bate |
| M-F6-08 | tortuosity_road U[1,2; 1,3], central 1,25 | parameters.json connection.tortuosity_road | 1.2-1.3, central 1.25 | bate |
| M-F6-08 | bandeira de longa distância 100 km | parameters.json connection.long_distance_flag_km | 100.0 | bate |
| M-F6-08 | IND linha INR 1,10 crore/km, 2025 | parameters.json IND.connection.line_cost_per_km | 1.1 INR crore/km 2025 | bate |
| M-F6-08 | "IND bay, BRA line and bay ... have no value yet (OQ-001)" | parameters.json IND bay_cost, BRA line_cost_per_km, BRA bay_cost | IND bay 3.0, BRA line 598332.0, BRA bay 1987188.27 | DIVERGE |
| M-F6-08 | estrada sem valor nos três países | parameters.json *.connection.road_cost_per_km | {'PRT': None, 'BRA': None, 'IND': None} | bate |
| M-F6-09 | eólica d_low 0,17 %/ano, d_high 0,53 %/ano | parameters.json wind.degradation_rate | 0.0017, faixa até 0.0053 | bate |
| M-F6-09 | terreno complexo 0,72 %/ano (Kim e Kim) | parameters.json wind.wind_degradation_complex_terrain | 0.0072 | bate |
| M-F6-09 | zona quente 0,94 %/ano (sensibilidade) | parameters.json degradation_by_zone.hot_zone_sensitivity.rate | "rate": 0.0094 | bate |
| M-F6-09 | zonas acima de T7 usam T7 | core/pv_zones.py FLEET_TOP_ZONE | FLEET_TOP_ZONE = 7 | bate |
| M-F6-09 | zonas com menos de 20 sistemas são agrupadas | scripts/derive_pv_degradation_by_zone.py --min-systems | "--min-systems", type=int, default=20 | bate |
| M-F6-10 | alpha_loss de 0,03 a 0,05 %/km (sensibilidade) | parameters.json connection.transmission_loss_per_km_sensitivity.range | 0.0003-0.0005 | bate |
| M-F6-10 | perdas de transmissão zero no caso central | parameters.json connection.transmission_loss_per_km | 0.0 | bate |
| M-F6-02 | LHS com semente registrada (42) | experiments.yaml sampler | latin_hypercube seed 42 | bate |
| M-F7-07 | H1 alpha = 0.6 | experiments.yaml hypothesis_rules.H1.alpha | 0.6 | bate |
| M-F7-07 | H1 beta = 0.2 | experiments.yaml hypothesis_rules.H1.beta | 0.2 | bate |
| M-F7-07 | H2 gamma = 0.3 | experiments.yaml hypothesis_rules.H2.gamma | 0.3 | bate |
| M-F7-07 | H3 delta = 0.2 | experiments.yaml hypothesis_rules.H3.delta | 0.2 | bate |
| M-F7-07 | H4 lower = 0.4 | experiments.yaml hypothesis_rules.H4.lower | 0.4 | bate |
| M-F7-07 | H4 upper = 0.6 | experiments.yaml hypothesis_rules.H4.upper | 0.6 | bate |
| M-F7-07 | H5 lambda = 0.2 | experiments.yaml hypothesis_rules.H5.lambda | 0.2 | bate |
| M-F7-07 | H5 sensitivity_lambda = 0.1 | experiments.yaml hypothesis_rules.H5.sensitivity_lambda | 0.1 | bate |
| M-F7-07 | H1 tolerance_multiple_of_k = 1,0 | experiments.yaml hypothesis_rules.H1 | 1.0 | bate |
| M-F7-07 | H3 tolerance_multiple_of_k = 1,0 | experiments.yaml hypothesis_rules.H3 | 1.0 | bate |
| M-F7-07 | H4 tolerance_multiple_of_k = 1,0 | experiments.yaml hypothesis_rules.H4 | 1.0 | bate |
| M-F7-08 | prim.outcome_threshold = 0.2 | experiments.yaml prim.outcome_threshold | 0.2 | bate |
| M-F7-08 | prim.peel_alpha = 0.05 | experiments.yaml prim.peel_alpha | 0.05 | bate |
| M-F7-08 | prim.mass_min = 0.05 | experiments.yaml prim.mass_min | 0.05 | bate |
| M-F7-08 | prim.min_coverage = 0.5 | experiments.yaml prim.min_coverage | 0.5 | bate |
| M-F7-08 | prim.max_restricted_descriptors = 3 | experiments.yaml prim.max_restricted_descriptors | 3 | bate |
| M-F7-08 | prim.bootstrap_replicates = 200 | experiments.yaml prim.bootstrap_replicates | 200 | bate |
| M-F7-08 | prim.percentile_low = 5 | experiments.yaml prim.percentile_low | 5 | bate |
| M-F7-08 | prim.percentile_high = 95 | experiments.yaml prim.percentile_high | 95 | bate |
| M-F7-08 | sensibilidades theta {0,10; 0,30}, cobertura {0,40; 0,60}, suporte {0,02; 0,10} | experiments.yaml prim.sensitivity | {'outcome_threshold': [0.1, 0.3], 'min_coverage': [0.4, 0.6], 'mass_min': [0.02, | bate |
| M-F7-08 | caso de interesse quando V_f >= theta | robustness_analysis/scenario_discovery.py cases_of_interest | `>= theta - 1e-12` | bate |
| M-F7-08 | (sem número) desfecho por futuro f=(m,s), sorteios s >= 1 | robustness_analysis/assemble.py prim_input | draws = futures[futures["sample"] >= 1] | bate |
| M-F7-07 | H5: G = 8,76 * G_cap * CFbar | robustness_analysis/h5_climate_pressure.py | TWH_PER_GW_AT_FULL_LOAD = 8.76 | bate |
| M-F7-07 | H2: gamma de 0,10 a 0,70 em passos de 0,05 | robustness_analysis/h2_aggregation.py (docstring; valor em código não conferido) | gamma` from 0.10 to 0.70 in steps of 0.05 | bate |
| M-F7-07 | H3: m em {k/2, 2k} | robustness_analysis/h3_robust_vs_nominal.py | SENSITIVITY_TOLERANCE_MULTIPLES = (0.5, 2.0) | bate |
| M-F7-02 | q_ref padrão 0 (mínimo) | experiments.yaml thresholds.regret_quantile | 0 | bate |

**Divergentes: 1** de 46. M-F6-08 "IND bay, BRA line and bay ... have no value yet (OQ-001)" (lido: IND bay 3.0, BRA line 598332.0, BRA bay 1987188.27)

A divergência de M-F6-08 é de **texto**: a frase "IND bay, BRA line and bay and the road of the three countries have no value yet (OQ-001)" já não é verdade para IND bay e BRA line e bay (têm valor em `parameters.json`) e OQ-001 está `Closed with proxies (COMMAND 86)` em `OPEN_QUESTIONS.md:34`. A estrada continua sem valor nos três países, mas `road_cost_excluded` é `true` e `group3_problems` não a cobra.

Verificação ao vivo: chamei `group3_problems` (lcoe_modeling/connection.py) com o `parameters.json` de hoje para PRT, IND e BRA, solar e eólica: **0 problemas nos seis casos**. Ou seja, o F6 não é mais barrado por custo de Group 3 faltando. Não rodei o F6.

## 2 (especial). Os cinco pontos pedidos

### (a) Regret e q_ref (M-F7-02, evaluator, D-F7-006, OQ-020, OQ-091)

| ponto | achado |
|---|---|
| regra | METHODOLOGY.md:306 (M-F7-02): `L*_f` é o quantil `q_ref` do LCOE sobre as células viáveis em `f`; `r = (LCOE - L*)/L*`; padrão `q_ref = 0` (mínimo; OQ-020); célula inviável em `f` recebe o regret da viável de maior LCOE em `f`. |
| código do mínimo | `robustness_analysis/evaluator.py:113-135 reference_levels`: mínimo corrente sobre as células viáveis e o maior LCOE viável por amostra; erro se uma amostra não tem célula viável. |
| regret | `evaluator.py:233-234`: `regret = draws / draw_low; regret -= 1.0`; P90 sobre sorteios em `:244`; MR = máximo sobre membros do núcleo em `:247`. |
| corte em zero | Não há corte na fórmula. Guarda em `evaluator.py:341-342` (erro `V-03 is violated` se MR < -1e-12) e `np.maximum(acc.mr, 0.0)` em `evaluator.py:344`, só para ruído. Com q_ref = 0 o regret não pode ser negativo. |
| q_ref diferente de 0 | `robustness_analysis/decision.py:68-77 regret_quantile`: levanta erro se `thresholds.regret_quantile != 0`, nomeando OQ-020. Docstring cita D-F7-009 ("Only q_ref = 0 is built"); **D-F7-006 define o conjunto de `L*` e não a recusa** (corrijo o que escrevi no COMANDO 143, onde atribuí a recusa ao D-F7-006). |
| teste | `tests/unit/test_robustness_pipeline.py:434 test_without_cf_min_or_with_another_q_ref_f7_refuses_before_reading_anything` existe. |
| config | `experiments.yaml thresholds.regret_quantile: 0` (confere). |
| OQ-020 | Aberta: testar sensibilidade do top-k a q_ref em {0, 0,01}; adotar o mínimo salvo se outliers dominarem. Não decide por 0 nem por 0,01. |
| OQ-091 | Aberta (criada em 13/11): critério numérico de troca, convenção para regret negativo com q_ref > 0, ajuste da guarda V-03 e a mudança para o F7 aceitar q_ref != 0. **Cita `evaluator.py:343` para a guarda; a guarda está em 341-342** (343 é `fragile = ...`). |
| conclusão | A regra é mais geral que o código: descreve um quantil; o código só constrói o mínimo, por decisão registrada (D-F7-009, OQ-020). Não é erro; é limite de implementação, documentado. Estado de M-F7-02: ok com ressalva q_ref = 0. |

### (b) CF_min (M-F7-01, kernel, `_check_floor`)

| ponto | achado |
|---|---|
| regra | METHODOLOGY.md:305 (M-F7-01): viável quando `CF(m, s0) >= CF_min`, lido do F5 no nominal, não dos sorteios; o kernel recebe um piso de energia por célula; para célula viável, um sorteio só é inviável se a energia é zero; célula com `CF < CF_min` em `f0` sai do conjunto F7; viável em `f0` e abaixo em algum membro é *climate-fragile*. |
| conjunto F7 | `robustness_analysis/cell_set.py:128`: `ok_ref = (ref.cf >= cf_min) & (energy_mwh > 0)` (sai quem tem CF abaixo em `f0`). |
| fragilidade | `cell_set.py:150`: `fails[:, j] = item.cf[index] < cf_min`; `evaluator.py:343`: `fragile = np.any([w.fails_cf_min ...])`. |
| piso | `cell_set.py:155`: `floor = np.where(fails, np.inf, 0.0)` (+inf onde `CF(m, s0) < CF_min`, 0 nos demais), entregue como `world.floor` a `lcoe_block(..., min_energy_mwh=world.floor[...])` (`evaluator.py:128` e `:212`). |
| kernel | `lcoe_modeling/kernel.py:267-273 _check_floor`: exige um valor por célula, rejeita NaN e negativo (infinito é permitido); em `lcoe_block` (`:292-`) a entrada com energia anual amostrada abaixo do piso vira `+inf`; piso 0 não muda nada. O kernel não conhece CF_min (D-F6-001). |
| valor | `cf_min` é `null` em PRT, BRA e IND (`pending_research`); só ZZZ tem valor (0,15 solar e 0,30 eólica, `synthetic: true`). Sem CF_min o F7 recusa antes de ler (teste acima). |
| conclusão | Regra e código batem: a comparação é `>=` em ambos, usa o CF nominal do F5, e o kernel só vê o piso. A ponta primária da faixa de CF_min e o curtailment seguem em aberto (OQ-090, L-033). |

### (c) Desfecho do PRIM (M-F7-08, pipeline, `prim.outcome_threshold`)

| ponto | achado |
|---|---|
| regra | METHODOLOGY.md:345: a unidade é o futuro `f = (m, s)` do núcleo (cada membro vezes sorteios `s >= 1`), não a célula; `V_f` é a parcela de capacidade da lista nominal `S^nom_k` cujos postos por regret em `f` passam de `k + m`; caso de interesse quando `V_f >= theta`, `theta = 0,20`. |
| unidade | `robustness_analysis/assemble.py:343`:`draws = futures[futures["sample"] >= 1]`; a saída é `displaced_capacity_share` por futuro (`futures.py:79`, forma `(M, N+1)`). |
| V_f | `robustness_analysis/futures.py:228-232`: `beyond = short_local & (rank_in_ranked >= outcome.k + outcome.m)`; `displaced[j, s] = q_local[beyond].sum() / short_capacity`. Os postos são de 0 a n-1 (`_positions`, `futures.py:98`), então `>= k+m` equivale a posto (de 1) `> k+m`, como a regra. Não verifiquei se o vetor ordenado é o LCOE ou o regret na futura `f`; a regra diz que a ordem é a mesma. |
| limiar | `scenario_discovery.py:65-67 cases_of_interest`: `shares >= theta - TOLERANCE`, com `TOLERANCE = 1e-12`; a regra diz `>=` (diferença só numérica). |
| config | `experiments.yaml prim.outcome_threshold: 0.2`, lido em `pipeline.py` (`DiscoverySettings(prim_cfg.outcome_threshold, ...)`) e repetido para `sensitivity.outcome_threshold` {0,1; 0,3}. Todos os números do bloco `prim` conferem (tabela acima). |
| conclusão | Desfecho por futuro, ponderado por capacidade, limiar 0,20: regra e código batem. Estado: ok. A questão A5 (e OQ-091) trata de outra coisa: o corte em zero do regret com q_ref > 0. |

### (d) Conversão de moeda (`to_usd_2024`, D-F6-008, `price_year`)

| ponto | achado |
|---|---|
| função | `lcoe_modeling/connection.py:88-105 to_usd_2024(amount, cost, indices)`: `usd_2024 = amount * scale * deflator[2024] / deflator[price_year] / fx[2024]`. USD de 2024 não precisa de índice; USD de outro ano levanta `ConversionError` ("needs a US deflator, which is not loaded"); ano nulo levanta erro. |
| índices | `GeoFREA_data/external/world_bank/conversion_indices.json` (gerado em 2026-11-02): `NY.GDP.DEFL.ZS` e `PA.NUS.FCRF` para BRA, IND e PRT, 2015 a 2025. **Não há série dos EUA.** |
| D-F6-008 | `lcoe_modeling/inputs.py:161-163`: recusa `price_year != 2024` só para `COST_PRICE_KEYS = (capex_usd_per_kw, opex_var_usd_per_mwh)`, os custos do bloco da tecnologia, que já são USD. |
| parameters.json | `price_year` nas chaves com valor: 2024 em 36, 2023 em 2 (PRT linha e baia, em MEUR), 2025 em 1 (IND linha, INR crore), 2022 em 1 (IND baia), 2017 em 1 (BRA baia, BRL), 2016 em 1 (BRA estrada alta, BRL), nulo em 3 (`road_cost_per_km` dos três, ver `road_cost_excluded`). |
| regra | M-F6-08: os custos de conexão ficam **na moeda e ano nativos** e o F6 os converte (deflator nacional e câmbio médio de 2024, `GEOFREA_DATA_DIR/external/world_bank/`). M-F6-07 e S-07: preços em USD constantes de 2024. |
| conflito com a decisão de 13/11 | A entrada "valores monetários na configuração" do DECISIONS.md diz que eles "entram na configuração já em USD de 2024 (o F6 exige `price_year` 2024, D-F6-008)". O código faz o contrário para os custos de conexão: guarda moeda e ano nativos e converte no F6; a exigência de 2024 vale só para capex e O&M variável. A entrada precisa de ajuste do autor, ou o código muda. |
| USD 2025 para 2024 | Nenhum valor hoje depende de um índice dos EUA: os custos em USD estão todos com ano 2024. O fator 0,9744 (CPI-U) ou 0,9725 (deflator do PIB) só seria usado se entrasse um custo em USD de 2025 (A7, OQ-093); `to_usd_2024` o recusaria hoje. |

### (e) Hipóteses H1 a H5 citadas na F8

| hipótese | regra no METHODOLOGY | bloco em experiments.yaml | módulo | arquivo | arquivos de teste que a citam | .tex em docs/thesis/hypotheses | arquivos de F8 que a citam | citada em M-F8-03 |
|---|---|---|---|---|---|---|---|---|
| H1 | sim (M-F7-07, bloco H1) | sim | sim | h1_rank_robustness.py | 8 | sim | 3 | sim |
| H2 | sim (M-F7-07, bloco H2) | sim | sim | h2_aggregation.py | 7 | sim | 3 | sim |
| H3 | sim (M-F7-07, bloco H3) | sim | sim | h3_robust_vs_nominal.py | 8 | sim | 2 | sim |
| H4 | sim (M-F7-07, bloco H4) | sim | sim | h4_axis_dominance.py | 8 | sim | 4 | sim |
| H5 | sim (M-F7-07, bloco H5) | sim | sim | h5_climate_pressure.py | 8 | sim | 2 | sim |

Grandezas que M-F8-03 nomeia por hipótese, procuradas por nome no código de F7 e F8 (presença do nome, não conferência do cálculo):

| hipótese | grandezas achadas |
|---|---|
| H1 | c_k: sim, v_k: sim |
| H2 | o_ref: sim, delta_z: sim |
| H3 | d_ref: sim, pi: sim |
| H4 | d_clim: sim, d_tec: sim, rho: sim |
| H5 | r_loss: sim, r_exp: sim |

Conclusão: as cinco hipóteses têm regra (M-F7-07), bloco de configuração, módulo e teste; todas aparecem na F8. Os limiares conferem (tabela do item 2). H4 tem fase própria `cross_country_h4` (M-F7-07 itens 4.1 e 4.2). Nenhuma foi executada em país real (item 3).

## 3. Especificado, não executado

**Evidência de execução em país real** (manifestos de `GeoFREA_data/outputs/<ISO3>/manifest.json`, lidos agora):

| país | fases F6 a F8 no manifesto | últimas fases que constam (F5) |
|---|---|---|
| PRT | nenhuma das sete fases consta no manifesto | technical_potential, potential_maps |
| IND | nenhuma das sete fases consta no manifesto | technical_potential, potential_maps |
| BRA | nenhuma das sete fases consta no manifesto | technical_potential, potential_maps |

As sete fases (`lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, `external_validation`, `results_synthesis`, `lcoe_maps`, `robustness_maps`) **não constam no manifesto de PRT, IND nem BRA**; só `technical_potential` e `potential_maps` rodaram (2026-11-12). Elas rodam apenas sobre os mundos sintéticos ZZZ e ZZZ2, em testes e CI (`tests/synthetic/`: 7 arquivos; F1 a F8 em `test_zzz2_end_to_end.py::test_every_phase_from_f1_to_f8_runs_and_succeeds`).

**Por que ainda não rodam em país real** (estado da config hoje, sem inferência de motivo além do que a config mostra):

| fase | estado e bloqueio na config |
|---|---|
| F6 `lcoe_modeling` | `group3_problems` sem problemas e o F5 rodou nos três países; nada na config bloqueia o F6 hoje. **Não encontrei registro de por que ele não foi rodado.** |
| `sample_size_convergence` | exige `cf_min` e `top_k_percent` por tecnologia (ambos `null`): recusa antes de rodar (`ConvergenceConfigError`, `convergence.py:233-243`). |
| F7 `robustness_analysis` | exige `cf_min`, `tau_lcoe_usd_per_mwh`, `top_k_percent` (todos `null` em PRT, BRA e IND), `national_targets` (todas `null`) e `hazard_thresholds` (todas `null`, OQ-051). |
| F7b `external_validation` | `config/published_potential.yaml` tem `entries: []`: sem estimativa publicada, a tabela comparativa fica vazia (teste `test_f8_shows_the_empty_published_comparison...`). |
| F8 `results_synthesis` | lê artefatos persistidos do F5, F6, F7 e F7b; sem F6, F7 e F7b reais, não há o que sintetizar além do F5. |

**Itens documentados nas regras que, por isso, estão "especificado, não executado"** (todas as 28 regras têm *execução real* = não; as de F7b e F8 e as hipóteses são as que o pedido destaca):

| regras | o que documentam | marca |
|---|---|---|
| M-F7b-01 a M-F7b-04 | inventário GEM, enriquecimento, tabela comparativa com o publicado, saída da fase | F7b nunca rodou em país real; o publicado está vazio |
| M-F8-01 a M-F8-03 | leitura de artefatos, todas as saídas da Seção 10 em `outputs/thesis/`, perfis `hypothesis_profiles` e T-R8 | F8 nunca rodou em país real; testada em ZZZ/ZZZ2 |
| M-F7-07 (H1 a H5), M-F7-06 (H4) | veredito de cada hipótese e fase `cross_country_h4` | sem veredito real: os limiares estão fixos e pré-registrados, os dados de decisão (cf_min, tau, p_k, metas, hazard) estão nulos |
| M-F7-08 (PRIM) | caixa de descoberta de cenários e bootstrap | só em ZZZ/ZZZ2 |
| M-F6-01 a M-F6-10 | kernel, amostragem, sumários, curvas de oferta, degradação, conexão | kernel e F6 testados em sintético; F6 não rodou em país real |

Seção 10: das 18 linhas `T-*` da tabela de saídas, nenhuma foi produzida com dados de PRT, IND ou BRA para F6 em diante (`T-R*` e `T-O*` de F6, F7, F7b e F8). Não conferi quais das saídas de F4 e F5 existem.

## 3. Código com lógica própria sem regra M-F6 a M-F8

Heurística (candidatos, não confirmados): funções e classes públicas de nível de módulo com 25 linhas ou mais, sem `M-F*` no docstring da função nem no do módulo.

| fase | pacote | públicas no nível do módulo | grandes sem M-F* | dessas, sem nenhum ID |
|---|---|---|---|---|
| F6 | lcoe_modeling | 48 | 1 | 0 |
| F7 | robustness_analysis | 215 | 2 | 0 |
| F7b | external_validation | 24 | 0 | 0 |
| F8 | results_synthesis | 67 | 3 | 0 |

Exemplos sem nenhum ID (até 10, os maiores):

(nenhum)

Lista completa: `05b_code_without_mf_rule_F6_F8.tsv`.

## 4. Afirmações que dependem de dado (linhas 280 a 361)

| padrão | acertos | com data ou auditoria na linha |
|---|---|---|
| percentual | 5 | 4 |

Casos que encontrei por leitura nas regras de F6 a F8:

| onde | afirmação | marcação sugerida |
|---|---|---|
| M-F6-08 (linha 297) | "IND bay, BRA line and bay and the road of the three countries have no value yet (OQ-001)" | já desatualizada (item 5); trocar por tabela gerada de `parameters.json` ou por nota com data |
| M-F6-10 (linha 299) | "F6 refuses to run ... while a Group 3 cost has no value (OQ-001)" | OQ-001 está fechada; o texto cita uma OQ resolvida como pendente |
| D-F6-008 / `F6_lcoe_modeling.md:24` | "BRA, PRT and IND fail with 32 items each" | valor de data X (é de uma rodada antiga; hoje `group3_problems` dá 0 problemas) |
| M-F8-03 (linha 361) | contagens e verdicts por hipótese citados como exemplos | não há números de execução na regra; ok |

## 5. Trechos que contradizem DECISIONS.md, OPEN_QUESTIONS.md ou LIMITATIONS.md

OQ citadas nas 28 regras: 11 citações de 9 OQ; estado em `OPEN_QUESTIONS.md`: {'open': 6, 'fora da tabela': 3, 'closed_with_proxies': 2}.

| trecho do METHODOLOGY | registro | conflito |
|---|---|---|
| M-F6-08 (linha 297): IND bay, BRA line e bay "não têm valor (OQ-001)" | OPEN_QUESTIONS.md:34 (OQ-001, `Closed with proxies`, COMMAND 86) e `parameters.json` | OQ-001 diz que todo custo unitário do Group 3 tem valor (BRA line, BRA bay, IND line, IND bay como proxy); `parameters.json` tem os quatro. O texto da regra está desatualizado. |
| M-F6-10 (linha 299): o F6 recusa enquanto um custo do Group 3 não tem valor (OQ-001) | OPEN_QUESTIONS.md:34 e `group3_problems` ao vivo | OQ-001 está fechada e `group3_problems` retorna 0 problemas para os seis casos; a estrada é nula mas `road_cost_excluded: true`. A frase descreve um estado anterior. |
| M-F6-08 (linha 297): custos de conexão em moeda e ano nativos, convertidos pelo F6 | DECISIONS.md (13/11/2026) "valores monetários na configuração" | A entrada diz que entram "já em USD de 2024"; a regra e o código convertem no F6. Pedido do autor de 13/11 registrado como decisão, sem a conferência com a regra. |
| M-F7-02 (linha 306): L* é o quantil `q_ref` | DECISIONS.md (nenhuma) e OPEN_QUESTIONS.md OQ-020 | Sem contradição: a regra diz padrão 0; OQ-020 está aberta; o código recusa ≠ 0. Registrado no ponto (a). |
| M-F6-02 e M-F7-04 (τ, CF_min, p_k fora do LHS) | DECISIONS.md (13/11) "parâmetros de decisão fora do LHS" | Sem contradição de texto, mas **a regra não descreve os eixos de sensibilidade de τ, CF_min e q_ref**; só `p_k` aparece (M-F7-07, `p_k` em {0,05; 0,10; 0,20}). Lacuna da regra frente à decisão. |
| L-033 (curtailment não modelado) | M-F6-01 a M-F6-10 | Sem contradição: nenhuma regra de F6 modela curtailment. |

Não comparei as 28 regras com as 66 entradas do DECISIONS.md uma a uma; li o que o pedido destacou (ponto 2) e o que a leitura das regras de F6 apontou.

