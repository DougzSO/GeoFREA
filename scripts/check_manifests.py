"""Check that the manifests of the countries are still valid: every registered artifact exists and its content hash matches (COMMAND 82).

usage: python scripts/check_manifests.py [ISO ...] [--bytes] [--out report.json]

For each artifact of `outputs/<ISO>/manifest.json` the file is resolved (`path.root` `data` is GEOFREA_DATA_DIR) and must exist; its canonical content hash
(`core.content_hash`) must equal `content_sha256`, or, for an entry without one, the SHA-256 of its bytes must equal `sha256`. `--bytes` also compares the byte hash
of every entry. The exit code is 1 when any artifact is missing or differs. Nothing is written except `--out`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.content_hash import content_hash  # noqa: E402
from geofrea.core.paths import data_root  # noqa: E402


def _bytes_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def check_country(iso: str, data_dir: Path, by_bytes: bool) -> dict:
    manifest = json.loads((data_dir / "outputs" / iso / "manifest.json").read_text(encoding="utf-8"))
    problems: list[dict] = []
    entries = manifest.get("artifacts", {})
    for key, entry in entries.items():
        where = entry.get("path", {})
        if where.get("root") != "data":
            problems.append({"key": key, "problem": f"root {where.get('root')!r} not checked"})
            continue
        path = data_dir / where["rel"]
        if not path.is_file():
            problems.append({"key": key, "path": where["rel"], "problem": "missing"})
            continue
        expected = entry.get("content_sha256")
        if expected:
            if content_hash(path) != expected:
                problems.append({"key": key, "path": where["rel"], "problem": "content hash differs"})
        elif _bytes_sha(path) != entry.get("sha256"):
            problems.append({"key": key, "path": where["rel"], "problem": "byte hash differs (no content hash registered)"})
        if by_bytes and entry.get("sha256") and _bytes_sha(path) != entry["sha256"]:
            problems.append({"key": key, "path": where["rel"], "problem": "byte hash differs"})
    return {"country": iso, "artifacts": len(entries), "problems": problems, "valid": not problems}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("countries", nargs="*", default=["PRT", "IND", "BRA"])
    parser.add_argument("--bytes", action="store_true", help="also compare the byte hash of every entry")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    data_dir = data_root()
    reports = [check_country(iso, data_dir, args.bytes) for iso in args.countries]
    for report in reports:
        status = "VALID" if report["valid"] else f"INVALID ({len(report['problems'])} problems)"
        print(f"{report['country']}: {report['artifacts']} artifacts, {status}")
        for problem in report["problems"][:20]:
            print("   ", problem)
    if args.out:
        args.out.write_text(json.dumps(reports, indent=1), encoding="utf-8")
    return 0 if all(r["valid"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
