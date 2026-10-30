"""Compare every PNG under two directories by decoded pixels (COMMAND 77, items 5 and h): same relative paths, same size, same RGBA array.

usage: python scripts/proofs/compare_png_dirs.py OLD_DIR NEW_DIR [--out file.json]

The text chunks of a PNG (date, run id) are not compared, only the pixels, as the item asks. Exit code 0 only when every PNG of either side has an
identical partner on the other.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def pixel_digest(path: Path) -> str:
    array = np.asarray(Image.open(path).convert("RGBA"))
    return hashlib.sha256(array.tobytes() + str(array.shape).encode()).hexdigest()


def compare(old: Path, new: Path) -> dict:
    a = {p.relative_to(old).as_posix(): p for p in old.rglob("*.png")}
    b = {p.relative_to(new).as_posix(): p for p in new.rglob("*.png")}
    rows = {}
    for name in sorted(set(a) | set(b)):
        ha = pixel_digest(a[name]) if name in a else None
        hb = pixel_digest(b[name]) if name in b else None
        rows[name] = {"equal": ha is not None and ha == hb}
    return {"n_png": len(rows), "n_equal": sum(r["equal"] for r in rows.values()), "different": [n for n, r in rows.items() if not r["equal"]]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    result = compare(args.old, args.new)
    result["equal"] = result["n_png"] > 0 and not result["different"]
    if args.out:
        args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"{result['n_equal']} of {result['n_png']} PNG equal by pixels; different: {result['different'][:5]}")
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
