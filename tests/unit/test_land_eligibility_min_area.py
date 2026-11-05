"""The minimum eligible area of Group 6: the pixel floor, the clusters of 8-connected pixels and their eligible area (`land_eligibility/min_area.py`)."""

from __future__ import annotations

from collections import deque

import numpy as np
import pytest

from geofrea.config_models.land_availability import ParameterSet
from geofrea.land_eligibility.min_area import (
    apply_minimum_area,
    cluster_areas,
    label_clusters,
    write_minimum_area,
)
from geofrea.land_eligibility.windows import NpyRows, NpyWriter


def _brute_force_labels(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """The reference: a breadth-first flood fill over the eight neighbours, labels in order of first appearance in row-major order."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    n = 0
    for r in range(h):
        for c in range(w):
            if not mask[r, c] or labels[r, c]:
                continue
            n += 1
            labels[r, c] = n
            queue = deque([(r, c)])
            while queue:
                y, x = queue.popleft()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not labels[yy, xx]:
                            labels[yy, xx] = n
                            queue.append((yy, xx))
    return labels, n


@pytest.mark.parametrize("seed", range(5))
def test_the_labels_are_those_of_a_flood_fill_over_eight_neighbours(seed):
    rng = np.random.default_rng(seed)
    fraction = np.where(rng.random((37, 29)) < 0.45, rng.random((37, 29)), 0.0).astype(np.float32)
    labels, n = label_clusters(fraction)
    reference, n_ref = _brute_force_labels(fraction > 0)
    assert n == n_ref
    # the same partition (the numbering of the labels may differ): each reference label maps to one label of ours
    pairs = {(int(a), int(b)) for a, b in zip(labels.ravel(), reference.ravel(), strict=True)}
    assert len(pairs) == n + 1  # 0 <-> 0 and one pair per cluster
    assert labels.dtype == np.int32


def test_two_pixels_that_touch_by_a_corner_are_one_cluster_and_by_nothing_are_two():
    fraction = np.zeros((6, 6), dtype=np.float32)
    fraction[1, 1] = fraction[2, 2] = 0.5  # diagonal neighbours
    fraction[4, 4] = 0.5  # alone
    labels, n = label_clusters(fraction)
    assert n == 2 and labels[1, 1] == labels[2, 2] != labels[4, 4]


def test_the_area_of_a_cluster_is_the_sum_of_eligible_fraction_times_pixel_area():
    fraction = np.zeros((4, 3), dtype=np.float32)
    fraction[0, 0], fraction[1, 1] = 0.5, 1.0  # one cluster across rows with different pixel areas
    fraction[3, 2] = 0.25
    area_row = np.array([1.2, 1.1, 1.0, 0.9])
    labels, n = label_clusters(fraction)
    areas = cluster_areas(labels, n, fraction, area_row)
    assert n == 2 and areas[0] == 0.0
    assert sorted(areas[1:]) == pytest.approx(sorted([0.5 * 1.2 + 1.0 * 1.1, 0.25 * 0.9]))


def test_a_cluster_is_kept_when_its_eligible_area_reaches_the_floor_and_dropped_below_it():
    fraction = np.zeros((5, 8), dtype=np.float32)
    fraction[1, 1:4] = 1.0  # 3 pixels of 1 km2
    fraction[3, 5:8] = 1.0
    fraction[3, 7] = 0.9999  # 2.9999 km2
    area_row = np.ones(5)
    kept, stats = apply_minimum_area(fraction, area_row, None, 3.0)
    assert (kept[1, 1:4] == 1.0).all() and (kept[3, 5:8] == 0.0).all()
    assert (stats.n_clusters, stats.n_clusters_kept) == (2, 1)
    assert stats.area_removed_by_cluster_floor_km2 == pytest.approx(2.9999, abs=1e-4)
    assert stats.area_removed_by_pixel_floor_km2 == 0.0
    # no rule, no change
    same, none = apply_minimum_area(fraction, area_row, None, None)
    assert (same == fraction).all() and none.n_clusters == 0


def test_the_pixel_floor_acts_before_the_clusters_are_formed():
    """A pixel below the floor is gone before the labelling, so it cannot join two clusters that it would have linked."""
    fraction = np.zeros((3, 7), dtype=np.float32)
    fraction[1, 0:3] = 1.0  # 3 km2
    fraction[1, 3] = 0.05  # the weak link
    fraction[1, 4:7] = 1.0  # 3 km2
    area_row = np.ones(3)
    one_cluster, stats = apply_minimum_area(fraction, area_row, None, 6.0)  # linked: 6.05 km2, kept
    assert (one_cluster == fraction).all() and stats.n_clusters == 1
    split, stats = apply_minimum_area(fraction, area_row, 0.10, 6.0)  # the link is dropped first: two clusters of 3 km2, both below 6
    assert (split == 0.0).all() and stats.n_clusters == 2 and stats.n_clusters_kept == 0
    assert stats.area_removed_by_pixel_floor_km2 == pytest.approx(0.05)
    only_pixels, stats = apply_minimum_area(fraction, area_row, 0.10, None)
    assert only_pixels[1, 3] == 0.0 and (only_pixels[1, :3] == 1.0).all() and stats.n_clusters == 0


def test_a_ribbon_across_the_whole_grid_is_one_cluster_whatever_the_rows_it_is_read_in(tmp_path):
    """The cluster crosses every row of the grid: read by stripes of any height it must keep or lose its whole area together."""
    h, w = 40, 6
    fraction = np.zeros((h, w), dtype=np.float32)
    fraction[:, 2] = 0.5  # 40 pixels of 0.5 km2 = 20 km2
    fraction[::2, 3] = 0.5  # a diagonal-free comb on the side, same cluster
    area_row = np.ones(h)
    raw_path = tmp_path / "raw.npy"
    writer = NpyWriter(raw_path, (h, w), np.float32)
    for r in range(0, h, 7):
        writer.write(fraction[r : r + 7])
    writer.close()
    for floor, kept in ((30.0, True), (30.1, False)):
        params = ParameterSet(
            slope_max_pct=5.0, settlement_setback_m=0.0, river_width_coefficient=7.2, river_width_exponent=0.5,
            river_buffer_steps=((None, 10.0),), excluded_classes=(), iucn_categories=(), min_cluster_km2=floor,
        )
        result, stats = write_minimum_area(NpyRows(raw_path), area_row, params, tmp_path / f"final_{floor}.npy")
        got = result[0:h]
        assert (got == fraction).all() if kept else (got == 0.0).all()
        assert stats.n_clusters == 1 and stats.n_clusters_kept == int(kept)


def test_with_no_rule_the_first_pass_result_is_the_result(tmp_path):
    raw = tmp_path / "raw.npy"
    np.save(raw, np.ones((3, 3), dtype=np.float32))
    params = ParameterSet(
        slope_max_pct=5.0, settlement_setback_m=0.0, river_width_coefficient=7.2, river_width_exponent=0.5,
        river_buffer_steps=((None, 10.0),), excluded_classes=(), iucn_categories=(),
    )
    rows, stats = write_minimum_area(NpyRows(raw), np.ones(3), params, tmp_path / "unused.npy")
    assert stats is None and rows.path == raw and not (tmp_path / "unused.npy").exists()
