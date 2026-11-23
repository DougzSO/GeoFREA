# Produção da IND, robustness_analysis, e estimativa do BRA (COMANDO 184)

Escrito para: o autor, para conferir o F7 da IND e decidir a memória do BRA no 185.

Data: 2026-11-18. HEAD `3fcdfbe` (sem alteração de código ou configuração neste comando); tag `prereg-v1` em `ccf764f`; digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneo: `GeoFREA_data/_snapshots/20261118_pre184`.

## Itens 1 a 5 do 183, com a IND
Comando: `python main.py IND --phases lcoe_modeling,robustness_analysis --real-run --production`. O `--plan` mostrou `lcoe_modeling` stale (182, a 4.000 amostras) e `robustness_analysis` sem entrada.

| Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) | acima do teto |
|---|---|---:|---:|---:|---:|---|
| lcoe_modeling | success | 1.367,8 | 1.492,4 | 1.128 | 1.536 | não |
| robustness_analysis | success | 9.268,8 (2 h 34 min) | 9.628,8 | **1.908** | 1.536 | **sim, 372 MB** (abaixo do limite rígido de 1.920 MB: não parou, margem de 12 MB) |

Pré-registro: `digest_live` = `digest_tag` = `51381bfcd1c1a6a1d1ea43fa7a86dc82ad1b37425c32d6b2900008611533fac6`. 80 tabelas + JSON; n_samples 4.000, semente 42, `provisional` falso. Aviso de memória registrado no log (pico 1.908 MB, 372 MB acima do teto).

Avisos do log: células sem LCOE no F6 deixadas de fora no F7 (L-253): restritivo 75 células (2.775 linhas), permissivo 151 (5.587); no central são as 84 do solar. Itens ignorados: exposição aos 5 canais (OQ-051).

### Invariantes V-03
Todas atendidas, sem violação, nas quatro combinações (solar e eólico, 2041-2070 e 2071-2100): MR >= 0 e finito nas ranqueadas (solar 0,0052 a 1,952; eólico 0,0023 a 3.108 principal, 4.635 sensibilidade; o máximo eólico é de células de LCOE muito alto, finito); 0 <= SR <= 1 (eólico chega a 1 e solar a 0,856); ranqueadas + climate-fragile = conjunto F7; nenhuma ranqueada com MR infinito; todo futuro tem célula viável (`lowest_lcoe` finito e positivo, 72.018 e 60.015 futuros), logo o argmin tem r = 0 (r por célula e futuro não é gravado; vale pela fórmula e pelo erro do avaliador).

### Contagens (janela principal; a sensibilidade só difere em climate-fragile do solar: 559)

| | solar | eólico |
|---|---:|---:|
| candidatas | 93.701 | 75.535 |
| conjunto F7 | 93.490 | 75.535 |
| ranqueadas | 93.159 | 75.535 |
| climate-fragile | 331 | 0 |
| climate-data-invalid | 84 | 0 |
| incomplete-ensemble | 0 | 0 |
| infeasible_at_f0 | 127 | 0 |
| top_k (10 %) | 9.349 | 7.554 |
| top_k_truncated | falso | falso |
| `target_unreachable` | falso | falso |

As 84 células climate-data-invalid do solar são as sem LCOE no F6 (L-253).

### Hipóteses (janela principal, variante primária; sem interpretar)

| Hipótese | solar | eólico |
|---|---|---|
| H1a (core_share >= 0,6) | 0,9024 met | 0,8900 met |
| H1b (vulnerable_share >= 0,2) | 0,0000 not_met | 0,0000 not_met |
| H1 | partially_supported | partially_supported |
| H2 (overlap < 0,3) | 0,5027 not_met | 0,3391 not_met |
| H3 (beyond_reach >= 0,2) | 0,000037 not_met | 0,0000 not_met |
| H4 (parcela climática da variância; perfil) | 0,896; climate_dominated | 0,9995; no_displacement |
| H5, alvo | 447 GW, 2035: E_0 771,67 TWh, G 759,38, folga +12,29 TWh | 138 GW, 2035: E_0 36,94 TWh, G 375,48, folga -338,54 TWh |
| H5a (perda de recurso >= 0,2) | 3,8156, **met** (perda de energia 46,90 TWh) | status `target_not_met_at_reference`, sem veredito (E_0 não excede G) |
| H5b (R_exp) | not available (V174b; nenhum canal tem limiar, OQ-051) | not available |
| T-R10 | `hazard_exposure` com 0 linhas: not available | idem |
| PRIM | no_cases (0 de 72.000 futuros) | no_cases (0 de 60.000) |

