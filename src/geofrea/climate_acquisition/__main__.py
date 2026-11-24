"""Command line of the ISIMIP3b acquisition: `python -m geofrea.climate_acquisition <plan|copy-local|download|verify>`.

`plan` reads the ISIMIP catalogue and writes the download plan; `copy-local` copies the CRAEI files that exist
(read only on the CRAEI side); `download` fetches what the plan still lists as `download`; `verify` re-hashes every
file of the manifest. The data directory comes from `--data-dir` or `GEOFREA_DATA_DIR`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import requests

from .catalogue import Catalogue
from .config import Requirement, load_config
from .download import Downloader
from .local_copy import copy_local, load_craei_hashes
from .manifest import Manifest
from .plan import DOWNLOAD, LOCAL_COPY, classify, crop_ratios, write_plan


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "geofrea-climate-acquisition"
    return s


def _paths(args, cfg):
    data = Path(args.data_dir or os.environ["GEOFREA_DATA_DIR"])
    root = data / "raw" / "isimip3b"
    return data, root, Manifest(root / cfg["manifest_file"], root)


def _fallback_water(craei_manifest: Path | None) -> dict:
    """Global water paths known from the CRAEI extension manifest, used if the catalogue is unreachable."""
    if craei_manifest is None or not Path(craei_manifest).is_file():
        return {}
    out = {}
    for rec in json.loads(Path(craei_manifest).read_text(encoding="utf-8")).values():
        if rec.get("family") == "water" and rec.get("global_sources"):
            out[f"{rec['variable']}/{rec['model']}/{rec['gcm']}/{rec['scenario']}"] = (rec["global_sources"][0], rec.get("soc"))
    return out


def cmd_plan(args, cfg):
    from .catalogue import build_requirements

    data, root, manifest = _paths(args, cfg)
    craei = Path(args.craei_raw) if args.craei_raw else None
    cat = Catalogue(cfg, _session())
    countries = args.countries or list(cfg["bboxes"])
    reqs, gaps = build_requirements(cfg, cat, countries, _fallback_water(Path(args.craei_manifest) if args.craei_manifest else None))
    status = classify(reqs, cfg["layout"], manifest, craei, cfg["local_source_country"])
    ratios = crop_ratios(reqs, craei, cfg["local_source_country"])
    free = shutil.disk_usage(data).free
    doc = write_plan(root / cfg["plan_file"], cfg, reqs, status, gaps, ratios, free, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(json.dumps({"summary": doc["summary"], "gaps": len(gaps), "estimated_download_bytes": doc["estimated_download_bytes"],
                      "free_bytes": free}, indent=1))


def cmd_copy_local(args, cfg):
    _, root, manifest = _paths(args, cfg)
    plan = json.loads((root / cfg["plan_file"]).read_text(encoding="utf-8"))
    reqs, status = [], {}
    for it in plan["items"]:
        reqs.append(Requirement.from_dict({k: it[k] for k in Requirement.__dataclass_fields__}))
        status[it["rel_path"]] = LOCAL_COPY if it["status"] == LOCAL_COPY else it["status"]
    res = copy_local(reqs, status, cfg, root, manifest, Path(args.craei_raw), load_craei_hashes(Path(args.craei_manifest) if args.craei_manifest else None))
    print(json.dumps(res, indent=1))
    return 1 if res["failed"] else 0


def cmd_download(args, cfg):
    data, root, manifest = _paths(args, cfg)
    plan = json.loads((root / cfg["plan_file"]).read_text(encoding="utf-8"))
    todo = [Requirement.from_dict({k: it[k] for k in Requirement.__dataclass_fields__}) for it in plan["items"] if it["status"] == DOWNLOAD]
    need = sum(i["est_bytes"] or 0 for i in plan["items"] if i["status"] == DOWNLOAD)
    free = shutil.disk_usage(data).free
    if need > free - cfg["download"]["free_space_margin_gb"] * 1024**3:
        print(f"stop: estimated {need} bytes does not fit in {free} free bytes minus the margin", file=sys.stderr)
        return 2
    logs = data / "logs" / "climate_acquisition"
    logs.mkdir(parents=True, exist_ok=True)
    log_file = logs / f"download_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.log"

    def log(msg: str) -> None:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(UTC).isoformat(timespec='seconds')} {msg}\n")

    dl = Downloader(cfg, _session(), root, manifest, logs / "jobs.json", root / "_staging", log=log)
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(dl.fetch, r): r for r in todo}
        for f in as_completed(futs):
            r = futs[f]
            try:
                log(f"{f.result()} {r.rel_path(cfg['layout'])}")
            except Exception as exc:  # noqa: BLE001 - a failed file is reported and the others go on
                failed.append(r.rel_path(cfg["layout"]))
                log(f"FAILED {r.rel_path(cfg['layout'])}: {exc}")
    print(json.dumps({"requested": len(todo), "failed": failed}, indent=1))
    return 1 if failed else 0


def cmd_verify(args, cfg):
    _, _, manifest = _paths(args, cfg)
    res = manifest.verify()
    print(json.dumps({k: len(v) for k, v in res.items()} | {"entries": len(manifest.entries)}, indent=1))
    return 1 if any(res.values()) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m geofrea.climate_acquisition")
    ap.add_argument("command", choices=["plan", "copy-local", "download", "verify"])
    ap.add_argument("--data-dir")
    ap.add_argument("--craei-raw", default=os.environ.get("CRAEI_RAW_CLIMATE_DIR"), help="read-only CRAEI raw/climate directory")
    ap.add_argument("--craei-manifest", default=os.environ.get("CRAEI_EXTENSION_MANIFEST"), help="read-only CRAEI manifest_extension_b12.json")
    ap.add_argument("--countries", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    cfg = load_config()
    return {"plan": cmd_plan, "copy-local": cmd_copy_local, "download": cmd_download, "verify": cmd_verify}[args.command](args, cfg) or 0


if __name__ == "__main__":
    raise SystemExit(main())
