# GeoFREA: especificação de correções e padronização de figuras (v2, para Claude Code)

## 0. Como usar este documento

- Código e documentação ficam no repositório `GeoFREA` (exemplos em `docs/figures/`). `GeoFREA_data` é a pasta de dados e saídas (`outputs/<ISO>/.../figures`), não um repositório.
- **Antes de editar qualquer coisa**: leia `docs/figures/inventory.md` e `src/geofrea/viz/mapstyle.py` (comando 56) e o código dos mapas v2 da F5 (comando 60). A infraestrutura nova evolui `mapstyle.py` (renomear ou envolver como `MapFigure`), não cria um segundo módulo paralelo. Não assuma nomes de arquivo ou funções deste documento; eles são descritos por comportamento.
- Nenhuma execução pesada (auditoria sobre dados reais, regeneração de figuras, suíte completa) enquanto a rodada final de um país estiver em curso.
- Saída de figuras: **somente PNG** (decisão do autor). Nada de SVG ou PDF.
- Os exemplos visuais são do Brasil (BRA), mas **toda regra vale para qualquer país**: nada de constantes hardcoded por país (limites, posições de elementos, tamanhos, ticks).
- Prioridades: **P0** = possível erro de resultado (auditar antes de polir figuras); **P1** = padronização estrutural; **P2** = acabamento.
- Cada tarefa tem critério de aceitação. Não marque como concluída sem rodar os países-arquétipo (T-13).
- As decisões do autor estão na seção 4 (já tomadas). Toda escolha nova sem fonte vira opção de config com default e registro em D-core ou no registro da fase, nunca decisão silenciosa.

---

## 1. Diagnóstico por figura (o que foi observado)

| Figura | Problema observado |
|---|---|
| `example_tall`, `example_small` | Elipse fictícia ("XXX", total 1.234,5 GW) em coordenadas aleatórias (Andes e Suíça). Faixa cinza à direita cortando a elipse (camada de contexto truncada) e halo branco fora do contorno. Posição de rosa dos ventos/escala/total **diferente entre as duas** (dentro do quadro vs. fora). Colorbar em "MW per cell" (depende da área da célula) |
| `BRA wind energy density by state` | 7 classes na legenda, só 2 usadas (quebras provavelmente globais, não dos dados). Bolhas vermelhas sobre roxo (baixo contraste); legenda de bolhas 10/100/1000 TWh com bolha enorme que nenhum estado atinge. "no potential" tem o mesmo cinza dos países vizinhos. Denominador do GWh/km² não declarado |
| `capacity_factor_wind` BRA/PRT/IND | Mascarado por elegibilidade sem dizer isso. Cinza "sem potencial" ≈ cinza dos vizinhos/oceano. Limites do colorbar diferem entre países (BRA 0,02–0,38; IND ~0,02–0,31; PRT 0,13–0,40) sem aviso. Regra de clip (extend) não documentada |
| `potential_capacity_density_*` | Escala solar BRA satura em 10 MW/km² (muito amarelo), IND em ~3, PRT ~9: incomparáveis entre países sem aviso. **PRT wind e PRT solar têm padrão espacial quase idêntico** (ver P0) |
| PRT (várias) | Pixelado: ~0,05° ≈ 5,5 km em país pequeno (~3 mil células). Células ultrapassam a costa/fronteira enquanto o contorno é vetorial preciso (efeito escada). Layouts com enorme espaço vazio entre painéis (grade fixa para país alto e estreito) |
| Climate forcing (`BRA_m_access_cm2_*`, `IND_*`) | Título cru com ID interno e "286043 cells". Sem rosa dos ventos/escala/graticule padrão. Colorbar do vento 0,64–1,36 enquanto os dados ficam em ~0,95–1,10: mapa praticamente branco. Temperatura 1–6,7 K com dados em ~2–3 K: baixo contraste. Apenas 1 GCM (ACCESS-CM2) enquanto o framework usa ensemble de 6. Campo é GCM interpolado (~100–200 km) exibido em 0,05°: sugere resolução que não existe |
| `*_eligibility` (BRA/PRT) | Título com "open questions OQ-046 to OQ-049" (jargão interno vazando). Typo no colorbar: "elgible share". Verde = elegível no painel de cima e verde = E1 protected (excluído) no painel de baixo: **mesma cor, significado oposto**. Colorbar contínuo usado para variável categórica. "none" quase branco = fundo |
| `*_aligned_layers` | Painéis pequenos, 12 por figura, ok como QA mas sem layout adaptativo. Land cover (categórico) com colorbar contínuo de códigos ESA. Distância a estrada/rio saturada pelo clip 1–99% (info perdida). Distância a rio com aspecto de ruído. População "per pixel" sem área do pixel |
| `excluded_share_E5/E4` | Escala `Reds` funciona bem para exclusão. Sem escala/rosa, tamanhos e fontes diferentes do resto |
| Nomes de arquivo | `capacity_factor_wind__ref__na__na.png` repetido entre países (colisões: `_1`, `_34cc24`). `__na__na` é ruído |

