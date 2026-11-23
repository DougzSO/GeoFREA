# Produção do BRA, F7 (COMANDO 185)

Escrito para: o autor, para decidir o teto de memória da F7 e seguir para o 186.

Data: 2026-11-19. Repositório em `3fcdfbe` (sem alteração), tag `prereg-v1` intacta, digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneo: `GeoFREA_data/_snapshots/20261119_pre185`.

## Rodadas

| Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) |
|---|---|---:|---:|---:|---|
| lcoe_modeling (4000 amostras) | success | 3.130 | n/d | 1.566 | 1.536 (acima 29,5 MB, dentro do limite 1.920) |
| robustness_analysis | success | 30.626 (8,5 h) | 31.443 | 3.174 | desligado (`GEOFREA_MEMORY_CAPS=0`) |

Pré-registro: `digest_live` = `digest_tag` (BRA).

## Memória (item 1b e item 2)

- Estimativa antes da rodada: ~3,2 GB. Medido no manifesto: 3.174 MB (o watchdog externo, que amostra a cada 30 s, viu 2.575 MB). Estimativa próxima do medido.
- Regra V185: pico > 1,25 x 1.536 = 1.920 MB, então a regra manda teto = ceil(1,25 x 3.174) em múltiplo de 64 = **3.968 MB**, limitado a memória física - 4 GB (6,36 - 4 = ~2,3 GB). O limite físico fica abaixo do próprio pico medido; a regra não fecha na máquina. Autorizada por você a flexibilização do teto, mas **não gravei o teto**: falta sua decisão (abaixo).
- Redução de `memory.max_batch_gb` (alternativa da regra) não aplicada: a F7 já respeita o lote; o resto do pico vem de estruturas por célula fora do orçamento (perfil do PRT).
- A rodada com tetos desligados terminou sem estourar a máquina (disponível 0,45 a 2,3 GB; o Windows reduziu o working set sob pressão).

## Itens do 183 para o BRA (`report183.py BRA`)

- `robustness_analysis` success; sem violações do V-03 (`FAILURES: []`) em todas as 6 combinações (solar/eólico x principal/sensibilidade, mais os conjuntos de conjunto comum do eólico).
- Células: solar 190.001 de 190.521 (520 `climate_data_invalid`, L-253); eólico 171.181 de 178.289 (core: 4 inválidas, 7.104 `incomplete_ensemble`; sensibilidade: 7.108 inválidas). Futuros: solar 72.018 (18 membros), eólico 60.015 (15 membros); comuns 52.013 e 44.011.
- Tabelas M-F7-11 presentes; H5/T-R10 de exposição a hazards não disponível (OQ-051, linhas = 0), 5 saídas puladas por isso. `hazard_context` rodou.
- H1: solar c_k 0,853 (met), v_k 0,0029 (not_met); eólico 0,963 / 0,0; veredicto `partially_supported` nos dois. H2 overlap: 0,340 solar, 0,510 eólico (not_met). H3: not_met. H4: sem regra (OQ-050); eólico `not_testable` por falta de meta nacional (OQ-010). H5 solar: meta de 90 GW em 2050 não atingida no ponto de referência: E_0 22,30 TWh/ano não excede G 162,58 TWh/ano (`target_not_met_at_reference`).
- Eólico: `target_unreachable` n/a (sem meta).

## Pendente

1. Decisão sobre o teto de `robustness_analysis`: (a) gravar 3.968 MB em `phase_caps` (fórmula) com D-F6 e ajustar `test_the_phases_of_f6_to_f8_have_no_cap_of_their_own`, aceitando que excede memória física - 4 GB; (b) manter o padrão e rodar o BRA F7 só com tetos desligados; (c) reduzir `max_batch_gb` e rerrodar (custa nova rodada de 8,5 h e invalida PRT/IND).
2. Commit do item acima: o 185 não manda commitar.
3. Prova P: diferenças esperadas restantes são `sample_size_convergence` de PRT/IND/BRA (não rerrodadas a 4000).
