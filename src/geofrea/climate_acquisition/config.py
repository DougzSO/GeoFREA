"""Configuration and the requirement record of the ISIMIP3b acquisition (config/climate_acquisition.yaml).

Provenance (A-11). Adapted from the CRAEI repository (https://github.com/DougzSO/CRAEI.git, commit
7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f), files `src/craei/acquire/isimip.py` and `src/craei/acquire/isimip_layer.py`
(job definition, decade-file overlap, bounding-box cut-out on the ISIMIP server). Adaptation: the job list is the
requirement matrix below, the output goes to the manifest of this package, and nothing is imported from CRAEI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "climate_acquisition.yaml"
ATMOSPHERE = "atmosphere"
WATER = "water"


def load_config(path: Path | None = None) -> dict:
    """Read the acquisition configuration."""
    return yaml.safe_load((path or CONFIG_PATH).read_text(encoding="utf-8"))


def bbox_tag(bbox: list[float]) -> str:
    """The longitude and latitude tag the ISIMIP server writes in a cut-out file name."""
    west, east, south, north = (float(v) for v in bbox)
    return f"lon{west}to{east}lat{south}to{north}"


def grid_cells(bbox: list[float], step: float = 0.5) -> int:
    """Number of 0.5 degree cells of a box (ISIMIP3b native grid)."""
    west, east, south, north = (float(v) for v in bbox)
    return round((east - west) / step) * round((north - south) / step)


@dataclass(frozen=True)
class Requirement:
    """One file the v2 climate channel needs: a (variable, GCM, [GHM], scenario, country) cut of a global ISIMIP file."""

    family: str  # "atmosphere" or "water"
    variable: str
    gcm: str
    ghm: str | None
    scenario: str
    country: str
    bbox: tuple[float, float, float, float]
    global_path: str  # path of the global file in the ISIMIP repository
    global_bytes: int
    global_checksum: str | None
    global_checksum_type: str | None
    time_step: str
    start_year: int
    end_year: int
    soc: str | None = None

    @property
    def global_name(self) -> str:
        return self.global_path.rsplit("/", 1)[-1]

    @property
    def name(self) -> str:
        """Name of the cut-out file: the global name with `global` replaced by the box tag."""
        return self.global_name.replace("_global_", f"_{bbox_tag(list(self.bbox))}_", 1)

    def rel_dir(self, layout: dict) -> str:
        return layout[self.family].format(
            country=self.country, gcm=self.gcm, ghm=self.ghm, scenario=self.scenario, variable=self.variable
        )

    def rel_path(self, layout: dict) -> str:
        return f"{self.rel_dir(layout)}/{self.name}"

    def as_dict(self) -> dict:
        return {
            "family": self.family,
            "variable": self.variable,
            "gcm": self.gcm,
            "ghm": self.ghm,
            "scenario": self.scenario,
            "country": self.country,
            "bbox": list(self.bbox),
            "global_path": self.global_path,
            "global_bytes": self.global_bytes,
            "global_checksum": self.global_checksum,
            "global_checksum_type": self.global_checksum_type,
            "time_step": self.time_step,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "soc": self.soc,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Requirement:
        d = dict(d)
        d["bbox"] = tuple(d["bbox"])
        return cls(**d)
