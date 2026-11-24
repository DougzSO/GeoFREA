# CI: `test_mapstyle_geo.py::test_neighbours_are_drawn_in_light_grey_within_the_buffer_only` failed once and passed on the rerun (2026-11-23)

Record for OQ-117. The test was not touched (COMMAND 210C, item d).

- Workflow `Unit tests and lint`, run 45279119672, job `unit (3.11)`, commit `f6a6388` (COMMAND 208A, `fix(convergence): same cell set as F7`), 2026-11-23 22:22 UTC. The same commit passed `Regression` and `Synthetic fixture (ZZZ)`.
- The commit does not touch `viz/mapstyle` or the test; the unit suite of the same tree had passed twice on the development machine (2,642 and 2,643 passed) and the run of the commit before it, `d6be079`, passed in CI.
- `gh run rerun --failed` of the same run: `Unit tests and lint` success (5 min 0 s). Nothing else changed between the two attempts.
- Only that test failed. The assertion counts the pixels of the neighbour colour in two maps (one with a neighbour inside the 2.5 degree buffer, one with a neighbour outside it); in the failed attempt the two counts were 214,543 for the map that must show the neighbour and 238,490 for the one that must not, against the expected greater than 5,000 and less than 1,500: the neighbour colour covered most of both canvases, which looks like a canvas-wide colour (a background or an unset layer), not like a drawn neighbour.

Log of the failed attempt (from `gh run view 45279119672 --attempt 1 --log-failed`):

```
        def count(canvas):
            canvas.fig.canvas.draw()
            rgba = np.asarray(canvas.fig.canvas.buffer_rgba())[..., :3] / 255.0
            return int((np.abs(rgba - grey).max(axis=2) < 0.01).sum())
    
>       assert count(a) > 5000 and count(b) < 1500  # a few grey pixels are the anti-aliasing of the text
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       assert (214543 > 5000 and 238490 < 1500)
E        +  where 214543 = <function test_neighbours_are_drawn_in_light_grey_within_the_buffer_only.<locals>.count at 0x72a2e9a6ab60>(MapFigure(fig=<Figure size 2244.09x2504.84 with 3 Axes>, ax=<Axes: >, cax=<Axes: >, overlay=<Axes: >, layout=Layout(wi...62...>, lonlat_extent=(7.090700277607778, 8.902312865031302, 46.2786915239116, 47.71856574089331)), no_data_label=None))
E        +  and   238490 = <function test_neighbours_are_drawn_in_light_grey_within_the_buffer_only.<locals>.count at 0x72a2e9a6ab60>(MapFigure(fig=<Figure size 2244.09x2504.84 with 3 Axes>, ax=<Axes: >, cax=<Axes: >, overlay=<Axes: >, layout=Layout(wi...62...>, lonlat_extent=(7.090700277607778, 8.902312865031302, 46.2786915239116, 47.71856574089331)), no_data_label=None))

tests/unit/test_mapstyle_geo.py:283: AssertionError
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/site-packages/rasterio/transform.py:178: 21 warnings
```
