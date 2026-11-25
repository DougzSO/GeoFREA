"""Tests of the ISIMIP3b acquisition package against a simulated network (no real connection, no real data)."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from geofrea.climate_acquisition import catalogue as cat_mod
from geofrea.climate_acquisition.catalogue import (
    Catalogue,
    HostError,
    build_requirements,
    check_host,
    overlaps,
    pattern_paths,
)
from geofrea.climate_acquisition.config import Requirement, bbox_tag, grid_cells, load_config
from geofrea.climate_acquisition.download import Downloader, DownloadError
from geofrea.climate_acquisition.local_copy import copy_local, load_craei_hashes
from geofrea.climate_acquisition.manifest import Manifest, sha256_file
from geofrea.climate_acquisition.plan import (
    DOWNLOAD,
    IN_MANIFEST,
    LOCAL_COPY,
    classify,
    crop_ratios,
    estimate_bytes,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "geofrea" / "climate_acquisition"


class Resp:
    def __init__(self, status=200, payload=None, body=b"", url=""):
        self.status_code, self._payload, self.body, self.url = status, payload, body, url
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 416:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield self.body


class FakeNet:
    """Simulated ISIMIP: catalogue, cut-out jobs, zip files with Range support."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.calls: list[tuple] = []
        self.jobs: dict[str, dict] = {}
        self.zips: dict[str, bytes] = {}
        self.fail_catalogue = 0
        self.fail_zip_get = 0
        self.job_polls_until_done = 1
        self.break_cutout_for: set[str] = set()
        self.global_files: dict[str, bytes] = {}

    def catalogue_dataset(self, spec):
        if spec.get("sector") == "water_global":
            return self._water(spec)
        var, gcm, scen = spec["climate_variable"], spec["climate_forcing"], spec["climate_scenario"]
        if gcm == "gfdl-esm4" and scen == "ssp370" and var == "tas":
            return []  # a gap
        label = cat_mod.VARIANT_LABEL.get(gcm, cat_mod.DEFAULT_VARIANT_LABEL)
        spans = [(1991, 2000), (2001, 2010), (2011, 2014)] if scen == "historical" else [(2031, 2040), (2041, 2050), (2051, 2060), (2061, 2070), (2071, 2080)]
        files = [{"name": f"{gcm}_{label}_w5e5_{scen}_{var}_global_daily_{a}_{b}.nc", "size": 2_000_000_000,
                  "checksum": "ab", "checksum_type": "sha512",
                  "path": f"ISIMIP3b/InputData/climate/atmosphere/bias-adjusted/global/daily/{scen}/{gcm.upper()}/{gcm}_{label}_w5e5_{scen}_{var}_global_daily_{a}_{b}.nc"}
                 for a, b in spans]
        good = {"specifiers": {"product": "InputData", "time_step": "daily"}, "files": files}
        hourly = {"specifiers": {"product": "SecondaryInputData", "time_step": "hourly"}, "files": files[:1]}
        return [hourly, good]

    def _water(self, spec):
        ghm, var, gcm, scen = spec["model"], spec["variable"], spec["climate_forcing"], spec["climate_scenario"]
        if ghm == "cwatm" and scen == "ssp585" and gcm == "ukesm1-0-ll":
            return []
        out = []
        if ghm == "h08" and gcm == "ukesm1-0-ll" and scen == "ssp126":  # only a daily dataset is on offer for this pair
            n = f"{ghm}_{gcm}_{var}_global_daily_2015_2100.nc"
            return [{"specifiers": {"soc_scenario": "2015soc-from-histsoc", "time_step": "daily"},
                     "files": [{"name": n, "size": 1, "checksum": None, "checksum_type": None, "path": "x/" + n}]}]
        socs = ["histsoc", "2015soc"] if scen == "historical" else ["2015soc-from-histsoc"]
        for soc in socs:
            y = "1850_2014" if scen == "historical" else "2015_2100"
            n = f"{ghm}_{gcm}_w5e5_{scen}_{soc}_default_{var}_global_monthly_{y}.nc"
            out.append({"specifiers": {"soc_scenario": soc, "time_step": "monthly"},
                        "files": [{"name": n, "size": 270_000_000, "checksum": None, "checksum_type": None,
                                   "path": f"ISIMIP3b/OutputData/water_global/{ghm}/{gcm}/{scen}/{n}"}]})
        return out

    # ---- session interface ----
    def get(self, url, params=None, headers=None, stream=False, timeout=None):
        self.calls.append(("GET", url, params))
        if "/datasets/" in url:
            if self.fail_catalogue:
                self.fail_catalogue -= 1
                raise ConnectionError("dns")
            return Resp(200, {"results": self.catalogue_dataset(params), "next": None}, url=url)
        if url in self.jobs:
            job = self.jobs[url]
            job["polls"] += 1
            status = "finished" if job["polls"] > self.job_polls_until_done else "started"
            return Resp(200, {"job_url": url, "status": status, "file_url": job["file_url"] if status == "finished" else None}, url=url)
        if url in self.zips:
            if self.fail_zip_get:
                self.fail_zip_get -= 1
                raise ConnectionError("reset")
            data = self.zips[url]
            have = int((headers or {}).get("Range", "bytes=0-").split("=")[1].split("-")[0])
            if have >= len(data):
                return Resp(416)
            return Resp(206 if have else 200, body=data[have:])
        if url in self.global_files:
            return Resp(200, body=self.global_files[url])
        return Resp(404)

    def head(self, url, timeout=None, allow_redirects=True):
        return Resp(200 if url.replace(self.cfg["files_base"] + "/", "") in self.global_files or "InputData" in url else 404)

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        path = json["paths"][0]
        if path in self.break_cutout_for:
            return Resp(200, {"job_url": f"{url}/broken"}, url=url) if False else Resp(500)
        jid = f"{url}/job{len(self.jobs)}"
        payload = b"NC-CUT:" + path.encode() + b":" + str(json["operations"][0]["bbox"]).encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(path.rsplit("/", 1)[-1].replace("_global_", "_cut_"), payload)
        zurl = f"https://files.isimip.org/api/v2/output/{len(self.jobs)}.zip"
        self.zips[zurl] = buf.getvalue()
        self.jobs[jid] = {"polls": 0, "file_url": zurl}
        return Resp(200, {"job_url": jid, "status": "queued"}, url=url)


