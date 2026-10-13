"""The only door F8 reads through: the artifacts a manifest registers (M-F8-01; D-F8-001).

The reader lives in `geofrea.core.artifact_reader` because the support phase `cross_country_h4` reads manifests through it too; F8 imports it
from here.
"""

from __future__ import annotations

from geofrea.core.artifact_reader import (
    ArtifactReader,
    MissingArtifactError,
    ThesisInputError,
    sha256_of,
)

__all__ = ["ArtifactReader", "MissingArtifactError", "ThesisInputError", "sha256_of"]
