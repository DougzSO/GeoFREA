# Produção da IND, F6, e estimativa do BRA (COMANDO 180)

Escrito para: o autor, para conferir a IND e a estimativa de custo e memória do BRA antes do 181.

Data: 2026-11-18. Repositório em `c934d71` (sem alteração de código ou configuração neste comando), tag `prereg-v1` em `ccf764f`, digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneo: `GeoFREA_data/_snapshots/20261118_pre180`.

## Itens 1 a 6 do 179, com a IND

Comando: `python main.py IND --phases lcoe_modeling,sample_size_convergence --real-run --production`. O `--plan` anterior mostrou só as duas fases a executar. `--production` não recusou nenhum parâmetro.

| Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) | acima do teto |
|---|---|---:|---:|---:|---:|---|
| lcoe_modeling | success | 348,6 | 265,2 | 1.330 | 1.536 | não |
| sample_size_convergence | success | 484,4 | 504,7 | 1.231 | 1.536 | não |

Pré-registro: `digest_live` = `digest_tag` = `51381bfcd1c1a6a1d1ea43fa7a86dc82ad1b37425c32d6b2900008611533fac6`.

### Sanidade do F6

| | solar | eólico |
|---|---:|---:|
| células candidatas (cenário central) | 93.701 | 75.535 |
| células com LCOE | 93.617 | 75.535 |
| pares célula-membro (37 e 31 membros) | 3.463.829 | 2.341.585 |
| pares excluídos (distância ou zona ausente) | 3.108 (84 células x 37 membros) | 0 |
| candidatas com distância ausente / zona PV ausente | 0 / 0 | 0 / n/a |
| fração da capacidade além do limite de 100 km | 1,06 % | 0,09 % |
| candidatas com `dist_grid_km` acima de 100 km | 13.237 | 4.571 |
| valores não finitos (nominal, sorteios, soma de `n_nonfinite`) | 0, 0, 0 | 0, 0, 0 |
| LCOE nominal p5 / p50 / p95 (USD/MWh, sobre os pares) | 26,37 / 29,45 / 34,92 | 37,47 / 71,34 / 193,69 |
| mínimo / máximo | 20,78 / 73,88 | 17,19 / 84.805,39 |
| τ primário (USD/MWh) | 28,26 | 36,43 |
| pares com LCOE nominal <= τ | 27,10 % | 4,08 % |
| capacidade com LCOE nominal <= τ (média sobre membros) | 47,17 % de 804,56 GW | 7,21 % de 214,06 GW |
| `road_cost_excluded` na proveniência | true | true |

A proveniência registra `road_cost_excluded` = true e `production` = true; o LCOE é um limite inferior (sem custo de acesso rodoviário; sensibilidade `road_cost_high`). O máximo eólico de 84.805 USD/MWh é de uma célula de fator de capacidade muito baixo (cauda do LCOE por MWh), não é valor não finito; o p95 é 193,69.

### Consistência do kernel (tolerância de arredondamento, 0,005, decisão do autor no 179)

| Tecnologia | LCOE do kernel | τ em parameters.json | diferença | a 2 casas |
|---|---:|---:|---:|---:|
| solar | 28,25741 | 28,26 | 2,59e-03 | 28,26 |
| eólico | 36,43489 | 36,43 | 4,89e-03 | 36,43 |

Ambos dentro de 0,005 e iguais ao τ gravado a duas casas (a diferença eólica, 4,89e-03, é a mais próxima do limite).

### Convergência (U-04)

top-k de 10 %; tolerância 0,01.

| Tecnologia | tamanho | 1 - Jaccard com o anterior | atende | tempo (s) |
|---|---:|---:|---|---:|
| solar | 500 | n/a | n/a | 115,5 |
| solar | 1.000 | 0,0051 | sim | 183 |
| eólico | 500 | n/a | n/a | 72 |
| eólico | 1.000 | 0,0000 | sim | 113 |

Os dois pares convergem em 1.000 (tamanho adotado). Tempos por tamanho pelos horários do log da rodada.

## Item 2. Estimativa do BRA (lcoe_modeling e sample_size_convergence)