@pytest.fixture()
def cfg(tmp_path):
    c = load_config()
    c["download"]["retries"] = 2
    c["download"]["poll_interval_s"] = 0
    return c


def no_sleep(_s):
    return None


def small_cfg(cfg):
    c = json.loads(json.dumps(cfg))
    c["gcms"] = ["gfdl-esm4", "ukesm1-0-ll"]
    c["water"]["ghms"] = ["cwatm", "h08"]
    return c


# ---------------------------------------------------------------- names, windows, hosts
def test_cutout_name_matches_the_isimip_server_convention(cfg):
    r = Requirement("atmosphere", "rsds", "gfdl-esm4", None, "ssp126", "BRA", tuple(cfg["bboxes"]["BRA"]),
                    "ISIMIP3b/x/gfdl-esm4_r1i1p1f1_w5e5_ssp126_rsds_global_daily_2041_2050.nc", 1, None, None, "daily", 2041, 2050)
    assert r.name == "gfdl-esm4_r1i1p1f1_w5e5_ssp126_rsds_lon-74.5to-34.0lat-34.5to6.0_daily_2041_2050.nc"
    assert bbox_tag([68.0, 98.0, 6.0, 37.5]) == "lon68.0to98.0lat6.0to37.5"
    assert grid_cells(cfg["bboxes"]["BRA"]) == 81 * 81


def test_decade_blocks_overlap_the_windows():
    assert overlaps("a_global_daily_2011_2014.nc", 1995, 2014)
    assert overlaps("a_global_daily_1991_2000.nc", 1995, 2014)
    assert not overlaps("a_global_daily_1981_1990.nc", 1995, 2014)
    assert not overlaps("a_global_daily_2071_2080.nc", 2041, 2070)