Observação sobre o item 4 do comando ("H5 testável nos dois pares"): o solar é testável e dá H5a met; o eólico tem alvo (375,48 TWh) mas o recurso abaixo de τ no cenário de referência não o atinge, e o código o classifica como `target_not_met_at_reference`, sem veredito.

Capacidade abaixo de τ no m0: solar 454,57 GW (restritivo 133,10; permissivo 2.474,08); eólico 13,58 GW (4,88; 45,00).

## Item 2. Estimativa do BRA (robustness_analysis, e o lcoe_modeling a 4.000 amostras)

### Base declarada
Medidas: PRT (183) e IND (este). Tamanho: o F7 trabalha por célula do conjunto F7 (PRT 3.414 solar e 3.332 eólico; IND 93.490 e 75.535; BRA 190.001 solar e 178.289 eólico, das tabelas do F6 do BRA). Membros e amostras iguais (4.000).

### Tempo
Taxa por célula candidata (solar + eólico): PRT 455,9 s / 6.746 = 0,0676 s; IND 9.268,8 s / 169.025 = 0,0548 s. BRA: 368.290 células. Estimativa: 20.200 s (5,6 h) com a taxa da IND a 24.900 s (6,9 h) com a do PRT. Linear em células; não há motivo para superlinearidade nos dois pontos (de PRT para IND a taxa caiu).

lcoe_modeling do BRA a 4.000 amostras: IND 1.367,8 s para 5.805.414 pares célula-membro, BRA 12.576.236 pares (180): ~2.960 s (49 min); pico da IND 1.128 MB, a do BRA ~1.500 a 1.600 MB (a base cresce com as células; a 500 amostras o BRA deu 1.578 MB).

Total estimado do BRA (F6 refeito + F7): ~6,4 a 7,7 h; recomendo `scripts/run_unattended.ps1` no 185.

### Memória e a regra do V185 (item 2 do 180)
Pico medido: PRT 711 MB (maior tecnologia 3.414 células), IND 1.908 MB (93.490). Extrapolação pela maior tecnologia (BRA 190.001): 13,3 KB por célula -> 711 + 13,3 x 187 mil = ~3.200 MB; pela soma das tecnologias: ~3.380 MB. Estimativa do pico do BRA: **3,2 a 3,4 GB**, contra teto de 1.536 MB (limite rígido 1.920 MB).

Pela regra: 3.200 > 1,25 x 1.536 = 1.920, então o teto seria ceil(1,25 x 3.200) = 4.000 MB; limite físico: 5,92 - 4 = 1.966 MB; não cabe. A regra manda reduzir `memory.max_batch_gb` (hoje 0,5), até 4 vezes. Ressalva: não sei quanto do pico do F7 depende do bloco; no F6 o bloco não dominava (o pico do BRA mal caiu com 0,5 GB, 1.575 -> 1.578 MB). Se o pico do F7 for dominado por tabelas por célula e não pelo bloco, nenhuma redução cabe e o BRA não roda dentro de 1.966 MB nesta máquina (5,92 GB); isso é decisão do 185. A IND, a 1.908 MB, ficou a 12 MB do limite rígido: está no limite do que esta máquina e a regra suportam.

## Estado
Critério de conclusão: `robustness_analysis` success na IND; digests iguais; V-03 sem violação; tabelas da M-F7-11 presentes. Nenhum arquivo do repositório alterado neste comando (git limpo).
