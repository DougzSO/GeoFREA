# Prontidão de F6 a F8 (COMANDO 169, somente leitura, 2026-11-17)

Escrito para: o autor, para levar ao chat de planejamento antes do 170.

Regras 1 a 4: nenhuma violada. Nenhuma fase, main ou orquestrador rodou em dado real. Instantâneo dos manifestos em `GeoFREA_data/_snapshots/20261117_pre169/`. Nenhum arquivo rastreado alterado (scripts auxiliares ficaram no scratchpad).

## Resumo: o que muda os comandos seguintes

1. **BLOQUEIO do 179: `sampler.max_size_for_convergence` é `null`.** A fase `sample_size_convergence` recusa rodar com esse valor (`convergence.py:247`, "the author's ceiling, D-F6-004"). Nenhum comando de 170 a 192 define o teto. O V182 supõe "o maior tamanho que o código testa", que só existe com o teto. O valor é do autor. A chave não está no subconjunto pré-registrado, então definir o teto não muda o digest.
2. **Premissa falsa do 177, item 1b (V177):** o O&M eólico de BRA e IND não é proxy. Em `config/parameters.json`, `opex_fixed_frac` eólico de BRA (0,0222) e IND (0,0207) já vem do IRENA 2024 (tabela A3, p. 209), `proxy: false`, Tier 1. A auditoria de produção dá 0 erros nos três países. O item 1b se aplica só "se o 169 mostrou que o `--production` recusa" e não recusa: **1b não se aplica**. A OQ-016 já não está em OPEN_QUESTIONS.
3. **Premissa do V174 (T1): o grupo5.tex não traz limiar de exposição θ.** A tab:g5-ind e o texto só definem os indicadores (contagem de dias acima de 35 e 40 °C, Rx5day, p95 de dias úmidos) e dizem que o gust "não tem limiar". Nenhum valor em dias por ano, mm ou fração, com fonte, de qualquer canal. Aplicada a regra como escrita (T2), os quatro canais saem EXCLUÍDOS e o H5b fica "not available" na v1.0. O 173 vai tabular isso; o 174 não é pergunta ao autor, é resultado do procedimento. Se o autor esperava canais dentro, precisa decidir antes.
4. **Não existem `--real-run` nem `--plan`** em `main.py` (o 176 cria os dois). Hoje o único freio é a guarda do pré-registro (tag `prereg-v1`) nas fases F6 e F7 e o fato de `run.target_phases` do settings parar em `overview`. O `--production` existe e é opcional.
5. **V-83 já foi feita, contra o W5E5, não o ERA5** (`docs/_audit/2026-10_data_diagnostics.md`, seção 9). A regra de calor do V174 pede ERA5: é trabalho novo do 173.
6. **`memory.max_batch_gb` não está no escopo de fingerprint de nenhuma fase.** O V179 a V181 diz que reduzir esse lote deixa `lcoe_modeling` de PRT e IND "stale". Pela configuração, não deixa. Só deixaria se o código de F6 mudasse.
7. **O tamanho adotado da U-04 não tem chave própria.** O F6 lê `sampler.initial_size`, que também é o ponto de partida da dobra da convergência. O 182 precisa dizer que a chave a escrever é `sampler.initial_size`.
8. **BRA `technical_potential` no manifesto novo: pico de 1.876 MB contra o teto de 1.984 MB** (o `memory_budget.json` ainda registra 1.579 MB, da medida de 2026-11-10). Margem de 5%.

## Item 1. Mundo sintético

Comando: `pytest tests/synthetic -m synthetic` com `--basetemp` em diretório temporário. Resultado: **129 passed, 1 deselected, 0 falha, em 18 min 36 s**.

