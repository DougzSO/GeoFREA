"""Time, peak memory and disk of F5 to F8 at the size of a real country, with no real value (audit 2026-10, M-2; COMMAND 39).

The real F3 and F4 outputs of the country (`outputs/<ISO3>/`, `interim/<ISO3>/`) are COPIED into a scratch `GEOFREA_DATA_DIR`, and F5 to F8 run there with the test parameters of the
synthetic country (the values `parameters.json` holds for ZZZ), the synthetic power curve and the test values of the pre-registered settings (`tests/synthetic/zzz_run.py`).
Nothing of this is a result: the scratch directory is removed when the numbers are recorded, and the real data directory is read and never written (the script prints the hash
of every file of `outputs/<ISO3>/` before and after, and refuses to continue if they differ). `raw/` is joined to the scratch directory (junction on Windows, symbolic link
elsewhere) because F7b reads the borders, the protected areas, the water bodies and the plant inventory from it; no phase of F5 to F8 writes there.

One scratch directory and one chain of phases per technology, because the phases loop over the technologies they are given and a second run in the same directory would resume the first:
`--tech wind` and `--tech solar`. Every phase runs in a new process, so its peak working set is its own; the disk is the growth of `outputs/<ISO3>/` + `interim/<ISO3>/`
in the scratch directory. F8 reads both technologies in a real run: here it reads the one of the chain.

Usage (GEOFREA_DATA_DIR is the real data directory):
    python scripts/size_f5_to_f8.py --country BRA --tech wind --scratch D:/tmp/size_wind --draws 500 [--keep]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHAIN = [
    "technical_potential",
    "potential_maps",
    "lcoe_modeling",
    "sample_size_convergence",
    "robustness_analysis",
    "external_validation",
    "lcoe_maps",
    "robustness_maps",
    "results_synthesis",
]
LABEL = {
    "technical_potential": "F5",
    "potential_maps": "F5 maps",
    "lcoe_modeling": "F6",
    "sample_size_convergence": "F6 convergence",
    "robustness_analysis": "F7",
    "external_validation": "F7b",
    "lcoe_maps": "F6 maps",
    "robustness_maps": "F7 maps",
    "results_synthesis": "F8",
}


def peak_rss_mb() -> float:
    """Peak working set of this process, MB."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return counters.PeakWorkingSetSize / 2**20
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def tree_size(*roots: Path) -> int:
    return sum(
        p.stat().st_size for root in roots if root.exists() for p in root.rglob("*") if p.is_file()
    )


def hash_tree(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            digest = hashlib.sha256()
            with open(p, "rb") as handle:
                for block in iter(lambda: handle.read(1 << 22), b""):
                    digest.update(block)
            out[p.relative_to(root).as_posix()] = digest.hexdigest()
    return out


def join_raw(real: Path, scratch: Path) -> None:
    link = scratch / "raw"
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real / "raw")],
            check=True,
            capture_output=True,
        )
    else:
        os.symlink(real / "raw", link, target_is_directory=True)


def remove_raw_link(scratch: Path) -> None:
    link = scratch / "raw"
    if link.is_symlink() or (sys.platform == "win32" and link.exists()):
        os.rmdir(link) if sys.platform == "win32" else link.unlink()


def prepare(real: Path, scratch: Path, country: str, draws: int) -> None:
    sys.path.insert(0, str(REPO / "tests" / "synthetic"))
    import zzz_run

    scratch.mkdir(parents=True, exist_ok=True)
    for sub in ("outputs", "interim"):
        shutil.copytree(real / sub / country, scratch / sub / country)
    join_raw(real, scratch)
    keep_all = {
        t: {"cf_min": {"value": 0.01}} for t in ("wind", "solar")
    }  # every candidate enters the F7 set: the largest size
    zzz_run.prepare_configuration(
        scratch,
        draws,
        draws,
        parameter_country=country,
        parameter_changes=keep_all,
        experiments_country=country,
    )


