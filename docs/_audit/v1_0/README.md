# docs/_audit/v1_0: command, decision and report history of v1.0

Copies, taken on 2026-11-23 (COMMAND 199), of the files that lived outside the repository and explain how v1.0 was built. They are dated records, not kept up to date: where a copy and the working file in `D:\Douglas\DOUTORADO\` differ, the working file is the live one. No data, no `.bak` files and no draft scripts are included. Texts are in Portuguese, as written for the author.

## Command and decision files

| File | What it is | Origin |
|---|---|---|
| `comandos_v1_0_GeoFREA.md` | the numbered command file for COMMANDS 166 to 198 (rules, order, execution log in section 4) | author and assistant, 2026-11-17 onward |
| `decisoes_v1_0_GeoFREA.md` | the author's decisions that count as verdicts (rule 14 of the command file) | approved 2026-11-17 |
| `comandos_v1_1_diagnostico.md` | the command file for COMMANDS 199 to 207 (phase names and hypothesis diagnostics) | 2026-11-23, copy refreshed in COMMAND 200B (with the [DONE] marks of 199 to 203) |

## Reports to the author (`_notas_geofrea`)

| File | What it is | Command |
|---|---|---|
| `GeoFREA_resumo_framework_20261117.md` | summary of the framework, read only, every number with its source path | 165A |
| `GeoFREA_limpeza_candidatos_20261117.md` | cleanup candidates by class (keep, regenerable, delete, unknown) | 165A |
| `GeoFREA_limpeza_executada_20261117.md` | cleanup that was executed (moved to `_to_delete/`) | 166 |
| `limpeza_167.md` | final deletion of the `_to_delete/` items and the quarantine | 167 |
| `producao_PRT_179.md` | production of PRT, `lcoe_modeling` (F6) | 179 |
| `producao_IND_180.md` | production of IND, `lcoe_modeling` (F6) | 180 |
| `producao_BRA_181.md` | production of BRA, `lcoe_modeling` (F6) | 181 |
| `producao_PRT_183.md` | production of PRT, `robustness_analysis` (F7) | 183 |
| `producao_IND_184.md` | production of IND, `robustness_analysis` (F7) | 184 |
| `producao_BRA_185.md` | production of BRA, `robustness_analysis` (F7) | 185 |
| `auditoria_pipeline_v1_0.md` | final audit of the v1.0 pipeline, re-run after COMMAND 191A | 191, 191A |
| `limpeza_pos_v1_0_197.md` | post-v1.0 cleanup of `GeoFREA_data` and the archive | 197 |
| `GeoFREA_v1_0_explicado.md` | didactic explanation of v1.0 with numbers checked against the artifacts | 198 |

## Reports already in `docs/_audit/` (cited, not duplicated)

| File | What it is | Command |
|---|---|---|
| [`../prontidao_169.md`](../prontidao_169.md) | readiness audit before production | 169 |
| [`../oq114_170.md`](../oq114_170.md) | wind capacity factor diagnosis (OQ-114) | 170 |
| [`../oq051_173.md`](../oq051_173.md) | hazard channels and thresholds (OQ-051) | 173 |

## Notes

- The checker `conferir198.py` is a draft script and is not versioned here.
- Several reports cite scratchpad or `_notas_geofrea` paths that exist only on the author's machine.
