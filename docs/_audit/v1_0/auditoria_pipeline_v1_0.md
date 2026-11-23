# Auditoria final da pipeline v1.0 (COMANDO 191, reexecutada após o COMANDO 191A)

Escrito para: o autor, para levar ao chat de planejamento e conferir se o plano foi cumprido. Data: 2026-11-23. Repositório em `fa090bb` (commit do 191A). Todo número vem de um artefato, com o caminho de origem ao lado; nada é interpretado. Esta versão substitui a de 2026-11-22.

## 0. O que mudou desde a primeira versão e o que o autor precisa ver (regra 4)

**Achados da primeira versão, todos tratados no COMANDO 191A:**

| Achado | Estado | Como |
|---|---|---|
| A: `cross_country_h4` e T-R6, T-R7 com um país só (BRA) | resolvido | `main.h4_countries` compara todos os países configurados; `main.require_h4_inputs` recusa país sem `h4_country`; F8 recusa veredito que deixou um país de fora (D-core-056). `cross_country_h4` refeito em 0,1° e em 0,05° com PRT, IND e BRA; os `h4_verdict` das duas escalas trazem 3 perfis (`3 of 3 countries have a profile`). T-R6, T-R7, T-R8, os `h4_verdict` e os perfis concordam no H4 nas duas escalas (conferido por script, 0 incoerências). |
| B: seção 4 do arquivo de comandos incompleta | resolvido | linhas 177 a 191A preenchidas a partir do `git log` e dos relatórios |
| C: nenhuma DEC "post-result correction" | resolvido | DEC-097 (COMANDO 191B) reclassifica a DEC-095: o commit `3fcdfbe` é correção pré-resultado (nenhum resultado de `robustness_analysis` veio do código anterior); o `c7af733` remete ao D-F7b-009 (pré-resultado) |
| D: `PROGRESS.json` defasado | resolvido | F7b e F8 `ran_clean` nos três países |

**Ponto de atenção que a correção expôs (decisão do autor):** o veredito do H4 por tecnologia, que a primeira versão do `T-R8_hypothesis_summary.csv` mostrava como `not_testable`, é agora `not_supported` nas duas tecnologias e nas duas escalas (3 de 3 países com perfil, nenhum par estrito de Climate-Dominated e Techno-Economic-Dominated). O `not_testable` anterior era artefato do `cross_country_h4` com um país.

**DEC-095 reclassificada (COMANDO 191B, DEC-097):** o teste de data do 191A era um proxy. O critério é que nenhum resultado de `robustness_analysis` foi produzido pelo código anterior ao `3fcdfbe`: o primeiro success (23:20 UTC) já rodou o código corrigido, commitado às 23:46 UTC. A correção é pré-resultado. Nenhuma fase foi reexecutada.

**Regras tocadas nesta auditoria.** Regra 1: rodei `python main.py <ISO> --plan` (prova P) e `scripts/check_manifests.py`; nenhuma fase executou e nenhum manifesto foi escrito (SHA-256 igual ao início desta reexecução, item 9). Também `git fetch`, `scripts/lint_docs.py` e `scripts/preregistration_digest.py` (só leitura).

**Memória:** `results_synthesis` rodou com `GEOFREA_MEMORY_CAPS=0` nos três países (V179c, L-254); por isso `memory_cap_mb` aparece vazio nessas entradas. Picos: PRT 369, IND 1.521, BRA 2.434 MB; o teto de fase fixado é 3.520 MB.

## 1. Estado por país e fase

Origem: `outputs/<ISO>/manifest.json` (0,05°) e `manifest__0p1deg.json` (0,1°), campos `status`, `finished_at`, `wall_s`, `cpu_s`, `peak_rss_mb`, `memory_cap_mb`, `peak_over_cap`. O `memory_cap_mb` é o teto vigente na rodada que gravou a entrada (`-` = sem teto de fase, ou limites desligados com `GEOFREA_MEMORY_CAPS=0`). `finished_at` em UTC.

### Escala 0,05°

