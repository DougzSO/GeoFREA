"""The key of the cache `era5_reduction` is pinned (COMMAND 134, item 1; OQ-078, L-068).

The year checkpoints and the annual-maximum products of ERA5 carry `cache_code("era5_reduction")`. The hourly year files they come from are no longer on disk
for BRA, PRT and the first IND product, so a change of this key makes a rebuild of the reduction depend on a new download from the CDS (a queue of 0 to
17 h per job, a request refused above two years of hourly fg10). This test fails when the key changes, so the change is made knowingly.
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
        "rebuilding the reduction of the ERA5 gust needs the hourly year files, which are not on disk for BRA, PRT and the original IND, "
        "so it means a RE-DOWNLOAD from the CDS (queue of 0 to 17 h per job, two years of hourly fg10 per request, days in all). "
        "If the change is wanted, say so in OQ-078 / L-068, then update PINNED_ERA5_REDUCTION to the new key: "
        f"{now}"
    )
