"""The key of the cache `era5_reduction` is pinned (COMMAND 134, item 1; OQ-078, L-068; message corrected in COMMAND 138).

The year checkpoints and the annual-maximum products of ERA5 carry `cache_code("era5_reduction")`. A change of this key makes a rebuild of the reduction worth doing: it
is recomputed locally from the hourly year files (kept in `raw/era5`, copied back from the archive in COMMAND 138; no download), about 27 minutes of computing in all
(estimate of COMMAND 133: BRA 12.5 min, IND 13 min, PRT 1.5 min). This test fails when the key changes, so the change is made knowingly. The pin stays.
"""

from __future__ import annotations

import pytest

from geofrea.core.cache_code import cache_code

PINNED_ERA5_REDUCTION = "03a922fda2d1a3370ee69f1fe5934f80cbf878b0a68edca9e829eb33e17c0392"


@pytest.mark.unit
def test_the_key_of_the_era5_reduction_cache_has_not_changed():
    now = cache_code("era5_reduction")
    assert now == PINNED_ERA5_REDUCTION, (
        "the key of the cache `era5_reduction` changed (the code of `data_acquisition.fetchers.era5` or of a module it imports): "
        "the reduction of the ERA5 gust would have to be rebuilt, which is a LOCAL recompute of about 27 min of computation "
        "(estimate of COMMAND 133; the hourly year files are in `raw/era5`, see L-068 and the README), not a download. "
        "If the change is wanted, say so in OQ-078 / L-068, then update PINNED_ERA5_REDUCTION to the new key: "
        f"{now}"
    )
