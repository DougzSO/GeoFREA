"""Reference turbine power curves, one file per curve in `config/power_curves/` (M-F5-03; D-F5-003, D-F5-004).

A curve is a table of nodes `(v_ms, p_kw)` read as piecewise linear between nodes. Below the first node (where the power is zero)
and above the last node (the declared cut-out) the power is zero. The file carries the provenance (U-05 fields); a curve flagged
`synthetic` is a test value and is refused in a production run (A-09). A curve describes a turbine; which curve a site gets is a
siting rule and lives in `technologies.yaml` (`iec_class_rule`, `power_curves`), not here.
"""

from __future__ import annotations

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
        v_ms: Node speeds, m/s, strictly increasing; the last node is the cut-out speed.
        p_kw: Node powers, kW, in [0, rated]; the first node has zero power.
        cut_out_ms: Declared cut-out speed, m/s, equal to the last node speed.
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
    cut_out_ms: float
    synthetic: bool
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
        if p[0] != 0:
            raise ValueError("the first node must have zero power (the curve is zero below it)")
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


def load_power_curve(path: Path) -> PowerCurve:
    """Read and validate a curve file; the file stem must equal `curve_id`.

    Implements: M-F5-03.

    Raises:
        PowerCurveError: the file is missing, is not a mapping, fails validation, or its stem differs from `curve_id`.
    """
    path = Path(path)
    if not path.is_file():
        raise PowerCurveError(f"power curve file not found: {path}")
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
