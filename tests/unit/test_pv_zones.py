"""PV thermal zones and the degradation rate of each zone (COMMAND 83, Group 3): classification limits, nearest land point, pooling of thin zones."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from geofrea.core.pv_zones import (
    NO_ZONE,
    ZONE_LIMITS_C,
    ZoneError,
    ZoneSource,
    cap_zone,
    classify_zone,
    derive_zone_rates,
    nearest_land_zone,
    zone_degradation_bounds,
    zones_for_cells,
)

# -- classification with synthetic limits, extremes included -------------------------------------------


@pytest.mark.unit
def test_the_limits_are_the_nine_of_karin_et_al():
    assert ZONE_LIMITS_C == (14.0, 19.0, 24.0, 29.0, 34.0, 39.0, 44.0, 49.0, 54.0)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("t", "zone"),
    [
        (-30.0, 1),  # far below the first limit
        (13.999, 1),
        (14.0, 2),  # a value on a limit belongs to the hotter zone
        (18.999, 2),
        (19.0, 3),
        (28.0, 4),
        (33.999, 5),
        (44.0, 8),
        (53.999, 9),
        (54.0, 10),  # on the last limit
        (80.0, 10),  # far above the last limit
    ],
)
def test_classify_zone_at_the_limits_and_the_extremes(t, zone):
    assert int(classify_zone(t)[0]) == zone


@pytest.mark.unit
def test_classify_zone_gives_no_zone_for_nan_and_returns_int8():
    out = classify_zone(np.array([20.0, np.nan, 60.0]))
    assert out.dtype == np.int8 and out.tolist() == [3, NO_ZONE, 10]


@pytest.mark.unit
def test_cap_zone_gives_t7_to_the_hotter_zones_and_keeps_no_zone():
    assert cap_zone(np.array([1, 6, 7, 8, 10, 0])).tolist() == [1, 6, 7, 7, 7, 0]


# -- nearest land point -------------------------------------------------------------------------------


@pytest.mark.unit
def test_a_coastal_cell_takes_the_nearest_land_point_and_a_far_cell_has_no_zone():
    point_lat = np.array([0.0, 0.0, 10.0])
    point_lon = np.array([0.0, 0.25, 0.0])
    point_zone = np.array([3, 5, 9], dtype="int8")
    # the first cell is 0.05 degree (about 5.5 km) west of the first point; the second is in the sea 30 km from the second point
    lat = np.array([0.0, 0.0, 40.0])
    lon = np.array([-0.05, 0.25 + 0.27, 0.0])
    zone, distance = nearest_land_zone(lat, lon, point_lat, point_lon, point_zone, max_distance_km=50.0)
    assert zone[0] == 3 and distance[0] == pytest.approx(5.56, abs=0.1)
    assert zone[1] == 5 and distance[1] == pytest.approx(30.0, abs=0.5)
    assert zone[2] == NO_ZONE and distance[2] > 3000.0  # beyond the declared limit
    tighter, _ = nearest_land_zone(lat, lon, point_lat, point_lon, point_zone, max_distance_km=20.0)
    assert tighter.tolist() == [3, NO_ZONE, NO_ZONE]


@pytest.mark.unit
def test_nearest_land_zone_is_exact_across_the_antimeridian_and_refuses_bad_inputs():
    zone, distance = nearest_land_zone(
        np.array([0.0]), np.array([179.99]), np.array([0.0, 0.0]), np.array([-179.99, 100.0]),
        np.array([4, 6], dtype="int8"), 100.0,
    )  # fmt: skip
    assert zone[0] == 4 and distance[0] == pytest.approx(2.22, abs=0.05)
    with pytest.raises(ZoneError, match="positive"):
        nearest_land_zone(np.array([0.0]), np.array([0.0]), np.array([0.0]), np.array([0.0]), np.array([1], dtype="int8"), 0.0)
    with pytest.raises(ZoneError, match="no PVCZ points"):
        nearest_land_zone(np.array([0.0]), np.array([0.0]), np.array([]), np.array([]), np.array([], dtype="int8"), 50.0)


@pytest.mark.unit
def test_zones_for_cells_read_the_csv_and_shift_the_package_zone_to_t1_to_t10(tmp_path):
    csv = tmp_path / "pvcz.csv"
    pd.DataFrame(
        {"lat": [0.0, 0.0], "lon": [0.0, 1.0], "T_equiv_rack_1p1eV": [10.0, 40.0], "T_equiv_rack_1p1eV_zone": [0.0, 6.0]}
    ).to_csv(csv, index=False)
    zones = zones_for_cells(np.array([0.0, 0.0]), np.array([0.01, 0.99]), ZoneSource(csv, 50.0))
    assert zones.tolist() == [1, 7]  # the package numbers zones 0 to 9, the layer 1 to 10
    with pytest.raises(FileNotFoundError, match="export_pvcz_csv"):
        zones_for_cells(np.array([0.0]), np.array([0.0]), ZoneSource(tmp_path / "absent.csv", 50.0))


# -- the rate of each zone ----------------------------------------------------------------------------


def _fleet(zone_to_plr):
    rows = [{"pv_climate_zone": z, "plr_median": v} for z, values in zone_to_plr.items() for v in values]
    return pd.DataFrame(rows)


@pytest.mark.unit
def test_zone_rates_are_the_positive_median_and_mean_of_the_loss_rate_per_zone():
    fleet = _fleet({f"T{z}": [-0.5 * z] * 30 + [-0.5 * z - 0.3] * 30 for z in range(1, 8)})
    rates = {r.zone: r for r in derive_zone_rates(fleet, min_systems=20)}
    assert set(rates) == set(range(1, 8))
    for z in range(1, 8):
        assert rates[z].n == 60 and rates[z].merged_with is None
        assert rates[z].median == pytest.approx((0.5 * z + 0.15) / 100.0)  # the median of two equal halves
        assert rates[z].mean == pytest.approx((0.5 * z + 0.15) / 100.0)


@pytest.mark.unit
def test_a_zone_with_too_few_systems_is_pooled_with_the_nearest_zone_and_an_empty_one_too():
    fleet = _fleet({"T3": [-0.4] * 50, "T4": [-0.9] * 30, "T5": [-1.0] * 3, "T6": [-0.8] * 25})
    rates = {r.zone: r for r in derive_zone_rates(fleet, min_systems=20)}
    # T1 and T2 are empty and join T3; T5 (3 systems) joins its nearest zone, T4 or T6 at the same distance: the colder one
    assert rates[1].n == rates[2].n == rates[3].n == 50
    assert rates[1].median == rates[3].median == pytest.approx(0.004)
    assert rates[4].n == rates[5].n == 33 and rates[5].merged_with == 4
    assert rates[4].median == pytest.approx(np.median([0.009] * 30 + [0.010] * 3))
    assert rates[6].n == rates[7].n == 25  # T7 is empty and joins T6
    assert rates[7].median == rates[6].median == pytest.approx(0.008)


@pytest.mark.unit
def test_the_sampling_bounds_run_from_the_median_to_the_mean_and_never_below_the_median():
    assert zone_degradation_bounds({"median": 0.004, "mean": 0.0051}) == (0.004, 0.0051)
    assert zone_degradation_bounds({"median": 0.0086, "mean": 0.0078}) == (0.0086, 0.0086)


@pytest.mark.unit
def test_the_derivation_refuses_a_table_without_the_columns_or_without_valid_rows():
    with pytest.raises(ZoneError, match="plr_median"):
        derive_zone_rates(pd.DataFrame({"pv_climate_zone": ["T1"]}), 20)
    with pytest.raises(ZoneError, match="no row"):
        derive_zone_rates(pd.DataFrame({"pv_climate_zone": [None], "plr_median": [np.nan]}), 20)


@pytest.mark.unit
def test_the_recorded_zone_rates_come_from_the_fleet_and_the_cool_and_hot_medians_are_near_jordan_et_al():
    """The values in parameters.json are those of `scripts/derive_pv_degradation_by_zone.py` on the public fleet file (0.48 and 0.88 %/yr)."""
    from geofrea.core.config_loader import load_parameters
    from tests.unit.test_lcoe_connection import PARAMETERS

    zones = load_parameters(PARAMETERS).countries["BRA"].technologies.solar.degradation_by_zone
    assert zones.min_systems == 20 and not zones.synthetic
    cool, hot = zones.zones["T1"].median * 100.0, zones.zones["T7"].median * 100.0
    assert abs(cool - 0.48) <= 0.15 and abs(hot - 0.88) <= 0.15
    # every zone has at least the minimum number of systems after pooling
    assert all(z.n >= zones.min_systems for z in zones.zones.values())
