"""Move the recorded content hash of Parquet artifacts from the kind `parquet:` to `parquet2:` with a proof (COMMAND 134, A-02, OQ-084).

usage: python scripts/restamp_parquet2.py [ISO3 ...] [--keys K1,K2] [--snapshot DIR] [--apply]

Dry run by default: it prints, for every entry, what it checked and the hash it would write, and writes nothing. With `--apply` it writes, per country, the new
`content_sha256` (kind `parquet2:`) and a `hash_restamps` record (manifest schema 2.12), after a copy of the manifest beside it (`manifest.json.before_restamp`).

An entry is restamped only when ALL of this holds, and the script fails closed (exit 1, nothing written for any country) when one thing fails:

1. the entry has a `parquet:` content hash (an entry that is already `parquet2:` is reported and left);
2. the file on disk is the registered one: the SHA-256 of its bytes is the recorded `sha256`, and its `parquet:` content hash is the recorded one;
3. a reference copy exists at the same relative path under `--snapshot` (default `<data root>/work/ref133_snapshot`) and the value of the file on disk equals the
   value of that copy, column by column and row by row, the Arrow type ignored (`string` and `large_string` are the same value; floats compare equal when both are
   NaN or bitwise equal as numbers);
4. the new hash is `content_hash(file, "parquet2")` of the file on disk.

With `--proof-manifest DIR` (COMMAND 178, authorised by the author) the reference copy of item 3 is replaced by the manifest of the same country saved before the
round, `DIR/manifest_<ISO>.json`: the entry must exist there with the same key and the SAME recorded `parquet:` content hash as today. That hash includes the Arrow
type and the value of every column, so the file on disk is the one that manifest described (same type, same value); the proof records `compared: "hash"` and the
SHA-256 of that manifest as the reference. Items 1, 2 and 4 stand as above. `--all-parquet` selects every entry still hashed with `parquet:` (default: `--keys`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core import paths as core_paths
from geofrea.core.content_hash import content_hash
from geofrea.core.scale import manifest_file_name

DEFAULT_KEYS = ("potential_aggregates_solar", "potential_aggregates_wind")
SCHEMA = "2.12"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _plain(arrow_type: pa.DataType) -> pa.DataType:
    """The type with the `large_` forms and dictionaries replaced by the plain ones (the value, not the layout)."""
    if pa.types.is_large_string(arrow_type):
        return pa.string()
    if pa.types.is_large_binary(arrow_type):
        return pa.binary()
    if pa.types.is_dictionary(arrow_type):
        return _plain(arrow_type.value_type)
    if pa.types.is_large_list(arrow_type) or pa.types.is_list(arrow_type):
        return pa.list_(_plain(arrow_type.value_type))
    return arrow_type


def values_equal(a: Path, b: Path) -> tuple[bool, str, int, int]:
    """(equal, reason, rows, columns): the two Parquet files hold the same values, the Arrow type ignored."""
    fa, fb = pq.ParquetFile(a), pq.ParquetFile(b)
    na, nb = fa.schema_arrow.names, fb.schema_arrow.names
    if na != nb:
        return False, f"columns differ: {na} vs {nb}", fa.metadata.num_rows, len(na)
    if fa.metadata.num_rows != fb.metadata.num_rows:
        return False, f"rows differ: {fa.metadata.num_rows} vs {fb.metadata.num_rows}", fa.metadata.num_rows, len(na)
    for name in na:
        ca = fa.read(columns=[name]).column(0).combine_chunks()
        cb = fb.read(columns=[name]).column(0).combine_chunks()
        ca, cb = ca.cast(_plain(ca.type)), cb.cast(_plain(cb.type))
        if pa.types.is_floating(ca.type) and pa.types.is_floating(cb.type):
            xa, xb = ca.to_numpy(zero_copy_only=False), cb.to_numpy(zero_copy_only=False)
            same = np.array_equal(xa.astype("float64"), xb.astype("float64"), equal_nan=True)
        else:
            same = ca.equals(cb)
        if not same:
            return False, f"column {name!r} has other values", fa.metadata.num_rows, len(na)
    return True, "", fa.metadata.num_rows, len(na)


def check_entry(iso: str, key: str, entry: dict, snapshot: Path, root: Path) -> dict:
    """What the script finds for one entry: `ok` with the proof fields, or `problem` with the reason (and `skip` for an entry that is already parquet2:)."""
    out: dict = {"iso": iso, "key": key}
    recorded = entry.get("content_sha256") or ""
    if recorded.startswith("parquet2:"):
        return {**out, "skip": "already parquet2:"}
    if not recorded.startswith("parquet:"):
        return {**out, "problem": f"the recorded content hash is {recorded[:12]!r}, not of kind parquet:"}
    rel = entry["path"]["rel"]
    path = root / rel
    if not path.is_file():
        return {**out, "problem": f"{rel} is absent"}
    file_sha = _sha256(path)
    if file_sha != entry["sha256"]:
        return {**out, "problem": "the bytes of the file are not the registered ones (sha256 differs from the manifest)"}
    if content_hash(path, "parquet") != recorded:
        return {**out, "problem": "the parquet: content hash of the file is not the recorded one"}
    ref = snapshot / rel
    if not ref.is_file():
        return {**out, "problem": f"no reference copy at {ref}"}
    equal, why, rows, cols = values_equal(path, ref)
    if not equal:
        return {**out, "problem": f"value differs from the reference copy: {why}"}
    return {
        **out,
        "ok": True,
        "rel": rel,
        "previous": recorded,
        "new": content_hash(path, "parquet2"),
        "file_sha256": file_sha,
        "reference_copy": str(ref.relative_to(root)) if root in ref.parents else str(ref),
        "reference_copy_sha256": _sha256(ref),
        "n_rows": rows,
        "n_columns": cols,
    }


def check_entry_by_hash(iso: str, key: str, entry: dict, before: dict | None, before_path: Path, root: Path) -> dict:
    """Like `check_entry`, with the manifest saved before the round as the reference: the same entry with the same `parquet:` content hash (type and value)."""
    out: dict = {"iso": iso, "key": key}
    recorded = entry.get("content_sha256") or ""
    if recorded.startswith("parquet2:"):
        return {**out, "skip": "already parquet2:"}
    if not recorded.startswith("parquet:"):
        return {**out, "problem": f"the recorded content hash is {recorded[:12]!r}, not of kind parquet:"}
    rel = entry["path"]["rel"]
    path = root / rel
    if not path.is_file():
        return {**out, "problem": f"{rel} is absent"}
    file_sha = _sha256(path)
    if file_sha != entry["sha256"]:
        return {**out, "problem": "the bytes of the file are not the registered ones (sha256 differs from the manifest)"}
    if content_hash(path, "parquet") != recorded:
        return {**out, "problem": "the parquet: content hash of the file is not the recorded one"}
    previous = None if before is None else before["artifacts"].get(key)
    if previous is None:
        return {**out, "problem": f"no entry {key!r} in the manifest saved before the round ({before_path})"}
    if previous.get("content_sha256") != recorded:
        return {**out, "problem": "the parquet: content hash differs from the one in the manifest saved before the round"}
    meta = pq.ParquetFile(path).metadata
    return {
        **out,
        "ok": True,
        "rel": rel,
        "previous": recorded,
        "new": content_hash(path, "parquet2"),
        "file_sha256": file_sha,
        "reference_copy": f"manifest:{before_path.name}",
        "reference_copy_sha256": _sha256(before_path),
        "compared": "hash",
        "n_rows": meta.num_rows,
        "n_columns": meta.num_columns,
    }


def schema_after_restamp(current: str | None) -> str:
    """The schema a manifest has after a restamp: 2.12 at least (the first with `hash_restamps`), never lower than the one it already has."""

    def key(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))

    return max(current or SCHEMA, SCHEMA, key=key)


def proof(found: dict, when: str) -> dict:
    body = {
        "artifact_key": found["key"],
        "restamped_at": when,
        "previous_content_sha256": found["previous"],
        "new_content_sha256": found["new"],
        "file_sha256": found["file_sha256"],
        "reference_copy": found["reference_copy"],
        "reference_copy_sha256": found["reference_copy_sha256"],
        "compared": found.get("compared", "value"),
        "n_rows": found["n_rows"],
        "n_columns": found["n_columns"],
    }
    body["proof_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("countries", nargs="*", default=["PRT", "IND", "BRA"])
    parser.add_argument("--keys", default=",".join(DEFAULT_KEYS))
    parser.add_argument("--snapshot", default=None, help="folder of the reference copy (default: <data root>/work/ref133_snapshot)")
    parser.add_argument("--proof-manifest", default=None, help="folder with manifest_<ISO>.json saved before the round: the reference is the same `parquet:` hash there, not a copy of the file")
    parser.add_argument("--all-parquet", action="store_true", help="every entry of the country still hashed with `parquet:` (default: --keys)")
    parser.add_argument("--apply", action="store_true", help="write the manifests (default: dry run)")
    args = parser.parse_args()
    outputs = core_paths.outputs_dir()
    root = outputs.parent
    snapshot = Path(args.snapshot) if args.snapshot else root / "work" / "ref133_snapshot"
    keys = [k for k in args.keys.split(",") if k]
    findings: list[dict] = []
    manifests: dict[str, tuple[Path, dict]] = {}
    for iso in args.countries:
        path = outputs / iso / manifest_file_name()
        data = json.loads(path.read_text(encoding="utf-8"))
        manifests[iso] = (path, data)
        before_path = Path(args.proof_manifest) / f"manifest_{iso}.json" if args.proof_manifest else None
        before = json.loads(before_path.read_text(encoding="utf-8")) if before_path is not None and before_path.is_file() else None
        country_keys = [k for k, a in data["artifacts"].items() if (a.get("content_sha256") or "").startswith("parquet:")] if args.all_parquet else keys
        for key in country_keys:
            entry = data["artifacts"].get(key)
            if entry is None:
                findings.append({"iso": iso, "key": key, "problem": "no such artifact in the manifest"})
            elif before_path is not None:
                findings.append(check_entry_by_hash(iso, key, entry, before, before_path, root))
            else:
                findings.append(check_entry(iso, key, entry, snapshot, root))
    for f in findings:
        state = "OK" if f.get("ok") else ("SKIP" if f.get("skip") else "PROBLEM")
        extra = f"{f['previous'][:20]} -> {f['new'][:21]}, rows {f['n_rows']}, columns {f['n_columns']}" if f.get("ok") else f.get("skip") or f.get("problem")
        print(f"{f['iso']} {f['key']}: {state}: {extra}")
    problems = [f for f in findings if f.get("problem")]
    if problems:
        print(f"FAIL CLOSED: {len(problems)} entry(ies) cannot be restamped; nothing was written.")
        return 1
    todo = [f for f in findings if f.get("ok")]
    if not args.apply:
        print(f"dry run: {len(todo)} entry(ies) would be restamped; run again with --apply.")
        return 0
    when = datetime.now(UTC).isoformat(timespec="seconds")
    for iso, (path, data) in manifests.items():
        mine = [f for f in todo if f["iso"] == iso]
        if not mine:
            continue
        shutil.copy2(path, path.with_name(path.name + ".before_restamp"))
        for f in mine:
            data["artifacts"][f["key"]]["content_sha256"] = f["new"]
            data.setdefault("hash_restamps", []).append(proof(f, when))
        data["schema_version"] = schema_after_restamp(data.get("schema_version"))
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        print(f"{iso}: manifest written ({len(mine)} restamped), schema {SCHEMA}, copy at {path.name}.before_restamp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
