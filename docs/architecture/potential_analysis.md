Corresponde à Fase 4 — Potential do GeoWorld legado.

# Potential Analysis — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/potential_calculator.py` (`PotentialCalculator`, 1020 linhas, lidas por completo em 2026-08-19). Cross-referenciado com `docs/analysis/analysis-potential_calculator.md` (congelado 2026-08-11, HEAD `6d59120`) e `docs/TASKS.md`/`docs/archive/backlog-full-2026-08.md` (estado em 2026-08-19, HEAD `fc7b43d`). Números de linha abaixo são da leitura atual (2026-08-19); podem divergir em ±poucas linhas do documento congelado.

---

## a. Propósito e I/O

**Propósito**: converter a superfície de suitability TOPSIS da Fase 3 em capacidade instalável (GW) e geração anual (TWh/ano) por tecnologia (solar/wind/biomass) × cenário (optimistic/balanced/conservative), com estatísticas zonais por região administrativa.

**Inputs**:
- GeoTIFF de suitability TOPSIS da Fase 3, localizado via `find_suitability_tif(suitability_dir, tech, country_code, allow_owa_fallback=False)` (`potential_calculator.py:188-193`) — **estritamente TOPSIS, nunca OWA** (única das três fases 4/5/6 com essa restrição — comentário explícito cita BLOCKER-006).
- `country_params: CountryParams | None`, mesclado via `build_tech_params(cfg.system, country_params)` (L176) → `self.tech_params[tech]` com `power_density_mw_km2`, `land_use_factor`, `capacity_factor`, `hours_year`, `thresholds` (dict por cenário).
- `mainland_gdf`, `context_gdf`, admin boundaries (via `styler.load_admin_boundaries`).
- CRS: `EPSG:4326` (herdado do raster de referência; validado contra os demais rasters via `validate_raster_crs`/`validate_raster_shape`, L217-219).

**Outputs** (por tech × cenário, `scenario_results[scenario]`, L542-553):
- `threshold` (float), `n_pixels` (int), `area_km2`, `area_eff_km2`, `capacity_mw`, `capacity_gw`, `generation_gwh`, `generation_twh`.
- `cap_map` (ndarray, MW/pixel) e `zonal_df` (DataFrame) — **presentes apenas no dict em memória**, removidos antes da serialização (`_DROP_KEYS = frozenset({"cap_map", "zonal_df"})`, L340) e **não** persistidos em `result.pkl`.
- GeoTIFF de máscara suitable por tech/cenário (uint8, 255=suitable/0=not, nodata=0): `outputs/{ISO3}/potential/tifs/{ISO3}_{tech}_suitable_{scenario}.tif` (L488-511).
- CSV zonal por tech/cenário: `outputs/{ISO3}/potential/data/{ISO3}_{tech}_{scenario}_zonal.csv`, colunas incluindo `capacity_mw_sum`, `generation_gwh`, e (desde BLOCKER-003) `area_km2_sum` (L513-540).
- Validado contra `PotentialResult` (Pydantic v2, `src/core/schemas.py`) antes de retornar (L356-357).

---

## b. Fórmulas e localização exata (código legado)

Todas em `_run_technology()`, loop por cenário, `potential_calculator.py:438-553`:

| # | Fórmula | Linha |
|---|---|---|
| 1 | `apt_mask = np.isfinite(suit_arr) & (suit_arr >= threshold)` | L440 |
| 2 | `area_apt = float(area_arr[apt_mask].sum())` — área geodésica via `build_pixel_area_array(transform, height, width)` (canônico, L426) | L462 |
| 3 | `area_eff = area_apt * params["land_use_factor"]` | L463 |
| 4 | `cap_mw = area_eff * params["power_density_mw_km2"]` | L464 |
| 5 | `cap_gw = cap_mw / 1_000.0` | L465 |
| 6 | `gen_gwh = cap_mw * params["capacity_factor"] * params["hours_year"] / 1_000.0` | L466-469 |
| 7 | `gen_twh = gen_gwh / 1_000.0` | L470 |
| 8 | `cap_map[apt_mask] = area_arr[apt_mask] * land_use_factor * power_density_mw_km2` (mapa por pixel, MW) | L481-486 |
| 9 | `threshold = params["thresholds"].get(scenario, FALLBACK_SUITABILITY_THRESHOLD)` | L439 |

Unidades: área em km² (geodésica, corrigida por latitude via `build_pixel_area_array`), potência em MW/GW, energia em GWh/TWh por ano. CRS EPSG:4326 para os rasters de entrada; a correção de área é feita numericamente (não por reprojeção).

---

## c. Parâmetros hardcoded

