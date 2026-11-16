"""Print the digests of the pre-registered subset of the configuration and the text of the message of the tag `prereg-v1` (DEC-081, COMMAND 155B).

Read-only: it creates no tag, writes no file and changes nothing. The tag is created once by the author at COMMAND 162T, on the commit that fills the subset,
with the text this script prints:

    python scripts/preregistration_digest.py                    # the registered countries (those that are not synthetic)
    python scripts/preregistration_digest.py --countries PRT IND BRA
    python scripts/preregistration_digest.py --check            # compares the live subset with the tag `prereg-v1` (exit 1 on a difference or no tag)

The subset and the way the digest is computed are in `geofrea.core.preregistration`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core import preregistration as prereg
from geofrea.core.config_fingerprint import CONFIG_FILES, DiskConfigSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--countries", nargs="+", help="default: every country of parameters.json that is not synthetic")
    parser.add_argument("--config-dir", type=Path, default=REPO / "config")
    parser.add_argument("--repo", type=Path, default=REPO, help="the git repository whose tag is read (default: this one)")
    parser.add_argument("--check", action="store_true", help="compare the live subset with the tag instead of printing the message")
    args = parser.parse_args(argv)

    source = DiskConfigSource({key: args.config_dir / name for key, name in CONFIG_FILES.items()}, args.config_dir / "turbines")
    countries = args.countries or prereg.registered_countries(source)
    if args.check:
        conflict = prereg.tag_conflict(countries, source, args.repo)
        if conflict is None:
            print(f"no tag {prereg.TAG_NAME} in {args.repo}: the subset is a draft")
            return 1
        if conflict:
            print(f"the subset differs from the tag {prereg.TAG_NAME}:")
            print("\n".join(f"  {line}" for line in conflict))
            return 1
        print(f"the subset of {', '.join(countries)} is the one registered in the tag {prereg.TAG_NAME}")
        return 0

    digests = prereg.live_digests(countries, source)
    print(f"aggregate  {digests.aggregate}")
    for iso, digest in digests.countries.items():
        print(f"{iso:<10} {digest}")
    print("\n--- message of the tag (git tag -a prereg-v1 -F <file>); nothing was created ---")
    print(prereg.tag_message(digests), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