Fases que executam de ponta a ponta no ZZZ (`test_zzz_end_to_end.py`, lista `PHASES`, mais as de F1 a F5 que entram como upstream): `hazard_context`, `technical_potential`, `potential_maps`, `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, `external_validation`, `lcoe_maps`, `robustness_maps`, `results_synthesis`. O `cross_country_h4` roda em teste próprio (`test_cross_country_h4_gives_not_testable_for_one_country_and_a_verdict_for_three`, um e três países). O segundo mundo (`test_zzz2_end_to_end.py`, "every phase from F1 to F8") reproduz todas com validação à mão. A escala 0,1° roda as mesmas fases no ZZZ. **Nenhuma fase esperada deixou de rodar** (A-06 sem pendência).

Nota: nos testes `sample_size_convergence` roda com `INITIAL_SIZE=16` e `CEILING=64` definidos no teste, ou seja, o teto é obrigatório também ali; em produção ele é nulo (resumo, ponto 1).

## Item 2. Auditoria de produção (sem rodar fase)

Chamada: `production.audit_parameters(parameters, technologies, [ISO], ['solar','wind'])`, com `config/parameters.json` e `technologies.yaml` do disco.

| País | Erros (recusa) | Avisos |
|---|---:|---:|
| PRT | 0 | 16 |
| IND | 0 | 19 |
| BRA | 0 | 17 |

Os avisos são todos Tier 3 (U-07) em valor ou faixa (discount_rate, luf, top_k_percent; wind eta_loss e cf_min; connection reference_project_mw, tortuosity_grid e _road, long_distance_flag_km, transmission_loss_per_km e a sensibilidade), mais `road_cost_excluded` como cenário central (LCOE é piso) nos três e, só em IND, `connection bay_cost: status proxy, a stand-in value (COMMAND 86)` (aviso, não erro). IND e BRA têm também aviso Tier 3 na faixa de `wind opex_fixed_frac`.

O&M eólico de BRA e IND: **não é proxy** (ver o resumo, ponto 2). PRT eólico: 0,024714, Tier 2, IRENA Europa.

## Item 3. Linha de comando

- Opções de `main.py`: `countries` (posicional), `--phases`, `--production`, `--revalidate`, `--scale {0p05deg,0p1deg}`, `--publish-reference`, `--rerun`. Não existem `--plan` nem `--real-run`.
- Só F6 e convergência: `python main.py PRT --phases lcoe_modeling,sample_size_convergence` (as fases anteriores entram automaticamente; as que estão `success` retomam do manifesto).
- Modo de plano: não existe. `scripts/run_unattended.ps1` tem `-DryRun` (só escreve no log o que faria), que não é o mesmo que listar fases stale.
- Guarda do pré-registro: `main.py:1531` passa `preregistration_guard=lambda phase: verify_preregistration(...)` ao orquestrador. Roda antes de `lcoe_modeling`, `sample_size_convergence` e `robustness_analysis`; compara o digest do subconjunto com a tag `prereg-v1`. País sintético é ignorado.
- Contra rodada real acidental (L-244): só a guarda (exige a tag e o digest igual), e `run.target_phases` do settings (padrão para em `overview`). Com `--phases lcoe_modeling` explícito e a tag válida, a rodada real roda. Não há trava específica (o 176 cria).
- `run_unattended.ps1`: roda `main.py <ISO> --phases <P> --rerun <P>`, sem `--production` nem `--real-run`; lista padrão de fases vai até `potential_maps`. O 176 item 4 e o 181 precisam passar as opções.

## Item 4. Tamanho e tempo

Células candidatas por país e tecnologia (linhas de `ensemble_<tech>__central.parquet`, uma por célula do conjunto candidato; o conjunto F7 é esse conjunto depois de `cf_min` e do filtro de ensemble completo, então os números são tetos):

| País | Solar | Eólico |
|---|---:|---:|
| PRT | 3.415 | 3.332 |
| IND | 93.701 | 75.535 |
| BRA | 190.521 | 178.289 |

Membros (`members.yaml`): 37 = 1 de referência (1995-2014) + 18 da janela principal (2041-2070) + 18 da janela de sensibilidade (2071-2100): 6 GCMs x 3 SSPs x 2 janelas. Tamanho de amostra configurado: `sampler.initial_size = 500` (LHS). Futuros por célula: 18 membros x 500 amostras = 9.000 na janela principal e 9.000 na de sensibilidade. Teto da dobra: nulo (ver o resumo).

Medida disponível: o `wall_s` do F5 nos manifestos novos (PRT 7,8 s, IND 96 s, BRA 301 s; pico 364, 1.049 e 1.876 MB). O `size_f5_to_f8.py` roda fases numa cópia dos dados reais; não rodei (cópia pesada e fora do "somente leitura"). Existe `docs/_audit/` de dimensionamento antigo, não reaproveitado.

Estimativa (base: razão de células BRA/PRT 56x, IND/PRT 27x, mais o custo por célula x amostra x membro do kernel fechado do F6; sem medida de F6 em dado real):
- F6 (500 amostras): PRT segundos a poucos minutos; IND da ordem de 10 a 30 min; BRA da ordem de 0,5 a 2 h.
- Convergência: refaz o F6 para cada tamanho dobrado (500, 1.000, 2.000...), então custa cerca de 2x o tamanho final; no BRA, horas. O teto decide.
- F7: pesa mais que o F6 (regret por membro e amostra): BRA da ordem de várias horas.
A incerteza é de ordem de grandeza. O 179 e o 180 medem PRT e IND e refinam.

## Item 5. Memória

`config/memory_budget.json`, `phase_caps.phases`, tem teto só para as 12 fases de F1 a F5 e apoio. **Não há entrada para** `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, `cross_country_h4`, `external_validation`, `lcoe_maps`, `robustness_maps` e `results_synthesis`: o teto que vale é o `cap_mb` do arquivo, 1.536 MB (limite duro 1,25x = 1.920 MB; folga `over_cap_reserve_mb` 300). `memory.max_batch_gb = 1` (`config/settings.yaml`): F6 e F7 dimensionam o bloco de células para que 4 arrays vivos de célula x amostra fiquem abaixo de 1 GB (`lcoe_modeling/inputs.py::cells_per_block`, A-10). `GEOFREA_MEMORY_CAPS=0` desliga os tetos de um rodada de `main.py` (medição e `peak_rss_mb` continuam). Espaço livre em D: 924 GB. `max_batch_gb` não entra em nenhum escopo de fingerprint.

