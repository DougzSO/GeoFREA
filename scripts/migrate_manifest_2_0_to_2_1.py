"""Single-use migration script: convert manifest.json from schema 2.0 to 2.1.

This script runs as part of COMMAND E5b (data migration E5b action 11):
converts each manifest.json and every path embedded in its artifact JSON
to use StoredPath (root + relative) instead of absolute paths. Performs
sha256 re-verification at the new location to ensure data integrity.

Usage:
    python scripts/migrate_manifest_2_0_to_2_1.py <manifest_json_path>

Schema changes:
  - 2.0: ArtifactEntry.path is a string (absolute Windows path)
  - 2.1: ArtifactEntry.path is StoredPath (root + posix-relative path)
  - Manifest schema_version bumped from "2.0" to "2.1"

On any sha256 mismatch, the script stops and reports the affected file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

from geofrea.core.paths import MissingPathEnvironmentError, to_stored_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_manifest")

_HASH_CHUNK_SIZE = 8 * 1024 * 1024


def _compute_sha256(path: Path) -> str:
    """Compute sha256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def migrate_manifest(manifest_path: Path) -> None:
    """Migrate a single manifest from schema 2.0 to 2.1.

    Args:
        manifest_path: Path to the manifest.json file to migrate.

    Raises:
        ValueError: If manifest is not schema 2.0, or if a sha256 mismatch
            is detected at the new location.
        MissingPathEnvironmentError: If required env vars are not set.
    """
    manifest_path = manifest_path.resolve()
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")

    logger.info("Loading manifest: %s", manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    # Check schema version
    if data.get("schema_version") != "2.0":
        raise ValueError(
            f"Expected schema_version '2.0', got {data.get('schema_version')}. "
            "This manifest is either already migrated or uses an unsupported version."
        )

    logger.info("Converting artifact paths from absolute to StoredPath...")
    migrated_artifacts: dict = {}

    for key, artifact_data in data.get("artifacts", {}).items():
        # Convert the path field from absolute string to StoredPath
        old_path_str = artifact_data["path"]
        old_path = Path(old_path_str)

        try:
            stored_path = to_stored_path(old_path)
            logger.info("  %s: %s -> %s", key, old_path_str, stored_path)

            # Re-verify sha256 at new location
            resolved_new_path = stored_path.resolve()
            if not resolved_new_path.exists():
                raise ValueError(f"File not found at new location: {resolved_new_path}")

            actual_sha256 = _compute_sha256(resolved_new_path)
            expected_sha256 = artifact_data["sha256"]

            if actual_sha256 != expected_sha256:
                raise ValueError(
                    f"SHA256 mismatch for {key}: expected {expected_sha256}, "
                    f"got {actual_sha256} at {resolved_new_path}"
                )

            # Update artifact entry with StoredPath
            artifact_data["path"] = stored_path.model_dump()
            migrated_artifacts[key] = artifact_data

        except MissingPathEnvironmentError as e:
            logger.error("Missing environment variable: %s", e.var_name)
            raise

    data["artifacts"] = migrated_artifacts
    data["schema_version"] = "2.1"

    # Write migrated manifest back to disk
    logger.info("Writing migrated manifest...")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info("Migration complete: %s", manifest_path)


def main() -> None:
    """Entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/migrate_manifest_2_0_to_2_1.py <manifest_json_path>")
        sys.exit(1)

    manifest_path = Path(sys.argv[1])
    try:
        migrate_manifest(manifest_path)
        logger.info("SUCCESS")
        sys.exit(0)
    except (ValueError, MissingPathEnvironmentError, OSError) as e:
        logger.error("FAILED: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
