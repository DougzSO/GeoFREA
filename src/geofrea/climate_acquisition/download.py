"""Download of one requirement through a server-side bounding-box cut-out, with resume and an alternative source.

Provenance (A-11). Adapted from the CRAEI repository (https://github.com/DougzSO/CRAEI.git, commit
7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f): `src/craei/acquire/isimip.py` (`submit_job`, `poll_job` written as a loop,
`_download_single_stream` with Range resume, the staging of partial files) and `src/craei/acquire/isimip_layer.py`
(the cut-out job on the ISIMIP files API v2, the zip unpacked into one record per file, the saved job URL that lets a
run pick up a job after a crash). Adaptation: no `isimip-client` package (plain HTTP on the documented API), the HTTP
session is injected, the manifest is the one of this package, and a last-resort path downloads the global file and
crops it locally.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .catalogue import check_host
from .config import Requirement
from .manifest import Manifest, atomic_write_text, sha256_file


class DownloadError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Downloader:
    def __init__(self, cfg: dict, session, root: Path, manifest: Manifest, jobs_path: Path, staging: Path, sleep=time.sleep,
                 allowed_hosts: set[str] | None = None, log=lambda msg: None):
        self.cfg, self.session, self.root, self.manifest = cfg, session, Path(root), manifest
        self.jobs_path, self.staging, self.sleep = Path(jobs_path), Path(staging), sleep
        self.allowed, self.log = allowed_hosts or set(), log
        self.dl = cfg["download"]
        self._jobs_lock = threading.Lock()

    # ---- job state, so a crashed run resumes the same server job -------------------------------------------
    def _jobs(self) -> dict:
        return json.loads(self.jobs_path.read_text(encoding="utf-8")) if self.jobs_path.exists() else {}

    def _save_job(self, key: str, url: str) -> None:
        with self._jobs_lock:
            jobs = self._jobs()
            jobs[key] = url
            atomic_write_text(self.jobs_path, json.dumps(jobs, indent=1, sort_keys=True))

    # ---- server cut-out ------------------------------------------------------------------------------------
    def _submit(self, req: Requirement, path: str) -> str:
        west, east, south, north = req.bbox
        body = {"paths": [path], "operations": [{"operation": "cutout_bbox", "bbox": [west, east, south, north],
                                                 "compute_mean": False, "output_csv": False}]}
        resp = self.session.post(check_host(self.cfg["files_api"], self.allowed), json=body, timeout=120)
        resp.raise_for_status()
        return resp.json()["job_url"]

    def _wait(self, job_url: str) -> dict:
        waited = 0.0
        while True:
            resp = self.session.get(check_host(job_url, self.allowed), timeout=60)
            resp.raise_for_status()
            job = resp.json()
            if job["status"] not in ("queued", "started"):
                return job
            if waited > self.dl["job_timeout_s"]:
                raise DownloadError(f"cut-out job timed out: {job_url}")
            self.sleep(self.dl["poll_interval_s"])
            waited += self.dl["poll_interval_s"]

    def _stream(self, url: str, part: Path) -> None:
        """Fetch `url` into `part`, resuming from the bytes already there."""
        check_host(url, self.allowed)
        part.parent.mkdir(parents=True, exist_ok=True)
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        resp = self.session.get(url, headers=headers, stream=True, timeout=120)
        if resp.status_code == 416:  # the part is already the whole file
            return
        resp.raise_for_status()
        mode = "ab" if (have and resp.status_code == 206) else "wb"
        with open(part, mode) as fh:
            fh.writelines(resp.iter_content(chunk_size=1 << 20))

    def _fetch_cutout(self, req: Requirement, path: str, rel: str) -> tuple[Path, str, str]:
        """Returns the staged .nc file, the file URL of the zip and the job URL."""
        key = f"{path}|{list(req.bbox)}"
        job_url = self._jobs().get(key)
        job = None
        if job_url:
            try:
                resp = self.session.get(job_url, timeout=60)
                resp.raise_for_status()
                job = resp.json()
                if job.get("status") == "failed":
                    job = None
            except Exception:  # noqa: BLE001 - a job the server forgot is simply submitted again
                job = None
        if job is None:
            job_url = self._submit(req, path)
            self._save_job(key, job_url)
        job = self._wait(job_url)
        if job["status"] != "finished" or not job.get("file_url"):
            raise DownloadError(f"cut-out job {job['status']} for {path}: {job.get('errors') or job.get('message')}")
        zname = job["file_url"].rsplit("/", 1)[-1]
        zpart = self.staging / (zname + ".part")
        self._stream(job["file_url"], zpart)
        with zipfile.ZipFile(zpart) as z:
            bad = z.testzip()
            members = [m for m in z.namelist() if m.lower().endswith(".nc")]
            if bad or len(members) != 1:
                zpart.unlink(missing_ok=True)
                raise DownloadError(f"bad cut-out zip for {path}: corrupt={bad} members={members}")
            out = self.staging / (Path(members[0]).name + ".part")
            with z.open(members[0]) as src, open(out, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        zpart.unlink(missing_ok=True)
        return out, job["file_url"], job_url

    def _fetch_global_and_crop(self, req: Requirement, path: str) -> tuple[Path, str, str]:
        """Last resort: the global file from the files server, verified by its catalogue checksum, cropped here."""
        url = f"{self.cfg['files_base']}/{path}"
        part = self.staging / (path.rsplit("/", 1)[-1] + ".global.part")
        self._stream(url, part)
        if req.global_checksum and req.global_checksum_type:
            h = hashlib.new(req.global_checksum_type)
            with open(part, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    h.update(chunk)
            if h.hexdigest() != req.global_checksum:
                part.unlink(missing_ok=True)
                raise DownloadError(f"global file checksum mismatch: {path}")
        out = self.staging / (req.name + ".part")
        crop_netcdf(part, out, req.bbox)
        part.unlink(missing_ok=True)
        return out, url, "local crop of the global file"

    # ---- one requirement ----------------------------------------------------------------------------------
    def fetch(self, req: Requirement, alt_paths: list[str] | None = None) -> str:
        """Bring one requirement to `root`, register it, and return the outcome (`cached` or `downloaded`)."""
        rel = req.rel_path(self.cfg["layout"])
        if self.manifest.is_intact(rel):
            return "cached"
        attempts, last = [], None
        candidates = [("cutout", req.global_path), *[("cutout", p) for p in (alt_paths or [])],
                      ("global_crop", req.global_path)]
        for mode, path in candidates:
            for attempt in range(int(self.dl["retries"])):
                try:
                    if mode == "cutout":
                        staged, url, job = self._fetch_cutout(req, path, rel)
                    else:
                        staged, url, job = self._fetch_global_and_crop(req, path)
                    return self._register(req, rel, staged, url, job, path, mode)
                except (DownloadError, OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
                    last = exc
                    attempts.append(f"{mode} {path} try {attempt + 1}: {exc}")
                    self.log(attempts[-1])
                    self.sleep(5 * (attempt + 1))
                except Exception as exc:  # noqa: BLE001 - HTTP errors of the injected session
                    last = exc
                    attempts.append(f"{mode} {path} try {attempt + 1}: {exc}")
                    self.log(attempts[-1])
                    self.sleep(5 * (attempt + 1))
        raise DownloadError(f"{rel}: every source failed ({last}); attempts: {attempts[-6:]}")

    def _register(self, req: Requirement, rel: str, staged: Path, url: str, job: str, path: str, mode: str) -> str:
        dst = self.root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(dst)  # the final name exists only for a complete file
        sha = sha256_file(dst)
        self.manifest.add(rel, {
            "sha256": sha,
            "size_bytes": dst.stat().st_size,
            "url": url,
            "accessed_utc": _now(),
            "bbox": list(req.bbox),
            "gcm": req.gcm,
            "ghm": req.ghm,
            "scenario": req.scenario,
            "variable": req.variable,
            "country": req.country,
            "period": [req.start_year, req.end_year],
            "time_step": req.time_step,
            "spatial_resolution_deg": 0.5,
            "origin": "isimip_server" if mode == "cutout" else "isimip_server_global_crop",
            "effective_source": f"{mode}; job {job}; global file {path}",
            "isimip_file": path,
            "soc": req.soc,
            "source_sha256": None,
        })
        return "downloaded"


def crop_netcdf(src: Path, dst: Path, bbox) -> None:
    """Crop a global NetCDF to the box (west, east, south, north) and write it to `dst`."""
    import xarray as xr

    west, east, south, north = bbox
    with xr.open_dataset(src) as ds:
        lat_desc = bool(ds["lat"][0] > ds["lat"][-1])
        sub = ds.sel(lon=slice(west, east), lat=slice(north, south) if lat_desc else slice(south, north))
        sub.load().to_netcdf(dst)
