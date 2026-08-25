"""WRI Global Power Plant Database fetcher.

Verified live 2026-08-24/25 (see docs/DECISIONS.md same dates): a
single unauthenticated GET against a GitHub-hosted CSV returns the
whole database — no pagination, no tiling, no auth. The cheapest fetch
of all 14 layers.

Pinned commit, NOT `master` (see PINNED_COMMIT_SHA below for why) —
the one hard requirement from this stage's instructions.

This is a genuinely GLOBAL dataset (see data_quality_audit's existing
`country_specific=False` classification for `power_plants` in
phase.py's _LAYER_REGISTRY, unchanged by this stage) — fetched once,
not once per country. `fetch_power_plants()` is idempotent: if the
file already exists on disk, it's returned without a new network call,
so re-running acquisition for a second country (e.g. BRA after PRT)
doesn't re-download ~12 MB for no reason.
"""

from __future__ import annotations

import logging
from pathlib import Path

from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.power_plants")

# The WRI/global-power-plant-database repo has been unmaintained since
# early 2022 (last commit "Update version to 1.3.0, announce project
# status ... This may be a final commit to this project" — verified by
# reading the commit message directly via the GitHub API 2026-08-24).
# v1.3.0 itself was never tagged as a GitHub release (only v1.0.0 and
# v1.1.0 exist as tags — v1.1.0 is a much smaller, years-out-of-date
# 2018 snapshot, not the current database). Pinning to this specific
# commit SHA — rather than `master` — is the only way to get the
# actual current (v1.3.0) database content AND have it stop moving
# under us if the repo is ever touched again. Verified 2026-08-24 that
# this SHA's raw CSV is byte-identical to `master`'s at the time of
# verification (same Content-Length and ETag).
PINNED_COMMIT_SHA = "7a91cfbb2a4e272597acbc00506d61fc1ec73b3d"

_CSV_URL = (
    "https://raw.githubusercontent.com/wri/global-power-plant-database/"
    f"{PINNED_COMMIT_SHA}/output_database/global_power_plant_database.csv"
)


def fetch_power_plants(outputs_dir: Path) -> Path | None:
    """Download the Global Power Plant Database CSV, once.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
            The file is saved under `outputs_dir/_global/raw/` — this
            is a global (not per-country) dataset, so it does not live
            under any single country's output tree.

    Returns:
        Path to the saved CSV, or None if the download failed (logged,
        not raised — one failed layer must not abort the whole
        acquisition phase, matching data_quality_audit's own
        established pattern for degrading gracefully per layer).
    """
    dest_dir = Path(outputs_dir) / "_global" / "raw"
    dest_path = dest_dir / "global_power_plant_database.csv"

    if dest_path.exists():
        return dest_path

    try:
        resp = get_with_retry(_CSV_URL, timeout=60)
    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch power plants database: %s", exc)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("Power plants database saved: %s", dest_path)
    return dest_path