| País | Fase | status | finished_at | wall_s | cpu_s | peak_rss_mb | memory_cap_mb | peak_over_cap |
|---|---|---|---|---|---|---|---|---|
| PRT | data_acquisition | success | 2026-11-18T17:57:46 | 17 | 13 | 359 | 1024 | - |
| PRT | data_quality_audit | success | 2026-11-05T19:09:15 | 23 | 19 | 535 | - | - |
| PRT | grid_alignment | success | 2026-11-18T17:57:50 | 4 | 1 | 298 | 576 | - |
| PRT | climate_forcing | success | 2026-11-18T17:59:46 | 116 | 109 | 308 | 768 | - |
| PRT | climate_maps | success | 2026-11-18T18:00:15 | 29 | 26 | 677 | 2944 | - |
| PRT | hazard_context | success | 2026-11-18T18:00:51 | 35 | 32 | 1046 | 3520 | - |
| PRT | siting_layers | success | 2026-11-09T22:37:24 | 40 | 1 | 274 | - | - |
| PRT | external_inputs | success | 2026-11-06T21:50:33 | 0 | 0 | 250 | - | - |
| PRT | overview | success | 2026-11-12T16:15:06 | 15 | 14 | 888 | 2560 | - |
| PRT | land_eligibility | success | 2026-11-18T18:01:08 | 17 | 11 | 712 | 1856 | - |
| PRT | technical_potential | success | 2026-11-18T18:01:15 | 7 | 5 | 729 | 1984 | - |
| PRT | potential_maps | success | 2026-11-18T18:01:24 | 9 | 8 | 760 | 2112 | - |
| PRT | lcoe_modeling | success | 2026-11-18T23:05:57 | 90 | 58 | 598 | 1536 | - |
| PRT | sample_size_convergence | success | 2026-11-18T21:09:13 | 58 | 62 | 684 | 1536 | - |
| PRT | robustness_analysis | success | 2026-11-18T23:20:10 | 456 | 392 | 711 | 1536 | - |
| PRT | external_validation | success | 2026-11-22T15:22:24 | 3 | 1 | 340 | 3520 | - |
| PRT | lcoe_maps | success | 2026-11-20T15:10:39 | 8 | 7 | 643 | - | - |
| PRT | robustness_maps | success | 2026-11-20T15:11:03 | 22 | 20 | 955 | - | - |
| PRT | results_synthesis | success | 2026-11-23T03:30:48 | 26 | 17 | 369 | - | - |
| IND | data_acquisition | success | 2026-11-18T18:12:27 | 617 | 555 | 1000 | 1024 | - |
| IND | data_quality_audit | success | 2026-11-06T12:15:17 | 142 | 122 | 1186 | - | - |
| IND | grid_alignment | success | 2026-11-18T18:13:09 | 42 | 7 | 393 | 576 | - |
| IND | climate_forcing | success | 2026-11-18T18:14:57 | 109 | 102 | 547 | 768 | - |
| IND | climate_maps | success | 2026-11-18T18:16:07 | 70 | 68 | 1399 | 2944 | - |
| IND | hazard_context | success | 2026-11-18T18:17:37 | 89 | 84 | 1573 | 3520 | - |
| IND | siting_layers | success | 2026-11-09T22:48:45 | 62 | 2 | 275 | - | - |
| IND | external_inputs | success | 2026-11-06T22:09:49 | 0 | 0 | 311 | - | - |
| IND | overview | success | 2026-11-12T16:38:14 | 37 | 30 | 1357 | 2560 | - |
| IND | land_eligibility | success | 2026-11-18T18:20:52 | 193 | 174 | 898 | 1856 | - |
| IND | technical_potential | success | 2026-11-18T18:22:09 | 76 | 64 | 1088 | 1984 | - |
| IND | potential_maps | success | 2026-11-18T18:22:35 | 26 | 23 | 1604 | 2112 | - |
| IND | lcoe_modeling | success | 2026-11-19T00:16:14 | 1368 | 1492 | 1128 | 1536 | - |
| IND | sample_size_convergence | success | 2026-11-18T21:23:53 | 510 | 411 | 1436 | 1536 | - |
| IND | robustness_analysis | success | 2026-11-19T02:50:44 | 9269 | 9629 | 1908 | 1536 | 372.0 |
| IND | external_validation | success | 2026-11-22T15:23:11 | 29 | 27 | 1642 | 3520 | - |
| IND | lcoe_maps | success | 2026-11-20T15:14:18 | 35 | 31 | 1739 | - | - |
| IND | robustness_maps | success | 2026-11-20T15:14:57 | 35 | 32 | 2186 | - | - |
| IND | results_synthesis | success | 2026-11-23T03:32:08 | 40 | 33 | 1521 | - | - |
| BRA | data_acquisition | success | 2026-11-18T18:26:30 | 188 | 164 | 844 | 1024 | - |
| BRA | data_quality_audit | success | 2026-11-06T11:33:09 | 160 | 78 | 1152 | - | - |
| BRA | grid_alignment | success | 2026-11-18T18:26:45 | 15 | 8 | 515 | 576 | - |
| BRA | climate_forcing | success | 2026-11-18T18:29:25 | 160 | 131 | 884 | 768 | 115.6 |
| BRA | climate_maps | success | 2026-11-18T18:31:00 | 94 | 82 | 2011 | 2944 | - |
| BRA | hazard_context | success | 2026-11-18T18:34:00 | 180 | 152 | 1426 | 3520 | - |
| BRA | siting_layers | success | 2026-11-09T23:35:05 | 98 | 4 | 272 | - | - |
| BRA | external_inputs | success | 2026-11-06T23:12:46 | 0 | 0 | 303 | - | - |
| BRA | overview | success | 2026-11-12T17:07:16 | 50 | 34 | 1186 | 2560 | - |
| BRA | land_eligibility | success | 2026-11-18T18:46:51 | 766 | 598 | 920 | 1856 | - |
| BRA | technical_potential | success | 2026-11-18T18:50:41 | 230 | 178 | 2074 | 1984 | 90.0 |
| BRA | potential_maps | success | 2026-11-18T18:51:37 | 54 | 46 | 1230 | 2112 | - |
| BRA | lcoe_modeling | success | 2026-11-19T11:04:40 | 3130 | 3333 | 1566 | 1536 | 29.5 |
| BRA | sample_size_convergence | success | 2026-11-18T21:54:38 | 1037 | 959 | 1455 | 1536 | - |
| BRA | robustness_analysis | success | 2026-11-19T19:36:24 | 30625 | 31443 | 3174 | - | - |
| BRA | external_validation | success | 2026-11-22T15:25:03 | 73 | 59 | 3093 | 3520 | - |
| BRA | lcoe_maps | success | 2026-11-20T15:21:12 | 32 | 26 | 2387 | - | - |
| BRA | robustness_maps | success | 2026-11-20T15:21:48 | 30 | 26 | 2569 | - | - |
| BRA | results_synthesis | success | 2026-11-23T03:34:51 | 76 | 56 | 2434 | - | - |

### Escala 0,1°

