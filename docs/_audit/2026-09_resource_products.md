# Auditoria de fatos — produtos GWA/GSA (vento e solar), verificação de rede + metadados locais

Data: 2026-09-15. Escopo: verificação de rede real (requisições HEAD/metadados, sem baixar nenhum raster completo) contra o padrão de endpoint já usado em `src/geofrea/data_acquisition/fetchers/wind.py`, mais leitura de arquivos locais (`README`/PDF/XML que acompanham os zips já baixados). Objetivo: fechar D10(3) com dado verificado antes de definir o protocolo de CF eólico. Nenhum commit foi feito.

Anexos consultados: `CLAUDE.md`, `docs/_audit/2026-09_F1-F2b.md` (auditoria anterior desta mesma série).

**⚠️ Ponto a validar — identificação de "D10(3)"**: busca em todo `docs/` não encontrou nenhum item rotulado literalmente `D10` com um subitem `(3)` que trate de eólica/CF/GWA. O único `D10` existente no repositório é `docs/architecture/suitability_criteria_audit.md` §7 (linha 203: "`os.environ` mutado em import-time"), que é sobre um achado de auditoria do legado sem relação com produtos GWA/CF eólico. Não assumi correspondência — prossegui com o conteúdo literal das Ações 2-4, autocontidas.

---

## 1. Achado estrutural prévio, necessário para interpretar a Seção 2

O endpoint `https://globalwindatlas.info/api/gis/country/{ISO3}/{parametro}/{altura}` usado por `fetchers/wind.py` **não valida a combinação parâmetro/altura antes de redirecionar** — verificado ao vivo nesta sessão: uma requisição com um nome de parâmetro inventado (`totally-fake-parameter-xyz`) e uma altura inexistente (`9999`) retornam **302 Found** exatamente como uma combinação real, sempre construindo `Location: https://gwa.cdn.nazkamapps.com/country_tifs_v4/{ISO3}_{parametro}_{altura}m.tif` sem checar se o arquivo existe no CDN de destino.

A existência real só é decidida no CDN (`gwa.cdn.nazkamapps.com`, backend Amazon S3): **200 OK** = arquivo existe; **403 Forbidden** = chave inexistente no bucket S3 (comportamento padrão do S3 para objeto ausente quando listagem está desabilitada — não é um 404 convencional, mas indica ausência). Por isso, todo código HTTP registrado na Seção 2 é o **código final após seguir o redirect até o CDN**, não o 302 da API (que seria sempre 302, e portanto sem valor informativo por si só).

---

## 2. Tabela produto × altura — GWA, PRT (código HTTP final no CDN)

Todas as células abaixo são o resultado de uma requisição `HEAD` real (curl `-I`), seguindo o redirect (`-L`) até o CDN, contra `PRT` (Portugal), 2026-09-15. Nenhum raster foi baixado por completo — apenas cabeçalhos HTTP.

| Produto | 10m | 50m | 100m | 150m | 200m | (sem altura) |
|---|---|---|---|---|---|---|
| `wind-speed` | 200 | 200 | 200 | 200 | 200 | — |
| `power-density` | 200 | 200 | 200 | 200 | 200 | — |
| `capacity-factor_IEC1` | 403 | 403 | 403 | 403 | 403 | **200** |
| `capacity-factor_IEC2` | 403 | 403 | 403 | 403 | 403 | **200** |
| `capacity-factor_IEC3` | 403 | 403 | 403 | 403 | 403 | **200** |
| `combined-Weibull-A` | 200 | 200 | 200 | 200 | 200 | — |
| `combined-Weibull-k` | 200 | 200 | 200 | 200 | 200 | — |
| `air-density` | 200 | 200 | 200 | 200 | 200 | — |

### Leitura da tabela, item por item da Ação 2

- **Alturas existentes em `wind-speed` e `power-density`**: as 5 alturas documentadas no docstring de `fetchers/wind.py` (10/50/100/150/200 m) **todas existem** para os dois produtos, confirmado no CDN (200 em todas as 10 células). `fetchers/wind.py` hoje só busca `wind-speed` a 100m (`_DEFAULT_HEIGHT_M = 100`) — as outras 4 alturas estão disponíveis mas não são buscadas.
- **`capacity-factor_IEC1/2/3`: existe, mas NÃO por altura**. A requisição height-qualificada (`.../capacity-factor_IEC1/100`, etc.) redireciona para uma URL de CDN que **não existe** (403 em todas as 15 combinações produto×altura testadas). Só a requisição **sem sufixo de altura** (`.../capacity-factor_IEC1`, sem `/100` no final) redireciona para um arquivo que **existe de fato** (`PRT_capacity-factor_IEC1.tif`, 200 OK, sem `_100m` ou qualquer sufixo de altura no nome do arquivo). **Em qual altura**: não determinável a partir do endpoint HTTP nem do nome do arquivo — o arquivo não carrega altura no path nem no filename. Determinar a altura de referência exigiria inspecionar os metadados internos do GeoTIFF (tags EXIF/GDAL) do arquivo real, o que não foi feito (instrução explícita: não baixar rasters completos). **Registrado como não verificado, sem estimar.**
- **Weibull A/k**: existem, com o nome de parâmetro `combined-Weibull-A`/`combined-Weibull-k` (não `weibull-A`/`weibull-k` — essas duas variantes de nome também retornam 302 na API, mas **403 no CDN**, confirmando que são nomes de parâmetro inválidos que a API aceita cegamente sem validar). `combined-Weibull-A`/`combined-Weibull-k` existem nas 5 alturas documentadas (200 em todas).
- **`air-density`**: não pedido explicitamente na Ação 2, mas testado como parte da varredura por já aparecer citado no docstring de `fetchers/wind.py` como produto irmão na mesma raiz de API — existe nas 5 alturas (200 em todas). Registrado por completude, sem uso implicado.

