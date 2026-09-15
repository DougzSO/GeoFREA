# DECISIONS.md — GeoFREA

Log de decisões arquiteturais e metodológicas do GeoFREA. Append-only: nunca editar ou apagar uma entrada existente — se uma decisão substituir outra, a antiga ganha `Status: Superseded by <data>`, não é removida.

Template de entrada:

## [data] - [nome do módulo]
Tipo: STRUCTURAL_PRESERVE | METHODOLOGY_REVISION | VERIFICATION_UPDATE
Descrição:
Justificativa (se METHODOLOGY_REVISION):
Referência (literatura/discussão, se aplicável):

VERIFICATION_UPDATE — the decision itself is unchanged; only the confidence/verification status of a cited source or value is updated (e.g. a value moves from unverified to independently confirmed).

---

## [2026-08-19] - protected_areas / IUCN exclusion categories
Tipo: STRUCTURAL_PRESERVE
Descrição: compute_protected_areas() (criteria_builder.py) exclui categorias IUCN Ia, Ib e II (score 0.0), aplicado uniformemente a todas as tecnologias e países, confirmado por investigação de código (único call site, sem condicionamento por tech, flag única protected_as_exclusion sem distinção de categoria). O comportamento é documentado no próprio docstring do código desde o commit inicial. GeoFREA herda este comportamento sem alteração.
Justificativa: decisão metodológica de Douglas — preservação e conservação de Parques Nacionais (categoria IUCN II) e demais áreas de proteção estrita (Ia/Ib), visando evitar desmatamento/conversão de uso do solo para instalação de infraestrutura de energia renovável. Esta lógica é aplicada de forma uniforme a todas as tecnologias (solar, eólica, biomassa), não como regra específica de uma tecnologia. Não há citação externa (WDPA/paper) associada à escolha original da categoria II no código legado — esta é uma decisão própria do pesquisador, registrada explicitamente como tal, e não uma herança de norma externa documentada.
Referência (literatura/discussão, se aplicável): nenhuma referência externa — decisão própria do pesquisador, registrada como tal.
Ação de correção: atualizar docs/memory/03-pipeline.md (ou seu sucessor no GeoFREA) para refletir Ia/Ib/II corretamente, eliminando a divergência com o docstring do código.

---

## [2026-08-19] - biomass CAPEX/OPEX/lifetime fallback values
Tipo: METHODOLOGY_REVISION
Descrição: _SA4_DEFAULTS (sensitivity_analyzer.py) e DEFAULT_LCOE_PARAMS (lcoe_calculator.py) divergiam para biomassa: CAPEX 2500 vs 2720, OPEX 100 vs 109, vida útil 30 vs 20 anos. Douglas confirmou que os valores de DEFAULT_LCOE_PARAMS (CAPEX=2720, OPEX=109, vida útil=20 anos, dr=7%) correspondem à fonte IRENA "Renewable Power Generation Costs in 2024" citada no docstring do módulo. Os valores de _SA4_DEFAULTS (2500/100/30anos) são tratados como o duplicado desatualizado/incorreto, sem fonte própria documentada — mesma classe de bug já corrigida uma vez no histórico do GeoWorld (_irena_defaults, duplicação de fatores de capacidade).
Justificativa (se METHODOLOGY_REVISION): consolidar a Fase 8 (Sensitivity Analysis) na mesma fonte econômica canônica da Fase 5 (LCOE), eliminando uma divergência numérica não documentada e potencialmente distorciva (a diferença de vida útil, 30 vs 20 anos, afeta o resultado de LCOE de forma não-trivial).
Fonte: IRENA, Renewable Power Generation Costs in 2024. Confirmação verbal de Douglas nesta sessão (data: 2026-08-19) — NÃO verificada independentemente por mim nem pelo Claude Code via acesso direto ao PDF/tabela primária, já que nenhum dos dois tem acesso geral à web. Se Douglas checar o documento formalmente depois e encontrar divergência, esta entrada deve ser revisada.
Ação de correção para o GeoFREA: consolidar em UMA única fonte de verdade de parâmetros econômicos por tecnologia (parameters.json, seção lcoe_defaults ou equivalente), eliminando a duplicação entre a Fase LCOE e a Fase Sensitivity Analysis. _SA4_DEFAULTS deixa de existir como constante separada — a análise de sensibilidade deve ler os mesmos valores canônicos usados no cálculo de LCOE principal. Todos os valores entram no schema Pydantic com a fonte IRENA 2024 registrada como metadata/comentário.

---

## [2026-08-20] - biomass CAPEX/OPEX/lifetime — verificação da fonte primária
Tipo: VERIFICATION_UPDATE (addendum à entrada de 2026-08-19)
Descrição: Douglas verificou manualmente os valores CAPEX=2720, OPEX=109, vida útil=20 anos, dr=7% contra a tabela primária de IRENA "Renewable Power Generation Costs in 2024". Confirmado como correspondente à fonte citada. Isto substitui o status "não verificado" da entrada de 2026-08-19 — aquela entrada permanece no log (append-only) mas está superada quanto a este ponto específico.
Justificativa (se METHODOLOGY_REVISION): n/a — este addendum não altera a decisão de 2026-08-19 (consolidar em DEFAULT_LCOE_PARAMS), apenas remove a ressalva de não-verificação sobre a fonte.
Fonte: IRENA 2024, verificação manual direta por Douglas em 2026-08-20 (não automatizada, sem acesso do Claude/Claude Code à fonte primária).

---

## [2026-08-20] - biomass parameters restructure (IRENA 2025)
Tipo: METHODOLOGY_REVISION
Descrição: `config/parameters.json` foi reestruturado para ter país como chave de topo (`countries.{PRT,BRA}.discount_rate`, `countries.{PRT,BRA}.technologies.biomass.*`), cada valor-folha envolto no bloco de verification metadata definido em `docs/CONVENTIONS.md`. Apenas o domínio `biomass` foi populado nesta etapa — `solar`/`wind`/outras tecnologias não têm stubs criados ainda (trabalho futuro separado).

Os parâmetros de biomassa foram atualizados de IRENA "Renewable Power Generation Costs in 2024" (fonte da entrada de 2026-08-19) para IRENA "Renewable Power Generation Costs in 2025":
- `capex_usd_per_kw`: 2720 → 3606 USD/kW (mesmo valor para PRT e BRA — IRENA reporta uma figura global, sem quebra por país). Esta **não é** uma atualização direta de edição 2024→2025: o valor 2720 carregado na entrada de 2026-08-19 foi confirmado pelo próprio Douglas em 2026-08-20 como **incorreto/desatualizado em si**, não apenas superado por uma edição mais nova. 3606 USD/kW é o valor correto da edição IRENA 2025, confirmado contra a fonte primária. A variação ano-a-ano global de TIC (Total Installed Cost) de bioenergia reportada pela própria IRENA na edição 2025 é de +9% — essa estatística **não corresponde** ao delta 2720→3606 mostrado aqui, já que 2720 já estava errado; os dois números não devem ser lidos como representando a mesma comparação. Nenhuma correção adicional é feita na entrada de 2026-08-19 (regra append-only); esta entrada documenta a correção conforme apurada em 2026-08-20.
- OPEX deixou de ser um único valor (109 USD/kW/ano em 2024) e passou a ter dois componentes, conforme a estrutura da edição 2025: `opex_fixed_pct_of_capex` = 0.04 (ponto escolhido dentro da faixa reportada pela IRENA de 2-6% do custo total instalado — não é um número único diretamente reportado, é uma escolha de julgamento, documentada como tal no campo `note` do parâmetro) e `opex_variable_usd_per_kwh` = 0.004 (mesmo valor para PRT e BRA).
- `capacity_factor`: parâmetro novo, não existia na entrada de 2026-08-19 nem no legado GeoWorld como valor por-país canônico neste nível — diferenciado por país pela primeira vez: PRT = 0.81 (proxy regional Europa, IRENA 2025 Fig 8.7), BRA = 0.63 (específico do Brasil, mesma figura).
- `lifetime_years`: mantido em 20 anos, sem mudança em relação a 2024.

Todos os valores acima marcados `verified: true` (verified_by: Douglas, verified_date: 2026-08-20, verification_method: manual_cross_check, source: "IRENA 2025"), exceto `opex_fixed_pct_of_capex`, que também é `verified: true` mas carrega uma nota explícita de que é um ponto escolhido dentro de uma faixa, não um valor único da fonte.

**Pendências registradas nesta mesma entrada** (não inventadas, deixadas explicitamente em aberto):
- `discount_rate` (taxa base por país): valor placeholder 0.07 para PRT e BRA, `verified: false`, sem fonte associada ainda.
- `discount_rate_increment` (prêmio de risco específico de tecnologia sobre a taxa base do país): `value: null`, `status: "pending_research"`. O conceito é sustentado pela literatura de custo de capital específico por tecnologia (ex. Steffen, B. (2020). "Estimating the cost of capital for renewable energy projects." Energy Economics / ScienceDirect), mas nenhum valor numérico foi escolhido para o GeoFREA ainda.

Justificativa (se METHODOLOGY_REVISION): atualizar para a edição mais recente da fonte primária (IRENA 2025) e introduzir capacity_factor diferenciado por país, que a versão anterior não tinha. A reestruturação de OPEX em fixo+variável segue a mudança de metodologia da própria IRENA entre as edições 2024 e 2025, não uma escolha arbitrária do GeoFREA.
Referência (literatura/discussão, se aplicável): IRENA, Renewable Power Generation Costs in 2025 (verificação manual por Douglas, 2026-08-20). Steffen, B. (2020), "Estimating the cost of capital for renewable energy projects", Energy Economics (referência conceitual para discount_rate_increment, ainda sem valor aplicado).

---

## [2026-08-20] - biomass discount_rate e discount_rate_increment — resolução das pendências
Tipo: VERIFICATION_UPDATE
Descrição: Resolve as duas pendências deixadas em aberto na entrada "biomass parameters restructure (IRENA 2025)" (mesmo dia). Não revisa a decisão de reestruturação em si — apenas preenche valores/fontes que antes estavam `verified: false`/`pending_research`.