| País | Fase | status | finished_at | wall_s | cpu_s | peak_rss_mb | memory_cap_mb | peak_over_cap |
|---|---|---|---|---|---|---|---|---|
| PRT | data_acquisition | success | 2026-11-22T16:41:29 | 11 | 7 | 324 | 1024 | - |
| PRT | data_quality_audit | success | 2026-11-22T16:41:54 | 25 | 18 | 549 | 1472 | - |
| PRT | external_inputs | success | 2026-11-22T16:41:55 | 1 | 0 | 293 | 384 | - |
| PRT | grid_alignment | success | 2026-11-22T16:41:59 | 4 | 2 | 307 | 576 | - |
| PRT | climate_forcing | success | 2026-11-22T16:43:35 | 96 | 89 | 308 | 768 | - |
| PRT | hazard_context | success | 2026-11-22T16:44:05 | 30 | 28 | 706 | 3520 | - |
| PRT | siting_layers | success | 2026-11-22T16:44:44 | 39 | 1 | 314 | 1152 | - |
| PRT | land_eligibility | success | 2026-11-22T16:45:02 | 19 | 11 | 378 | 1856 | - |
| PRT | technical_potential | success | 2026-11-22T16:45:08 | 6 | 4 | 344 | 1984 | - |
| PRT | lcoe_modeling | success | 2026-11-22T16:45:41 | 33 | 22 | 425 | 1984 | - |
| PRT | robustness_analysis | success | 2026-11-22T16:47:53 | 132 | 122 | 825 | 3968 | - |
| PRT | sample_size_convergence | success | 2026-11-22T16:48:07 | 14 | 16 | 505 | 1856 | - |
| IND | data_acquisition | success | 2026-11-22T16:50:55 | 139 | 133 | 1024 | 1024 | 0.3 |
| IND | data_quality_audit | success | 2026-11-22T16:53:04 | 129 | 116 | 1195 | 1472 | - |
| IND | external_inputs | success | 2026-11-22T16:53:07 | 2 | 0 | 352 | 384 | - |
| IND | grid_alignment | success | 2026-11-22T16:55:44 | 158 | 150 | 423 | 576 | - |
| IND | climate_forcing | success | 2026-11-22T16:57:28 | 104 | 94 | 517 | 768 | - |
| IND | hazard_context | success | 2026-11-22T16:58:49 | 81 | 74 | 1257 | 3520 | - |
| IND | siting_layers | success | 2026-11-22T16:59:54 | 64 | 2 | 339 | 1152 | - |
| IND | land_eligibility | success | 2026-11-22T17:05:38 | 344 | 298 | 787 | 1856 | - |
| IND | technical_potential | success | 2026-11-22T17:06:22 | 44 | 40 | 945 | 1984 | - |
| IND | lcoe_modeling | success | 2026-11-22T17:12:39 | 376 | 410 | 1243 | 1984 | - |
| IND | robustness_analysis | success | 2026-11-22T17:48:42 | 2163 | 2272 | 1161 | 3968 | - |
| IND | sample_size_convergence | success | 2026-11-22T17:50:32 | 110 | 136 | 1061 | 1856 | - |
| BRA | data_acquisition | success | 2026-11-22T17:53:27 | 138 | 130 | 834 | 1024 | - |
| BRA | data_quality_audit | success | 2026-11-22T17:55:58 | 151 | 80 | 1193 | 1472 | - |
| BRA | external_inputs | success | 2026-11-22T17:55:58 | 0 | 0 | 408 | 384 | 24.1 |
| BRA | grid_alignment | success | 2026-11-22T18:01:07 | 308 | 297 | 484 | 576 | - |
| BRA | climate_forcing | success | 2026-11-22T18:02:56 | 109 | 98 | 529 | 768 | - |
| BRA | hazard_context | success | 2026-11-22T18:05:23 | 147 | 121 | 1961 | 3520 | - |
| BRA | siting_layers | success | 2026-11-22T18:07:00 | 97 | 4 | 600 | 1152 | - |
| BRA | land_eligibility | success | 2026-11-22T18:21:08 | 848 | 753 | 1180 | 1856 | - |
| BRA | technical_potential | success | 2026-11-22T18:23:08 | 121 | 114 | 1425 | 1984 | - |
| BRA | lcoe_modeling | success | 2026-11-22T18:35:49 | 760 | 850 | 1263 | 1984 | - |
| BRA | robustness_analysis | success | 2026-11-22T20:19:42 | 6233 | 6653 | 1532 | 3968 | - |
| BRA | sample_size_convergence | success | 2026-11-22T20:23:31 | 228 | 281 | 1485 | 1856 | - |

### Fase de apoio `cross_country_h4`

| Manifesto | países registrados | artefatos | sha256 confere |
|---|---|---|---|
| `outputs/cross_country/manifest.json` (0,05°) | PRT, BRA, IND | 4 | sim |
| `outputs/cross_country/manifest__0p1deg.json` (0,1°) | PRT, BRA, IND | 4 | sim |

### Prova P

- `python main.py <ISO> --scale 0p05deg --real-run --plan --phases results_synthesis`: PRT, IND e BRA com 16 fases `resume` e 0 `execute` e 0 `stale_upstream` (`results_synthesis` retoma do manifesto).
- `python main.py <ISO> --scale 0p1deg --real-run --plan --phases technical_potential,lcoe_modeling,sample_size_convergence,robustness_analysis`: 12 fases `resume`, 0 `execute`, 0 stale nos três países.
- `GEOFREA_DATA_DIR=... python scripts/check_manifests.py PRT IND BRA`: PRT 254 artefatos, IND 256, BRA 294, todos `VALID` (existem e o hash de conteúdo confere). Nos manifestos `0p1deg` e `cross_country` conferi o SHA-256 dos bytes de todos os artefatos: nenhuma divergência: 191 (PRT), 193 (IND), 231 (BRA), 4 e 4 (`cross_country`).
- Manifestos de escala: `manifest__0p1deg.json` nos três países, 12 fases `success` cada (F1 a F2b, F3 a F7 e apoio), caminhos dos resumos em `artifacts__0p1deg/` (D-core-055).

## 2. Pré-registro

