"""Generate the PRIM reference fixture `tests/fixtures/prim_reference.json` with `ema_workbench` (D-F7-021, D16).

This script is not part of the project environment. It needs Python 3.12 or newer and `ema_workbench` 3.0.0, which `.venv` (Python 3.11) does
not have, so it ran once in a temporary environment outside `.venv`:

    PYTHONHASHSEED=0 <python3.12> scripts/generate_prim_reference.py tests/fixtures/prim_reference.json

The cases are small synthetic datasets (seeded NumPy generators); each stores its descriptors, its binary outcome, the settings and the
trajectory of the first box that `ema_workbench.analysis.prim.Prim.find_box` returns. `tests/unit/test_robustness_prim.py` compares the
own implementation (`geofrea.robustness_analysis.prim`) with it. No real data are used.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import ema_workbench
import numpy as np
import pandas as pd
from ema_workbench.analysis import prim

COMMAND = (
    "PYTHONHASHSEED=0 python scripts/generate_prim_reference.py tests/fixtures/prim_reference.json"
)


def _noise(rng: np.random.Generator, y: np.ndarray, share: float) -> np.ndarray:
    flip = rng.random(y.size) < share
    return np.where(flip, 1 - y, y).astype(int)


def _cases() -> list[dict]:
    cases = []
    rng = np.random.default_rng(101)
    x = pd.DataFrame({"a": rng.random(600), "b": rng.random(600), "c": rng.random(600)})
    y = _noise(rng, ((x["a"] > 0.6) & (x["b"] < 0.4)).astype(int).to_numpy(), 0.08)
    cases.append({"name": "two_real_planted_box", "x": x, "y": y, "alpha": 0.05, "mass_min": 0.05})
    cases.append(
        {"name": "two_real_planted_box_coarse", "x": x, "y": y, "alpha": 0.1, "mass_min": 0.1}
    )

    rng = np.random.default_rng(202)
    n = 800
    x = pd.DataFrame(
        {
            "a": rng.random(n),
            "b": rng.normal(size=n),
            "gcm": rng.choice(["g1", "g2", "g3", "g4"], n),
            "ssp": rng.choice(["s126", "s370", "s585"], n),
        }
    )
    y = ((x["a"] < 0.35) & x["gcm"].isin(["g1", "g2"]).to_numpy()).astype(int).to_numpy()
    y = _noise(rng, y, 0.1)
    cases.append({"name": "real_and_categorical", "x": x, "y": y, "alpha": 0.05, "mass_min": 0.05})

    rng = np.random.default_rng(303)
    n = 500
    x = pd.DataFrame({f"d{i}": np.round(rng.random(n), 1) for i in range(4)})
    y = _noise(rng, ((x["d0"] + x["d1"]) > 1.3).astype(int).to_numpy(), 0.05)
    cases.append({"name": "tied_values", "x": x, "y": y, "alpha": 0.05, "mass_min": 0.05})

    rng = np.random.default_rng(404)
    x = pd.DataFrame({"a": rng.random(400), "b": rng.random(400)})
    y = (rng.random(400) < 0.2).astype(int)
    cases.append({"name": "no_signal", "x": x, "y": y, "alpha": 0.05, "mass_min": 0.05})
    return cases


def _limits(box_lim: pd.DataFrame) -> dict:
    out = {}
    for column in box_lim.columns:
        lo, hi = box_lim.loc[0, column], box_lim.loc[1, column]
        if isinstance(lo, set):
            out[column] = {"categories": sorted(lo)}
        else:
            out[column] = {"lower": float(lo), "upper": float(hi)}
    return out


def main(target: Path) -> None:
    result = {
        "generator": {
            "command": COMMAND,
            "ema_workbench": ema_workbench.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "cases": [],
    }
    for case in _cases():
        x, y = case["x"], case["y"].astype(float)
        search = prim.Prim(
            x,
            y,
            peel_alpha=case["alpha"],
            paste_alpha=case["alpha"],
            mass_min=case["mass_min"],
        )
        box = search.find_box()
        trajectory = box.peeling_trajectory
        steps = []
        for i in range(len(trajectory)):
            row = trajectory.iloc[i]
            steps.append(
                {
                    "step": i,
                    "coverage": float(row["coverage"]),
                    "density": float(row["density"]),
                    "mass": float(row["mass"]),
                    "n": int(row["n"]),
                    "k": int(row["k"]),
                    "n_restricted": int(row["res_dim"]),
                    "limits": _limits(box.box_lims[i]),
                }
            )
        result["cases"].append(
            {
                "name": case["name"],
                "alpha": case["alpha"],
                "mass_min": case["mass_min"],
                "x": {c: x[c].tolist() for c in x.columns},
                "y": [int(v) for v in case["y"]],
                "steps": steps,
            }
        )
    target.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {target} ({len(result['cases'])} cases)", file=sys.stderr)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
