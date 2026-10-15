"""Rewrite the `.key` sidecars of the vector clip caches from the old identity (path, size, mtime, polygon) to the content key (OQ-026).

A cache is migrated only if it was current under the old key: its source exists at the recorded path with the recorded size and mtime. The
new key is `core.geo_utils.clip_cache_key` computed from the same source and the polygon hash stored in the old key, so the cache is not
recomputed; a cache that was already stale or whose source is gone is reported and left alone.

Run: `python scripts/migrate_clip_cache_keys.py [--apply]` (a dry run without `--apply`). Reads and writes only under GEOFREA_DATA_DIR/interim and GEOFREA_DATA_DIR/outputs (the F1b clip caches in `outputs/<ISO3>/processed`).
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.cache_key import cache_key
from geofrea.core.geo_utils import (
    CLIP_ALGORITHM_VERSION,
    _clip_hash_memo,
    clip_source_files,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def new_key_from_old(old: str, memo) -> tuple[str | None, str]:
    """`(new key or None, reason)` for an old-format key."""
    parts = old.split("|")
    if len(parts) != 4:
        return None, "not an old-format key (already migrated?)"
    source, size, mtime, polygon = Path(parts[0]), int(parts[1]), int(parts[2]), parts[3]
    if not source.is_file():
        return None, f"the source {source} is absent"
    st = source.stat()
    if st.st_size != size or st.st_mtime_ns != mtime:
        return None, "the cache was already stale under the old key (source size or mtime changed)"
    return cache_key(
        CLIP_ALGORITHM_VERSION, clip_source_files(source), {"polygon": polygon}, memo=memo
    ), "ok"


def main(argv: list[str]) -> int:
    load_dotenv(REPO_ROOT / ".env", override=False)
    apply = "--apply" in argv
    memo = _clip_hash_memo()
    root = core_paths.data_root()
    bases = [root / "interim", root / "outputs"]
    found = migrated = problems = 0
    key_files = sorted(f for base in bases if base.is_dir() for f in base.rglob("*.key"))
    for key_file in key_files:
        if key_file.name.endswith(".cachekey"):
            continue
        found += 1
        old = key_file.read_text(encoding="utf-8")
        new, reason = new_key_from_old(old, memo)
        rel = key_file.relative_to(root)
        if new is None:
            if "already migrated" in reason:
                print(f"[skip] {rel}: {reason}")
            else:
                problems += 1
                print(f"[PROBLEM] {rel}: {reason}")
            continue
        migrated += 1
        print(f"[{'write' if apply else 'would write'}] {rel}")
        if apply:
            key_file.write_text(new, encoding="utf-8")
    print(f"{found} key files; {migrated} migrated; {problems} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
