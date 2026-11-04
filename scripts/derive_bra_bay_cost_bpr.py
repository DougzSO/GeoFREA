"""BRA bay cost from the ANEEL Banco de Precos de Referencia (BPR), COMMAND 85 (OQ-001).

Sums price x quantity of every item of the switching module Entrada de Linha (EL) at 138 kV for each arrangement (BS, BD4, BD5, BPT) from
`banco-preco-referencia-item-modulo-manobra.csv`, and adds the infrastructure-of-switching module of 138 kV from
`banco-preco-referencia-item-infraestrutura-manobra.csv` (one block per arrangement, identical in each). Items carry their own reference
index (`IndiceReferencia`); the dominant one is 6/2017. Reads `GEOFREA_DATA_DIR/external/aneel_bpr/` (download the CSVs from
dadosabertos.aneel.gov.br, datasets bpr-banco-de-precos-de-referencia-subestacao) and writes `el138_modules.json` beside them.

Usage: python scripts/derive_bra_bay_cost_bpr.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
VOLTAGE_KV = "138"


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)


def _value(frame: pd.DataFrame) -> pd.Series:
    price = frame["VlrPrecoBrasil"].str.replace(",", ".").astype(float)
    quantity = frame["VlrQuantidade"].str.replace(",", ".").astype(float)
    return price * quantity


def main() -> None:
    folder = _data_dir() / "external" / "aneel_bpr"
    modules = _read(folder / "banco-preco-referencia-item-modulo-manobra.csv")
    modules["value"] = _value(modules)
    entrada = modules[
        (modules["NomTipoTensao"].str.strip() == VOLTAGE_KV)
        & (modules["SigTipoModuloManobra"] == "EL")
    ]
    equipment = entrada.groupby(entrada["DscTipoArranjo"].str.strip())["value"].sum()
    infra = _read(folder / "banco-preco-referencia-item-infraestrutura-manobra.csv")
    infra = infra[infra["NomTipoTensao"].str.strip() == VOLTAGE_KV].copy()
    infra["value"] = infra["VlrPrecoBrasil"].str.replace(",", ".").astype(float) * infra[
        "VlrQuantidade"
    ].str.replace(",", ".").astype(float)
    arrangements = len(equipment)
    per_module = (
        float(infra["value"].sum()) / arrangements
    )  # the block is repeated once per arrangement
    totals = {name: round(float(value) + per_module, 2) for name, value in equipment.items()}
    result = {
        "equipment": {k: round(float(v), 2) for k, v in equipment.items()},
        "infra_per_module": round(per_module, 2),
        "total": totals,
        "data_generation_date": str(modules["DatGeracaoConjuntoDados"].iloc[0]),
        "reference_indices_of_BPT_items": entrada[entrada["DscTipoArranjo"].str.strip() == "BPT"][
            "IndiceReferencia"
        ]
        .str.lstrip("0")
        .value_counts()
        .to_dict(),
    }
    (folder / "el138_modules.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