---

## 2. Tarefas

### T-14 (P0) Auditoria numérica antes de qualquer polimento visual

Figuras bonitas sobre números errados são o pior cenário para uma tese. Criar um script/teste `audit_potential.py` por país que gera um relatório (markdown + JSON):

1. **Wind vs solar em PRT**: a densidade de **capacidade** é, por definição, área elegível × LUF × PD / área da célula; ela **não** depende do recurso (CF). Padrões parecidos entre eólica e solar são esperados onde as máscaras da F3 coincidem, e a razão central esperada é (0,25×50)/(0,15×4,99) ≈ 16,7. O que precisa ser verificado: (a) a razão observada célula a célula e sua distribuição; (b) se a eligible share eólica e a solar diferem onde deveriam (cultivo é excluído para solar e permitido para eólica); se forem idênticas, a share de uma tecnologia está sendo usada para a outra (bug); (c) correlação da densidade de **energia** com o CF da própria tecnologia (aqui o recurso tem de aparecer). Reportar Pearson e Spearman para (b) e (c).
2. **Ponderação por área**: confirmar que totais (GW, TWh) usam a área real da célula (`R²·Δλ·(sin φ2 − sin φ1)`), não contagem de células nem área constante. Em 0,05°, a célula a 33°S tem ~17% menos área que a 5°N (BRA). Reportar o total com e sem ponderação para ver o efeito.
3. **Potencial sem corte de recurso**: BRA eólica 238,5 GW e 345,1 TWh/ano implicam CF médio ≈ 16,5%, porque o potencial técnico inclui toda a terra elegível. Isso é coerente com a definição adotada (potencial técnico sem corte econômico); o corte de recurso já está previsto como `CF_min` pré-registrado (OQ-008, Grupo 4). Aqui: gerar, por país e tecnologia, a **curva de oferta** (GW e TWh acumulados × CF; × LCOE quando a F6 existir) e o total por faixa de CF (<0,15 / 0,15–0,25 / 0,25–0,35 / >0,35). Não introduzir corte nenhum.
4. **Plausibilidade dos totais**: BRA solar 19.188 GW e 31.068 TWh/ano; IND 753 GW; PRT 264,5 GW. Reportar fração elegível, LUF × PD usados e a razão potencial/consumo elétrico nacional (consumo com fonte e ano). A comparação com potenciais publicados é a OQ-057 (Grupo 7); aqui só se registram os números. Conferir que o teto de densidade por país bate com LUF × PD do cenário (esperado no central: solar BRA e PRT 12,5, IND 5,0 MW/km²; eólica BRA e PRT 0,75, IND 0,37 MW/km²) e que os máximos observados (~10, ~9, ~3) ficam abaixo desses tetos por causa da eligible share < 1.
5. **Resolução efetiva por figura**: as figuras de BRA (CF eólico, densidade solar) parecem ter textura bem mais fina que as de PRT (blocos de ~5,5 km). Descobrir de qual grade cada figura sai (0,05° análise vs. camada F2a nativa) e se o pipeline é consistente entre países. Registrar a resolução e a origem do dado no metadado de cada figura (T-05).
6. **Climate forcing**: reportar, por GCM, SSP e janela, média/min/max de razão solar, razão de vento e ΔT por país. Sanidade: BRA solar ratio chega a ~1,07 em SSP1-2.6 2071–2100, maior que em SSP3-7.0 2041–2070. Pode ser real (redução de aerossóis/nuvens no ACCESS-CM2), mas deve ser checado contra os outros GCMs antes de entrar na tese.

