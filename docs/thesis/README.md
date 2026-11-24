# docs/thesis

LaTeX text of the thesis. `docs/METHODOLOGY.md` stays the single source of truth for the method; a text here states a definition or a rule in the form the thesis uses and must agree with it. The scientific content of a `.tex` file changes only with the author's authorization.

```
thesis/
  README.md
  references.bib          one bibliography; only keys that a .tex of this folder cites
  intro/                  introduction and notation (rewritten after the METHODOLOGY v2 is closed)
  theory/                 the three chapter 2 texts
  methods/
    land_eligibility.tex      F2b and F3: riparian buffers, settlements, terrain, elevation, minimum area
    technical_potential.tex   F5: capacity, capacity factor
    costs.tex                 F6: core costs, grid connection, degradation, the AC and DC basis of the IRENA values
    climate.tex               hazard exposure indicators and the validity range of the wind factor
    validation.tex            published potentials, spatial scale and external validation (F7b)
  hypotheses/             empty until `prereg-v2`
```

Open items of the text:

- `intro/notation.tex` still defines the notation of the hypotheses of v1 and refers to sections that no longer exist; `intro/cap1_introduction.tex` refers to the methodology chapter. Both are rewritten after the METHODOLOGY v2 is closed.
- `references.bib` holds the keys of the cited works that were in the two bibliographies of v1; the intro and theory texts also cite works that are in the author's main bibliography and not here.
- Thesis figures and tables are not stored here. F8 writes them to `GEOFREA_DATA_DIR/outputs/thesis/`, named by their T-ID.
