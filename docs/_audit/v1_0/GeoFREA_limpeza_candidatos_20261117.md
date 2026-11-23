# GeoFREA: candidatos a limpeza (somente leitura, 2026-11-17)

Gerado pelo COMANDO 165A. Nada foi apagado, movido nem alterado. As classes sao: MANTER (entrada ou saida valida de fase que fica, config, codigo, testes, docs, linha de base, instantaneos), REGENERAVEL (recalculavel, com o custo), APAGAR (orfao, substituido ou sem referencia, com a evidencia) e INCERTO (decisao do autor). Nenhum arquivo que o manifesto cita (artefato ou caminho na saida de uma fase valida) esta marcado APAGAR. 'Modificado' e a data do diretorio ou do arquivo.

## Totais por classe

| Classe | GeoFREA_data: itens | GeoFREA_data: tamanho | GeoFREA: itens | GeoFREA: tamanho |
|---|---:|---:|---:|---:|
| MANTER | 101 | 189.41 GB | 69 | 45.7 MB |
| REGENERAVEL | 19 | 11.17 GB | 5 | 919.1 MB |
| APAGAR | 6 | 121.8 MB | 3 | 7.8 MB |
| INCERTO | 42 | 876.3 MB | 17 | 2.7 MB |

Espaco recuperavel certo (APAGAR): **129.6 MB**. Espaco que o autor pode liberar se decidir sobre os INCERTO: 879.0 MB (sem contar `references/`, onde o ganho real e 1.42 GB, ver a nota). Regeneravel: 12.09 GB.

## Tabela 1: GeoFREA_data (D:/Douglas/DOUTORADO/GeoFREA_data)