Aceitação: relatório gerado para BRA, PRT, IND; itens 1, 2, 4 e 5 com conclusão explícita (ok ou bug); item 3 com curvas e faixas; item 6 com tabela por GCM. Bug encontrado vira OQ e para o polimento visual até ser corrigido.

---

### T-01 (P1) Módulo único de layout de mapa

Criar uma função/classe única (ex.: `MapFigure`) usada por **todos** os mapas: climate forcing, technical potential, overview, layers, eligibility, exemplos. Nenhum script plota mapa por conta própria.

Estrutura fixa (grade de layout, não "melhor canto vazio"):
- **Cabeçalho**: título (negrito) + subtítulo (cinza), alinhados à esquerda.
- **Eixo do mapa**: aspecto calculado a partir do bbox do país (em projeção, ver T-08); tamanho da figura derivado do aspecto, sem espaço morto.
- **Colorbar** à direita, altura igual à do mapa (ou horizontal embaixo se o aspecto for muito largo).
- **Rodapé**: escala (esquerda), caixa de totais (centro/direita), fonte/versão (direita, fonte pequena).
- **Rosa dos ventos de 8 pontas** (decisão do autor), posição fixa no cabeçalho à direita, fora do eixo. Um único estilo em todo o projeto, derivado da lógica já portada do craei-brazil em `mapstyle.py`. Isso substitui a escolha de "canto mais livre" do comando 56: posição fixa dá a mesma diagramação em todos os países.
- Presets de tamanho por destino: `thesis` (largura de página), `article_single` (~90 mm), `article_double` (~180 mm), `slide`. Fontes definidas em pt (não proporcionais ao canvas, hoje variam muito entre figuras).
- Saída: só PNG, 300 dpi no tamanho de impressão.
- Tema (cores, fontes, espessura de linha) em um único arquivo de estilo.

Aceitação: gerar as 20 figuras analisadas; sobreposição elemento×elemento = 0; mesma posição relativa de cada elemento entre BRA, PRT, IND.

---

### T-02 (P1) Política de cores semântica

Problemas: verde significa "elegível" e "excluído (E1 protected)" na mesma figura; vermelho/verde não é seguro para daltonismo; solar quente/eólica fria (proposta do Douglas) **colide** com `Reds` usado para exclusão (elegível = 1 − excluído, mesma família de cor com sentidos opostos).

Decisão do autor (implementar em um único arquivo de paleta versionado; os defaults abaixo valem):
- **Solar** (CF, densidade, elegibilidade solar): `YlOrBr`, truncado para começar em ~15% (não branco, para não se confundir com o mar branco).
- **Eólica**: `GnBu` (ou `PuBuGn`), mesma regra de truncamento.
- **Exclusão (excluded share)**: `Reds`, **somente** nas figuras de diagnóstico (layers/F3), nunca ao lado de mapas colorizados por tecnologia na mesma figura.
- **Classes dominantes (E1–E6)**: paleta qualitativa segura para daltonismo (Okabe–Ito ou similar), sem verde/vermelho; "none" com cor distinguível do fundo (ou padrão hachurado).
- **Climate forcing**: divergente centrado em 1,0 (razões) ou 0 (Δ%) — `RdBu`/`BrBG`; temperatura sequencial `YlOrRd`/`magma`.
- Não usar `viridis` para solar e eólica ao mesmo tempo (hoje ambas usam, indistinguíveis).
- Tudo como mapa lógico `variável → (cmap, norm)` em um lugar só.

Aceitação: a mesma cor nunca aparece com significados diferentes na mesma figura; teste com simulador de daltonismo (deuteranopia/protanopia).

---

### T-03 (P1) Escalas e normalização