### Já migrados para config (confirmado nesta leitura)
- `threshold` fallback (L439): usa `FALLBACK_SUITABILITY_THRESHOLD` de `src.core.constants` — **não** é mais um literal `0.60` bare. Corresponde ao item #3 de `code-duplication.md` §3, confirmado fixed (mesmo achado documentado em `analysis-potential_calculator.md` §1 item 1).
- `power_density_mw_km2`, `land_use_factor`, `capacity_factor`, `hours_year`, `thresholds` por cenário: todos vêm de `parameters.json` via `build_tech_params()` — não hardcoded no módulo.

### Ainda hardcoded (sem correspondência científica — cosméticos, não candidatos a migração)
- `SCENARIO_COLORS`, `SCENARIO_ALPHA` (L92-102) — cores/alpha de plot por cenário.
- `_TECH_REPORT_LABELS` (L104-108) — rótulos de exibição.
- `_PANEL_GAP_PX=8`, `_TITLE_FRAC=0.06`, `_FOOTER_FRAC=0.025`, `_TITLE_MIN_PX=80`, `_FOOTER_MIN_PX=30` (L110-114) — layout do painel de comparação PNG.
- `SCENARIOS = ["optimistic", "balanced", "conservative"]` (L90) — lista estrutural, espelha `settings.yaml`'s `potential.scenarios`; não é um valor científico per se, mas define quais cenários existem — mudar isso exige tocar código, não só config.

Nenhum parâmetro científico hardcoded remanescente foi encontrado neste módulo (consistente com `analysis-potential_calculator.md`, que já havia confirmado a correção do `0.60`).

---

## d. Cross-check de BLOCKERs já resolvidos

| BLOCKER | Confirmado presente? | Evidência |
|---|---|---|
| BLOCKER-003 (área geodésica real por região, `area_km2_sum` no CSV zonal) | **Sim** | L525-536: segunda passada de `zonal_stats_raster(area_arr, apt_mask, ...)` computa `area_km2_sum` por admin e faz merge no `zonal_df` antes do `to_csv`; comentário no código cita BLOCKER-003 explicitamente. |
| BLOCKER-006 (resolução centralizada TOPSIS/OWA via `raster_io.find_suitability_tif`) | **Sim** | L188-193, com `allow_owa_fallback=False` e comentário citando BLOCKER-006 — Fase 4 nunca usou OWA, comportamento estrito preservado. |
| REFACTOR-005 (escrita GeoTIFF via `safe_raster_write`) | **Sim** | L495-511, `with safe_raster_write(tif_out, ...) as dst:` para a máscara suitable. |
| Fix "dup_geo_area" (usar sempre `build_pixel_area_array()` canônico) | **Sim** | L425-426, comentário `✅ FIX (dup_geo_area)` explícito, chama `src.utils.geo_stats.build_pixel_area_array()`. |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **Docstring desatualizada sobre `use_owa`** (`analysis-potential_calculator.md` §2b, ainda presente): o docstring do módulo (L22-24) afirma que `_run_technology` aceita `use_owa=True` "reserved for future scenario-specific runs; not yet wired in the orchestrator" — mas `_run_technology`'s assinatura real (L383-395) **não tem** esse parâmetro, e nenhum código no arquivo referencia `use_owa`. É uma nota aspiracional nunca implementada. **Pergunta**: no GeoFREA, esse recurso (potencial calculado a partir de OWA em vez de só TOPSIS) deve ser (i) implementado de verdade, (ii) descartado explicitamente, ou (iii) mantido como está (TOPSIS-only, sem essa opção)?
2. **`_plot_comparison` relê PNGs do disco no mesmo run** (`analysis-potential_calculator.md` §2c, confirmado ainda presente em L768-775): em vez de receber a imagem/caminho diretamente de onde `_plot_potential_map` acabou de salvar (L563-567), o método reconstrói o caminho esperado independentemente e checa `.exists()`. Baixo risco (mesmo run, artefato cosmético), mas é estruturalmente o mesmo padrão do BUG_07 (reconstrução a partir do disco em vez de usar o que acabou de ser produzido em memória). **Pergunta**: vale a pena, no redesign, evitar esse padrão sistematicamente (passar o objeto/caminho diretamente), ou é aceitável para artefatos puramente cosméticos?
3. **`cap_map`/`zonal_df` nunca persistidos** (L340, `_DROP_KEYS`): a Fase 6 (Results) do legado precisa reconstruir/reler esses valores a partir de outros artefatos (ver BLOCKER-010, D8/D9 em `DECISIONS.md`). **Pergunta**: no GeoFREA, o contrato de saída da Fase Potential deve incluir esses dados por padrão (ex: sempre persistir `area_km2`/`capacity_mw` por pixel, ou pelo menos por zona), eliminando a necessidade de uma fase downstream reconstruir?
4. **Cenários fixos (optimistic/balanced/conservative)**: os offsets de cada cenário vêm de `settings.yaml`'s `potential.scenarios` (Campaign-08 em `TASKS.md`, ainda aberto — deltas `±0.10` sem justificativa documentada). **Pergunta**: os três cenários e seus deltas são uma decisão metodológica fixa, ou candidatos a revisão no GeoFREA?
