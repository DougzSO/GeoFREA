"""Reference turbine power curves, one file per curve in `config/turbines/` (M-F5-03; D-F5-003, D-F5-004).

A curve is a table of nodes `(v_ms, p_kw)`. The first node is the cut-in speed and may have a non-zero power (a tabulated model
output starts there); the last node is the declared cut-out. The power is zero below the cut-in and above the cut-out by rule, and
linear between nodes inside `[cut-in, cut-out]`; no node is added and nothing is extrapolated. A file is a `.csv` (provenance in `#`
header lines, then `wind_speed_ms,power_kw`) or a `.yaml` (the test curves). The file carries the provenance (U-05 fields); a curve
flagged `synthetic` is a test value and is refused in a production run (A-09). The curve also carries the air density it refers to
(`reference_density_kg_m3`, the `rho0` of the density correction). Which curve a technology uses lives in `technologies.yaml`
(`power_curve`), not here.
"""

from __future__ import annotations

import csv
import hashlib
from itertools import pairwise
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class PowerCurveError(ValueError):
    """A power curve file is malformed or cannot be used (A-09)."""


class SyntheticCurveError(PowerCurveError):
    """A curve flagged `synthetic` was asked for in a production run (A-09, D-F5-003)."""


class PowerCurve(BaseModel):
    """A reference power curve with its provenance.

    Args:
        curve_id: Identifier, equal to the file stem.
        iec_class: IEC class the curve stands for (free text, `S` or `synthetic` allowed).
        rated_power_kw: Rated power, kW, equal to the largest node power.
        v_ms: Node speeds, m/s, strictly increasing; the first node is the cut-in speed, the last the cut-out speed.
        p_kw: Node powers, kW, in [0, rated]; the first node may be non-zero (the power is zero below the cut-in).
        cut_in_ms: Cut-in speed, m/s; when declared it equals the first node speed.
        cut_out_ms: Declared cut-out speed, m/s, equal to the last node speed.
        reference_density_kg_m3: Air density the curve refers to (`rho0` of the density correction); `None` when the file does not
            say, and the caller then uses the standard-atmosphere constant.
        reference_density_verified: True only when the density was read from the model inputs the table was produced with.
        license, source_url, commit: Provenance of a table taken from a repository.
        synthetic: True for a test curve.
        source: Citation of the curve, required when not synthetic.
        tier: Evidence tier (U-07), required when not synthetic, `None` when synthetic.
        verified, verified_by, verified_date, verification_method: Verification metadata (U-05).
        note: Free-text caveat.
    """

    model_config = ConfigDict(extra="forbid")

    curve_id: str
    iec_class: str
    rated_power_kw: float
    v_ms: list[float]
    p_kw: list[float]
    cut_in_ms: float | None = None
    cut_out_ms: float
    reference_density_kg_m3: float | None = None
    reference_density_verified: bool = False
    synthetic: bool
    license: str | None = None
    source_url: str | None = None
    commit: str | None = None
    source: str | None = None
    tier: int | None = None
    verified: bool = False
    verified_by: str | None = None
    verified_date: str | None = None
    verification_method: str = "unverified"
    note: str | None = None

    @model_validator(mode="after")
    def _check_table(self) -> PowerCurve:
        v, p = self.v_ms, self.p_kw
        if len(v) != len(p) or len(v) < 2:
            raise ValueError("v_ms and p_kw need the same length, at least 2 nodes")
        if any(b <= a for a, b in pairwise(v)):
            raise ValueError("v_ms must be strictly increasing")
        if v[0] < 0:
            raise ValueError("v_ms must not be negative")
        if self.rated_power_kw <= 0:
            raise ValueError("rated_power_kw must be positive")
        if any(x < 0 or x > self.rated_power_kw for x in p):
            raise ValueError("p_kw must lie in [0, rated_power_kw]")
        if self.cut_in_ms is not None and self.cut_in_ms != v[0]:
            raise ValueError(
                f"cut_in_ms ({self.cut_in_ms}) must be the first node speed ({v[0]}): the curve starts at the cut-in"
            )
        if self.reference_density_kg_m3 is not None and self.reference_density_kg_m3 <= 0:
            raise ValueError("reference_density_kg_m3 must be positive")
        if max(p) != self.rated_power_kw:
            raise ValueError("rated_power_kw must equal the largest node power")
        if self.cut_out_ms != v[-1]:
            raise ValueError(
                f"cut_out_ms ({self.cut_out_ms}) must be the last node speed ({v[-1]}): the cut-out must be declared"
            )
        if self.synthetic and self.tier is not None:
            raise ValueError("a synthetic curve carries no evidence tier (U-07)")
        if not self.synthetic and (self.source is None or self.tier is None):
            raise ValueError(
                "a curve that is not synthetic needs a source and a tier (U-05, U-07); a placeholder real-looking curve breaks A-09"
            )
        return self

    @property
    def p_normalized(self) -> list[float]:
        """Node powers divided by the rated power, in [0, 1]."""
        return [x / self.rated_power_kw for x in self.p_kw]


