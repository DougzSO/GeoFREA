"""ISIMIP catalogue queries and the requirement matrix of the v2 climate channel.

Provenance (A-11). Adapted from the CRAEI repository (https://github.com/DougzSO/CRAEI.git, commit
7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f): `src/craei/acquire/isimip.py` (`dataset_paths`, `dataset_paths_by_pattern`,
`_file_overlaps`, the retry on the metadata API and the variant label of UKESM1-0-LL) and
`src/craei/acquire/isimip_layer.py` (`search`, host check). Adaptation: the HTTP session is injected so the code runs
against a simulated network, and a gap in the catalogue is returned as data instead of an exception.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from .config import ATMOSPHERE, WATER, Requirement


class CatalogueError(RuntimeError):
    """The catalogue could not be read after the retries."""


class HostError(ValueError):
    """A URL outside isimip.org was requested."""


# Variant label of each GCM in the ISIMIP3b file names, used only by the pattern fallback.
VARIANT_LABEL = {"ukesm1-0-ll": "r1i1p1f2"}
DEFAULT_VARIANT_LABEL = "r1i1p1f1"
GHM_DIR = {"cwatm": "CWatM", "h08": "H08", "miroc-integ-land": "MIROC-INTEG-LAND", "watergap2-2e": "WaterGAP2-2e"}


def check_host(url: str, allowed: set[str] | None = None) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host != "isimip.org" and not host.endswith(".isimip.org") and host not in (allowed or set()):
        raise HostError(f"host not authorised for the ISIMIP acquisition: {host}")
    return url


def file_years(name: str) -> tuple[int, int] | None:
    m = re.search(r"_(\d{4})_(\d{4})\.nc$", name)
    return (int(m.group(1)), int(m.group(2))) if m else None


def overlaps(name: str, start: int, end: int) -> bool:
    years = file_years(name)
    return years is not None and years[0] <= end and years[1] >= start


class Catalogue:
    """Read-only client of the ISIMIP data API (`data.isimip.org`)."""

    def __init__(self, cfg: dict, session, sleep=time.sleep, allowed_hosts: set[str] | None = None):
        self.cfg = cfg
        self.session = session
        self.sleep = sleep
        self.allowed = allowed_hosts or set()
        self.retries = int(cfg["download"]["retries"])
        self.consulted: list[str] = []

    def _get_json(self, url: str, params: dict | None) -> dict:
        check_host(url, self.allowed)
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, params=params, timeout=60)
                self.consulted.append(getattr(resp, "url", url))
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - any transport or HTTP error is retried the same way
                last = exc
                self.sleep(15 * (attempt + 1))
        raise CatalogueError(f"{url} {params}: {last}")

    def search(self, **spec) -> list[dict]:
        """All datasets that match `spec`, following the `next` links."""
        out: list[dict] = []
        url, params = f"{self.cfg['data_api']}/datasets/", dict(spec, page_size=200)
        while url:
            doc = self._get_json(url, params)
            out += doc["results"]
            url, params = doc.get("next"), None
        return out

    def atmosphere_dataset(self, variable: str, gcm: str, scenario: str) -> dict | None:
        found = [
            d for d in self.search(
                simulation_round=self.cfg["simulation_round"], climate_variable=variable, climate_forcing=gcm,
                climate_scenario=scenario, bias_adjustment="w5e5",
            )
            if d["specifiers"].get("product") == "InputData"
            and d["specifiers"].get("time_step") == self.cfg["atmosphere"]["time_step"]
        ]
        return found[0] if found else None

    def water_datasets(self, ghm: str, gcm: str, scenario: str, variable: str) -> list[dict]:
        w = self.cfg["water"]
        return self.search(
            simulation_round=self.cfg["simulation_round"], product="OutputData", sector=w["sector"], model=ghm,
            climate_forcing=gcm, climate_scenario=scenario, variable=variable,
        )

    def head_ok(self, path: str) -> bool:
        """The global file exists on the files server (used by the pattern fallback)."""
        resp = self.session.head(f"{self.cfg['files_base']}/{path}", timeout=20, allow_redirects=True)
        return resp.status_code == 200


def pattern_paths(cfg: dict, variable: str, gcm: str, scenario: str, start: int, end: int) -> list[str]:
    """Daily atmosphere file paths from the decade naming convention, for when the catalogue is unreachable.

    The historical experiment ends in 2014, so its last block is 2011-2014; the future blocks are plain decades.
    """
    label = VARIANT_LABEL.get(gcm, DEFAULT_VARIANT_LABEL)
    ceiling = 2014 if scenario == cfg["historical_scenario"] else None
    first = start - ((start - 1) % 10)
    paths = []
    for d_start in range(first, end + 1, 10):
        d_end = min(d_start + 9, ceiling) if ceiling else d_start + 9
        name = f"{gcm}_{label}_w5e5_{scenario}_{variable}_global_daily_{d_start}_{d_end}.nc"
        paths.append(
            f"{cfg['simulation_round']}/InputData/climate/atmosphere/bias-adjusted/global/daily/{scenario}/{gcm.upper()}/{name}"
        )
    return paths


def _pick_water(cfg: dict, scenario: str, datasets: list[dict]) -> tuple[dict | None, str | None]:
    """The dataset of the wanted human-forcing scenario and monthly step; else the time step that is on offer instead."""
    w = cfg["water"]
    want = w["historical_soc"] if scenario == cfg["historical_scenario"] else w["future_soc_prefix"]
    same_soc = [
        d for d in datasets
        if (soc := str(d["specifiers"].get("soc_scenario", ""))) == want or (scenario != cfg["historical_scenario"] and soc.startswith(want))
    ]
    for d in same_soc:
        if d["specifiers"].get("time_step", w["time_step"]) == w["time_step"]:
            return d, None
    return None, (str(same_soc[0]["specifiers"].get("time_step")) if same_soc else None)


def build_requirements(cfg: dict, cat: Catalogue, countries: list[str], fallback_water: dict | None = None):
    """The matrix of files the v2 channel needs, and the gaps found while building it.

    Returns `(requirements, gaps)`. A gap is a dict with the family, the key of the missing combination, the reason
    and the URLs consulted; its pair is not downloaded (the others proceed).
    """
    reqs: list[Requirement] = []
    gaps: list[dict] = []
    scenarios = [cfg["historical_scenario"], *cfg["scenarios"]]
    ref, fut = cfg["reference_window"], cfg["future_window"]

    for variable in cfg["atmosphere"]["variables"]:
        for gcm in cfg["gcms"]:
            for scen in scenarios:
                span = ref if scen == cfg["historical_scenario"] else fut
                key = f"{variable}/{gcm}/{scen}"
                try:
                    ds = cat.atmosphere_dataset(variable, gcm, scen)
                except CatalogueError:
                    ds = None
                    files = [
                        {"path": p, "name": p.rsplit("/", 1)[-1], "size": 0, "checksum": None, "checksum_type": None}
                        for p in pattern_paths(cfg, variable, gcm, scen, span["start"], span["end"])
                        if cat.head_ok(p)
                    ]
                else:
                    files = ds["files"] if ds else []
                files = [f for f in files if overlaps(f["name"], span["start"], span["end"])]
                if not files:
                    gaps.append({"family": ATMOSPHERE, "key": key, "reason": "no daily file in the catalogue for the window",
                                 "urls": list(cat.consulted[-2:])})
                    continue
                for f in files:
                    y0, y1 = file_years(f["name"])  # type: ignore[misc]
                    for country in countries:
                        reqs.append(Requirement(
                            ATMOSPHERE, variable, gcm, None, scen, country, tuple(cfg["bboxes"][country]), f["path"],
                            int(f.get("size") or 0), f.get("checksum"), f.get("checksum_type"),
                            cfg["atmosphere"]["time_step"], y0, y1,
                        ))

    w = cfg["water"]
    for ghm in w["ghms"]:
        for gcm in cfg["gcms"]:
            for scen in scenarios:
                for variable in w["variables"]:
                    key = f"{variable}/{ghm}/{gcm}/{scen}"
                    other_step = None
                    try:
                        ds, other_step = _pick_water(cfg, scen, cat.water_datasets(ghm, gcm, scen, variable))
                    except CatalogueError:
                        ds = None
                    entry = None
                    if ds is None and other_step is not None:
                        gaps.append({"family": WATER, "key": key, "reason": f"time step {other_step} differs from {w['time_step']}",
                                     "urls": list(cat.consulted[-2:])})
                        continue
                    if ds is not None:
                        f = ds["files"][0]
                        entry = (f["path"], int(f.get("size") or 0), f.get("checksum"), f.get("checksum_type"),
                                 ds["specifiers"].get("soc_scenario"))
                    elif fallback_water and key in fallback_water:
                        p, soc = fallback_water[key]
                        entry = (p, 0, None, None, soc)
                    if entry is None:
                        gaps.append({"family": WATER, "key": key, "reason": "no dataset in the catalogue for the pair",
                                     "urls": list(cat.consulted[-2:])})
                        continue
                    y = file_years(entry[0].rsplit("/", 1)[-1]) or (0, 0)
                    for country in countries:
                        reqs.append(Requirement(
                            WATER, variable, gcm, ghm, scen, country, tuple(cfg["bboxes"][country]), entry[0], entry[1],
                            entry[2], entry[3], w["time_step"], y[0], y[1], entry[4],
                        ))
    return reqs, gaps