## Item 6. U-04

- Tamanhos testados: partem de `initial_size` (500) e dobram até o teto.
- Regra de parada: 1 - Jaccard dos top-k de dois tamanhos consecutivos < `convergence_tolerance` (0,01).
- Limite máximo: `max_size_for_convergence`, nulo: a fase recusa (resumo, ponto 1).
- Onde o tamanho adotado é escrito: o resultado da fase traz `adopted_size` (None se o teto veio antes); a configuração não é atualizada sozinha. O F6 lê `sampler.initial_size`; não há chave separada.
- `sampler` não está no subconjunto pré-registrado (`PARAMETER_SELECTORS` e `EXPERIMENT_SELECTORS`). Está no escopo de fingerprint de `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis` e `results_synthesis`.

## Item 7. Sensibilidades (M-F7-07 e M-F7-08)

Todas dentro de uma invocação de `robustness_analysis`, salvo a escala:
- H1 a H3: sem o GCM da exceção de TCR, p_k em {5, 10, 20} %, m em {k/2, k, 2k} (`sensitivity_variants` de `h1_`, `h2_`, `h3_`). H4: eixo climático por SSP, sem o GCM de TCR, p_k, m, fronteiras {0,30; 0,70} e {0,45; 0,55} (`h4_axis_dominance.py`).
- H5: λ = 0,10, **τ nas duas pontas do faixa registrada** (`h5_climate_pressure.py`, `tau_min` e `tau_max`), domínio dinâmico, sem o GCM de TCR.
- SR: usa só o τ primário (`pipeline.py`, `decision.tau`); as pontas de τ aparecem só no H5.
- Janela 2071-2100: papel `sensitivity` dentro do mesmo `robustness_analysis` (`WINDOW_ROLES = ("core", "sensitivity")`). Ressalva: `hazard_windows_available` tem só 2041-2070, então a exposição de perigo da janela de sensibilidade não existe.
- Escala 0,1°: `--scale 0p1deg` (execução separada, manifesto `manifest__0p1deg.json`). Testes sintéticos cobrem F3 a F7 nessa escala em ZZZ (`test_the_scale_check_runs_every_phase`, `test_f7_runs_at_the_coarse_scale...`). Não verificado em dado real.

## Item 8. Figuras

