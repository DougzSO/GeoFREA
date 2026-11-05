"""Peak memory, time and difference from the existing raster of each layer of F2a and F2b on a real country (COMMAND 88, item 0).

usage: python scripts/profiling/measure_layer_memory.py ISO [layer ...] --out rows.jsonl [--max-seconds N] [--compare]

Each layer runs through `core.layer_process.run_layer` (a child process, as in a run) with its output in a scratch directory; the peak is that of the
child. Nothing is written to `raw/` or to the outputs of the country; the clip caches of `interim/<ISO>/grid_alignment` are read (and made if stale,
as a run does). With `--compare`, a raster the country already has is compared with the new one by `core.equivalence` (largest absolute and relative
difference, pixels outside the tolerance). A layer is stopped, and its row says `partial`, after `--max-seconds`; its peak is then a lower bound.

Layers: glo30 (elevation, slope, slope bins), solar, wind_<product>_<height>m, land_cover, land_cover_counts, population, grid, poi, roads, lakes,
rivers, physical (F2b, `dist_grid_km`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

DEFAULT_LAYERS = [
    "glo30", "solar", "wind_wind_speed_100m", "wind_weibull_a_150m", "wind_air_density_200m", "land_cover", "land_cover_counts",
    "population", "settlements", "grid", "poi", "roads", "lakes", "rivers", "physical",
]  # fmt: skip
POI_THRESHOLD_KV = {"BRA": 138.0, "PRT": 150.0, "IND": 220.0}


def build_context(iso: str, out_dir: Path):
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    from geofrea.core import paths as core_paths
    from geofrea.core.config_loader import load_settings
    from geofrea.core.constants import CELL_NESTING_PIXELS
    from geofrea.data_acquisition.schemas import AcquisitionResult
    from geofrea.grid_alignment.adapter import acquisition_result_to_grid_alignment_inputs
    from geofrea.grid_alignment.layers import LayerContext
    from geofrea.grid_alignment.reference_grid import build_reference_grid

    data = core_paths.data_root()
    raw = json.loads((data / "outputs" / iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))

    def absolute(value):  # the artifact keeps portable `data:` paths
        if isinstance(value, str) and value.startswith("data:"):
            return str(data / value[5:])
        if isinstance(value, list):
            return [absolute(v) for v in value]
        if isinstance(value, dict):
            return {k: absolute(v) for k, v in value.items()}
        return value

    raw = absolute(raw)
    raw.setdefault("timestamp", "1970-01-01T00:00:00+00:00")
    settings = load_settings(REPO / "config" / "settings.yaml")
    geo = settings.geospatial
    inputs = acquisition_result_to_grid_alignment_inputs(AcquisitionResult.model_validate(raw), geo.resolutions, geo.distance_cap_km)
    substations = data / geo.poi_substations_geojson.format(iso=iso)
    inputs = inputs.model_copy(
        update={
            "poi_voltage_threshold_kv": POI_THRESHOLD_KV[iso],
            "poi_line_tolerance_m": geo.poi_line_tolerance_m,
            "poi_substation_source": substations if substations.is_file() else None,
            "road_classes": geo.road_classes,
            "warp_mem_limit_mb": geo.warp_mem_limit_mb,
        }
    )
    grid = build_reference_grid(inputs.country_gdf, float(inputs.resolution_deg), nesting_pixels=CELL_NESTING_PIXELS)
    return (
        LayerContext(inputs=inputs, grid=grid, out_dir=out_dir, interim_dir=core_paths.interim(iso, "grid_alignment"), country_code=iso),
        data / "outputs" / iso / "grid_alignment" / "artifacts",
    )


def job(ctx, layer: str):
    """(builder, kwargs, the rasters it writes as name -> existing raster to compare with, kind of the budget)."""
    base = "geofrea.grid_alignment.layers:"
    if layer == "glo30":
        return base + "build_glo30", {}, ["elevation", "slope", "slope_counts"], "glo30"
    if layer.startswith("wind_"):
        return base + "build_wind", {"key": layer[5:]}, [layer], "wind"
    plain = {
        "solar": "build_solar", "land_cover": "build_land_cover", "land_cover_counts": "build_land_cover_counts", "population": "build_population", "settlements": "build_settlements",
        "grid": "build_grid_distance", "roads": "build_roads", "lakes": "build_lakes", "rivers": "build_rivers",
    }  # fmt: skip
    if layer in plain:
        return base + plain[layer], {}, [layer], layer
    if layer == "poi":
        return base + "build_poi", {"name": "poi", "threshold_kv": ctx.inputs.poi_voltage_threshold_kv, "counts_path": ctx.out_dir / "poi_counts.json"}, ["poi"], "poi"
    raise SystemExit(f"unknown layer {layer}")


def measure(iso: str, layers: list[str], rows_path: Path, max_seconds: float, compare: bool) -> None:
    from geofrea.core import layer_process
    from geofrea.core.equivalence import compare_rasters
    from geofrea.core.memory_guard import CommitLimitExceeded

    scratch = Path(tempfile.mkdtemp(prefix=f"m88_{iso}_"))
    ctx, existing = build_context(iso, scratch / "aligned")
    ctx.out_dir.mkdir(parents=True)
    try:
        for layer in layers:
            started = time.perf_counter()
            row = {"iso": iso, "layer": layer}
            if layer == "physical":
                from geofrea.siting_layers.physical_layers import LAYER_SPECS

                target = "geofrea.siting_layers.physical_layers:write_physical_layer"
                kwargs = {"src_path": existing / f"{iso}_grid_aligned.tif", "out_path": scratch / "dist_grid_km.tif", "spec": LAYER_SPECS[0]}
                names = []
            else:
                target, kwargs, names, _ = job(ctx, layer)
                kwargs = {"ctx": ctx, **kwargs}
            # the layer is stopped by the timer thread through the child: run_layer has no time limit, so the limit is a daemon that ends the child
            killer = threading.Timer(max_seconds, lambda: _kill_children())
            killer.start()
            try:
                _, record = layer_process.run_layer(layer, target, kwargs, work_dir=scratch)
                row.update(status="ok" if time.perf_counter() - started < max_seconds else "partial")
                row.update(peak_rss_mb=record.peak_rss_mb, peak_commit_mb=record.peak_commit_mb, wall_s=record.wall_s)
            except CommitLimitExceeded as exc:
                row.update(status=f"stopped: {exc}", wall_s=round(time.perf_counter() - started, 1))
            except layer_process.LayerFailedError as exc:
                partial = time.perf_counter() - started >= max_seconds - 1
                row.update(status="partial" if partial else f"failed: {str(exc)[-200:]}", wall_s=round(time.perf_counter() - started, 1))
                if exc.record is not None:
                    row.update(peak_rss_mb=exc.record.peak_rss_mb, peak_commit_mb=exc.record.peak_commit_mb)
            finally:
                killer.cancel()
            if compare and row.get("status") == "ok":
                deltas = {}
                for name in names:
                    old, new = existing / f"{iso}_{name}_aligned.tif", ctx.path(name)
                    if old.exists() and new.exists():
                        deltas[name] = compare_rasters(old, new).as_dict()
                row["compare"] = deltas
            with rows_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(json.dumps({k: v for k, v in row.items() if k != "compare"}), flush=True)
            for stale in ctx.out_dir.glob("*.tif"):  # one layer at a time on disk
                stale.unlink(missing_ok=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _kill_children() -> None:
    from geofrea.core import layer_process

    import psutil

    for child in psutil.Process().children(recursive=False):
        layer_process.kill_tree(child)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("iso")
    parser.add_argument("layers", nargs="*")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1200)
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args(argv)
    measure(args.iso, args.layers or DEFAULT_LAYERS, args.out, args.max_seconds, args.compare)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
