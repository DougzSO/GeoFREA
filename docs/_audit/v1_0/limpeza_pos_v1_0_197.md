# COMANDO 197: limpeza pós-v1.0 (2026-11-23)

Instantâneo (regra 3): `GeoFREA_data/_snapshots/snapshot_197_20261123/` (manifestos de 0,05° e 0,1° dos três países, os do cross_country e `latest.json`, com SHA256SUMS). Tag `v1.0` inalterada (`107d1b8`).

## Espaço livre em D:

| | KB livres | GB livres |
|---|---|---|
| antes | 956.864.264 | 912,5 |
| depois | 956.923.004 | 912,6 |
| diferença | 58.740 | 0,06 |

O ganho é pequeno porque os itens grandes de `GeoFREA_data` são M ou R (ver abaixo). Antes disso, o COMANDO 196 já tinha liberado 1,33 GiB das referências.

## Tabela por classe

| Classe | O que entrou | Itens | Tamanho |
|---|---|---|---|
| M (manter: citado por manifesto da v1.0 ou pela referência do 192) | artefatos dos manifestos (1.299 caminhos), `references/` (2,12 GB), pastas `audit/` e `unattended/` citadas pelos manifestos, logs cujo run_id está em manifesto ou referência, `_snapshots` do 178 e o último | 74 itens avulsos + os artefatos dos manifestos | 5,55 MB avulsos; `outputs/` 9,31 GB e `references/` 2,12 GB mantidos |
| R (manter: regenerável e lido por código) | `cache/clipped` (6,61 GB, nomes com hash da fonte e dos parâmetros, sem duplicata por chave), `interim/` (3,79 GB: caches de F2a, F3 e F1b, `_mainland_cache`, `cf_tables`), figuras e tabelas das pastas de fase, `outputs/thesis`, `outputs/comparison` | pastas inteiras | 10,4 GB mantidos, nenhum arquivo tocado |
| D (citado só por documento: movido para `archive/pre_v1_0/`) | 3 instantâneos (`_snapshots/20261117_pre169`, `pre170`, `pre173`), 2 relatórios de auditoria F1b, 4 pastas `unattended/20261029_*` (IND e BRA), 1 log de integridade, 1 log de rodada | 11 | 2,90 MB |
| X (apagado) | 128 itens de `audit/` e `unattended/` de rodadas antigas que nenhum manifesto cita, 189 logs com run_id fora dos manifestos e da referência, 135 logs fora do padrão run_id e sem citação, 72 arquivos `*.cachekey.before_adopt` e `*.before_restamp`, 18 instantâneos antigos sem citação (incluindo `latest_before_192.json` e `snapshot_196_20261123`), `snapshots_190A_20261122`, `round_fabdem_101.ps1` e `round_group6_98.ps1`, 25 pastas `__pycache__` do repositório | 546 + 25 | 31,99 MB + 23,3 MB |

A lista completa do apagado está em `GeoFREA_data/archive/pre_v1_0/DELETED_LIST_197.json`; a dos movidos, com origem e destino, em `GeoFREA_data/archive/pre_v1_0/MOVED.json`. O ambiente aceitou a exclusão, então não usei `_to_delete_pos_v1_0`.

Exceções que ficam sem citação, como pedido: `technical_potential/sensitivity_150m/` (D-F5-027, 0,56 GB só no BRA) e `external/` inteiro (27,2 GB, entradas). `raw/` (141 GB) não foi tocado. Os `archive/` de outubro (figuras de docs) já estavam arquivados e ficaram onde estavam.

## Caminhos atualizados nos documentos (só o caminho)

10 arquivos: `docs/PROGRESS.json`, `docs/phases/core.md`, `docs/phases/F1b_data_quality_audit.md`, `docs/_audit/checkpoint_98.md`, `oq051_173.md`, `oq114_170.md`, `performance_75.md`, `prontidao_169.md`, `revalidation_52.md`, `round_133.md` (11 linhas). Cada caminho passou a começar por `archive/pre_v1_0/`.

## Não provado, mantido

- `outputs/<ISO>/grid_alignment/artifacts/<ISO>_slope_aligned.tif` e `<ISO>_slope_counts_aligned.tif` (BRA 0,29 GB, IND 0,10 GB, PRT 0,005 GB; 3 de novembro): o manifesto cita as versões FABDEM sob as chaves `aligned/slope` e `aligned/slope_counts`, então estas parecem substituídas, mas só uma rodada de `grid_alignment` provaria que nada as lê. Ficaram como R.
- `interim/*/land_eligibility/*.npz` (formato anterior ao diretório de cache): o código converte um `.npz` com a mesma chave (`land_eligibility/pipeline.py`), então não são obsoletos por regra. Ficaram como R.
- Figuras em `outputs/<ISO>/<fase>/figures` e `overview`: não estão nos manifestos, mas são saídas da v1.0. Ficaram como R.

## Verificação (item 5)

- Manifestos dos três países, nas duas escalas, os do cross_country e `latest.json`: iguais aos do instantâneo (`cmp`).
- Prova P: `--plan` com 0 `stale` a 0,05° e a 0,1°; 0 `execute` a 0,05°.
- Digest agregado igual a `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235`.
- `lint_docs` limpo. Tag `v1.0` no commit `107d1b8`.