_CSV_NUMBERS = {
    "rated_power_kw",
    "cut_in_ms",
    "cut_out_ms",
    "reference_density_kg_m3",
    "tier",
}
_CSV_BOOLS = {"synthetic", "verified", "reference_density_verified"}


def _read_csv_curve(path: Path) -> dict:
    """The fields of a `.csv` curve: `# key: value` header lines, then `wind_speed_ms,power_kw` rows."""
    header: dict[str, object] = {}
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            key, sep, value = line[1:].partition(":")
            if not sep:
                continue
            key, value = key.strip(), value.strip()
            if key in _CSV_NUMBERS:
                header[key] = float(value) if value.lower() != "null" else None
            elif key in _CSV_BOOLS:
                header[key] = value.lower() == "true"
            else:
                header[key] = None if value.lower() == "null" else value
        else:
            rows.append(line)
    reader = csv.reader(rows)
    names = next(reader, None)
    if names is None or [n.strip() for n in names] != ["wind_speed_ms", "power_kw"]:
        raise PowerCurveError(f"{path}: the columns must be wind_speed_ms,power_kw (got {names})")
    v_ms, p_kw = [], []
    for row in reader:
        v_ms.append(float(row[0]))
        p_kw.append(float(row[1]))
    if "tier" in header and header["tier"] is not None:
        header["tier"] = int(header["tier"])  # type: ignore[call-overload]
    header["v_ms"] = v_ms
    header["p_kw"] = p_kw
    return header


def curve_path(curves_dir: Path, curve_id: str) -> Path | None:
    """The file of `curve_id` in `curves_dir`, `.csv` before `.yaml`, or `None` when neither exists."""
    for suffix in (".csv", ".yaml"):
        candidate = Path(curves_dir) / f"{curve_id}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def load_power_curve(path: Path) -> PowerCurve:
    """Read and validate a curve file (`.csv` or `.yaml`); the file stem must equal `curve_id`.

    Implements: M-F5-03.

    Raises:
        PowerCurveError: the file is missing, is malformed, fails validation, or its stem differs from `curve_id`.
    """
    path = Path(path)
    if not path.is_file():
        raise PowerCurveError(f"power curve file not found: {path}")
    if path.suffix == ".csv":
        try:
            data = _read_csv_curve(path)
        except ValueError as exc:
            raise PowerCurveError(f"{path}: {exc}") from exc
    else:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PowerCurveError(f"{path}: expected a mapping at the top level")
    try:
        curve = PowerCurve.model_validate(data)
    except ValueError as exc:
        raise PowerCurveError(f"{path}: {exc}") from exc
    if curve.curve_id != path.stem:
        raise PowerCurveError(
            f"{path}: curve_id {curve.curve_id!r} differs from the file stem {path.stem!r}"
        )
    return curve


def curve_file_sha256(path: Path) -> str:
    """SHA-256 of the curve file, recorded in the potential tables and the manifest so a change of curve invalidates F5 (A-02)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_curve_usable(curve: PowerCurve, production: bool) -> None:
    """Refuse a synthetic curve in a production run.

    Implements: M-F5-03.

    Raises:
        SyntheticCurveError: `production` is true and the curve is synthetic.
    """
    if production and curve.synthetic:
        raise SyntheticCurveError(
            f"curve {curve.curve_id!r} is synthetic (a test value) and cannot be used in a production run (D-F5-003)"
        )