`settings.figures` hoje é `summary`. Está no escopo de fingerprint de `climate_maps`, `overview`, `potential_maps`, `lcoe_maps` e `robustness_maps`. Trocar para `all` deixa stale, nos três países, `climate_maps`, `overview` e `potential_maps` (as duas outras ainda não rodaram). `results_synthesis` e as T-* não leem `settings.figures`. Não há sobreposição por linha de comando em `main.py`.

## Item 9. Limiares de perigo

- `hazard_thresholds` em `experiments.yaml`: os cinco canais com `threshold: null`, `source: null`, `tier: null` (tx35_days days, tx40_days days, rx5day_mm mm, wet_p95_exceed_freq fraction, gust_mean_annual_max_ms m/s).
- `hazard_indicators` (definições): tx35 (35 °C, Tier 1, fonte CRAEI/IPCC AR6 Atlas), tx40 (40 °C, Tier 1), wet_p95_exceed_freq (1,0 mm, p95, Tier 2). **rx5day_mm não tem definição em `hazard_indicators`.**
- grupo5.tex, tab:g5-ind: tx35 "3 (author threshold)", tx40 "1 for wind (edge of the normal operating range), 3 for PV", rx5day "3", wet_p95 "3", gust "n/a, context only". Fonte com chave do .bib: o texto cita IEC 61400-1 (faixa -10 a +40 °C) para o tx40 do eólico; para os demais não há θ numérico em dias, mm ou fração. Marcas `% verify` no grupo5.tex nas linhas 17, 21, 25, 26, 53, 56, 57 e outras.
- `hazard_thresholds` **não** está no subconjunto pré-registrado. Está só no escopo de fingerprint de `robustness_analysis` (nenhum manifesto real dela existe, então nenhuma fase com manifesto fica stale ao preenchê-lo).
- V-83: feita contra o W5E5 em 2026-10-15 (`docs/_audit/2026-10_data_diagnostics.md`, seção 9); r de 0,96 a 0,997 no limiar de 35 °C. Contra o ERA5: não feita. `raw/era5` tem `IND_box_daily_jobs.json` e a pasta por país; a presença do máximo diário por país não foi conferida arquivo a arquivo.

## Item 10. OQ-114, disponibilidade

- Usinas eólicas do GEM (`raw/gem/<ISO>/gem_solar_wind_<ISO>.parquet`), em operação e com coordenada: BRA 1.144 usinas, 36,04 GW; IND 679, 38,94 GW; PRT 361, 5,73 GW (todas as operacionais têm lat e lon).
- `raw/gwa`: só `wind_speed`, `weibull_a`, `weibull_k` e `air_density` (3 alturas) por país, mais CHN e PAK. **Sem camadas de capacity factor** (o 170 baixa pela fonte do F1).
- CF de frota já no repositório: PRT eólico 27,4% (REN 2023) e solar 17,2%; BRA eólico 38% (ABEEólica, Boletim Anual 2025, p. 8; DEC-088 b); IND nenhum (o 22% de tab:g4-cf é piso da CERC). PDFs em `GeoFREA_data/external/solar_basis/` (`abeeolica_boletim_anual_2025.pdf`, `ren_dados_tecnicos_2024.pdf`, `cerc_order_517_mp_2024.pdf`) e `extracts.json`. Base (bruto ou líquido de curtailment) e período: DEC-088 e L-033 dizem que o valor de frota é líquido e o F6 não modela curtailment.

## Item 11. F7b

OQ-068 vigente: `external_validation/pipeline.py:201` ainda chama `prepare_shared_layers` (camadas F3 inteiras). Pico estimado no BRA: cerca de 1,5 GB antes de avaliar a primeira usina (texto da OQ-068), contra o teto de 1.536 MB (duro 1.920). O 187 se aplica.

## Item 12. F8: saídas T-*

Todas as 18 saídas da seção 10 têm construtor em `results_synthesis/runner.py` (tabela de despacho, linhas 48 a 65): T-M1 `dag.t_m1`; T-M2 e T-M3 `method_tables`; T-R1, T-R2, T-R11 e T-O3 `potential_and_cost`; T-R3 `climate_change`; T-R4 e T-R5 `ranking_figures`; T-R6, T-R7, T-R9, T-R10, T-R12, T-O1 e T-O2 `robustness_tables`; T-R8 `synthesis`. Nenhuma "não implementada". Conformidade só em país sintético (PROGRESS).