| Item | Valor | Origem |
|---|---|---|
| tag `prereg-v1` no remoto | objeto `685a29cc46e184ca148c233920f1c692d2218fe3`, commit `ccf764f1fb675f961d7c4d92ff0a66fb3d5fc326` (`git ls-remote --tags origin`) | remoto `origin` |
| digest agregado da tag (regra 5) | `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235`, igual ao esperado | `python scripts/preregistration_digest.py` |
| `digest_live` = `digest_tag` PRT, 0,05° e 0,1° | `50b617071b83f60a5a3ee9e722cd1bd2fc4cb3126b05ca0cd3cdeda21bf4df99` (os dois manifestos) | `outputs/PRT/manifest.json` e `manifest__0p1deg.json`, campo `preregistration` |
| `digest_live` = `digest_tag` IND, 0,05° e 0,1° | `51381bfcd1c1a6a1d1ea43fa7a86dc82ad1b37425c32d6b2900008611533fac6` (os dois manifestos) | `outputs/IND/manifest.json` e `manifest__0p1deg.json`, campo `preregistration` |
| `digest_live` = `digest_tag` BRA, 0,05° e 0,1° | `b51ee7d55d940684b524166ac17bfcde4f2c5381dd6e65d0b97188bf514c2c48` (os dois manifestos) | `outputs/BRA/manifest.json` e `manifest__0p1deg.json`, campo `preregistration` |

O manifesto guarda um único registro `preregistration` por país e escala (o último `digest_live` comparado antes de `lcoe_modeling`, `sample_size_convergence` ou `robustness_analysis`); a entrada de cada fase não carrega o campo. A guarda recusa a fase se os dois digests diferem (`core/preregistration.py`); as três fases dos seis manifestos estão `success`.

## 3. Repositório

| Verificação | Resultado | Origem |
|---|---|---|
| HEAD = origin/main | `fa090bbacdd68abb229337b3eef7cb17cfee827f` nos dois | `git rev-parse HEAD origin/main` (após `git fetch`) |
| workflows no HEAD | Regression, Unit tests and lint, Synthetic fixture (ZZZ): os três `success` | `gh run list --branch main` |
| `git status` | limpo (0 linhas) no início e no fim | `git status --short` |
| lint | `ruff check .`: All checks passed (última execução no COMANDO 190C); `scripts/lint_docs.py`: 0 failures | execução local |
| suíte local | última execução completa (COMANDO 191A, antes do commit): 2742 passed, 1 skipped, 1 failed; a falha era `test_no_module_branches_on_the_scale_by_name` (uma comparação de `scale_id` em `results_synthesis/output.py`), corrigida em seguida; depois dela rodaram `test_scale.py`, `test_cross_country.py` e `test_results_synthesis.py`: 29 passed. A suíte inteira não foi repetida depois dessa correção de uma linha; a evidência no HEAD é o CI (`Unit tests and lint` e `Synthetic fixture (ZZZ)`: success). | execução local e CI |

## 4. Saídas da tese (T-*)