### Base declarada

Medidas: PRT (comando 179) e IND (este). Tamanho do BRA, das tabelas de candidatas do próprio BRA em `outputs/BRA/land_eligibility`: solar 190.521 células, eólico 178.289 (PRT 3.415 e 3.332; IND 93.701 e 75.535). Membros: supus os mesmos da IND (37 solar, 31 eólico), porque o conjunto de GCMs e cenários é o mesmo; pares célula-membro do BRA: 7.049.277 + 5.526.959 = 12.576.236 (PRT 229.610; IND 5.805.414).

Tamanho de bloco: a F6 dimensiona o bloco de células para que quatro arrays célula x amostra fiquem abaixo de `memory.max_batch_gb` (= 1 GB, METHODOLOGY A-10). Com 500 amostras o bloco é de 62.375 células e ocupa cerca de 1.000 MB; a F7 (convergência) faz o mesmo. Por isso o pico não cresce em proporção às células: o bloco fica em 1 GB e o resto (base e tabelas acumuladas) cresce devagar. Medido: lcoe_modeling PRT 330 MB com bloco de 55 MB (base 275), IND 1.330 MB com bloco de 998 MB (base 332).

### lcoe_modeling

| | PRT (medido) | IND (medido) | BRA (estimado) |
|---|---:|---:|---:|
| pares célula-membro | 229.610 | 5.805.414 | 12.576.236 |
| wall_s | 41,1 | 348,6 | 722 (ajuste linear nos dois pontos: 28,4 s + 5,5e-5 s por par); 755 (proporcional à IND) |
| pico (MB) | 330 | 1.330 | ~1.400 (bloco de 998 MB + base de ~400 MB, base extrapolada nos dois pontos); proporcional aos pares daria 2.544 a 2.881 |

### sample_size_convergence

A fase gasta tempo por célula x amostra testada. Taxa medida: PRT 2,5 us por célula-amostra, IND 1,9 us.

| Cenário no BRA | célula-amostras | wall_s |
|---|---:|---:|
| os dois convergem em 1.000 (como na IND) | 553 milhões | 1.056 (taxa da IND) a 1.361 (taxa do PRT) |
| solar vai a 4.000 (como no PRT) e o eólico converge em 1.000 | 1.696 milhões | 3.240 (taxa da IND) a 4.170 (taxa do PRT) |

Pico: PRT 606 MB (bloco de 437 MB com 3.414 células x 4.000 amostras), IND 1.231 MB (bloco de 998 MB, base de 233 MB). Para o BRA, o bloco continua em ~1 GB e a base cresce com as células (de 169 MB com 3,4 mil células a 233 MB com 93 mil): ~1.300 MB.

### Contra o teto e a regra de memória (V179 a V181)

Teto das duas fases: 1.536 MB (padrão do arquivo, sem entrada em `phase_caps`). Limite da regra: 1,25 x 1.536 = 1.920 MB.

| Fase | pico estimado do BRA | passa de 1.920 MB? |
|---|---:|---|
| lcoe_modeling | ~1.400 MB | não |
| sample_size_convergence | ~1.300 MB | não |

A regra não foi aplicada: nenhuma entrada de `config/memory_budget.json`, nenhuma redução de `memory.max_batch_gb` e nenhum D-F6 de memória. A memória física da máquina é 5,92 GB, então o limite físico da regra seria 5,92 - 4 = 1,92 GB (1.966 MB).

Ressalva da estimativa: se o pico fosse proporcional aos pares célula-membro, sem considerar que o bloco tem tamanho fixo, o lcoe_modeling do BRA daria 2,5 a 2,9 GB e a regra mandaria reduzir `max_batch_gb`. A estimativa acima usa o bloco limitado, que é como a fase foi construída e que se confirma nos dois pontos medidos (base de 275 e 332 MB). O 181 mede o BRA de fato.

Duração estimada para as duas fases do BRA, somando lcoe_modeling e convergência: de cerca de 30 a 35 min (os dois convergem em 1.000) a cerca de 66 a 82 min (solar vai a 4.000).