## Item 13. window_list_131 (`docs/_audit/window_list_131.md`)

O documento não tem coluna de estado; todos os itens estão "held back" (não feitos) na data do 131.
1. Nove formas de lint da OQ-073 (`raster_io`, `cf_table`, `cells`): fecha até 12 fases.
2. `spawn` explícito em `era5.py` (OQ-078): depende de reproduzir o travamento no Linux; fica fora (o 177 já exclui).
3. Nota da base DC na unidade de `reference_project_mw` em `parameters.json`, três países.
4. Código morto (`_pixel_raster`, `draw_backdrop`, `draw_overlay` etc.).
5. Correção da OQ-074, se estiver em `viz/mapstyle.py`.
6. Escrever as tabelas do F5 com o esquema do modelo de linha (OQ-084, correção 2): muda o writer de `technical_potential`.
7. Otimizações da seção G da auditoria 130.
8. Retrabalho de memória de `hazard_context`, `climate_maps` e `overview` do BRA (OQ-068).
9. Repontar três notas de `parameters.json` para `docs/_audit/groups1-2_implementation_report.md`.
Marcados para a janela única pelo 177: itens 3 e 9 (as duas mudam notas de `parameters.json`, mesmo arquivo e mesmo efeito de fingerprint). Os itens 1, 4, 5, 6, 7 e 8 o 177 chama "demais itens marcados para a próxima rodada completa": **o documento não marca quais**; o 177 precisa que o autor diga (ou o 177 aplica só 3 e 9).

## Item 14. Premissas dos comandos 170 a 192

- **170:** confirmadas, com o acréscimo do V170 (não há CF do GWA em `raw/gwa`; baixar). L-028, L-032, L-033 e tab:g4-cf existem.
- **171:** confirmadas (DEC-088, L-028, L-032).
- **172:** confirmadas.
- **173:** premissa a ajustar: a V-83 existe contra o W5E5, não o ERA5; `rx5day_mm` não está em `hazard_indicators`.
- **174:** contradição: o grupo5.tex não tem θ de exposição (resumo, ponto 3). Também `hazard_thresholds` não está no subconjunto, então o digest não muda e não há fase com manifesto stale.
- **175:** confirmadas: τ nas pontas no H5, top_k 5 e 20 em H1 a H4, SR só com τ primário. OQ-094, OQ-008, DEC-061, DEC-074, DEC-085, DEC-088 a DEC-090 existem.
- **176:** `--real-run` e `--plan` não existem: o comando se aplica por inteiro.
- **177:** item 1b não se aplica (resumo, ponto 2). A lista "demais itens" da window_list não está marcada (item 13).
- **178:** confirmadas: `--publish-reference`, `scripts/restamp_parquet2.py` e o baseline `prereg_162F_baseline_20261117.json` existem.
- **179:** bloqueio do `max_size_for_convergence` (resumo, ponto 1). `--real-run` depende do 176.
- **180:** ok; a estimativa do BRA vai pela proporção de células.
- **181:** `run_unattended.ps1` não passa `--production` nem `--real-run` (176 item 4).
- **182:** o "limite do código" é o teto nulo (ponto 1); a chave a gravar é `sampler.initial_size` (ponto 7); `sampler` está fora do subconjunto, então vale o ramo "diferente: alterar a configuração"; ficam stale `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis` e `results_synthesis` (nenhuma com manifesto real hoje).
- **183 a 186:** confirmadas; sem teto de memória medido para F6 a F8.
- **187:** confirmada (OQ-068 vigente).
- **188:** confirmada; tetos de F6 a F8 ausentes.
- **189:** janela 2071-2100 já sai do `robustness_analysis` (item 7); só conferir as tabelas. A escala 0,1° tem a opção e só testes sintéticos.
- **190:** as T-* não leem `settings.figures`; o V190 manda manter `summary`.
- **191:** ok. Pode não haver manifesto de escala (V189).
- **192:** `--allow-without-reference` existe em `scripts/publish_reference.py`; no `main.py` só `--publish-reference`.

## Item 15

Nenhum arquivo rastreado alterado; nenhuma fase em dado real. `git status` limpo e manifestos com o SHA-256 do início (verificado ao fim).
