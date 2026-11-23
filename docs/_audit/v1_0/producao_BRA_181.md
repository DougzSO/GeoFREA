# Produção do BRA, F6 (COMANDO 181)

Escrito para: o autor, para conferir a produção do BRA, a mudança de `memory.max_batch_gb` e seguir para o 182.

Data: 2026-11-18. HEAD `c934d71`; tag `prereg-v1` em `ccf764f`; digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneos: `_snapshots/20261118_pre181` e `_pre181b`.

## Primeira rodada (parada por teto)
`python main.py BRA --phases lcoe_modeling,sample_size_convergence --real-run --production`

| Fase | Estado | wall_s | pico (MB) | teto (MB) |
|---|---|---:|---:|---:|
| lcoe_modeling | success | 695,2 | 1.575 | 1.536 (acima 39,1) |
| sample_size_convergence | failed | 677,2 | 1.948 | 1.536 (limite rígido 1.920) |

Parada de memória em `sample_size_convergence`: 1.945 MB acima de 1.920 MB. PARAR; o autor autorizou flexibilizar.

## Regra de memória (V179 a V181), D-F6 de memória
- Pico estimado 1.948 MB > 1,25 x 1.536 = 1.920. Teto pela regra: ceil(1,25 x 1.948) = 2.435 -> 2.496 MB (múltiplo de 64).
- Limite físico: 5,92 GB - 4 GB = 1.966 MB. 2.496 não cabe -> primeira redução: `memory.max_batch_gb` 1 -> 0,5 (`config/settings.yaml`). Teto em `config/memory_budget.json` não alterado (1.536).
- Nenhum fingerprint se moveu (a chave não está em nenhum escopo); o `--plan` mostrou PRT e IND como "resume". Para os três países terem a mesma proveniência (`cells_per_block`, `max_batch_gb`), reexecutei com `--rerun` `lcoe_modeling,sample_size_convergence` em PRT, IND e BRA. Os valores não dependem do bloco (amostras sorteadas uma vez por membro).
- Registro em `docs/phases/F6_lcoe_modeling.md` (D-F6) e commit de `settings.yaml`: pendentes, fora do escopo do 181 (sem commit). Atenção: `config/settings.yaml` está modificado e não commitado.

## Rodada final (max_batch_gb 0,5), regra 7
| País | Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) | acima do teto |
|---|---|---|---:|---:|---:|---:|---|
| PRT | lcoe_modeling | success | 29,5 | 15,2 | 330 | 1.536 | não |
| PRT | sample_size_convergence | success | 57,5 | 61,6 | 684 | 1.536 | não |
| IND | lcoe_modeling | success | 342,2 | 225,6 | 1.133 | 1.536 | não |
| IND | sample_size_convergence | success | 510,0 | 411,4 | 1.436 | 1.536 | não |
| BRA | lcoe_modeling | success | 753,2 | 523,0 | 1.578 | 1.536 | sim, 42,3 MB (abaixo do limite rígido 1.920; não parou) |
| BRA | sample_size_convergence | success | 1.036,7 | 958,9 | 1.455 | 1.536 | não |

digest_live = digest_tag: PRT 50b617071b83..., IND 51381bfcd1c1..., BRA b51ee7d55d940684b524166ac17bfcde4f2c5381dd6e65d0b97188bf514c2c48.

Observação: o pico do lcoe_modeling do BRA (1.578) quase não caiu com o bloco menor; domina a base (tabelas acumuladas), não o bloco. A convergência caiu de 1.948 para 1.455 MB.

## Itens 3 e 5 do 179, BRA
Item 3 (sanidade):

| | solar | eólico |
|---|---:|---:|
| candidatas (central) / com LCOE | 190.521 / 190.001 | 178.289 / 178.289 |
| pares célula-membro (37 e 31) | 7.030.037 | 5.518.828 |
| excluídos | 19.240 (520 células x 37) | 0 |
| distância / zona ausente | 0 / 0 | 0 / n/a |
| capacidade além de 100 km | 7,23 % | 4,88 % |
| candidatas com dist_grid_km > 100 km | 10.616 | 5.926 |
| não finitos | 0, 0, 0 | 0, 0, 0 |
| LCOE nominal p5/p50/p95 (USD/MWh) | 46,57 / 52,09 / 63,55 | 48,59 / 129,73 / 536,87 |
| mínimo / máximo | 40,61 / 135,34 | 22,83 / 10.326,21 |
| τ primário | 43,97 | 31,95 |
| pares com LCOE <= τ | 0,19 % | 0,19 % |
| capacidade com LCOE <= τ | 0,35 % de 16.457,9 GW | 0,25 % de 1.989,3 GW |
| `road_cost_excluded` | true | true |

LCOE é limite inferior (sem custo de estrada; sensibilidade `road_cost_high`).

Item 4 (kernel, tolerância 0,005): solar 43,97484 vs 43,97 (4,84e-03); eólico 31,94537 vs 31,95 (4,63e-03). Ambos passam e arredondam a 43,97 e 31,95.

Item 5 (convergência U-04, top-k 10 %, tolerância 0,01): solar 500 -> 1.000: 1 - Jaccard 0,000316, converge; eólico: 0,000336, converge. Tamanho adotado 1.000 nos dois.

## Conclusão
Ambas as fases em success no BRA; digests iguais; agregado idêntico. Pendências: registrar o D-F6 e commitar `settings.yaml` (comando próprio); a L de PRT solar (não convergiu até 4.000) fica para o 182.
