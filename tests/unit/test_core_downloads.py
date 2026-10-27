"""State of a download that writes to a temporary name first."""

from __future__ import annotations

import pytest

from geofrea.core.downloads import is_complete_download


@pytest.mark.unit
def test_is_complete_download_distinguishes_partial_from_complete(tmp_path):
    final_path = tmp_path / "a.nc"
    tmp_download_path = tmp_path / "a.part.nc"

    assert is_complete_download(final_path, tmp_download_path) == "absent"

    tmp_download_path.write_bytes(b"partial-bytes")
    assert is_complete_download(final_path, tmp_download_path) == "partial"

    tmp_download_path.rename(final_path)
    assert is_complete_download(final_path, tmp_download_path) == "complete"