def run_phase(scratch: Path, country: str, tech: str, phase: str) -> dict:
    """Run one phase in this process (called through `--phase` in a new process) and return its numbers."""
    import main  # repo-root script

    sys.path.insert(0, str(REPO / "tests" / "synthetic"))
    import zzz_run

    from geofrea.core.config_loader import load_audit_config, load_settings

    os.environ["GEOFREA_DATA_DIR"] = str(scratch)
    main.TECHNOLOGIES_YAML = scratch / "technologies_with_synthetic_rule.yaml"
    main.EXPERIMENTS_YAML = scratch / "experiments_zzz.yaml"
    main.PARAMETERS_JSON = scratch / "parameters_synthetic.json"
    main.POWER_CURVES_DIR = zzz_run.CURVES
    settings = load_settings(main.SETTINGS_YAML)
    before = tree_size(scratch / "outputs" / country, scratch / "interim" / country)
    wall, cpu = time.perf_counter(), time.process_time()
    ok, _orchestrator, results = main.run_geofrea(
        country,
        [phase],
        [],
        settings.geospatial.resolutions,
        settings.geospatial.distance_cap_km,
        load_audit_config(main.AUDIT_YAML),
        f"size-{tech}-{phase}",
        False,
        None,
        (tech,),
        False,
        settings.figures,
        settings.memory.max_batch_gb,
    )
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    after = tree_size(scratch / "outputs" / country, scratch / "interim" / country)
    return {
        "phase": phase,
        "label": LABEL[phase],
        "tech": tech,
        "ok": bool(ok),
        "status": results[phase].status,
        "error": results[phase].error,
        "wall_s": round(wall, 1),
        "cpu_s": round(cpu, 1),
        "peak_working_set_mb": round(peak_rss_mb()),
        "disk_added_mb": round((after - before) / 2**20, 1),
    }


def main_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--country", default="BRA")
    parser.add_argument("--tech", choices=("wind", "solar"), required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument(
        "--phase",
        help="(internal) run this one phase in this process and print its numbers as JSON",
    )
    parser.add_argument("--keep", action="store_true", help="keep the scratch directory")
    parser.add_argument("--out", type=Path, help="JSON file for the table")
    args = parser.parse_args(argv)
    if args.phase:
        print(
            "SIZE_RESULT "
            + json.dumps(run_phase(args.scratch, args.country, args.tech, args.phase))
        )
        return 0

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env", override=False)
    real = Path(os.environ["GEOFREA_DATA_DIR"])
    real_outputs = real / "outputs" / args.country
    hashes_before = hash_tree(real_outputs)
    print(f"{len(hashes_before)} files hashed in {real_outputs}", flush=True)
    rows: list[dict] = []
    try:
        prepare(real, args.scratch, args.country, args.draws)
        base = tree_size(
            args.scratch / "outputs" / args.country, args.scratch / "interim" / args.country
        )
        print(f"scratch ready; copied inputs {base / 2**20:.0f} MB", flush=True)
        for phase in CHAIN:
            done = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__)),
                    "--country",
                    args.country,
                    "--tech",
                    args.tech,
                    "--scratch",
                    str(args.scratch),
                    "--draws",
                    str(args.draws),
                    "--phase",
                    phase,
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "GEOFREA_DATA_DIR": str(args.scratch)},
                check=False,
            )
            line = next((x for x in done.stdout.splitlines() if x.startswith("SIZE_RESULT ")), None)
            if line is None:
                rows.append(
                    {
                        "phase": phase,
                        "label": LABEL[phase],
                        "tech": args.tech,
                        "ok": False,
                        "error": (done.stderr or done.stdout)[-1500:],
                    }
                )
                print(json.dumps(rows[-1]), flush=True)
                break
            rows.append(json.loads(line[len("SIZE_RESULT ") :]))
            print(json.dumps(rows[-1]), flush=True)
            if not rows[-1]["ok"]:
                break
        total = tree_size(
            args.scratch / "outputs" / args.country, args.scratch / "interim" / args.country
        )
        rows.append(
            {"phase": "total", "tech": args.tech, "disk_added_mb": round((total - base) / 2**20, 1)}
        )
    finally:
        remove_raw_link(args.scratch)
        if (
            args.scratch / "raw"
        ).exists():  # never let rmtree follow the join into the real raw directory
            print(
                f"{args.scratch / 'raw'} is still joined to the real raw directory: scratch left in place",
                flush=True,
            )
        elif not args.keep:
            shutil.rmtree(args.scratch, ignore_errors=True)
    if args.out:
        args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    after = hash_tree(real_outputs)
    if after != hashes_before:
        changed = sorted(
            k for k in set(after) | set(hashes_before) if after.get(k) != hashes_before.get(k)
        )
        print(f"REAL OUTPUTS CHANGED: {changed[:20]}", flush=True)
        return 2
    print(f"real outputs of {args.country}: {len(after)} files, every hash unchanged", flush=True)
    return 0 if all(r.get("ok", True) for r in rows) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main_cli(sys.argv[1:]))