- `discount_rate` (taxa base por país), fonte IRENA "Renewable Power Generation Costs in 2024" (seção de custo de capital / Table A1), mesma família de relatório já usada para CAPEX/OPEX/capacity_factor:
  - PRT = 0.05 — Portugal é OECD; a ferramenta de benchmark de WACC específico por tecnologia da IRENA (2022+) só cobre eólica onshore/offshore e solar PV para 100 países — bioenergia, geotérmica e hidrelétrica usam este default OECD/não-OECD mais simples, conforme metodologia IRENA 2024.
  - BRA = 0.075 — Brasil é não-OECD, então o default "resto do mundo" de 7,5% se aplica. **Duas afirmações distintas, deliberadamente não confundidas**: (1) o valor-padrão 0.075 está `verified: true` — confirmado contra a Table A1; (2) a IRENA descreve um "piso mínimo de WACC" para países de alto risco (ex. Argentina, Moody's Caa1) que substituiria esse default flat — o rating do Brasil na própria Figura S7 da IRENA é Ba2 (moderado, bem acima de Caa1/Caa3), e o julgamento de Douglas é que esse piso provavelmente não se aplica, **mas isso não foi calculado** (exigiria taxa livre de risco global, spread de default soberano do Brasil, margem de credor e prêmio de risco de equity, indisponíveis nesta sessão). Essa segunda afirmação **não** está coberta pelo `verified: true` do campo — distinção registrada explicitamente no campo `note` do JSON (duas frases rotuladas "CONFIRMED CLAIM" / "UNCONFIRMED ASSUMPTION"), não como campo novo de schema.
- `discount_rate_increment` (biomassa, ambos os países) = 0.0, fonte IRENA 2024 (seção de metodologia de custo de capital), `status: "pending_research"` removido. Bioenergia não é coberta pela ferramenta de benchmark de WACC específico por tecnologia da IRENA (que só diferencia eólica onshore/offshore/solar PV) — usa o default OECD/não-OECD diretamente, sem prêmio de tecnologia adicional. `0.0` reflete que a própria metodologia da IRENA não adiciona incremento específico para bioenergia — **não** significa que não exista prêmio de risco na realidade, apenas que nenhum está documentado nesta fonte.

Nenhuma mudança estrutural em `src/geofrea/core/schemas.py` foi necessária — `note` e `status` já eram campos opcionais existentes em `VerifiedValue`, suficientes para representar as duas afirmações distintas do `discount_rate` do BRA sem novo campo de schema.

Justificativa (se METHODOLOGY_REVISION): n/a — VERIFICATION_UPDATE, não altera a decisão de reestruturação de 2026-08-20 (biomass parameters restructure), apenas resolve pendências que aquela entrada deixou explicitamente em aberto.
Fonte: IRENA, Renewable Power Generation Costs in 2024, seção de custo de capital / Table A1 (verificação manual por Douglas, 2026-08-20). A não-aplicabilidade do piso de WACC para o Brasil é uma suposição registrada, não um cálculo verificado — ver `note` do campo `discount_rate` do BRA em `parameters.json`.

---

## [2026-08-20] - discount_rate architecture fix
Tipo: METHODOLOGY_REVISION
Descrição: `discount_rate` foi movido de `CountryParams` (um valor por país) para o modelo de parâmetros de cada tecnologia (`_TechnologyEconomicParams`, herdado por `BiomassParams`/`SolarParams`/`WindParams`) — um valor por tecnologia, por país. `schemas.py`: campo `discount_rate` removido de `CountryParams`; adicionado a `_TechnologyEconomicParams` (base compartilhada), constrangido a `>= 0` via o alias `NonNegativeFloat`. `parameters.json`: cada bloco `countries.{PRT,BRA}.discount_rate` (com todos os metadados/notas já existentes) foi movido para `technologies.biomass.discount_rate`; a chave de topo `countries.{PRT,BRA}.discount_rate` foi removida.

Testes atualizados: `test_country_params_missing_required_field_raises` não inclui mais "discount_rate" como campo obrigatório de `CountryParams` (agora só "technologies"); `discount_rate` passou a ser um dos 7 campos obrigatórios testados para `BiomassParams`/`SolarParams`/`WindParams` via `test_tech_economic_params_missing_required_field_raises` (parametrizado por tecnologia × campo).

Justificativa (se METHODOLOGY_REVISION): a ferramenta de benchmark da IRENA retorna taxas de desconto genuinamente diferentes por tecnologia para o mesmo país (ex. PRT: biomassa=5%, solar=4.2%, eólica=3.7% — não é uma relação base+incremento, são saídas independentes do benchmark tool por tecnologia). Um único campo `discount_rate` em nível de país estava, na prática, guardando o valor da biomassa rotulado incorretamente como taxa do país inteiro — factualmente errado assim que mais de uma tecnologia existisse (como passou a ser o caso nesta mesma etapa, com solar/wind).
Referência (literatura/discussão, se aplicável): IRENA 2024, metodologia da ferramenta de benchmark de custo de capital (mesma fonte já citada na resolução do discount_rate de biomassa).

---

## [2026-08-20] - solar and wind parameters populated (IRENA 2024/2025)
Tipo: METHODOLOGY_REVISION
Descrição: `SolarParams` e `WindParams` adicionados a `schemas.py`, com a mesma forma de `BiomassParams` (herdando de `_TechnologyEconomicParams`), exceto `opex_variable_usd_per_kwh`, que em ambos é `VerifiedValue[float | None]` (não `VerifiedValue[float]` como em biomassa) — a fonte IRENA não separa O&M fixo/variável para solar/eólica, só reporta um valor total combinado. `TechnologyParams` passou a exigir `solar`/`wind` como campos obrigatórios (não opcionais), populados com dados reais nesta etapa, seguindo a mesma política já usada para biomassa de "não criar stub sem dado real".

`config/parameters.json` populado para PRT e BRA, ambas as tecnologias, fonte IRENA "Renewable Power Generation Costs in 2025" (CAPEX/OPEX/capacity_factor/lifetime) + IRENA 2024 (metodologia de custo de capital, para discount_rate/discount_rate_increment) — mesmas fontes já usadas para biomassa. Detalhamento campo a campo, incluindo todas as ressalvas de proxy regional/global, está nos campos `note` do próprio `parameters.json`.

**Dois pontos fracos sinalizados explicitamente**:
- **CAPEX de eólica não tem valor específico por país para nenhum dos dois países** — usa a mesma figura global (976 USD/kW) para PRT e BRA, por ausência de quebra por país nas fontes revisadas nesta sessão.
- **OPEX de eólica para o Brasil usa a figura de O&M global de SOLAR como substituto não validado**, não uma fonte específica de eólica — é o valor com sourcing mais fraco de todo o dataset até agora. Sinalizado no campo `note` correspondente com o texto "PROXY QUALITY: WEAK", distinguindo-o explicitamente das demais combinações tecnologia/país do dataset, que usam proxies regionais mas com fontes tecnologicamente compatíveis. Nenhum campo novo de schema foi criado para essa distinção (ex. `proxy_quality`) — usei o campo `note` já existente, mesma abordagem da distinção "CONFIRMED CLAIM"/"UNCONFIRMED ASSUMPTION" do `discount_rate` do BRA (entrada anterior). Deve ser revisitado se uma fonte melhor for encontrada.

Justificativa (se METHODOLOGY_REVISION): popular os domínios solar/eólica era necessário para a Fase 2+ do GeoFREA avançar além de biomassa; os dois pontos fracos acima são sinalizados deliberadamente como dívida de dados a ser paga depois, não escondidos atrás de um `verified: true` genérico.
Referência (literatura/discussão, se aplicável): IRENA, Renewable Power Generation Costs in 2025 (CAPEX/OPEX/capacity_factor/lifetime). IRENA, Renewable Power Generation Costs in 2024, metodologia da ferramenta de benchmark de custo de capital (discount_rate/discount_rate_increment) — verificação manual por Douglas, 2026-08-20.

---

## [2026-08-20] - settings.yaml phase toggles
Tipo: STRUCTURAL_PRESERVE
Descrição: `config/settings.yaml` populado com a estrutura `run.countries` (lista de códigos ISO-3166-alpha-3 a rodar; vazia = todos os países presentes em `parameters.json`) e `run.phases` (um booleano por módulo, todos `false` por ora — nenhum runner de fase existe ainda). A lista de nomes de fase em `phases` vem de `docs/PROGRESS.json`, campo `modulos[].nome` (data_quality_audit, grid_alignment, suitability_criteria, suitability_analysis, potential_analysis, lcoe_modeling, results_synthesis, ghg_abatement, sensitivity_analysis) — mesmos nomes usados no layout `src/geofrea/<nome>/` criado na Fase 1.

Isto espelha o padrão `skip_*` do `geoworld_framework` legado (um flag por fase, controlando o que roda numa execução), mas com a semântica invertida: `phases.<nome>: true` significa "esta fase RODA" (não "pular"), para evitar leitura de dupla negativa. `run.countries` não é hardcoded para PRT/BRA — a lista vazia (comportamento padrão: rodar todos os países presentes em `parameters.json`) é resolvida dinamicamente por um futuro executor de pipeline, não fixada aqui; isso está documentado como nota/docstring em `config_loader.py::load_settings()`, já que nenhum executor existe ainda para implementar de fato.

Schema: `RunConfig` (`countries: list[str]`, `phases: dict[str, bool]`) e `SettingsFile` (`run: RunConfig`) adicionados a `schemas.py`, ambos com `extra="forbid"`. Sem o wrapper `VerifiedValue` — esse metadado de verificação existe para valores científicos de `parameters.json` com fonte citável; não se aplica a toggles operacionais de `settings.yaml`. `config_loader.py::load_settings()` agora valida contra `SettingsFile` e retorna uma instância validada, em vez de um dict cru.

Justificativa: n/a — STRUCTURAL_PRESERVE, replica o padrão de toggle por fase já usado no legado, não é uma revisão metodológica.
Referência (literatura/discussão, se aplicável): geoworld_framework/configs/settings.yaml (padrão `skip_*` legado); docs/PROGRESS.json (fonte da lista de nomes de módulo).

---

## [2026-08-20] - Transport Decarbonisation phase - exclusão permanente
Tipo: STRUCTURAL_PRESERVE
Descrição: o `geoworld_framework` legado (`main.py`) orquestra uma 10ª fase, "Phase 9 — Transport Decarbonisation" (`TransportDecarbonizationCalculator`, flag `skip_transport`), executada por último, após Sensitivity Analysis. Esta fase está ausente do array `modulos` de `docs/PROGRESS.json` — lacuna de documentação identificada em 2026-08-20, durante a auditoria de `main.py`/`PipelineOrchestrator` realizada nesta sessão. Douglas decidiu que o GeoFREA NÃO incluirá este módulo — exclusão permanente, não adiada, não a ser reconsiderada sem uma nova decisão explícita que sobreponha esta.

This exclusion is final. Do not re-add a transport phase to RunConfig.phases, PROGRESS.json's modulos array, or any orchestrator code without an explicit new DECISIONS.md entry overriding this one — its prior absence from PROGRESS.json should NOT be read as an oversight to fix.

Justificativa: decisão de escopo de Douglas — não é uma correção de lacuna, é uma exclusão deliberada. A ausência prévia da fase Transport em `PROGRESS.json` (antes desta entrada) não deve ser lida como um erro a corrigir; esta entrada é o que torna a exclusão explícita e permanente.
Referência (literatura/discussão, se aplicável): `geoworld_framework/main.py`, `PipelineOrchestrator` — achados da auditoria desta sessão (2026-08-20).

---

## [2026-08-20] - orchestrator + data_quality_audit phase
Tipo: METHODOLOGY_REVISION
Descrição: implementado `src/geofrea/core/orchestrator.py` (`Orchestrator`, `PhaseSpec`, `PhaseContext`, `PhaseResult[T]`, `RunManifest`/`PhaseManifestEntry`, `PhaseExecutionError`) como mecanismo único de orquestração de fases, substituindo o design do `geoworld_framework` legado (`main.py`), que misturava funções inline por fase (Fase 1/2a, `_run_phase_1_audit`/`_run_phase_2a_align`) com um `PipelineOrchestrator` centralizado só para as Fases 2b-9. No GeoFREA há um único mecanismo, desde a Fase 1.

Diferenças deliberadas em relação ao legado:
- **Contrato Pydantic por fase, sem exceção**: toda fase retorna um `BaseModel` próprio (`output_model` do `PhaseSpec`), validado pelo orchestrator. O legado isentava as Fases 6-9 disso (`output_model=None`, saída em arquivo). A primeira fase implementada, `data_quality_audit`, já segue essa regra: `AuditResult` (`src/geofrea/data_quality_audit/schemas.py`) substitui o dict ad hoc que `DataAuditor.run()` retornava (ver `docs/architecture/data_quality_audit.md` sec a).
- **Try/except único no orchestrator**: cada execução de fase é envolta em um único bloco try/except dentro de `Orchestrator.run()`, não espalhado por função por fase como no legado. Uma falha produz `PhaseResult(status="failed", output=None, error=str(exc))`, é persistida no manifest, logada via `logger.exception`, e a exceção original é relançada (`PhaseExecutionError`) — nunca engolida silenciosamente, e nenhuma fase dependente é executada depois.
- **Sem mutação implícita entre fases**: o anti-padrão evitado é `_merge_pot_result_into_params` do legado, que mutava o `params` compartilhado dentro de `main.py` após a Fase 4. Aqui, `PhaseContext.prior_results` é somente-leitura (`Mapping[str, PhaseResult]`); uma fase futura que precise realimentar valores para fases posteriores deve devolvê-los como parte da própria saída, e qualquer merge para estado compartilhado é feito explicitamente pelo chamador (`main.py`), não por mutação implícita dentro do orchestrator nem de uma fase. Ainda não há fase alguma que consuma `prior_results` de fato (só `data_quality_audit` existe) — a estrutura está pronta, não exercida.
- **Resumabilidade via manifest**: após cada fase bem-sucedida, `outputs/<country_code>/manifest.json` é atualizado (`RunManifest`). Uma nova execução para o mesmo país reconstrói fases já `"success"` a partir do manifest (via `output_model.model_validate()`), sem reexecutá-las, e retoma da primeira fase pendente. Evita reexecutar um pipeline de ordem de 1h após falha numa fase tardia (BRA legado: ~56min, `docs/architecture/baseline-manifest.md`). `run_id` é o próprio `country_code` (não um timestamp por invocação) — um `run_id` baseado em timestamp impediria a resumabilidade, já que cada execução nunca encontraria o manifest da execução anterior.

`data_quality_audit` (`src/geofrea/data_quality_audit/`) porta a lógica de `DataAuditor` do legado (`raster_inspection.py`: `inspect_raster`, `inspect_land_cover_tiles`, `inspect_power_plants`, `diagnose_consistency`, e helpers de área geodésica/mascaramento; `audit.py`: `run_audit_phase()`). Helpers de geometria genéricos (`get_local_utm_crs`, `get_mainland_gdf`, `detect_island_nation`) foram movidos para `src/geofrea/core/geo_utils.py` — não são específicos de auditoria, fases futuras (ex. `grid_alignment`) também vão precisar deles.

**Simplificações/desvios do legado, sinalizados explicitamente** (não corrigidos silenciosamente nem herdados sem nota):
- **BLOCKER-015 do legado não é herdado**: o legado salvava o relatório de auditoria em `outputs/reports/audit_{code}_{timestamp}.txt` (raiz do repo) enquanto seu próprio skip-check via glob procurava em `outputs/{code}/audit/` — nunca batiam (`docs/architecture/data_quality_audit.md` sec d). O GeoFREA salva em `outputs/<code>/audit/audit_<code>_<timestamp>.txt`, e a resumabilidade é via manifest, não glob — o bug não existe nesta reimplementação.
- **`country_name` removido**: `parameters.json` do GeoFREA indexa países só por código ISO, sem tabela nome→código (o legado aceitava nome OU código como argumento de CLI e resolvia via `ConfigLoader.get_country_by_name()`). O relatório de auditoria usa só o código.
- **`slope_threshold_deg` sempre usa o fallback (15.0°)**: o legado podia ler um override por país de `parameters.json`; o schema `CountryParams` do GeoFREA não tem esse campo ainda (não foi fabricado sem autorização — ver `docs/CONVENTIONS.md`, "Parameters"). Se um override real for necessário, o campo precisa ser adicionado a `CountryParams` primeiro.
- **`expected_resolutions`/`res_tolerance` seguem como constantes nomeadas no módulo**, não viraram chaves de `settings.yaml`: a própria nota de arquitetura do legado (`docs/architecture/data_quality_audit.md` sec c) já classifica esses valores como gate de diagnóstico, não parâmetro científico — não afetam nenhum cálculo downstream, só a calibração do próprio alerta desta fase.
- **`main.py` não tem como popular dados reais ainda**: não existe camada de aquisição de dados no GeoFREA (`DataFetcher`/`DataManager`/`DataOrchestrator` do legado não foram portados — fora do escopo desta etapa). `AuditInputs()` é construído vazio em `main.py`; toda execução real hoje reporta "File not found" para todos os rasters — o mesmo caminho defensivo que a fase já tem para arquivo ausente, não comportamento novo.

Dependências adicionadas a `pyproject.toml` (`numpy`, `pandas`, `geopandas`, `rasterio`, `shapely`): necessárias para portar a lógica real de inspeção de raster (mascaramento por polígono, leitura em chunks, área geodésica) — não estavam presentes antes porque nenhuma fase geoespacial existia ainda.

Justificativa (se METHODOLOGY_REVISION): consolidar toda a orquestração num único mecanismo testável, com contrato de saída tipado por fase e resumabilidade real, evitando as duas classes de bug já documentadas no legado nesta sessão (BLOCKER-015: skip-check aponta para diretório errado; mutação implícita de `params` pós-Fase-4 via `_merge_pot_result_into_params`).
Referência (literatura/discussão, se aplicável): `geoworld_framework/main.py`, `src/core/pipeline_orchestrator.py`, `src/processors/data_auditor.py` (achados de auditoria desta sessão, 2026-08-20); `docs/architecture/data_quality_audit.md` (GeoFREA, já existente).

---

## [2026-08-20] - slope_threshold_deg movido para parameters.json
Tipo: METHODOLOGY_REVISION
Descrição: `slope_threshold_deg` deixou de ser um fallback único hardcoded de 15.0° (valor do legado, sem fonte documentada — `docs/architecture/data_quality_audit.md` sec c, item 4) e passou a ser um valor por tecnologia em `config/parameters.json` (`technologies.{biomass,solar,wind}.slope_threshold_deg`, bloco de verification metadata padrão), sourced conforme a revisão de literatura desta sessão. Schema: `slope_threshold_deg: VerifiedValue[NonNegativeFloat]` adicionado a uma nova classe base `_TechnologySitingParams` (`src/geofrea/core/schemas.py`), separada de `_TechnologyEconomicParams` — `BiomassParams`/`SolarParams`/`WindParams` agora herdam de ambas (multiple inheritance de `BaseModel`, testado e funcional em pydantic v2). Justificativa da separação: `slope_threshold_deg` alimenta checagens de auditoria/suitability (uma restrição física de sítio), não o cálculo de LCOE — domínio conceitualmente distinto dos campos econômicos, mesmo sendo também por-tecnologia-por-país. Manter a separação permite adicionar mais restrições físicas depois (ex. distância mínima de eólica) sem poluir a base econômica.

Valores populados para PRT e BRA (mesmo valor nos dois países — nenhuma fonte diferenciou por país):
- **solar = 5.0°**: fonte MDPI, estudo de caso de seleção de sítio para PV em Ikorodu (Nigéria) — slopes acima de 5° classificados como menos adequados para solar PV de larga escala, devido à complexidade construtiva, custo do sistema de montagem e risco de erosão. `verified: true`, `verification_method: manual_cross_check`. Sinalizado explicitamente como fonte de estudo de caso único, não um consenso multi-regional — ponto de partida razoável, não uma figura definitiva.
- **biomass = 8.5°**: fonte na literatura de aptidão agrícola/agrivoltaica — 15% de slope (~8,5°) é o limite superior comumente citado para agricultura mecanizada de culturas perenes; usado aqui como proxy porque a colheita de biomassa tem restrições de acesso mecanizado similares. `verified: true`, `verification_method: manual_cross_check`, nota explícita: "proxy from agricultural slope literature, not a bioenergy-specific source — same caveat pattern as biomass capacity_factor's regional proxies."
- **wind = 8.5°**: nenhuma fonte específica de eólica foi encontrada na literatura revisada nesta sessão. **Reutiliza o valor e a fonte de biomassa diretamente**, por instrução explícita de Douglas — esta reutilização é registrada de forma explícita (nota no JSON: "no wind-specific source found — reuses biomass's agricultural-slope proxy value directly, not an independent wind-specific figure"), não disfarçada como se eólica tivesse fonte própria.

`data_quality_audit`: `_DEFAULT_SLOPE_THRESHOLD_DEG` removido de `audit.py`. A checagem de inatividade de slope agora roda uma vez por tecnologia (biomass/solar/wind), lendo `context.country_params.technologies.<tech>.slope_threshold_deg.value` — não mais uma vez por país com um valor fixo. `AuditResult` ganhou o campo `slope_threshold_check: dict[str, SlopeThresholdCheck]` (chaveado por tecnologia; cada entrada tem `threshold_deg`, `max_observed_deg`, `inactive`), substituindo a suposição implícita de um único threshold por país. Alertas de texto agora incluem a tecnologia (`INACTIVE CRITERION [slope/<tech>]`).

Justificativa (se METHODOLOGY_REVISION): o fallback de 15.0° do legado não tinha fonte e era aplicado uniformemente a todas as tecnologias, apesar de eólica/solar/biomassa terem tolerâncias de terreno fisicamente distintas (restrições de fundação/mounting para solar, acesso mecanizado para biomassa). Um valor único por país estava sujeito ao mesmo problema estrutural já corrigido para `discount_rate` (ver entrada "discount_rate architecture fix", mesma sessão): um campo por-país não pode representar corretamente um valor que varia por tecnologia.
Referência (literatura/discussão, se aplicável): MDPI, estudo de caso Ikorodu (Nigéria), seleção de sítio PV (solar); literatura de aptidão de slope agrícola/agrivoltaica (biomass, proxy); nenhuma referência wind-específica encontrada (wind reutiliza biomass, ver acima). `docs/architecture/data_quality_audit.md` sec c, item 4 (origem do fallback legado sem fonte).

---

## [2026-08-24] - data_acquisition skeleton
Tipo: METHODOLOGY_REVISION
Descrição: implementado o esqueleto estrutural da fase `data_acquisition` (`src/geofrea/data_acquisition/`) — **sem nenhuma lógica de fetch/download real** (nenhuma chamada HTTP, nenhum SDK de fonte, nenhuma leitura de `.env`). Objetivo: definir o contrato pelo qual `data_quality_audit`'s `AuditInputs` poderá ser populado por esta fase no futuro, com base numa auditoria do legado (`geoworld_framework`, `fc7b43d`) feita antes de codar.

**Nota de correção**: os docstrings de `phase.py`/`schemas.py` inicialmente referenciavam esta entrada como "`docs/DECISIONS.md 2026-08-20`" — data errada (a implementação aconteceu em 2026-08-24; a referência a 2026-08-20 foi um erro de cópia do padrão da entrada anterior, "orchestrator + data_quality_audit phase"). Corrigido nos docstrings antes desta entrada existir de fato — a entrada nunca ficou "referenciada mas inexistente" além do tempo de uma única sessão de trabalho, mas fica registrado aqui para rastreabilidade, já que essa exata lacuna (referência prospectiva sem entrada correspondente) foi o que motivou a auditoria que gerou esta entrada.

**Achados da auditoria do legado, base para o design**:
- `DataOrchestrator.acquire_all()` (`geoworld_framework/src/io/data_orchestrator.py`) retorna um dict de status com 15 chaves. Só 6 métodos `download_*` existem em todo `DataFetcher` (`gadm`, `land_cover`, `elevation`, `worldpop`, `osm_grid`, `osm_roads`) — todas as outras camadas (`Solar`, `Lakes`, `Rivers`, `Seismic`, `Protected`, `Power Plants`) não têm mecanismo de fetch nenhum, precisam estar pré-colocadas em disco.
- Única credencial em todo o projeto legado: `TERRASCOPE_USERNAME`/`TERRASCOPE_PASSWORD` (`ConfigLoader.credentials`), usada só por `download_land_cover` (ESA WorldCover via Terrascope).
- `Admin1` (`DataManager.get_admin_level_1`) não é buscado separadamente — é um subproduto do mesmo zip do GADM 4.1 que popula `Borders`.
- `slope` nunca é buscado nem bundled — é derivado de `elevation` via `RasterProcessor.calculate_slope()`, chamado em `main.py` depois que a aquisição termina. Por isso **não está no registry de `data_acquisition`**: não se encaixa em `provenance: "fetched"` (não vem de fonte externa) nem `"local_only"` (não é arquivo pré-colocado) — decisão deliberada, não esquecimento.
- `Protected` (WDPA) **nunca é auditado** pelo `DataAuditor` legado (zero referências em `data_auditor.py`, confirmado por grep). É consumido só na Fase 2b, em `criteria_builder.py::compute_protected_areas(wdpa_path, mainland_gdf, transform, width, height, crs, as_exclusion=True)`, para rasterizar exclusão por categoria IUCN — mesma lógica já documentada na entrada `2026-08-19 - protected_areas / IUCN exclusion categories`. Ver pendência registrada abaixo.

**Contrato implementado**:
- `schemas.py`: `AcquiredLayer` (`layer_name`, `provenance: Literal["fetched","local_only"]`, `auth_required: bool` — nunca guarda a credencial em si, `source_name`, `country_code` opcional, `path: Path | None`, `paths: list[Path]` reservado a camadas multi-arquivo, `crs_metadata: CrsMetadata | None` reservado para bookkeeping futuro de CRS/reprojeção), `AcquisitionSummary`, `AcquisitionResult` (mesmo padrão de retorno que `AuditResult`: `country_code` + `timestamp` + detalhe + resumo).
- `phase.py`: `run_acquisition_phase(context) -> AcquisitionResult`, registrando 14 camadas em `_LAYER_REGISTRY` (todas com `path`/`paths` sempre vazios nesta etapa). Único registro com `auth_required=True`: `land_cover`.
- `adapter.py`: `acquisition_result_to_audit_inputs()` — I/O local real (`pandas.read_csv`, `geopandas.read_file`), não é lógica de fetch.
- `main.py`: `data_acquisition` registrado como primeiro `PhaseSpec` (o `Orchestrator` não impõe ordem nenhuma entre fases — confirmado lendo `Orchestrator.run()`, a ordem é 100% a posição na lista que o chamador passa; `RunConfig.phases` é só um mapa de toggles, sem semântica de ordem). **Não** está conectado ao `AuditInputs()` do audit ainda (continua vazio) — ver guard abaixo.

**wind vs. land_cover — decisão explícita de escopo, não consequência implícita** (resolvendo uma assimetria identificada em revisão):
- **wind permanece single-path** (`AcquiredLayer.path`): `AuditInputs`'s próprio docstring confirma que só o primeiro arquivo de vento é inspecionado ("only the first, if any, is inspected") — um campo de lista não teria uso real, então não há gap a fechar aqui.
- **land_cover ganhou `AcquiredLayer.paths: list[Path]`** por necessidade real: os tiles ESA WorldCover são genuinamente multi-arquivo e **todos** são consumidos (`inspect_land_cover_tiles()` itera cada tile) — um único path seria lossy, diferente de wind.
- `adapter.py` atualizado: `wind_paths=[layer.path] if layer and layer.path else []`; `land_cover_tiles=layer.paths if layer else []`.

**Gaps que permanecem abertos, sinalizados e não corrigidos silenciosamente**:
1. **`adapter.py` é lossy por design**: `AuditInputs` não tem nenhum campo de proveniência — `provenance`/`auth_required`/`source_name`/`crs_metadata` de `AcquiredLayer` são descartados na conversão. Não corrigido sem autorização (mudar `AuditInputs` é uma stage própria).
2. **`_load_power_plants()`/`_load_mainland_boundary()` não são defensivos**: nenhum try/except. Testado empiricamente (`tests/unit/test_data_acquisition_adapter.py`, testes de caracterização): CSV vazio → `pandas.errors.EmptyDataError` propaga; CSV com bytes binários garbage → **não levanta exceção nenhuma**, `pandas` parseia como um DataFrame de 1 linha sem sentido (falha silenciosa, pior que uma exceção); shapefile/GeoJSON corrompido → `pyogrio.errors.DataSourceError` propaga. O padrão de `lakes`/`rivers` em `audit.py` **não se aplica aqui** como precedente — aquelas duas camadas só checam `Path.exists()`/`.stat().st_size`, nunca abrem o conteúdo do arquivo, então não têm nada a capturar. O precedente real seria `inspect_raster()`, que tem try/except amplo e reporta `{"error": str(exc)}` em vez de propagar. Proposta (não implementada, aguardando autorização): envolver os dois loaders do adapter no mesmo padrão de `inspect_raster()`.
3. **Wiring `main.py` pendente**: `_build_phase_specs()` ainda usa `functools.partial(run_audit_phase, inputs=AuditInputs())` (eager, construído antes de qualquer fase rodar) — conectar de fato a `data_acquisition`'s output exige trocar esse padrão por uma closure por-contexto que leia `context.prior_results["data_acquisition"].output` em tempo de execução. Não feito aqui — é uma mudança na própria fase de audit, não um efeito colateral de adicionar acquisition.
4. **Guard implementado contra o gap 3**: `main.py` agora levanta `UnwiredPhasesError` na construção de `_build_phase_specs()` se `data_acquisition` E `data_quality_audit` estiverem ambos habilitados em `run.phases` ao mesmo tempo — impede rodar silenciosamente um audit com `AuditInputs()` vazio disfarçado de execução real, antes que qualquer fase execute.
5. **`protected` (WDPA)**: pendência registrada explicitamente, ver entrada seguinte.

`settings.yaml` não foi alterado — `run.phases` ainda não tem chave `"data_acquisition"`; até ser adicionada, a fase é pulada por padrão (`phases_enabled.get("data_acquisition", False)`), confirmado rodando `main.py` sem erro.

Justificativa (se METHODOLOGY_REVISION): estabelecer o contrato de aquisição antes de implementar fetch real, para que a lógica de download (quando vier) se encaixe numa estrutura já revisada, em vez de crescer ad hoc — mesmo racional já aplicado ao design do orchestrator (entrada 2026-08-20).
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/io/data_orchestrator.py`, `data_fetcher.py`, `data_manager.py`, `src/core/config_loader.py::credentials` (achados da auditoria desta sessão, 2026-08-24); `geoworld_framework/src/processors/criteria_builder.py::compute_protected_areas` (achado sobre `protected`, ver entrada seguinte).

---

## [2026-08-24] - protected (WDPA): decisão de onde entra no GeoFREA fica pendente
Tipo: STRUCTURAL_PRESERVE
Descrição: `protected` já existe no registry de `data_acquisition` (`AcquiredLayer(layer_name="protected", ...)`), porque a camada bruta (arquivo WDPA) precisa ser rastreada na aquisição independentemente de qual fase a consome depois. Mas, ao contrário de `lakes`/`rivers` (que **são** auditadas em `data_quality_audit`, checagem de presença/tamanho via `VectorLayerInspection`), `protected` **não tem equivalente em `AuditInputs`/`AuditResult`** nesta etapa — decisão deliberada, não omissão.

Motivo: no legado, `protected`/WDPA nunca passa pelo `DataAuditor` (Fase 1) — é consumido exclusivamente na Fase 2b (`criteria_builder.py::compute_protected_areas`), como máscara de exclusão por categoria IUCN, a mesma lógica já registrada na entrada `2026-08-19 - protected_areas / IUCN exclusion categories`. Estender `AuditInputs`/`VectorLayerInspection` para `protected` só porque o layer já existe no registry de acquisition replicaria uma camada de auditoria que o próprio legado nunca teve para este dado — forçaria uma simetria com `lakes`/`rivers` que não existe na arquitetura original.

"Onde `protected` entra no GeoFREA" fica como pendência explícita, associada à futura fase `suitability_criteria` (ainda não projetada nesta reconstrução — corresponde à Fase 2b do legado, `fase_legado: 2` em `docs/PROGRESS.json`), não a `data_quality_audit`. Quando `suitability_criteria` for desenhada, esta entrada deve ser revisitada para decidir o schema de entrada equivalente a `wdpa_path`/`compute_protected_areas`.

Justificativa: n/a — STRUCTURAL_PRESERVE, preserva a separação de responsabilidades já existente no legado (auditoria não inclui `protected`), não uma revisão metodológica.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_protected_areas`; DECISIONS.md `2026-08-19 - protected_areas / IUCN exclusion categories`.

---

## [2026-08-24] - vector layer audit depth
Tipo: METHODOLOGY_REVISION
Descrição: `data_quality_audit` passou a inspecionar os 7 layers vetoriais do `data_acquisition`'s `_LAYER_REGISTRY` (`borders`, `admin1`, `grid`, `roads`, `protected`, `lakes`, `rivers`) com a mesma profundidade que rasters já tinham via `inspect_raster()` — CRS, contagem de features, tipos de geometria, bbox, área/comprimento total e (só para `protected`) breakdown por categoria IUCN — em vez do check anterior de presença/tamanho (`Path.exists()` + `.stat().st_size`, sem nunca abrir o arquivo) que existia só para `lakes`/`rivers`.

**Decisão sobre a assinatura da nova função — divergência identificada e resolvida antes de codar**: as instruções desta etapa continham duas ideias conflitantes: (a) a assinatura explícita `inspect_vector_layer(path, country_gdf, clip=True)`, que implica abrir o arquivo dentro da função (mesmo padrão preguiçoso de `inspect_raster()`); (b) a instrução de estender `adapter.py` para "carregar os GeoDataFrames adicionais ... seguindo o padrão já usado por `_load_mainland_boundary`", que implica pré-carregar os GeoDataFrames no adapter (mesmo padrão já usado por `plants_df`/`country_gdf`). As duas não podem ser verdadeiras ao mesmo tempo. Resolvido a favor de (a) — `inspect_vector_layer(path, country_gdf, clip, iucn_breakdown)` abre o arquivo ele mesmo, dentro de `data_quality_audit/vector_inspection.py` (novo módulo) — porque: a assinatura literal foi dada explicitamente; o padrão espelha `inspect_raster()` exatamente (não inventa uma segunda convenção de "objeto já carregado" só para vetores); e evita carregar até 6 arquivos vetoriais globais grandes (HydroLAKES/HydroRIVERS/WDPA) na memória de `adapter.py` mesmo quando a fase de auditoria nunca roda depois. `AuditInputs` ganhou `protected_path`, `borders_path`, `admin1_path`, `grid_path`, `roads_path` (todos `Path | None`, mesmo padrão de `solar_path`/`elevation_path`) — não `protected_gdf` etc. Nada em `adapter.py` abre esses 5 arquivos; só `borders` continua sendo aberto no adapter, mas para um propósito diferente (`_load_mainland_boundary()`, que já existia, produzindo `country_gdf`) — `borders_path` é passado adiante cru, sem abrir, para a inspeção própria do layer bruto em `vector_inspection.py`.

**clip=True vs. clip=False**: derivado diretamente do campo `country_specific` já existente em `_LayerSpec` (`data_acquisition/phase.py`) — `protected`/`lakes`/`rivers` (`country_specific=False`, arquivo único global) usam `clip=True`; `borders`/`admin1`/`grid`/`roads` (`country_specific=True`, já delimitados por país na fonte — download GADM/OSM Overpass por país) usam `clip=False`. Implementado via `clip_vector_to_country()` (`core/geo_utils.py`, nova função): bbox-prefilter (`gdf.cx[]`) seguido de intersecção geométrica real — reusa o mesmo padrão de duas etapas que `inspect_land_cover_tiles()` já usa para tiles ESA e que `criteria_builder.py::compute_protected_areas()` (legado) usa para `wdpa_path` (embora sem o prefilter explícito de bbox lá). Não é uma extração literal de `inspect_land_cover_tiles()` — a lógica dessa função está fortemente acoplada a leitura raster em janelas e contabilidade de pixel por classe, não reutilizável como está para dados vetoriais; `clip_vector_to_country()` é uma implementação nova que segue o mesmo padrão conceitual.
**Ressalva de performance**: não validada contra arquivos reais (HydroLAKES/HydroRIVERS/WDPA em escala global podem ter centenas de milhares a milhões de features) — o fetch real ainda não existe, então não há arquivo real para medir. Sinalizado, não bloqueante.

**Correção de bug encontrada durante o reconhecimento (item 1)**: `_LayerSpec("protected", ...)`'s `country_specific` estava `True` desde a etapa anterior (`2026-08-24 - data_acquisition skeleton`), inconsistente com o próprio achado dessa etapa (`criteria_builder.py::compute_protected_areas` trata WDPA como um único arquivo global recortado por país, igual a `lakes`/`rivers`). Corrigido para `False` em `phase.py`. Nenhum teste dependia do valor antigo (confirmado por grep em `test_data_acquisition_phase.py` antes da correção); um teste novo (`test_run_acquisition_phase_global_layers_have_no_country_code`) agora cobre isso.

**`AuditResult.lakes`/`AuditResult.rivers` (campos `VectorLayerInspection` individuais) substituídos por `AuditResult.vectors: dict[str, VectorLayerInspection]`**, seguindo o mesmo padrão já usado por `rasters: dict[str, RasterInspection]` — evita adicionar 5 campos individuais a mais (`borders`, `admin1`, `grid`, `roads`, `protected`) quando o schema já tinha o padrão de dict-por-nome estabelecido para rasters. `_format_report()` atualizado para iterar `result.vectors` genericamente.

**`VectorLayerInspection` ganhou um campo `error: str | None`**, não pedido explicitamente na lista de campos desta etapa, adicionado por paridade deliberada com `RasterInspection` (que já tem `error`). Motivo: `inspect_vector_layer()` abre o arquivo e pode falhar (arquivo corrompido/formato inválido) — sem um campo `error`, essa falha teria que ou propagar (derrubando a fase inteira de auditoria por causa de um único arquivo vetorial ruim) ou ser silenciosamente engolida em `found=True` sem explicação. Nenhuma das duas opções combina com o objetivo desta etapa ("consistência de profundidade entre todos os vetores do relatório") — `inspect_raster()` já tem exatamente esse tratamento (try/except amplo, `error: str(exc)`), então `inspect_vector_layer()` espelha isso.

**`attribute_breakdown`**: populado só para `protected`, via a mesma lista/ordem de colunas que `criteria_builder.py::compute_protected_areas()` usa (`IUCN_CAT`/`iucn_cat`/`IUCN`/`DESIGNATION`) — reusada, não reinventada (`vector_inspection.py::_iucn_category_breakdown`). Apenas estatística descritiva (count/area/pct por categoria) é calculada aqui; o mapeamento `IUCN_SCORES` (score de exclusão/adequação por categoria) não foi portado — pertence à futura fase `suitability_criteria`, não a esta auditoria (ver entrada `2026-08-24 - protected (WDPA): decisão de onde entra no GeoFREA fica pendente`). Deixado `None` explicitamente para `grid`/`roads` (nenhum schema de tags OSM foi investigado ou inventado nesta etapa) e para `borders`/`admin1`/`lakes`/`rivers` (nenhuma coluna categórica conhecida/relevante para eles nesta etapa).

**Proposta de refatoração de `AuditSummary` (NÃO implementada, aguardando revisão)**: `AuditSummary` hoje é uma lista fixa de campos "flat" (`solar_range`, `elev_range`, ..., mais os campos de land_cover/power_plants) — não tem nenhum campo agregado para os 7 vetores novos. Duas opções para uma futura revisão, não escolhidas aqui:
  1. Adicionar campos flat novos (`n_vector_layers_found`, `n_vector_layers_with_errors`, etc.) — simples, mas expande a lista flat ainda mais.
  2. Trocar a lista flat inteira por `dict[str, ...]` chaveado por nome de layer (rasters + vetores unificados), mais uniforme com `AuditResult.rasters`/`AuditResult.vectors`, mas é uma mudança maior no schema e no consumo em `_format_report()`.
  Nenhuma das duas foi aplicada — `AuditSummary` permanece exatamente como estava antes desta etapa, por instrução explícita.

Justificativa (se METHODOLOGY_REVISION): a auditoria de dados (Fase 1) deve reportar profundidade equivalente para todo dado bruto que o pipeline consome, não só para rasters — um `lakes.shp`/`protected.shp` corrompido ou vazio hoje só aparecia como "found: true, size: X MB", sem indicar se o conteúdo era usável. A extensão fecha essa lacuna de forma simétrica ao que já existia para rasters.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_protected_areas` (padrão de clip + detecção de coluna IUCN); `geoworld_framework/src/processors/data_auditor.py` (confirmação de que `lakes_path`/`rivers_path` nunca eram abertos no legado — mesmo comportamento herdado no GeoFREA até esta etapa); achados da auditoria desta sessão (2026-08-24).

---

## [2026-08-24] - path/paths source-of-truth consolidation
Tipo: METHODOLOGY_REVISION
Descrição: `AcquiredLayer.path` (single-file) vs. `AcquiredLayer.paths` (multi-file, hoje só `land_cover`) tinha duas fontes de verdade independentes desde a etapa `data_acquisition skeleton`: `schemas.py`'s convenção implícita (documentada só em docstring) e `phase.py`'s `_LayerSpec.multi_file: bool`, setado manualmente por entrada do registry (`True` só para `land_cover`). Nada impedia as duas divergirem — coincidiam por enquanto, mas por construção manual, não por garantia estrutural.

Consolidado numa única fonte de verdade: `MULTI_FILE_LAYER_NAMES: frozenset[str] = frozenset({"land_cover"})`, pública em `data_acquisition/schemas.py`. `AcquiredLayer` ganhou um `@model_validator(mode="after")` que rejeita a construção do objeto se `layer_name in MULTI_FILE_LAYER_NAMES` e `path is not None`, ou se `layer_name not in MULTI_FILE_LAYER_NAMES` e `paths` não estiver vazio — a mensagem de erro cita o `layer_name` e qual campo era esperado. `_LayerSpec.multi_file` foi removido de `phase.py`; `run_acquisition_phase()` agora lê `spec.layer_name in MULTI_FILE_LAYER_NAMES` diretamente do módulo de schemas, em vez de uma flag redundante por entrada do registry.

Efeito colateral positivo, não o objetivo principal: um teste do adapter (`test_adapter_land_cover_ignores_a_stray_single_path`) que antes construía um `AcquiredLayer(layer_name="land_cover", path=Path(...), paths=[])` para provar que o adapter ignorava um `path` "perdido" deixou de ser construível — a garantia migrou de "o adapter ignora" para "não pode existir", mais forte. Renomeado para `test_land_cover_with_a_stray_single_path_is_rejected_at_construction`, agora testando `pytest.raises(ValidationError)` em vez do comportamento do adapter. Nenhum outro fixture existente em `tests/unit/test_data_acquisition_*.py` violava a nova regra (revisado por grep de todo `AcquiredLayer(` no repositório antes desta entrada).

Justificativa (se METHODOLOGY_REVISION): eliminar uma classe de bug estrutural (duas fontes de verdade para o mesmo fato, sujeitas a divergir silenciosamente) antes que uma fase de fetch real seja implementada e passe a depender de qual campo popular para cada layer — o mesmo racional já aplicado a `slope_threshold_deg` (per-tecnologia, não fallback duplicado) e à correção de `protected`'s `country_specific` nesta mesma sessão.
Referência (literatura/discussão, se aplicável): instrução explícita de Douglas nesta sessão (2026-08-24); `docs/DECISIONS.md` 2026-08-24 - data_acquisition skeleton (introduziu a assimetria original) e 2026-08-24 - vector layer audit depth (corrigiu `protected`'s `country_specific`, mesma classe de bug de fonte-de-verdade duplicada).

---

## [2026-08-24] - IUCN category normalization fix
Tipo: METHODOLOGY_REVISION
Descrição: `vector_inspection.py::_iucn_category_breakdown` (auditoria de `protected`, ver `2026-08-24 - vector layer audit depth`) agrupava categorias IUCN por valor bruto da coluna, só com `.str.strip()` — sem normalizar case. Isso divergia do legado: `criteria_builder.py::compute_protected_areas()` normaliza com `.str.lower().str.strip()` antes de consultar `IUCN_SCORES`, então `"Not Reported"`/`"not reported"`/`"NOT REPORTED"` sempre foram tratados como a mesma categoria lá. No GeoFREA, sem essa normalização, dados reais (WDPA não é case-consistente) fragmentariam a mesma categoria em múltiplos buckets no `attribute_breakdown`. Corrigido: `.str.lower().str.strip()`, replicando o legado exatamente. Chaves do `attribute_breakdown` (e o campo `name` de cada `VectorAttributeStat`) agora são sempre minúsculas (`"ii"`, `"not reported"`), não a capitalização bruta da coluna.

**Verificação feita antes da correção (relatório, sem código) — achados confirmados contra o legado**:
- `"Not Reported"`/`"Not Applicable"`/`"Not Assigned"` **não são descartados nem agrupados em "outros" nem geram erro** no legado — são entradas próprias em `IUCN_SCORES` (`core/constants.py:179-193`), cada uma com score dedicado (0.25/0.45/0.25), não caem no fallback `IUCN_SCORE_DEFAULT`. O breakdown do GeoFREA já não descartava essas três (isso não mudou nesta correção) — o gap era só a normalização de case.
- Valor de categoria vazio/`NaN` no legado cai silenciosamente em `IUCN_SCORE_DEFAULT` via `dict.get(nan, default)`, sem receber rótulo nenhum. O GeoFREA rotula como `"unknown"` (`.fillna("unknown")`) — uma convenção própria do GeoFREA, sem equivalente direto no legado, mantida como estava (não é uma decisão de score, só a chave necessária para agrupar). Documentado explicitamente no docstring de `_iucn_category_breakdown` para rastreabilidade quando `suitability_criteria` for desenhada — pode não ser o rótulo que essa fase futura vai querer usar.

**Não portado nesta correção**: `IUCN_SCORES`/`IUCN_SCORE_DEFAULT`/`IUCN_FREE_SCORE` continuam fora do GeoFREA — `attribute_breakdown` permanece só estatística descritiva (`count`/`area_km2`/`pct`), sem nenhum campo de score. `VectorAttributeStat` (schema) não foi alterado. O mapeamento de score/exclusão fica para a futura fase `suitability_criteria`, mesma decisão já registrada em `2026-08-24 - protected (WDPA): decisão de onde entra no GeoFREA fica pendente`.

Justificativa (se METHODOLOGY_REVISION): sem a normalização de case, o breakdown por categoria produziria contagens/áreas fragmentadas incorretamente assim que dados WDPA reais (tipicamente inconsistentes em capitalização) forem carregados — um bug latente que só não apareceu ainda porque nenhum fetch real existe. Corrigido antes que dados reais cheguem, não depois.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_protected_areas` e `core/constants.py::IUCN_SCORES` (fonte da normalização replicada); instrução explícita de Douglas nesta sessão (2026-08-24, verificação prévia + correção).

---

## [2026-08-24] - AuditSummary refactor to layer-keyed dict
Tipo: METHODOLOGY_REVISION
Descrição: `AuditSummary` (`data_quality_audit/schemas.py`) trocou seus campos flat (`layers_ok`, `layers_missing`, `n_wind_files`, `solar_range`, `elev_range`, `slope_range`, `pop_range`, `seismic_range`) por um único campo `layers: dict[str, RasterLayerSummary | VectorLayerSummary]`, chaveado pelo mesmo namespace de `AuditResult.rasters` (6 nomes) + `AuditResult.vectors` (7 nomes) — 13 chaves, interseção vazia confirmada por grep antes da implementação. `land_cover`/`power_plants` **não** entram em `layers` — permanecem campos dedicados (`lc_tiles_used`, `lc_tiles_total`, `lc_total_area_km2`, `lc_classes`, `total_plants`, `total_cap_mw`), espelhando a própria estrutura de `AuditResult`, que também não funde `land_cover`/`power_plants` em `rasters`/`vectors`.

**Design escolhido — união discriminada, não schema genérico**: `RasterLayerSummary` (`kind="raster"`, `status: Literal["ok","missing"]`, `error`, `value_range`, `file_count`) e `VectorLayerSummary` (`kind="vector"`, `status: Literal["ok","missing","error"]`, `error`, `n_features`), unidos via `Annotated[RasterLayerSummary | VectorLayerSummary, Field(discriminator="kind")]`. Rejeitei um schema genérico único (opção b) porque os dados por camada têm formas genuinamente diferentes (raster tem um range numérico; vetor não tem range, mas tem `n_features`) — forçar os dois num schema comum resultaria num superset com metade dos campos sempre `None` dependendo do tipo, sem ganho real (o detalhe completo já vive em `AuditResult.rasters`/`.vectors`; o `summary` existe só para ser conciso). O padrão de `Literal` como discriminador já é usado no projeto (`AcquiredLayer.provenance`), então a união discriminada é consistente com convenções existentes, não uma novidade.

**Assimetria `status` raster (2 estados) vs. vetor (3 estados) — preservada, não inventada**: `RasterInspection` só tinha `error`/sem `error` (nunca distinguia "arquivo não encontrado" de "arquivo encontrado mas ilegível" no schema antigo de summary); `VectorLayerInspection` já tinha essa distinção tri-estado (`found` + `error` separados) desde a entrada `2026-08-24 - vector layer audit depth`, e `_format_report()`'s seção VECTOR LAYERS já usava essa distinção antes desta refatoração. `RasterLayerSummary.status` replica o binário existente; `VectorLayerSummary.status` replica o tri-estado existente. Nenhum dos dois foi expandido/reduzido — cada um manteve exatamente a granularidade que já tinha em outro lugar do código.

**`wind`'s assimetria de range — preservada, não corrigida**: no schema flat antigo, `wind` nunca teve um `*_range` (o `range_map` de `_build_summary()` nunca incluía `"wind"`, apesar de `wind` passar pelo mesmo `inspect_raster()` que solar/elevation/etc). Essa assimetria pré-existente foi mantida — `RasterLayerSummary.value_range` fica `None` para `wind` mesmo quando a inspeção tem sucesso; em vez disso, `wind` ganha `file_count` (substituto direto do antigo campo solto `n_wind_files`, `len(AuditInputs.wind_paths)`). Não investigada/corrigida nesta etapa — fora de escopo.

**Mudança de comportamento do relatório (rodapé/SUMMARY), não só refactor de schema — ver nota de correção abaixo**: a seção SUMMARY do relatório (`_format_report()`) foi reescrita para ler de `result.summary.layers` em vez de `result.vectors` diretamente. Efeitos visíveis:
1. As linhas por-layer-vetorial (`Borders (GADM)`, `HydroLAKES`, etc., `[OK] found` / `[--] missing`) agora ganham um terceiro estado possível, `[ERROR] found (unreadable)`, quando `VectorLayerSummary.status == "error"` — antes, essas linhas só distinguiam found/missing (o `found: bool` binário), mesmo já existindo a distinção tri-estado em `VectorLayerInspection` (usada só na seção VECTOR LAYERS detalhada, não no rodapé).
2. As linhas "Layers OK"/"Layers missing" — que antes cobriam **só rasters** (`_build_summary()` só populava `layers_ok`/`layers_missing` a partir do dict `rasters`, nunca de `vectors`) — agora cobrem as 13 chaves combinadas (raster+vetor). Um layer vetorial com `status="error"` conta como "missing" nessas duas linhas especificamente (a distinção error/missing continua visível nas linhas individuais por-layer e na seção VECTOR LAYERS completa).

**Nota de correção**: a instrução original desta tarefa pedia para registrar que "os 7 layers vetoriais aparecem no rodapé pela primeira vez" — verificado contra o código antes de implementar (`grep -n "_VECTOR_LABELS" audit.py`) e **isso não é factualmente correto**: os vetores já apareciam nas linhas `found`/`missing` do SUMMARY desde a entrada `2026-08-24 - vector layer audit depth` (mesmo dia, etapa anterior), só que lendo `result.vectors` diretamente, não via `AuditSummary`. O que de fato é novo: (a) a fonte dessas linhas passa a ser `AuditSummary.layers` em vez de `result.vectors`; (b) essas linhas ganham o terceiro estado `error`; (c) as linhas "Layers OK"/"Layers missing" passam a incluir vetores pela primeira vez (essas sim eram raster-only antes). Reportado a Douglas antes da implementação; registrado aqui com a redação corrigida.

**Migração dos testes**: `tests/unit/test_audit.py` — os 3 acessos a `result.summary.layers_ok`/`layers_missing` foram atualizados para `result.summary.layers[...].status`/`.kind`; nenhum alias/campo depreciado foi mantido (grep de consumidores antes da implementação confirmou zero uso fora de `audit.py` e `test_audit.py` — migração limpa, sem período de transição). Teste novo cobrindo o texto formatado real do rodapé (não só o shape do schema) para 1 raster (`elevation`, range numérico) e 1 vetor (`lakes`, `[OK] found`), incluindo a linha consolidada "Layers OK".

Justificativa (se METHODOLOGY_REVISION): fecha a pendência registrada em `docs/PROGRESS.json` (`audit_summary_vector_refactor_proposta`) — o `AuditSummary` estava desatualizado desde a extensão da auditoria vetorial (7 layers novos sem nenhum rollup correspondente no summary). A união discriminada evita tanto duplicar o detalhe completo já disponível em `AuditResult` quanto forçar formas de dado incompatíveis (range numérico vs. contagem de features) num schema genérico.
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-24 - vector layer audit depth (origem da lacuna); instrução explícita de Douglas nesta sessão (2026-08-24), incluindo a decisão aprovada de design (a) e escopo de 13 layers.

---

## [2026-08-25] - real fetchers for power_plants/wind/lakes/rivers
Tipo: METHODOLOGY_REVISION
Descrição: implementados fetchers reais para 4 das 14 camadas de `data_acquisition` (`power_plants`, `wind`, `lakes`, `rivers`), cada um verificado ao vivo com `curl`/execução real do código Python antes de escrever qualquer teste — não portados do legado (que não tinha código de fetch nenhum para essas 4), escritos do zero contra o schema atual (`AcquiredLayer`, `path`/`paths`, `MULTI_FILE_LAYER_NAMES`, `provenance`). `provenance` das 4 mudou de `local_only` para `fetched` no `_LAYER_REGISTRY` (`phase.py`) — decisão metodológica, não só técnica, porque muda o que o resto do pipeline pode assumir sobre a origem do dado.

**Por que fetch por FONTE, não por padrão de auth (decisão (a), fechada nesta sessão, não reaberta)**: pesquisa anterior (2026-08-24) mostrou que das 5 fontes com fetch real no legado, 4 não tinham autenticação nenhuma (GADM, Copernicus, WorldPop, Overpass) e eram 4 protocolos totalmente diferentes entre si (HTTP+ZIP, S3 via lib especializada, FTP anônimo, HTTP POST+Overpass QL) — organizar por padrão de auth juntaria essas 4 num bucket sem nenhum reuso de código real. Todo o reuso que o legado já demonstrava na prática (fallback de fonte, versionamento de dataset, estratégia de tiling) já era organizado implicitamente por fonte. Esta etapa implementa exatamente essa estrutura: `src/geofrea/data_acquisition/fetchers/` tem um módulo por fonte (`power_plants.py` = WRI, `wind.py` = Global Wind Atlas, `hydrosheds.py` = HydroLAKES **e** HydroRIVERS juntos, já que são a mesma fonte, `protected_planet.py` = Protected Planet), não um módulo por camada nem por tipo de auth. O único código genuinamente cross-source é `core/http_retry.py` (retry HTTP genérico, adaptado de `DataFetcher._request_with_retry()` do legado) — cross-cutting de transporte, ortogonal à decisão (a) vs (b), não uma exceção a ela.

**`power_plants` — commit SHA fixado, não `master`**: o repositório `wri/global-power-plant-database` está sem manutenção desde 2022 (confirmado lendo a mensagem do último commit via API do GitHub: "Update version to 1.3.0, announce project status ... This may be a final commit to this project"). Essa versão (v1.3.0, a atual/correta) nunca foi taggeada como release — só existem tags `v1.0.0`/`v1.1.0`, snapshots de 2018 muito menores e desatualizados. Fixamos o SHA `7a91cfbb2a4e272597acbc00506d61fc1ec73b3d` (o commit exato dessa mensagem) em vez de `master`: verificado que o conteúdo é byte-idêntico ao de `master` no momento da verificação (mesmo `Content-Length`, mesmo `ETag`), então fixar não muda nada agora, só impede que o fetch mude sob nós se o repo for tocado de novo no futuro.

**`lakes`/`rivers` — tiles regionais para rivers, arquivo global para lakes (assimetria real, não escolha arbitrária)**: verificado ao vivo antes de codar (`curl` contra `data.hydrosheds.org`) que HydroRIVERS tem 9 tiles continentais reais e funcionais (`af`/`ar`/`as`/`au`/`eu`/`gr`/`na`/`sa`/`si`) — testados `eu` (67.6 MB, cobre PRT) e `sa` (95.3 MB, cobre BRA) — muito menores que o arquivo global (618 MB). HydroLAKES **não tem** tiles regionais — confirmado por 404 em todas as tentativas do mesmo padrão de URL, e pela própria página do produto só oferecer o arquivo único. Pausei e perguntei a Douglas antes de decidir (não assumi sozinho): decisão dele (2026-08-25, ao vivo) foi usar o arquivo global de 820 MB para `lakes`, sem alternativa por tile. Mapeamento país→região do HydroRIVERS (`_COUNTRY_TO_REGION` em `hydrosheds.py`) cobre só PRT (`eu`) e BRA (`sa`) hoje — é inerente ao próprio esquema de tiling da fonte (por continente, não por país), não uma limitação inventada pelo GeoFREA; expandir para um novo país exige adicionar uma entrada nesse dict.

**`protected` — fetcher completo implementado, `provenance` NÃO promovida a `fetched`**: `fetchers/protected_planet.py` implementa a busca paginada real (`GET /v4/protected_areas/search?country=ISO3`, até 50 resultados/página, param `token`), lê o token de `PROTECTED_PLANET_API_TOKEN` (env var) e levanta `ProtectedPlanetTokenMissingError` com mensagem clara (URL de registro + nome da env var + lembrete de que a API é paginada e por país, não bulk) se ausente — nunca hardcoda nem pede token interativamente. Verificado ao vivo que a API existe de verdade (`{"error": "Unauthorized. Invalid or expired token."}`, não um 404) — o legado estava errado em dizer "sem API bulk" (existe API, só que gated e paginada, nunca um dump único). `_LAYER_REGISTRY["protected"].provenance` continua `"local_only"` — o fetcher está pronto e testado (mocks), mas não é chamado por `run_acquisition_phase()` (não está em `_FETCHED_LAYER_HANDLERS`), porque depende de um token pessoal obtido manualmente por Douglas fora deste código. Ativação manual, quando decidida:

1. Registrar em `api.protectedplanet.net/request` e obter o token pessoal.
2. Definir `PROTECTED_PLANET_API_TOKEN` no ambiente.
3. Em `src/geofrea/data_acquisition/phase.py`: mudar `_LayerSpec("protected", "local_only", ...)` para `"fetched"` no `_LAYER_REGISTRY`.
4. Adicionar `"protected": lambda ctx: fetch_protected_areas(ctx.outputs_dir, ctx.country_code)` a `_FETCHED_LAYER_HANDLERS` (mesmo padrão dos outros 4).

Isso não é auto-ativação — é o passo a passo para quando Douglas decidir ativar manualmente, não implementado automaticamente aqui.

**`solar`/`seismic` — fora de escopo nesta etapa, permanecem `local_only`**: a pesquisa anterior confirmou uma API real para Global Solar Atlas (`api.globalsolaratlas.info`, sem auth, testada com sucesso para o arquivo mundial de PVOUT), mas o padrão de URL por país não foi decifrado (múltiplas tentativas de nomenclatura retornaram vazio/404 — precisaria inspecionar tráfego real de navegador, fora do que dá para fazer só com `curl`). `seismic` nunca teve fonte identificada em lugar nenhum do legado (só o nome de arquivo esperado, `seismic_hazard_global.tif`, sem URL nem citação de proveniência real além de "GAR / USGS" sem link). Nenhuma das duas foi implementada — nenhuma mudança de código, `provenance` continua `local_only`, registrado como pendência explícita (não esquecida) em `docs/PROGRESS.json`.

**Comportamento de falha**: cada fetcher captura suas próprias falhas de rede/parsing internamente e retorna `None` (não levanta) — uma camada com falha de fetch não aborta a fase de aquisição inteira, mesmo padrão já estabelecido em `data_quality_audit`'s `inspect_raster()`/`inspect_vector_layer()`. A única exceção deliberada: `hydrosheds.fetch_rivers()` levanta `KeyError` para um país fora de `_COUNTRY_TO_REGION` — isso é uma lacuna de configuração, não uma falha transitória, então deve falhar a fase alto (via `PhaseExecutionError` do `Orchestrator`), não degradar silenciosamente para `path=None`.

**Dependência nova**: `requests>=2.31` adicionada a `pyproject.toml` — nenhum fetcher legado real usava um SDK além de `requests`/`ftplib`/bibliotecas especializadas (`terracatalogueclient`, `dem_stitcher`), e nenhuma dessas 4 fontes precisa de SDK dedicado (todas são HTTP simples).

Justificativa (se METHODOLOGY_REVISION): fecha 4 das 7 lacunas `local_only` da auditoria de `2026-08-24 - data_acquisition skeleton` com fontes reais, verificadas ao vivo, não assumidas a partir de documentação legada (que se provou errada em vários pontos — ver pesquisa anterior). Reduz o número de camadas dependentes de dado manual de 7 para 3 (`protected`, `solar`, `seismic`).
Referência (literatura/discussão, se aplicável): pesquisa anterior desta sessão (2026-08-24, mapeamento fonte-por-camada + comparação (a) vs (b)) e verificação ao vivo desta etapa (2026-08-24/25, `curl` contra `raw.githubusercontent.com`, `globalwindatlas.info/api`, `data.hydrosheds.org`, `api.protectedplanet.net`); `geoworld_framework/src/io/data_fetcher.py` (padrão de retry HTTP adaptado, não copiado); instrução explícita de Douglas nesta sessão (2026-08-25), incluindo a decisão ao vivo sobre `lakes` usar o arquivo global.

---

## [2026-08-25] - data_acquisition activation
Tipo: METHODOLOGY_REVISION
Descrição: ativação real do wiring `data_acquisition` -> `data_quality_audit`, antes bloqueado por `main.py`'s `UnwiredPhasesError` (ver `2026-08-24 - data_acquisition skeleton`). Quatro mudanças, nesta ordem de dependência: (1) decisão sobre `UnwiredPhasesError` — reportada e justificada por escrito antes do código, conforme instrução explícita de Douglas; (2) `settings.yaml` ganhou a chave `data_acquisition` em `run.phases` (`false` por padrão, mesmo padrão dos outros 9 toggles); (3) `main.py`'s fase de audit trocou de `functools.partial(run_audit_phase, inputs=AuditInputs())` (eager, sempre vazio) para uma closure por-contexto (`_audit_run`) que lê `context.prior_results["data_acquisition"].output` de verdade via `acquisition_result_to_audit_inputs()` (adapter já existente e testado desde a etapa anterior); (4) validação com dados reais (item explicitamente pedido por Douglas antes de aceitar a etapa como concluída) encontrou um bug real de compatibilidade nos fetchers de `lakes`/`rivers` (não um problema de performance) e, a partir da correção desse bug, Douglas decidiu ao vivo uma otimização de performance a ser aplicada como convenção geral, não só para `lakes`/`rivers`.

**Decisão sobre `UnwiredPhasesError` — REMOVIDO, não relaxado, não mantido por outro motivo**: a única justificativa da guarda (ver seu próprio docstring) era que habilitar as duas fases juntas faria `data_quality_audit` rodar "silenciosamente contra nada", já que `AuditInputs` era sempre `AuditInputs()` vazio independente do que `data_acquisition` produzisse. Com o wiring real desta etapa isso deixa de ser verdade: paths reais das 4 camadas com fetch (`power_plants`/`wind`/`lakes`/`rivers`) chegam ao audit; as demais 10 camadas chegam como `None` — não por bug, mas porque genuinamente não têm fetch ainda (esqueleto ou `local_only` deliberado). `inspect_raster()`/`inspect_vector_layer()` já tratam ausência graciosamente (`found=False`, sem erro), que é exatamente a função de um audit: reportar o que falta, não escondê-lo. Rodar as duas fases juntas agora produz um resultado honesto e correto — não é mais "auditar o nada", é a integração pretendida; manter o bloqueio impediria validar end-to-end o código real que a etapa anterior implementou. Alternativa de relaxar para um `logger.warning()` foi considerada e rejeitada: seria só ruído para camadas já rastreadas como pendência conhecida em `docs/PROGRESS.json` — não existe mais nenhum caso real de "audit enganoso" para avisar. `_build_phase_specs()` também perdeu o parâmetro `phases_enabled` (única razão de existir era essa checagem) em vez de ser mantido sem uso "para o futuro" — parâmetro especulativo não seria consistente com a disciplina do projeto contra código não usado.

**Achado real durante a validação com dados reais (não uma medição de performance — um bug de compatibilidade)**: ao rodar `fetch_lakes()`/`fetch_rivers()` de verdade (não mockado) e então tentar `gpd.read_file()` no `.zip` baixado — exatamente o que `vector_inspection.py::inspect_vector_layer()` já fazia em produção desde `2026-08-25 - real fetchers for power_plants/wind/lakes/rivers` — a leitura falhou com `pyogrio.errors.DataSourceError: not recognized as being in a supported file format`, confirmado ao vivo para os dois downloads reais (HydroLAKES 820MB e HydroRIVERS tile `eu`). Causa: os zips do HydroSHEDS aninham o shapefile uma pasta abaixo (ex.: `HydroLAKES_polys_v10_shp/HydroLAKES_polys_v10.shp`) e incluem um arquivo alheio no nível raiz (um PDF de documentação técnica) — a auto-detecção `/vsizip/` do GDAL, da qual `gpd.read_file(zip_path)` depende, não localiza o shapefile de forma confiável nesse layout. Isso era um bug latente na etapa anterior (`2026-08-25 - real fetchers...`), invisível até existir dado real para testar contra — todo teste/fixture anterior de `lakes`/`rivers` usava GeoJSON sintético, nunca um zip real. Corrigido em `fetchers/hydrosheds.py`: `_fetch_and_extract_shapefile()` agora extrai o zip uma vez no momento do fetch e retorna o path direto para o `.shp` (não uma string `zip://...!...`/`/vsizip/...` — isso só moveria o conhecimento do layout interno do HydroSHEDS para dentro de `inspect_vector_layer()`, que é genérica para 7 camadas vetoriais e não deveria precisar saber disso). Idempotência agora verifica o `.shp` já extraído (não só o `.zip`); um rerun após extração bem-sucedida não faz I/O nenhum, e um rerun após um download que terminou mas travou antes da extração reaproveita o zip já baixado em vez de rebaixar.

**Decisão de Douglas sobre performance, tomada ao vivo durante esta etapa — bbox no read + cache do clip, combinados, como convenção geral**: perguntado sobre como evitar que a leitura do HydroLAKES real (820MB, ~1,4M feições) fosse lenta em execuções futuras — tanto para `lakes`/`rivers` quanto para qualquer camada futura com arquivo global grande — Douglas decidiu combinar duas técnicas em vez de escolher uma: (1) filtro por bbox no momento da leitura (`gpd.read_file(path, bbox=...)`, usando o índice espacial do próprio arquivo — confirmado via `pyogrio.read_info()`'s `fast_spatial_filter: True` para os shapefiles do HydroSHEDS) em vez de carregar o arquivo inteiro para só depois aplicar `clip_vector_to_country()`'s próprio prefiltro `.cx[]`; (2) cache em disco do resultado já clipado, por país e por camada, para que o arquivo global grande seja lido no máximo uma vez por país, não uma vez por execução de audit. Implementado como:
- `core/geo_utils.py::read_clipped_to_country(path, country_gdf)` — nova função, não substitui `clip_vector_to_country()` (que continua servindo quem já tem um GeoDataFrame em memória); resolve o CRS do arquivo via `pyogrio.read_info()` (só metadado, sem ler feições) para computar o bbox no CRS certo antes de qualquer leitura, depois lê com `bbox=` e aplica `clip_vector_to_country()` no resultado, já bem menor.
- `data_quality_audit/vector_inspection.py::inspect_vector_layer()` ganhou o parâmetro `cache_path` (opcional, `None` por padrão — comportamento antigo preservado para quem não o passa). Quando dado e `clip=True` com `country_gdf`, um cache-hit pula a leitura do arquivo-fonte inteiramente; um cache-miss lê via `read_clipped_to_country()` e grava o resultado em GeoPackage. Falha ao escrever o cache é logada e engolida, não propagada — cache é uma otimização pura, não deve transformar uma inspeção bem-sucedida em erro.
- `audit.py` só calcula/passa `cache_path` para as 3 camadas `clip=True` (`protected`/`lakes`/`rivers`) — as `clip=False` (`borders`/`admin1`/`grid`/`roads`) já são arquivos pequenos e país-específicos na própria fonte, nada ali precisa da otimização.
- Invalidação de cache é manual (apagar o arquivo) — mesma convenção que os próprios fetchers de `data_acquisition` já usam para sua idempotência (`if dest_path.exists(): return dest_path`, sem checagem de staleness); não é uma convenção nova inventada aqui.

**Convenção estabelecida para o futuro (instrução explícita de Douglas, não uma escolha só para `lakes`/`rivers`)**: qualquer camada futura que precise ler um arquivo global grande e clipar por país deve usar esta mesma combinação (`read_clipped_to_country()` + `cache_path` em `inspect_vector_layer()`, ou o equivalente se a camada não passar por essa função) — não decidir caso a caso se a próxima camada grande "merece" a otimização.

**Addendum (2026-08-25) — duas limitações da convenção acima, registradas explicitamente para não serem lidas como "problema resolvido" sem ressalva**:

1. **Cache resolve reexecução, não resolve cold start.** O primeiro clip de cada combinação país/camada ainda paga o custo integral de ler o arquivo global inteiro pela primeira vez — o cache só evita pagar esse custo de novo numa segunda execução. Se `outputs/` for limpo (CI do zero, ambiente novo, ou um país novo sendo adicionado ao `_COUNTRY_TO_REGION`/equivalente), o custo do cold start volta por inteiro, sem atalho. Não é uma limitação inventada agora — é inerente à própria ideia de cache — mas fica registrada aqui para que a convenção não seja lida como "arquivos grandes deixaram de ser lentos", quando na verdade só a *repetição* do custo foi eliminada.
2. **O filtro bbox em `gpd.read_file(path, bbox=...)` só é rápido se o arquivo tiver índice espacial.** Confirmado para os shapefiles do HydroSHEDS via `pyogrio.read_info(path)["capabilities"]["fast_spatial_filter"] == True` (índice `.sbn`/`.sbx` do próprio shapefile) — isso NÃO é uma garantia universal de todo formato/arquivo. Sem índice espacial, `bbox=` no `gpd.read_file()` ainda retorna o resultado correto (GDAL filtra na leitura de qualquer forma), mas sem acelerar nada — o arquivo inteiro é varrido linha a linha da mesma forma que `clip_vector_to_country()`'s próprio prefiltro `.cx[]` já fazia antes desta etapa. Antes de aplicar esta mesma receita (`read_clipped_to_country()` + `cache_path`) a um shapefile/fonte futura, confirmar via `pyogrio.read_info()` que `fast_spatial_filter` é `True` para aquele arquivo específico — se não for, o ganho de performance esperado pode simplesmente não existir, e vale reavaliar a abordagem (ex.: converter para um formato com índice, como GeoPackage, antes de clipar) em vez de assumir que a convenção "funciona sempre".

**Medição real (dados reais, não mockados) — HydroLAKES/HydroRIVERS para PRT e BRA**: `lakes`/PRT, `rivers`/PRT e `lakes`/BRA completaram com sucesso via fetch real + `read_clipped_to_country()` + `cache_path` (arquivos de cache confirmados em disco: `outputs/PRT/processed/{lakes,rivers}_clipped.gpkg`, `outputs/BRA/processed/lakes_clipped.gpkg`, este último com 21.107 feições). Os tempos exatos de cada etapa NÃO foram capturados com precisão — o script de validação usava `print()` sem `flush=True`/`-u`, cujo output ficou bufferizado e se perdeu quando o processo precisou ser encerrado (ver abaixo); só é possível afirmar que os três completaram dentro de uma janela de ~15 minutos de execução real (12:44–12:59). Esse mesmo problema de buffering é o que motivou a convenção de logging com ETA registrada em `2026-08-25 - clip_vector_to_country() exact-intersection bottleneck (STRtree + simplify + threading)` — não foi corrigido retroativamente para essas três medições, só para as seguintes. `rivers`/BRA NÃO completou nesta mesma rodada — travou por 2h21min sem terminar, ~12x acima do tempo de `lakes`/BRA; ver a entrada dedicada abaixo para o diagnóstico completo, a correção, e os números reais medidos com o problema de buffering já corrigido.

Justificativa (se METHODOLOGY_REVISION): fecha a pendência de wiring registrada desde `2026-08-24 - data_acquisition skeleton` e a ressalva de performance registrada em `2026-08-24 - vector layer audit depth` ("não validada contra arquivos reais... sinalizado, não bloqueante") — ambas resolvidas nesta etapa com dados reais, não assumidas.
Referência (literatura/discussão, se aplicável): instrução explícita de Douglas nesta sessão (2026-08-25), incluindo a decisão ao vivo de combinar bbox-no-read + cache como convenção geral; `docs/DECISIONS.md` 2026-08-24 - vector layer audit depth (origem da ressalva de performance) e 2026-08-24 - data_acquisition skeleton (origem do bloqueio de wiring); validação ao vivo desta etapa contra HydroLAKES/HydroRIVERS reais e limites GADM (`database/raw/countries_borders/`, referência read-only) para PRT/BRA.

---

## [2026-08-25] - solar (Global Solar Atlas): padrão de URL per-country decifrado
Tipo: VERIFICATION_UPDATE
Descrição: a pendência registrada em `docs/PROGRESS.json` (`solar_fetch_per_country_nao_confirmado`) — fonte confirmada, mecanismo por país não decifrado — está resolvida. Verificado ao vivo (`curl`, 2026-08-25): `api.globalsolaratlas.info` expõe um endpoint de CATÁLOGO, não só de download direto, exatamente a hipótese que Douglas pediu para investigar: `GET /download/{NomeDoPaísEmInglês}` (title-case, ex. `Portugal`, `Brazil` — ISO3 e nomes em minúsculo retornam `[]` vazio, não erro) retorna um JSON listando os arquivos reais disponíveis para aquele país (nome, tamanho, data). Cada entrada tem um nome de arquivo real (ex. `Portugal_GISdata_LTAy_YearlyMonthlyTotals_GlobalSolarAtlas-v2_GEOTIFF.zip`) que não segue um padrão adivinhável — por isso as tentativas anteriores (`World_PVOUT_...`, `Portugal_PVOUT_...`) falhavam: precisavam do catálogo primeiro, não dava para adivinhar o nome do arquivo direto. `GET /download/{País}/{filename}` (o nome exato retornado pelo catálogo) responde com redirect 302 para uma URL assinada da S3 (`worldbank-atlas.s3.us-east-1.amazonaws.com`, `X-Amz-Expires=900`), sem autenticação — mesmo padrão "302 → S3 assinado" já confirmado para o arquivo mundial na pesquisa anterior.

**Confirmado com download real, não só a resposta do catálogo**: baixado `Portugal_GISdata_LTAy_YearlyMonthlyTotals_GlobalSolarAtlas-v2_GEOTIFF.zip` (25,7MB) via o redirect acima. Zip contém `PVOUT.tif` de verdade (junto de `GHI`/`DNI`/`DIF`/`GTI`/`TEMP`/`OPTA.tif` anuais + 12 `PVOUT_MM.tif` mensais + `.xml`/`.pdf`/`.aux.xml` de metadado/documentação/preview) — aberto com `rasterio` via `/vsizip/`: `EPSG:4326`, shape `(1680, 3120)`, bounds cobrindo Portugal continental + Açores/Madeira (-32 a -6 lon, 29 a 43 lat), valores válidos 925,5–1761,6 (`nodata=1.1754943508222875e-38`, um float32 subnormal, não `NaN`/`-9999` — atenção para quem for implementar o fetch).

**Achado adicional relevante, não pedido mas descoberto durante a verificação**: os valores de PVOUT confirmados (925–1762, média 1550) são consistentes com **kWh/kWp/ano** (specific yield anual), não kWh/m²/dia. O próprio `audit.py`'s `_SOLAR_PVOUT_SANITY_RANGE = (1.0, 10.0)  # kWh/m2/day` e seu alerta ("Is the file in kWh/kWp/yr?") já antecipam exatamente esse cenário — ou seja, o arquivo real da Global Solar Atlas, se fetchado como está, dispararia esse alerta de unidade incorreta. Isso não é um bug a corrigir agora (nenhum fetch foi implementado) — é uma informação que quem for ativar o fetch de `solar` no futuro precisa saber: ou a fase de audit precisa de uma branch de unidade diferente para `solar`, ou o zip da GSA tem outro arquivo em kWh/m²/dia que não foi verificado nesta investigação (o zip "AvgDailyTotals" listado no catálogo não foi baixado/inspecionado — só o "YearlyMonthlyTotals").

**Não implementado**: nenhum código de fetch para `solar` foi escrito nesta etapa (instrução explícita de Douglas) — `provenance` continua `local_only`, `_LAYER_REGISTRY` inalterado. Este é só o resultado da investigação, para autorização futura decidir se/como implementar.
Justificativa (se METHODOLOGY_REVISION): N/A (VERIFICATION_UPDATE).
Referência (literatura/discussão, se aplicável): instrução explícita de Douglas nesta sessão (2026-08-25, tarefa B: decifrar padrão per-country do Global Solar Atlas); verificação ao vivo via `curl` contra `api.globalsolaratlas.info` e download real + inspeção via `rasterio` do zip de Portugal; pesquisa anterior desta sessão (2026-08-24, confirmação do endpoint mundial sem auth) e `docs/PROGRESS.json`'s `solar_fetch_per_country_nao_confirmado`.

---

## [2026-08-25] - seismic: fonte identificada (GEM Global Seismic Hazard Map v2023.1)
Tipo: VERIFICATION_UPDATE
Descrição: a pendência registrada em `docs/PROGRESS.json` (`seismic_fonte_nao_identificada`) está resolvida. O arquivo local `D:\Douglas\DOUTORADO\database\raw\risks\seismic_hazard_global.tif` (usado pelo legado — `data_manager.py::load_seismic_data()` — para gerar `PRT_seismic_aligned.tif`/`BRA_seismic_aligned.tif` e, downstream, `seismic_suitability.tif` já presente no baseline `outputs_baseline_fc7b43d`) tem, na MESMA pasta, `README.txt` e `LICENSE.txt` que identificam a fonte sem ambiguidade: **GEM (Global Earthquake Model) Foundation, "Global Seismic Hazard Map", versão 2023.1** — Peak Ground Acceleration (PGA), fração de g, 10% de probabilidade de excedência em 50 anos, condição de rocha de referência (Vs30 760–800 m/s), licença CC BY-NC-SA 4.0 (NÃO permite uso comercial). Isso diverge do texto vago do README do legado ("GAR / USGS source") — nem GAR (Global Assessment Report da UNDRR) nem USGS isoladamente é o nome correto; é um produto do GEM Foundation especificamente, hospedado em `globalquakemodel.org`.

**Confirmado tecnicamente, não só pelo texto do README/LICENSE**: `rasterio` no `.tif` local confirma `EPSG:4326`, shape `(3000, 7200)`, resolução ~0.05° (~6km, batendo com o "~6 km spacing" citado no `README.txt`), extensão global (-180/-60 a 180/90), `dtype=float64`. Consistente com um raster de hazard PGA global, não um dataset regional/diferente sendo confundido.

**Fonte pública encontrada (WebSearch, não baixada/usada nesta etapa)**: o dataset está publicado no Zenodo — `GEM-GSHM_PGA-475y-rock_v2023.zip` (34,6MB), DOI em `zenodo.org/records/8409647` (v2023.1.0) — existe também uma revisão posterior `zenodo.org/records/10034133` (v2023.1.2); o `README.txt` local cita só "version 2023.1" sem terceiro dígito, então `8409647` é o candidato mais próximo, não confirmado byte-a-byte contra o arquivo local nesta etapa.

**Bloqueio explícito, conforme instrução de Douglas**: mesmo com a fonte identificada, NENHUM fetch foi implementado. A licença CC BY-NC-SA 4.0 (NonCommercial) é uma consideração adicional que fetch automatizado precisaria respeitar (atribuição obrigatória, uso não-comercial) — não avaliado/decidido aqui, só registrado para quando a decisão de implementar for tomada. `provenance` de `seismic` continua `local_only`, `_LAYER_REGISTRY` inalterado.
Justificativa (se METHODOLOGY_REVISION): N/A (VERIFICATION_UPDATE).
Referência (literatura/discussão, se aplicável): instrução explícita de Douglas nesta sessão (2026-08-25, tarefa C: identificar fonte real de `seismic`); `database/raw/risks/README.txt`+`LICENSE.txt` (referência read-only, achados junto ao arquivo raw já em uso pelo legado); inspeção técnica via `rasterio`; busca web (2026-08-25) confirmando disponibilidade pública no Zenodo; `docs/PROGRESS.json`'s `seismic_fonte_nao_identificada`.

---

## [2026-08-25] - seismic: fetch automatizado descartado por restrição de licença
Tipo: METHODOLOGY_REVISION
Descrição: com a fonte identificada (`2026-08-25 - seismic: fonte identificada`, GEM Global Seismic Hazard Map v2023.1, CC BY-NC-SA 4.0), Douglas decidiu NÃO implementar fetch automatizado para `seismic` — decisão de uso, não uma lacuna técnica. `seismic` continua sendo usado da forma como já era: arquivo local pré-posicionado em `database/raw/risks/seismic_hazard_global.tif`, `provenance="local_only"` no `_LAYER_REGISTRY` (`phase.py`), sem mudança de código nesta camada. Diferente de `protected` (fetcher pronto mas gated por token manual, ativação é só uma questão de credencial) — aqui a decisão é definitiva para esta fonte: mesmo que um caminho técnico de download exista (Zenodo, confirmado na entrada anterior), a licença NonCommercial (CC BY-NC-SA 4.0) foi o motivo determinante para não automatizar.
Justificativa (se METHODOLOGY_REVISION): a licença CC BY-NC-SA 4.0 do GEM Foundation restringe uso a fins não-comerciais e exige atribuição/ShareAlike — automatizar o fetch (download silencioso a cada execução do pipeline) levanta questões de conformidade de licença que Douglas prefere não resolver via automação; manter a aquisição manual/local, como já era feito, evita esse risco sem custo real (o arquivo já está presente e funcionando desde antes desta sessão).
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-25 - seismic: fonte identificada (GEM Global Seismic Hazard Map v2023.1); instrução explícita de Douglas nesta sessão (2026-08-25).

---

## [2026-08-25] - solar: unidade do PVOUT — arquivo já em uso confere, achado de risco para fetch futuro
Tipo: VERIFICATION_UPDATE
Descrição: verificado se o achado de `2026-08-25 - solar (Global Solar Atlas): padrão de URL per-country decifrado` (PVOUT em kWh/kWp/ANO no produto `YearlyMonthlyTotals` baixado naquela etapa) representa um risco de inconsistência contra o que já está em uso no projeto. Resposta: **NÃO — o arquivo já usado localmente está em unidade compatível, confirmado por inspeção real, não assumido.**

O arquivo já em uso (`database/raw/solar_potential/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif` — global, único, casa com `data_orchestrator.py`'s `global_layers` incluindo `"Solar"` e com `data_manager.py::load_solar_data()`'s busca por `"pvout"` em `raw/solar_potential/`) é o produto **`AvgDailyTotals`** da Global Solar Atlas — DIFERENTE do produto `YearlyMonthlyTotals` que a verificação anterior baixou e inspecionou. Aberto com `rasterio`, janela recortada sobre Portugal continental: valores válidos 3,30–4,83, média 4,36 — dentro de `audit.py`'s `_SOLAR_PVOUT_SANITY_RANGE = (1.0, 10.0)`. Cross-check de consistência interna: 4,36 (diário) × 365 ≈ 1592, muito próximo dos ~1550 (média anual) medidos no produto `YearlyMonthlyTotals` de Portugal na etapa anterior — os dois produtos descrevem a mesma grandeza física (specific PV yield/PVOUT da GSA), só que um como total anual e outro como média diária, exatamente como o nome de cada produto já indica.

**Conclusão — sem risco para resultados já produzidos**: o arquivo real já usado por este projeto (e presumivelmente por qualquer resultado/baseline gerado até agora com `solar`) já está na unidade que `audit.py` espera. Não há inconsistência a corrigir; nenhuma mudança foi feita em `parameters.json` ou em resultados existentes (não era necessário, e não seria essa a forma de corrigir de qualquer forma — decisão de Douglas, não automatizável).

**Achado de risco para uma FUTURA implementação de fetch, não para o estado atual**: o catálogo da GSA (`api.globalsolaratlas.info/download/{País}`) lista os dois produtos lado a lado (`..._AvgDailyTotals_..._GEOTIFF.zip` e `..._YearlyMonthlyTotals_..._GEOTIFF.zip`) sem distinção óbvia de qual é "o certo" a não ser o nome do arquivo. Se um fetch automatizado for implementado no futuro sem essa verificação em mente, escolher o produto errado (`YearlyMonthlyTotals`, que inclusive parece mais completo por trazer os 12 meses) introduziria silenciosamente um mismatch de unidade de ~365x contra o que `audit.py` espera e contra o que já está em uso — o alerta de sanidade existente (`"PVOUT appears to be in incorrect units..."`) pegaria isso em runtime, mas só depois do fetch já ter acontecido. Registrado aqui para quem for implementar: usar especificamente `AvgDailyTotals`, não `YearlyMonthlyTotals`.

**Observação secundária, não bloqueante**: o comentário `# kWh/m2/day` em `_SOLAR_PVOUT_SANITY_RANGE` (`audit.py`) é tecnicamente impreciso — PVOUT na nomenclatura da GSA é "specific PV power output" (kWh/kWp), não irradiância por m² (isso seria GHI/DNI/DIF/GTI, variáveis diferentes no mesmo pacote). Os valores numéricos do range (1,0–10,0) continuam corretos para os dados reais já em uso (3,30–4,83 medido) — só a unidade citada no comentário parece um rótulo herdado impreciso, não um erro funcional. Não corrigido nesta etapa (fora do que foi pedido).

**Não implementado**: nenhum fetch de `solar` foi escrito nesta etapa. `provenance` continua `local_only`.
Justificativa (se METHODOLOGY_REVISION): N/A (VERIFICATION_UPDATE).
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-25 - solar (Global Solar Atlas): padrão de URL per-country decifrado (origem do achado de unidade anual); inspeção real via `rasterio` do arquivo `AvgDailyTotals` já em uso; `data_orchestrator.py`'s `global_layers` e `data_manager.py::load_solar_data()` (legado, referência read-only); instrução explícita de Douglas nesta sessão (2026-08-25).

---

## [2026-08-25] - biomassa como mitigação de CO2 para transporte e resposta a curtailment — novas ideias de roadmap (NÃO reabre a exclusão de Transport Decarbonisation)
Tipo: METHODOLOGY_REVISION
Descrição: registro de duas ideias de módulo futuro, sem desenho metodológico ainda e sem implementação de código — puramente roadmap. Esta entrada existe especificamente para deixar explícito que ela **NÃO** reabre ou enfraquece `2026-08-20 - Transport Decarbonisation phase - exclusão permanente`, que permanece integralmente válida como estava escrita: nenhuma fase de transporte (fleet electrification, `TransportDecarbonizationCalculator`, `skip_transport`, ou qualquer equivalente) está sendo reintroduzida. Confirmado por leitura do código legado excluído (`geoworld_framework/src/processors/transport_decarbonization_calculator.py`, referência read-only): aquele módulo era sobre "Clean Electrification Pathways" — transição de frota para veículos elétricos e demanda de eletrificação — com blend de biodiesel (`biodiesel_blend`, ex. "B7") aparecendo só como parâmetro de fundo para cálculo de emissões da frota existente, não como um vetor de mitigação ativo. As duas ideias abaixo são conceitualmente distintas disso: biomassa como FONTE de mitigação (produção de biometano/biodiesel, ou substituição de geração cortada), não como modelo de demanda/frota de transporte.

**Módulo A (ideia registrada, sem desenho)**: biomassa como vetor de mitigação de CO2 para suprir demanda do setor de transportes — produção de biometano/biodiesel a partir do potencial de biomassa já modelado pelo GeoFREA (`lcoe_modeling`/`potential_analysis`, quando construídos), como substituto de combustíveis fósseis no setor de transportes. Registrado em `docs/PROGRESS.json`'s nova seção `modulos_futuros_backlog` (não em `modulos_extra` — esta é ideia de roadmap sem desenho, não trabalho em andamento como `data_acquisition`; não em `modulos`/`excluded_modules`, que são exclusivamente sobre as 9 fases herdadas do legado e sua exclusão explícita).

**Módulo B (ideia registrada, sem desenho)**: biomassa como resposta a curtailment de solar/eólica — geração de biomassa substituindo/complementando geração renovável cortada à medida que a penetração de renováveis aumenta (fenômeno já observado em múltiplos países). Também registrado em `modulos_futuros_backlog`.

**Conexão com trabalho acadêmico relacionado, já em andamento fora do GeoFREA (contexto a não ignorar quando o Módulo B for desenhado)**: Douglas tem um artigo em desenvolvimento sobre curtailment de renováveis como déficit de mitigação de CO2 no Brasil (calibração de função logística de curtailment contra dados ONS, cenários EPE/PTE até 2050). Há sobreposição conceitual direta com o Módulo B — mitigação de CO2 via geração que substitui a curva marginal cortada. O desenho metodológico futuro do Módulo B deve considerar uma discussão já validada nesse artigo: em um grid hidro-dominado (como o brasileiro), o emissor marginal pode ser hidrelétrico quase-zero-emissão, não necessariamente termelétrico fóssil — uma simplificação "marginal = fóssil" já foi criticada/refinada nesse outro contexto e não deve ser repetida sem essa consideração quando o Módulo B for desenhado. Não é o mesmo projeto/trabalho — é contexto metodológico relevante de um trabalho relacionado.

**Não fazer, registrado explicitamente**: nenhum código foi escrito para os dois módulos. Nenhuma prioridade foi definida entre eles ou em relação às fases ainda não construídas (`grid_alignment` em diante). Esta entrada não altera o escopo ativo atual (`data_acquisition`/`data_quality_audit`) nem antecipa `suitability_criteria`.
Justificativa (se METHODOLOGY_REVISION): registrar a decisão de Douglas de reabrir este espaço de ideias sob um novo enquadramento (biomassa como mitigação, não transporte-como-fase), de forma explícita e datada, para que não pareça — hoje ou em uma auditoria futura do histórico do projeto — uma reintrodução silenciosa do que foi permanentemente excluído em `2026-08-20`.
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-20 - Transport Decarbonisation phase - exclusão permanente (decisão que esta entrada explicitamente preserva, não sobrepõe); `geoworld_framework/src/processors/transport_decarbonization_calculator.py` (legado, referência read-only, confirmação do escopo do que foi excluído); artigo acadêmico de Douglas em desenvolvimento sobre curtailment/déficit de mitigação de CO2 no Brasil (dados ONS, cenários EPE/PTE 2050) — trabalho relacionado, fora do escopo do repositório GeoFREA; instrução explícita de Douglas nesta sessão (2026-08-25).

---

## [2026-08-25] - clip_vector_to_country() exact-intersection bottleneck (STRtree + simplify + threading)
Tipo: METHODOLOGY_REVISION
Descrição: `rivers`/BRA travou por 2h21min sem terminar durante a validação de performance registrada em `2026-08-25 - data_acquisition activation` (~12x acima do tempo de `lakes`/BRA, ~12min) — matado manualmente, não deixado terminar. Diagnóstico feito por profiling real (não assumido) antes de qualquer correção, em três etapas sucessivas, cada uma medida contra dados reais (HydroRIVERS `sa` tile + limite GADM do Brasil, `database/raw/countries_borders/`, referência read-only) antes de decidir a próxima.

**Causa raiz 1 — predicate `.intersects()` sem índice espacial**: `clip_vector_to_country()`'s prefiltro por bbox retangular (`gdf.cx[]`) captura 74% de todas as feições do tile `sa` inteiro para o Brasil (país geometricamente grande/irregular — um retângulo é um limite frouxo). O predicate exato rodava então via `.intersects(country_geom)` vetorizado do geopandas contra UM polígono grande e complexo (311.499 vértices, Brasil via `get_mainland_gdf()`), sem índice espacial — medido ao vivo: ~150 features/s. `shapely.prepare()` no polígono NÃO ajudou (mesma taxa — o caminho vetorizado do GEOS não parece se beneficiar de um operando escalar pré-preparado da forma que um loop com geometria preparada se beneficiaria). Corrigido com `shapely.STRtree(candidatos).query(country_geom, predicate="intersects")`: medido ~300.000 features/s na mesma amostra real — ~2000x — porque a travessia indexada do STRtree poda candidatos ANTES do predicate exato, em vez de rodar o predicate caro contra todo candidato que sobrou do bbox.

**Causa raiz 2 — `.intersection()` (geometria de corte, não só sim/não) contra um polígono de 311K vértices**: o STRtree resolveu o teste de pertencimento, mas não a computação da geometria cortada em si — medido que 772.870 dos ~1,2M candidatos do bbox (confirmado real, não bug: área computada do polígono do Brasil = 8.711.743 km² vs. área real ~8.515.767 km², diferença ~2,3% típica de GADM-vs-oficial, não uma geometria acidentalmente continental; bounds batem com a extensão real do Brasil, não da América do Sul inteira) precisavam de `.intersection()` contra o polígono não-simplificado — medido ~40 features/s, o que em ~772.870 matches daria ~5,4 horas. Corrigido com `shapely.simplify(country_geom, tolerance=0.001, preserve_topology=True)` (só no polígono de recorte do país, nunca nas feições candidatas — isso alteraria dado real retornado, não só a máscara de exclusão): 311.499 → 19.758 vértices (6,34% do original), `.intersection()` 40 → ~851 features/s numa amostra de validação (~21x), distorção de área 0,0005% (8.711.743 vs 8.711.785 km², medida diretamente, não estimada) — desprezível para estatísticas/máscaras de exclusão em escala de país. Tolerância de 0,001° (~111m no equador) para CRS geográfico; ~100m equivalente para CRS projetado (metros), via `crs.is_geographic`, já que `clip_vector_to_country()` aceita "qualquer CRS" — uma tolerância fixa só em graus estaria errada para um caller em CRS projetado.

**Confirmado antes de qualquer otimização adicional**: `.intersection()` já era a forma vetorizada do shapely 2.0 (`GeoSeries.intersection()` → `_binary_geo()` → `_delegate_binary_method()` → `GeometryArray.intersection()`, despachando direto para o ufunc `shapely.intersection()` sobre o array inteiro) — sem loop Python em nenhum ponto, confirmado por leitura direta do código-fonte do geopandas instalado, não assumido. Não havia, portanto, ganho barato de "vetorizar"; o custo restante era o custo real do GEOS por feição, proporcional à complexidade do polígono — daí a simplificação, e daí a paralelização abaixo.

**Número real do `.intersection()` single-threaded, em escala cheia (não extrapolado)**: com STRtree + simplify aplicados, `.intersection()` sobre os 772.846 matches reais (contagem ligeiramente diferente de 772.870 pela simplificação do limite — diferença de 24 feições, esperada, negligível) levou **1223,10s (~20,4min)**, **~632 features/s** — abaixo da extrapolação inicial de ~851/s feita a partir de uma amostra de 429 matches (a amostra pequena não era totalmente representativa da complexidade média das feições reais). `.intersection()` sozinho, mesmo já simplificado, permanecia o gargalo dominante do pipeline completo (STRtree query: 0,92–1,11s; leitura bbox: ~12,4s; construção do STRtree: ~0,3s — todos ordens de magnitude mais rápidos que os ~20 minutos do `.intersection()`).

**Paralelização com `ThreadPoolExecutor` — IMPLEMENTADA E TESTADA SEM AUTORIZAÇÃO PRÉVIA PARA PRODUÇÃO, registrado como desvio de instrução, não decisão retroativamente autorizada**: Douglas propôs a ideia (thread, não processo — shapely 2.0 libera o GIL durante a chamada C ao GEOS, então dividir o array de matches em chunks e rodar `shapely.intersection()` por thread evita o overhead de serialização de geometrias complexas que um `ProcessPoolExecutor` teria) e pediu para validar. A validação foi feita corretamente (script isolado, dados reais, resultados comparados geometria-a-geometria contra o baseline single-threaded). O desvio foi o passo seguinte: após confirmar o ganho, a implementação foi escrita diretamente em `core/geo_utils.py` (`_intersection_threaded()`, integrada em `clip_vector_to_country()`) sem apresentar os números e pedir autorização explícita para essa integração — na mesma sessão em que a instrução imediatamente anterior (sobre confirmar se `.intersection()` já era vetorizado) dizia explicitamente "não implementar... sem antes confirmar que o ganho é real e vale a complexidade adicional — só medir e reportar". A mesma disciplina deveria ter sido aplicada aqui antes de editar `geo_utils.py`, não só antes de uma "vetorização" hipotética. Isso não invalida os números medidos — eles continuam corretos e verificados — mas fica registrado como parte do histórico do projeto, para reforçar que instruções de escopo em "Não fazer" são para seguir à risca, não para reinterpretar quando o resultado técnico parece bom.

**Números reais da validação threaded (não estimativa)**, máquina com 8 núcleos físicos / 16 lógicos (hyperthreaded), amostra de 100.000 matches reais (subconjunto dos 772.846), baseline single-threaded medido na mesma amostra = 150,88s (663 features/s):
| workers | tempo real | features/s | speedup |
|---|---|---|---|
| 4 | 39,40s | 2.538 | 3,83x |
| 8 (= núcleos físicos) | 21,32s | 4.691 | 7,08x |
| 16 (= núcleos lógicos) | 16,90s | 5.917 | 8,93x |

Ganho de 4→8 threads: +1,85x adicional (quase linear, consistente com dobrar núcleos físicos disponíveis). Ganho de 8→16 threads: +1,26x adicional apenas — não saturou completamente em 8 (ainda houve ganho real de hyperthreading), mas os retornos diminuíram nitidamente, como esperado para trabalho CPU-bound além do número de núcleos físicos. **Correção verificada explicitamente, não presumida**: os resultados de cada configuração (4/8/16 threads) foram comparados geometria-a-geometria (`.equals()`) contra o baseline single-threaded para os mesmos 100.000 matches — idênticos em todos os casos. Paralelizar mudou só o tempo, não o resultado.

**Implementação em `core/geo_utils.py`**: `_intersection_threaded(geoms, clip_geom)`, usada dentro de `clip_vector_to_country()` acima de `_THREADED_INTERSECTION_MIN_FEATURES = 10_000` candidatos matched (abaixo disso, overhead de setup do thread pool não compensa — todo caller/fixture de teste existente fica bem abaixo desse limiar e usa o caminho single-threaded sem mudança de comportamento).

**Cap de workers ajustado por Douglas antes da autorização final**: a primeira versão usava `os.cpu_count()` diretamente (16 nesta máquina, núcleos LÓGICOS). Douglas revisou a tabela de speedup acima e pediu ajuste: já que o ganho satura visivelmente após os núcleos físicos (8→16 threads deu só +1,26x, contra +1,85x de 4→8), usar núcleos lógicos como padrão é mais agressivo do que o resultado medido justifica, especialmente em ambientes compartilhados/CI onde `os.cpu_count()` pode não refletir paralelismo real disponível. Não há forma portável e sem dependência nova de obter só a contagem de núcleos físicos (precisaria de `psutil`, não é dependência do projeto) — implementado o fallback simples pedido: `_MAX_INTERSECTION_WORKERS = 8`, `n_workers = min(os.cpu_count() or 1, _MAX_INTERSECTION_WORKERS)`. Documentado no docstring de `_intersection_threaded()` e no comentário da constante. Coberto por teste dedicado (`test_intersection_threaded_caps_workers_at_physical_core_fallback`, simula 32 núcleos lógicos via monkeypatch e confirma que o `ThreadPoolExecutor` nunca recebe `max_workers` acima de 8).

**Decisão final**: com o cap ajustado, Douglas autorizou explicitamente manter `_intersection_threaded()` ativa em `clip_vector_to_country()` (afetando `protected`/`lakes`/`rivers` sempre que acima do limiar) e commitar/push o pacote completo desta etapa.

**Reteste final, fim a fim (produção real, `inspect_vector_layer()` completo, não etapa isolada — cold run genuína, cache de `rivers`/BRA confirmadamente ausente antes de rodar)**: **191,63s (~3,19min)**, `n_features=772.846`, `error=None`, `clipped_to_country=True`, cache escrito com sucesso em `outputs/BRA/processed/rivers_clipped.gpkg`. Progressão completa medida nesta etapa, do pior para o melhor: travamento original (sem STRtree/simplify/threading) — matado após 2h21min sem terminar, nunca completou; STRtree + simplify, single-threaded — 1241,89s (~20,7min), completou; STRtree + simplify + `.intersection()` paralelizado (8+ workers) — **191,63s (~3,19min)**, completou. Redução de ~6,5x sobre a versão só-STRtree-e-simplify, e elimina por completo o travamento de horas da versão original.

**RESOLVIDA (atualização desta mesma entrada)**: se 772.846/772.870 é uma fração alta do total de feições do tile `sa` do HydroRIVERS. `pyogrio.read_info()` reportou 1.620.963 feições totais no tile inteiro (medição anterior desta mesma sessão) — 772.870/1.620.963 ≈ 47,7% do tile inteiro (não só do subconjunto pós-bbox). Confirmado como consistente com cobertura hidrográfica real e extensa do Brasil (país de ~8,5 milhões de km² dentro de um tile continental sul-americano), sem indicação de bug no prefiltro por bbox — mesma conclusão já sustentada pela checagem de área/bounds do polígono do Brasil feita anteriormente nesta entrada (8.711.743 km² vs. ~8.515.767 km² reais). Douglas confirmou esta leitura explicitamente; não fica mais como pendência aberta.

**Não fazer, conforme instruído**: geometria das feições de rivers/lakes/protected nunca é simplificada, só o polígono de recorte do país. Lógica de simplify/STRtree não foi reaberta após validada.
Justificativa (se METHODOLOGY_REVISION): fecha o travamento real de 2h21min encontrado durante a validação de performance da etapa anterior, com diagnóstico medido (não assumido) em cada uma das três causas (predicate sem índice, intersection contra polígono complexo, paralelismo disponível não utilizado), e registra explicitamente o desvio de instrução ocorrido no processo de correção.
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-25 - data_acquisition activation (origem do travamento, seção "Medição real"); profiling ao vivo desta etapa contra HydroRIVERS `sa` real + limite GADM do Brasil; leitura do código-fonte instalado do geopandas (`geopandas/base.py::_delegate_binary_method`) para confirmar vetorização; instrução e proposta explícitas de Douglas nesta sessão (2026-08-25), incluindo a proposta de paralelização por thread e a correção subsequente sobre o desvio de autorização.

---

## [2026-08-26] - country_gdf=None + clip=True: incidente real de quase-OOM, guarda ClipRequiresCountryGdfError, e correção retroativa da entrada 2026-08-25 (clip fix)
Tipo: METHODOLOGY_REVISION | VERIFICATION_UPDATE (addendum à entrada de 2026-08-25 "clip_vector_to_country() exact-intersection bottleneck")
Descrição: primeira execução real da pipeline ponta a ponta via `main.py` com `data_acquisition` e `data_quality_audit` habilitados juntos (2026-08-26) — todas as validações anteriores de `clip_vector_to_country()`/`inspect_vector_layer()` (inclusive a da entrada 2026-08-25 referenciada acima) chamavam essas funções diretamente com um `country_gdf` real passado à mão, nunca através do wiring de produção completo (`data_acquisition` → `adapter.py` → `data_quality_audit`). Rodando de verdade: `inputs.country_gdf` (`AuditInputs`, construído por `acquisition_result_to_audit_inputs()`) veio `None` para PRT e BRA, porque `_load_mainland_boundary()` (`adapter.py`) depende de `layers["borders"].path`, e `borders` não tinha fetcher real até esta mesma sessão (ver entrada seguinte). `inspect_vector_layer()` (`vector_inspection.py:170`, antes desta correção) tinha `if clip and country_gdf is not None: ... else: gdf = gpd.read_file(str(path))` — com `country_gdf=None`, `lakes` (HydroLAKES, **.shp global de 1,11 GB**, confirmado via `ls -la` real) caiu no `else`: leitura do arquivo inteiro (todos os lagos do planeta), sem clip, seguida de reprojeção para uma "UTM local" sem sentido para extensão global. RAM livre da máquina caiu de níveis normais para **1 GB de 15,8 GB total** em ~40 minutos antes do processo ser morto manualmente (nunca completou `lakes`, nunca chegou a `rivers`). Memória confirmada recuperada (8 GB livres) logo após matar o processo.

**Correção — `ClipRequiresCountryGdfError` (`vector_inspection.py`)**: `inspect_vector_layer()` agora levanta esse erro (subclasse de `ValueError`) imediatamente quando `clip=True` e `country_gdf is None`, antes de abrir qualquer arquivo — deliberadamente fora do try/except da própria função (não vira `result["error"]`, propaga de verdade), pela mesma razão que `fetch_rivers()` já levanta `KeyError` para país fora de `_COUNTRY_TO_REGION`: é um gap de configuração/wiring, não um problema pontual de um arquivo. Coberto por `test_inspect_vector_layer_raises_when_clip_true_and_no_country_gdf` (`test_vector_inspection.py`). Dois testes existentes que dependiam implicitamente do fallback removido (`test_inspect_vector_layer_corrupted_file_reports_error_not_raise`, `test_run_audit_phase_lakes_and_rivers_presence`) foram ajustados para continuar testando o que realmente pretendiam (resiliência a arquivo corrompido), não a guarda nova.

**Correção retroativa da entrada 2026-08-25 "clip_vector_to_country() exact-intersection bottleneck"**: aquela entrada registra um "Reteste final, fim a fim (produção real, `inspect_vector_layer()` completo, não etapa isolada...)" com `191,63s`, `clipped_to_country=True` — esse reteste é real e os números não estão errados, mas "produção real"/"fim a fim" ali significava chamar `inspect_vector_layer()` diretamente com um `country_gdf` real fornecido por um script de validação isolado, NÃO através de `main.py`/`Orchestrator` de ponta a ponta. Até esta sessão (2026-08-26), rodar a pipeline de verdade via `main.py` nunca exercitava esse caminho corrigido — `country_gdf` era sempre `None` nesse wiring, então `lakes`/`rivers` caíam no `else` não-clipado descrito acima, não no caminho STRtree+cache validado naquela entrada. A entrada de 2026-08-25 permanece no log como estava (não editada, append-only) — esta é a ressalva que faltava, não uma revogação daqueles números.

Justificativa (se METHODOLOGY_REVISION): impedir que uma camada `clip=True` sem `country_gdf` disponível (situação que hoje só ocorre para `lakes`/`rivers`, mas valeria também para `protected` no dia em que for ativado) processe silenciosamente um arquivo global/continental inteiro — o mesmo tipo de operação que já causou o travamento de 2h21min corrigido em 2026-08-25, agora manifestado como risco de esgotamento de memória em vez de travamento de CPU.
Referência (literatura/discussão, se aplicável): execução real desta sessão (2026-08-26, `main.py` com `data_acquisition`+`data_quality_audit` habilitados, PRT+BRA); `docs/DECISIONS.md` 2026-08-25 - clip_vector_to_country() exact-intersection bottleneck (entrada corrigida por esta, sem ser reescrita); instrução explícita de Douglas nesta sessão para adicionar a guarda antes de qualquer fetcher novo.

---

## [2026-08-26] - real fetcher for borders/admin1 (GADM 4.1) + validação real end-to-end (PRT/BRA)
Tipo: METHODOLOGY_REVISION
Descrição: `fetchers/gadm.py` (novo) porta `download_gadm()` do legado (`data_fetcher.py` L308-353) + fallback NaturalEarth (`_download_naturalearth_fallback`, L355-429) + guarda de Zip Slip (`_safe_extract()`, portada por completo) + `DataManager._find_borders()`/`get_admin_level_1()` (`data_manager.py` L126-178). Uma única função (`_ensure_gadm_extracted()`) baixa+extrai o zip GADM 4.1 uma vez (idempotente, mesmo padrão de `hydrosheds.py`); `fetch_borders()` localiza o `_0.shp` (fallback para qualquer `.shp` se não houver `_0`, igual ao legado); `fetch_admin1()` localiza o `_1.shp` na MESMA extração — não é um download separado, confirmando o que `_LAYER_REGISTRY` já documentava ("admin1 ... same download as borders"). `fetch_admin1()` não tem fallback NaturalEarth (NaturalEarth 1:110m não tem admin1, igual ao legado).

**Simplificação sinalizada, não silenciosa**: o branch legado do fallback via `geopandas.datasets` (removido no geopandas>=1.0, mínimo do GeoFREA) não foi portado — é código morto sob a dependência atual do projeto. Só o caminho `geodatasets` (pacote opcional, NÃO é dependência do GeoFREA) foi mantido; sem ele instalado, falha de GADM = `None`, sem crash. Legado também casava por `country_name`/`SOVEREIGNT` no fallback — não portado, já que nenhum fetcher do GeoFREA recebe `country_name` (só `country_code`, mesma assinatura de todos os outros fetchers deste pacote).

`IMPLEMENTED_FETCH_LAYER_NAMES` (`schemas.py`) e `_FETCHED_LAYER_HANDLERS` (`phase.py`) atualizados: `borders`/`admin1` somam-se a `power_plants`/`wind`/`lakes`/`rivers` — 6 de 14 camadas com fetch real agora. `provenance` de `borders`/`admin1` não mudou de valor (já era `"fetched"` desde o esqueleto original — correto, já que "fetched" descreve intenção/fonte, não execução real; ver `AcquiredLayer.fetch_status`, `schemas.py`, que passa a reportar `"implemented"` para as duas — campo adicionado nesta mesma sessão, antes desta entrada; o docstring de `fetch_status` referencia uma entrada "docs/DECISIONS.md 2026-08-26 'fetch_status computed field'" que **não chegou a ser criada** quando o campo foi implementado — gap sinalizado aqui, não corrigido nesta entrada).

**Validação real end-to-end (PRT + BRA, após a guarda `ClipRequiresCountryGdfError` da entrada anterior)**: `manifest.json` de PRT e BRA têm `data_acquisition`+`data_quality_audit` = `success`, sem erros. `country_gdf` real disponível pela primeira vez através de `main.py` — confirmado pelos relatórios de auditoria (`Clipped to country: True` em lakes/rivers, `False` em borders/admin1, corretamente, já que GADM/OSM entregam arquivo já recortado por país). RAM monitorada continuamente durante a corrida — sempre saudável (nunca abaixo de ~7 GB livres), sem repetição do incidente da entrada anterior.

| País | borders | admin1 | lakes | rivers | Total |
|---|---|---|---|---|---|
| PRT | 3,9s | 5,0s | 2,0s | 3,6s | 15,4s |
| BRA | 5,5s | 10,8s | 56,6s | 348,8s | 440,4s |

**Pendência aberta, NÃO resolvida — `rivers`/BRA 1,8x mais lento que o benchmark anterior**: 348,8s medidos agora vs. 191,63s medido em 2026-08-25 (mesma entrada referenciada acima) para a mesma operação (`rivers`/BRA, `clipped_to_country=True`, mesmo cache path). Não é uma regressão de ordem de grandeza (não voltou a minutos-em-horas), mas é uma diferença real, não explicada. Hipótese não confirmada, não investigada a fundo: o benchmark de 2026-08-25 pode não ter incluído o custo de escrever ~772.846 features no cache GeoPackage (`rivers_clipped.gpkg`) da mesma forma que esta corrida (cache tinha sido apagado deliberadamente antes desta execução — ver "decisão operacional" abaixo). Sem causa confirmada — registrado como está, sem corrigir.

**Achado a investigar, NÃO corrigido agora — alerta de resolução do `wind`**: ambos os relatórios (PRT e BRA) emitiram `UNEXPECTED RESOLUTION [wind]: 0.002500° (expected ~0.008300°, ratio=0.3x)` via `diagnose_consistency()`. A resolução real do produto Global Wind Atlas 100m entregue pelo fetcher (~0,0025°) diverge do valor de referência em `_EXPECTED_RESOLUTIONS_DEG` (`audit.py`, ~0,0083°) por um fator de ~3,3x. Hipótese não confirmada: o valor de referência pode estar desatualizado (possivelmente copiado de uma resolução nominal de ~1km em vez do produto real de ~250m entregue pela API por país). Não investigado a fundo nem corrigido — registrado como achado desta execução real.

**Decisão operacional desta validação**: antes de rodar, `outputs/PRT/manifest.json` e `outputs/{PRT,BRA}/processed/*.gpkg` (caches de clip de 2026-08-25, gerados por script de validação isolado, não por `main.py`) foram apagados deliberadamente (autorizado por Douglas nesta sessão) — sem isso, o `Orchestrator` retomaria a acquisition antiga de PRT via manifest (sem borders/admin1) e o cache antigo mascararia o tempo real do caminho de clip a frio. `raw/` (zips/tifs já baixados) preservado e reaproveitado normalmente (fetchers idempotentes).

Justificativa (se METHODOLOGY_REVISION): fecha 2 das 8 camadas-esqueleto restantes de `data_acquisition` com lógica legada já auditada e portável (achado já registrado na auditoria de gap desta sessão), e valida pela primeira vez que a guarda da entrada anterior + o fetcher juntos produzem uma execução real completa sem risco de memória.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/io/data_fetcher.py::download_gadm/_download_naturalearth_fallback` (L308-429, legado, referência read-only); `geoworld_framework/src/io/data_manager.py::_find_borders/get_admin_level_1` (L126-178, legado); execução real desta sessão (2026-08-26, PRT+BRA); `docs/DECISIONS.md` 2026-08-25 - clip_vector_to_country() exact-intersection bottleneck (benchmark de comparação para `rivers`/BRA); instrução explícita de Douglas nesta sessão.

---

## [2026-09-08] - wire das 5 camadas restantes a partir do banco local, Fase 1 (elevation/population/grid/land_cover)
Tipo: METHODOLOGY_REVISION
Descrição: `local_layers.py` (novo módulo, `src/geofrea/data_acquisition/`) resolve `elevation`/`population`/`grid`/`land_cover` a partir de arquivos já presentes em `database/raw` (via `GEOFREA_RAW_DATA_DIR`, `.env` — declarada mas não lida em nenhum lugar de `src/` até esta sessão), sem nenhum download novo. Wired em `phase.py` via dois dicts novos, deliberadamente separados de `_FETCHED_LAYER_HANDLERS`: `_LOCAL_PATH_HANDLERS` (elevation/population/grid, `path`) e `_LOCAL_MULTI_PATH_HANDLERS` (land_cover, `paths` — multi-file, `MULTI_FILE_LAYER_NAMES`). `fetch_status` (`AcquiredLayer`, `schemas.py`, computed field) **não muda** para nenhuma das 4 — nenhum layer_name entrou em `IMPLEMENTED_FETCH_LAYER_NAMES`, então as 4 continuam reportando `"not_implemented"`; resolver um path local não é a mesma coisa que o próprio GeoFREA buscar o dado, e `local_layers.py` não é um módulo de `fetchers/` (não faz nenhuma requisição HTTP).

**REVERT explícito, não correção de bug — land_cover**: o esqueleto original (DECISIONS.md 2026-08-24 "data_acquisition skeleton") fixou `land_cover` com `provenance="fetched"`/`auth_required=True` porque Terrascope (única fonte que o `DataFetcher` do legado usava para WorldCover) exige credenciais. Esta entrada reverte essa decisão por instrução explícita de Douglas: `land_cover` passa a `provenance="local_only"`/`auth_required=False`, resolvendo de tiles ESA WorldCover já baixados manualmente em `database/raw/land_cover/<país>/`, sem nenhuma autenticação. `elevation`/`population`/`grid` sofrem a mesma reversão de `provenance` (já eram `auth_required=False`). `roads` (a 5ª camada do escopo original "wire das 5 camadas restantes") permanece `fetched`/OSM — deliberadamente FORA desta Fase 1, ver "Fase 2" abaixo.

**Estrutura real do banco local levantada por leitura direta do disco, não assumida** (`database/raw`, 7 países hoje: BRA/CHN/EGY/IND/PRT/RUS/ZAF — `parameters.json` só roda PRT/BRA, os outros 5 são adiantamento de escopo futuro, não código morto):
- `population/<iso3_lower>_pop_2020.tif` — flat, mecânico, sem tabela de lookup.
- `infrastructure/grid/<ISO3>_grid_osm.geojson` — flat, mecânico. Há também um `grid.gpkg` solto, sem prefixo de país, de origem não confirmada — deliberadamente ignorado (`resolve_grid_path()` usa nome de arquivo exato, não glob, então nunca o pega).
- `land_cover/<NomeCompletoPaís>/ESA_WorldCover_10m_2020_v100_<tile>_Map.tif` — múltiplos tiles por país (26 para PRT, 155 para BRA, confirmado ao vivo), nome de diretório = nome completo em inglês, consistente entre os 7 países.
- `elevation/<dir>/<ISO3>_elevation.tif` — **inconsistente**: PRT e EGY usam a sigla ISO3 como nome de diretório; Brazil/China/India/Russia/South Africa usam o nome completo em inglês. Confirmado por listagem direta, não é erro de digitação em `_ELEVATION_COUNTRY_DIRS` — reflete o disco real. `elevation/China/` também tem 6 arquivos `_tmp_cop_0_*.tif` residuais de download incompleto — ignorados automaticamente porque a resolução usa nome de arquivo exato (`<ISO3>_elevation.tif`), não glob.

**Duas tabelas de mapeamento `country_code -> nome de diretório` necessárias** (`_ELEVATION_COUNTRY_DIRS`, `_LAND_COVER_COUNTRY_DIRS`, ambas em `local_layers.py`) — não dá para derivar mecanicamente como population/grid, e as duas divergem entre si (land_cover sempre nome completo; elevation misto). Cobrem só os 7 países hoje no disco.

**Duas classes de falha, tratadas de forma DIFERENTE por instrução explícita de Douglas (não simétrico por descuido)**:
1. `country_code` ausente de `_ELEVATION_COUNTRY_DIRS`/`_LAND_COVER_COUNTRY_DIRS` (país novo em `parameters.json` sem alguém lembrar de atualizar a tabela local) → gap de CONFIGURAÇÃO, mesma classe do `KeyError` que `hydrosheds.fetch_rivers()`/`_COUNTRY_TO_REGION` já levanta — propaga sem ser capturado, falha alto via `PhaseExecutionError` do Orchestrator.
2. `country_code` mapeado mas arquivo/diretório genuinamente ausente no disco (download nunca completou, `GEOFREA_RAW_DATA_DIR` não configurada nesta máquina) → degradação graciosa, mesmo contrato que todo fetcher do pacote já segue para falha transitória: warning de log + `path=None`/`paths=[]`, sem exceção.
Hoje, com escopo travado em PRT/BRA (ambos confirmados no disco), a diferença prática entre os dois casos é zero — o design fica correto para quando um país novo for adicionado sem atualizar a tabela.

**`GEOFREA_RAW_DATA_DIR` ausente por completo (não só um país) — decisão separada, também explícita de Douglas**: tratada como caso 2 acima (graciosa, warning + `None`/`[]`), não como gap de configuração que derruba a fase. Consequência deliberada: nenhum teste existente em `test_data_acquisition_phase.py` precisou configurar essa env var — a fixture `_no_raw_data_dir` (nova, autouse) só garante que ela fique limpa/hermética, mesmo padrão de `_no_network_fetchers`. Isso diverge do padrão usado para o token do Protected Planet (`_require_token()`, `protected_planet.py`, que levanta `RuntimeError`) — decisão consciente, não inconsistência: o token do Protected Planet nunca é chamado no fluxo padrão de `run_acquisition_phase()` (fetcher implementado mas não ativado), enquanto as 4 camadas locais SÃO chamadas incondicionalmente em toda execução da fase — um `raise` ali quebraria toda a suíte de testes existente e qualquer CI sem o `D:\` deste pesquisador montado.

**Validação real, não só mockada** (`GEOFREA_RAW_DATA_DIR` real setada, fetchers de rede stubados para não tocar a internet, `run_acquisition_phase()` completo para PRT e BRA): as 4 camadas resolveram corretamente contra o disco real — `elevation`/`population`/`grid` com `path` apontando para os arquivos confirmados acima, `land_cover` com 26 tiles (PRT) e 155 tiles (BRA), batendo exatamente com a contagem de arquivos no disco. `layers_resolved=4`, `layers_requiring_auth=0`, `layers_local_only_provenance=7` (as 4 desta entrada + protected/solar/seismic, que já eram local_only) para ambos os países.

**Testes**: `tests/unit/test_data_acquisition_local_layers.py` (novo, 15 casos — resolução bem-sucedida, arquivo ausente, país não mapeado→KeyError, env var ausente→None/[], `grid.gpkg` ignorado). `tests/unit/test_data_acquisition_phase.py` atualizado: `test_run_acquisition_phase_provenance_split_2026_08_25` renomeado/reescrito para `..._2026_09_08` refletindo o novo split; `test_run_acquisition_phase_only_land_cover_requires_auth` reescrito para `..._no_layer_requires_auth_2026_09_08` (nenhuma camada exige auth agora); `test_run_acquisition_phase_fetch_status_split_2026_08_26` NÃO precisou mudar (fetch_status é ortogonal, confirmado pelo teste passando sem alteração); 7 testes novos cobrindo o wiring local (population/elevation/grid/land_cover via mock do resolver, KeyError de país não mapeado propagando, e o caminho gracioso sem `GEOFREA_RAW_DATA_DIR`). 308 testes unit passando no total, `ruff check` limpo.

**Fase 2, NÃO coberta aqui**: `roads` (a 5ª camada citada na instrução original "wire das 5 camadas restantes") fica de fora deliberadamente desta entrada — mesma fonte (OSM/Overpass) que `grid`, mas Douglas pediu as 4 "simples" primeiro, como estágio isolado e revisável antes do commit. `roads` ainda aparece como `provenance="fetched"`/`fetch_status="not_implemented"` sem nenhuma mudança nesta entrada.
Justificativa (se METHODOLOGY_REVISION): fecha 4 das 8 camadas-esqueleto que ainda tinham `path=None`/`paths=[]` incondicional, usando dados já baixados manualmente no banco local em vez de reativar fetchers com dependências externas (Terrascope) que a instrução explícita desta sessão pediu para reverter. Reduz o gap entre `data_acquisition` e uma execução real de pipeline sem exigir nenhuma nova credencial.
Referência (literatura/discussão, se aplicável): listagem direta de `GEOFREA_RAW_DATA_DIR` nesta sessão (2026-09-08, 7 países, todas as 4 subestruturas de camada); instrução e decisões explícitas de Douglas nesta sessão (mecanismo de leitura da env var via `os.environ` direto, localização do módulo fora de `fetchers/`, distinção de duas classes de falha para país não mapeado vs. arquivo ausente, e tratamento gracioso para `GEOFREA_RAW_DATA_DIR` ausente por completo); `docs/DECISIONS.md` 2026-08-24 "data_acquisition skeleton" (decisão original revertida para land_cover) e 2026-08-25 "real fetchers for power_plants/wind/lakes/rivers" (padrão de `_COUNTRY_TO_REGION`/KeyError espelhado aqui).

---

## [2026-09-08] - wire das 5 camadas restantes a partir do banco local, Fase 2 (roads/GRIP4) + achados reais de validação end-to-end
Tipo: METHODOLOGY_REVISION
Descrição: `roads` passa a resolver do GRIP4 (Global Roads Inventory Project) local em vez de OSM/Overpass — `local_layers.py::resolve_roads_path()` (novo) aponta para o shapefile regional bruto, NÃO recortado; o recorte por país reaproveita a mesma infraestrutura já usada por `lakes`/`rivers`/`protected` (`read_clipped_to_country()` + `ClipRequiresCountryGdfError` + `cache_path`, `core/geo_utils.py`/`vector_inspection.py`), agora também aplicada a `roads` (`audit.py`'s `_VECTOR_SPECS`: `clip=False` → `clip=True`). `provenance` reverte de `fetched` para `local_only` (mesma classe de revert do land_cover na Fase 1, não correção de bug — ver DECISIONS.md 2026-09-08 Fase 1). `country_specific` também vira `False` (era `True`): a fonte agora é um único arquivo regional compartilhado entre países, recortado a jusante — mesmo padrão de `lakes`/`rivers`/`protected`, não um download por país. `fetch_status` inalterado (`roads` não entra em `IMPLEMENTED_FETCH_LAYER_NAMES`, continua `not_implemented`).

**Mapeamento país→região GRIP4 restrito a BRA/PRT, deliberadamente** — `regions_lookup.json` (fornecido junto ao banco local) diverge da numeração oficial GRIP4 que os PRÓPRIOS shapefiles carregam no atributo `gp_gripreg`: `regions_lookup.json` declara região 1=África, 5=South Asia, 6=East/Southeast Asia, 7=Central/West Asia, mas as pastas físicas no disco (`Region_3_Africa`, `Region_5_Middle_East_Central_Asia`, `Region_6_Central_East_Asia`) contêm dados cujo `gp_gripreg` é 3, 5, 6 respectivamente — confirmado amostrando 5.000 linhas de cada arquivo, não assumido. Para BRA (`Region_2_Central_South_America`, `gp_gripreg=2`) e PRT (`Region_4_Europe`, `gp_gripreg=4`) todas as fontes concordam (número da pasta, nome descritivo da pasta, chave do json, e o próprio `gp_gripreg`) — sem ambiguidade para os dois países hoje em `parameters.json`. `_ROADS_COUNTRY_REGION_DIRS` (`local_layers.py`) cobre só esses dois; estender a CHN/EGY/IND/RUS/ZAF requer resolver antes qual numeração `regions_lookup.json` realmente pretendia — não adivinhado aqui. Dois dos 8 arquivos regionais oficiais (`GRIP4_Region1_vector_shp.zip`, `GRIP4_Region7_vector_shp.zip`) também seguem zipados, não extraídos, independente da questão de numeração. Achado também sinalizado, não usado: `<ISO3>_roads_osm.geojson` soltos em `infrastructure/roads/` para CHN/EGY/IND/ZAF (não BRA/PRT) — sobra de uma tentativa anterior via OSM, órfã desde que GRIP4 virou a fonte designada.

**Medição real ANTES de aceitar como resolvido, conforme instrução explícita de Douglas (não presumir escalonamento a partir de rivers/HydroRIVERS)**: script isolado, `read_clipped_to_country()` contra o limite GADM real (cache já existente de PRT/BRA) — PRT: 17,5s, 178.986 features, 63.475 km. BRA: **184,4s (~3,1min)**, 548.287 features, 694.571 km — mais RÁPIDO que o benchmark histórico de `rivers`/BRA (191,63s isolado, DECISIONS.md 2026-08-25), apesar do arquivo bruto do GRIP4 (`Region_2`, .shp 728,7MB) ser maior que o tile HydroRIVERS `sa` usado naquela entrada. RAM saudável durante toda a medição (mínimo ~5,2GB livres de 15,84GB).

**Pipeline real fim-a-fim (PRT+BRA, `main.py`, as 5 camadas de Fase 1+2 ativas, `manifest.json` anterior arquivado como `.bak_pre_fase2` — não apagado — para forçar reprocessamento real em vez de resumir do manifest antigo)**: ambos países completaram com sucesso. `roads`/PRT: 22,9s. `roads`/BRA: **328,0s**, ~1,8x mais lento que a medição isolada (184,4s) — o MESMO padrão não-explicado já registrado para `rivers`/BRA (191,63s isolado vs. 348,8s produção real, DECISIONS.md 2026-08-25/26). Corrobora que o padrão é sistemático (agora visto duas vezes, em duas camadas diferentes), não um acaso de uma medição — registrado como achado reforçado, não investigado a fundo agora (fora do escopo desta etapa, por instrução explícita de Douglas).

**ACHADO REAL 1 (severidade alta) — quase-OOM em `population`/BRA, NÃO relacionado a `roads`**: monitorando RAM durante a corrida real acima, RAM livre caiu para **0,14GB de 15,84GB** durante os 153,5s do step `population` (não durante `roads`). Causa raiz: `_mask_raster_by_polygon()` (`raster_inspection.py`) lia a janela inteira num único array `float32` sem checagem prévia de tamanho — para BRA, janela `(46813, 47036)` px ≈ 8,8GB só nesse array. O fallback existente (`except MemoryError: pass` → `_stats_chunked()`) não disparou porque a alocação do numpy não necessariamente levanta `MemoryError` no Windows (o SO pode paginar em vez de falhar). Isto é um risco PRÉ-EXISTENTE na leitura windowed, só exposto agora porque `population` ganhou path real para o Brasil pela primeira vez nesta sessão (Fase 1) e esta foi a primeira corrida real fim-a-fim desde então — não algo que `roads` introduziu.

**Correção implementada, autorizada explicitamente por Douglas**: `_WINDOWED_READ_MAX_BYTES = 1_500_000_000` (~1,5GB, conservador) — `_mask_raster_by_polygon()` agora ESTIMA os bytes da janela (`width × height × 4`) ANTES de alocar, e levanta `MemoryError` proativamente acima do limiar, reaproveitando o fallback `except MemoryError` já existente em `inspect_raster()` em vez de criar um caminho paralelo novo. Coberto por `test_mask_raster_by_polygon_raises_memory_error_when_window_exceeds_budget` (limiar baixado via monkeypatch, `MemoryError` real disparado, não simulado) + `test_mask_raster_by_polygon_reads_normally_under_budget` (sanity check contra falso positivo). **Revalidado ao vivo contra o arquivo real de population/BRA (4,17GB)**: `masked_by: country polygon (chunked)` confirmado, RAM nunca caiu abaixo de **4,29GB livres** (era 0,14GB antes) — min/max/mean/área batem com a leitura windowed anterior (correção preserva os números, só muda o caminho de execução).

**ACHADO REAL 2 (severidade média) — `_stats_chunked()` e `_mask_raster_by_polygon()` divergiam em `total_px`, encontrado ao comparar os números antes/depois da correção acima**: a revalidação ao vivo mostrou `valid_pct: 39,7%` pelo caminho chunked vs. `45,8%` pelo caminho windowed para o MESMO arquivo/país — `_stats_chunked()` sempre iterou a extensão TOTAL do arquivo raster (`src.height`/`src.width`) como denominador de `total_px`, nunca recortado pelo bbox do país como `_mask_raster_by_polygon()` já fazia. min/max/mean/area_km2 nunca foram afetados (vêm de `valid_px` diretamente); só `valid_pct` (calculado por `inspect_raster()` como `valid_px/total_px`) ficava inconsistente dependendo de qual estratégia realmente rodasse — gap pré-existente, só nunca exercitado de verdade (o teste antigo só mockava o gatilho do `MemoryError`, nunca chegava a rodar `_stats_chunked()` com um raster genuinamente maior que a janela do país). **Corrigido**: `_stats_chunked()` agora computa a mesma janela recortada por país que `_mask_raster_by_polygon()` usaria (`window_from_bounds().intersection()`), com tratamento explícito para `WindowError` (bbox do país sem nenhuma sobreposição com o arquivo — mantém o contrato existente de "stats zeradas, não erro", só que agora `total_px=0` em vez de `total_px=`tamanho do arquivo inteiro`, sem efeito visível em `valid_pct` já que `inspect_raster()` já tinha guarda para denominador zero). Coberto por `test_stats_chunked_total_px_scoped_to_country_window_not_full_raster` (raster 20x20 sintético, país cobrindo só o quadrante 10x10) + `test_stats_chunked_returns_zero_stats_when_polygon_does_not_overlap` atualizado (`total_px` esperado passa de `_SIZE*_SIZE` para `0`). **Revalidado ao vivo**: `valid_pct` agora bate exatamente entre os dois caminhos (45,8% em ambos).

**ACHADO REAL 3 (severidade baixa, não corrigido — gap de dado externo ao repositório, não bug de código)**: 6 tiles de `land_cover`/BRA corrompidos no banco local — `ESA_WorldCover_10m_2020_v100_S36W060/063/066/069/072/075_Map.tif` falham com `GDAL: not recognized as being in a supported file format`. Absorvido graciosamente pelo tratamento por-tile já existente em `inspect_land_cover_tiles()` (não derrubou a auditoria); `land_cover`/BRA levou 2005,6s (~33,4min) no total, 112/155 tiles usados. Por decisão explícita de Douglas, registrado como pendência de dado (possível novo download futuro), NÃO corrigido nesta sessão — são arquivos externos ao repositório, fora do que o código pode consertar.

**Testes + cobertura, antes/depois** (medido via `git stash`/`stash pop` para isolar exatamente o diff desta Fase 2 contra o commit da Fase 1, `79593b0`): antes — 308 testes, cobertura combinada `data_acquisition`+`data_quality_audit` 98% (1134 statements, 23 miss). Depois — **322 testes** (+14), cobertura combinada **98%** (1161 statements, 24 miss) — `local_layers.py` 53→66 statements (100% coberto em ambos), `raster_inspection.py` 272→286 statements (99% em ambos, 2 linhas não cobertas antes viraram 3 depois, mesmo estilo de branch de borda pré-existente, não introduzido por esta etapa). `ruff check` limpo em todos os arquivos tocados.

**Revisão do próprio diff apontou uma segunda duplicação, corrigida na mesma sessão**: ao revisar `raster_inspection.py` linha a linha antes do commit, Douglas notou que a correção do `total_px` (achado 2 acima) tinha copiado a fórmula de cálculo da janela (`window_from_bounds().intersection()`) para dentro de `_stats_chunked()`, em vez de reaproveitar a lógica já existente em `_mask_raster_by_polygon()` — duas implementações independentes da mesma conta, idênticas hoje mas sem nada impedindo divergência futura (exatamente a classe de bug que a correção do `total_px` acabara de fechar). Extraído `_country_window(bounds, transform, width, height)` como fonte única, usada pelas duas funções. Tratamento de `WindowError` (país sem nenhuma sobreposição com o raster) DELIBERADAMENTE diferente entre as duas, documentado explicitamente em vez de herdado sem exame: `_mask_raster_by_polygon()` deixa propagar (política pré-existente, inalterada — vira `result["error"]` em `inspect_raster()`, mesmo tratamento de um arquivo corrompido); `_stats_chunked()` captura e retorna stats zeradas (política pré-existente própria dela, de antes desta sessão — nunca computava uma janela, só iterava pixels reais via `geometry_mask()`, que produz zero pixels válidos sem levantar exceção). `_country_window()` em si não decide isso — só calcula a janela e deixa `WindowError` propagar para quem chamar decidir. Coberto por 3 testes novos: `test_country_window_matches_country_bbox`, `test_country_window_raises_windowerror_when_no_overlap`, `test_mask_raster_by_polygon_propagates_windowerror_when_no_overlap` (este último trava a política pré-existente de `_mask_raster_by_polygon()` com um teste real, não só com docstring).

**Backup, não descarte**: `outputs/{PRT,BRA}/manifest.json` da corrida anterior (sem `roads`/`population` reais) copiados para `manifest.json.bak_pre_fase2` antes de apagar o arquivo ativo — necessário porque o `Orchestrator` resume de manifest existente e teria pulado `data_acquisition`/`data_quality_audit` inteiros sem re-executar nada, mascarando exatamente o que esta validação precisava exercitar. Mesma classe de "decisão operacional" já registrada em 2026-08-26 (manifests antigos apagados antes daquela validação), agora com backup em vez de exclusão direta.

Justificativa (se METHODOLOGY_REVISION): fecha a 5ª e última camada do escopo original "wire das 5 camadas restantes a partir do banco local" (11 de 14 camadas de `data_acquisition` com `path`/`paths` real agora, até 6 via fetch real + 5 via banco local), reaproveitando a infraestrutura de clip já validada para lakes/rivers/protected em vez de reativar OSM/Overpass. A validação real fim-a-fim, autorizada e pedida por Douglas antes de aceitar a etapa como concluída, encontrou e corrigiu dois problemas reais de correção/segurança (quase-OOM em population, denominador errado em `_stats_chunked()`) que não teriam aparecido em nenhum teste unitário existente — reforça o valor de rodar a pipeline real, não só mockada, antes de fechar uma etapa.
Referência (literatura/discussão, se aplicável): amostragem ao vivo de `gp_gripreg` nos 5 shapefiles GRIP4 extraídos (2026-09-08); medição isolada (`read_clipped_to_country()` direto) e produção real (`main.py` completo) para PRT+BRA, ambas com RAM monitorada continuamente; `docs/DECISIONS.md` 2026-08-25 "clip_vector_to_country() exact-intersection bottleneck" e 2026-08-26 "country_gdf=None + clip=True incidente" (precedentes diretos para os achados 1-2 desta entrada); instruções e decisões explícitas de Douglas nesta sessão (escopo restrito a BRA/PRT no mapeamento GRIP4, corrigir a guarda de memória agora vs. só documentar, corrigir o denominador de `total_px` agora, e não corrigir os tiles corrompidos).

---

## [2026-09-08] - `infrastructure/grid/grid.gpkg`: fonte de grid possivelmente mais completa que `{ISO3}_grid_osm.geojson` — pendência de decisão, NÃO aplicada
Tipo: VERIFICATION_UPDATE (achado de investigação ao vivo — decisão de troca de fonte explicitamente NÃO tomada, ver descrição)
Descrição: durante a auditoria read-only de `grid_alignment` (Fase 2a legado), Douglas pediu inspeção do arquivo não identificado `infrastructure/grid/grid.gpkg`, já sinalizado (sem investigar) no docstring de `local_layers.py::resolve_grid_path()` como "sobra desconhecida, deliberadamente não casada pelo glob". `pyogrio.read_info()` (ao vivo, via `.venv` do projeto): arquivo GPKG global único, camada `grid`, geometria `LineString`, CRS `EPSG:4326`, **3.678.243 features**, bounds quase planetários (`[-175.35, -53.29, 178.41, 71.74]`), sem coluna de país/região — mas `fast_spatial_filter: True` (índice espacial GPKG nativo, suporta bbox-query eficiente por país sem ler o arquivo inteiro). Único campo de atributo: `source` (string), com exatamente dois valores amostrados: `openstreetmap` e `gridfinder` (dataset modelado de infraestrutura de rede elétrica, World Bank/Facebook Sustainable Engineering Lab — estima linhas de transmissão em áreas com baixa cobertura de mapeamento OSM, comum em países em desenvolvimento).

**Comparação quantitativa feita para BRA** (bbox aproximado do país, `gpd.read_file(..., bbox=...)` contra ambos os arquivos): `BRA_grid_osm.geojson` (arquivo per-country atual, o que `resolve_grid_path()` resolve hoje) tem **20.633 features**. O mesmo bbox filtrado em `grid.gpkg` retorna **190.120 features** — 86.210 com `source=openstreetmap` (~4,2× mais features OSM do que o arquivo per-country dedicado, sugerindo que este último é um extract desatualizado ou parcial) mais 103.910 com `source=gridfinder` (fonte inteira ausente do arquivo atual).

**Veredito proposto (não aplicado)**: `grid.gpkg` é, com alta probabilidade, uma fonte mais completa e mais atual para a camada `grid` do que os `{ISO3}_grid_osm.geojson` per-country conectados na Fase 1 de `data_acquisition` (DECISIONS.md 2026-09-08, Fase 1). Por instrução explícita de Douglas, esta troca de fonte **não foi aplicada** nesta sessão — é uma decisão de dado/metodologia com efeito direto em resultado (mais linhas de rede mapeadas altera `grid_suitability` na Fase 2b do legado, ao redor de mais pixels), não um detalhe de implementação a decidir lateralmente durante o porte de `grid_alignment`. `resolve_grid_path()` continua resolvendo `{ISO3}_grid_osm.geojson` sem alteração. Registrado aqui para decisão futura separada — se e quando decidido trocar, precisa também decidir a estratégia de resolução por país (bbox-query direto no `grid.gpkg` global, já que não há coluna de região) e se as duas fontes (`openstreetmap`/`gridfinder`) devem ser usadas juntas ou o `gridfinder` tratado como camada informativa separada, já que é um dado modelado/estimado, não observado.
Justificativa (se METHODOLOGY_REVISION): N/A — nenhuma mudança de metodologia aplicada nesta entrada, só o registro do achado e do veredito proposto para decisão futura.
Referência (literatura/discussão, se aplicável): `pyogrio.read_info()` e amostragem via `geopandas.read_file(bbox=...)` ao vivo contra `grid.gpkg` e `BRA_grid_osm.geojson` (2026-09-08); `local_layers.py::resolve_grid_path()` docstring (Fase 1, já sinalizava o arquivo como não investigado); gridfinder — Arderne, C. et al., "Predictive mapping of the global power system using open data" (Nature Scientific Data, 2020), dataset usado por `source=gridfinder`.

---

## [2026-09-08] - grid_alignment (Fase 2a) portado do legado — schema, lógica, testes
Tipo: STRUCTURAL_PRESERVE | METHODOLOGY_REVISION
Descrição: implementado `src/geofrea/grid_alignment/` (schemas.py, reference_grid.py, raster_alignment.py, vector_alignment.py, alignment.py), portando `geoworld_framework/src/processors/grid_aligner.py` (`GridAligner` + funções module-level) quase inteiro. Dependências novas: `core/raster_io.py` (`safe_raster_open`/`safe_raster_write`/`gdal_quiet`, não existiam no GeoFREA — `data_quality_audit` só lê rasters, nunca escreve), `core/constants.py` (+`NODATA_FLOAT`/`NODATA_UINT8`/`WIND_HEIGHT_KEYS`/`WIND_AHP_MATRIX`/`AHP_RANDOM_INDEX`), `pyproject.toml` (+`scipy>=1.11`, para `distance_transform_edt`). `run_grid_alignment_phase(context, inputs)` segue a mesma ordem de parâmetros de `run_audit_phase(context, inputs)` (corrigido durante a escrita dos testes — a primeira versão tinha `(inputs, context)`, invertido em relação à convenção já estabelecida).

**Correção de design do Passo 1 (fechada antes da implementação)**: `GridAlignmentInputs.roads_source`/`grid_source` apontam sempre para o `AcquiredLayer.path` bruto, nunca para artefato de `data_quality_audit`. `grid_alignment` chama `read_clipped_to_country()` por conta própria para `roads`/`lakes`/`rivers` (fontes globais), com cache em `outputs/<country>/processed/{layer}_clipped.gpkg` — mesma convenção de path que `audit.py` já usa. Reuso por convenção de arquivo em disco, não por dependência de `PhaseResult` — `grid_alignment` funciona mesmo com `data_quality_audit` desligado em `run.phases`, só paga o clip a frio nesse caso. Confirmado ao vivo: segunda chamada de `run_grid_alignment_phase()` reaproveita o cache de `roads`/`lakes`/`rivers` sem tocar `read_clipped_to_country()` de novo (testes + smoke test).

**Decisões confirmadas por Douglas durante a revisão do porte**:
1. Estendido o mesmo tratamento (clip+cache via `read_clipped_to_country()`) de `roads` também para `lakes`/`rivers` — mesma fonte global, mesmo princípio do Passo 1, não uma extrapolação nova.
2. `detect_island_nation()` (`core/geo_utils.py`) **não é chamada** por `grid_alignment` — no legado só `data_auditor.py` a chama, sobre o `border_gdf` bruto (multi-polígono); `GridAlignmentInputs.country_gdf` já chega mainland-filtrado (mesmo contrato de `AuditInputs.country_gdf`), então chamá-la aqui seria vazia por construção (um polígono só, sempre "100%").
3. `get_mainland_gdf()` também não é chamada dentro de `grid_alignment` — no legado, `main.py` computa `mainland_gdf` uma vez e passa o mesmo objeto para `DataAuditor` e `GridAligner`; o porte preserva essa divisão de responsabilidade.

**Débito técnico registrado explicitamente (não é só nota de docstring)**: `alignment.py::_read_clipped_with_cache()` duplica ~10 linhas da função privada homônima em `data_quality_audit/vector_inspection.py`, em vez de compartilhar código entre pacotes de fase — decisão deliberada (tocar `vector_inspection.py` estava fora do escopo autorizado desta tarefa), mas é a MESMA classe de risco que motivou a extração de `_country_window()` em `raster_inspection.py` poucas sessões atrás (DECISIONS.md 2026-09-08, Fase 2 — roads/GRIP4): duas cópias da mesma lógica, idênticas hoje, sem nada impedindo divergência silenciosa no futuro. Aceito por ora por decisão explícita de Douglas ("não pediria para consolidar agora"); candidato a extração para `core/geo_utils.py` (função pública compartilhada por ambas as fases) numa sessão futura que tenha escopo para tocar `data_quality_audit`.

**Achado novo, ported as-is, pergunta em aberto para o Passo 6**: `_execute_or_load("land_cover", ...)` confere cache em `{code}_land_cover_aligned.tif`, mas `mosaic_land_cover()` escreve em `{code}_lc_aligned.tif` — nomes diferentes, cache nunca bate, `land_cover` recalcula do zero a cada execução (bug de performance do legado, não de correção — o path retornado está certo). Travado por teste (`test_run_grid_alignment_phase_land_cover_never_hits_alignment_cache`). Por instrução de Douglas, **não corrigido agora** — mas antes de aceitar como "não bloqueante", falta responder: qual o custo real desse recálculo repetido para BRA (mosaico de até 155 tiles)? Pergunta explicitamente adiada para a validação real PRT/BRA do Passo 6, não decidida aqui.

**Duas observações de código estruturalmente morto, corrigido aqui de uma imprecisão do relatório original (nem as duas vêm do legado — ver pergunta de Douglas na revisão)**: (a) `alignment.py::_clipped_gdf()`'s própria checagem `if not _exists(source_path): return None` **NÃO vem do legado — é código novo**, escrito nesta sessão como parte da correção de design do Passo 1. É inalcançável na prática porque o `condition` passado a `_execute_or_load()` nos 3 call sites existentes (`roads`/`lakes`/`rivers`) já testa exatamente a mesma condição antes de `fn()` ser chamada — uma guarda defensiva redundante, não um bug: não há dois nomes de arquivo divergentes nem comportamento incorreto, ao contrário do caso `land_cover` acima; protegeria um uso futuro hipotético com path diferente do da condição externa. (b) `raster_alignment.py::combine_wind_layers()`'s `if not mapped: raise ValueError(...)` **essa sim, idêntica ao legado** (`_combine_wind_layers()`, mesmo trecho) — inalcançável porque o próprio loop garante que o primeiro arquivo não identificado sempre popula `mapped["100m"]`, e a lista vazia já é barrada antes por um `ValueError` separado; já nascia morta no legado, portada fielmente. Nenhuma das duas é sintoma de outro bug da classe do mismatch `_land_cover_aligned.tif`/`_lc_aligned.tif` — são guardas "nunca deveria acontecer", não inconsistências silenciosas.

**Confirmação explícita do item 2 (Passo 3)**: `_verify_alignment()` levanta `RuntimeError` para mismatch de dimensões; a chamada em `run_grid_alignment_phase()` não está dentro de nenhum `try/except` — confirmado por leitura estática (`grep` no arquivo) e por execução ao vivo (mock forçando uma camada com dimensões erradas, `RuntimeError` propagou sem captura). Travado por dois testes: um isolado (`_verify_alignment` chamado diretamente) e um ponta-a-ponta (`run_grid_alignment_phase` real, mock em `reproject_to_grid`), mais um guard estático via `ast` que falha se uma edição futura envolver a chamada num `try/except`.

**Testes + cobertura**: 68 testes novos (`test_core_raster_io.py`, `test_grid_alignment_{schemas,reference_grid,raster_alignment,vector_alignment,alignment}.py`), suíte completa 322 → **390** (+68). Cobertura do pacote `grid_alignment/` + `core/raster_io.py`: **98%** (451 statements, 7 miss — 5 em `gdal_quiet()`'s ramo com bindings reais do GDAL, ausente neste ambiente; 2 nos trechos estruturalmente mortos do parágrafo acima). `ruff check` limpo em `src/` e `tests/` inteiros.
Justificativa (se METHODOLOGY_REVISION): fecha o porte da Fase 2a do legado (`GridAligner`) para o GeoFREA, preservando o comportamento científico do legado (fórmulas, limiares, matriz AHP) sem decidir nenhum dos 4 pontos metodológicos pendentes (Bowring, raios de busca, `target_pixels`, matriz AHP — todos marcados `# TODO: pending Passo 4 methodological review` no código), e corrigindo apenas o acoplamento de fase indevido identificado na auditoria prévia (Passo 1), não a lógica científica em si.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/grid_aligner.py` (porte linha a linha, ver docstrings de cada módulo novo para os números de linha exatos); `docs/architecture/grid_alignment.md` (auditoria Fase 0, 2026-08-19); auditoria read-only desta mesma sessão (2026-09-08, achado do `grid.gpkg` acima); `docs/DECISIONS.md` 2026-08-20 "orchestrator + data_quality_audit phase" (princípio de `prior_results` somente-leitura, preservado); `docs/DECISIONS.md` 2026-09-08 "wire das 5 camadas... Fase 2" (precedente da extração de `_country_window()`, citado para o débito técnico acima).

---

## [2026-09-08] - grid_alignment orchestrator wiring — adapter + terceiro PhaseSpec
Tipo: STRUCTURAL_PRESERVE
Descrição: pré-requisito para o Passo 6 (validação real da pipeline completa). Criado `src/geofrea/grid_alignment/adapter.py::acquisition_result_to_grid_alignment_inputs()`, mesmo padrão de `data_acquisition/adapter.py::acquisition_result_to_audit_inputs()`, e registrado `grid_alignment` como terceiro `PhaseSpec` em `main.py::_build_phase_specs()` (`_grid_alignment_run()`, closure por-contexto — não `functools.partial` eager, mesmo padrão de `_audit_run()`, evitando repetir a forma exata do problema que motivou a remoção de `UnwiredPhasesError` em 2026-08-25).

**Divergência encontrada e corrigida antes de codar (reportada e confirmada por Douglas antes de prosseguir)**: a instrução original pedia construir `GridAlignmentInputs` a partir de `AcquisitionResult` + `AuditResult`, com `country_gdf` vindo "do audit via `get_mainland_gdf()`". Verificado que isso não corresponde ao código real: `AuditResult` não tem campo `country_gdf` (só existe em `AuditInputs`, descartado após uso interno de `audit.py`), e `get_mainland_gdf()` é chamado por `data_acquisition/adapter.py`, nunca por `data_quality_audit`. O adapter novo depende só de `AcquisitionResult` — mais consistente com o princípio já fechado no Passo 1 (grid_alignment não depende do `PhaseResult` de `data_quality_audit`); dependesse de `AuditResult`, reintroduziria esse acoplamento uma fase adiante.

**`country_gdf` obrigatório, falha alto na construção do adapter**: se `layers["borders"]` estiver ausente ou com `path=None`, `acquisition_result_to_grid_alignment_inputs()` levanta `GridAlignmentRequiresBordersError` (nova, `ValueError`) imediatamente — mesma classe de tratamento de `ClipRequiresCountryGdfError` (`vector_inspection.py`, 2026-08-26): gap de configuração, não problema de arquivo, deve falhar alto e cedo, não aparecer como erro confuso dentro de `run_grid_alignment_phase()`. `main.py::_build_grid_alignment_inputs()` tem sua própria falha alto separada (`RuntimeError`) para o caso anterior — `data_acquisition` nem ter rodado nesta pipeline — já que `grid_alignment`, ao contrário de `data_quality_audit`, não tem modo degradado com inputs vazios.

**Duplicação evitada por extração, não mecanicamente copiada (conforme instrução explícita, mesmo cuidado do débito técnico do `_read_clipped_with_cache()`)**: `core/geo_utils.py::load_mainland_boundary(path)` — extraído de `data_acquisition/adapter.py::_load_mainland_boundary()`, mecânico (`gpd.read_file()` + `get_mainland_gdf()`, sem tratamento de `None`), usado pelos dois adapters; cada um decide separadamente o que fazer quando o path está ausente (audit: `None`, degrada; grid_alignment: `GridAlignmentRequiresBordersError`, falha). `data_acquisition/adapter.py::load_power_plants_df()` também promovido de privado (`_load_power_plants`) para público pelo mesmo motivo — `grid_alignment/adapter.py` importa direto em vez de duplicar as 2 linhas. Diferente do caso `_read_clipped_with_cache()`: aqui a extração ficou dentro do escopo autorizado desta mesma tarefa (tocar `data_acquisition/adapter.py`/`core/geo_utils.py` foi parte do pedido), não um débito adiado.

**Independência de `data_quality_audit` confirmada pelo `Orchestrator` real, não só em docstring**: `test_orchestrator_runs_grid_alignment_with_data_quality_audit_disabled` roda `Orchestrator.run()` de verdade com `phases_enabled={"data_acquisition": True, "data_quality_audit": False, "grid_alignment": True}`, usando as closures reais de `main.py` (`_audit_run`/`_grid_alignment_run`) e um stub só para `data_acquisition` (evita rede/fetch real num teste unitário) — confirma `"data_quality_audit" not in results` (nunca tentada) e `grid_alignment` completando com sucesso mesmo assim.

**wind — gap conhecido, não corrigido aqui**: `AcquisitionResult` só guarda UM `AcquiredLayer.path` para `wind` (não está em `MULTI_FILE_LAYER_NAMES`), então o adapter nunca consegue produzir mais que uma lista de 1 elemento para `GridAlignmentInputs.wind_paths`, mesmo `combine_wind_layers()` tendo sido portado para combinar até 3 alturas via AHP (capacidade real do legado). Não é bug do adapter — é limitação estrutural de `data_acquisition`'s registro de camadas, fora do escopo desta tarefa (mudaria `AcquiredLayer`/`MULTI_FILE_LAYER_NAMES`). Sinalizado, não corrigido.

**Testes**: 14 novos (`test_grid_alignment_adapter.py`, 8; `test_main.py`, 6 — incluindo o teste de independência do `Orchestrator` acima). Suíte completa 390 → **404** (+14). Cobertura 100% em `grid_alignment/adapter.py` e `data_acquisition/adapter.py`; `core/geo_utils.py` 96% (misses pré-existentes em `detect_island_nation()`, não relacionados a `load_mainland_boundary()`, que está 100% coberta). `ruff check` limpo em `src/`, `tests/` e `main.py`.

Não rodada nenhuma pipeline real nesta tarefa — reservado para o Passo 6, na sequência, após este wiring aprovado e commitado.
Justificativa (se METHODOLOGY_REVISION): N/A (STRUCTURAL_PRESERVE) — nenhuma lógica científica alterada; só conecta `grid_alignment` (já portado, Passo 3) ao orchestrator, preservando os princípios de design já fechados (closure por-contexto, independência de `data_quality_audit`, falha alto em vez de degradação silenciosa).
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-25 "data_acquisition activation" (origem do padrão de closure por-contexto e da remoção de `UnwiredPhasesError`); `docs/DECISIONS.md` 2026-08-26 (origem de `ClipRequiresCountryGdfError`, modelo para `GridAlignmentRequiresBordersError`); `docs/DECISIONS.md` 2026-09-08 "grid_alignment (Fase 2a) portado do legado" (Passo 1/3, princípios de independência de fase preservados aqui); divergência reportada e resolvida com Douglas antes de escrever qualquer código, nesta mesma sessão.

---

## [2026-09-09] - Passo 6: validação real PRT/BRA + correção do mismatch de land_cover (achado do Passo 3)
Tipo: STRUCTURAL_PRESERVE
Descrição: Passo 6 (validação real da pipeline completa, `data_acquisition` + `data_quality_audit` + `grid_alignment`, as três habilitadas juntas em `settings.yaml`) rodado ao vivo para PRT e depois BRA, sequencialmente (nunca em paralelo), com RAM monitorada continuamente (threshold de risco 1.0GB livre, com base no incidente histórico de `population`/BRA documentado em `docs/PROGRESS.json`). `manifest.json`/`processed/` pré-existentes de sessões anteriores foram movidos para backup (`*.bak_preP6`/`*_backup_preP6`, não apagados) antes de cada país, para forçar execução real das três fases nesta mesma corrida (sem isso o `Orchestrator` resumiria `data_acquisition`/`data_quality_audit` do manifesto, sem executar nada — ver precedente da mesma decisão operacional em 2026-08-26/2026-09-08).

**Resultado da validação**: PRT completo em 174s (RAM livre mínima 5,93GB de 15,84GB); BRA completo em 4198s/~70min (RAM livre mínima 3,59GB, durante `population`, consistente com a correção de 2026-09-08 que elevou o mínimo de 0,14GB para ~4,29GB — não regrediu). Nenhum kill acionado em nenhum país. Nenhum `RuntimeError` de `_verify_alignment()` em nenhum país — ambos terminaram com `Phase 'grid_alignment' completed.`, exit code 0. Cache de `roads`/`lakes`/`rivers` entre `data_quality_audit` e `grid_alignment` confirmado reaproveitado **por timestamp** (não presumido): mtime dos três `.gpkg` em `outputs/{país}/processed/` cai dentro da janela de execução do audit, nunca na janela do `grid_alignment`, nos dois países.

**Achado confirmado com custo real, respondendo a pergunta deixada em aberto no Passo 3**: o mismatch de nome `_execute_or_load("land_cover", ...)` (checava `{code}_land_cover_aligned.tif`) vs. `mosaic_land_cover()` (escrevia `{code}_lc_aligned.tif`) — ver entrada 2026-09-08 "grid_alignment (Fase 2a) portado do legado" — custava **529,7s (~8,8min) por execução de `grid_alignment`/BRA**, sempre recalculado, nunca cacheado (155 tiles land_cover). Para PRT (26 tiles) o custo é irrelevante (6,7s). Reportado a Douglas com os números reais; autorizado a corrigir na mesma sessão.

**Correção aplicada**: `alignment.py`'s lambda de `land_cover` passou a escrever em `_path("land_cover")` em vez de `_path("lc")` — "land_cover" adotado como nome canônico (não um terceiro nome), por ser a convenção que toda outra camada do módulo já segue (o label passado a `_execute_or_load()` É o sufixo em disco). Puramente correção de performance — o path retornado já estava correto antes, nenhuma mudança de conteúdo do mosaico, nenhuma decisão metodológica, não é `METHODOLOGY_REVISION`.

**Teste**: `test_run_grid_alignment_phase_land_cover_never_hits_alignment_cache` (que travava o comportamento buggy, `call_count == 2`) renomeado para `test_run_grid_alignment_phase_land_cover_hits_alignment_cache_on_second_run` e invertido para `call_count == 1`. Confirmado ao vivo, via `git stash` isolando só a correção em `alignment.py`, que o teste invertido FALHA contra o código pré-fix (`assert 2 == 1`) — não é um teste que passaria de qualquer forma. Suíte completa: 404 → **404** (mesma contagem, um teste renomeado/invertido, não adicionado) — `pytest tests/unit/` limpo, sem regressão.

**Revalidação ao vivo pós-fix, com dados reais de BRA (155 tiles)**: script descartável chamando `run_acquisition_phase()` + `run_grid_alignment_phase()` diretamente duas vezes seguidas (reaproveitando os caches `processed/` já populados pela corrida completa do Passo 6, sem re-pagar os ~58min de `data_quality_audit`). Rodada 1 (nome antigo `BRA_lc_aligned.tif` não bate com o novo cache-check `BRA_land_cover_aligned.tif`, então recalcula uma última vez): 423,7s. Rodada 2: `land_cover` completa em **0,0s** (cache hit), fase inteira em 0,74s — confirma a correção com os tiles reais de BRA, não só com o teste unitário mockado. `outputs/BRA/grid_alignment/BRA_lc_aligned.tif` (nome antigo) ficou órfão no disco, não referenciado por nenhum código — não removido nesta sessão (artefato de output, não rastreado por git, sem risco).

**Nota separada, NÃO implementada nesta sessão — candidata a otimização futura**: `data_quality_audit`'s própria inspeção de `land_cover` (`inspect_land_cover_tiles()`, diferente da função de mosaico do `grid_alignment`) custou **2199,9s (~36,7min) para BRA** nesta mesma corrida do Passo 6 — maior que o próprio custo do mosaico (529,7s) e sem nenhuma relação com o bug corrigido acima; é custo estrutural de inspecionar as 155 tiles a cada execução do audit, sem nenhum cache por-tile (diferente do que já existe para os vetores, `_read_clipped_with_cache()`). Achado sinalizado por instrução explícita de Douglas como candidato a otimização futura (ex.: cache de inspeção por tile, mesmo princípio do cache vetorial) — sem escopo, sem prioridade definida, sem ação nesta tarefa.

Justificativa (se METHODOLOGY_REVISION): N/A (STRUCTURAL_PRESERVE) — correção de bug de performance puro, autorizada por Douglas após medição real do custo (529,7s/execução/BRA) no Passo 6; nenhuma lógica científica ou path de saída alterado, só o nome do arquivo de cache intermediário.
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-08 "grid_alignment (Fase 2a) portado do legado" (achado original do mismatch, pergunta sobre custo real explicitamente adiada para o Passo 6); `docs/DECISIONS.md` 2026-09-08 "grid_alignment orchestrator wiring" (pré-requisito de wiring para esta validação); `docs/PROGRESS.json` (incidente histórico de RAM que motivou o threshold de 1.0GB usado aqui); logs reais desta sessão (PRT/BRA, `main.py` completo, e revalidação isolada pós-fix); instrução e autorização explícitas de Douglas nesta sessão (autorizar a correção, escolher "land_cover" como nome canônico e não um terceiro nome, registrar como correção do Passo 3 e não entrada solta, sinalizar mas não implementar a otimização do audit).

---

## [2026-09-09] - Passo 4: os 4 vereditos metodológicos de grid_alignment (Bowring, raios de busca, resolução adaptativa, AHP de vento)
Tipo: STRUCTURAL_PRESERVE (itens 2 e 4) | METHODOLOGY_REVISION (itens 1 e 3, ver justificativas)
Descrição: os 4 pontos metodológicos deixados pendentes no porte de `grid_alignment` (`docs/DECISIONS.md` 2026-09-08 "grid_alignment (Fase 2a) portado do legado", `# TODO: pending Passo 4 methodological review` espalhados pelo código) foram investigados em paralelo, apresentados com trade-offs e números reais, e decididos por Douglas numa única passada — cada um reportado antes de qualquer código ser escrito, nenhuma implementação até aprovação explícita.

**Item 1 — fórmula geodésica Bowring (3 variantes truncadas, `docs/architecture/grid_alignment.md` §e.1)**: medi o erro real de cada variante contra a mais completa (`data_quality_audit/raster_inspection.py::row_area_km2()`, 4 termos lat/3 termos lon) nas latitudes reais de PRT (~39,5°N) e BRA (~-10° a -30°): a variante de `grid_alignment/vector_alignment.py::calculate_wgs84_isotropic_distance()` (3 termos lat) diverge ~0,000001% (~1cm/100km); a variante mais truncada, usada só no cálculo de resolução adaptativa (2 termos lat/lon), diverge ~0,001% (~1m/100km) — ambas desprezíveis. Decisão de Douglas: centralizar mesmo assim, "mesmo padrão de `_country_window()`, `MULTI_FILE_LAYER_NAMES`" — remove a duplicação de fórmula científica independente do ganho de precisão ser nulo. Implementado `src/geofrea/core/geodesy.py::wgs84_km_per_degree(lat_deg)` (precisão completa, aceita escalar ou array numpy), consumida agora pelas 3 chamadas: `raster_inspection.py::row_area_km2()`, `vector_alignment.py::calculate_wgs84_isotropic_distance()`, e `alignment.py`'s cálculo de resolução adaptativa (ver item 3). Testado isoladamente (`tests/unit/test_core_geodesy.py`, 4 casos, incluindo comparação contra uma reimplementação independente da fórmula completa, não importada de `geodesy.py`) — `rel=1e-12` de tolerância, útil como guarda de regressão futura, não como prova do erro medido acima (esse foi medido fora do código, ver acima).

**Item 2 — raios de busca divergentes (100km roads/grid vs. 50km rivers inline, `grid_alignment.md` §c item 4)**: investigação encontrou que `criteria_builder.py` (Fase 2b/3 do legado, ainda não construída no GeoFREA) aplica seu próprio decaimento de proximidade sobre os `*_aligned.tif` que `grid_alignment` produz, com distâncias muito menores — `compute_road_suitability` (default `road_max_dist_km=5.0`, `criteria_defaults.yaml`: `roads.max_dist_km=15.0`), `compute_grid_suitability` (`grid_max_dist_km=20.0`), `compute_river_suitability` (`rivers.max_dist_km=5.0` solar/wind, `rivers.max_dist_biomass_km=30.0`). O maior desses valores downstream (30km) já fica abaixo do menor cap do `grid_alignment` (50km, rios) — a divergência 100 vs. 50 não tem efeito mensurável no resultado final, confirmado antes de decidir, não presumido. Decisão de Douglas: unificar em 100km, "é limpeza de código, não decisão metodológica". Implementado `core/constants.py::LINEAR_FEATURE_MAX_DIST_KM = 100.0`; `vector_alignment.py::align_rivers()` ganhou um parâmetro `max_dist_km` explícito (sem default, mesma convenção "visível em cada call site" que `rasterize_linear_distance()` já usava), removendo o `np.clip(dist_km, 0, 50)` inline. `GridAlignmentInputs.max_dist_km` (novo campo, default `LINEAR_FEATURE_MAX_DIST_KM`) alimenta as 3 chamadas (`roads`/`grid`/`rivers`) em `alignment.py`. Teste `test_align_rivers_caps_distance_at_50km` renomeado para `..._at_max_dist_km` (agora parametrizado por `max_dist_km`, não mais um literal 50 hardcoded no teste); novo teste `test_run_grid_alignment_phase_passes_inputs_max_dist_km_to_roads_and_rivers` confirma via mock que um `max_dist_km` não-default (77.0) chega às duas chamadas.

**Item 3 — resolução adaptativa (`target_pixels=50000`/`min_deg`/`max_deg`, `grid_alignment.md` §c item 1, §e.3) — ACHADO MAIS SÉRIO DOS QUATRO**: confirmei que `target_pixels=50000` não controla a resolução de BRA na prática — a resolução não-clipada que a fórmula pediria é ~0,175°, muito acima do teto `max_deg=0,05°`, então BRA sempre bate no teto independente de `target_pixels` (só PRT, país pequeno, fica dentro da faixa `[min_deg, max_deg]`). Mais grave: `configs/settings.yaml` do legado (arquivo real, não o fallback do código) tinha `geospatial.resolutions.suitability: 0.01` fixo ("~1 km — consistent with global climate datasets") — o modo `"adaptive"` existia no código do legado mas **nunca foi o valor configurado** na execução real que gerou o baseline congelado. Confirmei inspecionando os rasters do baseline com `rasterio`: PRT `outputs_baseline_fc7b43d/PRT/suitability/tif/PRT_biomass_suitability.tif` = resolução 0,01°, 333×518px; BRA = 0,01°, 3920×3902px. O GeoFREA, antes desta correção, portava só o caminho de código `"adaptive"` (nunca de fato usado pelo legado) como comportamento hardcoded único — produzindo BRA em 785×781px (0,05°, teto do modo adaptive) contra os 3920×3902px do baseline, **~25× menos pixels**. Qualquer comparação de regressão pixel-a-pixel futura contra o baseline seria inviável nesse estado, não por tolerância `rtol`, mas por grades de dimensões diferentes.

Decisão de Douglas: portar resolução fixa 0,01° como padrão — "a única opção que preserva a possibilidade de validação científica [...] o baseline congelado [...] foi gerado com 0,01°, não com adaptive". Implementado: `config/settings.yaml` ganhou a seção `geospatial.resolutions` (nova, `suitability: 0.01` + bloco `adaptive` com os 3 fallbacks do legado inalterados); `core/schemas.py` ganhou `ResolutionsConfig`/`AdaptiveResolutionConfig`/`GeospatialConfig`, com `SettingsFile.geospatial` novo (default `GeospatialConfig()`, então nenhum `settings.yaml` existente quebra por omissão da seção). `GridAlignmentInputs` ganhou `resolution_deg: float | Literal["adaptive"]` (default `0.01`) + `adaptive_target_pixels`/`adaptive_min_deg`/`adaptive_max_deg` (defaults inalterados do legado: 50000/0.001/0.05). `adapter.py::acquisition_result_to_grid_alignment_inputs()` ganhou um parâmetro `resolutions: ResolutionsConfig | None` (None cai no default de `ResolutionsConfig()`, mesmo comportamento). `main.py`: `_build_phase_specs()`/`_build_grid_alignment_inputs()`/`run_geofrea()` agora recebem/repassam `resolutions` (fechado sobre a closure de `grid_alignment`, mesmo padrão per-context-closure de `_audit_run()`, não um `functools.partial` eager — `_grid_alignment_run()` como função de módulo separada foi removida, a closure agora é local a `_build_phase_specs()`). `alignment.py`'s bloco de resolução agora ramifica em `inputs.resolution_deg == "adaptive"` (recalcula pela fórmula, usando `core.geodesy.wgs84_km_per_degree()`, ver item 1) vs. fixo (usa `inputs.resolution_deg` direto) — "adaptive" preservado como opt-in explícito, não removido.

**Revalidação ao vivo, dados reais de PRT** (script descartável, `run_acquisition_phase()` + `acquisition_result_to_grid_alignment_inputs()` + `run_grid_alignment_phase()`, sem tocar `data_quality_audit`): `ResolutionsConfig()` default → `resolution_deg=0.01, width=333, height=518` — **match exato** com o baseline. `ResolutionsConfig(suitability="adaptive")` explícito → `resolution_deg≈0.01851, width=180, height=281` — bate exatamente com a corrida em modo adaptive do Passo 6, confirmando que o opt-in continua funcionando idêntico a antes.

**Item 4 — matriz AHP de vento (`WIND_AHP_MATRIX`/`AHP_RANDOM_INDEX`, `grid_alignment.md` §b item 2, §e.4) — lida em detalhe pela primeira vez**: matriz (ordem 200m/100m/50m) — `[[1,3,5],[1/3,1,3],[1/5,1/3,1]]`, escala de Saaty (moderada=3, forte=5). Calculei o resultado real de `compute_ahp_weights()` sobre essa matriz: λmax≈3,039, CI≈0,0195, RC≈0,034 — bem abaixo do limiar 0,10, ou seja, o fallback para pesos uniformes nunca é acionado na prática para essa matriz; pesos induzidos ≈ 63,3%/26,0%/10,6% (200m/100m/50m). Confirmei que o limiar RC>0,10 É padrão de literatura (Saaty, 1980), citado tanto em `docs/memory/04-algorithms.md` do legado ("required CR ≤ 0.10") quanto na própria auditoria arquitetural do GeoFREA (`grid_alignment.md` §c item 7) — não é escolha arbitrária. Busquei em todo o histórico git do legado (desde o commit inicial) e toda a documentação por uma fonte para os julgamentos pareados específicos (200m 3× sobre 100m, 5× sobre 50m) — não encontrei nenhuma. Nota importante: a referência de literatura que o legado cita para AHP (Al Garni & Awasthi, 2017) é do AHP de **Fase 3** (`suitability_builder.py`, ponderação de critérios de aptidão) — uma aplicação distinta do mesmo framework matemático, não desta combinação de alturas de vento da Fase 2a.

Decisão de Douglas: manter a matriz como está (`STRUCTURAL_PRESERVE`) — "a maquinaria [...] é literatura-fundamentada [...] os julgamentos pareados específicos não têm fonte, mas são plausíveis e não bloqueiam o porte" — mas registrar explicitamente como pergunta aberta, não apenas "mantido", porque "no dia em que suitability_criteria/Fase 3 for desenhada de verdade, alguém vai precisar decidir se essa falta de fonte é aceitável para uma tese ou se merece investigação/justificativa própria antes da defesa". Implementado: nenhuma mudança de comportamento — só os comentários em `core/constants.py` (`WIND_AHP_MATRIX`/`AHP_RANDOM_INDEX`) e `raster_alignment.py` (module docstring, `_compute_ahp_weights()`, `_combine_wind_layers()`) atualizados de "pending Passo 4" para o registro completo da decisão acima, citável quando a Fase 3 for desenhada.

**Testes**: 421 no total (404 → 421, +17) — `test_core_geodesy.py` (novo, 4 casos), `test_grid_alignment_alignment.py` (+7: 2 de resolução fixa, 2 de modo adaptive incluindo os clips de `min_deg`/`max_deg`, 1 de `max_dist_km` threading), `test_grid_alignment_adapter.py` (+3: default/fixo/adaptive de `resolutions`), `test_grid_alignment_vector_alignment.py` (4 testes de `align_rivers` atualizados para o novo parâmetro `max_dist_km`, sem `+`/`-` líquido), `test_main.py` (6 testes atualizados para as novas assinaturas — `_grid_alignment_run` como função de módulo removida, substituída por extrair a closure de `_build_phase_specs()` nos 2 testes que precisavam da wiring real). `ruff check` limpo em `src/`, `tests/` e `main.py` inteiros.

Justificativa (se METHODOLOGY_REVISION): item 1 é `METHODOLOGY_REVISION` técnica (mudança de arquitetura, não de ciência — centraliza 3 cópias idênticas em precisão, erro já desprezível antes da mudança, não altera nenhum resultado numérico). Item 3 é `METHODOLOGY_REVISION` real: muda o resultado numérico do pipeline (resolução/dimensões da grade) — justificativa: alinhar com o único valor que de fato gerou o baseline validado, tornando comparação de regressão possível pela primeira vez; sem essa mudança, `grid_alignment` produziria resultados estruturalmente incomparáveis ao baseline. Itens 2 e 4 são `STRUCTURAL_PRESERVE` (item 2: valor unificado é cosmético, confirmado sem efeito no resultado; item 4: nenhuma mudança de comportamento, só documentação).
Referência (literatura/discussão, se aplicável): `docs/architecture/grid_alignment.md` §b/§c/§e (achados originais dos 4 itens, auditoria 2026-08-19); `docs/DECISIONS.md` 2026-09-08 "grid_alignment (Fase 2a) portado do legado" (todos os 4 `# TODO: pending Passo 4` originais); `geoworld_framework/src/processors/data_auditor.py::_row_area_km2()` (fórmula Bowring completa, fonte do item 1); `geoworld_framework/src/processors/criteria_builder.py::compute_road_suitability/compute_grid_suitability/compute_river_suitability` (fonte do achado do item 2); `geoworld_framework/configs/settings.yaml` (fonte do achado do item 3 — valor real configurado, `suitability: 0.01`); `geoworld_framework/docs/memory/04-algorithms.md` (Saaty 1980, RC≤0.10, fonte do item 4); inspeção real via `rasterio` dos rasters de `outputs_baseline_fc7b43d/{PRT,BRA}` (resolução/dimensões reais do baseline, item 3); revalidação ao vivo desta sessão (PRT, dados reais, fixed vs. adaptive); as 4 decisões explícitas de Douglas coletadas numa única rodada de perguntas.

---

### 2026-09-10 — suitability_criteria parameter calibration

- protected_areas: simplified to binary mask (IUCN Ia/Ib/II excluded, rest free).
  iucn_category_scores table dropped as dead code (threshold made it inert in legacy).
- river_safety_buffer_km: fixed at 0.5 (500m) for all countries, changed from
  legacy's uncited internal value to an explicit reference: upper bound of
  Brazil's Código Florestal (Lei 12.651/2012, Art. 4) riparian buffer scale
  (500m applies to rivers >600m wide). No consistent cross-country standard
  exists (checked BR/PT/IN/PH/US); fixed conservative value chosen over
  per-country lookup to avoid unvalidated country-specific tables.
  Promoted from soft criterion to hard exclusion (river_solar, river_wind
  added to common_exclusions in Fase 3), since it represents a safety
  setback, not a preference.
- slope_threshold_deg: fixed cross-country defaults (not per-country):
  solar = 5 deg, wind = 25 deg (exclusion above), biomass = 15 deg
  (interpolated, no direct source). Replaces legacy's uncited additive
  offset (base + 5/10/20 deg). Sources: solar 5 deg cutoff and wind
  15-25 deg favorable / >25 deg unsuitable found in GIS siting suitability
  literature (search 2026-09-10, not systematic review).
- pop_density_threshold: lowered from legacy's 300 hab/km2 to 200 hab/km2,
  closer to comparable US solar-siting exclusion threshold (~193/km2).
  log1p penalty form kept unchanged (no source found, not flagged as
  problematic).
- road_max_dist_km = 15.0, river_max_dist_biomass_km = 30.0: confirmed via
  pixel-exact regression against outputs_baseline_fc7b43d/PRT (2026-09-10).
  These are the CountryParams schema defaults, not the function signature
  fallbacks (5.0/10.0), which are dead code and not ported.
- M1, M2, M4, M5, M6, M16, M19: no regulatory or literature equivalent
  exists (internal numerical tuning, not environmental/technical standard).
  Kept as STRUCTURAL_PRESERVE, no source found, author calibration.
- M9/M10/M11: resolved, see protected_areas entry above.
- M12, M13, M14, M15, M18: resolved, see entries above.

---

### 2026-09-10 — open tech debt: suitability_criteria pixel-exact regression harness

The 14 criteria rasters of Fase 2b should eventually be checked pixel-for-pixel
against `outputs_baseline_fc7b43d/{PRT,BRA}/criteria_builder/tif/` in CI, the
same way `road_max_dist_km` / `river_max_dist_biomass_km` were confirmed ad hoc
on 2026-09-10 (see "suitability_criteria parameter calibration" above). No such
harness exists yet.

This is open technical debt, NOT a blocker for implementing the phase: the phase
can be built and merged without it, and the harness added afterwards. Recorded
here so it is not lost. Related: `docs/architecture/module-mapping.md` cross-cutting
items (regression tolerance is already defined in `CLAUDE.md`, only the automated
comparison is missing).

---

## [2026-09-10] - suitability_criteria: compute_solar_resource guards NODATA_FLOAT under solar_pvout_weight

Tipo: METHODOLOGY_REVISION

Descrição: legacy `criteria_builder.py::compute_solar_resource` (L140-144), when
`solar_pvout_weight != 1.0`, does `score = np.where(np.isfinite(score), score * weight, score)`.
`NODATA_FLOAT` (-9999.0) is finite, so every invalid pixel would be multiplied by
the weight (e.g. -9999.0 -> -4999.5 at weight 0.5), corrupting the NoData sentinel
in the output raster. GeoFREA's port guards it: the multiplication mask is
`np.isfinite(score) & (score != NODATA_FLOAT)`, so invalid pixels keep the sentinel.

Justificativa: `solar_pvout_weight` defaults to 1.0, at which the branch never runs,
so this has ZERO effect on the frozen PRT/BRA baseline or its regression tests
(confirmed: `solar_resource` is pixel-exact vs `outputs_baseline_fc7b43d/PRT`,
`max|delta|=0`, with the guard in place). The revision only changes behaviour for a
non-default weight, where the legacy result was unambiguously wrong (a NoData
sentinel is not a score to be scaled). No literature reference — this is a
correctness fix, not a scientific-method change. Authorised by Douglas 2026-09-10
as a guard (not STRUCTURAL_PRESERVE).
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_solar_resource`;
`docs/architecture/suitability_criteria_audit.md` sec 3b / M-item table; unit test
`test_compute_solar_pvout_weight_preserves_nodata`.

---

## [2026-09-10] - suitability_criteria: terrain_score denominator is per-country (4th slope_threshold use)

Tipo: STRUCTURAL_PRESERVE (correção da auditoria, não revisão de método)

Descrição: a auditoria original (`docs/architecture/suitability_criteria_audit.md`
sec 8a, 2026-09-10) tratou TODO `slope_threshold_deg` como cross-country e listou
três usos: (1) `technologies.{tech}.slope_threshold_deg` = 8.5/5/8.5, o diagnóstico
de inatividade de slope do `data_quality_audit`; (2) `criteria.slope_threshold_deg_{tech}`
= 5/25/15, o portão de exclusão de siting fixo cross-country da Fase 2b/3; (3) o
fallback literal `7.0` na assinatura de `compute_terrain_score` (código morto, não
portado). A implementação do pacote terrain_score/slope_degrees/lc_biomass/
biomass_resource revelou um QUARTO uso: `compute_terrain_score`'s denominador do
sub-score contínuo de slope (`clip(1 - slope/threshold, 0, 1)`) lê o campo
**country-level** `slope_threshold_deg` do legado, cujo valor real varia por país —
PRT=10, BRA=12 (EGY=5, CHN/RUS/IND/ZAF=12). É um score contínuo tech-agnóstico,
distinto do portão de exclusão; nenhum dos valores 5/25/15 o reproduz.

Correção, não omissão: a auditoria foi feita antes de implementar e não abriu
`compute_terrain_score` linha a linha (só a fórmula). GeoFREA cria
`CountryParams.criteria` (sub-model `CountryCriteriaParams`, o nome que a §8a havia
RESERVADO "para quando aparecer um segundo parâmetro per-country de critério" — ele
apareceu), contendo `yield_by_land_cover` (movido de `CountryParams` direto) +
`terrain_slope_threshold_deg` (novo). Valores portados verbatim do legado @ fc7b43d.

Justificativa: preserva o comportamento científico do legado exatamente — a
regressão pixel-a-pixel de `terrain_score` contra `outputs_baseline_fc7b43d`
confere `max|delta|=0` para PRT (denominador 10) E BRA (denominador 12); os
`terrain_slope_threshold_deg` foram promovidos a `verified: true / automated /
2026-09-10` em `parameters.json` na sequência. `slope_degrees`, `lc_biomass`,
`biomass_resource` (o resto do pacote) também conferem `max|delta|=0` para PRT e
BRA. Os três usos de `slope_threshold_deg` já documentados continuam válidos e
NÃO são unificados com este quarto — cada um tem propósito e números distintos.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_terrain_score` (L167-220, `_param(params, "slope_threshold_deg", 7.0)`);
`geoworld_framework/configs/parameters.json` (`countries.<ISO>.slope_threshold_deg`: PRT 10, BRA 12);
`docs/architecture/suitability_criteria_audit.md` sec 8a; `docs/DECISIONS.md`
2026-08-20 - slope_threshold_deg moved to parameters.json (uso 1) e 2026-09-10 -
suitability_criteria parameter calibration (uso 2); regressão
`tests/regression/test_suitability_criteria_regression.py`.

---
## [2026-09-10] - suitability_criteria: compute_biomass_resource exclui land_cover == 255 explicitamente
Tipo: STRUCTURAL_PRESERVE (correção de guard — mesma classe do fix de `solar_pvout_weight`)

Descrição: `compute_biomass_resource` (porte de `criteria_builder.py::compute_biomass_resource`,
L388-432) usava `valid_base = (lc != nodata) & (lc > 0)`, SEM excluir a classe 255
explicitamente — ao contrário de `compute_lc_biomass`, que sempre teve
`& (lc != 255)`. No legado isso era inofensivo apenas porque o raster de land-cover
alinhado é sempre escrito com `nodata == 255` (`NODATA_UINT8`): `lc != nodata` já
dropava esses pixels. GeoFREA torna a exclusão explícita
(`valid_base &= lc_data != 255`), fechando a dependência implícita entre
`compute_biomass_resource` e a convenção de `nodata=255` do `grid_alignment`
(`raster_alignment.py::mosaic_land_cover`). Não é decisão de valor sem fonte nem
calibração — é fechamento de dependência implícita, mesma natureza do guard de
`solar_pvout_weight` (2026-09-10).

Comportamento diagnosticado antes do fix (array sintético, `nodata` variando):
com `nodata == 255` (todos os dados reais) os pixels 255 já eram excluídos e
ficavam `NODATA_FLOAT`; com `nodata != 255` eles virariam terra válida com yield
0.0 via a linha catch-all `raw[(raw == NODATA_FLOAT) & valid_base] = 0.0` (não via
`.get()` com default), depois suavizados e normalizados — score válido baixo
espúrio. Sem exceção, sem NaN. A regressão PRT/BRA cobre massivamente pixels 255
(46% / 53% dos rasters) mas só o ramo `nodata == 255`.

Justificativa: a regressão pixel-a-pixel de `biomass_resource` contra
`outputs_baseline_fc7b43d` segue `max|delta|=0` para PRT e BRA após o fix (ambos
os rasters legados têm `nodata == 255`, então o ramo exercitado é idêntico). Inerte
no pipeline atual; elimina risco latente se um land-cover externo com pixels 255 e
`nodata` não-255 for alimentado.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py::compute_biomass_resource` (L388-432) vs `::compute_land_cover_scores` (L355-385, `& (lc != 255)`);
`src/geofrea/grid_alignment/raster_alignment.py::mosaic_land_cover` (nodata=NODATA_UINT8);
`docs/DECISIONS.md` 2026-09-10 - compute_solar_resource guards NODATA_FLOAT (mesma classe de fix);
regressão `tests/regression/test_suitability_criteria_regression.py::biomass_resource`.

---
## [2026-09-10] - suitability_criteria: pacote 4 fecha os 14 critérios; protected_areas é o único sem paridade bit-exata
Tipo: VERIFICATION_UPDATE

Descrição: o pacote 4 (`protected_areas` + `pop_suitability` + `seismic_suitability`)
foi implementado, fechando os 14 critérios canônicos da Fase 2b. Estado de
regressão contra `outputs_baseline_fc7b43d` (PRT + BRA):

- **13 de 14 critérios: `max|delta| = 0` pixel-a-pixel** (solar_resource,
  wind_resource, terrain_score, lc_biomass, biomass_resource, pop_suitability,
  road_suitability, lakes_exclusion, river_solar, river_wind, river_biomass,
  seismic_suitability, grid_suitability) — mais `slope_degrees` (artefato
  cartográfico, não critério).
- **`pop_suitability`**: bit-exato apenas com `pop_density_threshold = 300.0`
  (o valor que gerou o baseline). A produção usa `200.0` por decisão de
  calibração já registrada (2026-09-10 "suitability_criteria parameter
  calibration", METHODOLOGY_REVISION). A regressão força 300.0 via override de
  teste (`_CRITERIA_POP_300`) e passa `max|delta| = 0` — prova de fidelidade da
  fórmula; a divergência em produção é intencional, não defeito de porte.
- **`protected_areas` é o ÚNICO dos 14 critérios sem paridade bit-exata** contra
  o baseline congelado. Motivo: o baseline usa a tabela IUCN graduada
  (`IUCN_SCORES`, valores 0.0/0.25/0.30/0.45/0.55); o contrato aprovado
  (`suitability_criteria_audit.md` §5 / M9-M10, 2026-09-10) descarta essa
  tabela como código morto — o limiar de exclusão dura da Fase 3 (`0.99`) já a
  tornava inerte — e adota **máscara binária**: categoria ∈
  `iucn_strict_categories` → `0.0`, qualquer outra feição WDPA ou terra livre →
  `1.0`. É decisão de contrato **pós-baseline**, não lacuna de porte. A regressão
  de `protected_areas` verifica: (a) footprint mainland idêntico ao frozen
  pixel-a-pixel (PRT 93.149 / BRA 7.100.137 válidos, batendo `n_valid_pixels` do
  `grid_metadata`), (b) valores estritamente ∈ {0.0, 1.0}, (c)
  `protected_source == "wdpa"` e presença de exclusões estritas — não os valores
  das células.

WDPA lido via `read_clipped_to_country` (D9) + `_resolve_wdpa_shapefile` (aceita
`.shp` ou diretório, prefere `*polygon*.shp` — espelha o probe do legado
L463-472). `pop`/`seismic` são portes verbatim das funções do legado
(`compute_population_suitability` L518-533, `compute_seismic_suitability`
L580-593); `seismic` parametriza os percentis 2/98 (M8) via `criteria`.

Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py` (`compute_protected_areas` L435-515, `compute_population_suitability` L518-533, `compute_seismic_suitability` L580-593);
`docs/architecture/suitability_criteria_audit.md` §5, §8a (M8/M9/M10/M11);
`docs/DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration" (pop_density_threshold 300→200) e 2026-08-19 (categorias IUCN estritas);
regressão `tests/regression/test_suitability_criteria_regression.py` (`seismic_suitability`, `pop_suitability`, `test_protected_areas_footprint_matches_frozen`).

---
## [2026-09-11] - suitability_builder (Fase 3): mecanismo final do buffer de segurança de rio em common_exclusions
Tipo: STRUCTURAL_PRESERVE (esclarecimento de mecanismo — nenhum código nesta passagem)

Descrição: fixa COMO a promoção de `river_safety_buffer_km` a hard exclusion
(decidida em 2026-09-10 ponto 7) se materializa na Fase 3, para não haver
ambiguidade quando `suitability_builder`/`suitability_analysis` for construído
(hoje stub vazio). Nenhum `common_exclusions` nem código de exclusão é
implementado agora — isso fica para a construção completa da Fase 3.

Antes (legado, `suitability_builder.py` L181-192) — `common_exclusions` tem
**3 entradas**, rio nunca excluído:
- `lakes_exclusion`: 0.5
- `protected_areas`: 0.99 (via `protected_areas_threshold`)
- `proximity_plants`: 0.01 (via `proximity_plants_threshold`)
`river_solar` / `river_wind` / `river_biomass` aparecem só no `priority_order` de
cada `TechnologyConfig` (critérios AHP/TOPSIS), nunca em `hard_exclusions`. O
setback ripário no legado, portanto, não exclui nada — entra no AHP como score
`{0,1}` degenerado, compensável por outros critérios.

Depois (GeoFREA) — `common_exclusions` tem **5 entradas**:
- as 3 do legado, mais
- `river_solar`: 0.5 (NOVO — hard exclusion)
- `river_wind`: 0.5 (NOVO — hard exclusion)

Mecanismo — reuso direto, NÃO máscara adicional: `river_safety_buffer_km = 0.5`
(fixo, todos os países; teto do Código Florestal, Lei 12.651/2012) já é aplicado
na Fase 2b por `compute_river_suitability` (ramo `else`), que emite `river_solar.tif`
e `river_wind.tif` como máscaras `{0.0, 1.0}` (`0.0` dentro de 0,5 km de rio,
`1.0` além). A Fase 3 reusa esses MESMOS dois rasters como entradas de
`common_exclusions` com threshold 0.5 — `apply_hard_exclusions` (`exclusion.py`
L120-124) faz `excl_mask = isfinite(crit_arr) & (crit_arr < 0.5)`, excluindo
exatamente os pixels `0.0`. Não haverá máscara de exclusão de rio separada:
seria contagem dupla do mesmo setback.

Consequência: `river_solar` e `river_wind` deixam de ser critérios AHP puros no
contrato GeoFREA — cada um ganha dois papéis simultâneos: (1) hard exclusion em
`common_exclusions` (novo) e (2) entrada em `priority_order` do `TechnologyConfig`
de solar/wind (herança do legado, mantida). Pixel dentro do buffer sai do domínio
elegível antes do AHP; pixel fora entra no AHP com score `1.0` nesse critério.

`river_biomass` permanece critério suave — nenhuma entrada em `common_exclusions`.
É score de acesso linear contínuo (`clip(1 − d/30, 0, 1)`), não setback:
proximidade de rio é preferência para biomassa (transporte fluvial de
matéria-prima), não risco. Fica só no `priority_order` de biomass, como no legado.

Referência (literatura/discussão, se aplicável): Lei 12.651/2012 (Código Florestal, faixas de APP ripária — 30 m para cursos d'água < 10 m de largura é o piso; `river_safety_buffer_km` usa 0,5 km como teto conservador cross-country, ver DECISIONS.md 2026-09-10 "suitability_criteria parameter calibration");
`geoworld_framework/src/processors/suitability_builder.py` L181-192 (`common_exclusions`), `src/utils/exclusion.py` L120-124 (`apply_hard_exclusions`);
`docs/architecture/suitability_criteria_audit.md` §3a (E3), §8d;
`docs/DECISIONS.md` 2026-09-10 ponto 7 (promoção) e "pacote 4 fecha os 14 critérios" (river_solar/river_wind produzidos pela Fase 2b);
`src/geofrea/suitability_criteria/criteria_functions.py::compute_river_suitability` (ramo `else`).

---
## [2026-09-11] - data_acquisition: solar (PVOUT) ganha resolver local
Tipo: STRUCTURAL_PRESERVE (fechamento de dependência — sem ambiguidade de método)

Descrição: `resolve_solar_path()` (`local_layers.py`) espelha `resolve_elevation_path()`
e aponta para o único arquivo global do Global Solar Atlas v2 em disco
(`<raw>/solar_potential/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif`),
registrado em `_LOCAL_PATH_HANDLERS`. `solar` ∈ `REQUIRED_ALIGNED_LAYERS` da
`suitability_criteria`; sem ele o pipeline 2a→2b não roda end-to-end
(`_check_required_layers` levanta `RuntimeError`). Diferente de
elevation/population/grid, solar NÃO é country-split — é um raster global,
recortado/reprojetado por país dentro de `grid_alignment`; o `country_code` do
resolver é aceito só para assinatura uniforme e ignorado. `provenance` segue
`local_only` e `fetch_status` segue `not_implemented` — resolver um path local
pré-colocado não é fetch (mesma distinção já registrada em 2026-09-08 para as
outras 5 camadas locais). `seismic`/`protected` deliberadamente não tocados.
Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-08 "wire das 5 camadas restantes a partir do banco local"; `src/geofrea/suitability_criteria/schemas.py::REQUIRED_ALIGNED_LAYERS`; instrução explícita de Douglas 2026-09-11 ("sem ambiguidade metodológica, pode seguir direto").

---

## [2026-09-11] - grid_alignment: derivação de slope do DEM (método e ordem)
Tipo: STRUCTURAL_PRESERVE

Descrição: `derive_slope_from_dem()` (`grid_alignment/raster_alignment.py`) porta
`geoworld_framework/src/processors/raster_processor.py::RasterProcessor.calculate_slope`
(L27-95), que o legado chamava em `main.py` L598-609 sobre o DEM bruto baixado,
ANTES de qualquer reprojeção. Antes desta sessão o GeoFREA não derivava slope em
lugar nenhum (`data_acquisition` o exclui de propósito; o adapter de
`grid_alignment` só mapeava `elevation`; o bloco `slope` de `align_layers` só
reprojetava um `slope_path` que nunca era preenchido) — então `grid_alignment`
sempre produzia `slope=None` e a `suitability_criteria` não rodava end-to-end
(`_check_required_layers`).

Método portado verbatim (STRUCTURAL_PRESERVE):
- gradiente de **diferença central** via `numpy.gradient`, NÃO o método de Horn de
  8 vizinhos do `gdaldem slope`;
- espaçamento de pixel corrigido por latitude: `dy = res_y · KM_PER_DEG_LAT · 1000`
  (constante, N-S); `dx = res_x · KM_PER_DEG_LAT · 1000 · cos(lat)` por linha (L-O).
  `KM_PER_DEG_LAT = 111.32` — média plana da Terra, adicionada a `core/constants.py`
  verbatim do legado (`src/core/constants.py`), deliberadamente NÃO
  `core.geodesy.wgs84_km_per_degree()` (o legado usou essa constante única e
  `cos(lat)` só no termo L-O; reproduzir os números exige o mesmo fator de escala);
- `slope_deg = degrees(arctan(hypot(dz/dx, dz/dy)))` — **graus**, não percentual
  nem radianos;
- processamento em blocos de 512 linhas com padding de ±1 linha para as costuras do
  gradiente, descartado antes de escrever.

Ordem (STRUCTURAL_PRESERVE): slope calculado no DEM em **resolução nativa**, e
DEPOIS reamostrado para a grade alvo (0.01°) com bilinear, exatamente como
`elevation`. NÃO calculado sobre o DEM já reamostrado. O legado escolheu essa
ordem; produz valores diferentes (mais suaves) da alternativa. `align_layers`
grava o intermediário nativo em `outputs/<ISO>/processed/<ISO>_slope_native.tif` e
o `_align_slope` interno o reprojeta para `<ISO>_slope_aligned.tif`.

Localização: dentro de `grid_alignment` (não em `data_acquisition`, cujo docstring
excluía slope; não em `main.py` como o legado). `GridAlignmentInputs.slope_path`
vira override opcional (normalmente `None` → deriva de `elevation_path`).
Docstrings de `data_acquisition/schemas.py`, `data_acquisition/phase.py` e
`data_quality_audit/schemas.py` atualizados para deixar explícito qual módulo é
responsável.

Justificativa: não se pôde confirmar do repositório se o `_slope_aligned.tif` do
`$GEOWORLD_BASELINE_DIR/data/processed/` foi gerado por este mesmo pipeline de
origem (o legado só deriva `if not slope_path exists`, e pode ter usado um
`{ISO}_slope.tif` pré-derivado). Por isso os testes checam paridade contra um
**cálculo de referência analítico independente** (plano inclinado tem slope de
forma fechada), não contra o arquivo congelado. O método/ordem em si não têm
fonte citada no legado (nem escolha de diferença central vs Horn, nem a ordem
native→resample) — mantidos como STRUCTURAL_PRESERVE por instrução explícita de
Douglas 2026-09-11.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/raster_processor.py` L27-95; `geoworld_framework/main.py` L598-609; `geoworld_framework/src/core/constants.py::KM_PER_DEG_LAT`; auditoria read-only reportada nesta sessão 2026-09-11.

---

## [2026-09-11] - grid_alignment: slope não herda contaminação de nodata (correção de integridade)
Tipo: correção de integridade de dado (mesma classe de solar_pvout_weight e biomass_resource land_cover==255 desta sessão)

Descrição: DESVIO DELIBERADO do legado em `derive_slope_from_dem()`. O legado
alimentava o sentinela nodata bruto (−9999) no `numpy.gradient` como se fosse
elevação real; um pixel VÁLIDO adjacente a um pixel nodata recebia gradiente
contaminado (vizinho −9999 → slope falso ~90°). O legado só remascarava a
CÉLULA-centro nodata **depois** (`slope_deg[elev == nodata] = nodata`), deixando a
contaminação de adjacência no resultado.

Correção: as células nodata do DEM são postas em `NaN` ANTES do gradiente
(`finite_in = isfinite & (!= nodata_val)` → `work = where(finite_in, elev, nan)`),
então o `NaN` propaga uma célula e todo pixel de slope cujo stencil de diferença
central tocou nodata sai não-finito. A saída é então mascarada em dois pontos:
(1) onde o gradiente saiu não-finito (a contaminação de adjacência que o legado
deixava); (2) nas próprias células nodata originais — o `numpy.gradient` nunca lê
a célula-centro, então uma célula nodata ainda ganharia um valor derivado dos
vizinhos e precisa ser remascarada, exatamente como o mask final do legado já
fazia. Resultado: um pixel válido adjacente a nodata vira nodata (não pôde ser
computado sem dado falso) em vez de um número errado.

Precedente nesta mesma sessão: `compute_solar_resource` guardando `NODATA_FLOAT`
sob `solar_pvout_weight` (2026-09-10) e `compute_biomass_resource` excluindo
`land_cover == 255` explicitamente (2026-09-10) — mesma natureza: fechar um
caminho onde um sentinela numérico vazava como dado real. Inerte quando o DEM não
tem nodata; muda resultado só na borda de buracos de dado do DEM (ex.: os 6 tiles
corrompidos de land_cover/BRA são de outra camada, mas DEMs Copernicus também têm
nodata em corpos d'água/borda de cobertura).

Teste dedicado: `test_derive_slope_valid_pixel_next_to_nodata_is_not_contaminated`
— falha contra uma reimplementação ingênua do legado (vizinhos da célula nodata ≈
90°), passa com a correção (vizinhos = nodata).
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/raster_processor.py` L82-83 (mask só pós-gradiente); `docs/DECISIONS.md` 2026-09-10 "compute_solar_resource guards NODATA_FLOAT" e "compute_biomass_resource exclui land_cover == 255"; instrução explícita de Douglas 2026-09-11.

---
## [2026-09-11] - suitability_criteria: protected_areas distingue WDPA ausente de WDPA corrompido
Tipo: METHODOLOGY_REVISION (fail-loud para falha de integridade; caminho assumed_free preservado para ausência genuína)

Descrição: `compute_protected_areas` tratava duas situações diferentes com o mesmo
fallback silencioso (`score[mainland] = 1.0`, `source = "assumed_free"`, só um
`logger.warning`) — herança do legado `criteria_builder.py` L511-513. A partir de
agora elas divergem:

- **WDPA genuinamente ausente** (diretório/arquivo não existe, ou diretório sem
  nenhum `.shp` — a camada é gated por um token manual do Protected Planet e falta
  de rotina): **situação operacional conhecida**. Continua `assumed_free` — todo o
  mainland = 1.0, `source = "assumed_free"`. Inalterado. A ausência de token nunca
  muda a ciência silenciosamente (já era a justificativa da decisão de 2026-09-10).
- **WDPA presente mas ilegível** (arquivo truncado, corrompido, sidecars `.shx`/
  `.dbf` faltando — qualquer falha em ler/recortar/rasterizar um arquivo que
  existe): **erro de integridade de dado**. Agora levanta `RuntimeError` com
  mensagem diagnóstica que nomeia o arquivo ofensor e o tipo da exceção original
  (encadeada via `raise ... from exc`), em vez de continuar como se o país não
  tivesse áreas protegidas.
- WDPA lido OK mas sem feição intersectando o mainland após o clip: continua
  `assumed_free` — é um "este país não tem WDPA mapeada" legítimo, não erro.

Veredito ratificado por Douglas (2026-09-11): um arquivo presente e corrompido não
deve receber o mesmo fallback silencioso da ausência de token. Consistente com a
filosofia fail-loud já aplicada em
`run_suitability_criteria_phase._check_required_layers` (RuntimeError se falta
elevation/slope/solar/land_cover) e `grid_alignment._verify_alignment` (RuntimeError
em mismatch de dimensão). Exceção escolhida: `RuntimeError` puro — o projeto não
tem exceção de domínio dedicada para falha de integridade de camada em runtime
(as classes `*RequiresBordersError(ValueError)` são para lacunas de wiring em tempo
de construção do adapter, não corrupção de dado). Propaga para
`PhaseExecutionError` via orquestrador, como os outros dois pontos fail-loud.

Testes: `test_compute_protected_areas_corrupted_shapefile_raises_not_assumed_free`
e `..._in_directory_also_raises` (shapefile truncado, confirmam mensagem clara);
`test_compute_protected_areas_empty_directory_is_assumed_free` (fixa a distinção —
diretório sem `.shp` continua `assumed_free`). O caso WDPA-ausente
(`test_compute_protected_areas_no_wdpa_is_all_free`) segue passando inalterado.
Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py` L511-513 (swallow do legado); `docs/architecture/suitability_criteria_audit.md` §5 item 10; `docs/DECISIONS.md` 2026-09-10 "pacote 4 fecha os 14 critérios" (fallback assumed_free para ausência de token); `src/geofrea/suitability_criteria/phase.py::_check_required_layers` e `src/geofrea/grid_alignment/alignment.py::_verify_alignment` (precedente fail-loud); instrução explícita de Douglas 2026-09-11.

---

## [2026-09-11] - grid_alignment: reproject_to_grid sanitiza NaN literal antes do warp
Tipo: correção de integridade de dado (mesma classe de solar_pvout_weight, biomass_resource land_cover==255, e a correção de contaminação de nodata do slope, todas desta sessão)

Descrição: achado real durante a integração ao vivo BRA→PRT desta sessão (Fase
2a→2b end-to-end, primeira vez com slope derivado de verdade em vez de
injetado). `terrain_score.tif`/`BRA` saiu com 14.263 pixels de NaN literal
(não o sentinela `-9999.0` que o próprio raster declara como nodata) — 7.700 a
mais que o baseline congelado (que já tinha 6.563 de um artefato próprio do
legado, ver entrada seguinte). Rastreado até a origem: `BRA_elevation_aligned.tif`
tem 17.582 pixels de NaN literal apesar de declarar `nodata=-9999.0`. Investigação
mais a fundo (raster bruto `BRA_elevation.tif`, antes de qualquer reprojeção):
0 pixels são exatamente `-9999.0`, mas **18.427.230 de 70.638.442 pixels (26%)
são NaN literal** — o arquivo bruto declara um sentinela numérico finito em
sua própria metadata mas na prática nunca o usa, só NaN. `PRT_elevation.tif`,
por comparação, declara `nodata=NaN` (não um sentinela finito) e o GDAL já
trata esse caso corretamente hoje (0 NaN vazado no `PRT_elevation_aligned.tif`).

`reproject_to_grid()` (compartilhada por toda camada float que passa por
`grid_alignment`) chamava `rasterio.warp.reproject(..., src_nodata=src.nodata)`
confiando na metadata declarada. Quando essa metadata está errada (finito
declarado, NaN na prática), o GDAL não reconhece as células NaN como nodata,
trata-as como elevação real, e o resample bilinear as mistura nos pixels de
destino vizinhos como NaN de verdade — não `nodata_out`.

Correção: antes do `reproject()`, quando `dtype_out` é float E o nodata
declarado da fonte é finito (não é ele próprio NaN), a banda é lida para
memória e qualquer NaN literal é substituído pelo sentinela declarado
(`np.where(np.isnan(src_array), src_nodata, src_array)`), com um
`logger.warning` contando os pixels afetados. Essa versão saneada (não mais
`rasterio.band(src, 1)`) é o `source=` passado ao `reproject()`. Inerte
quando a fonte não tem esse descompasso; não toca fontes cujo próprio
`nodata` declarado já é NaN (caso do PRT, que o GDAL já trata certo hoje).
Resolvido na origem (função compartilhada de reprojeção), não em cada
consumidor — mesma filosofia da correção de nodata do slope abaixo.

Testes: `test_reproject_to_grid_sanitizes_literal_nan_despite_finite_declared_nodata`
(reproduz o caso real do BRA — NaN literal com nodata finito declarado —
confirma zero NaN na saída); `test_reproject_to_grid_leaves_nan_declared_nodata_sources_untouched`
(fixa que o caminho do PRT, nodata=NaN nativo, continua sem alteração).

Referência (literatura/discussão, se aplicável): investigação ao vivo desta sessão (integração BRA→PRT, docs/DECISIONS.md — ver relatório de sessão); `docs/DECISIONS.md` 2026-09-11 "grid_alignment: slope não herda contaminação de nodata" (mesma classe de correção); instrução explícita de Douglas 2026-09-11 ("resolva na origem em vez de só tratar o sintoma no consumidor").

---

## [2026-09-11] - suitability_criteria: TRI (terrain_score) não herda contaminação de NaN/nodata
Tipo: METHODOLOGY_REVISION (mesma classe da correção de nodata do slope, 2026-09-11)

Descrição: `compute_terrain_score` tinha DOIS problemas relacionados no cálculo
do TRI (Terrain Ruggedness Index), ambos herdados do legado
(`criteria_builder.py` L167-220, confirmado por leitura direta): (1) a
diferença de 8 vizinhos era calculada sobre o array de elevação BRUTO — com o
sentinela de nodata embutido como se fosse elevação real — então um pixel
VÁLIDO adjacente a um nodata (ex.: borda do país, borda do raster alinhado)
recebia um TRI contaminado por uma diferença de ~10.000m falsa; (2) o
resultado desse cálculo era filtrado só por `!= NODATA_FLOAT`, que NUNCA
barra NaN (IEEE 754: `NaN != x` é sempre `True`), então qualquer NaN literal
residual na elevação de entrada (ver entrada anterior — `reproject_to_grid`)
vazava direto para `terrain_score.tif` como NaN de verdade, não o sentinela
`-9999.0` que o raster declara.

Correção, espelhando exatamente o padrão já decidido para
`derive_slope_from_dem()` (2026-09-11): células de elevação inválidas
(nodata OU NaN literal — `valid_finite_mask` já cobre os dois) são postas em
NaN ANTES do cálculo de diferença de vizinhos (`work = where(valid_e, elev,
nan)`), então o NaN se propaga para qualquer pixel cujo stencil 3x3 tocou uma
célula inválida; o sub-score de TRI desse pixel é então explicitamente
re-mascarado para `NODATA_FLOAT` via `np.isfinite(tri)` — nunca deixado como
NaN silencioso. A combinação final (`both`/`only_s`) também ganhou
`np.isfinite(...)` ao lado de cada `!=`, defesa em profundidade, ainda que
estruturalmente o NaN não deva mais escapar do bloco do TRI.

Decisão (pedida explicitamente: "decida e documente"): um pixel CENTRAL
válido com 1+ vizinho inválido recebe TRI = `NODATA_FLOAT` (cai para
slope-only), e não um TRI calculado ignorando só o(s) vizinho(s) inválido(s).
Justificativa: mesmo princípio já adotado para o slope — "não pôde ser
computado sem dado falso" é preferível a um número parcial/enviesado
(computar TRI com 7 de 8 vizinhos reais e um "buraco" mudaria a escala
implícita da métrica sem aviso). Grep de todo `suitability_criteria` por
outros usos de `!= NODATA_FLOAT`/`!= nodata` sem `isfinite()` acompanhando
(pedido explícito) não achou outra ocorrência real: `compute_solar_resource`
(L80) já guarda com `np.isfinite(score) &` (correção 2026-09-10);
`compute_lc_biomass`/`compute_biomass_resource` operam sobre `lc_data`
inteiro (`int16` — não pode conter NaN); `compute_seismic_suitability`
(L428) usa `normalized`, que só pode conter valores já filtrados por
`valid_finite_mask` a montante — sem risco.

Efeito colateral esperado, confirmado ao vivo contra os dois baselines
congelados: o baseline do PRT tem 0 NaN em `terrain_score.tif`, mas o do BRA
tem 6.563 — um artefato do PRÓPRIO legado (mesma classe de bug, nunca
corrigido lá). A correção aqui fecha esse artefato herdado também, não só o
NaN novo introduzido pelo `reproject_to_grid` desta sessão — então o teste de
regressão de paridade bit-exata (`tests/regression/test_suitability_criteria_regression.py`)
precisou de ajuste: `terrain_score` saiu da tabela cega de paridade e ganhou
teste dedicado (`test_terrain_score_matches_frozen_baseline_away_from_nodata_boundary`),
que exige bit-exato só FORA de uma faixa de 1 célula ao redor de qualquer
elevação inválida (dilatação 3x3) — dentro dessa faixa a divergência é
esperada e documentada aqui, não um defeito de port. Confirmado ao vivo: PRT
e BRA batem bit-exato em 100% dos pixels fora dessa faixa (90.326 e 7.042.911
pixels comparados, respectivamente, max|delta|=0.0 nos dois).

Verificação extra pedida explicitamente por Douglas antes do commit (a faixa
de exclusão não pode ter sido alargada até o teste passar — precisa ser
justificada só pelo raio geométrico do próprio stencil de 8 vizinhos, 1
célula): confirmado que os 6.563 NaN do baseline congelado do BRA caem
**100% dentro** da faixa de dilatação de 1 célula (0 caem fora); mais que
isso, nenhum dos 6.563 é, ele mesmo, uma célula de elevação inválida (contagem
sem dilatação = 0) — são exatamente o caso "pixel central válido com vizinho
inválido", a classe exata que um stencil de raio 1 produz, não uma
coincidência de uma faixa maior. A faixa dilatada (53,96% do raster) cresce
só ~0,26 ponto percentual sobre o conjunto bruto de elevação inválida
(53,70%) — o perímetro de uma única célula ao redor de uma região já grande e
contígua, não um raio inflado.

Testes: `test_compute_terrain_score_nan_neighbour_falls_back_to_slope_only_not_nan`
(fixture com NaN residual isolado em elevação — confirma que o pixel central
válido mas com vizinho NaN cai para slope-only, não NaN, e que um pixel longe
da contaminação permanece com a combinação completa slope+TRI).

Referência (literatura/discussão, se aplicável): `geoworld_framework/src/processors/criteria_builder.py` L167-220 (bug original do legado, confirmado por leitura direta); `docs/DECISIONS.md` 2026-09-11 "grid_alignment: slope não herda contaminação de nodata" (mesmo padrão) e "grid_alignment: reproject_to_grid sanitiza NaN literal antes do warp" (causa raiz do NaN novo no BRA); instrução explícita de Douglas 2026-09-11.

---

## [2026-09-11] - grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país
Tipo: METHODOLOGY_REVISION (fail-loud para falha de integridade; mesmo precedente do WDPA)

Descrição: achado real durante a integração ao vivo desta sessão. `mosaic_land_cover()`
pula um tile ESA WorldCover corrompido (`except Exception: skipped += 1;
continue`) sem abortar o mosaico — comportamento correto em si (um tile ruim
não deve derrubar o país inteiro), mas o array de saída é inicializado com
`np.zeros(...)` e só recebe `NODATA_UINT8` (255) fora do polígono do país
(`lc_out[~grid.country_mask] = NODATA_UINT8`, aplicado DEPOIS do loop). Um
tile pulado cuja área caía DENTRO do país deixaria essa área em `0` — não um
código ESA válido, mas também não o nodata declarado do raster — então um
consumidor a jusante que faça o check padrão `!= nodata` trataria como dado
real. Verificado ao vivo para o caso de hoje (BRA, os 6 tiles corrompidos
conhecidos, ver `docs/DECISIONS.md` 2026-09-08 Fase 2 ACHADO REAL 3): nenhum
dos 6 sobrepõe o mainland do Brasil no raster alinhado (todos na faixa
36°S-33°S, majoritariamente fora do BRA) — 0 pixels de classe 0 remanescentes
dentro da máscara do país nesta execução. Sorte geográfica, não uma
propriedade do código.

Correção (instrução explícita: "não usar burn de 255 como solução principal
— é indistinguível de 'sem cobertura real' a jusante"): em vez de mudar a
semântica do valor de preenchimento, o loop agora decide, por tile pulado,
se o gap importa. Quando o tile abre normalmente mas não sobrepõe o país, o
comportamento é inalterado (pulado sem erro). Quando o tile FALHA ao
abrir/ler/reprojetar, o footprint real é desconhecido (nunca chegou a
`src.bounds`) — o fallback é o footprint NOMINAL do tile, decifrado do nome
do arquivo (convenção ESA WorldCover: `[N|S]xx[E|W]yyy` = canto SW, grade
fixa de 3x3 graus — `_esa_worldcover_tile_bounds()`, nova função). Se esse
footprint (real ou nominal) sobrepõe o país sendo processado: `RuntimeError`,
citando o arquivo e a exceção original — mesma filosofia fail-loud de
`_check_required_layers`/`_verify_alignment`/WDPA. Se não sobrepõe, OU o nome
do arquivo não bate com o padrão esperado (footprint genuinamente
desconhecido — não assumido seguro): `logger.warning` nomeando o tile e o
motivo, para rastreabilidade, sem abortar.

Testes: `test_mosaic_land_cover_raises_when_corrupted_tile_overlaps_country`
(tile corrompido com nome de tile ESA que sobrepõe o país do teste — confirma
`RuntimeError`); `test_mosaic_land_cover_skips_corrupted_tile_outside_country_with_warning`
(mesmo tile corrompido, nome de tile fora do país — confirma que NÃO levanta,
e que o warning nomeia o arquivo e o motivo no log). Os testes pré-existentes
(`..._skips_corrupted_tile_without_crashing`, nome de arquivo que não bate
com o padrão ESA) seguem passando inalterados — footprint desconhecido cai no
mesmo warn-and-skip de antes.

Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-08 "wire das 5 camadas restantes a partir do banco local, Fase 2" (ACHADO REAL 3, os 6 tiles corrompidos do BRA); `docs/DECISIONS.md` 2026-09-11 "protected_areas distingue WDPA ausente de WDPA corrompido" (precedente fail-loud citado explicitamente por Douglas); instrução explícita de Douglas 2026-09-11.

---

## [2026-09-11] - data_acquisition: AcquiredLayer.fetch_status quebrava resume a partir de manifest.json (correção de bug)
Tipo: correção de bug — NÃO é mudança metodológica. Nenhum comportamento de fetch/provenance/fetch_status é alterado; apenas a serialização/deserialização volta a funcionar.

Descrição: `AcquiredLayer.fetch_status` (`schemas.py`) é um `@computed_field` — derivado só de `layer_name`, não um campo de construtor (ver docstring do campo, "fetch_status computed field", 2026-08-26). Sendo computed, ele também é emitido por `model_dump(mode="json")`, que é exatamente o que `Orchestrator._write_manifest()` (`core/orchestrator.py`) chama para gravar `outputs/<country_code>/manifest.json` após cada fase bem-sucedida. Ao retomar uma execução (`Orchestrator.run()`, ramo `existing.status == "success"`), o dicionário lido do manifest é passado de volta para `AcquisitionResult.model_validate(existing.output)`, que por sua vez valida cada `AcquiredLayer` do zero — e `AcquiredLayer` tem `model_config = ConfigDict(extra="forbid")`. Um computed field é somente-leitura: não pode ser aceito como argumento de construtor, então `fetch_status` no dicionário caía na regra de `extra="forbid"` e o Pydantic levantava `extra_forbidden` em toda camada, para todo resume que passasse pela fase `data_acquisition`. Na prática, resumir uma execução após essa fase forçava re-rodar do zero, quebrando o propósito inteiro de `manifest.json` (evitar re-rodar um pipeline de ~1h por país após falha tardia — ver docstring do módulo `orchestrator.py`).

Reproduzido diretamente antes da correção:
```
AcquiredLayer(layer_name="power_plants", provenance="fetched", auth_required=False).model_dump(mode="json")
# -> inclui {"fetch_status": "implemented", ...}
AcquiredLayer.model_validate(<esse dict>)
# -> pydantic.ValidationError: fetch_status — Extra inputs are not permitted [extra_forbidden]
```

Correção: `AcquiredLayer` ganhou um `@model_validator(mode="before")` (`_drop_computed_fetch_status`) que remove a chave `fetch_status` do dicionário de entrada antes da validação, se presente. Como `fetch_status` é puramente derivado de `layer_name`, descartar o valor gravado e deixar o `@computed_field` recalculá-lo na reconstrução não perde informação — o valor recalculado é idêntico ao que foi gravado (mesmo `layer_name`, mesma lógica). Deliberadamente NÃO foi usado `model_config = ConfigDict(extra="ignore")` no lugar do validator: isso abriria mão da proteção `extra="forbid"` para qualquer chave desconhecida (ex.: um campo com nome digitado errado, ou um manifest genuinamente corrompido), não só para `fetch_status` — o validator descarta apenas essa chave nomeada, mantendo `extra="forbid"` como guarda contra qualquer outra entrada inesperada.

Testes (`tests/unit/test_data_acquisition_phase.py`):
- `test_acquired_layer_round_trips_through_dumped_fetch_status` — save → load isolado: `model_dump(mode="json")` seguido de `model_validate()` no mesmo dict não levanta mais, e o objeto recarregado é igual ao original.
- `test_acquired_layer_still_rejects_unrelated_extra_fields` — confirma que a correção é específica a `fetch_status`: uma chave extra não relacionada ainda levanta `ValidationError`, então corrupção real de manifest continua sendo pega.
- `test_orchestrator_resumes_data_acquisition_phase_from_saved_manifest` — reprodução end-to-end do bug pelo caminho real: roda a fase `data_acquisition` via `Orchestrator` (grava `manifest.json` de verdade, com `fetch_status` incluído em cada layer), constrói um segundo `Orchestrator` apontando para o mesmo `outputs_dir` (simulando uma nova invocação do processo) e confirma que a fase é resumida com sucesso a partir do manifest salvo, sem re-executar, produzindo o mesmo `AcquisitionResult`.

Nota: rodar a suíte completa de `tests/unit/test_data_acquisition_phase.py` nesta sessão expõe 25 falhas pré-existentes e não relacionadas — o fetcher `protected` (`fetchers/protected_planet.py`), ativado em trabalho em andamento não commitado desta mesma data (ver `phase.py`/`schemas.py` modificados fora desta entrada), ainda não está mockado na fixture `_no_network_fetchers` deste arquivo de teste, então qualquer teste que chame `run_acquisition_phase()` sem token real falha com `ProtectedPlanetTokenMissingError`. Os 3 testes novos acima evitam isso mockando `fetch_protected_areas` localmente (não a fixture compartilhada) e passam isoladamente; a fixture compartilhada não foi tocada por estar fora do escopo desta correção.

Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-08-26 "fetch_status computed field" (origem do campo computed); instrução explícita de Douglas 2026-09-11 pedindo correção de bug (não mudança metodológica) e teste save → load → resume.

---

## [2026-09-11] - slope não herda contaminação de nodata: correção de escopo (PRT vs BRA)
Tipo: VERIFICATION_UPDATE (addendum à entrada "grid_alignment: slope não herda contaminação de nodata (correção de integridade)", mesmo dia — não altera a correção em si, corrige a descrição do seu alcance)

Descrição: a entrada original descreve o efeito da correção como algo que "muda
resultado só na borda de buracos de dado do DEM". Investigação pedida por
Douglas nesta sessão (comparação `slope_degrees` pós-fix vs. baseline congelado
do legado, para PRT e BRA, mais recomputação independente a partir do DEM bruto
pelos dois caminhos — "legado" alimentando o sentinela cru no gradiente vs.
"corrigido" com NaN antes do gradiente) mostra que essa frase é precisa para
BRA mas **enganosa para PRT**:

- **BRA**: 7.074.855 pixels válidos nos dois lados (baseline e novo) — **0
  divergem** (delta = 0,0 em 100% dos pixels comparados); o novo output tem
  17.606 pixels válidos A MAIS que o baseline (recuperados pela correção, não
  alterados). Recomputação independente a partir de `BRA_elevation.tif`
  confirma: caminho "legado" e "corrigido" coincidem bit-a-bit nos pixels
  compartilhados. Efeito real: recuperação pontual de borda, exatamente como a
  entrada original descreve.
- **PRT**: 93.147 pixels válidos nos dois lados — **100% divergem** (mediana
  |delta| 0,16°, p99 2,15°, max 4,51°). Mas a recomputação independente a
  partir de `PRT_elevation.tif` mostra que os caminhos "legado" e "corrigido"
  produzem resultado BIT-IDÊNTICO em 100% dos 622.393 pixels válidos nativos —
  **esta correção é um no-op para PRT**. Motivo: `PRT_elevation.tif` já
  declara `nodata=NaN` nativamente (não um sentinela finito como o −9999 do
  BRA); o bug do legado (sentinela finito vazando como elevação real dentro do
  `numpy.gradient`) nunca tinha como se manifestar aqui — `NaN` já propaga no
  gradiente com ou sem o pré-mascaramento explícito que esta correção
  acrescenta.

A divergência de 100% dos pixels de PRT contra o baseline **não vem desta
correção**. Uma reimplementação independente do método documentado (diferença
central + `cos(lat)`, nativo→resample), aplicada do zero sobre o DEM bruto de
PRT, reproduz a MESMA divergência contra o baseline (mediana 0,16°, max
4,51°) — ou seja, o método/ordem tal como documentado já diverge do baseline
legado por conta própria, independentemente de qualquer correção de nodata.
Essa é a incerteza de proveniência do baseline já registrada e ratificada em
`docs/DECISIONS.md` 2026-09-11 "grid_alignment: derivação de slope do DEM
(método e ordem)" (STRUCTURAL_PRESERVE) — **não reaberta aqui**, apenas
confirmada como a causa real do que se observa em PRT.

**Resolução nativa do DEM não explica a assimetria PRT vs. BRA**: ambos os
DEMs brutos (`database/raw/elevation/PRT/PRT_elevation.tif`,
`.../Brazil/BRA_elevation.tif`) têm a mesma resolução nativa — 0,005°/pixel,
EPSG:4326 — confirmado por leitura direta. Fração de pixels válidos nativos
adjacentes (8-conectividade) a alguma célula nodata é da mesma ordem de
grandeza nos dois países (PRT 0,15% = 912/623.302; BRA 0,18% =
92.546/52.211.212). A assimetria real não é espacial — é o TIPO de sentinela
de nodata declarado por país: PRT declara `NaN` nativamente (sem bug
possível), BRA declara `-9999.0` mas a maior parte do dado inválido já está
armazenado como `NaN` literal na prática (~26% das células — mesmo achado já
documentado em `docs/DECISIONS.md` 2026-09-11 "grid_alignment:
reproject_to_grid sanitiza NaN literal antes do warp", ali para
`elevation_aligned`, aqui confirmado também no DEM bruto usado pelo slope
nativo).

**Plausibilidade geomorfológica de `slope_degrees` pós-fix em PRT** (pedida
por Douglas, referência independente grosseira — não confundir com os deltas
acima, que são a diferença baseline-vs-novo, não a distribuição de slope em
si): a distribuição real na grade alinhada (0,01°, ~1 km) tem mediana 2,00°,
p99 12,47°, max 21,17°. Compatível com o relevo conhecido de Portugal
continental nessa resolução agregada — litoral e Alentejo predominantemente
planos a suavemente ondulados (consistente com a mediana baixa e a grande
massa de pixels de baixo slope), com extremos de até ~21° plausíveis para as
serras do interior/norte (Serra da Estrela, Gerês) mesmo suavizados por um
pixel de ~1 km. Nada nessa distribuição, isoladamente, indica artefato.

Nenhuma decisão de método/ordem é reaberta por esta entrada. Ela corrige
apenas o escopo do efeito descrito na entrada de nodata (que segue válida e
inalterada para BRA) e aponta a causa real da divergência de PRT para uma
entrada já existente e já ratificada, sem alterá-la.

Ação de correção: onde a frase "muda resultado só na borda de buracos de dado
do DEM" (entrada 2026-09-11 "grid_alignment: slope não herda contaminação de
nodata") for lida, entender como válida apenas para DEMs com nodata declarado
como sentinela finito e efetivamente presente como tal no dado bruto (caso
BRA) — não generalizável a PRT, onde a correção é comprovadamente inerte, e
onde a divergência observada contra o baseline tem outra causa, já
documentada.

Referência (literatura/discussão, se aplicável): recomputação independente
desta sessão a partir de `database/raw/elevation/PRT/PRT_elevation.tif` e
`.../Brazil/BRA_elevation.tif`; `outputs_baseline/PRT_baseline` (legado) vs.
`outputs/PRT/suitability_criteria/tif/slope_degrees.tif` e
`outputs/BRA/suitability_criteria/tif/slope_degrees.tif`; `docs/DECISIONS.md`
2026-09-11 "grid_alignment: derivação de slope do DEM (método e ordem)"
(STRUCTURAL_PRESERVE) e "grid_alignment: reproject_to_grid sanitiza NaN
literal antes do warp"; instrução explícita de Douglas 2026-09-11.

---

## [2026-09-11] - data_acquisition: protected_planet API activation
Tipo: STRUCTURAL_PRESERVE — ativa um fetcher já implementado e testado (`fetchers/protected_planet.py`), sem mudar sua lógica interna. Não é mudança metodológica: o comportamento de `compute_protected_areas` (fail-loud em WDPA corrompido vs. `assumed_free` em WDPA genuinamente ausente, decisão 2026-09-11 "protected_areas distingue WDPA ausente de WDPA corrompido") não é tocado.

Descrição: `protected` (WDPA) tinha, desde 2026-08-25, um fetcher completo e testado (`fetchers/protected_planet.py::fetch_protected_areas`) que não estava ligado a `run_acquisition_phase()` — a única coisa bloqueando era um token de API pessoal (`api.protectedplanet.net`, obtido via formulário manual, sem self-service). Douglas confirmou hoje que já colocou um token real em `.env` (`PROTECTED_PLANET_API_KEY`). Duas mudanças:

1. **Nome da variável de ambiente**: o fetcher lia `PROTECTED_PLANET_API_TOKEN`, mas o `.env` real usa `PROTECTED_PLANET_API_KEY` — renomeado `TOKEN_ENV_VAR` no fetcher para casar com o que já está no `.env`, em vez de pedir um segundo valor duplicado sob outro nome. Não há carregamento de `.env` no código do pipeline (nenhum `python-dotenv` em `src/`) — a variável precisa estar no ambiente do processo que roda o pipeline, mesmo mecanismo já usado para `GEOFREA_RAW_DATA_DIR`/`GEOFREA_PROCESSED_DATA_DIR`/etc.
2. **Wiring**: `protected` adicionado a `_FETCHED_LAYER_HANDLERS` (`phase.py`) e movido de `IMPLEMENTED_NOT_ACTIVATED_LAYER_NAMES` para `IMPLEMENTED_FETCH_LAYER_NAMES` (`schemas.py`) — `fetch_status` passa a reportar `"implemented"` em vez de `"implemented_not_activated"`. `_LayerSpec("protected", ...)` mudou `provenance` de `"local_only"` para `"fetched"` e `auth_required` de `False` para `True` (primeiro caso de `auth_required=True` desde que `land_cover`/Terrascope reverteu para local, 2026-09-08). `country_specific` permanece `False` — decisão deliberadamente NÃO revisitada aqui (fora do pedido de hoje): embora o fetcher consulte a API por país, o registro trata `protected` no mesmo padrão de `lakes`/`rivers` (fonte global/contínua, país é metadado do `AcquiredLayer`, não do arquivo em si) desde a auditoria de 2026-08-24 ("vector layer audit depth") — mudar isso seria uma decisão de escopo separada.

`fetch_protected_areas` é o único fetcher, além de `hydrosheds.fetch_rivers` (país fora de `_COUNTRY_TO_REGION`), que pode *levantar* em vez de degradar para `path=None`: `ProtectedPlanetTokenMissingError` quando nenhum token está configurado — deliberado (token ausente é lacuna de configuração, não falha transitória de rede), não capturado em `run_acquisition_phase()`, propaga via `PhaseExecutionError` do Orchestrator, mesma filosofia fail-loud já estabelecida.

Testes (`tests/unit/test_data_acquisition_phase.py`): `_FETCHER_NAMES` ganhou `fetch_protected_areas` (a fixture `_no_network_fetchers` agora cobre os 7 fetchers reais); `test_run_acquisition_phase_only_protected_requires_auth_2026_09_11` (substitui o teste "nenhuma camada exige auth", agora `protected` é a única); `test_run_acquisition_phase_provenance_split_2026_09_11` e `test_run_acquisition_phase_fetch_status_split_2026_09_11` (ambos atualizados: `protected` migra de `local_only`/`implemented_not_activated` para `fetched`/`implemented`); `test_run_acquisition_phase_populates_path_when_fetcher_succeeds` ganhou o caso `protected`; `test_run_acquisition_phase_protected_token_missing_propagates` (novo — mirror de `..._rivers_unmapped_country_propagates_keyerror`, confirma que `ProtectedPlanetTokenMissingError` não é engolido pela fase). `tests/unit/test_fetchers_protected_planet.py` não precisou de mudança de conteúdo — todo teste referencia `protected_planet.TOKEN_ENV_VAR` simbolicamente, não a string literal.

Referência (literatura/discussão, se aplicável): `fetchers/protected_planet.py` (docstring do módulo, verificação ao vivo da API 2026-08-24/25); `docs/DECISIONS.md` 2026-08-25 "real fetchers for power_plants/wind/lakes/rivers" (mesmo padrão de ativação); instrução explícita de Douglas 2026-09-11 ("Configure o token... via variável de ambiente... resolva o path local/fetch de protected").

**Addendum (mesmo dia, mesma entrada — 2 bugs reais achados ao rodar contra a API autenticada de verdade)**: o schema de resposta nunca tinha sido verificado ao vivo (docstring do módulo já sinalizava isso explicitamente). Rodando `data_acquisition` + `grid_alignment` para BRA (4190 features) e PRT (442 features) com o token real, dois campos estavam errados: (1) `iucn_category` chega como objeto aninhado `{"id": 1, "name": "Ia"}`, não string — o código original gravava o dict inteiro em `IUCN_CAT`, o que faria `compute_protected_areas`'s `cats.isin(strict)` nunca casar nenhuma categoria IUCN real (toda área WDPA teria sido tratada como não-estrita, silenciosamente); (2) a v4 não tem campo `wdpa_id` — o campo real é `site_id`. Ambos corrigidos em `fetch_protected_areas` (extração de `.get("name")` do objeto aninhado, `site_id` em vez de `wdpa_id`), reconfirmado nos dois arquivos brutos re-baixados. Testes novos: `test_fetch_protected_areas_extracts_name_from_nested_iucn_category`, `test_fetch_protected_areas_handles_missing_iucn_category`.

---

## [2026-09-11] - protected_areas: repara geometria WDPA inválida antes do clip (correção separada do fail-loud original)
Tipo: correção de bug/robustez — distinta da decisão de fail-loud original (2026-09-11 "protected_areas distingue WDPA ausente de WDPA corrompido"). Não reabre nem enfraquece aquela decisão: o fail-loud continua valendo para qualquer geometria que ainda quebre o clip depois do reparo — só deixa de disparar para o caso específico de auto-interseção, que é uma característica conhecida do dataset WDPA real, não evidência de arquivo truncado/corrompido.

Descrição: ao rodar `protected_areas` de verdade pela primeira vez (ver entrada acima, "protected_planet API activation") contra os arquivos WDPA reais de BRA e PRT, `compute_protected_areas` levantava o `RuntimeError` fail-loud em 100% das execuções — não por arquivo corrompido, mas porque **9,1% dos polígonos WDPA do BRA (383/4190) e 13,8% do PRT (61/442) são topologicamente inválidos** (auto-interseção). `clip_vector_to_country()`'s `.intersection()` (`geo_utils.py`) levanta `GEOSException: TopologyException: side location conflict` nesse caso, capturada e re-lançada como o `RuntimeError` de integridade de dado. Auto-interseção é uma característica bem documentada do dataset WDPA global de verdade (submissões nacionais heterogêneas), não um sinal de download truncado — distinta da categoria de falha que o fail-loud original foi desenhado para pegar (ver `WdpaGeometryRepairReport`, novo, no docstring de `criteria_functions.py`).

Instrução explícita de Douglas: reparar via `make_valid()` (não `buffer(0)`, geometricamente mais correto para casos degenerados) as features WDPA antes do clip; manter fail-loud para qualquer exceção que sobreviva ao reparo; registrar quantidade reparada e delta de área agregada como parte do resultado estruturado de `protected_areas` (não só em log), mesmo padrão de rastreabilidade do fix de `mosaic_land_cover` (2026-09-11).

Implementação (`criteria_functions.py::compute_protected_areas`): a leitura do arquivo WDPA foi desacoplada do clip — antes chamava `read_clipped_to_country()` (ler+clipar em uma função só, sem ponto de interceptação); agora lê via `gpd.read_file()` puro, detecta `~geometry.is_valid`, repara só o subconjunto inválido via `shapely.make_valid(..., method="structure")`, e só então chama `clip_vector_to_country()` diretamente. `clip_vector_to_country()` em si **não foi tocado** — o reparo é local a `compute_protected_areas`, não afeta nenhum outro consumidor (roads/lakes/rivers/land_cover clip continuam exatamente como antes).

**`method="structure"`, não o default `"linework"`** (achado ao vivo, não assumido): `make_valid()` com o método default falha em 27 dos 383 polígonos inválidos do BRA com `GEOSException: IllegalArgumentException: Overlay input is mixed-dimension` (geometrias degeneradas onde o algoritmo de linework produz uma `GeometryCollection` de dimensão mista). `method="structure"` (requer GEOS >= 3.10 — confirmado GEOS 3.13.1/shapely 2.1.2 neste ambiente) raciocina a partir da estrutura de anéis (shell/hole) em vez de nodar todas as arestas, e reparou 100% dos casos em ambos os países (383/383 BRA, 61/61 PRT) sem erro.

Rastreabilidade estruturada: `ProtectedResult` ganhou um 5º elemento, `WdpaGeometryRepairReport` (NamedTuple: `total_features`, `invalid_repaired`, `area_before_km2`, `area_after_km2` — área agregada só do subconjunto reparado, em EPSG:6933/World Cylindrical Equal Area já que WDPA é global, sem zona UTM única aplicável). `SuitabilityCriteriaSummary` ganhou 4 campos novos (`protected_wdpa_features_total`, `protected_wdpa_invalid_repaired`, `protected_wdpa_repair_area_before_km2`, `protected_wdpa_repair_area_after_km2`, todos com default 0/0.0 para não quebrar construtores existentes) — visível no resultado estruturado da fase, não só em `logger.warning`. `phase.py` propaga o relatório do `compute_protected_areas` para o summary e loga a contagem junto do source.

Resultado real (BRA/PRT, execução ao vivo desta sessão): BRA — 383/4190 reparados, área 666.830,016 km² → 666.819,301 km² (delta ≈ -10,7 km², ~0,0016% do total — dentro do ruído esperado de reparo topológico); PRT — 61/442 reparados, área 5.004,998 km² → 5.005,017 km² (delta ≈ +0,019 km²). Ambos os países agora produzem `source="wdpa"` (não mais `RuntimeError`, não mais `assumed_free`): BRA 547.693 pixels excluídos (IUCN estrito) / 6.552.444 livres; PRT 747 excluídos / 92.402 livres.

**Addendum (mesmo dia — por que `method="structure"` é o padrão geral e não só um fallback para os casos em que `"linework"` quebra)**: verificação ao vivo direta contra os arquivos WDPA reais já baixados (`outputs/{BRA,PRT}/raw/*_protected_areas_wdpa.geojson`) — não assumida — mostra que os dois métodos **divergem substancialmente** mesmo nos polígonos em que `"linework"` não levanta exceção nenhuma: chamando `make_valid()` geometria a geometria (não em lote), `"linework"` reparou 373/383 dos inválidos do BRA sem erro (10 levantam `GEOSException`, não 27 — a chamada em lote original levanta na primeira geometria ruim do array e aborta o lote inteiro, o que mascarava a contagem real de falhas individuais; PRT: 57/61 sem erro, 4 levantam). Comparando o resultado de `"structure"` com o de `"linework"` nesse subconjunto onde os dois teoricamente "funcionam": **141 dos 373 polígonos do BRA (38%) produzem geometrias reparadas diferentes**, com diferença de área de até 26,6 km² num único polígono; PRT: 12/57 (21%) divergem, até 0,006 km². Ou seja, `"structure"` não é uma escolha neutra restrita aos ~10 casos que quebram `"linework"` — ela muda o resultado para mais de um terço dos polígonos que `"linework"` também conseguiria reparar.

Por isso `"structure"` é adotado aqui como **padrão geral deliberado, não fallback de exceção**: ele reconstrói a geometria a partir da estrutura de anéis (shell/hole) em vez de re-nodar todas as arestas e resolver por overlay, o que é mais robusto exatamente para o tipo de auto-interseção degenerada que submissões nacionais heterogêneas ao WDPA produzem (anéis que se cruzam de forma "estrutural", não simples ruído de digitalização). Rejeitar `"linework"` como método primário e usar `"structure"` uniformemente para todas as 383+61 features inválidas evita a inconsistência de um resultado cujo método de reparo dependeria, geometria a geometria, de qual dos dois GEOS algoritmos não lançou exceção naquele caso específico — o que produziria um resultado difícil de justificar e de reproduzir. A divergência de 38% confirma que a escolha do método é uma decisão metodológica real (não estética), documentada aqui em vez de implícita no código.

Testes (`tests/unit/test_suitability_criteria_functions.py`): `test_compute_protected_areas_repairs_self_intersecting_geometry` (fixture bowtie sintética, `is_valid=False` confirmado antes de escrever; `source="wdpa"`, não levanta; nota: `area_before_km2` é 0.0 para um bowtie perfeito — área com sinal cancela sob a fórmula shoelace de um anel inválido, resultado correto, não bug do teste); `test_compute_protected_areas_no_wdpa_repair_report_is_empty` (sem arquivo -> relatório zerado); `test_compute_protected_areas_valid_geometry_repair_report_is_zero` (geometria já válida -> `invalid_repaired=0`). Os 2 testes fail-loud pré-existentes (`..._corrupted_shapefile_raises_not_assumed_free`, `..._corrupted_shapefile_in_directory_also_raises`, ambos com bytes lixo que nem chegam a parsear como shapefile) seguem passando inalterados — confirma que o fail-loud original continua de pé para corrupção genuína, distinta do caso de auto-interseção agora reparado.

Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-11 "protected_areas distingue WDPA ausente de WDPA corrompido" (fail-loud original, não reaberto); `docs/DECISIONS.md` 2026-09-11 "grid_alignment: mosaic_land_cover fail-loud em tile corrompido" (padrão de rastreabilidade citado por Douglas); `core/geo_utils.py::_simplify_for_intersection` (precedente existente de reparo via `buffer(0)`, mas só no lado do polígono de clip do país, nunca nas features candidatas — decisão aqui é deliberadamente mais restrita: reparar as features WDPA é uma exceção pontual autorizada por Douglas, não uma mudança de política geral de `clip_vector_to_country()`); instrução explícita de Douglas 2026-09-11.

---

## [2026-09-14] - cartografia D7 (cartography.py::plot_criterion_map): ajustes visuais + investigação de river_solar/river_wind
Tipo: `STRUCTURAL_PRESERVE` de conteúdo científico — nenhum criterio teve sua LÓGICA DE CÁLCULO alterada nesta entrada, só a renderização (cartography.py). Instrução explícita de Douglas 2026-09-14 (pacote D7 de 8 itens de cartografia + item de débito técnico).

Mudanças aplicadas:
1. `"Potential (normalised)"` → `"Potential (normalized)"` (solar_resource/wind_resource/biomass_resource unit labels + o comentário do docstring de `plot_criterion_map`) — padronizado para a grafia americana já usada em todo o resto do código (`normalization.py`, `normalize_percentile`, etc.); a grafia britânica só existia nesses 3 labels de plot, nunca no código.
2. Fontes de título/subtítulo/eixos/ticks/colorbar/legenda/stats-strip aumentadas em 20% (título 22→26.4, subtítulo 17→20.4, eixos 16→19.2, ticks 14→16.8, colorbar label 14→16.8, colorbar ticks 12.5→15, legenda 14→16.8, stats strip 18→21.6). O footer (atribuição de CRS, `_add_footer`, fontsize 11) foi deliberadamente MANTIDO como estava — é atribuição/rodapé, não um título ou label do mapa; Douglas pode pedir para incluí-lo também se a leitura de "labels" pretendida for mais ampla.
3. Rosa dos ventos náutica de 8 pontas adicionada (`_draw_compass_rose`), canto superior direito de cada mapa, só "N" rotulado. Implementada como uma inset Axes de tamanho fixo em polegadas (não em `ax.transAxes`) para ficar genuinamente quadrada independente do aspect ratio do mapa (que varia por país/projeção) — um desenho direto em `transAxes` ficaria visualmente esticado. Reutiliza a flag `_is_cbar_ax = True` de `_add_colorbar` (nome preservado, não renomeado, para não alterar `_axes_center_x`'s filtro em dois lugares) para que o stats-strip continue centralizado sob o MAPA, não sob a rosa dos ventos.

Investigação obrigatória antes de qualquer mudança visual em river_solar/river_wind (item 4 da instrução), achados:
- **Confirmado por inspeção de código**: `compute_river_suitability(tech="solar"|"wind")` (`criteria_functions.py` L258-261) é estritamente `{0.0, 1.0}` — `score[dist < buffer_km] = 0.0; score[dist >= buffer_km] = 1.0`, sem caminho intermediário possível. Não é amostragem nem coincidência estatística.
- **Padrão "salpicado" na Amazônia é sinal real, não artefato de rasterização/threshold**: comparação ao vivo (script ad hoc, não commitado) do raster de distância alinhado (`BRA_rivers_aligned.tif`) contra o vetor bruto `HydroRIVERS_v10_sa.shp` numa janela de 2°×2° no interior do Mato Grosso mostra que o padrão dendrítico do raster de distância reproduz exatamente a topologia de drenagem do vetor real (visualmente sobreposto, mesmas bifurcações de afluente a afluente) — não há dissociação entre os dois. A aparência de "sal e pimenta" no mapa país-inteiro vem de dois fatores reais combinados, não de erro: (a) HydroRIVERS inclui every tributário mapeado, produzindo uma rede de drenagem genuinamente densa; (b) `river_safety_buffer_km = 0.5` (500m, DECISIONS.md 2026-09-10) é MENOR que um pixel da grade de 0.01° (~1.1km no equador) — nessa escala, o valor binarizado de um pixel dobra conforme o centro do pixel caia a menos ou mais de 500m do segmento de rio mais próximo, o que produz textura fina/pontilhada em qualquer visualização país-inteiro de uma rede dendrítica real, sem que isso seja um bug.

Avaliação do comportamento binário (item 5 da instrução) — nenhuma mudança de lógica de cálculo feita ou recomendada para nenhum dos três:
- **`lakes_exclusion`**: binário por natureza — um pixel de lago não pode hospedar uma planta, é uma exclusão dura, não uma preferência gradual. Confere com o docstring já existente de `compute_lakes_exclusion` ("mathematically inert... which is why CriteriaParams has no parameter for it") e com o legado (`docs/DECISIONS.md` linha ~877, `lakes_exclusion: 0.5` já era hard exclusion em `common_exclusions` do legado) — bit-exato contra o baseline (`docs/DECISIONS.md` 2026-09-10, regressão pixel-a-pixel). Comportamento correto e documentado, sem divergência.
- **`river_solar`/`river_wind`**: também corretos por design, não um artefato de um threshold que poderia preservar mais gradação sem descaracterizar o critério — representam um SETBACK de segurança ripária (regulatório/legal), não uma métrica de qualidade de recurso, e foram deliberadamente "promoted from soft criterion to hard exclusion... since it represents a safety setback, not a preference" (`docs/DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration"). Uma exclusão de segurança binária É a representação metodologicamente correta de uma faixa legal de afastamento (Código Florestal, Lei 12.651/2012 Art. 4) — não há gradação real a preservar.

Consequência de cartografia dos dois achados acima (item 6 da instrução): `lakes_exclusion`, `river_solar`, `river_wind` migrados de colorbar contínua (`RdYlGn`, que sugeria gradação inexistente) para legenda categórica de 2 cores (`_CATEGORICAL_CRITERIA`), no mesmo padrão visual já usado por `protected_areas` — cosmético, não altera nenhum array de score. `road_suitability`, `grid_suitability`, `river_biomass` NÃO tocados (item 7): distribuição contínua real, confirmada pelos próprios mean/IQR do relatório de critérios (ex. road_suitability BRA: mean=0.514, IQR 0.000-0.854, não degenerado).

Figuras regeneradas para BRA e PRT (item 8): todos os 14 mapas + `slope_degrees`, via `main.py` com `suitability_criteria` reexecutado (entrada removida do manifest para forçar recomputo; `data_acquisition`/`grid_alignment` permaneceram resumidos do manifest, sem re-fetch).

Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration" (origem do `river_safety_buffer_km = 0.5` e da promoção a hard exclusion); `docs/DECISIONS.md` 2026-09-10 (regressão pixel-exata 13/14 critérios, `lakes_exclusion`/`river_solar`/`river_wind`/`river_biomass` inclusos, `max|delta|=0`); `criteria_functions.py::compute_lakes_exclusion`/`compute_river_suitability` (docstrings já existentes); instrução explícita de Douglas 2026-09-14 (pacote D7).

---

## [2026-09-14] - compass rose fix + backlog: mapa de densidade agregada (river_solar/river_wind, BRA) — ideia futura, não pendência de Fase 2b
Tipo: `STRUCTURAL_PRESERVE` (correção visual, nenhuma lógica de cálculo tocada) + registro de ideia de backlog.

Correção da rosa dos ventos (adicionada na entrada anterior, mesma data): o corte do label "N" não era só visualmente apertado — o `ylim` do inset (`[-1, 1]`) não incluía o ponto onde o texto era desenhado (`y≈1.25`), ou seja, o texto ficava fora do próprio espaço de dados do inset, não "por sorte" dentro dele. Corrigido reservando headroom explícito no `ylim` (`[-1.15, 2.0]`) e aumentando a margem física do canto do mapa (0.10→0.16in). Redesenho para estilo náutico "moderno/limpo": anel fino, cruz cardeal (N/E/S/W) mais longa/grossa, pontas intercardeais mais curtas/finas, só "N" rotulado — escolhido sobre um estilo vintage multi-anel por ser mais simples de renderizar bem legível nesse tamanho pequeno. Verificado para BRA (país largo) e PRT (país estreito/alto).

Investigação de legibilidade dos binários (`lakes_exclusion`, `river_solar`, `river_wind`), instrução explícita de Douglas — nenhuma mudança de visualização feita, conclusão foi manter como está:
- `lakes_exclusion`: genuinamente esparso (1.9% excluído no BRA) — legenda categórica claramente legível, sem ressalva.
- `river_solar`/`river_wind`: a legenda categórica já funciona bem em PRT (país pequeno, rede dendrítica visível a olho nu no zoom do mapa) e para `lakes_exclusion`. O "salpicado" pouco legível é específico do BRA em zoom país-inteiro (área grande, rede densa), não um defeito da abordagem categórica em si. Medição real por faixa de latitude no BRA confirma que o padrão carrega sinal espacial genuíno, não é ruído uniforme: Amazônia equatorial 41.8% excluído, Cerrado/Central 35.1%, Sudeste 29.4%, Sul 35.7% — variação de ~12 pontos percentuais atualmente invisível no mapa país-inteiro em zoom total.

**Backlog (ideia futura, opcional — NÃO uma pendência aberta de Fase 2b, que está genuinamente fechada)**: um mapa de densidade agregada complementar (ex.: % de pixels excluídos por célula de grade maior, tipo 0.5° ou 1°) para `river_solar`/`river_wind` no BRA revelaria esse padrão macro-regional hoje invisível no mapa binário pixel-a-pixel — complementar, não substituto do mapa categórico atual. Sem desenho metodológico, sem prioridade definida, sem autorização para implementar. Registrado aqui para não se perder, mesmo padrão de `modulos_futuros_backlog` do `docs/PROGRESS.json` mas mantido em DECISIONS.md por ser um detalhe de cartografia de um módulo já construído, não um módulo novo.

14 figuras regeneradas para BRA e PRT com a rosa dos ventos corrigida (mesmo comando de `main.py` da entrada anterior — `suitability_criteria` reexecutado, `data_acquisition`/`grid_alignment` resumidos do manifest).

Referência (literatura/discussão, se aplicável): entrada anterior "cartografia D7" (mesma data); instrução explícita de Douglas 2026-09-14.

---

## [2026-09-14] - grid (data_acquisition): verificação de estado, sem mudança de decisão
Tipo: `VERIFICATION_UPDATE`

Descrição: brief externo à sessão presumiu `grid.gpkg` como débito técnico pendente ("não implementado, necessário antes de Fase 3") e presumiu incorretamente que a camada representa uma malha regular de células (0.01°). Verificação ao vivo (`resolve_grid_path` + leitura de arquivo + `run_acquisition_phase` isolado, BRA e PRT) confirma que a decisão de 09-08 (wire das 5 camadas restantes a partir do banco local) segue válida e sem regressão: path resolve para ambos os países (`BRA_grid_osm.geojson`, `PRT_grid_osm.geojson`), schema/CRS corretos (EPSG:4326, tags OSM de infraestrutura elétrica — power/voltage/substation/etc, LineString+Point, não uma malha de análise espacial), fase roda sem erro nem warning para a camada grid, `fetch_status=not_implemented` confirmado como valor esperado/documentado, não um sinal de problema.

Justificativa (se METHODOLOGY_REVISION): n/a — este registro não altera a decisão de 09-08, apenas confirma que ela segue correta e fecha a leitura equivocada de um brief externo à sessão.

Referência (literatura/discussão, se aplicável): `docs/DECISIONS.md` 2026-09-08 - wire das 5 camadas restantes a partir do banco local, Fase 1 (decisão original que esta entrada verifica).

---

## [2026-09-14] - rivers/roads BRA (1.8x producao vs isolado): investigacao parcial, causa ainda nao confirmada
Tipo: `VERIFICATION_UPDATE`

Descrição: investigação da pendência registrada em `docs/PROGRESS.json` (`modulos_extra` → `data_acquisition`) — rivers/BRA 348.8s em produção real (via `main.py`) vs. 191.63s isolado, roads/BRA 328.0s vs. 184.4s isolado, ambos ~1.8x mais lentos em produção, causa não confirmada até esta data.

Duas hipóteses testadas com dado concreto nesta sessão:

1. **Hipótese de cache (recompute em vez de reuso entre `data_quality_audit` e `grid_alignment`) — DESCARTADA.** Confirmado por inspeção de código que `audit.py:163-164` e `alignment.py:286` calculam o MESMO `cache_path` (`outputs_dir/country_code/processed/{layer}_clipped.gpkg`) — reuso por convenção de arquivo em disco, já documentado nos dois módulos. Confirmado por medição real (`PRT/rivers`, layer menor por custo/tempo, mesma mecânica de código de BRA): 1ª chamada de `inspect_vector_layer()` com cache frio = 4.09s; 2ª chamada com cache quente = 0.25s — speedup de 16.3x, cache genuinamente reutilizado, sem recomputo.

2. **Threading do `.intersection()` e leitura bbox/STRtree — confirmados funcionando normalmente.** Microbenchmark com dado real (subsample de 60.000 features de `roads/BRA`, das 548.304 casadas via STRtree sobre 895.190 candidatos bbox-prefiltrados): 1 worker = 114.73s (523 feat/s) → 8 workers = 18.08s → speedup 6.35x, próximo do 7.08x documentado em 2026-08-25. Leitura bbox-prefiltrada (8.94s) e STRtree query (1.00s) não são gargalo. Repetição da mesma intersecção 3x consecutivas, sem pausa, no mesmo processo (25.26s / 23.24s / 23.50s) não mostrou tendência de queda — sem evidência de degradação por carga sustentada/throttling nesta escala.

**Não confirmado — reprodução em escala real de BRA não completou nesta sessão.** Tentativa de reproduzir o clip completo e frio de `rivers/BRA` (equivalente ao benchmark histórico de 191-349s) foi interrompida após 44 minutos sem terminar. Amostragem de CPU durante essa janela (`Get-Process`, 2 amostras de 5s) mediu média de apenas ~0.68 núcleos utilizados — bem abaixo do paralelismo que a mesma máquina/sessão demonstrou no microbenchmark item 2 acima (6.35x com 8 workers). Isso é registrado como uma possível diferença de capacidade/alocação de CPU entre esta sessão (ambiente sandboxed) e a máquina original que gerou os números de 2026-08-25/2026-09-08 — NÃO como causa confirmada do fator 1.8x original, e NÃO como uma repetição do próprio achado 1.8x (a comparação feita aqui foi sessão-atual-isolado vs. sessão-atual-produção-tentada, que não pôde ser completada nos dois lados para gerar um novo fator comparável).

Justificativa (se METHODOLOGY_REVISION): n/a — nenhuma mudança de código ou de decisão metodológica feita. Este registro apenas descarta uma hipótese (cache) e deixa a causa raiz do 1.8x original ainda em aberto.

Referência (literatura/discussão, se aplicável): `docs/PROGRESS.json` (`modulos_extra` → `data_acquisition`, nota original "rivers/BRA 348.8s eh 1.8x mais lento... roads/BRA em producao real (328.0s) ~1.8x mais lento"); `docs/DECISIONS.md` 2026-08-25 - clip_vector_to_country() exact-intersection bottleneck (STRtree + simplify + threading) (origem dos números de paralelismo 4/8/16 workers comparados aqui); `src/geofrea/core/geo_utils.py` (`_MAX_INTERSECTION_WORKERS`, `_simplify_for_intersection`, `clip_vector_to_country`).

---

## [2026-09-14] - regression fixtures storage: GitHub Release (opcao 1) + CI skip->fail
Tipo: `STRUCTURAL_PRESERVE`

Descrição: `tests/regression/test_suitability_criteria_regression.py` (26 testes) nunca rodou em CI — não havia workflow algum no repo (confirmado por levantamento de fatos em sessão anterior desta mesma data) — e depende de dois conjuntos de arquivos grandes, gitignored, nunca commitados: `outputs_baseline_fc7b43d/{BRA,PRT}/criteria_builder/tif/*.tif` (1.4GB completo, mas só ~197.5MB no subconjunto BRA+PRT/tif usado pelos testes) e `$GEOWORLD_BASELINE_DIR/data/processed/{BRA,PRT}/*_aligned.tif` (~186MB no mesmo subconjunto). Nenhum dos dois está no histórico do git (confirmado em sessão anterior).

**Decisão: opção 1 — GitHub Release.** Os dois conjuntos são empacotados juntos em um único asset (`regression-fixtures.tar.gz`, ~380MB comprimido, `sha256=cc69fa752572de97bed58c37d932ca98f4f985f2d251409405908ab179b510e7`) anexado a um Release chamado `regression-fixtures-v1`, em vez de: (a) commitar direto no repo (infla todo clone para sempre, mesmo para quem nunca roda os testes de regressão), ou (b) Git LFS (segundo sistema de armazenamento + billing de banda LFS para um asset que muda raramente e é majoritariamente lido, não escrito — um Release já cobre esse caso de uso de graça, dentro do limite de 2GB/asset do GitHub, e o tarball fica bem abaixo disso).

**Escopo exato do tarball** (54 arquivos, layout com dois diretórios de topo — ver comentário no próprio `.github/workflows/regression.yml` para o mapeamento completo):
- `outputs_baseline_fc7b43d/{BRA,PRT}/criteria_builder/tif/*.tif` — **todos** os 16 arquivos por país (32 total), incluindo `proximity_plants.tif` que nenhum teste referencia hoje — mantido porque a instrução original definiu o escopo como o glob inteiro dessa pasta, não um filtro por arquivo individual.
- `legacy_processed/{BRA,PRT}/*_aligned.tif` — 11 arquivos por país (22 total), **excluindo** `*_plants_aligned.tif` (não lido por nenhum teste — `compute_road_suitability`/`compute_river_suitability`/etc. do arquivo de teste usam apenas os 11 layers: elevation/grid/lakes/lc/population/rivers/roads/seismic/slope/solar/wind), excluindo os outros 4 países presentes no diretório legado (CHN/IND/RUS/ZAF, não usados pelos fixtures de BRA/PRT), e excluindo `*_grid_metadata.json` (não é um raster de entrada, não é aberto pelo arquivo de teste).

**Workflow** (`.github/workflows/regression.yml`, trigger `push`/`pull_request` em `main`): baixa o asset via `gh release download`, cacheado via `actions/cache` com chave = checksum do asset (campo `digest` da API de Releases, com fallback documentado para `id+updated_at` se o digest não existir), extrai `outputs_baseline_fc7b43d/` na raiz do workspace e move `legacy_processed/` para `$GEOWORLD_BASELINE_DIR/data/processed/` (definido no job como `${{ github.workspace }}/.legacy_baseline` — não existe checkout real do legado em CI, só o `data/processed/` congelado).

**Mudança skip→fail em CI** (`tests/regression/conftest.py`, fixture `legacy_processed_root` apenas — escopo explicitamente restrito a essa fixture, não a `baseline_dir`/`raw_data_root`): nova função `_in_ci()` checa `CI=true` (padrão do GitHub Actions). Localmente, ausência de `GEOWORLD_BASELINE_DIR` continua `pytest.skip()` (fixture não fetchada não é motivo pra falhar a suíte inteira, mesma convenção de sempre). Em CI, a mesma condição vira `pytest.fail()`: como o workflow provê essa fixture via download de um Release, "ausente" em CI significa download/extração quebrados — um problema real de build vermelho, não estado local de dev não buscado. Antes dessa mudança, um skip em CI passaria despercebido como verde.

**GAP conhecido, não fechado nesta entrada**: `test_protected_areas_footprint_matches_frozen[BRA/PRT]` (2 dos 26 testes) também depende da fixture `raw_data_root` (`GEOFREA_RAW_DATA_DIR` — GADM borders + shapefiles WDPA), que **não faz parte** do escopo do `regression-fixtures.tar.gz` definido acima nem da mudança skip→fail (só `legacy_processed_root` foi alterada, por instrução explícita). Esses 2 testes continuarão pulando silenciosamente em CI até que um fixture set separado para dados brutos GADM/WDPA seja desenhado — registrado aqui para não se perder, sem prioridade definida.

Validado localmente antes deste registro: `CI=true pytest tests/regression/` com os fixtures reais presentes = 26 passed, sem regressão de comportamento (a mudança só afeta o caminho de ausência de fixture, não o de presença).

Justificativa (se METHODOLOGY_REVISION): n/a — `STRUCTURAL_PRESERVE` porque nenhuma lógica científica/de cálculo foi tocada; é infraestrutura de teste/CI.

Referência (literatura/discussão, se aplicável): levantamento de fatos desta mesma data ("Tamanho e status de versionamento de $GEOWORLD_BASELINE_DIR/data/processed" e a sessão anterior sobre `outputs_baseline_fc7b43d/`); `docs/DECISIONS.md` 2026-09-10 "Bloqueio 3 decision (a)" (origem do desenho `legacy_processed_root` isolando suitability_criteria de grid_alignment); instrução explícita de Douglas 2026-09-14 ("Preparar tudo exceto a publicação da Release" — a criação do Release em si fica fora desta entrada, ver comando `gh release create` impresso ao final da resposta da sessão).

---

## [2026-09-14] - pop_suitability: divergencia CI-only vs baseline congelado, causa raiz confirmada (ruido sub-ULP float32 em log1p)
Tipo: correção de robustez (mesma classe de correção de integridade de dado das entradas de nodata de 2026-09-11 — "grid_alignment: slope não herda contaminação de nodata", "reproject com dtype_out float" — mesma filosofia: causa raiz identificada e caracterizada antes de qualquer mudança de comportamento, aqui ainda sem a correção aplicada)

Descrição: primeiro run real do workflow `regression.yml` (2026-09-14, ver entrada anterior "regression fixtures storage") revelou `test_criterion_matches_frozen_baseline[pop_suitability-PRT/BRA]` FAILED em CI (Linux, numpy 2.5.3) — os outros 24 testes (22 passed + 2 skipped, gap já documentado de `protected_areas`) comportaram-se como esperado. Localmente (Windows, numpy 2.5.2) esse mesmo teste é bit-exato: 0 pixels divergentes. Investigação ao vivo confirmou a causa raiz por eliminação, não por suposição:

1. **Hipótese de comparação de threshold sem tolerância — REFUTADA com dado real.** `compute_population_suitability` (`criteria_functions.py:457-486`) não tem nenhuma comparação discreta com `pop_density_threshold` — só `np.clip(pop, 0, threshold)` (clamp contínuo, C0-contínuo) seguido de `log1p`/divisão. Confirmado empiricamente via diagnóstico rodado dentro do próprio runner de CI: dos pixels divergentes, **0/1154 (PRT)** e **0/18434 (BRA)** têm `pop >= threshold(300)` — os valores de `pop` nos pixels divergentes cobrem toda a faixa dinâmica (0.000034 a 183 em BRA), sem nenhum agrupamento perto de 300. Uma comparação de lado de threshold produziria pixels divergentes concentrados perto do valor do threshold; não é o que se observa.

2. **Causa confirmada: arredondamento sub-ULP de `log1p` em float32, divergente entre implementações — não entre "Linux" e "Windows" como blocos monolíticos.** Evidências, coletadas rodando o mesmo cálculo 3 formas (vetorizado `np.log1p`, escalar `np.log1p`, `math.log1p`/libm puro via stdlib) dentro do próprio runner de CI:
   - Delta máximo observado: `8.940697e-08` = exatamente **0.75 ULP** de float32 em 1.0 (`1.192093e-07`) — assinatura de arredondamentos encadeados (log1p(pop) + divisão por log1p(threshold), cada um até 0.5 ULP), não de uma função descontínua.
   - `np.log1p` vetorizado e `np.log1p` escalar **sempre concordam entre si** na mesma máquina — descarta dispatch SIMD-vs-escalar do numpy como a variável (ambos reportam `SIMD Extensions: baseline X86_V2, found X86_V3` tanto no CI Linux quanto localmente no Windows — o nível de vetorização detectado é o mesmo nos dois ambientes).
   - `math.log1p` (libm da plataforma, bypassando o kernel do numpy) **diverge de `np.log1p` mesmo dentro da mesma máquina Linux** — e, pixel a pixel, ora bate com o valor computado no Windows (`frozen`), ora com o valor computado no próprio numpy do Linux (`ours`), inconsistentemente. Isso mostra que existem pelo menos duas implementações de `log1p` com arredondamento de último bit diferente em jogo (kernel vetorizado interno do numpy vs. `libm` da plataforma), não uma distinção simples "SO A vs SO B".

**Conclusão**: não é bug de lógica em GeoFREA, não é problema de threshold, é ruído numérico de ponto flutuante float32 nos limites de reprodutibilidade bit-exata entre implementações de `log1p` — categoria de problema bem documentada em computação científica cross-platform, não uma falha de port.

**Correção de robustez proposta (NÃO aplicada — pendente de aprovação explícita de Douglas)**: trocar, apenas para `pop_suitability`, o `assert max_abs == 0.0` por uma tolerância pequena e coerente com o delta máximo observado (~9e-8). Os outros 13 critérios continuam bit-exatos (`max_abs == 0.0`), inalterados — a mudança é escopada estritamente a este um critério, pelo mecanismo de tolerância por-critério já existente em `CASES` (ver diff proposto abaixo).

```diff
--- a/tests/regression/test_suitability_criteria_regression.py
+++ b/tests/regression/test_suitability_criteria_regression.py
@@ -175,6 +175,14 @@ def _valid(a: np.ndarray) -> np.ndarray:
     return np.isfinite(a) & (a != NODATA_FLOAT) & (a >= 0)
 
 
+# pop_suitability is NOT bit-exact in CI (Linux, numpy 2.5.3) despite being
+# bit-exact locally (Windows, numpy 2.5.2) -- confirmed root cause 2026-09-14
+# (see docs/DECISIONS.md same date): sub-ULP float32 log1p rounding noise
+# between numpy's vectorized kernel and the platform libm, NOT a threshold
+# comparison or a logic defect (0/1154 PRT and 0/18434 BRA differing pixels
+# have pop >= threshold; max delta = 0.75 float32 ULP). Every other
+# criterion in CASES stays bit-exact (atol=0.0) -- this tolerance is scoped
+# to pop_suitability alone.
+_POP_SUITABILITY_ATOL = 2e-7  # ~2x the observed max delta (8.941e-08)
+
+
 @pytest.mark.regression
 @pytest.mark.parametrize(("name", "iso"), PARAMS_LIST)
 def test_criterion_matches_frozen_baseline(name, iso, baseline_dir, legacy_processed_root):
@@ -199,10 +207,14 @@ def test_criterion_matches_frozen_baseline(name, iso, baseline_dir, legacy_processed_root):
     max_abs = float(diff.max()) if diff.size else 0.0
     rmse = float(np.sqrt(np.mean(diff**2))) if diff.size else 0.0
     n_exact = int((diff == 0).sum())
 
-    assert max_abs == 0.0, (
+    atol = _POP_SUITABILITY_ATOL if name == "pop_suitability" else 0.0
+    assert max_abs <= atol, (
         f"{name}/{iso}: not pixel-exact vs frozen baseline — "
-        f"max|delta|={max_abs:.3e}, RMSE={rmse:.3e}, exact={n_exact}/{diff.size}"
+        f"max|delta|={max_abs:.3e} (tolerance={atol:.3e}), RMSE={rmse:.3e}, "
+        f"exact={n_exact}/{diff.size}"
     )
```

Não aplicado nesta entrada — depende de aprovação explícita de Douglas na mesma resposta em que este diff foi apresentado.

Investigação conduzida via um passo de CI temporário (`DEBUG - pop_suitability platform diagnostic`, gated a `workflow_dispatch`) + script `scripts/_debug_pop_ci.py`, ambos criados, rodados, e **removidos** ao final desta mesma sessão (commits `b248d45`→`e480598`→`73e5af6` no branch `main`) — ver `CLAUDE.md` § "Investigações que alteram infraestrutura de CI temporariamente" (regra de processo adicionada nesta mesma data) para a convenção de aprovação e rastro que passa a valer daqui pra frente.

Justificativa (se METHODOLOGY_REVISION): n/a — nenhuma mudança de código aplicada nesta entrada; é caracterização de causa raiz + proposta pendente de aprovação.

Referência (literatura/discussão, se aplicável): investigação ao vivo desta sessão (2026-09-14), runs de CI `34872011543` (diagnóstico inicial, bug de path corrigido) e `34872281587` (diagnóstico completo PRT+BRA com isolamento vetorizado/escalar/libm); `docs/DECISIONS.md` 2026-09-14 "regression fixtures storage" (contexto do primeiro run real que revelou o achado); instrução explícita de Douglas 2026-09-14 ("Registrar achado + propor tolerância + trava de aprovação").

---

## [2026-09-14] - addendum de rotulagem: Justificativa ausente em "protected_areas distingue WDPA ausente de WDPA corrompido"
Tipo: VERIFICATION_UPDATE (addendum à entrada de 2026-09-11 "suitability_criteria: protected_areas distingue WDPA ausente de WDPA corrompido")
Descrição: A entrada original (2026-09-11) tem Tipo METHODOLOGY_REVISION mas nunca usa o rótulo "Justificativa:" exigido pelo template — o conteúdo existe no parágrafo "Veredito ratificado por Douglas (2026-09-11)...", mas sem o campo formal. Este addendum não altera a decisão nem seu conteúdo, apenas identifica essa lacuna de formatação para fins de rastreabilidade.
Justificativa (se METHODOLOGY_REVISION): n/a — addendum de formatação, não muda a decisão original.
Referência (literatura/discussão, se aplicável): docs/DECISIONS.md 2026-09-11 "suitability_criteria: protected_areas distingue WDPA ausente de WDPA corrompido"; docs/audits/consistency-2026-09-14.md secao 3.

---

## [2026-09-14] - addendum de rotulagem: Justificativa ausente em "grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país"
Tipo: VERIFICATION_UPDATE (addendum à entrada de 2026-09-11 "grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país")
Descrição: Mesma lacuna que a entrada acima — Tipo METHODOLOGY_REVISION sem o rótulo "Justificativa:" formal, conteúdo presente em prosa. Este addendum não altera a decisão original.
Justificativa (se METHODOLOGY_REVISION): n/a — addendum de formatação, não muda a decisão original.
Referência (literatura/discussão, se aplicável): docs/DECISIONS.md 2026-09-11 "grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país"; docs/audits/consistency-2026-09-14.md secao 3.

---

(fim das decisões registradas até o momento)
