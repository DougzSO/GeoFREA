# Limpeza 167 (2026-11-17)

Regras 1 a 4: nenhuma violada. Nenhuma fase, main ou orquestrador rodou em dado real. Instantâneo dos manifestos em `GeoFREA_data/_snapshots/20261117_pre167/` (SHA256SUMS.txt).

Teste de exclusão (item 2): criar e apagar um arquivo vazio em `GeoFREA_data/` funcionou. Os itens APAGAR foram excluídos de fato; não houve `_to_delete_20261117`.

| Item | Decisão | Feito | Tamanho | Destino |
|---|---|---|---|---|
| D1 `GeoFREA_data/_to_delete/` | APAGAR | sim (159 arquivos: os 158 mais o MOVED.json) | 125 MB | excluído |
| D2 `references/` | PODAR pela função do store | NÃO: não existe função de poda em `core/reference_store.py` (só publish, resolve, mark_historical). Nada apagado à mão. | 1,42 GB pendentes | pendente: COMANDO 196 |
| D3 `_quarantine_20261030/` | APAGAR se sem referência | sim. Buscadas as strings `_quarantine_20261030`, `quarantine_2026`, `GeoFREA_data_profile76`, `docs_backup`, `restore_quarantine`, `moves.json`, `IND_aside_75`, `PRT_aside_75`, `IND_partial_75` em todos os arquivos versionados do repositório e em `raw/_shared_origin/manifest.json` e nos três manifestos: 0 ocorrências. Havia uma junção `GeoFREA_data_profile76\raw` apontando para `GeoFREA_data\raw`; removida só a junção antes (raw com 2264 arquivos antes e depois). | 1.106 MB, 555 arquivos | excluído |
| D4 backups da v3 (bak, bak2 a bak12) e `comandos_grupos_4_5_7_v2.md` | APAGAR | sim, 13 arquivos; ficam o v3 vigente e o bak13 | 0,8 MB | excluído |
| D5 caches do repositório | APAGAR | sim: `.mypy_cache` 7 MB, `.pytest_cache` 1 MB, `.ruff_cache` 1 MB e 26 pastas `__pycache__` fora de `.venv` (26 MB, recriadas pela prova P e apagadas de novo) | ~35 MB | excluído |
| D6 `GeoFREA_data/work/` | APAGAR | sim (vazia) | 0 | excluído |
| D7 `database/`, `geoworld_framework/`, `other/`, `shared-data-sources/` | MANTER | só inventário (abaixo) | | |
| D8 INCERTO restantes | MANTER | não tocados | | |
| D9 relatórios soltos na raiz | MOVER | sim, 3 arquivos para `_notas_geofrea/`: GeoFREA_resumo_framework_20261117.md, GeoFREA_limpeza_candidatos_20261117.md, GeoFREA_limpeza_executada_20261117.md | | `_notas_geofrea/` |

Espaço liberado: cerca de 1,27 GB (125 + 1.106 + 35 + 1 MB). Espaço livre em D: 923 GB antes, 924 GB depois (df, arredondado).

## Inventário do item 5 (somente leitura)

`database/`: 2.735 arquivos, 132,5 GB (archive 60,7 GB, raw 71,5 GB, unused 0,35 GB). O `raw/_shared_origin/manifest.json` registra 233 arquivos copiados de `database/raw` para `GeoFREA_data/raw`: todos existem na origem com o mesmo tamanho (233 de 233, 0 divergência), somando 19,89 GB (cerca de 15% de `database/`). Hash não calculado.

| Pasta | Primeiro nível | Tamanho | Data |
|---|---|---:|---|
| geoworld_framework | .git | 1.678 MB | 2026-10-15 |
| | .venv | 772 MB | 2026-03-19 |
| | data | 1.248 MB | 2026-05-21 |
| | outputs | 1.497 MB | 2026-08-18 |
| | outputs_baseline | 66 MB | 2026-08-06 |
| | src | 3,0 MB | 2026-06-25 |
| | tests, docs, configs, scripts e arquivos soltos | < 1 MB cada | 2026-05 a 2026-08 |
| other | 15 arquivos soltos (playbooks v1 e v2, .tex dos grupos antigos, portfólio de artigos, notas .txt) | ~0,3 MB no total | 2026-09-21 a 2026-11-03 |
| shared-data-sources | data | 27,1 MB | 2026-10-15 |
| | scripts | 0,1 MB | 2026-10-15 |
| | 4 .md | < 0,1 MB | 2026-10-15 |

## Verificação (item 7)
- Os três manifest.json têm o mesmo SHA-256 do instantâneo (BRA fa2df673…, IND f3bea2bc…, PRT 46b5a9f4…).
- Prova P: 0 diferenças (12 fases por país).
- `git status` do repositório: limpo. Nenhum commit.