def test_only_isimip_hosts_are_allowed():
    check_host("https://files.isimip.org/api/v2")
    with pytest.raises(HostError):
        check_host("https://example.com/x")


def test_pattern_fallback_uses_the_ukesm_variant_and_the_2014_ceiling(cfg):
    paths = pattern_paths(cfg, "tas", "ukesm1-0-ll", "historical", 1995, 2014)
    assert [p.rsplit("_", 2)[-2:] for p in paths] == [["1991", "2000.nc"], ["2001", "2010.nc"], ["2011", "2014.nc"]]
    assert all("r1i1p1f2" in p for p in paths)


# ---------------------------------------------------------------- requirement matrix
def test_matrix_uses_only_daily_inputdata_and_the_window_blocks(cfg):
    c = small_cfg(cfg)
    net = FakeNet(c)
    reqs, _ = build_requirements(c, Catalogue(c, net, sleep=no_sleep), ["BRA", "IND", "PRT"])
    atm = [r for r in reqs if r.family == "atmosphere"]
    assert {r.time_step for r in atm} == {"daily"}
    assert all("InputData/climate" in r.global_path and "SecondaryInputData" not in r.global_path for r in atm)
    hist = [r for r in atm if r.scenario == "historical" and r.variable == "tas" and r.gcm == "ukesm1-0-ll" and r.country == "BRA"]
    assert [(r.start_year, r.end_year) for r in hist] == [(1991, 2000), (2001, 2010), (2011, 2014)]
    fut = [r for r in atm if r.scenario == "ssp126" and r.variable == "tas" and r.gcm == "gfdl-esm4" and r.country == "PRT"]
    assert [(r.start_year, r.end_year) for r in fut] == [(2041, 2050), (2051, 2060), (2061, 2070)]


def test_gap_in_the_catalogue_is_recorded_not_raised(cfg):
    c = small_cfg(cfg)
    reqs, gaps = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA"])
    keys = {g["key"] for g in gaps}
    assert "tas/gfdl-esm4/ssp370" in keys
    assert "dis/cwatm/ukesm1-0-ll/ssp585" in keys and "qtot/cwatm/ukesm1-0-ll/ssp585" in keys
    assert not [r for r in reqs if r.variable == "tas" and r.gcm == "gfdl-esm4" and r.scenario == "ssp370"]
    step_gap = next(g for g in gaps if g["key"] == "dis/h08/ukesm1-0-ll/ssp126")
    assert "time step daily differs from monthly" in step_gap["reason"] and step_gap["urls"]
    assert [r for r in reqs if r.variable == "dis" and r.ghm == "h08" and r.gcm == "ukesm1-0-ll" and r.scenario == "ssp585"]


def test_water_historical_takes_histsoc_and_future_the_2015soc_variant(cfg):
    c = small_cfg(cfg)
    reqs, _ = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA"])
    w = {(r.scenario == "historical"): r.soc for r in reqs if r.family == "water"}
    assert w[True] == "histsoc" and w[False].startswith("2015soc")


def test_catalogue_retries_then_falls_back_to_the_pattern(cfg):
    c = small_cfg(cfg)
    c["gcms"] = ["gfdl-esm4"]
    c["water"]["ghms"] = []
    net = FakeNet(c)
    net.fail_catalogue = 10 ** 6
    reqs, gaps = build_requirements(c, Catalogue(c, net, sleep=no_sleep), ["BRA"])
    assert [r for r in reqs if r.variable == "tas" and r.scenario == "historical"]
    assert not [g for g in gaps if g["family"] == "atmosphere" and "ssp126" in g["key"]]


# ---------------------------------------------------------------- manifest
def test_manifest_requires_its_fields_and_verifies_by_hash(tmp_path):
    m = Manifest(tmp_path / "m.json", tmp_path)
    with pytest.raises(ValueError):
        m.add("a.nc", {"sha256": "x"})
    f = tmp_path / "a.nc"
    f.write_bytes(b"abc")
    from geofrea.climate_acquisition.manifest import ENTRY_FIELDS
    e = {k: None for k in ENTRY_FIELDS} | {"sha256": hashlib.sha256(b"abc").hexdigest(), "size_bytes": 3}
    m.add("a.nc", e)
    assert Manifest(tmp_path / "m.json", tmp_path).is_intact("a.nc")
    assert m.verify() == {"missing": [], "size": [], "sha256": []}
    f.write_bytes(b"abd")
    assert m.verify()["sha256"] == ["a.nc"]