---

## 3. Período de referência e configuração do sistema PV assumida pelo PVOUT (GSA) e período de referência (GWA)

### 3.1 GSA — Global Solar Atlas / PVOUT: encontrado localmente

Fonte: `database/raw/solar_potential/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif.pdf` e seu par `PVOUT.tif.xml` (metadado ISO 19115:2003/19139, texto idêntico nos dois formatos — verificado por grep cruzado). Este é exatamente o arquivo já em uso pelo GeoFREA (`data_acquisition/local_layers.py::_SOLAR_PVOUT_RELPATH`).

| Campo | Conteúdo literal do metadado |
|---|---|
| **Título** | "Longterm average of daily totals of potential photovoltaic electricity production – Global Solar Atlas" |
| **Data de publicação** | 2025-04 |
| **Período de referência declarado** | "covering the period from 1994/1999/2005/2007/2018/2019 (depending on the region) to 2024" — **início do período varia por região** (não um único ano-base global), fim comum em 2024. |
| **Configuração do sistema PV assumida** | "Assessment of PV power production potential for a **free standing PV power plant** with **c-Si modules** mounted at **optimum tilt** to maximize monthly PV production." — usina fotovoltaica de solo (não integrada a edifício), módulos de silício cristalino, inclinação fixa otimizada para maximizar a produção mensal (não rastreador solar/tracking, não inclinação horizontal fixa única). |
| **Entradas principais do modelo** | "Global irradiation at optimum tilt (GTI) and air temperature (TEMP)" — GTI (não GHI puro) + temperatura do ar, algoritmos Solargis. |
| **Resolução espacial declarada** | 30 arc-sec (~30 arcsegundos, ≈0.9 km no equador). |
| **Extensão geográfica** | -180 a 180° lon, -60 a 65° lat (cobertura quase global, exclui extremos polares). |
| **Fonte/licença** | Solargis (autor/originador) para o World Bank/ESMAP (dono), CC BY 4.0 com cláusula de arbitragem adicional. |

### 3.2 GWA — Global Wind Atlas: não encontrado localmente

Busca no diretório local de vento (`database/raw/wind_potential/`) encontrou **só arquivos `.tif` brutos** (3 arquivos, todos de um teste anterior para a Rússia — `RUS_wind-speed_{50,100,200}m.tif`), **sem nenhum arquivo `README`, `.pdf`, `.xml` ou metadado sidecar de qualquer tipo** acompanhando-os — confirmado por listagem completa do diretório. Busca mais ampla em todo `D:\Douglas\DOUTORADO\` por qualquer arquivo relacionado a "GWA"/"globalwindatlas"/documentação de vento também não encontrou nada. Isso é consistente com o comportamento do próprio fetcher: `fetchers/wind.py::fetch_wind()` salva só o GeoTIFF bruto retornado pelo CDN (`dest_path.write_bytes(resp.content)`), sem baixar nenhum metadado adicional — a API do GWA não parece expor um endpoint de metadado/documentação separado do próprio raster (a checagem HTTP da Seção 2 não revelou nenhum endpoint de metadado, só o padrão `{param}/{altura}` de dados).

**Período de referência do GWA: não encontrado localmente, sem estimar.**

---

**Critério de conclusão**: tabela produto × altura (Seção 2) com código HTTP em cada célula ✓ (48 células preenchidas: 8 produtos × 5 alturas + 3 variantes sem altura); período de referência de GSA preenchido (Seção 3.1, com o texto literal do metadado) ✓; período de referência de GWA marcado "não encontrado localmente" (Seção 3.2) ✓. Único arquivo criado é este (`docs/_audit/2026-09_resource_products.md`); nenhum raster foi baixado por completo; nenhum arquivo de `src/`, `config/`, `tests/` ou `database/raw/` foi modificado.
