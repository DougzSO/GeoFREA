Corresponde à Fase 2a — Grid Alignment do GeoWorld legado.

# Grid Alignment — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/grid_aligner.py` (`GridAligner` + funções module-level, 1213 linhas, lidas por completo em 2026-08-19). Cross-referenciado com `docs/TASKS.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: reprojetar todos os datasets brutos heterogêneos (rasters e vetores) para uma grade de referência única (mesmo transform/dimensões/CRS), com correspondência topológica estrita — pré-requisito para qualquer operação pixel-a-pixel nas fases seguintes.

**Inputs** (`run(**kwargs)`, L920-1145): caminhos de elevação, slope, solar, múltiplas camadas de vento (50/100/200m), tiles de land cover, população, rede elétrica, estradas, lagos, rios, sismicidade, `plants_df` — todos brutos, em seus CRS/resoluções originais.

**Outputs** (`aligned: Dict[str, Optional[Path]]`, um GeoTIFF por camada em `data/processed/{ISO3}/{ISO3}_{layer}_aligned.tif`):
- `elevation`, `slope`, `solar`, `seismic`, `population` — reprojetados via `_reproject_to_grid()` (bilinear, float32).
- `wind` — combinação ponderada por AHP de até 3 alturas (50/100/200m).
- `land_cover` — mosaico de tiles ESA WorldCover (nearest-neighbour, uint8).
- `grid`, `roads` — raster de distância geodésica a feições lineares (km, float32, clipado a `max_dist_km`).
- `lakes` — máscara binária (uint8).
- `rivers` — raster de distância geodésica a rios (km, clipado a 50 km — ver §c).
- `plants` — máscara binária de localização de usinas existentes.
- `{ISO3}_grid_metadata.json` (CRS, resolução, transform, dimensões, `n_valid_pixels`).

**CRS de saída**: sempre `EPSG:4326` (`build_reference_grid()`, L112). Resolução: `settings.yaml`'s `geospatial.resolutions.suitability`, podendo ser `"adaptive"` (calculada dinamicamente, ver §b) ou um valor fixo em graus.

---

## b. Fórmulas e localização exata

| # | Fórmula | Linha |
|---|---|---|
| 1 | **Grade de referência**: bounds arredondados para múltiplos da resolução (`floor`/`ceil`), `width/height = round((max−min)/res)` | `build_reference_grid()`, L103-113 |
| 2 | **Pesos AHP (método do autovetor principal)**: `weights = mean(matrix/col_sum(matrix), axis=1)`; `λmax = mean(matrix@weights / weights)`; `CI=(λmax−n)/(n−1)`; `RC=CI/RI(n)` (tabela `AHP_RANDOM_INDEX`); se `RC > 0.10`, cai para pesos uniformes | `_compute_ahp_weights()`, L268-287; uso em `_combine_wind_layers()`, L349-358 |
| 3 | **Combinação de camadas de vento**: `resultado = Σ(camada_i × peso_i) / Σ(peso_i)` por pixel, ponderação AHP (3 alturas) ou uniforme (`1/n` se RC>0.10 ou menos de 3 alturas presentes) | `_combine_wind_layers()`, L368-424 |
| 4 | **Distância geodésica isotrópica (WGS84, aproximação de Bowring)**: `dist_transform_edt` (scipy, em pixels) × `sqrt(res_x·lon_km_deg × res_y·lat_km_deg)`, onde `lat_km_deg`/`lon_km_deg` usam série de cossenos em função da latitude central da grade | `_calculate_wgs84_isotropic_distance()`, L550-594 |
| 5 | **Resolução adaptativa**: `área_km² = (maxx−minx)·lon_km × (maxy−miny)·lat_km`; `res_computada = sqrt(área/target_pixels) / sqrt(lat_km·lon_km)`, clipada a `[min_deg, max_deg]` | `GridAligner.run()`, L947-971 |

Unidades: distâncias em km (rios/estradas/rede), resolução em graus decimais, CRS sempre EPSG:4326.

**⚠️ Achado novo (não documentado em nenhum BLOCKER/REFACTOR existente)**: a fórmula de correção geodésica por latitude (série de cossenos Bowring) aparece em **três variantes truncadas diferentes**, em dois arquivos distintos, nunca centralizada:
- `data_auditor.py::_row_area_km2()` (Fase 1): 4 termos em `lat_km` (até `cos(6φ)`), 3 termos em `lon_km` (até `cos(5φ)`) — a versão mais completa.
- `grid_aligner.py::_calculate_wgs84_isotropic_distance()` (L579-588, usado para distância a rios/estradas/rede): 3 termos em `lat_km` (até `cos(4φ)`), 3 termos em `lon_km` (até `cos(5φ)`) — falta o termo `cos(6φ)`.
- `grid_aligner.py::run()`, cálculo de resolução adaptativa (L950-956): só 2 termos em `lat_km` (até `cos(2φ)`), 2 termos em `lon_km` (até `cos(3φ)`) — a mais truncada das três.

Os erros introduzidos por essas truncações são pequenos (a magnitude dos termos de ordem superior é ~10⁻³–10⁻⁴ do termo principal), mas é uma duplicação de fórmula científica não centralizada — ver §e.1.

---

## c. Parâmetros hardcoded