# ---------------------------------------------------------------- local copy
def _craei_tree(tmp_path, c, reqs):
    craei = tmp_path / "craei_raw"
    hashes = {}
    for r in reqs:
        if r.country != "BRA" or r.variable not in ("rsds", "dis"):
            continue
        p = (craei / "isimip3b" / r.gcm / r.scenario / r.variable / r.name) if r.family == "atmosphere" else \
            (craei / "isimip3b_water" / str(r.ghm) / r.gcm / r.scenario / r.variable / r.name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"data:" + r.name.encode())
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return craei, hashes


def _craei_manifest(tmp_path, craei, hashes):
    doc = {f"k{i}": {"files": [{"file": f"{craei}/{n}", "sha256": h, "bytes": 1}], "job_url": "j", "file_url": "u", "date": "2026-11-12T00:00:00Z"}
           for i, (n, h) in enumerate(hashes.items())}
    p = tmp_path / "craei_manifest.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_local_copy_checks_hashes_never_touches_the_source_and_is_idempotent(tmp_path, cfg):
    c = small_cfg(cfg)
    reqs, _ = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA", "IND"])
    craei, hashes = _craei_tree(tmp_path, c, reqs)
    before = {p: p.read_bytes() for p in craei.rglob("*.nc")}
    root = tmp_path / "raw"
    man = Manifest(root / "m.json", root)
    status = classify(reqs, c["layout"], man, craei, c["local_source_country"])
    assert {s for r, s in status.items() if "/IND/" in r} == {DOWNLOAD}
    assert LOCAL_COPY in status.values()
    ch = load_craei_hashes(_craei_manifest(tmp_path, craei, hashes))
    res = copy_local(reqs, status, c, root, man, craei, ch)
    assert res["failed"] == [] and res["copied"] == sum(1 for s in status.values() if s == LOCAL_COPY)
    assert {p: p.read_bytes() for p in craei.rglob("*.nc")} == before
    assert man.verify() == {"missing": [], "size": [], "sha256": []}
    assert all(e["source_sha256"] == e["sha256"] and e["origin"] == "craei_local_copy" for e in man.entries.values())
    status2 = classify(reqs, c["layout"], man, craei, c["local_source_country"])
    assert IN_MANIFEST in status2.values() and LOCAL_COPY not in status2.values()
    assert not list(root.rglob("*.part"))


def test_local_copy_refuses_a_source_whose_hash_differs_from_the_craei_manifest(tmp_path, cfg):
    c = small_cfg(cfg)
    c["gcms"] = ["gfdl-esm4"]
    reqs, _ = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA"])
    craei, hashes = _craei_tree(tmp_path, c, reqs)
    victim = next(iter(hashes))
    hashes[victim] = "0" * 64
    root = tmp_path / "raw"
    man = Manifest(root / "m.json", root)
    res = copy_local(reqs, classify(reqs, c["layout"], man, craei, c["local_source_country"]), c, root, man, craei, load_craei_hashes(_craei_manifest(tmp_path, craei, hashes)))
    assert len(res["failed"]) == 1 and "differs from the CRAEI manifest" in res["failed"][0]["reason"]
    assert len(man.entries) == res["copied"]


def test_without_a_craei_hash_the_hash_is_computed_on_both_sides(tmp_path, cfg):
    c = small_cfg(cfg)
    c["gcms"] = ["gfdl-esm4"]
    reqs, _ = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA"])
    craei, _ = _craei_tree(tmp_path, c, reqs)
    root = tmp_path / "raw"
    man = Manifest(root / "m.json", root)
    res = copy_local(reqs, classify(reqs, c["layout"], man, craei, c["local_source_country"]), c, root, man, craei, {})
    assert res["failed"] == [] and {e["hash_reference"] for e in man.entries.values()} == {"computed_on_both_sides"}


