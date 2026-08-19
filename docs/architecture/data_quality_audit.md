Corresponde à Fase 1 — Audit do GeoWorld legado.

# Data Quality Audit — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/data_auditor.py` (`DataAuditor` + funções module-level, 1390 linhas, lidas por completo em 2026-08-19). Cross-referenciado com `docs/TASKS.md`/`docs/archive/backlog-full-2026-08.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: auditoria de qualidade dos dados brutos **antes** de qualquer processamento — não modifica dados, não alimenta cálculo científico downstream. Mascara pelo polígono real do país (não bounding-box) para estatísticas de área precisas (docstring do módulo justifica isso explicitamente: um bbox de Portugal incluiria ~50.000 km² da Espanha).

**Inputs** (`run()`, L898-909): `status` dict do `DataOrchestrator` (caminhos para Solar/Wind/Seismic/Land Cover/Lakes/Rivers), `elev_path`, `slope_path`, `pop_path`, `plants_df`, `country_gdf` (polígono mainland, via `get_mainland_gdf()`), `skip_land_cover`.

**Outputs**: dict `audit` (rasters, land_cover, power_plants, alerts, summary, timings) — **não persistido como artefato Pydantic do pipeline** (é só um relatório de texto). Relatório salvo em `outputs/reports/audit_{CODE}_{timestamp}.txt` (L1385-1389) — **raiz do repo, não `outputs/{ISO3}/audit/`** (ver §d, BLOCKER-015).

**Não há CRS/shape de saída** — este módulo lê rasters em seu CRS nativo (reprojeta apenas para UTM local ao calcular área via `get_local_utm_crs`, `src/utils/utils.py`, usado em `get_mainland_gdf`/`detect_island_nation`).

---

## b. Fórmulas e localização exata

| # | Fórmula | Linha |
|---|---|---|
| 1 | **Área geodésica por linha de pixel** (correção por latitude, aproximação de arco meridional/paralelo WGS84): `lat_km = (111132.92 − 559.82·cos(2φ) + 1.175·cos(4φ) − 0.0023·cos(6φ)) / 1000`; `lon_km = (111412.84·cos(φ) − 93.50·cos(3φ) + 0.118·cos(5φ)) / 1000`; área do pixel = `res_x·lon_km × res_y·lat_km` | `_row_area_km2()`, L219-265 |
| 2 | **Detecção de nação insular**: `largest_pct = largest_polygon_area / total_area`; é insular se `largest_pct < (1 − threshold_pct)`, `threshold_pct=0.60` (i.e., insular se o maior polígono cobre <40% do território total) | `detect_island_nation()`, L112-152 |
| 3 | **Checagem de inatividade do critério de slope**: se `slope_max_observado < slope_threshold_deg` (de `parameters.json`, fallback 15.0°), emite alerta de que o critério de slope não exclui nenhum pixel | `run()`, L1042-1086 |
| 4 | **Sanity check de PVOUT solar**: alerta se `mean` fora de `(1.0, 10.0)` kWh/m²/dia — indício de unidade errada (ex. arquivo em kWh/kWp/ano) | `run()`, L978-991 |
| 5 | **Diagnóstico de resolução divergente**: alerta se `resolution / expected > (1+tol)` ou `< (1−tol)`, `tol` de `settings.yaml`'s `audit.resolution_tolerance` (fallback 0.5) | `diagnose_consistency()`, L794-837 |

---

## c. Parâmetros hardcoded

