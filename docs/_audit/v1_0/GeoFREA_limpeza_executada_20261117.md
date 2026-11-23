# Limpeza executada (COMANDO 166), 2026-11-17

Instantâneo dos manifestos: `GeoFREA_data/_snapshots/20261117_pre166/` (SHA-256 em SHA256SUMS.txt). Ao final, os três `manifest.json` têm o mesmo SHA-256.

## Movido para `GeoFREA_data/_to_delete/` (não apagado)
A ferramenta de exclusão com pedido de permissão não estava disponível, então valeu o plano alternativo. Lista completa com origem, destino e tamanho: `_to_delete/MOVED.json`. A estrutura relativa a `D:\Douglas\DOUTORADO` foi preservada.

| Item | Arquivos | Tamanho |
|---|---|---|
| cache/clipped/BRA_wind_speed_100m_72efbec52c8c_..tif.8660.tmp | 1 | 120,8 MB |
| interim/_code_digest_cache.json.13848.tmp | 1 | 340,8 KB |
| interim/_code_digest_cache.json.9008.tmp | 1 | 0 |
| outputs/{BRA,IND,PRT}/manifest.json.before_restamp | 3 | 626,7 KB |
| GeoFREA/tests/**/__pycache__/*-pytest-9.2.0.pyc | 152 | 7,8 MB |

Total: 158 arquivos, 129.605.316 bytes (129,6 MB), igual ao da 165A. Nenhum manifesto cita esses itens (a única ocorrência de 72efbec52c8c no manifesto da BRA é o SHA-256 do arquivo bruto de origem). O `_code_digest_cache.json` sem sufixo e o `.tif` final do recorte ficaram. Para apagar de vez: remover a pasta `_to_delete/`. Para restaurar: mover de volta pelo MOVED.json.

## Quarentena: nada movido
Regra do comando: qualquer referência impede a mudança. As seis pastas têm referência em documentos (nenhuma em código, config, testes ou manifestos):
- external/epe_r1: docs/_audit/bra_line_138_86.md
- archive/figures_20261026: docs/PROGRESS.json, docs/figures/migration_68.md
- archive/figures_20261020: docs/_audit/2026-10_general_audit_71.md, potential_maps_v2.md, docs/phases/F5_technical_potential.md
- archive/figures_run_report_20261022: docs/_audit/2026-10_general_audit_71.md, potential_maps_v2.md
- archive/docs_figures_67b: docs/_audit/2026-10_general_audit_71.md, docs/figures/display_layers_70.md, display_resolution_67b.md
- archive/docs_figures_potential_maps_v2: docs/_audit/potential_maps_v2.md e archive/_docs_figures_move_log_72.json

Não foi criado `_quarantine_20261117/` nem MOVED.json de quarentena. Se quiser mover mesmo assim (as referências são registros de onde os arquivos arquivados estão), é preciso um comando que autorize e atualize esses textos.

## Repositório
git rm de scripts/report_pv_zone_shares.py e scripts/seed_deferred_check.py (busca confirmou zero referência). Commit e757c99, push feito, três workflows success. Tag prereg-v1 continua em ccf764f.

## Mantido
references/, outputs/*/unattended, audit, grid_alignment/artifacts, external/solar_basis, sensitivity_above3000m, docs/_audit, database/, geoworld_framework/, _quarantine_20261030/ e os backups do arquivo de comandos. Backup novo: comandos_grupos_4_5_7_v3.bak13_20261117.md.