Diretório: `D:\Douglas\DOUTORADO\GeoFREA_data\outputs	hesis\` (arquivos `T-<id>_<nome>[_<ISO>][_<tec>].{csv,tex,pdf,png,provenance.json}`). Hash: SHA-256 da concatenação dos SHA-256 dos arquivos da saída (tabelas, figuras e `provenance.json`, em ordem de nome), 12 primeiros dígitos. Origem da lista: `outputs/<ISO>/artifacts/results_synthesis.json`.

| T-* | hash PRT | hash IND | hash BRA | status |
|---|---|---|---|---|
| T-M1 | ea803f50bf11 | ea803f50bf11 | ea803f50bf11 | gerado |
| T-M2 | 750f6408e368 | 65770e85c615 | 9c8bb758773c | gerado |
| T-M3 | b11ef60f22a6 | e4b7b2e0ef8e | a9ff7267d9b3 | gerado |
| T-R1 | 0e9545f873f4 | 42a3e6573573 | c51fafc62d16 | gerado |
| T-R2 | 44b7375f4af7 | 0123b86e9954 | e87c89733b66 | gerado |
| T-R3 | 67cce054475a | 4ca46b158a18 | b3734cb53fa4 | gerado |
| T-R4 | 642f66215a3b | e23a33ad09dc | 6272bf4b03a3 | gerado |
| T-R5 | 6e902641b54f | 8de7a87de302 | 84818795bb18 | gerado |
| T-R6 | 2cd12781f069 | a4e081e3c647 | de538955c072 | gerado |
| T-R7 | f701fcba95df | f701fcba95df | f701fcba95df | gerado |
| T-R8 | 9aa5c42cc72b | 959e4ed4a7b3 | 06ad8ee1a471 | gerado |
| T-R9 | f3de875d12ca | af9b58210246 | bfe687ba9fbb | gerado |
| T-R10 | 1ee42cc8e7f8 | b419b0937afa | b2a61f1aca5f | not available (V174b): arquivos só com o cabeçalho, sem limiar de exposição registrado |
| T-R11 | 9ca33cd8ac2e | 9beab7b56e2b | b10e1e6c7b5e | gerado |
| T-R12 | 8db1af802082 | d104d9a1a8de | eec5f8cdf03c | gerado |
| T-O3 | 24c572d349ac | f9ce6ec9a900 | eeb4c71e1542 | gerado |

T-M1 e T-R7 são saídas entre países (um só conjunto de arquivos, sem ISO no nome); T-R6, T-R7 e T-R8 leem o `cross_country_h4` de três países (item 0). R_exp da T-R6: coluna vazia (V174b).

Não construídas: T-O1 solar e eólica nos três países ("no box to draw: the primary search ended as no_cases"; a T-O1 não é essencial).

## 5. Resultados (só números lidos dos artefatos)

Números com ponto decimal e sem separador de milhar. Janela core (2041-2070), cenário central e membro de referência m0, salvo indicação.

### 5a. Potencial, LCOE e conjunto F7 (membro de referência m0, janela core)

Origem: `outputs/thesis/T-R2_potential_<ISO>_<tec>.csv` (série `all_present`, `reference_m0`); LCOE: mediana entre células de `outputs/<ISO>/robustness_analysis/artifacts/nominal_lcoe_by_member_<tec>__core.parquet` (membro m0, cenário central); τ e domínio: `h5_summary_<tec>__core.parquet` (variante primária); fração: `potential_below_tau_<tec>__core.parquet` (m0, central, `all_present`, base nominal) sobre a potência `all_present` central de m0; conjunto F7 e k: `outputs/thesis/T-R8_hypothesis_profiles_<ISO>.json`.

| País | Tec. | P central (GW) | P restritivo (GW) | P permissivo (GW) | E central (TWh/ano) | E restritivo | E permissivo | LCOE nominal p50 (USD/MWh) | τ (USD/MWh) | capacidade com LCOE <= τ (GW) | fração | candidatas | conjunto F7 | k |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT | solar | 153.3 | 32.01 | 563.8 | 247.3 | 51.71 | 906.3 | 50.38 | 54.53 | 152.3 | 0.9934 | 3415 | 3414 | 342 |
| PRT | wind | 22.79 | 3.37 | 77.04 | 52.17 | 7.81 | 175.2 | 63.65 | 49.64 | 2.033 | 0.08918 | 3332 | 3332 | 334 |
| IND | solar | 806.1 | 211.6 | 4890.8 | 1331.6 | 353.5 | 8000.8 | 29.03 | 28.26 | 454.6 | 0.5639 | 93701 | 93490 | 9349 |
| IND | wind | 214.1 | 60.13 | 879.6 | 331.5 | 99.34 | 1297.3 | 71.79 | 36.43 | 13.58 | 0.06342 | 75535 | 75535 | 7554 |
| BRA | solar | 16489.5 | 4183.0 | 47080.7 | 26741.6 | 6789.5 | 76202.8 | 52.3 | 43.97 | 12.35 | 0.0007487 | 190521 | 190001 | 19001 |
| BRA | wind | 1990.7 | 372.2 | 6071.5 | 2712.2 | 506.5 | 8251.1 | 144.4 | 31.95 | 2.01 | 0.00101 | 178289 | 171181 | 17119 |

### 5b. H1 a H5 (variante primária, janela core; entre colchetes o intervalo entre as variantes de sensibilidade)

Origem: `outputs/thesis/T-R8_hypothesis_profiles_<ISO>.json` (campos `hypotheses.<H>.statistics`), que lê as tabelas `h1`..`h5_summary`, `h4_country` e `hypothesis` de `outputs/<ISO>/robustness_analysis/artifacts/`. O p_k² do H1 é `(k/n)²` com `k` e `n_cells` do `h1_summary`, derivado na F8 (DEC-096) e igual ao `reference` que o F7 gravou.

| País | Tec. | H1 C_k [faixa] | V_k | p_k² | H1 veredito | H2 O [faixa] | O_ref | H2 veredito | H3 D [faixa] | D_ref | Pi | B | H3 veredito |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT | solar | 0.9737 [0.9474; 0.9789] | 0 | 0.01004 | partially_supported_core_stable | 0.3197 [0.2892; 0.471] | 0.139 | not_supported | 0.009224 [0; 0.02362] | 0.7996 | 0.001057 | 0.002099 | not_supported |
| PRT | wind | 0.9611 [0.9311; 0.979] | 0 | 0.01005 | partially_supported_core_stable | 0.4451 [0.4023; 0.47] | 0.0644 | not_supported | 0 [0; 0] | 0.7995 | -0.0003776 | 0.001991 | not_supported |
| IND | solar | 0.9024 [0.7855; 0.9072] | 0 | 0.01 | partially_supported_core_stable | 0.5027 [0.3064; 0.7611] | 0.2472 | not_supported | 3.703e-05 [0; 0.004727] | 0.7993 | -0.0003246 | 0.001071 | not_supported |
| IND | wind | 0.89 [0.8644; 0.9131] | 0 | 0.01 | partially_supported_core_stable | 0.3391 [0.2556; 0.8022] | 0.1737 | not_supported | 0 [0; 0] | 0.8 | 0.0008376 | 0.007432 | not_supported |
| BRA | solar | 0.8532 [0.8147; 0.902] | 0.002947 | 0.01 | partially_supported_core_stable | 0.3398 [0.01291; 0.5152] | 0.1317 | not_supported | 0.0002808 [0; 0.006832] | 0.8 | -4.689e-05 | 0.00206 | not_supported |
| BRA | wind | 0.9628 [0.9529; 0.9708] | 0 | 0.01 | partially_supported_core_stable | 0.5097 [0.4223; 0.5688] | 0.1224 | not_supported | 0 [0; 0] | 0.8 | -0.0009942 | 0.004899 | not_supported |

| País | Tec. | H4 D_clim | D_tec | rho | perfil | H5 E_0 (TWh) | G | H_0 | R_loss | R_exp | H5 status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT | solar | 0 | 0 | n/a | no_displacement | 245.8 | n/a | n/a | n/a | not available (V174b) | not_testable: not testable: no national target (OQ-010) |
| PRT | wind | 0 | 0 | n/a | no_displacement | 6.243 | n/a | n/a | n/a | not available (V174b) | not_testable: not testable: no national target (OQ-010) |
| IND | solar | 0.001533 | 0 | 1 | climate_dominated | 771.7 | 759.4 | 12.29 | 3.816 | not available (V174b) | tested: H5b is not available: no hazard channel has a threshold: ['tx35_days', 'tx40_days', 'rx5day_mm', 'wet_p95_exceed_freq', 'gust_mean_annual_max_ms'] are null (OQ-051) |
| IND | wind | 0 | 0 | n/a | no_displacement | 36.94 | 375.5 | -338.5 | n/a | not available (V174b) | target_not_met_at_reference: target not met at reference: E_0 36.9393 does not exceed G 375.479 TWh/year |
| BRA | solar | 0 | 0 | n/a | no_displacement | 22.3 | 162.6 | -140.3 | n/a | not available (V174b) | target_not_met_at_reference: target not met at reference: E_0 22.3023 does not exceed G 162.579 TWh/year |
| BRA | wind | 0 | 0 | n/a | no_displacement | 9.821 | n/a | n/a | n/a | not available (V174b) | not_testable: not testable: no national target (OQ-010) |

Veredito do H4 por tecnologia (comparação entre países; origem `outputs/thesis/T-R8_hypothesis_summary.csv`): solar: not_supported (3 países, climate_dominated 1, techno_economic_dominated 0, mixed 0, no_displacement 2); wind: not_supported (3 países, climate_dominated 0, techno_economic_dominated 0, mixed 0, no_displacement 3).

### 5c. PRIM (caixa primária)

Origem: `outputs/<ISO>/robustness_analysis/artifacts/prim_box_<tec>__core.parquet` (linha `primary`).

| País | Tec. | status | n de futuros | n de casos | taxa-base | densidade | cobertura |
|---|---|---|---|---|---|---|---|
| PRT | solar | no_cases | 72000 | 0 | 0 | n/a | n/a |
| PRT | wind | no_cases | 60000 | 0 | 0 | n/a | n/a |
| IND | solar | no_cases | 72000 | 0 | 0 | n/a | n/a |
| IND | wind | no_cases | 60000 | 0 | 0 | n/a | n/a |
| BRA | solar | no_cases | 72000 | 0 | 0 | n/a | n/a |
| BRA | wind | no_cases | 60000 | 0 | 0 | n/a | n/a |

### 5d. F7b (resumo das três tabelas)

Origem: `outputs/<ISO>/external_validation/artifacts/` (`exclusion_shares`, `enrichment`, `published_comparison`).

**M-F7b-01, fração excluída por restrição nas usinas em operação** (média da parcela excluída; parcela das usinas com alguma exclusão)

| País | Tec. | usinas avaliadas | E1 | E2 | E3 | E4 | E5 | E6 | combinada (média; >0) |
|---|---|---|---|---|---|---|---|---|---|
| PRT | solar | 168 | 0.05344 | 0.00126 | 0.001729 | 0.4776 | 0.366 | 0.06266 | 0.7391; 1 |
| PRT | wind | 361 | 0.2843 | 0.0008001 | 0.0007956 | 0.5147 | 0.2615 | 0.04136 | 0.747; 1 |
| IND | solar | 3724 | 0.01442 | 0.01013 | 0.0406 | 0.06832 | 0.6138 | 0.4786 | 0.7687; 1 |
| IND | wind | 679 | 0.1006 | 0.01054 | 0.02969 | 0.03628 | 0.3427 | 0.7627 | 0.8369; 0.9672 |
| BRA | solar | 3946 | 0.08351 | 0.0008839 | 0.0115 | 0.1965 | 0.3203 | 0.1314 | 0.5132; 0.9916 |
| BRA | wind | 1135 | 0.1282 | 0.000714 | 0.006023 | 0.1248 | 0.1021 | 0.03381 | 0.3319; 0.9336 |

**M-F7b-02, razão de enriquecimento** (parcela da capacidade em operação no decil de menor custo (decil 1) sobre a parcela da área elegível do decil)

| País | Tec. | decil 1 | decil 2 | decil 10 | capacidade fora das candidatas (parcela) |
|---|---|---|---|---|---|
| PRT | solar | 4.159 | 0.8171 | 0.2677 | 0.0235 |
| PRT | wind | 4.918 | 1.324 | 0.3664 | 0.1986 |
| IND | solar | 2.955 | 1.054 | 0.2042 | 0.109 |
| IND | wind | 4.643 | 2.171 | 0.2025 | 0.2492 |
| BRA | solar | 7.296 | 1.413 | 0.04069 | 0.04726 |
| BRA | wind | 9.238 | 0.621 | 0 | 0.09827 |

**M-F7b-03, potencial publicado ao lado do F5** (sem razão nem veredito; `pending` sem valor)

| País | Tec. | fonte (ano) | estado | valor publicado | F5 central m0 | F5 restritivo | F5 permissivo | mesma definição |
|---|---|---|---|---|---|---|---|---|
| PRT | solar | SIMOES, S (2023) | pending | n/a | 153.3 | 32.01 | 563.8 | False |
| PRT | wind | SIMOES, S (2023) | pending | n/a | 22.79 | 3.37 | 77.04 | False |
| IND | solar | MINISTRY OF NEW AND RENEWABLE ENERGY (2024) | pending | n/a | 806.1 | 211.6 | 4890.8 | True |
| IND | solar | NATIONAL INSTITUTE OF SOLAR ENERGY (2025) | pending | n/a | 806.1 | 211.6 | 4890.8 | True |
| IND | wind | NATIONAL INSTITUTE OF WIND ENERGY (s/ano) | pending | n/a | 214.1 | 60.13 | 879.6 | True |
| IND | wind | NATIONAL INSTITUTE OF WIND ENERGY (s/ano) | pending | n/a | 214.1 | 60.13 | 879.6 | True |
| IND | wind | NATIONAL INSTITUTE OF WIND ENERGY (s/ano) | pending | n/a | 214.1 | 60.13 | 879.6 | True |
| BRA | wind | AMARANTE, Odilon A (2001) | registered | 143 GW | 1990.7 | 372.2 | 6071.5 | True |
| BRA | wind | MINISTERIO DE MINAS E ENERGIA; EMPRESA DE PESQUI (2020) | pending | n/a | 1990.7 | 372.2 | 6071.5 | True |
| BRA | wind | MINISTERIO DE MINAS E ENERGIA; EMPRESA DE PESQUI (2020) | pending | n/a | 1990.7 | 372.2 | 6071.5 | True |
| BRA | wind | EUREK, Kelly et al (2017) | registered | 14580.0 GW | 1990.7 | 372.2 | 6071.5 | True |
| BRA | solar | EMPRESA DE PESQUISA ENERGETICA (2018) | registered | 307 GW | 16489.5 | 4183.0 | 47080.7 | True |
| BRA | solar | EMPRESA DE PESQUISA ENERGETICA (2018) | registered | 28519.0 GW | 16489.5 | 4183.0 | 47080.7 | False |

Entradas por país (registered, pending): {'PRT': (0, 2), 'IND': (0, 5), 'BRA': (4, 2)}.

## 6. Desvios posteriores à tag `prereg-v1`

A tag está no commit `ccf764f` (2026-11-17 10:45 -03). O primeiro resultado de produção é o F6 do PRT do COMANDO 179, em 2026-11-18 (relatório `_notas_geofrea/producao_PRT_179.md`, repositório em `c934d71`, de 16:52 -03).

| DEC ou commit | data | descrição | rótulo |
|---|---|---|---|
| DEC-091 (`0d032e8`) | 2026-11-17 23:39 -03 | veredito do CF eólico, ramo B (OQ-114) | pré-resultado |
| DEC-092 (`d26994e`) | 2026-11-18 08:28 -03 | CF eólico de frota da Índia derivado | pré-resultado |
| DEC-093 (`1f15ddb`) | 2026-11-18 09:41 -03 | nenhum limiar de exposição com fonte; conjunto de canais do H5b vazio (OQ-051, OQ-115) | pré-resultado |
| DEC-094 (`48fa500`) | 2026-11-18 10:35 -03 | eixos de sensibilidade de tau, cf_min, q_ref e top_k (OQ-094) | pré-resultado |
| DEC-095 (`fa090bb`) | 2026-11-23 | rótulo de `3fcdfbe` (post-result correction pelo teste de data) e remissão do `c7af733` ao D-F7b-009 | registro; rótulo substituído pela DEC-097 |
| DEC-097 (COMANDO 191B) | 2026-11-23 | reclassifica a DEC-095: `3fcdfbe` é pré-resultado | registro |
| DEC-096 (`fa090bb`) | 2026-11-23 | p_k² do H1 derivado na F8 de k e n do F7 | pré-registro intacto; só código da F8 |
| D-core-056 (`fa090bb`) | 2026-11-23 | `cross_country_h4` compara todos os países configurados; recusa país sem `h4_country` | correção de infraestrutura fora da closure da F7; sem resultado alterado |
| D-core-055 (`0bc6a64`) | 2026-11-22 20:32 -03 | resumos de fase em `artifacts__<escala>` (correção de `main.py`; recuperação dos hashes de 0,05°) | correção de infraestrutura, fora do fingerprint de qualquer fase; sem resultado alterado |

DEC-089 e DEC-090 (2026-11-17) entram no próprio commit da tag, não depois dela. O digest do subconjunto pré-registrado não mudou em nenhum desses commits (digest agregado igual, item 2).

**Correções de código de fase depois do primeiro resultado (regra 8), com o rótulo da DEC-097:**

| Commit | data | o que muda | registro existente |
|---|---|---|---|
| `3fcdfbe` fix(f7) | 2026-11-18 20:46 -03 | F7 deixa de fora as células do F5 que o F6 exclui por falta de zona PV (`thesis_tables.py`) | **pré-resultado** (DEC-097, que substitui o rótulo da DEC-095; nenhum resultado de F7 anterior existia); L-253 |
| `c7af733` fix(f7b) | 2026-11-22 12:25 -03 | F7b deixa de fora as células sem LCOE do F6 (COMANDO 188A, D-F7b-009) | pré-resultado (DEC-095 d, mantido), D-F7b-009 |
| `86fabd8` feat(f6) | 2026-11-18 19:58 -03 | adoção do tamanho de amostra convergido (U-04), protocolo previsto | `docs/phases/F6_lcoe_modeling.md` (não é correção de erro) |
| `b361b96` perf(f7b) | 2026-11-20 11:57 -03 | F7b avalia usinas por janelas de linhas, bit-idêntico (OQ-068) | D-F7b-008 |
| `c632831` feat(f8) | 2026-11-22 22:01 -03 | frase na legenda da T-R6; teto de `results_synthesis`; sem efeito sobre o conteúdo numérico das saídas | V179c, L-254 |
| `fa090bb` fix(cross_country) | 2026-11-23 | p_k² na F8 e guardas do `cross_country_h4`; só `main.py` e `results_synthesis` | DEC-096, D-core-056 |

## 7. Pendências

### 7a. Perguntas abertas (`docs/OPEN_QUESTIONS.md`, 19)

OQ-014, OQ-043, OQ-057 e OQ-072 seguem a decisão do autor no COMANDO 191A; as demais seguem a classificação proposta na primeira versão.

| OQ | assunto | classe | motivo |
|---|---|---|---|
| OQ-007 | funções de perda C2 e C3 (F5/F6) | não bloqueia | o H5b e a T-R10 ficam "not available" por V174b/DEC-093; basta declarar a lacuna (L-250) |
| OQ-013 | pilha e hospedagem do explorer E1 | depois da v1.0 | E1 fora da v1.0 (seção 1, item 1) |
| OQ-014 | justificativa na literatura do min-max regret (Cap. 2) | bloqueia o texto | decisão do autor (COMANDO 191A); é revisão de literatura do capítulo, não afeta a pipeline |
| OQ-020 | sensibilidade q_ref = 0,01 não implementada | não bloqueia | o F7 recusa q_ref != 0 (D-F7-009); declarar como não rodada |
| OQ-043 | fonte do limite wind_factor_valid_range 0,5-1,5 | não bloqueia (L-231) | decisão do autor (COMANDO 191A); o limite é guarda Tier 3 declarada na L-231 |
| OQ-057 | potencial publicado do M-F7b-03: 9 entradas `pending` | bloqueia o texto | decisão do autor (COMANDO 191A); 4 registradas e 9 sem valor; o autor confere fonte, valor, definição e tier antes de citar |
| OQ-064 | sensibilidade à resolução da grade | não bloqueia | a rodada de 0,1° (COMANDO 189) cobre metade do pedido (F3 a F7 nos três países); falta 0,025° e o registro da dispersão como limitação |
| OQ-071 | retunar o ZZZ2 solar | depois da v1.0 | ZZZ2 só testa; decisão de 2026-11-12 deixou para depois dos Grupos 4, 5 e 7 |
| OQ-072 | licença CC BY-NC-SA do FABDEM e CC BY do REN | bloqueia publicação e depósito | decisão do autor (COMANDO 191A); o COMANDO 137 deixou para antes de qualquer publicação ou divulgação |
| OQ-078 | travamento do fork do ERA5 no Linux | depois da v1.0 | não reproduzido; o código roda em Windows |
| OQ-095 | rios e estradas do BRA 1,8x mais lentos no pipeline completo | depois da v1.0 | desempenho, sem efeito no resultado |
| OQ-096 | local do relatório da F1b (`audit/` ou A-08) | depois da v1.0 | consistência documental |
| OQ-097 | nomes das camadas de recurso na F3 | depois da v1.0 | refatoração |
| OQ-099 | tecnologias da F1b | depois da v1.0 | refatoração |
| OQ-100 | lista padrão de países | depois da v1.0 | refatoração |
| OQ-101 | versões de esquema das saídas | depois da v1.0 | refatoração |
| OQ-102 | chaves dos rasters alinhados da F2a | depois da v1.0 | refatoração |
| OQ-103 | expectativa para a camada de declividade | depois da v1.0 | configuração de auditoria |
| OQ-106 | ZZZ sem linha de base versionada de fingerprints | depois da v1.0 | teste sintético |

Resumo da classificação: bloqueia o texto: OQ-014 e OQ-057; bloqueia publicação e depósito: OQ-072; não bloqueia: OQ-007, OQ-020, OQ-043 (L-231) e OQ-064; depois da v1.0: as outras 12.

Fechadas nesta etapa: OQ-068 (COMANDO 187), OQ-098 (COMANDO 190C), OQ-094 e OQ-008 (COMANDO 175), OQ-051 e OQ-115 (COMANDO 174), OQ-114 (COMANDO 171).

### 7b. Marcas nos `.tex` e no `.bib` (`docs/thesis/methods/`)

| Arquivo | `\vfy` | `% verify` | `% open` |
|---|---|---|---|
| group1_technical_potential.tex | 0 | 8 | 0 |
| group2_core_costs.tex | 0 | 1 | 0 |
| group3_connection_degradation.tex | 0 | 2 | 0 |
| group6_land_eligibility.tex | 0 | 2 | 0 |
| grupo4.tex | 6 | 6 | 0 |
| grupo5.tex | 1 | 8 | 0 |
| grupo7.tex | 6 | 3 | 0 |
| synthesis_and_scenario_discovery.tex | 0 | 1 | 0 |
| total | 13 | 31 | 0 |

`refs_grupos_4_5_7.bib`: 55 entradas, 24 com `% verify` (DOI, páginas, autores, título ou ano não conferidos na fonte primária) e 8 com `% agent` (metadado tirado do texto do agente de pesquisa, sem conferência independente).

## 8. Lista de conferência da v1.0 (seção 1, item 1 do arquivo de comandos)

| # | Critério | Sim/Não | Evidência |
|---|---|---|---|
| 1 | F1 a F8 em produção nos três países | sim | item 1: todas as fases `success` em PRT, IND e BRA, incluindo `results_synthesis` |
| 2 | `cross_country_h4` | sim | manifestos de 0,05° e 0,1° com PRT, BRA e IND; `h4_verdict` com `3 of 3 countries have a profile`; veredito `not_supported` nas duas tecnologias (D-core-056) |
| 3 | F7b (`external_validation`) | sim | `success` nos três países; resumo em 5d |
| 4 | `lcoe_maps` | sim | `success` nos três países (finished 2026-11-20) |
| 5 | `robustness_maps` | sim | `success` nos três países (finished 2026-11-20) |
| 6 | rodada de sensibilidade de janela 2071-2100 | sim | papel `sensitivity` no `robustness_analysis` dos seis manifestos; tabelas H1 a H5 presentes (COMANDO 189) |
| 7 | rodada de escala 0,1° (V-07) | sim | F3 a F7 nos três países, manifestos `manifest__0p1deg.json`, H1 a H3 iguais aos de 0,05° (COMANDO 189) |
| 8 | saídas essenciais da seção 10 geradas (T-R10 e R_exp "not available", V174b) | sim | item 4: as 16 geradas; T-R6, T-R7 e T-R8 coerentes com o `cross_country_h4` de três países (conferido por script nas duas escalas, 0 incoerências); p_k² na T-R6 e nos perfis |
| 9 | prova P limpa | sim | item 1: `--plan` sem `execute` nem stale nas duas escalas; `check_manifests` VALID |
| 10 | V-03 sem violação | sim | 24 conjuntos de tabelas, 0 violações (COMANDO 189A); o r por célula e futuro não é gravado, então "r >= 0" e a célula de regret zero por futuro repousam no evaluator (`evaluator.py`, regret negativo levanta erro) |
| 11 | pré-registro: digests iguais; tag íntegra | sim | item 2 |
| 12 | repositório: HEAD = origin/main; workflows; lint | sim | item 3 |
| 13 | tag `v1.0` | sim (COMANDO 192) | tag anotada `c0b7f5e` no commit `107d1b8`, no remoto |
| 14 | seção 4 do arquivo de comandos preenchida | sim | linhas 177 a 191A preenchidas (achado B) |
| 15 | desvios rotulados e pendências classificadas | sim | itens 6 e 7 (DEC-095, reclassificada pela DEC-097; classificação das OQs pela decisão do autor) |

Todos os critérios estão em "sim", salvo a tag `v1.0` (COMANDO 192). Ressalvas que não mudam a resposta: a suíte inteira não foi repetida depois da última correção de uma linha (item 3).

## 9. Nada foi alterado

Nesta reexecução: SHA-256 de `outputs/*/manifest*.json` e `outputs/cross_country/manifest*.json`, HEAD (`fa090bb`) e `git status` (limpo) iguais aos do início da reexecução. O único arquivo escrito é este relatório (fora do repositório, regra 12).