# ---------------------------------------------------------------- size estimate
def test_crop_ratio_is_measured_on_local_files_and_scaled_by_cells(tmp_path, cfg):
    c = small_cfg(cfg)
    reqs, _ = build_requirements(c, Catalogue(c, FakeNet(c), sleep=no_sleep), ["BRA", "IND", "PRT"])
    craei, _ = _craei_tree(tmp_path, c, reqs)
    ratios = crop_ratios(reqs, craei, c["local_source_country"])
    assert ("atmosphere", "rsds") in ratios and ("atmosphere", "tas") in ratios  # tas takes the mean of the daily variables
    bra = next(r for r in reqs if r.country == "BRA" and r.variable == "tas")
    ind = next(r for r in reqs if r.country == "IND" and r.variable == "tas" and r.global_path == bra.global_path)
    e_b, e_i = estimate_bytes(bra, ratios, c["bboxes"]["BRA"]), estimate_bytes(ind, ratios, c["bboxes"]["BRA"])
    assert e_i == pytest.approx(e_b * grid_cells(c["bboxes"]["IND"]) / grid_cells(c["bboxes"]["BRA"]), abs=1)  # estimates are whole bytes


# ---------------------------------------------------------------- download
def _one_req(c, net, country="IND", variable="tas", scen="ssp126", gcm="gfdl-esm4"):
    reqs, _ = build_requirements(c, Catalogue(c, net, sleep=no_sleep), [country])
    return next(r for r in reqs if r.variable == variable and r.scenario == scen and r.gcm == gcm and r.start_year == 2041)


def _dl(tmp_path, c, net):
    root = tmp_path / "raw"
    man = Manifest(root / "m.json", root)
    return Downloader(c, net, root, man, tmp_path / "logs" / "jobs.json", root / "_staging", sleep=no_sleep), man, root


def test_download_registers_hash_url_date_and_bbox_and_leaves_no_partial(tmp_path, cfg):
    c = small_cfg(cfg)
    net = FakeNet(c)
    r = _one_req(c, net)
    dl, man, root = _dl(tmp_path, c, net)
    assert dl.fetch(r) == "downloaded"
    rel = r.rel_path(c["layout"])
    e = man.entries[rel]
    assert e["sha256"] == sha256_file(root / rel) and e["bbox"] == list(c["bboxes"]["IND"]) and e["origin"] == "isimip_server"
    assert e["url"].startswith("https://files.isimip.org/") and e["accessed_utc"].endswith("Z") and e["period"] == [2041, 2050]
    assert not list(root.rglob("*.part"))
    posts = [x for x in net.calls if x[0] == "POST"]
    assert posts[0][2]["operations"][0]["bbox"] == c["bboxes"]["IND"]
    assert dl.fetch(r) == "cached" and len([x for x in net.calls if x[0] == "POST"]) == 1


def test_download_resumes_a_partial_zip_and_a_saved_job(tmp_path, cfg):
    c = small_cfg(cfg)
    net = FakeNet(c)
    r = _one_req(c, net)
    dl, _, _ = _dl(tmp_path, c, net)
    net.fail_zip_get = 1  # the first transfer drops
    assert dl.fetch(r) == "downloaded"
    assert len([x for x in net.calls if x[0] == "POST"]) == 1  # the saved job was reused after the drop
    # a half-written zip left by a crash is completed through a Range request
    r2 = _one_req(c, net, scen="ssp585")
    path = r2.global_path
    dl2, _, root2 = _dl(tmp_path / "b", c, net)
    job_url = dl2._submit(r2, path)
    dl2._save_job(f"{path}|{list(r2.bbox)}", job_url)
    zurl = net.jobs[job_url]["file_url"]
    zpart = root2 / "_staging" / (zurl.rsplit("/", 1)[-1] + ".part")
    zpart.parent.mkdir(parents=True)
    zpart.write_bytes(net.zips[zurl][:20])
    assert dl2.fetch(r2) == "downloaded"
    rng = [x for x in net.calls if x[0] == "GET" and x[1] == zurl]
    assert rng, "the zip was fetched"