- Regra explícita e configurável de limites: `fixed` (físico, ex.: CF 0–0,5), `percentile` (ex.: 2–98) ou `shared` (compartilhado entre países/cenários). Qualquer clip aparece no subtítulo/legenda (ex.: "escala truncada em 10 MW/km²") e com `extend` coerente.
- **Cross-country**: modo `scale_scope = per_country | shared_across_countries`. CF usa escala `fixed` por tecnologia, igual nos três países (solar 0,10–0,25; eólica 0–0,60, com `extend`). Densidades usam `per_country` por padrão e `shared` nas figuras de comparação entre países. O modo fica no metadado e no subtítulo quando houver clip.
- **Entre cenários** (restrictive/central/permissive; SSPs/janelas): escala compartilhada obrigatória em small-multiples.
- Normas não lineares quando necessário (`log`, `sqrt`, `PowerNorm`): distância a estrada/grid/rio hoje fica toda saturada exceto na Amazônia.
- Climate forcing: limites **simétricos e baseados nos dados** (percentil dos valores do conjunto SSP×janela, não limite global enorme); mostrar em Δ% em vez de razão ("+3%" é mais legível que "1,03").
- Unidades e terminologia únicas: preferir `MW/km²` a `MW per cell` (depende de área/latitude); CF adimensional (0–1) ou em %; declarar se CF é DC ou AC.

---

### T-04 (P1) Títulos, rótulos, idioma

- Título sucinto: `País · Tecnologia · Variável`; subtítulo: `Cenário · Clima (· SSP · janela)`. Usar nome do país (por config/idioma), não só ISO3, nas figuras de tese.
- Proibido: IDs internos (OQ-046…, nomes de modelo crus como `m_access_cm2_ssp370_2041_2070`), contagem de células no título.
- Corrigir typo "elgible" → "eligible" (grep global por typos em rótulos).
- Idioma configurável (`en`/`pt`) para todos os rótulos.
- Legenda de classes (E1–E6) com **patches discretos nomeados**, não colorbar. Land cover ESA com legenda de classes com nomes (Tree cover, Cropland, Built-up, …).
- Caixa de totais padronizada: `Total: X GW · Y TWh/ano · CF médio Z · área elegível W km²`.

---

### T-05 (P1) Nomenclatura de arquivos e metadados

- Padrão: `{ISO3}_{fase}_{variavel}_{tecnologia}_{cenario}_{clima}.{ext}`; omitir campos não aplicáveis (nunca `na`), ex.: `BRA_F3_excluded-share_E5-land-cover_wind.png`, `BRA_F4_forcing_ACCESS-CM2_SSP3-7.0_2041-2070.png`, `PRT_F5_capacity-factor_wind_central_ref.png`.
- ISO3 sempre no nome (hoje 3 países geram o mesmo nome e colidem).
- Slugs legíveis, sem hash.
- Metadado embutido no PNG (tEXt): hash do commit, hash da config, data, grade/resolução, fonte dos dados, escala (`fixed/percentile/shared`) e limites usados. **Sem JSON sidecar por figura** (excesso de arquivos); no máximo um `figures_index.json` por pasta, registrado como artefato.
- Os nomes novos entram pelos `produces` das fases e pela regeneração normal; as figuras antigas vão para `archive/` (sem apagar). Não criar script de renomear arquivos legados. Atualizar referências em `docs/` que apontem para nomes antigos.

---

### T-06 (P1, foco) Pixelização e resolução — robustez para qualquer país

Princípio: **não mascarar a resolução real com suavização/interpolação**; melhorar a apresentação honestamente.

1. **Clipping**: recortar o raster pelo polígono do país na renderização (clip path/máscara por cobertura fracionária) para que a borda/costa seja nítida; hoje as células ultrapassam o contorno vetorial.
2. **Resolução de apresentação separada da análise**: manter a grade de análise fixa (0,05°) para comparabilidade (RQ1/RQ5), mas renderizar camadas descritivas (CF, eligible share, camadas F2a) na resolução nativa quando existir. Rotular claramente qual é qual.
3. **Grade de análise não muda** (decisão do autor): 0,05° em todos os países. Camadas descritivas são desenhadas na resolução nativa em que existem; mapas de resultado da análise (potencial, CF por célula de análise) ficam em 0,05°, com a resolução declarada no subtítulo. Grade adaptativa para análise fica fora deste trabalho (teste de sensibilidade de resolução fica registrado como OQ para depois).
4. Evitar *moiré/linhas finas*: `pcolormesh/imshow` com `interpolation='nearest'`, `antialiased=False`/`edgecolors='face'` e `rasterized=True`; dpi mínimo definido.
5. Hillshade discreto de fundo (opcional, `terrain_context: true`) para dar leitura espacial em países pequenos.
6. Países de grade grosseira (poucas células): reduzir borda/linhas, ampliar fonte do contorno e adicionar contorno de unidades administrativas leves.

