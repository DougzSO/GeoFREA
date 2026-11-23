# Produção do PRT, F6 (COMANDO 179)

Escrito para: o autor, para decidir o item 4 e seguir para o 180.

Data: 2026-11-18. Repositório em `c934d71` (origin/main), tag `prereg-v1` em `ccf764f`, digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneo: `GeoFREA_data/_snapshots/20261118_pre179` (manifestos de PRT, IND e BRA, com `SHA256SUMS.txt`).

## Item 2. A rodada

Comando: `python main.py PRT --phases lcoe_modeling,sample_size_convergence --real-run --production`. O `--plan` anterior mostrou só as duas fases a executar (as oito de F1 a F5 retomadas do manifesto). `--production` não recusou nenhum parâmetro. run_id `7316fcfeb35df6983e2b38a069e49c9a9d961cb0e4d91032042a5cbf6a4dbcb9`.

| Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) | acima do teto |
|---|---|---:|---:|---:|---:|---|
| lcoe_modeling | success | 41,1 | 18,5 | 330 | 1.536 | não |
| sample_size_convergence | success | 75,3 | 69,9 | 606 | 1.536 | não |

Pré-registro: `digest_live` = `digest_tag` = `50b617071b83f60a5a3ee9e722cd1bd2fc4cb3126b05ca0cd3cdeda21bf4df99`.

## Item 3. Sanidade do F6

| | solar | eólico |
|---|---:|---:|
| células candidatas (cenário central) | 3.415 | 3.332 |
| células com LCOE | 3.414 | 3.332 |
| membros | 37 | 31 |
| pares célula-membro | 126.318 | 103.292 |
| pares excluídos (distância ou zona ausente) | 37 (1 célula x 37 membros) | 0 |
| candidatas com distância ausente / zona PV ausente | 0 / 0 | 0 / n/a |
| fração da capacidade além do limite de 100 km | 0,0 % | 0,0 % |
| candidatas com `dist_grid_km` acima de 100 km | 0 | 0 |
| valores não finitos (nominal, sorteios, soma de `n_nonfinite`) | 0, 0, 0 | 0, 0, 0 |
| LCOE nominal p5 / p50 / p95 (USD/MWh, sobre os pares) | 45,06 / 48,82 / 52,71 | 45,94 / 65,46 / 111,28 |
| mínimo / máximo | 42,04 / 60,65 | 31,83 / 246,34 |
| τ primário (USD/MWh) | 54,53 | 49,64 |
| pares com LCOE nominal <= τ | 98,99 % | 10,43 % |
| capacidade com LCOE nominal <= τ (média sobre membros) | 99,86 % de 153,27 GW | 6,96 % de 22,79 GW |
| `road_cost_excluded` na proveniência | true | true |

A proveniência de cada tabela (chave `geofrea_lcoe_provenance` nos metadados do parquet) registra `road_cost_excluded` = true, `production` = true e o aviso "the access road is not billed (no sourced road cost): the LCOE is a lower bound; sensitivity road_cost_high". Em ambos os casos o LCOE é um limite inferior.

A exclusão de 37 pares do solar é uma célula candidata que não entra na tabela de LCOE em nenhum dos 37 membros. Nenhuma candidata tem distância ou zona ausente na tabela de candidatas; o motivo exato dessa célula não está registrado separadamente no código ("distância ou zona ausente" é um contador único em `pipeline.py`).

## Item 4. Consistência do kernel: atendida com tolerância de arredondamento (decisão do autor)

Executei o kernel (`lcoe_block`, pelas funções de `scripts/calibrate_tau_irena.py`) na célula de referência do PRT, com a taxa central do par:

| Tecnologia | LCOE do kernel | τ em parameters.json | diferença |
|---|---:|---:|---:|
| solar | 54,5319471509263 | 54,53 | 1,95e-03 |
| eólico | 49,642507066595506 | 49,64 | 2,51e-03 |

O kernel reproduz o τ arredondado em duas casas (54,53 e 49,64), mas não com tolerância de 1e-6: o τ gravado em `config/parameters.json` tem duas casas decimais e a diferença de arredondamento é de até 0,005. A tolerância de 1e-6 não pode ser atendida contra um valor gravado com duas casas.

Decisão do autor (2026-11-18): aceitar a tolerância de arredondamento, isto é, comparar o kernel com o τ gravado em duas casas com tolerância de 0,005. Os dois casos passam (1,95e-03 e 2,51e-03, abaixo de 0,005; e o arredondamento a duas casas dá 54,53 e 49,64 exatamente). O τ não foi regravado; nenhuma configuração mudou.

## Item 5. Convergência (U-04)

top-k de 10 % (342 de 3.414 células no solar; 334 de 3.332 no eólico); tolerância 0,01 de 1 - Jaccard entre tamanhos consecutivos (amostras independentes, L-239).

| Tecnologia | tamanho | 1 - Jaccard com o anterior | atende | tempo (s) |
|---|---:|---:|---|---:|
| solar | 500 | n/a | n/a | 4,9 |
| solar | 1.000 | 0,0116 | não | 7,9 |
| solar | 2.000 | 0,0231 | não | 17,7 |
| solar | 4.000 | 0,0116 | não | 31,9 |
| eólico | 500 | n/a | n/a | 5,8 |
| eólico | 1.000 | 0,0000 | sim | 6,9 |

- **Eólico:** a regra da U-04 dá 1.000 (adotado).
- **Solar:** não convergiu até o teto de 4.000 (os três pares ficam em 0,0116, 0,0231 e 0,0116, todos acima de 0,01). Pelo V182 o tamanho a adotar é o maior testado (4.000), com a L nova "U-04 not met for solar; adopted the largest tested size, 4000; 1 - Jaccard at that size 0.0116" (registro previsto no V182; não gravado neste comando, que não altera código nem documentos).

Os tempos por tamanho vêm dos horários do log da rodada (`/tmp/r179_PRT.txt`), não do manifesto.