| # | Local | Valor | Status |
|---|---|---|---|
| 1 | `detect_island_nation`, `threshold_pct` (L114) | `0.60` | Hardcoded default de argumento — nunca sobrescrito em nenhuma chamada real (`run()` chama sem argumento, L951) |
| 2 | `expected_resolutions` fallback dict (L869-876) | `land_cover=0.0001°, solar/wind=0.0083°, elevation/slope=0.005°` | Fallback se `settings.yaml`'s `audit.expected_resolutions` ausente — não é científico, é um gate de diagnóstico |
| 3 | `res_tolerance` fallback (L896) | `0.5` | Fallback se `audit.resolution_tolerance` ausente de `settings.yaml` — **já tem warning explícito adicionado (INVAR-002)**, ver §d |
| 4 | `slope_threshold_deg` fallback (L1063) | `15.0°` | Só usado se o país não tiver entrada em `parameters.json` (via `has_country()`) — puramente para a checagem de inatividade do alerta, não afeta cálculo real de nenhuma fase downstream |
| 5 | Sanity bounds do PVOUT solar (L982) | `(1.0, 10.0)` kWh/m²/dia | Hardcoded, gate de qualidade de dado |
| 6 | `_CHUNK_ROWS = 4_000` (L72) | Tamanho de chunk para leitura de rasters grandes (fallback de memória) | Puramente técnico/performance, não científico |

Nenhum parâmetro científico (CF, LUF, densidade, threshold de suitability) é usado por este módulo — ele é estritamente diagnóstico.

---

## d. Cross-check de BLOCKERs/INVARs já resolvidos

| Item | Confirmado presente? | Evidência |
|---|---|---|
| **INVAR-001** (`ConfigLoader.has_country()` adicionado; `except Exception` genérico removido) | **Sim** | L1049-1068: usa `self.cfg.has_country(country_code)` explicitamente para decidir entre fallback (15.0°) e leitura real de `parameters.json`, com comentário extenso justificando por que `has_country()` é usado em vez de `try/except ConfigError` (distinguir "país ausente" de "entrada existente mas malformada"). |
| **INVAR-002** (`resolution_tolerance` ausente gera `logger.warning` explícito) | **Sim** | L889-895: bloco `if "resolution_tolerance" not in audit_cfg:` com `logger.warning(...)` explícito, comentário extenso (L877-888) documentando que essa chave não afeta nenhum valor científico downstream, só a calibração do próprio alerta de diagnóstico. |
| **BLOCKER-015** (skip-check da Fase 1 olha para diretório errado) | **Confirmado ainda ABERTO** (não é bug deste módulo, mas do chamador) | Este módulo persiste corretamente em `outputs/reports/audit_{CODE}_{timestamp}.txt` (L1385-1389, `self.reports_dir = cfg.base_dir / "outputs" / "reports"`, L863). O bug está em `main.py`'s skip-check (não lido nesta passada, mas `TASKS.md` confirma: glob aponta para `outputs/{code}/audit/`, que este módulo nunca escreve). |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **`threshold_pct=0.60` de `detect_island_nation` nunca é configurável** — está hardcoded e nunca sobrescrito em nenhuma chamada real. **Pergunta**: esse limiar (40% de território "perdido" pela filtragem de mainland dispara o alerta) tem base metodológica específica, ou é um valor de bom senso que poderia virar parâmetro de config no GeoFREA?
2. **A auditoria não bloqueia nem altera o pipeline** — é puramente informativa (gera um relatório de texto, nunca é lida por nenhuma fase downstream, conforme `docs/memory/03-pipeline.md`). **Pergunta**: no GeoFREA, os alertas desta fase (ex. "SLOPE THRESHOLD INACTIVE", "PVOUT em unidade errada") deveriam ganhar algum mecanismo de bloqueio automático (ex. abortar o pipeline, ou exigir confirmação humana) em vez de só aparecer no relatório de texto?
3. **`_row_area_km2`'s fórmula geodésica** (aproximação de arco meridional/paralelo) é reimplementada aqui — e uma fórmula de área de pixel **diferente e mais simples** é usada em `src/utils/geo_stats.py::build_pixel_area_array()` (usada pelas Fases 4/5, ver `potential_analysis.md`/`lcoe_modeling.md`). **Não confirmado nesta leitura** se as duas fórmulas produzem resultados numericamente equivalentes (a da Fase 1 usa uma série de cossenos WGS84 mais elaborada; a das Fases 4/5 não foi lida em detalhe aqui). **Pergunta/ação futura**: vale comparar as duas implementações e decidir se o GeoFREA deve ter uma única função de área geodésica compartilhada entre todas as fases, incluindo Audit?