| Caminho | Tamanho | Modificado | Quem referencia | Classe | Motivo |
|---|---:|---|---|---|---|
| `raw/_shared_origin/` | 97.1 KB | 2026-10-14 | codigo/config/docs: 2 arquivos | MANTER | entrada de F1: manifesto de origem dos dados compartilhados. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/cmip6/` | 4.53 GB | 2026-09-27 | codigo/config/docs: 40 arquivos | MANTER | entrada de F1: CMIP6; entrada do F4. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/copernicus_dem30/` | 49.72 GB | 2026-10-07 | codigo/config/docs: 18 arquivos | MANTER | entrada de F1: elevacao GLO-30; entrada do F2a (grid_alignment/adapter.py) e base do FABDEM. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/era5/` | 45.12 GB | 2026-10-01 | codigo/config/docs: 44 arquivos | MANTER | entrada de F1: ERA5 horario e maximos diarios; entrada do F4 (climate_forcing). Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/esa_worldcover/` | 6.94 GB | 2026-10-08 | codigo/config/docs: 12 arquivos | MANTER | entrada de F1: WorldCover 10 m; entrada do F2a (land_cover). Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/gadm/` | 454.2 MB | 2026-10-06 | codigo/config/docs: 42 arquivos | MANTER | entrada de F1: fronteiras administrativas; entrada de todas as fases. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/gem/` | 29.4 MB | 2026-10-07 | codigo/config/docs: 48 arquivos | MANTER | entrada de F1: GEM trackers; entrada do F7b e do F2a. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/gwa/` | 16.12 GB | 2026-09-23 | codigo/config/docs: 38 arquivos | MANTER | entrada de F1: Global Wind Atlas; entrada do F2b e do F5. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/hydrosheds/` | 2.56 GB | 2026-09-23 | codigo/config/docs: 24 arquivos | MANTER | entrada de F1: rios; entrada do F2b e do F3. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/infrastructure_grid/` | 77.8 MB | 2026-10-14 | codigo/config/docs: 12 arquivos | MANTER | entrada de F1: rede eletrica; entrada do F2a. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/infrastructure_roads/` | 5.87 GB | 2026-10-14 | codigo/config/docs: 8 arquivos | MANTER | entrada de F1: estradas (GRIP4); entrada do F2b. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/isimip3b/` | 6.38 GB | 2026-10-05 | codigo/config/docs: 14 arquivos | MANTER | entrada de F1: ISIMIP3b; entrada do F4. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/land_cover/` | 6.89 GB | 2026-10-14 | codigo/config/docs: 79 arquivos | MANTER | entrada de F1: cobertura do solo; entrada do F2a e do F3. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/natural_earth/` | 3.2 MB | 2026-10-20 | codigo/config/docs: 6 arquivos | MANTER | entrada de F1: Natural Earth; entrada de figuras. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/population/` | 6.29 GB | 2026-10-14 | codigo/config/docs: 99 arquivos | MANTER | entrada de F1: populacao; entrada do F2b. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/solar_potential/` | 368.8 MB | 2026-10-14 | codigo/config/docs: 10 arquivos | MANTER | entrada de F1: PVOUT (Global Solar Atlas); entrada do F2b e do F5. Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/w5e5/` | 188.6 MB | 2026-10-15 | codigo/config/docs: 7 arquivos | MANTER | entrada de F1: W5E5; entrada do F4 (comparacao de dias de calor). Baixar de novo leva horas e depende de rede e de credenciais |
| `raw/wdpa/` | 99.3 MB | 2026-09-23 | codigo/config/docs: 12 arquivos | MANTER | entrada de F1: areas protegidas; entrada do F2b e do F3. Baixar de novo leva horas e depende de rede e de credenciais |
| `external/acer/` | 2.2 MB | 2026-11-02 | codigo/config: 1 arquivos | MANTER | entrada: ACER; entrada do F6 (custos de conexao) |
| `external/aneel_bpr/` | 2.9 MB | 2026-11-02 | codigo/config: 1 arquivos | MANTER | entrada: custos de baia da ANEEL; entrada do F6 (scripts/derive_bra_bay_cost_bpr.py) |
| `external/aneel_rea/` | 21.8 KB | 2026-11-02 | codigo/config: 0 arquivos | MANTER | entrada:  |
| `external/dnit/` | 132.0 KB | 2026-11-02 | codigo/config: 1 arquivos | MANTER | entrada:  |
| `external/epe_r1/` | 101.2 MB | 2026-11-02 | codigo/config: 0; docs: 1 | INCERTO | nenhum codigo nem config le esta pasta; so um documento a cita. Decisao do autor |
| `external/fabdem/` | 26.39 GB | 2026-11-06 | codigo/config: 10 arquivos | MANTER | entrada: DEM FABDEM; entrada do F2a (slope, D-F3-029); derivado do GLO-30 por scripts/acquire_fabdem.py |
| `external/ghsl/` | 100.8 MB | 2026-11-05 | codigo/config: 7 arquivos | MANTER | entrada: GHSL SMOD; entrada do F2a |
| `external/ind_costs/` | 46.9 KB | 2026-11-02 | codigo/config: 0 arquivos | MANTER | entrada:  |
| `external/osm_substations/` | 18.8 MB | 2026-11-02 | codigo/config: 5 arquivos | MANTER | entrada: subestacoes OSM; entrada do F2a (scripts/fetch_osm_substations.py) |
| `external/pv_degradation/` | 314.4 KB | 2026-11-02 | codigo/config: 4 arquivos | MANTER | entrada:  |
| `external/pvcz/` | 9.4 MB | 2026-11-02 | codigo/config: 13 arquivos | MANTER | entrada: zonas termicas do PV; entrada do F5 (degradacao por zona) |
| `external/solar_basis/` | 149.1 MB | 2026-11-16 | scripts/fetch_solar_basis_sources.py (codigo: 1) | INCERTO | PDFs baixados no COMANDO 161Q (fontes das notas de CF e de razao DC/AC). Regeneraveis pelo script, mas a EPE e a CSTEP responderam 404: se o autor ainda for ler os PDFs, manter |
| `external/vth/` | 39.1 MB | 2026-11-02 | codigo/config: 1 arquivos | MANTER | entrada: temperatura-limite (VTH); entrada do F5 |
| `external/world_bank/` | 3.3 KB | 2026-11-02 | codigo/config: 2 arquivos | MANTER | entrada:  |
| `cache/clipped/ (sem os .tmp)` | 7.10 GB | 2026-11-03 | grid_alignment (cache de recortes por chave de fingerprint, D-core-cache) | REGENERAVEL | recorte dos rasters brutos por pais; custo: reexecutar o F2a de PRT, IND e BRA (minutos a dezenas de minutos, ver wall_s dos manifestos) a partir de raw/ |
| `cache/clipped/BRA_wind_speed_100m_72efbec52c8c_c0_r666_w15742_h15701.tif.8660.tmp` | 120.8 MB | 2026-11-03 | nenhuma (nome com .tmp e o pid 8660; o manifesto nao o cita) | APAGAR | arquivo temporario de uma escrita interrompida em 2026-11-03; o arquivo final do mesmo recorte existe (BRA_wind_speed_100m_72efbec52c8c_..tif) |
| `interim/PRT/data_quality_audit/` | 59.9 MB | 2026-10-29 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase data_quality_audit de PRT; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/PRT/grid_alignment/` | 59.4 MB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase grid_alignment de PRT; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/PRT/land_eligibility/` | 18.3 MB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase land_eligibility de PRT; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/PRT/sanity/` | 1.3 KB | 2026-10-28 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase sanity de PRT; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/PRT/siting_layers/` | 2.6 KB | 2026-11-09 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase siting_layers de PRT; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/IND/data_quality_audit/` | 345.1 MB | 2026-10-29 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase data_quality_audit de IND; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/IND/grid_alignment/` | 268.6 MB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase grid_alignment de IND; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/IND/land_eligibility/` | 856.1 MB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase land_eligibility de IND; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/IND/sanity/` | 21.5 KB | 2026-10-29 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase sanity de IND; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/IND/siting_layers/` | 2.6 KB | 2026-11-09 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase siting_layers de IND; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/BRA/data_quality_audit/` | 390.7 MB | 2026-11-02 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase data_quality_audit de BRA; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/BRA/grid_alignment/` | 385.9 MB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase grid_alignment de BRA; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/BRA/land_eligibility/` | 1.59 GB | 2026-11-12 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase land_eligibility de BRA; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/BRA/sanity/` | 49.1 KB | 2026-10-09 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase sanity de BRA; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/BRA/siting_layers/` | 2.6 KB | 2026-11-09 | caches por fase (paths.interim); chaves por fingerprint de codigo (D-F3-021) | REGENERAVEL | cache da fase siting_layers de BRA; custo: reexecutar a fase (wall_s do manifesto) |
| `interim/_mainland_cache/` | 85.5 MB | 2026-11-04 | codigo: 1 arquivos | REGENERAVEL | cache de geometria continental |
| `interim/cf_tables/` | 14.6 MB | 2026-11-13 | codigo: 1 arquivos | REGENERAVEL | tabelas de CF (COMANDO 75) |
| `interim/_code_digest_cache.json` | 584.1 KB | 2026-11-17 | core/code_fingerprint.py | REGENERAVEL | cache de digests de codigo; recalculado em segundos |
| `interim/_code_digest_cache.json.13848.tmp` | 340.8 KB | 2026-11-02 | nenhuma (sufixo .tmp com pid) | APAGAR | temporario de escrita do cache de digests; o arquivo final existe |
| `interim/_code_digest_cache.json.9008.tmp` | - | 2026-11-05 | nenhuma (sufixo .tmp com pid) | APAGAR | temporario de escrita do cache de digests; o arquivo final existe |
| `outputs/PRT/artifacts/ (arquivos citados no manifesto)` | 70.3 KB | 2026-11-17 | manifesto de PRT: 11 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/artifacts/ (1 arquivos nao citados)` | 8.4 KB | 2026-11-17 | fase artifacts (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida artifacts (figuras de diagnostico e de overview) |
| `outputs/PRT/audit/ (arquivos citados no manifesto)` | 13.0 KB | 2026-11-02 | manifesto de PRT: 1 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/audit/ (35 arquivos nao citados)` | 456.9 KB | 2026-11-02 | o manifesto cita um unico relatorio (data_quality_audit.report_path); docs/phases/F1b_data_quality_audit.md, docs/_audit/revalidation_52.md e docs/_audit/2026-09_data_state_pre_G.md citam relatorios antigos pelo nome | INCERTO | relatorios de F1b de rodadas anteriores (2026-09-23 em diante); substituidos pelo vigente, mas alguns sao citados nos documentos: o autor decide |
| `outputs/PRT/climate_forcing/ (arquivos citados no manifesto)` | 7.1 MB | 2026-10-07 | manifesto de PRT: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/climate_forcing/ (38 arquivos nao citados)` | 17.8 MB | 2026-10-07 | fase climate_forcing (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida climate_forcing (figuras de diagnostico e de overview) |
| `outputs/PRT/data_quality_audit/ (7 arquivos nao citados)` | 62.4 KB | 2026-10-14 | fase data_quality_audit (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida data_quality_audit (figuras de diagnostico e de overview) |
| `outputs/PRT/deferred_check.json/ (1 arquivos nao citados)` | 6.4 KB | 2026-11-06 | fase deferred_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida deferred_check.json (figuras de diagnostico e de overview) |
| `outputs/PRT/grid_alignment/artifacts/ (arquivos citados no manifesto)` | 16.7 MB | 2026-10-07 | manifesto de PRT: 29 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/grid_alignment/artifacts/ (55 arquivos nao citados)` | 4.6 MB | 2026-10-07 | scripts/audit_slope_canopy_99.py e audit_slope_dem_test_100.py leem *_slope_counts_aligned.tif | INCERTO | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `outputs/PRT/land_eligibility/ (arquivos citados no manifesto)` | 8.7 MB | 2026-10-07 | manifesto de PRT: 27 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/manifest.json/ (1 arquivos nao citados)` | 192.0 KB | 2026-11-17 | fase manifest.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida manifest.json (figuras de diagnostico e de overview) |
| `outputs/PRT/overview/ (arquivos citados no manifesto)` | 6.1 MB | 2026-10-07 | manifesto de PRT: 9 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/overview/ (16 arquivos nao citados)` | 9.3 MB | 2026-10-07 | fase overview (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida overview (figuras de diagnostico e de overview) |
| `outputs/PRT/siting_layers/ (arquivos citados no manifesto)` | 7.2 MB | 2026-10-07 | manifesto de PRT: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/technical_potential/artifacts/ (arquivos citados no manifesto)` | 13.7 MB | 2026-10-27 | manifesto de PRT: 22 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/technical_potential/artifacts/ (10 arquivos nao citados)` | 3.3 MB | 2026-10-27 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/PRT/technical_potential/figures/ (arquivos citados no manifesto)` | 2.0 MB | 2026-10-27 | manifesto de PRT: 4 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/PRT/technical_potential/figures/ (21 arquivos nao citados)` | 6.7 MB | 2026-10-27 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/PRT/technical_potential/figures_run_report/ (6 arquivos nao citados)` | 392.6 KB | 2026-10-27 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/PRT/technical_potential/sensitivity_150m/ (8 arquivos nao citados)` | 6.8 MB | 2026-10-16 | docs: 3 arquivos; codigo: 0 | MANTER | sensibilidade de altura de cubo 150 m (D-F5-027; o relatorio docs/_audit/2026-10_general_audit_71.md diz 'keep') |
| `outputs/PRT/unattended/ (86 arquivos nao citados)` | 3.1 MB | 2026-11-06 | scripts/run_unattended.ps1 escreve; core/deferred_check.py le o resumo | INCERTO | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `outputs/PRT/unattended_check.json/ (1 arquivos nao citados)` | 37.0 KB | 2026-11-06 | fase unattended_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida unattended_check.json (figuras de diagnostico e de overview) |
| `outputs/PRT/manifest.json.before_restamp` | 190.3 KB | 2026-11-12 | scripts/restamp_parquet2.py cria; nenhum codigo o le | APAGAR | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `outputs/PRT/deferred_check.json` | 6.4 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/PRT/unattended_check.json` | 37.0 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/PRT/manifest.json` | 192.0 KB | 2026-11-17 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/IND/artifacts/ (arquivos citados no manifesto)` | 83.6 KB | 2026-11-17 | manifesto de IND: 11 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/audit/ (arquivos citados no manifesto)` | 13.2 KB | 2026-11-06 | manifesto de IND: 1 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/audit/ (26 arquivos nao citados)` | 355.7 KB | 2026-11-06 | o manifesto cita um unico relatorio (data_quality_audit.report_path); docs/phases/F1b_data_quality_audit.md, docs/_audit/revalidation_52.md e docs/_audit/2026-09_data_state_pre_G.md citam relatorios antigos pelo nome | INCERTO | relatorios de F1b de rodadas anteriores (2026-09-23 em diante); substituidos pelo vigente, mas alguns sao citados nos documentos: o autor decide |
| `outputs/IND/climate_forcing/ (arquivos citados no manifesto)` | 78.9 MB | 2026-10-07 | manifesto de IND: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/climate_forcing/ (38 arquivos nao citados)` | 15.0 MB | 2026-10-07 | fase climate_forcing (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida climate_forcing (figuras de diagnostico e de overview) |
| `outputs/IND/deferred_check.json/ (1 arquivos nao citados)` | 5.8 KB | 2026-11-06 | fase deferred_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida deferred_check.json (figuras de diagnostico e de overview) |
| `outputs/IND/grid_alignment/artifacts/ (arquivos citados no manifesto)` | 450.5 MB | 2026-10-06 | manifesto de IND: 31 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/grid_alignment/artifacts/ (57 arquivos nao citados)` | 105.4 MB | 2026-10-06 | scripts/audit_slope_canopy_99.py e audit_slope_dem_test_100.py leem *_slope_counts_aligned.tif | INCERTO | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `outputs/IND/land_eligibility/ (arquivos citados no manifesto)` | 211.7 MB | 2026-10-07 | manifesto de IND: 27 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/manifest.json/ (1 arquivos nao citados)` | 209.8 KB | 2026-11-17 | fase manifest.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida manifest.json (figuras de diagnostico e de overview) |
| `outputs/IND/overview/ (arquivos citados no manifesto)` | 6.3 MB | 2026-10-07 | manifesto de IND: 9 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/overview/ (16 arquivos nao citados)` | 9.3 MB | 2026-10-07 | fase overview (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida overview (figuras de diagnostico e de overview) |
| `outputs/IND/siting_layers/ (arquivos citados no manifesto)` | 194.9 MB | 2026-10-07 | manifesto de IND: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/technical_potential/artifacts/ (arquivos citados no manifesto)` | 350.7 MB | 2026-10-27 | manifesto de IND: 22 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/technical_potential/figures/ (arquivos citados no manifesto)` | 3.0 MB | 2026-10-27 | manifesto de IND: 4 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/IND/technical_potential/figures/ (21 arquivos nao citados)` | 7.2 MB | 2026-10-27 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/IND/technical_potential/figures_run_report/ (6 arquivos nao citados)` | 1.4 MB | 2026-10-27 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/IND/technical_potential/sensitivity_150m/ (8 arquivos nao citados)` | 116.0 MB | 2026-10-16 | docs: 3 arquivos; codigo: 0 | MANTER | sensibilidade de altura de cubo 150 m (D-F5-027; o relatorio docs/_audit/2026-10_general_audit_71.md diz 'keep') |
| `outputs/IND/technical_potential/sensitivity_above3000m/ (8 arquivos nao citados)` | 118.3 MB | 2026-10-16 | docs: 2 arquivos; codigo: 0 | INCERTO | sensibilidade do limite de 3000 m (D-F3-017); nenhum codigo atual escreve esta pasta; citada em 2 documentos |
| `outputs/IND/unattended/ (65 arquivos nao citados)` | 2.7 MB | 2026-11-06 | scripts/run_unattended.ps1 escreve; core/deferred_check.py le o resumo | INCERTO | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `outputs/IND/unattended_check.json/ (1 arquivos nao citados)` | 37.9 KB | 2026-11-06 | fase unattended_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida unattended_check.json (figuras de diagnostico e de overview) |
| `outputs/IND/manifest.json.before_restamp` | 208.1 KB | 2026-11-12 | scripts/restamp_parquet2.py cria; nenhum codigo o le | APAGAR | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `outputs/IND/deferred_check.json` | 5.8 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/IND/unattended_check.json` | 37.9 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/IND/manifest.json` | 209.8 KB | 2026-11-17 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/BRA/artifacts/ (arquivos citados no manifesto)` | 101.2 KB | 2026-11-17 | manifesto de BRA: 11 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/audit/ (arquivos citados no manifesto)` | 13.2 KB | 2026-11-06 | manifesto de BRA: 1 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/audit/ (27 arquivos nao citados)` | 361.8 KB | 2026-11-06 | o manifesto cita um unico relatorio (data_quality_audit.report_path); docs/phases/F1b_data_quality_audit.md, docs/_audit/revalidation_52.md e docs/_audit/2026-09_data_state_pre_G.md citam relatorios antigos pelo nome | INCERTO | relatorios de F1b de rodadas anteriores (2026-09-23 em diante); substituidos pelo vigente, mas alguns sao citados nos documentos: o autor decide |
| `outputs/BRA/climate_forcing/ (arquivos citados no manifesto)` | 172.6 MB | 2026-10-07 | manifesto de BRA: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/climate_forcing/ (38 arquivos nao citados)` | 15.8 MB | 2026-10-07 | fase climate_forcing (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida climate_forcing (figuras de diagnostico e de overview) |
| `outputs/BRA/data_quality_audit/ (4 arquivos nao citados)` | 37.2 KB | 2026-10-14 | fase data_quality_audit (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida data_quality_audit (figuras de diagnostico e de overview) |
| `outputs/BRA/deferred_check.json/ (1 arquivos nao citados)` | 5.9 KB | 2026-11-06 | fase deferred_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida deferred_check.json (figuras de diagnostico e de overview) |
| `outputs/BRA/grid_alignment/artifacts/ (arquivos citados no manifesto)` | 1.10 GB | 2026-10-07 | manifesto de BRA: 29 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/grid_alignment/artifacts/ (55 arquivos nao citados)` | 290.2 MB | 2026-10-07 | scripts/audit_slope_canopy_99.py e audit_slope_dem_test_100.py leem *_slope_counts_aligned.tif | INCERTO | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `outputs/BRA/land_eligibility/ (arquivos citados no manifesto)` | 478.4 MB | 2026-10-07 | manifesto de BRA: 27 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/manifest.json/ (1 arquivos nao citados)` | 230.0 KB | 2026-11-17 | fase manifest.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida manifest.json (figuras de diagnostico e de overview) |
| `outputs/BRA/overview/ (arquivos citados no manifesto)` | 7.6 MB | 2026-10-07 | manifesto de BRA: 9 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/overview/ (16 arquivos nao citados)` | 10.9 MB | 2026-10-07 | fase overview (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida overview (figuras de diagnostico e de overview) |
| `outputs/BRA/siting_layers/ (arquivos citados no manifesto)` | 507.1 MB | 2026-10-07 | manifesto de BRA: 13 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/technical_potential/artifacts/ (arquivos citados no manifesto)` | 956.3 MB | 2026-10-28 | manifesto de BRA: 22 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/technical_potential/figures/ (arquivos citados no manifesto)` | 3.7 MB | 2026-10-28 | manifesto de BRA: 4 arquivos | MANTER | entrada ou saida de fase valida (artefato do manifesto ou caminho citado na saida da fase) |
| `outputs/BRA/technical_potential/figures/ (21 arquivos nao citados)` | 7.3 MB | 2026-10-28 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/BRA/technical_potential/figures_run_report/ (6 arquivos nao citados)` | 2.2 MB | 2026-10-28 | fase technical_potential (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida technical_potential (figuras de diagnostico e de overview) |
| `outputs/BRA/technical_potential/sensitivity_150m/ (8 arquivos nao citados)` | 425.3 MB | 2026-10-16 | docs: 3 arquivos; codigo: 0 | MANTER | sensibilidade de altura de cubo 150 m (D-F5-027; o relatorio docs/_audit/2026-10_general_audit_71.md diz 'keep') |
| `outputs/BRA/unattended/ (63 arquivos nao citados)` | 2.9 MB | 2026-11-06 | scripts/run_unattended.ps1 escreve; core/deferred_check.py le o resumo | INCERTO | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `outputs/BRA/unattended_check.json/ (1 arquivos nao citados)` | 37.2 KB | 2026-11-06 | fase unattended_check.json (figuras e tabelas listadas na saida da fase, nao como artefatos do registro) | MANTER | saida da fase valida unattended_check.json (figuras de diagnostico e de overview) |
| `outputs/BRA/manifest.json.before_restamp` | 228.3 KB | 2026-11-12 | scripts/restamp_parquet2.py cria; nenhum codigo o le | APAGAR | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `outputs/BRA/deferred_check.json` | 5.9 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/BRA/unattended_check.json` | 37.2 KB | 2026-11-06 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/BRA/manifest.json` | 230.0 KB | 2026-11-17 | core/deferred_check.py, core/orchestrator.py | MANTER | estado vigente do pais |
| `outputs/comparison/` | 667.4 KB | 2026-10-26 | codigo: 17 arquivos | INCERTO | pasta de comparacao entre paises; verificar o conteudo antes de qualquer decisao |
| `logs/PRT/ (run_id vigente, 1 arquivo)` | 8.7 KB | 2026-11-17 | run_id do manifest.json | MANTER | log da rodada que gerou o estado vigente |
| `logs/PRT/ (74 logs de rodadas anteriores)` | 1.3 MB | 2026-11-17 | nenhum manifesto vigente cita estes run_id; alguns sao nomes de rodadas de referencia (references/<run_id>) | INCERTO | historico de execucao; inclui o log da rodada real acidental do PRT (445b0b7c...) do COMANDO 162B |
| `logs/IND/ (run_id vigente, 1 arquivo)` | 8.7 KB | 2026-11-17 | run_id do manifest.json | MANTER | log da rodada que gerou o estado vigente |
| `logs/IND/ (75 logs de rodadas anteriores)` | 1.4 MB | 2026-11-17 | nenhum manifesto vigente cita estes run_id; alguns sao nomes de rodadas de referencia (references/<run_id>) | INCERTO | historico de execucao; inclui o log da rodada real acidental do PRT (445b0b7c...) do COMANDO 162B |
| `logs/BRA/ (run_id vigente, 1 arquivo)` | 9.7 KB | 2026-11-17 | run_id do manifest.json | MANTER | log da rodada que gerou o estado vigente |
| `logs/BRA/ (76 logs de rodadas anteriores)` | 1.4 MB | 2026-11-17 | nenhum manifesto vigente cita estes run_id; alguns sao nomes de rodadas de referencia (references/<run_id>) | INCERTO | historico de execucao; inclui o log da rodada real acidental do PRT (445b0b7c...) do COMANDO 162B |
| `references/6ec04875eac7.../ (rodada vigente, latest.json)` | 2.28 GB | 2026-11-12 | references/latest.json; core/deferred_check.py | MANTER | referencia vigente dos tres paises (hard links para objects/) |
| `references/objects/ + latest.json` | 3.70 GB | 2026-11-09 | armazem de conteudo (SHA-256); os arquivos das rodadas sao hard links | MANTER | armazem das referencias; so a funcao de poda do store deve mexer nele |
| `references/1d34ab239123660e1622c3c5.../` | - | 2026-11-09 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/27c9336b9e3f342f868258e8.../` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/3a1b06e04c67118279bd49bf.../` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/74931e0a24f00a184ad0bfa8.../` | - | 2026-11-06 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/864efbcb2848180b4cb610e0.../` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/8f55f3e74ab30dcc8d7a2e8b.../` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/9c2dc3c88f93a3f8a0947187.../` | - | 2026-11-06 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/f392f2c4c3ed13d24920544b.../` | - | 2026-11-06 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | rodada aceita anterior. O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/seed_20261102_BRA/` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | semente (seed_). O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `references/seed_20261102_IND/` | - | 2026-11-04 | nenhum latest.json aponta; o store guarda toda rodada aceita (reference_store.py) | INCERTO | semente (seed_). O espaco liberado e so o dos arquivos que so ela guarda (ver a nota abaixo da tabela); apagar so pela funcao do store |
| `archive/_cleanup_72_data_log.json/` | 4.0 KB | 2026-10-27 | docs/scripts que citam: 0 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); nenhum documento o cita |
| `archive/_docs_figures_move_log_72.json/` | 7.4 KB | 2026-10-27 | docs/scripts que citam: 0 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); nenhum documento o cita |
| `archive/docs_figures_2026-10_data_diagnostics_figures/` | 2.1 MB | 2026-10-27 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_67b/` | 3.3 MB | 2026-10-27 | docs/scripts que citam: 2 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_audit_potential_65/` | 444.6 KB | 2026-10-27 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_coverage_alignment_54/` | 1.0 MB | 2026-10-27 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_potential_maps_absolute/` | 724.8 KB | 2026-10-27 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_potential_maps_v2/` | 2.3 MB | 2026-10-27 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/figures_20261020/` | 20.5 MB | 2026-10-20 | docs/scripts que citam: 2 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/figures_20261026/` | 55.3 MB | 2026-10-26 | docs/scripts que citam: 2 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/figures_run_report_20261022/` | 3.9 MB | 2026-10-22 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/group6_pre/` | 14.8 KB | 2026-11-05 | docs/scripts que citam: 1 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/hash_memos_20261027/` | 368.4 KB | 2026-10-27 | docs/scripts que citam: 0 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); nenhum documento o cita |
| `archive/logs_legacy_20261027/` | 2.2 MB | 2026-10-27 | docs/scripts que citam: 0 | INCERTO | arquivado pelo autor (scripts/archive_figures.py); nenhum documento o cita |
| `_baselines/` | 33.8 KB | 2026-11-17 | - | MANTER | linha de base do COMANDO 162B2 (hashes de technical_potential e potential_maps) |
| `_snapshots/` | 1.3 MB | 2026-11-17 | - | MANTER | instantaneos dos manifestos (regra 3 dos comandos) |
| `fixtures/` | 773.3 KB | 2026-09-24 | - | INCERTO | fixture do mundo sintetico ZZZ; verificar quem a le |
| `work/` | - | 2026-11-12 | - | INCERTO | pasta de trabalho vazia |

Espaco: as pastas de rodadas anteriores guardam hard links; as 9 rodadas e as 2 sementes juntas tem 1,42 GB de bytes que so elas guardam (as 2 sementes 0,79 GB e as 9 rodadas 0,63 GB), calculado por inode no COMANDO 165A. As linhas de references/ mostram tamanho '-' por isso.

## Tabela 2: GeoFREA (repositorio)

| Caminho | Tamanho | Modificado | Quem referencia | Classe | Motivo |
|---|---:|---|---|---|---|
| `docs/figures/ (25 arquivos)` | 7.7 MB | - | git | MANTER | figuras e guias de estilo citados em docs/figures/*.md |
| `tests/ (206 arquivos)` | 2.6 MB | - | git | MANTER | testes |
| `docs/_audit/ (131 arquivos)` | 2.6 MB | - | git | INCERTO | relatorios de auditoria (historico, citados em DECISIONS e LIMITATIONS); muitos sao relatorios de comandos de auditoria antigos (ids 59, 71, 147): o autor decide se o historico fica no repositorio ou so no git |
| `src/ (199 arquivos)` | 2.4 MB | - | git | MANTER | codigo das fases |
| `scripts/ (72 arquivos)` | 519.6 KB | - | git | MANTER | scripts (tabela abaixo) |
| `docs/phases/ (14 arquivos)` | 491.3 KB | - | git | MANTER | registros de decisao por fase |
| `docs/DECISIONS.md/ (1 arquivos)` | 332.1 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/thesis/ (21 arquivos)` | 288.3 KB | - | git | MANTER | textos dos grupos e .bib |
| `config/ (12 arquivos)` | 249.3 KB | - | git | MANTER | configuracao congelada pelo prereg-v1 e demais YAML/JSON |
| `docs/METHODOLOGY.md/ (1 arquivos)` | 201.5 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `main.py/ (1 arquivos)` | 83.0 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/LIMITATIONS.md/ (1 arquivos)` | 58.4 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/PIPELINE_GUIDE.md/ (1 arquivos)` | 56.3 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/data/ (2 arquivos)` | 52.3 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/OPEN_QUESTIONS.md/ (1 arquivos)` | 41.0 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/CONVENTIONS.md/ (1 arquivos)` | 22.2 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `docs/PROGRESS.json/ (1 arquivos)` | 19.0 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `CLAUDE.md/ (1 arquivos)` | 10.2 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `README.md/ (1 arquivos)` | 8.1 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `.github/ (3 arquivos)` | 6.6 KB | - | git | MANTER | workflows |
| `docs/PROJECT_SUMMARY.md/ (1 arquivos)` | 3.4 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `pyproject.toml/ (1 arquivos)` | 1.9 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `.claude/ (2 arquivos)` | 1.3 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `ci/ (1 arquivos)` | 0.6 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `.gitignore/ (1 arquivos)` | 0.6 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `.gitattributes/ (1 arquivos)` | 0.3 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `.env.example/ (1 arquivos)` | 0.2 KB | - | git | MANTER | documento ou arquivo de projeto versionado |
| `scripts/acquire_cmip6_resource_channel.py` | 10.9 KB | 2026-10-08 | tests 0, src 2, docs 1, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_dem30.py` | 1.0 KB | 2026-10-08 | tests 0, src 3, docs 5, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_era5_gust.py` | 28.0 KB | 2026-10-14 | tests 1, src 1, docs 6, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_era5_tmax_daily.py` | 9.6 KB | 2026-10-14 | tests 0, src 0, docs 1, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/acquire_fabdem.py` | 2.4 KB | 2026-11-06 | tests 2, src 1, docs 5, scripts 2 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_fabdem_test_100.py` | 7.7 KB | 2026-11-06 | tests 1, src 0, docs 1, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_gem_trackers.py` | 1.7 KB | 2026-10-08 | tests 0, src 2, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_ghsl_smod.py` | 1.6 KB | 2026-11-05 | tests 0, src 1, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_natural_earth.py` | 1.7 KB | 2026-10-20 | tests 0, src 1, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/acquire_worldcover10m.py` | 1.7 KB | 2026-10-20 | tests 0, src 0, docs 2, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/adopt_aligned_cache_keys.py` | 11.8 KB | 2026-11-06 | tests 2, src 2, docs 9, scripts 2 | MANTER | usado por teste, codigo ou outro script |
| `scripts/affected_tests.py` | 5.1 KB | 2026-11-09 | tests 1, src 0, docs 6, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/archive_figures.py` | 2.4 KB | 2026-10-26 | tests 0, src 0, docs 2, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/audit_potential.py` | 28.2 KB | 2026-11-13 | tests 1, src 0, docs 11, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/audit_slope_bin_error_97.py` | 4.0 KB | 2026-11-05 | tests 0, src 0, docs 1, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/audit_slope_canopy_99.py` | 12.8 KB | 2026-11-06 | tests 1, src 0, docs 1, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/audit_slope_dem_test_100.py` | 23.5 KB | 2026-11-06 | tests 1, src 0, docs 2, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/calibrate_tau_irena.py` | 15.3 KB | 2026-11-16 | tests 1, src 0, docs 2, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/check_manifests.py` | 3.5 KB | 2026-11-12 | tests 0, src 0, docs 5, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/coverage_audit_59.py` | 15.4 KB | 2026-10-20 | tests 0, src 0, docs 6, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/derive_bra_bay_cost_bpr.py` | 3.2 KB | 2026-11-02 | tests 0, src 0, docs 3, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/derive_pv_degradation_by_zone.py` | 8.0 KB | 2026-11-02 | tests 1, src 3, docs 4, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/export_pvcz_csv.py` | 3.0 KB | 2026-11-02 | tests 1, src 1, docs 1, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/f2b_sanity_report.py` | 7.8 KB | 2026-10-16 | tests 0, src 0, docs 3, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/fetch_conversion_indices.py` | 7.1 KB | 2026-11-16 | tests 2, src 1, docs 4, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/fetch_osm_substations.py` | 5.6 KB | 2026-11-02 | tests 0, src 2, docs 5, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/fetch_solar_basis_sources.py` | 13.3 KB | 2026-11-17 | tests 1, src 0, docs 0, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/find_decision.py` | 1.6 KB | 2026-10-27 | tests 0, src 0, docs 3, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/freeze_v01_fixtures.py` | 1.3 KB | 2026-10-08 | tests 2, src 0, docs 6, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/gcm_selection_spread.py` | 7.0 KB | 2026-10-08 | tests 1, src 0, docs 8, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/generate_prim_reference.py` | 4.9 KB | 2026-10-09 | tests 2, src 0, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/generate_zzz2_fixture.py` | 5.9 KB | 2026-11-05 | tests 2, src 0, docs 4, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/generate_zzz_fixture.py` | 19.1 KB | 2026-11-12 | tests 2, src 1, docs 11, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/lint_docs.py` | 14.2 KB | 2026-11-13 | tests 1, src 0, docs 2, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/list_expired_expected.py` | 2.3 KB | 2026-11-04 | tests 1, src 1, docs 2, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/make_archetype_fixtures.py` | 2.8 KB | 2026-10-26 | tests 0, src 1, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/make_style_guide_examples.py` | 3.1 KB | 2026-10-26 | tests 0, src 0, docs 3, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/place_w5e5_tasmax.py` | 4.2 KB | 2026-10-15 | tests 0, src 0, docs 3, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/preregistration_digest.py` | 2.8 KB | 2026-11-16 | tests 1, src 1, docs 1, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/publish_reference.py` | 4.3 KB | 2026-11-12 | tests 0, src 1, docs 5, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/rebaseline_config_fingerprint.py` | 4.8 KB | 2026-11-16 | tests 2, src 2, docs 6, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/report_group6_decomposition.py` | 17.3 KB | 2026-11-06 | tests 2, src 0, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/report_poi_counts.py` | 3.5 KB | 2026-11-02 | tests 0, src 0, docs 1, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/report_pv_zone_shares.py` | 4.1 KB | 2026-11-02 | tests 0, src 0, docs 0, scripts 0 | APAGAR | nenhuma referencia em testes, codigo, documentos ou outros scripts; recuperavel pelo git |
| `scripts/report_road_distance.py` | 6.7 KB | 2026-11-09 | tests 0, src 0, docs 1, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/restamp_parquet2.py` | 9.2 KB | 2026-11-12 | tests 1, src 1, docs 3, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/run_unattended.ps1` | 18.2 KB | 2026-11-06 | tests 1, src 0, docs 8, scripts 2 | MANTER | usado por teste, codigo ou outro script |
| `scripts/seed_deferred_check.py` | 2.1 KB | 2026-10-29 | tests 0, src 0, docs 0, scripts 0 | APAGAR | nenhuma referencia em testes, codigo, documentos ou outros scripts; recuperavel pelo git |
| `scripts/seed_references.py` | 2.5 KB | 2026-11-04 | tests 0, src 0, docs 2, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/size_f5_to_f8.py` | 11.7 KB | 2026-10-15 | tests 0, src 0, docs 8, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/stamp_manifest_hashes.py` | 5.2 KB | 2026-10-20 | tests 1, src 0, docs 4, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/unattended_check.py` | 7.0 KB | 2026-11-09 | tests 1, src 1, docs 6, scripts 2 | MANTER | usado por teste, codigo ou outro script |
| `scripts/unattended_resume.py` | 3.4 KB | 2026-11-06 | tests 1, src 0, docs 1, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/verify_cache_integrity.py` | 5.9 KB | 2026-11-06 | tests 0, src 0, docs 8, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/verify_era5_hourly.py` | 3.5 KB | 2026-11-12 | tests 0, src 0, docs 1, scripts 0 | INCERTO | script de uso pontual: so documentos o citam (registro historico); sem teste |
| `scripts/zzz2_world.py` | 7.9 KB | 2026-11-02 | tests 2, src 0, docs 5, scripts 1 | MANTER | usado por teste, codigo ou outro script |
| `scripts/zzz3_world.py` | 5.2 KB | 2026-11-12 | tests 1, src 0, docs 0, scripts 0 | MANTER | usado por teste, codigo ou outro script |
| `scripts/zzz_climate_fixture.py` | 12.8 KB | 2026-10-15 | tests 0, src 0, docs 5, scripts 2 | MANTER | usado por teste, codigo ou outro script |
| `src/geofrea.egg-info/` | 9.5 KB | 2026-11-09 | gitignore | MANTER | instalacao editavel (pip install -e): o pacote precisa dela |
| `.venv/` | 887.0 MB | 2026-09-22 | gitignore | REGENERAVEL | ambiente virtual do projeto (pytest 9.1.1); custo de recriar: segundos a minutos |
| `.mypy_cache/` | 6.7 MB | 2026-11-10 | gitignore | REGENERAVEL | cache do mypy; custo de recriar: segundos a minutos |
| `.pytest_cache/` | 149.7 KB | 2026-11-02 | gitignore | REGENERAVEL | cache do pytest; custo de recriar: segundos a minutos |
| `.ruff_cache/` | 113.9 KB | 2026-11-09 | gitignore | REGENERAVEL | cache do ruff; custo de recriar: segundos a minutos |
| `.git/` | 30.2 MB | 2026-11-17 | gitignore | MANTER | historico do repositorio |
| `.env` | 0.7 KB | 2026-09-27 | gitignore | MANTER | caminhos e chaves locais (nao versionado) |
| `**/__pycache__/ (627 arquivos: Python, pytest 9.0.2 do interpretador global e pytest 9.1.1 do .venv)` | 25.1 MB | - | gitignore; o .venv usa o pytest 9.1.1 e o Python global o 9.0.2 | REGENERAVEL | bytecode; recriado na proxima execucao (segundos) |
| `**/__pycache__/*-pytest-9.2.0.pyc (152 arquivos)` | 7.8 MB | - | nenhuma: nem o Python global (pytest 9.0.2) nem o .venv (pytest 9.1.1) usam o pytest 9.2.0 | APAGAR | bytecode de testes compilado por uma versao do pytest que nao esta mais instalada em nenhum dos dois ambientes |

## Fora dos dois diretorios (informativo, nao entra nos totais)

- `_quarantine_20261030/` (D:/Douglas/DOUTORADO): modificado em 2026-10-30; 1,11 GB, 555 arquivos (du e find do COMANDO 165A). Decisao do autor.
- `other/` (D:/Douglas/DOUTORADO): modificado em 2026-11-05; 1 MB, 14 arquivos (du e find do COMANDO 165A). Decisao do autor.
- `database/` (D:/Douglas/DOUTORADO): modificado em 2026-10-27; 126,4 GB, 2.735 arquivos (du e find do COMANDO 165A). Decisao do autor.
- `geoworld_framework/` (D:/Douglas/DOUTORADO): modificado em 2026-08-19; 5,06 GB, 20.311 arquivos (du e find do COMANDO 165A). Decisao do autor.
- `shared-data-sources/` (D:/Douglas/DOUTORADO): modificado em 2026-10-15; 27 MB, 17 arquivos (du e find do COMANDO 165A). Decisao do autor.
- 12 copias de seguranca do arquivo de comandos (`comandos_grupos_4_5_7_v3.bak*_2026111*.md`, 803.0 KB no total) e `comandos_grupos_4_5_7_v2.md`: o autor pode manter so a ultima.

## Os 15 maiores APAGAR

| Caminho | Tamanho | Evidencia |
|---|---:|---|
| `cache/clipped/BRA_wind_speed_100m_72efbec52c8c_c0_r666_w15742_h15701.tif.8660.tmp` | 120.8 MB | arquivo temporario de uma escrita interrompida em 2026-11-03; o arquivo final do mesmo recorte existe (BRA_wind_speed_100m_72efbec52c8c_..tif) |
| `**/__pycache__/*-pytest-9.2.0.pyc (152 arquivos)` | 7.8 MB | bytecode de testes compilado por uma versao do pytest que nao esta mais instalada em nenhum dos dois ambientes |
| `interim/_code_digest_cache.json.13848.tmp` | 340.8 KB | temporario de escrita do cache de digests; o arquivo final existe |
| `outputs/BRA/manifest.json.before_restamp` | 228.3 KB | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `outputs/IND/manifest.json.before_restamp` | 208.1 KB | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `outputs/PRT/manifest.json.before_restamp` | 190.3 KB | copia do manifesto anterior ao restamp de 2026-11-12; substituida pelo manifest.json vigente |
| `scripts/report_pv_zone_shares.py` | 4.1 KB | nenhuma referencia em testes, codigo, documentos ou outros scripts; recuperavel pelo git |
| `scripts/seed_deferred_check.py` | 2.1 KB | nenhuma referencia em testes, codigo, documentos ou outros scripts; recuperavel pelo git |
| `interim/_code_digest_cache.json.9008.tmp` | 0.0 KB | temporario de escrita do cache de digests; o arquivo final existe |

## Os 15 maiores INCERTO

| Caminho | Tamanho | Motivo |
|---|---:|---|
| `outputs/BRA/grid_alignment/artifacts/ (55 arquivos nao citados)` | 290.2 MB | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `external/solar_basis/` | 149.1 MB | PDFs baixados no COMANDO 161Q (fontes das notas de CF e de razao DC/AC). Regeneraveis pelo script, mas a EPE e a CSTEP responderam 404: se o autor ainda for ler os PDFs, manter |
| `outputs/IND/technical_potential/sensitivity_above3000m/ (8 arquivos nao citados)` | 118.3 MB | sensibilidade do limite de 3000 m (D-F3-017); nenhum codigo atual escreve esta pasta; citada em 2 documentos |
| `outputs/IND/grid_alignment/artifacts/ (57 arquivos nao citados)` | 105.4 MB | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `external/epe_r1/` | 101.2 MB | nenhum codigo nem config le esta pasta; so um documento a cita. Decisao do autor |
| `archive/figures_20261026/` | 55.3 MB | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/figures_20261020/` | 20.5 MB | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `outputs/PRT/grid_alignment/artifacts/ (55 arquivos nao citados)` | 4.6 MB | rasters de contagem de slope e arquivos auxiliares do F2a fora do registro do manifesto; scripts de auditoria dependem deles |
| `archive/figures_run_report_20261022/` | 3.9 MB | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `archive/docs_figures_67b/` | 3.3 MB | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |
| `outputs/PRT/unattended/ (86 arquivos nao citados)` | 3.1 MB | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `outputs/BRA/unattended/ (63 arquivos nao citados)` | 2.9 MB | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `outputs/IND/unattended/ (65 arquivos nao citados)` | 2.7 MB | pastas de rodadas desassistidas (adopt.log, manifest_before, memory.csv); historico de rodadas antigas |
| `docs/_audit/ (131 arquivos)` | 2.6 MB | relatorios de auditoria (historico, citados em DECISIONS e LIMITATIONS); muitos sao relatorios de comandos de auditoria antigos (ids 59, 71, 147): o autor decide se o historico fica no repositorio ou so no git |
| `archive/docs_figures_potential_maps_v2/` | 2.3 MB | arquivado pelo autor (scripts/archive_figures.py); citado em documentos |

## Plano de remocao em dry-run (NAO EXECUTADO)

So os itens APAGAR. Cada comando abaixo esta como comentario; o autor aprova num comando separado. Antes de executar qualquer um, imprimir o item e tirar um instantaneo dos manifestos (regra 3).

```bash
# dry-run: nada abaixo foi executado
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/cache/clipped/BRA_wind_speed_100m_72efbec52c8c_c0_r666_w15742_h15701.tif.8660.tmp'   # 120.8 MB
# find 'D:/Douglas/DOUTORADO/GeoFREA' -path '*/__pycache__/*' -name '*-pytest-9.2.0.pyc' -not -path '*/.venv/*' -delete   # 7.8 MB
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/interim/_code_digest_cache.json.13848.tmp'   # 340.8 KB
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/outputs/BRA/manifest.json.before_restamp'   # 228.3 KB
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/outputs/IND/manifest.json.before_restamp'   # 208.1 KB
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/outputs/PRT/manifest.json.before_restamp'   # 190.3 KB
# git -C 'D:/Douglas/DOUTORADO/GeoFREA' rm -- scripts/report_pv_zone_shares.py   # 4.1 KB; precisa de commit proprio e da suite
# git -C 'D:/Douglas/DOUTORADO/GeoFREA' rm -- scripts/seed_deferred_check.py   # 2.1 KB; precisa de commit proprio e da suite
# rm -- 'D:/Douglas/DOUTORADO/GeoFREA_data/interim/_code_digest_cache.json.9008.tmp'   # 0.0 KB
```
