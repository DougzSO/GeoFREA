# docs

Index of the documents of GeoFREA v2. The documents describe the current state only; the history is in git and in the tags `v1.0`, `v1.1` and `v1-final`.

| Document | What it is |
|---|---|
| `METHODOLOGY.md` | The method and the architecture, version 2.0.0: the single source of truth. Rules `M-`, `U-`, `A-`, `V-`, `S-`, thesis outputs `T-`. |
| `DECISIONS.md` | Decisions of v2, append-only, from DEC-001 ("GeoFREA v2 adopted"). |
| `OPEN_QUESTIONS.md` | Unresolved items only. |
| `LIMITATIONS.md` | Declared limitations and every Tier 3 value, one line each. |
| `CONVENTIONS.md` | How code, records and tests are written. |
| `PIPELINE_GUIDE.md` | How the pipeline runs: the graph, when a phase resumes, what each phase costs, the commands. |
| `PROGRESS.json` | Status per phase, country and milestone. |
| `phases/` | One record per phase (`F1` to `F8`, `core`): the contract, the conformance table and the active implementation decisions `D-`. The records of F4 and F7 start empty and the modules M1 to M3 get theirs when they are built. |
| `data/` | Provenance of data: grid and coverage. |
| `figures/` | Style guide, the single specification of the figures and examples. |
| `evidence/` | Measurement and audit reports that the documents cite, by subject: `costs/`, `land_and_potential/`, `climate/`, `infrastructure/`, `v1_diagnostics/`. |
| `thesis/` | LaTeX text of the thesis (see its README). |
| `v1/` | `record.md`: the results and the diagnosis of v1; `inheritance.md`: one row per item of the v1 registers that carries over. |

Identifier prefixes: `M-<phase>-nn` method item, `D-<phase>-nnn` implementation decision, `DEC-nnn` decision, `OQ-nnn` open question, `L-nnn` limitation, `T-<id>` thesis output, `H<n>` hypothesis. A v1 decision cited in v2 text is written "v1 DEC-nnn".
