# D4: exclusões que atingem as usinas existentes (COMANDO 204)

Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `2ae1654`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d4_run.py`, `d4_report.py`), dados em `D4_dados/`. Este texto é gerado de `D4_dados/`; os números não foram digitados à mão. Nenhum valor novo é proposto: o relatório só classifica.

**Objeto.** As usinas em operação do GEM (conjunto `operating` do F7b: todas as usinas com pixel válido, sem filtro de safra nem de precisão de localização, `vintage_min_start_year`, `excluded_location_accuracy` e `vintage_reason` nulos em `experiments.yaml`) e as parcelas excluídas que o motor de elegibilidade do F3 calcula no pixel de 0,01 grau de cada usina (cenário central). Classes pedidas: **(a)** artefato do dado posterior à usina, **(b)** limite mais estrito que a prática, **(c)** exclusão legítima (usina antiga em área hoje restrita). Além delas, os dados mostram dois efeitos que não cabem nas três: a **precisão da coordenada** do GEM (chamada aqui de a2, artefato do dado que não é posterior à usina) e o **tamanho do pixel** (a parcela do pixel contra a pegada da usina). Eles aparecem separados.

## 0. Base e conferências

| Par | Unidades no pixel válido | MW | Unidades com localização exata | % das unidades | % da capacidade | Unidades sem ano de início | Erro máx. E5 recalculado | Erro máx. E4 recalculado (FABDEM) | Erro máx. E4 recalculado (GLO-30) |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 168 | 3.523 | 164 | 97,6% | 97,7% | 10 | 0,000000 | 0,000000 | 0,442 |
| PRT wind | 361 | 5.730 | 359 | 99,4% | 99,5% | 0 | 0,000000 | 0,000000 | 0,080 |
| IND solar | 3.724 | 99.269 | 3.287 | 88,3% | 53,2% | 164 | 0,000000 | 0,000000 | 0,599 |
| IND wind | 679 | 38.937 | 58 | 8,5% | 9,4% | 276 | 0,000000 | 0,000000 | 0,068 |
| BRA solar | 3.946 | 24.894 | 601 | 15,2% | 79,4% | 47 | 0,000000 | 0,000000 | 0,518 |
| BRA wind | 1.135 | 35.946 | 1.129 | 99,5% | 99,1% | 21 | 0,000000 | 0,000000 | 0,063 |

- **E5 e E4 recalculados** das camadas alinhadas da F2a nos pixels das usinas e comparados com o que o F7b gravou (`validation_units`): E5 com erro máximo 0 nos seis pares; E4 com erro máximo 0 usando as contagens de declividade do **FABDEM** (`<ISO>_slope_counts_fabdem_aligned.tif`), que é o que o motor usa. A declividade do GLO-30 (`<ISO>_slope_counts_aligned.tif`, superfície com copas e prédios) dá E4 diferente (última coluna) e entra só como comparação.
- **Camadas:** cobertura do solo = ESA WorldCover **2020** v100, 10 m (`land_cover_counts`, 14.400 amostras por pixel); assentamentos = GHS-SMOD R2023A, época 2020, classe 13 ou maior; áreas protegidas = o GeoJSON bruto do WDPA do projeto (colunas `IUCN_CAT`, `wdpa_id`, `name`; **sem `STATUS_YR` nem tipo de designação**).
- **Safra:** o mapa de cobertura é de 2020; uma usina com início até 2019 já existia quando o mapa foi feito, uma com início em 2021 ou depois não.
- Manifestos iguais ao instantâneo `_snapshots/20261123_pre204` (seção 9).

## 1. Achados em uma página

**Efeito da precisão da coordenada (a2).** Parcela excluída combinada no pixel da usina (média ponderada pela capacidade), por precisão de localização do GEM:

| Par | Localização | Unidades | MW | Excluída combinada, média | Capacidade com combinada >= 0,5 | Capacidade com combinada = 1 |
|---|---|---|---|---|---|---|
| PRT solar | todas | 168 | 3.523 | 0,739 | 83,6% | 6,7% |
| PRT solar | exata | 164 | 3.444 | 0,745 | 84,6% | 6,9% |
| PRT solar | aproximada | 4 | 79 | 0,504 | 38,3% | 0,0% |
| PRT wind | todas | 361 | 5.730 | 0,747 | 79,5% | 28,0% |
| PRT wind | exata | 359 | 5.700 | 0,746 | 79,4% | 28,2% |
| PRT wind | aproximada | 2 | 30 | 0,864 | 100,0% | 0,0% |
| IND solar | todas | 3.724 | 99.269 | 0,769 | 80,2% | 37,6% |
| IND solar | exata | 3.287 | 52.806 | 0,736 | 79,8% | 21,7% |
| IND solar | aproximada | 437 | 46.463 | 0,805 | 80,7% | 55,7% |
| IND wind | todas | 679 | 38.937 | 0,837 | 83,6% | 71,1% |
| IND wind | exata | 58 | 3.653 | 0,535 | 54,7% | 19,9% |
| IND wind | aproximada | 621 | 35.284 | 0,868 | 86,5% | 76,4% |
| BRA solar | todas | 3.946 | 24.894 | 0,513 | 48,7% | 18,9% |
| BRA solar | exata | 601 | 19.775 | 0,409 | 37,0% | 9,0% |
| BRA solar | aproximada | 3.345 | 5.119 | 0,914 | 94,3% | 57,1% |
| BRA wind | todas | 1.135 | 35.946 | 0,332 | 28,8% | 12,9% |
| BRA wind | exata | 1.129 | 35.604 | 0,332 | 28,7% | 13,0% |
| BRA wind | aproximada | 6 | 341 | 0,366 | 43,5% | 0,0% |

- **IND eólica:** 58 das 679 unidades têm localização exata (9,4% da capacidade). Com todas as unidades, 64,7% da capacidade fica em pixel que é ele mesmo assentamento; com as exatas, 5,9%. **BRA solar:** 11,3% contra 0,5%.
- **Artefato posterior à usina em E5 (a1):** parcela de "construído" (classe 50) no pixel das usinas de localização exata, início até 2019 contra início em 2021 ou depois (mapa de 2020): PRT solar 0,100 contra 0,011 (fundo 0,027); PRT wind 0,011 contra 0,011 (fundo 0,027); IND solar 0,164 contra 0,019 (fundo 0,019); IND wind 0,013 contra 0,014 (fundo 0,019); BRA solar 0,048 contra 0,005 (fundo 0,004); BRA wind 0,010 contra 0,018 (fundo 0,004).
- **Declividade (E4):** declividade média (FABDEM, usinas de localização exata) acima do limite central em PRT solar (3,91 graus contra 2,86), PRT wind (12,68 graus contra 11,31); abaixo em IND solar, IND wind, BRA solar, BRA wind.
- **Áreas protegidas (E1):** o arquivo do WDPA do projeto não traz o ano de designação, então a classe (c) não é testável. A parcela da capacidade dentro de área protegida em categoria estrita (Ia, Ib, II) vai de 0,0% a 3,3% entre os pares; o resto está em Not Reported, V, VI, IV, III ou Not Applicable (seção 5).

## 2. Item 1: E5, a classe do WorldCover nos pixels das usinas

`excluded_classes` do cenário central: solar `cropland_excluded` (classes 10, 40, 50, 70, 80, 90, 95), eólica `forest_excluded` (10, 50, 70, 80, 90, 95). Composição média do pixel da usina (parcela das 14.400 amostras de 10 m, ponderada pela capacidade) e E5 registrado; "solo exposto" (60) não é excluído.

| Par | Localização | Unidades | E5 médio | Capacidade com E5 >= 0,5 | árvores (10) | lavoura (40) | construído (50) | solo exposto (60) | arbustos (20) | pastagem (30) |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | todas | 168 | 0,366 | 36,6% | 0,212 | 0,122 | 0,025 | 0,051 | 0,117 | 0,466 |
| PRT solar | exata | 164 | 0,372 | 37,4% | 0,216 | 0,123 | 0,025 | 0,052 | 0,109 | 0,467 |
| PRT wind | todas | 361 | 0,262 | 24,5% | 0,249 | 0,009 | 0,011 | 0,026 | 0,063 | 0,640 |
| PRT wind | exata | 359 | 0,260 | 24,2% | 0,248 | 0,009 | 0,011 | 0,026 | 0,063 | 0,641 |
| IND solar | todas | 3.724 | 0,614 | 66,4% | 0,047 | 0,386 | 0,160 | 0,271 | 0,058 | 0,057 |
| IND solar | exata | 3.287 | 0,556 | 60,8% | 0,030 | 0,424 | 0,092 | 0,302 | 0,060 | 0,081 |
| IND wind | todas | 679 | 0,343 | 33,2% | 0,062 | 0,384 | 0,263 | 0,128 | 0,098 | 0,047 |
| IND wind | exata | 58 | 0,039 | 0,0% | 0,018 | 0,550 | 0,017 | 0,146 | 0,176 | 0,089 |
| BRA solar | todas | 3.946 | 0,320 | 28,8% | 0,110 | 0,133 | 0,072 | 0,070 | 0,319 | 0,291 |
| BRA solar | exata | 601 | 0,235 | 17,7% | 0,087 | 0,136 | 0,010 | 0,079 | 0,386 | 0,301 |
| BRA wind | todas | 1.135 | 0,102 | 5,4% | 0,073 | 0,036 | 0,013 | 0,071 | 0,647 | 0,143 |
| BRA wind | exata | 1.129 | 0,102 | 5,5% | 0,073 | 0,037 | 0,013 | 0,072 | 0,648 | 0,142 |

Fundo (média sobre os pixels válidos do país): PRT: construído 0,027, lavoura 0,056, árvores 0,296, solo exposto 0,026; IND: construído 0,019, lavoura 0,494, árvores 0,240, solo exposto 0,086; BRA: construído 0,004, lavoura 0,084, árvores 0,552, solo exposto 0,008.

**De onde vem o E5 (usinas de localização exata).** Parcela do E5 médio que cada classe excluída responde:

| Par | E5 médio | Árvores | Lavoura | Construído | Água e áreas úmidas |
|---|---|---|---|---|---|
| PRT solar | 0,372 | 58,1% | 33,1% | 6,9% | 2,0% |
| PRT wind | 0,260 | 95,3% | não excluída | 4,1% | 0,6% |
| IND solar | 0,556 | 5,4% | 76,2% | 16,6% | 1,8% |
| IND wind | 0,039 | 46,1% | não excluída | 44,4% | 9,6% |
| BRA solar | 0,235 | 36,9% | 58,2% | 4,3% | 0,6% |
| BRA wind | 0,102 | 70,9% | não excluída | 13,0% | 15,0% |

**Teste de safra (usinas de localização exata): o "construído" no pixel, por data de início da usina.** O mapa é de 2020. Se o mapa vê a usina como área construída, as usinas até 2019 mostram mais "construído" que as de 2021 em diante, que o mapa ainda não viu; sem artefato, os dois grupos ficam parecidos com o fundo.

| Par | Início | Unidades | MW | Construído | Fundo | Capacidade com construído >= 0,1 | Solo exposto | Fundo | E5 médio |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | até 2019 | 79 | 516 | 0,100 | 0,027 | 44,5% | 0,139 | 0,026 | 0,267 |
| PRT solar | 2020 | 9 | 196 | 0,014 | 0,027 | 0,0% | 0,152 | 0,026 | 0,197 |
| PRT solar | 2021 ou depois | 66 | 2.684 | 0,011 | 0,027 | 0,2% | 0,028 | 0,026 | 0,404 |
| PRT solar | sem ano | 10 | 48 | 0,101 | 0,027 | 51,5% | 0,069 | 0,026 | 0,421 |
| PRT wind | até 2019 | 326 | 5.295 | 0,011 | 0,027 | 0,6% | 0,022 | 0,026 | 0,264 |
| PRT wind | 2020 | 2 | 24 | 0,007 | 0,027 | 0,0% | 0,022 | 0,026 | 0,504 |
| PRT wind | 2021 ou depois | 31 | 381 | 0,011 | 0,027 | 0,0% | 0,078 | 0,026 | 0,190 |
| IND solar | até 2019 | 1.278 | 25.524 | 0,164 | 0,019 | 38,7% | 0,300 | 0,086 | 0,559 |
| IND solar | 2020 | 192 | 2.128 | 0,062 | 0,019 | 23,0% | 0,273 | 0,086 | 0,582 |
| IND solar | 2021 ou depois | 1.791 | 23.884 | 0,019 | 0,019 | 4,9% | 0,308 | 0,086 | 0,551 |
| IND solar | sem ano | 26 | 1.269 | 0,088 | 0,019 | 25,4% | 0,308 | 0,086 | 0,537 |
| IND wind | até 2019 | 29 | 1.743 | 0,013 | 0,019 | 1,3% | 0,093 | 0,086 | 0,038 |
| IND wind | 2021 ou depois | 8 | 1.122 | 0,014 | 0,019 | 0,0% | 0,258 | 0,086 | 0,028 |
| IND wind | sem ano | 21 | 788 | 0,030 | 0,019 | 6,3% | 0,104 | 0,086 | 0,056 |
| BRA solar | até 2019 | 102 | 2.478 | 0,048 | 0,004 | 13,1% | 0,113 | 0,008 | 0,214 |
| BRA solar | 2020 | 32 | 893 | 0,004 | 0,004 | 0,8% | 0,588 | 0,008 | 0,029 |
| BRA solar | 2021 ou depois | 420 | 14.129 | 0,005 | 0,004 | 0,8% | 0,044 | 0,008 | 0,245 |
| BRA solar | sem ano | 47 | 2.275 | 0,002 | 0,004 | 0,0% | 0,057 | 0,008 | 0,276 |
| BRA wind | até 2019 | 609 | 15.338 | 0,010 | 0,004 | 0,2% | 0,118 | 0,008 | 0,119 |
| BRA wind | 2020 | 53 | 1.778 | 0,002 | 0,004 | 0,0% | 0,102 | 0,008 | 0,040 |
| BRA wind | 2021 ou depois | 446 | 17.480 | 0,018 | 0,004 | 3,4% | 0,032 | 0,008 | 0,096 |
| BRA wind | sem ano | 21 | 1.008 | 0,001 | 0,004 | 0,0% | 0,004 | 0,008 | 0,079 |

Em 2020 o mapa pode ter pegado obras: nas solares de 2020 o "solo exposto" fica acima do fundo (por exemplo BRA solar), e solo exposto não é classe excluída.

## 3. Item 2: E4, a declividade nos pixels das usinas

Limite central: solar 2,86 graus (5%), eólica 11,31 graus (20%); restritivo 3% e 10%, permissivo 10% e 30%. Declividade média do pixel (graus, ponderada pela capacidade) com o FABDEM (usado pelo motor) e com o GLO-30, e, na segunda tabela, a parcela da capacidade cujo pixel tem E4 >= 0,5, isto é, metade ou mais das amostras de 30 m acima do limite central (FABDEM, o que o motor usa).

| Par | Unidades | Declividade média, FABDEM (graus) | GLO-30 (graus) | Mediana (GLO-30) | p90 (GLO-30) | E4 central (motor) | E4 restritivo | E4 permissivo |
|---|---|---|---|---|---|---|---|---|
| PRT solar | 168 | 3,88 | 4,59 | 3,87 | 8,43 | 0,478 | 0,652 | 0,234 |
| PRT wind | 361 | 12,65 | 12,88 | 12,02 | 19,68 | 0,515 | 0,770 | 0,307 |
| IND solar | 3.724 | 1,22 | 1,78 | 1,43 | 3,52 | 0,068 | 0,155 | 0,026 |
| IND wind | 679 | 2,05 | 2,82 | 1,93 | 4,70 | 0,036 | 0,075 | 0,020 |
| BRA solar | 3.946 | 2,07 | 2,51 | 3,46 | 8,89 | 0,197 | 0,344 | 0,074 |
| BRA wind | 1.135 | 4,75 | 5,04 | 3,44 | 11,74 | 0,125 | 0,269 | 0,060 |

| Par | Capacidade com E4 central >= 0,5 (FABDEM) | Capacidade com E4 central > 0 |
|---|---|---|
| PRT solar | 54,0% | 99,6% |
| PRT wind | 51,0% | 99,0% |
| IND solar | 3,7% | 69,7% |
| IND wind | 1,6% | 30,4% |
| BRA solar | 14,4% | 86,8% |
| BRA wind | 7,5% | 56,3% |

A diferença entre FABDEM e GLO-30 (colunas 3 e 4 da primeira tabela) é a do modelo de elevação: o GLO-30 é uma superfície (copas, prédios, painéis) e acrescenta declividade; o motor já usa o FABDEM.

## 4. Item 3: E6, assentamentos (GHS-SMOD) e distância ao assentamento

`classe GHS >= 13` é assentamento (M-F2a-11). A distância é do **ponto** da usina à borda do pixel de assentamento mais próximo (janela de 7 x 7 pixels; "sem assentamento" quando não há nenhum na janela). Setbacks: solar 0 / 500 / 1.000 m e eólica 500 / 800 / 1.000 m (permissivo / central / restritivo).

| Par | Localização | Unidades | E6 médio | Capacidade com E6 = 1 | Pixel da usina é assentamento | Ponto dentro do setback central | Ponto dentro de 1.000 m | Distância mediana (m) | Sem assentamento na janela |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | todas | 168 | 0,063 | 2,3% | 1,8% | 3,4% | 12,6% | 1.125 | 47,0% |
| PRT solar | exata | 164 | 0,062 | 2,3% | 1,8% | 3,5% | 12,4% | 1.130 | 46,2% |
| PRT wind | todas | 361 | 0,041 | 2,2% | 1,1% | 3,6% | 5,1% | 1.531 | 78,9% |
| PRT wind | exata | 359 | 0,039 | 2,2% | 1,1% | 3,6% | 4,6% | 1.540 | 79,3% |
| IND solar | todas | 3.724 | 0,479 | 36,0% | 33,5% | 47,0% | 58,7% | 317 | 18,5% |
| IND solar | exata | 3.287 | 0,369 | 20,2% | 18,0% | 35,0% | 53,8% | 354 | 17,0% |
| IND wind | todas | 679 | 0,763 | 65,9% | 64,7% | 75,7% | 77,2% | 0 | 7,1% |
| IND wind | exata | 58 | 0,405 | 10,5% | 5,9% | 38,9% | 45,4% | 845 | 16,2% |
| BRA solar | todas | 3.946 | 0,131 | 11,4% | 11,3% | 13,1% | 14,6% | 0 | 70,9% |
| BRA solar | exata | 601 | 0,015 | 0,5% | 0,5% | 1,0% | 2,9% | 1.506 | 84,3% |
| BRA wind | todas | 1.135 | 0,034 | 1,8% | 1,8% | 3,5% | 3,9% | 2.086 | 81,4% |
| BRA wind | exata | 1.129 | 0,034 | 1,8% | 1,8% | 3,5% | 3,9% | 2.105 | 81,8% |

**Teste de safra para E6 (usinas de localização exata).** Parcela da capacidade cujo pixel é assentamento, por data de início (a época do GHS-SMOD é 2020):

| Par | Início | Unidades | MW | Capacidade em pixel de assentamento |
|---|---|---|---|---|
| PRT solar | até 2019 | 79 | 516 | 4,9% |
| PRT solar | 2020 | 9 | 196 | 0,0% |
| PRT solar | 2021 ou depois | 66 | 2.684 | 0,8% |
| PRT solar | sem ano | 10 | 48 | 30,6% |
| PRT wind | até 2019 | 326 | 5.295 | 1,2% |
| PRT wind | 2020 | 2 | 24 | 0,0% |
| PRT wind | 2021 ou depois | 31 | 381 | 0,0% |
| IND solar | até 2019 | 1.278 | 25.524 | 23,1% |
| IND solar | 2020 | 192 | 2.128 | 17,3% |
| IND solar | 2021 ou depois | 1.791 | 23.884 | 12,6% |
| IND solar | sem ano | 26 | 1.269 | 19,1% |
| IND wind | até 2019 | 29 | 1.743 | 3,7% |
| IND wind | 2021 ou depois | 8 | 1.122 | 0,0% |
| IND wind | sem ano | 21 | 788 | 19,0% |
| BRA solar | até 2019 | 102 | 2.478 | 0,2% |
| BRA solar | 2020 | 32 | 893 | 0,6% |
| BRA solar | 2021 ou depois | 420 | 14.129 | 0,6% |
| BRA solar | sem ano | 47 | 2.275 | 0,0% |
| BRA wind | até 2019 | 609 | 15.338 | 0,0% |
| BRA wind | 2020 | 53 | 1.778 | 0,0% |
| BRA wind | 2021 ou depois | 446 | 17.480 | 3,6% |
| BRA wind | sem ano | 21 | 1.008 | 0,0% |

## 5. Item 4: E1, a designação do WDPA nas usinas dentro de área protegida

Ponto da usina dentro de um polígono do WDPA do projeto, contra a parcela do pixel que o motor exclui. O arquivo traz `IUCN_CAT` mas **não traz o ano de designação (`STATUS_YR`) nem o tipo de designação**; sem eles não se testa se a área protegida é posterior à usina.

| Par | Localização | Unidades | E1 do pixel, médio | Capacidade com E1 >= 0,5 | Ponto dentro de área protegida | Unidades dentro | Pixel com E1 > 0 e ponto fora |
|---|---|---|---|---|---|---|---|
| PRT solar | todas | 168 | 0,053 | 4,8% | 8,2% | 11 | 0,7% |
| PRT solar | exata | 164 | 0,055 | 4,9% | 8,4% | 11 | 0,7% |
| PRT wind | todas | 361 | 0,284 | 28,5% | 28,1% | 106 | 5,6% |
| PRT wind | exata | 359 | 0,285 | 28,5% | 28,2% | 106 | 5,6% |
| IND solar | todas | 3.724 | 0,014 | 1,1% | 1,0% | 97 | 3,8% |
| IND solar | exata | 3.287 | 0,022 | 1,6% | 1,4% | 71 | 6,1% |
| IND wind | todas | 679 | 0,101 | 9,8% | 9,7% | 43 | 4,9% |
| IND wind | exata | 58 | 0,172 | 16,9% | 15,6% | 10 | 12,1% |
| BRA solar | todas | 3.946 | 0,084 | 8,4% | 8,3% | 227 | 1,4% |
| BRA solar | exata | 601 | 0,092 | 9,3% | 9,1% | 61 | 1,2% |
| BRA wind | todas | 1.135 | 0,128 | 13,3% | 12,4% | 162 | 1,6% |
| BRA wind | exata | 1.129 | 0,129 | 13,4% | 12,5% | 162 | 1,6% |

Categoria IUCN das usinas cujo ponto cai dentro de área protegida (MW; "estrita" = Ia, Ib, II):

| Par | MW dentro | MW em categoria estrita | Parcela estrita | Por categoria (MW) |
|---|---|---|---|---|
| PRT solar | 288,8 | 0,0 | 0,0% | Not Reported: 286,9, IV: 1,9 |
| PRT wind | 1.608,9 | 0,0 | 0,0% | Not Reported: 1.268,9, V: 340,0 |
| IND solar | 982,7 | 0,0 | 0,0% | Not Reported: 875,7, Not Applicable: 107,0 |
| IND wind | 3.765,0 | 0,0 | 0,0% | Not Reported: 2.054,0, Not Applicable: 1.711,0 |
| BRA solar | 2.054,0 | 16,5 | 0,8% | V: 1.999,0, Not Reported: 16,5, VI: 16,5, Ib: 10,0, II: 6,5, III: 5,5 |
| BRA wind | 4.446,8 | 147,8 | 3,3% | V: 4.284,0, II: 147,8, Not Reported: 15,0 |

## 6. Classificação por restrição (item 5)

Regras usadas (cada uma é uma medida desta seção, não um valor novo de parâmetro):

- **(a1) artefato posterior à usina:** nas usinas de localização exata com pelo menos 20 unidades até 2019, o "construído" (E5) ou a parcela em pixel de assentamento (E6) das usinas até 2019 é pelo menos o dobro do das usinas de 2021 em diante, o dobro do fundo (E5) e pelo menos 0,02 maior em E5; em E6 a regra é a diferença de pelo menos 5 pontos percentuais e a razão de pelo menos 1,5 entre as usinas até 2019 e as de 2021 em diante (não há fundo de assentamentos).
- **(a2) artefato da coordenada:** com todas as unidades, o E5 médio (E5) ou a parcela da capacidade em pixel de assentamento (E6) é pelo menos 1,5 vez o das unidades de localização exata.
- **(b) limite mais estrito que a prática:** a restrição é uma escolha de parâmetro do cenário (classe excluída, limite de declividade, setback, categoria do WDPA) e as usinas existentes a violam em parte relevante: E5, E5 médio de pelo menos 0,2 com mais de 50% dele em classes de escolha (lavoura na solar, árvores nas duas); E4, declividade média no pixel acima do limite central ou capacidade com E4 >= 0,5 acima de 10%; E6, parcela da capacidade (exata) com o ponto dentro do setback central acima de 10%; E1, pelo menos 5% da capacidade dentro de área protegida e mais de 50% dela em categoria não estrita.
- **(c) exclusão legítima (usina antiga em área hoje restrita):** exige o ano de designação ou de construção da restrição; só é avaliável para as camadas com ano. Nenhuma das quatro camadas traz o ano da restrição (WorldCover 2020 e GHS-SMOD 2020 são fotografias; o WDPA do projeto não tem `STATUS_YR`): **não avaliável** nos quatro casos.

| Par | E5 (WorldCover) | E4 (declividade) | E6 (assentamentos) | E1 (áreas protegidas) |
|---|---|---|---|---|
| PRT solar | a1: sim; a2: não (E5 0,37 com todas contra 0,37 com exatas); b: sim (E5 exato 0,37, 91% dele em classes de escolha) | b: sim (média 3,9 graus contra 2,9; 54% da capacidade com E4 >= 0,5) | a1: não (até 2019 4,9% contra 2021 em diante 0,8%); a2: não (1,8% com todas contra 1,8% com exatas); b: não (3,5% dentro do setback central) | b: sim (8,2% da capacidade dentro; 100% dela em categoria não estrita) |
| PRT wind | a1: não; a2: não (E5 0,26 com todas contra 0,26 com exatas); b: sim (E5 exato 0,26, 95% dele em classes de escolha) | b: sim (média 12,7 graus contra 11,3; 51% da capacidade com E4 >= 0,5) | a1: não (até 2019 1,2% contra 2021 em diante 0,0%); a2: não (1,1% com todas contra 1,1% com exatas); b: não (3,6% dentro do setback central) | b: sim (28,1% da capacidade dentro; 100% dela em categoria não estrita) |
| IND solar | a1: sim; a2: não (E5 0,61 com todas contra 0,56 com exatas); b: sim (E5 exato 0,56, 82% dele em classes de escolha) | b: não (média 1,2 graus contra 2,9; 4% da capacidade com E4 >= 0,5) | a1: sim (até 2019 23,1% contra 2021 em diante 12,6%); a2: sim (33,5% com todas contra 18,0% com exatas); b: sim (35,0% dentro do setback central) | b: não (1,0% da capacidade dentro; 100% dela em categoria não estrita) |
| IND wind | a1: não; a2: sim (E5 0,34 com todas contra 0,04 com exatas); b: não (E5 exato 0,04, 46% dele em classes de escolha) | b: não (média 3,0 graus contra 11,3; 2% da capacidade com E4 >= 0,5) | a1: não (até 2019 3,7% contra 2021 em diante 0,0%); a2: sim (64,7% com todas contra 5,9% com exatas); b: sim (38,9% dentro do setback central) | b: sim (9,7% da capacidade dentro; 100% dela em categoria não estrita) |
| BRA solar | a1: sim; a2: não (E5 0,32 com todas contra 0,23 com exatas); b: sim (E5 exato 0,23, 95% dele em classes de escolha) | b: sim (média 1,5 graus contra 2,9; 14% da capacidade com E4 >= 0,5) | a1: não (até 2019 0,2% contra 2021 em diante 0,6%); a2: sim (11,3% com todas contra 0,5% com exatas); b: não (1,0% dentro do setback central) | b: sim (8,3% da capacidade dentro; 99% dela em categoria não estrita) |
| BRA wind | a1: não; a2: não (E5 0,10 com todas contra 0,10 com exatas); b: não (E5 exato 0,10, 71% dele em classes de escolha) | b: não (média 4,7 graus contra 11,3; 7% da capacidade com E4 >= 0,5) | a1: não (até 2019 0,0% contra 2021 em diante 3,6%); a2: não (1,8% com todas contra 1,8% com exatas); b: não (3,5% dentro do setback central) | b: sim (12,4% da capacidade dentro; 97% dela em categoria não estrita) |

(c) não é avaliável em nenhuma coluna. O cruzamento com o ano de entrada em operação do GEM foi feito para as duas camadas fotográficas (E5 e E6) como teste de safra (a1).

## 7. O que os achados dizem

Só o que os números mostram; a decisão sobre o que fazer fica para o D0.

- **E5, artefato posterior à usina (a1):** PRT solar, IND solar, BRA solar. Nas usinas de 2020 das solares, o solo exposto passa de três vezes o fundo e de três vezes o das usinas de 2021 em diante em PRT solar, BRA solar (compatível com obras no mapa de 2020); solo exposto não é classe excluída.
- **E5, escolha de parâmetro (b):** PRT solar, PRT wind, IND solar, BRA solar: o E5 vem de classes que o cenário central escolheu excluir (lavoura na solar, árvores nas duas tecnologias), não de erro do mapa. Artefato da coordenada (a2): IND wind.
- **E4:** (b) em PRT solar, PRT wind, BRA solar. A declividade do pixel mistura o terreno da usina com o do resto do pixel de 1,1 km. O GLO-30 dá declividade média maior que o FABDEM em todos os pares (0,23 a 0,77 graus a mais); o motor já usa o FABDEM.
- **E6:** artefato da coordenada (a2) em IND solar, IND wind, BRA solar; artefato posterior à usina (a1) em IND solar; limite mais estrito que a prática (b) em IND solar, IND wind. Com todas as unidades, IND eólica e BRA solar têm a capacidade em pixel de assentamento muito acima da das unidades de localização exata (seção 4), o que é compatível com coordenadas de cidade ou de município (o GEM marca essas unidades como localização aproximada).
- **E1:** (b) em PRT solar, PRT wind, IND wind, BRA solar, BRA wind; a designação do cenário central exclui todas as categorias. O ano de designação não está no arquivo, então (c) não é avaliável.

## 8. Origem dos números e limites

| Número | Origem |
|---|---|
| usinas, precisão de localização, ano de início, E1 a E6 do pixel | `outputs/<ISO>/external_validation/artifacts/validation_units.parquet` (F7b), GEM em `raw/gem/<ISO>/gem_solar_wind_<ISO>.parquet` |
| cobertura do solo | `outputs/<ISO>/grid_alignment/artifacts/<ISO>_land_cover_counts_aligned.tif` (WorldCover 2020 v100) |
| declividade | `<ISO>_slope_counts_fabdem_aligned.tif` (motor) e `<ISO>_slope_counts_aligned.tif` (GLO-30) |
| assentamentos | `<ISO>_settlements_aligned.tif` (GHS-SMOD R2023A, época 2020) |
| áreas protegidas | `raw/wdpa/<ISO>/<ISO>_protected_areas_wdpa.geojson` |
| limites e classes do cenário | `config/experiments.yaml`, `land_availability.technologies` |

Limites:

- A localização das usinas é a do GEM; "aproximada" quer dizer que a coordenada pode estar a quilômetros da usina. Em IND eólica só 58 unidades têm localização exata; as parcelas "exatas" dessa tecnologia vêm de pouca capacidade.
- O pixel tem 0,01 grau (cerca de 1,1 km); as parcelas E1 a E6 são do pixel, não da pegada da usina. Uma usina pequena num pixel com terreno íngreme em outra parte do pixel recebe E4 alto sem estar na parte íngreme. A pegada da usina não é medida aqui.
- A classe (c) não é avaliável: faltam anos de designação (WDPA) e de mudança de uso (WorldCover e GHS-SMOD são de 2020).
- A distância ao assentamento usa uma janela de 7 x 7 pixels e a borda do pixel de 0,01 grau, não a geodésica por subpixel do motor (M-F2b-01).
- O ano de início do GEM falta em parte das unidades (coluna 7 da tabela da seção 0); elas ficam no grupo "sem ano".

## 9. Manifestos e referências no momento da geração

Manifestos comparados com o instantâneo (SHA-256): 8 de 8 iguais.
Tag `v1.0` aponta para `107d1b8` e o objeto da tag `prereg-v1` é `685a29cc`, como registrados.
