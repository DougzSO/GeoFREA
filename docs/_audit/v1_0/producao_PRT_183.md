# Produção do PRT, robustness_analysis (COMANDO 183)

Escrito para: o autor, para conferir as invariantes e as contagens do primeiro F7 de produção antes de ler resultado.

Data: 2026-11-18. HEAD `86fabd8`, com alterações locais sem commit (ver abaixo). Tag `prereg-v1` em `ccf764f`; digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235` (idêntico). Instantâneo: `GeoFREA_data/_snapshots/20261118_pre183`.

## Item 1. A rodada
`python main.py PRT --phases lcoe_modeling,robustness_analysis --real-run --production`. O `--plan` mostrou `lcoe_modeling` stale (182) e `robustness_analysis` sem entrada.

Primeira rodada: `lcoe_modeling` success (90 s, pico 598 MB, F6 a 4.000 amostras); `robustness_analysis` **failed** (118 s, pico 826 MB), `ThesisTableError: central: F5 rows without an F6 nominal LCOE`. Causa: a célula solar 7426615 (0,9 MW, `pvcz_zone` 0, distâncias válidas) tem linhas no F5 mas o F6 a deixa de fora (zona ou distância ausente); o F7 exigia uma correspondência 1 para 1. O autor escolheu a opção 1: o F7 deixa de fora a célula sem LCOE em qualquer membro e conta em aviso (L-253); célula com LCOE em alguns membros e sem em outros continua erro. Alteração em `thesis_tables.py` (`merge_nominal_lcoe`) e em `tests/unit/test_robustness_futures.py` (o teste de recusa passou a cobrir o caso parcial; novo teste da célula totalmente ausente), L-253 em `docs/LIMITATIONS.md`. Sem commit.

Segunda rodada (o `lcoe_modeling` foi retomado do manifesto):

| Fase | Estado | wall_s | cpu_s | pico (MB) | teto (MB) | acima do teto |
|---|---|---:|---:|---:|---:|---|
| lcoe_modeling | success | 90,0 | 57,5 | 598 | 1.536 | não |
| robustness_analysis | success | 455,9 | 391,7 | 711 | 1.536 | não |

Pré-registro: `digest_live` = `digest_tag` = `50b617071b83f60a5a3ee9e722cd1bd2fc4cb3126b05ca0cd3cdeda21bf4df99`. 80 tabelas parquet + o JSON (4 tabelas por tecnologia e janela x 20). n_samples 4.000, semente 42, `provisional` falso.

Avisos do log: células sem LCOE do F6 deixadas de fora: central 1 célula (37 linhas), permissivo 3 células (111 linhas). Itens ignorados: meta de capacidade (OQ-010) e exposição aos 5 canais (OQ-051).

## Item 2. Invariantes V-03 (solar e eólico, janela principal 2041-2070 e sensibilidade 2071-2100)
Todas atendidas, sem violação, nas quatro combinações:
- MR >= 0 e finito nas ranqueadas (solar principal: mín 0 e máx 0,4524; sensibilidade 0 a 0,4479; eólico principal 0,0362 a 6,102; sensibilidade 0,0400 a 6,306).
- 0 <= SR <= 1 (solar 0,315 a 0,854; eólico 0 a 0,996).
- Ranqueadas + climate-fragile = conjunto F7; linhas ranqueadas = contagem da classe.
- Nenhuma ranqueada com MR infinito; mr_clim e mr_tech >= 0.
- Ao menos uma célula viável com r = 0 por futuro: o regret é r = LCOE/L* - 1, com L* o menor LCOE viável do futuro (M-F7-02), então o argmin tem r = 0 por construção; verifiquei `lowest_lcoe` finito e positivo em todos os futuros (72.018 no solar, 60.015 no eólico: membros x (4.000 + nominal)); o avaliador falha se um futuro não tem célula viável.
- r >= 0 por célula e futuro não é gravado em tabela; vale pela fórmula acima e por MR >= 0 (MR é o máximo do P90 de r).

## Item 3. Contagens (iguais nas duas janelas)

| | solar | eólico |
|---|---:|---:|
| candidatas | 3.415 | 3.332 |
| conjunto F7 | 3.414 | 3.332 |
| ranqueadas | 3.414 | 3.332 |
| climate-fragile | 0 | 0 |
| climate-data-invalid | 1 | 0 |
| incomplete-ensemble | 0 | 0 |
| infeasible_at_f0 | 0 | 0 |
| top_k (10 %) | 342 | 334 |
| top_k_truncated | falso | falso |
| membros do conjunto | 18 | 15 |

k de cada top_k (variantes de H1): solar 171 (5 %), 342 (10 %), 683 (20 %); eólico 167, 334, 667. A célula climate-data-invalid do solar é a mesma sem LCOE do F6 (L-253).

## Item 4. M-F7-11, hipóteses (janela principal, variante primária), sem interpretar

As 20 tabelas por tecnologia e janela estão presentes (`robustness`, `ssp_scores`, `h1_sites`, `h1_summary`, `h2_regions`, `h2_summary`, `h3_sites`, `h3_summary`, `h4_country`, `h5_members`, `h5_summary`, `hypothesis`, `hazard_exposure`, `potential_below_tau`, `nominal_lcoe_by_member`, `draw_statistics`, `futures`, `prim_box`, `prim_boxes`, `prim_bootstrap`).

| Hipótese | estatística (limiar) | solar | eólico |
|---|---|---|---|
| H1a | h1a_core_share >= 0,6 | 0,9737, met | 0,9611, met |
| H1b | h1b_vulnerable_share >= 0,2 | 0,0000, not_met | 0,0000, not_met |
| H1 (veredito) | | partially_supported | partially_supported |
| H1 referência | h1_core_share_reference | 0,0100 | 0,0100 |
| H2 | h2_overlap_index < 0,3 (testável se referência < 0,3) | 0,3197, not_met | 0,4451, not_met |
| H3 | h3_beyond_reach_share >= 0,2 (testável se referência >= 0,2) | 0,0092, not_met | 0,0000, not_met |
| H4 | h4_variance_share_climate (sem regra pré-registrada, OQ-050) | 0,053; perfil no_displacement (D_clim 0, D_tec 0) | 0,836 |
| H5 | primária (h5a, h5b) | not testable: no national target (OQ-010) | not testable (OQ-010) |
| H5 (descritivo) | potencial abaixo de τ no m0 | 152,25 GW | 2,03 GW |
| H5b (R_exp) e T-R10 | | not available na v1.0 (V174b): `hazard_exposure` com 0 linhas | idem |
| PRIM | status | no_cases (0 de 72.000 futuros de interesse) | no_cases (0 de 60.000) |

PRIM sem caixa escolhida em nenhuma tecnologia (`no_cases`). RQ4 (tau-b de Kendall MR x SR) 0,857 solar e 0,949 eólico. As tabelas H1 por variante (sem o IPSL-CM6A-LR, top-k 5/10/20 %, tolerância 0,5k/1k/2k) estão presentes; todas `partially_supported`.

## Estado
Condição de conclusão: `robustness_analysis` success; digests iguais; V-03 sem violação; tabelas da M-F7-11 presentes. Pendências: commit das alterações do F7 (código, teste, L-253) e a prova P (`lcoe_modeling` e `sample_size_convergence` de IND e BRA seguem stale do 182; `robustness_analysis` novo no PRT). Nada interpretado, nada mais alterado.
