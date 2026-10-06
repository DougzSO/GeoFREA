"""Refreeze the V-01 regression fixtures (F1, F2a, E1-E3) from the current code.

Run only with Douglas's authorization (METHODOLOGY V-01); the authorization and the resulting counts go in
the phase record. Writes tests/fixtures/v01/zzz.npz and tests/fixtures/v01/zzz_summary.json.

    python scripts/freeze_v01_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "src")]

from tests.regression.v01_run import run_zzz  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        arrays = run_zzz(Path(tmp))
    out = REPO_ROOT / "tests" / "fixtures" / "v01"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "zzz.npz", **{k.replace("/", "__"): v for k, v in arrays.items()})
    summary = {
        k: {"shape": list(v.shape), "min": float(v.min()), "max": float(v.max()), "sum": float(v.sum())}
        for k, v in arrays.items()
    }
    (out / "zzz_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"froze {len(arrays)} layers -> {out}")


if __name__ == "__main__":
    main()