def test_a_failing_server_falls_back_to_the_global_file_and_crops_it(tmp_path, cfg, monkeypatch):
    c = small_cfg(cfg)
    net = FakeNet(c)
    r = dataclasses.replace(_one_req(c, net), global_checksum=None, global_checksum_type=None)
    net.break_cutout_for.add(r.global_path)
    net.global_files[f"{c['files_base']}/{r.global_path}"] = b"GLOBAL"
    monkeypatch.setattr("geofrea.climate_acquisition.download.crop_netcdf", lambda s, d, b: d.write_bytes(b"CROPPED:" + s.read_bytes()))
    dl, man, root = _dl(tmp_path, c, net)
    assert dl.fetch(r) == "downloaded"
    e = man.entries[r.rel_path(c["layout"])]
    assert e["origin"] == "isimip_server_global_crop" and (root / r.rel_path(c["layout"])).read_bytes() == b"CROPPED:GLOBAL"


def test_when_every_source_fails_nothing_enters_the_manifest(tmp_path, cfg):
    c = small_cfg(cfg)
    net = FakeNet(c)
    r = _one_req(c, net)
    net.break_cutout_for.add(r.global_path)
    dl, man, root = _dl(tmp_path, c, net)
    with pytest.raises(DownloadError):
        dl.fetch(r)
    assert man.entries == {} and not (root / r.rel_path(c["layout"])).exists()


def test_parallel_downloads_do_not_corrupt_the_job_file_or_the_manifest(tmp_path, cfg):
    from concurrent.futures import ThreadPoolExecutor

    c = small_cfg(cfg)
    net = FakeNet(c)
    reqs, _ = build_requirements(c, Catalogue(c, net, sleep=no_sleep), ["IND"])
    todo = [r for r in reqs if r.variable == "tas"][:24]
    dl, man, root = _dl(tmp_path, c, net)
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(dl.fetch, todo)) == ["downloaded"] * len(todo)
    assert len(json.loads((tmp_path / "logs" / "jobs.json").read_text(encoding="utf-8"))) == len({(r.global_path) for r in todo})
    assert len(Manifest(root / "m.json", root).entries) == len(todo)
    assert man.verify() == {"missing": [], "size": [], "sha256": []}


def test_crop_netcdf_cuts_the_box(tmp_path):
    import numpy as np
    import xarray as xr

    from geofrea.climate_acquisition.download import crop_netcdf

    lat, lon = np.arange(89.75, -90, -0.5), np.arange(-179.75, 180, 0.5)
    ds = xr.Dataset({"tas": (("time", "lat", "lon"), np.zeros((2, lat.size, lon.size), dtype="f4"))}, coords={"time": [0, 1], "lat": lat, "lon": lon})
    ds.to_netcdf(tmp_path / "g.nc")
    crop_netcdf(tmp_path / "g.nc", tmp_path / "c.nc", (68.0, 98.0, 6.0, 37.5))
    with xr.open_dataset(tmp_path / "c.nc") as out:
        assert out.lon.min() >= 68.0 and out.lon.max() <= 98.0 and out.lat.min() >= 6.0 and out.lat.max() <= 37.5
        assert out.sizes["lon"] == 60 and out.sizes["lat"] == 63


# ---------------------------------------------------------------- boundaries of the package
def test_nothing_is_imported_from_craei_and_adapted_files_carry_provenance():
    for f in SRC.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+craei\b", text, re.MULTILINE), f.name
    adapted = ["catalogue.py", "config.py", "download.py", "local_copy.py", "manifest.py", "plan.py"]
    for name in adapted:
        head = (SRC / name).read_text(encoding="utf-8")[:2500]
        assert "Provenance (A-11)" in head and "7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f" in head and "github.com/DougzSO/CRAEI" in head, name


def test_the_acquisition_config_is_read_by_no_phase():
    phases = Path(__file__).resolve().parents[2] / "src" / "geofrea"
    users = [p for p in phases.rglob("*.py") if "climate_acquisition" not in p.parts and "climate_acquisition.yaml" in p.read_text(encoding="utf-8")]
    assert users == []
