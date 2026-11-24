# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""Confere que a reconstrucao por celula reproduz o LCOE nominal gravado (F6) e a decomposicao soma o total."""
import sys
import numpy as np
import d1_common as c

for iso, tech in c.PAIRS:
    df, res, nom, cells = c.load_cells(iso, tech)
    d = (df["lcoe_recon"] - df["lcoe_stored"]).abs()
    full = c.components(
        df, nom, capex=float(nom.capex_usd_per_kw[0]), opex_frac=float(nom.opex_fixed_frac[0]),
        life=float(nom.lifetime_years[0]), rate=float(nom.discount_rate[0]), cf=None,
        connection=True, degradation=True, loss=True,
    )
    d2 = np.abs(full - df["lcoe_recon"].to_numpy())
    print(iso, tech, "n", len(df), "sem armazenado", int(df["lcoe_stored"].isna().sum()),
          "max|recon-gravado|", float(np.nanmax(d)), "max|decomp-recon|", float(np.nanmax(d2)),
          "capex", float(nom.capex_usd_per_kw[0]), "om", float(nom.opex_fixed_frac[0]), "life", float(nom.lifetime_years[0]),
          "rate", float(nom.discount_rate[0]), "alpha", float(nom.transmission_loss_per_km[0]), "opexvar", float(nom.opex_var_usd_per_mwh[0]))
    sys.stdout.flush()