Aceitação: PRT sem "escada" na costa e na fronteira; o mesmo código gera BRA, PRT, IND e os arquétipos sintéticos de T-13 sem ajuste manual.

---

### T-07 (P1) Contexto geográfico e áreas sem dado

- Países vizinhos em cinza claro (contexto), oceano em branco ou azul muito claro; **"sem potencial/excluído" com cor própria** (ex.: cinza médio + hachura) e entrada própria na legenda. Hoje os dois cinzas quase se confundem.
- Inset localizador: só na figura de overview de cada país (decisão do autor), `locator_inset: auto` com esse comportamento. Vizinhos recortados por um buffer de ~2–3° em volta do país.
- Fonte única para fronteiras: a geometria contígua do GADM 4.1 (comando 55), com o rodapé curto "Boundaries: GADM 4.1, illustrative" (L-047).
- Ilhas distantes já são descartadas pela regra contígua. Países que cruzam o antimeridiano ficam fora deste trabalho (OQ para a fase de expansão a outros países).

---

### T-08 (P1) Projeção e área

- Hoje os mapas parecem estar em lat/lon (plate carrée) com barra de escala em km; escala fica errada longe do equador e a forma do país é distorcida.
- Projeção de visualização LAEA centrada no centroide do país (default automático), só para desenhar; reprojeção do raster na renderização por vizinho mais próximo; cálculos de área continuam na fórmula esférica. Preferir `pyproj`/`rasterio` (já dependências) a acrescentar `cartopy`.
- Barra de escala calculada na projeção usada, com comprimento "bonito" (1-2-5 × 10ⁿ) escolhido pela extensão do mapa.
- Manter graticule com rótulos em graus, discretos.

---

### T-09 (P1) Figuras de climate forcing

- Layout igual ao resto (T-01), painéis iguais: ΔSolar (%), ΔVento (%), ΔT (K).
- Título: `País · Forçante climática · SSP · janela vs 1995–2014`; subtítulo com a fonte (GCM ou "média do ensemble de 6 GCMs").
- **Mostrar o ensemble**: mapa da média multimodelo + medida de dispersão/concordância (hachura onde <2/3 dos modelos concordam no sinal, ou mapa do desvio-padrão). Um único GCM só como material suplementar ou como linha "membro".
- Nota de resolução: "campo nativo ~X km, interpolado para 0,05°". Não exibir contagem de células.
- Limites de cor conforme T-03 (simétricos, baseados nos dados, compartilhados entre SSPs de um mesmo país para comparação).
- Figura-resumo por país: grade SSP × janela com escala compartilhada.

---

### T-10 (P1) Figuras de elegibilidade (F3)

- Remover "(open questions OQ-…)" do título; mover para log/metadado.
- Painéis superiores: cores por tecnologia (T-02); inferiores: classes qualitativas com legenda discreta.
- **Definir e documentar "dominante"**: critério (maior share? ordem de precedência E1→E6?) na nota da figura e no código; tratar empates e sobreposição de exclusões.
- Mostrar "share da terra" com denominador declarado (área terrestre total vs. área com dado).
- Layout adaptativo ao aspecto do país (PRT hoje tem grande vazio horizontal): grade 2×2 vs 1×4 conforme razão largura/altura.
- Adicionar figura de contribuição de cada exclusão (barras empilhadas: % da área excluída por E1…E6, por tecnologia), mais informativa para a tese do que só o mapa "dominante".

---

### T-11 (P2) Figuras de camadas alinhadas (F2a) — QA

- Rótulo de unidade correto (população em hab/km², não "por pixel").
- Land cover categórico com legenda de classes; normas não lineares (T-03) para distâncias; indicar quando o clip esconde variação.
- Layout adaptativo (linhas/colunas conforme aspecto) e mesmo layout/estilo do resto.
- Marcar como `diagnostic` (não destinado à tese) ou promover um subconjunto a figura de metodologia.

