"""Decompose the change of the eligible area caused by Group 6 (COMMAND 97), by criterion, per country, technology and scenario.

Two steps, run around the Group 6 round of a country:

    python scripts/report_group6_decomposition.py snapshot PRT IND BRA   # BEFORE the round: keep the pre-Group 6 numbers
    python scripts/report_group6_decomposition.py report PRT             # AFTER F3 of that country

`snapshot` reads the last accepted round of the reference store (`GeoFREA_data/references/latest.json`, or `--reference-run <run_id>`): its
`land_eligibility.json` is the authority for the eligible area of every technology and scenario. The per-criterion excluded areas are in the cell tables
of that round (`outputs/<ISO>/land_eligibility/artifacts/cells_<tech>__<scenario>.parquet`), which the store does not keep and the new round overwrites; the
snapshot sums them and refuses them (A-09) unless their eligible area equals the reference summary, so a table of another round is never taken for the
reference. The snapshot is written to `GeoFREA_data/archive/group6_pre/<ISO>.json`.

`report` reads the snapshot and the new tables and summary and writes `docs/_audit/group6_decomposition/<ISO>.csv` and `.md`.

Method (the same for every row). With `C` the area of the cells, `X_k` the area excluded by criterion k (`excluded_area_km2_Ek` of the cell table) and
`e_k = X_k / C`, the eligible fraction is a product of the pixels' `1 - e_k` terms, so the log of the ratio of the areas is, to first order, the sum of
`d_k = ln(1 - e_k_new) - ln(1 - e_k_old)`. The change of the area before the minimum-area rules is attributed in proportion to `d_k`:
`attribution_k = A_old * expm1(S) / S * d_k`, `S = sum d_k`; what the product does not explain (the exclusions overlap, so they are not independent) is the
`interaction` term, `(A_pre - A_old) - A_old * expm1(S)`. The minimum-area rules are exact: `A_new - A_pre`, from the summary of the scenario. The criteria
are: `settlements` (E6 of Group 6), `density_removed` (E6 of the density rule, which no scenario keeps), `slope` (E4), `rivers` (E3), `other` (E1, E2 and E5,
unchanged by Group 6: a non-zero value is a finding, not noise). The terms add up to the total change by construction, and the interaction is always reported.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TECHNOLOGIES = ("solar", "wind")
SCENARIOS = ("restrictive", "central", "permissive")
CONSTRAINTS = ("E1", "E2", "E3", "E4", "E5", "E6")
RELATIVE_TOLERANCE = 1e-6
CRITERIA = ("settlements", "density_removed", "slope", "rivers", "other")
THRESHOLD_CRITERIA = ("rivers", "settlements", "density", "slope", "elevation", "min_area")


class DecompositionError(RuntimeError):
    """The inputs of the decomposition do not belong together (A-09: fail loud, name the file)."""


def table_sums(path: Path) -> dict:
    """The sums of a cell table that the decomposition uses: cell area, eligible area and the excluded area of each criterion (km2)."""
    table = pd.read_parquet(path)
    sums = {
        "cell_area_km2": float(table["cell_area_km2"].sum()),
        "eligible_area_km2": float(table["eligible_area_km2"].sum()),
    }
    for c in CONSTRAINTS:
        sums[f"excluded_E{c[1]}_km2"] = float(table[f"excluded_area_km2_{c}"].sum())
    return sums


def reference_summary(data_root: Path, iso: str, run_id: str | None) -> Path:
    """The `land_eligibility.json` of the reference store for `iso`: the run `run_id`, or the one `latest.json` names."""
    store = data_root / "references"
    if run_id is None:
        latest = json.loads((store / "latest.json").read_text(encoding="utf-8"))
        if iso not in latest:
            raise DecompositionError(f"{store / 'latest.json'} has no accepted round for {iso}")
        run_id = latest[iso]
    path = store / run_id / iso / "files" / "outputs" / iso / "artifacts" / "land_eligibility.json"
    if not path.is_file():
        raise DecompositionError(f"the reference round {run_id} of {iso} keeps no land_eligibility.json: {path}")
    return path


def snapshot(summary_path: Path, tables_dir: Path, iso: str, reference: str) -> dict:
    """The per-criterion sums of the pre-Group 6 round, checked against the eligible area of its summary.

    Raises:
        DecompositionError: a table of `tables_dir` does not add up to the eligible area of `summary_path`.
    """
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    out: dict = {"iso": iso, "reference": reference, "summary": str(summary_path), "technologies": {}}
    for tech, block in summary["technologies"].items():
        out["technologies"][tech] = {}
        for scenario, sc in block["scenarios"].items():
            path = tables_dir / Path(str(sc["cells"]).split(":", 1)[-1]).name
            if not path.is_file():
                raise DecompositionError(f"{iso} {tech} {scenario}: the cell table {path} of the reference round is missing")
            sums = table_sums(path)
            expected = float(sc["eligible_area_km2"])
            if not math.isclose(sums["eligible_area_km2"], expected, rel_tol=RELATIVE_TOLERANCE, abs_tol=1e-6):
                raise DecompositionError(
                    f"{iso} {tech} {scenario}: {path.name} holds {sums['eligible_area_km2']:.6f} km2 eligible but the reference summary says "
                    f"{expected:.6f}: the table is not the one of the reference round, nothing was written"
                )
            sums["parameter_set"] = sc.get("parameter_set")
            out["technologies"][tech][scenario] = sums
    return out


def _g(value: float) -> str:
    return f"{value:g}"


def threshold_texts(old: dict, new: dict, settlement_min_class: int) -> dict:
    """The old and the new limit of each criterion as text, from the `parameter_set` of the pre-Group 6 snapshot and of the new summary.

    Args:
        old: `parameter_set` of the scenario in the snapshot (slope in degrees, riparian setback in km, density, `min_eligible_area_km2`).
        new: `parameter_set` of the scenario in the new summary (slope in percent, river width model, settlement setback, cluster and pixel floors).
        settlement_min_class: `land_availability.settlements.min_class` (GHS-SMOD class from which a pixel is a settlement).

    Returns:
        `{<criterion>_old, <criterion>_new}` for the criteria of `THRESHOLD_CRITERIA`.
    """

    def limit(value, unit):
        return "no limit" if value is None else f"{_g(value)} {unit}"

    steps = new["river_buffer_steps"]
    if len(steps) == 1:
        buffers = f"buffer {_g(steps[0][1])} m"
    else:
        buffers = "buffer " + "/".join(_g(b) for _, b in steps) + " m (width < " + "/".join(_g(w) for w, _ in steps[:-1]) + " m)"
    floors = []
    if new.get("min_cluster_km2") is not None:
        floors.append(f"cluster >= {new['min_cluster_km2']:.2f} km2")
    if new.get("min_pixel_fraction") is not None:
        floors.append(f"pixel fraction >= {_g(new['min_pixel_fraction'])}")
    return {
        "rivers_old": f"setback {_g(old['riparian_setback_km'] * 1000)} m; streams with Q >= {_g(old['riparian_min_discharge_m3s'])} m3/s",
        "rivers_new": f"W = {_g(new['river_width_coefficient'])} Q^{_g(new['river_width_exponent'])}, {buffers}",
        "settlements_old": "none (density rule)",
        "settlements_new": f"GHS-SMOD class >= {settlement_min_class}, setback {_g(new['settlement_setback_m'])} m",
        "density_old": limit(old["pop_density_max_per_km2"], "persons/km2"),
        "density_new": limit(new["pop_density_max_per_km2"], "persons/km2") if new["pop_density_max_per_km2"] is not None else "not applied",
        "slope_old": f"{_g(old['slope_max_deg'])} deg ({100 * math.tan(math.radians(old['slope_max_deg'])):.1f} %)",
        "slope_new": f"{_g(new['slope_max_pct'])} % ({math.degrees(math.atan(new['slope_max_pct'] / 100)):.2f} deg)",
        "elevation_old": limit(old["elevation_max_m"], "m"),
        "elevation_new": limit(new["elevation_max_m"], "m"),
        "min_area_old": f"cell >= {_g(old['min_eligible_area_km2'])} km2",
        "min_area_new": "; ".join(floors) if floors else "no floor",
    }


def decompose(old: dict, new: dict, min_area: dict | None) -> dict:
    """One row of the decomposition from the sums of the old and the new scenario (see the module docstring for the method).

    Args:
        old: `table_sums` of the pre-Group 6 table of the scenario.
        new: `table_sums` of the new table.
        min_area: `min_area` of the new scenario summary (`area_before_km2`, `area_removed_by_*_km2`), None when the scenario has no minimum-area rule.
    """
    if not math.isclose(old["cell_area_km2"], new["cell_area_km2"], rel_tol=1e-9):
        raise DecompositionError("the old and the new tables do not cover the same cell area (another grid?)")
    cell_area = old["cell_area_km2"]
    a_old, a_new = old["eligible_area_km2"], new["eligible_area_km2"]
    if min_area is None:
        a_pre = a_new
        pixel_floor = cluster_floor = 0.0
    else:
        a_pre = float(min_area["area_before_km2"])
        pixel_floor = float(min_area["area_removed_by_pixel_floor_km2"])
        cluster_floor = float(min_area["area_removed_by_cluster_floor_km2"])
        if not math.isclose(a_pre - pixel_floor - cluster_floor, a_new, rel_tol=1e-6, abs_tol=1e-3):
            raise DecompositionError(
                f"the minimum-area record ({a_pre} - {pixel_floor} - {cluster_floor}) does not give the eligible area of the table ({a_new})"
            )
    d = {}
    for c in CONSTRAINTS:
        e_old, e_new = old[f"excluded_{c}_km2"] / cell_area, new[f"excluded_{c}_km2"] / cell_area
        d[c] = math.log1p(-e_new) - math.log1p(-e_old)
    terms = {
        "settlements": math.log1p(-new["excluded_E6_km2"] / cell_area),
        "density_removed": -math.log1p(-old["excluded_E6_km2"] / cell_area),
        "slope": d["E4"],
        "rivers": d["E3"],
        "other": d["E1"] + d["E2"] + d["E5"],
    }
    total_log = sum(terms.values())
    gain = a_old * (math.expm1(total_log) / total_log if abs(total_log) > 1e-12 else 1.0)
    row = {
        "area_old_km2": a_old,
        "area_before_min_area_km2": a_pre,
        "area_new_km2": a_new,
        "change_km2": a_new - a_old,
        "change_pct": 100.0 * (a_new - a_old) / a_old if a_old else float("nan"),
    }
    for name in CRITERIA:
        row[f"{name}_km2"] = gain * terms[name]
    row["interaction_km2"] = (a_pre - a_old) - a_old * math.expm1(total_log)
    row["min_area_km2"] = a_new - a_pre
    row["min_area_pixel_floor_km2"] = -pixel_floor
    row["min_area_cluster_floor_km2"] = -cluster_floor
    for c in CONSTRAINTS:
        row[f"excluded_{c}_old_km2"] = old[f"excluded_{c}_km2"]
        row[f"excluded_{c}_new_km2"] = new[f"excluded_{c}_km2"]
    parts = sum(row[f"{n}_km2"] for n in CRITERIA) + row["interaction_km2"] + row["min_area_km2"]
    if not math.isclose(parts, row["change_km2"], rel_tol=1e-9, abs_tol=1e-6):
        raise DecompositionError(f"the terms add up to {parts} km2 and the change is {row['change_km2']} km2")
    return row


def build_report(snap: dict, summary_path: Path, tables_dir: Path, settlement_min_class: int = 13) -> list[dict]:
    """The rows (technology x scenario) of the decomposition of one country from its snapshot and its new summary and tables."""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = []
    for tech in TECHNOLOGIES:
        if tech not in snap["technologies"] or tech not in summary["technologies"]:
            raise DecompositionError(f"{snap['iso']}: technology {tech!r} is missing from the snapshot or from the new summary")
        for scenario in SCENARIOS:
            sc = summary["technologies"][tech]["scenarios"][scenario]
            path = tables_dir / Path(str(sc["cells"]).split(":", 1)[-1]).name
            new = table_sums(path)
            if not math.isclose(new["eligible_area_km2"], float(sc["eligible_area_km2"]), rel_tol=RELATIVE_TOLERANCE, abs_tol=1e-6):
                raise DecompositionError(f"{path.name} does not add up to the eligible area of the new summary")
            row = decompose(snap["technologies"][tech][scenario], new, sc.get("min_area"))
            limits = threshold_texts(snap["technologies"][tech][scenario]["parameter_set"], sc["parameter_set"], settlement_min_class)
            rows.append({"country": snap["iso"], "technology": tech, "scenario": scenario, **row, **limits})
    return rows


def write_report(rows: list[dict], out_dir: Path, iso: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = out_dir / f"{iso}.csv", out_dir / f"{iso}.md"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    head = ["technology", "scenario", "area_old_km2", "area_new_km2", "change_pct", *[f"{n}_km2" for n in CRITERIA], "interaction_km2", "min_area_km2"]
    lines = [
        f"# Group 6: change of the eligible area, {iso}",
        "",
        "Areas in km2 (`change_km2` = sum of the criteria + interaction + minimum area). Method: `scripts/report_group6_decomposition.py`.",
        "",
        "| " + " | ".join(head) + " |",
        "|" + "|".join("---" for _ in head) + "|",
    ]
    for r in rows:
        cells = [str(r[h]) if isinstance(r[h], str) else (f"{r[h]:.2f}" if h == "change_pct" else f"{r[h]:,.1f}") for h in head]
        lines.append("| " + " | ".join(cells) + " |")
    if all(f"{c}_old" in rows[0] for c in THRESHOLD_CRITERIA):
        lines += ["", f"## Limits of each criterion, old (before Group 6) and new, {iso}", ""]
        head2 = ["technology", "scenario", *[f"{c}_{v}" for c in THRESHOLD_CRITERIA for v in ("old", "new")]]
        lines += ["| " + " | ".join(head2) + " |", "|" + "|".join("---" for _ in head2) + "|"]
        lines += ["| " + " | ".join(str(r[h]) for h in head2) + " |" for r in rows]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return csv_path, md_path


def _settlement_min_class() -> int:
    """`land_availability.settlements.min_class` of `config/experiments.yaml`."""
    import yaml

    config = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    return int(config["land_availability"]["settlements"]["min_class"])


def _data_root() -> Path:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    from geofrea.core import paths

    return paths.data_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="before the round: keep the pre-Group 6 numbers of the countries")
    snap.add_argument("countries", nargs="+")
    snap.add_argument("--reference-run", default=None)
    snap.add_argument("--data-root", type=Path, default=None)
    rep = sub.add_parser("report", help="after F3 of a country: the decomposition")
    rep.add_argument("countries", nargs="+")
    rep.add_argument("--data-root", type=Path, default=None)
    rep.add_argument("--out", type=Path, default=REPO / "docs" / "_audit" / "group6_decomposition")
    args = parser.parse_args(argv)
    root = args.data_root or _data_root()

    status = 0
    for iso in args.countries:
        snapshot_path = root / "archive" / "group6_pre" / f"{iso}.json"
        tables = root / "outputs" / iso / "land_eligibility" / "artifacts"
        try:
            if args.command == "snapshot":
                if snapshot_path.exists():
                    raise DecompositionError(f"{snapshot_path} exists: the pre-Group 6 numbers are kept once and never overwritten")
                summary = reference_summary(root, iso, args.reference_run)
                result = snapshot(summary, tables, iso, reference=summary.parents[5].name)
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path.write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
                print(f"{iso}: snapshot of the reference round {result['reference'][:12]} written to {snapshot_path}")
            else:
                if not snapshot_path.is_file():
                    raise DecompositionError(f"no snapshot of {iso}: run `snapshot {iso}` before the Group 6 round")
                rows = build_report(
                    json.loads(snapshot_path.read_text(encoding="utf-8")),
                    root / "outputs" / iso / "artifacts" / "land_eligibility.json",
                    tables,
                    _settlement_min_class(),
                )
                csv_path, md_path = write_report(rows, args.out, iso)
                print(f"{iso}: decomposition written to {csv_path} and {md_path}")
        except (DecompositionError, FileNotFoundError, KeyError) as error:
            print(f"{iso}: {error}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