| # | Local | Valor | Status |
|---|---|---|---|
| 1 | `adaptive_cfg` fallback (L910-916) | `target_pixels=50000, min_deg=0.001, max_deg=0.05` | Fallback se `settings.yaml`'s `geospatial.resolutions.adaptive` ausente — **INVAR-003 confirmado aqui, ver §d** |
| 2 | `self.resolution = 0.01` (L918) | Valor inicial antes do `run()` recalcular | Nunca usado de fato (sempre sobrescrito) |
| 3 | `max_dist_km=100.0` (L603, default de `_align_linear_features`) | Distância máxima codificada para grid/roads | Usado para `grid` e `roads` (ambos chamam sem override) |
| 4 | Clipe de distância de rios, **inline** `np.clip(dist_km, 0, 50)` (L784) | `50` km | **Divergência não documentada**: rios usam um limite hardcoded diferente (50 km) do parâmetro `max_dist_km` (100 km) usado por grid/roads — não é um bug per se (pode ser intencional, rios sendo mais "locais"), mas não está exposto como parâmetro nomeado consistente com o de `_align_linear_features` |
| 5 | `buffer_deg=0.05` (L141, default de `_load_and_clip_vector_data`) | Buffer do bbox de recorte vetorial | Usado como default; `_align_linear_features` sobrescreve para `0.01` (L620) |
| 6 | `tolerance = abs(transform.a) * 0.5` (L634, L766) | Tolerância de simplificação geométrica (meio pixel) | Repetido em dois lugares (`_align_linear_features`, `_align_rivers`), não centralizado |
| 7 | Consistency Ratio de AHP, `0.10` (L353) | Limiar de Saaty para aceitar a matriz de comparação pareada | Padrão da literatura (Saaty 1980), consistente com `memory/04-algorithms.md` |
| 8 | `_CHUNK_ROWS`-equivalente para land cover, `step = 8192` (não presente aqui — nota: land cover mosaic não usa chunking por linha, processa tile inteiro) | — | N/A, não se aplica a este módulo |

---

## d. Cross-check de BLOCKERs/INVARs já resolvidos

| Item | Confirmado presente? | Evidência |
|---|---|---|
| **INVAR-003** (`grid_aligner.py:910,960,968-969` — fallback silencioso P1, latente, baixa severidade) | **Confirmado ainda ABERTO** (não corrigido, apenas confirmado presente) | L910-916 (`adaptive_cfg` fallback dict), L960 (`self.adaptive_cfg.get("target_pixels", 50000)`), L968-969 (`.get("min_deg", 0.001)`/`.get("max_deg", 0.05)`) — nenhum desses `.get()` emite warning se a chave estiver ausente de `settings.yaml`, ao contrário do padrão já aplicado em `data_auditor.py` para `resolution_tolerance` (INVAR-002). Números de linha batem exatamente com o que `TASKS.md` registra. |
| REFACTOR-005 (uso de `safe_raster_write`) | **Sim, 100% adotado neste módulo** | 7 call sites confirmados: `_reproject_to_grid` (L258), `_combine_wind_layers` (L452), `_mosaic_land_cover` (L540), `_align_linear_features` (L673), `_align_lakes` (L737), `_align_rivers` (L798), `_align_plants` (L876) — bate com a contagem "7 call sites" de `code-duplication.md` §4a. |
| Item 5 / Item 11 (comentários `✅ Item 5`/`✅ Item 11` no código, L30-32, L34-36, L479-480) | **Sim, já corrigidos** | Import de `pandas` ausente e import duplicado de `rasterio` — ambos corrigidos, com comentários explicativos deixados no código (não removidos após a correção, ao contrário da convenção usual do projeto — nota estilística, não um bug). |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **Três variantes truncadas da mesma fórmula geodésica** (§b, achado novo): `data_auditor.py`, e duas funções em `grid_aligner.py`, implementam versões com números de termos diferentes da correção Bowring por latitude. **Pergunta**: no GeoFREA, vale centralizar numa única função (`src/utils/geodesy.py`?) usada por todas as fases que precisam de área/distância geodésica, eliminando a divergência de precisão entre elas? Isso incluiria também a fórmula usada em `build_pixel_area_array()` (Fases 4/5, não lida em detalhe nesta auditoria — candidato a comparação futura).
2. **Limite de distância de rios (50 km) hardcoded, diferente do de grid/roads (100 km)**: não há explicação no código sobre por que rios têm um raio de busca menor. **Pergunta**: isso é uma decisão metodológica deliberada (rios "contam" apenas localmente) ou um valor arbitrário que deveria ser unificado/parametrizado?
3. **Resolução adaptativa**: `target_pixels=50000` (tamanho-alvo da grade, controlando o trade-off entre performance e granularidade espacial) não tem justificativa documentada em `parameters.json`/`DECISIONS.md`. **Pergunta**: esse valor foi calibrado empiricamente (ex. tempo de execução aceitável) ou é uma escolha arbitrária que poderia mudar no GeoFREA?
4. **AHP para combinação de alturas de vento**: o `WIND_AHP_MATRIX` (matriz de comparação pareada Saaty) não foi lido em detalhe nesta auditoria (vive em `src/core/constants.py`). **Pergunta futura**: qual a justificativa dos julgamentos pareados específicos usados nessa matriz (por que 50m/100m/200m recebem esses pesos relativos)?