---

### T-12 (P2) Mapa por estado/unidade administrativa

- Classes de cor por quantis/Jenks **calculadas dos dados do mapa** (ou compartilhadas entre cenários), nunca 7 classes com 5 vazias. Mostrar só as classes existentes ou usar escala contínua.
- Declarar o denominador (GWh/km² sobre área total do estado ou sobre área elegível).
- Bolhas: legenda de tamanhos derivada dos dados (ex.: mínimo/mediana/máximo), contorno claro, cor que contraste com o fundo; ou substituir por mapa + gráfico de barras ranqueado dos estados (mais legível).
- Parametrizar o nível administrativo (ADM1) para qualquer país, com tratamento de países sem ADM1 útil.
- Small-multiple restrictive/central/permissive com escala compartilhada: é a visualização natural do "intervalo de disponibilidade de terra" (U-06).

---

### T-13 (P1) Figuras de exemplo reais + testes de regressão visual

- Em `docs/figures/examples`: substituir elipses por **mapas reais com dados sintéticos** e marca "EXAMPLE – synthetic data" (sem "XXX" nem totais inventados parecidos com resultados reais). Devem ser geradas pelo mesmo `MapFigure` e servir de referência do padrão.
- Conjunto de **países-arquétipo** para teste automático, com geometria real do GADM e dados sintéticos: alto e estreito (PRT, CHL), largo (BRA), compacto (CHE), fragmentado (IDN), minúsculo (LUX). Antimeridiano (FJI, RUS) e territórios distantes (FRA) ficam para a fase de expansão. As geometrias ficam como fixtures pequenas (simplificadas) no repositório de testes.
- Teste: gera todos os tipos de figura (densidade, CF, forçante, elegibilidade, estado) para cada arquétipo e verifica: sem sobreposição de elementos, sem texto cortado, aspecto sem espaço morto, escala/rosa na posição padrão; imagem-referência (golden) com tolerância.
- CI/`make figures-check`.

---

### T-15 (P1/P2) Figuras novas recomendadas

1. **Curvas de oferta** (potencial acumulado × CF e × LCOE) por país/tecnologia/cenário de terra — resposta direta a RQ1/RQ2 e muito mais defensável que um número total.
2. **Painel de comparação entre países** (BRA, PRT, IND) com escala compartilhada e mesmas métricas (RQ5).
3. **Faixa de disponibilidade de terra** (restrictive–central–permissive) como barras de intervalo.
4. **Δ do potencial/CF por SSP×janela** (mapa e total), conectando F4→F5 (RQ3).
5. **Validação externa** (RO5): fica para a F7b. Não fazer agora.
Itens 1 (só × CF por enquanto), 2, 3 e 4 entram neste trabalho; 1 × LCOE entra depois da F6.

---

## 3. Ordem de execução sugerida

1. **T-14** (auditoria; pode invalidar figuras).
2. **T-01, T-02, T-03, T-04, T-05** juntos (infraestrutura de figura).
3. **T-08, T-06, T-07** (projeção, resolução, contexto).
4. **T-09, T-10, T-12, T-11** (migrar cada família de figuras para o novo módulo).
5. **T-13** (exemplos + testes), depois **T-15**.

## 4. Decisões do autor (tomadas)

1. Paleta: solar `YlOrBr`, eólica `GnBu`, exclusão `Reds` só em figuras de diagnóstico, classes E1–E6 em Okabe-Ito; climate forcing divergente (`RdBu`/`BrBG`) e temperatura `YlOrRd`.
2. Rosa dos ventos de 8 pontas, posição fixa no cabeçalho; inset localizador só no overview.
3. Sem corte de recurso no potencial técnico; curvas de oferta e faixas de CF; o corte é o `CF_min` do Grupo 4.
4. Grade de análise fixa em 0,05°; resolução nativa só para camadas descritivas.
5. Escala compartilhada entre países nas figuras de comparação; CF com escala fixa por tecnologia; demais por país.
6. Climate forcing: média do ensemble (6 GCMs solar e temperatura; 5 vento) com hachura de concordância de sinal (< 2/3); membros individuais como suplementares.
7. Saída só PNG.
