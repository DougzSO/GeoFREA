"""Titles and labels of the common map style (COMMAND 66): `Country · Technology · Variable`, subtitle `Scenario · Climate`, the country in
English (or Portuguese), no internal id, no cell count, no raw model name, no known typo anywhere in the sources."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
TITLE = re.compile(r"^[^·\n]+ · [^·\n]+ · [^·\n]+$")


def _map(**kwargs):
    country = synthetic_country("wide")
    args = {
        "iso": "BRA",
        "technology": "Wind",
        "variable": "Capacity density",
        "label": "MW/km²",
        "tech": "wind",
        "scenario": "Central",
        "climate": "Reference climate",
    }
    args.update(kwargs)
    return ms.raster_map(country.grid, country.grid_extent, country.geometry, **args)


@pytest.mark.parametrize(
    "iso,name",
    [
        ("BRA", "Brazil"),
        ("PRT", "Portugal"),
        ("IND", "India"),
        ("IDN", "Indonesia"),
        ("CHE", "Switzerland"),
    ],
)
def test_the_country_is_named_in_english(iso, name):
    assert ms.country_name(iso) == name


def test_the_country_can_be_named_in_portuguese():
    assert ms.country_name("BRA", "pt") == "Brasil" and ms.country_name("IND", "pt") == "Índia"
    assert ms.country_name("PRT", "pt") == "Portugal"
    with pytest.raises(ValueError):
        ms.country_name("BRA", "fr")


def test_an_unknown_code_asks_for_the_name():
    with pytest.raises(ValueError):
        ms.country_name("QQQ")


def test_the_title_has_the_three_parts_and_the_name_of_the_country():
    canvas = _map()
    title = canvas.texts["title"].get_text().replace("\n", " ")
    assert title == "Brazil · Wind · Capacity density" and TITLE.match(title)
    assert canvas.texts["subtitle"].get_text().startswith("Central · Reference climate")
    assert "BRA" not in title


def test_the_title_never_shows_the_code_of_the_country():
    with pytest.raises(ValueError):
        ms.format_title("BRA", "Wind", "Capacity density")


@pytest.mark.parametrize(
    "text",
    [
        "Brazil · Wind · open questions OQ-046 to OQ-049",
        "Brazil · Wind · OQ046",
        "BRA · m_access_cm2_ssp370_2041_2070",
        "Brazil · 286043 cells",
        "Brazil · 1,204 grid cells",
        "Brazil · capacity_factor_wind",
        "Central · ssp370",
        "see L-047",
        "D-F5-031 applies",
        "Brazil · COMMAND 59",
        "Brazil · Wind · elgible share",
        "Portugal · Solar · Potental",
    ],
)
def test_internal_ids_cell_counts_and_typos_are_refused(text):
    with pytest.raises(ValueError):
        ms.validate_label(text)


@pytest.mark.parametrize(
    "text",
    [
        "Brazil · Wind · Capacity density",
        "Central · Reference climate",
        "MW per cell",
        "Eligible share of land",
        "SSP3-7.0 · 2071-2100 vs 1995-2014",
        "Boundaries: GADM 4.1, illustrative",
        "Total: 238.5 GW · 345.1 TWh/yr · mean CF 16.5%",
        "E5 land cover",
    ],
)
def test_ordinary_labels_pass(text):
    assert ms.validate_label(text) == text


def test_a_map_refuses_an_internal_id_in_any_of_its_texts():
    with pytest.raises(ValueError):
        _map(subtitle="Central · open questions OQ-046 to OQ-049")
    with pytest.raises(ValueError):
        _map(label="elgible share")
    with pytest.raises(ValueError):
        _map(variable="286043 cells")
    with pytest.raises(ValueError):
        _map(total_text="Total 12 GW from 33,000 cells")
    with pytest.raises(ValueError):
        _map(country="BRA")


def test_a_legend_refuses_an_internal_id_too():
    country = synthetic_country("small")
    canvas = ms.new_map(
        country.geometry, iso="BRA", technology="Wind", variable="Dominant exclusion"
    )
    spec = ms.qualitative_legend("Dominant exclusion", ["E1 protected", "elgible share"])
    with pytest.raises(ValueError):
        ms.draw_classed_legend(canvas, spec)


def test_the_totals_box_has_the_standard_form():
    text = ms.totals_text(
        capacity_gw=238.53, energy_twh=345.05, mean_cf=0.165, eligible_km2=1_437_000
    )
    assert text == "Total: 238.5 GW · 345.1 TWh/yr · mean CF 16.5% · eligible area 1,437,000 km²"
    assert ms.validate_label(text)
    pt = ms.totals_text(capacity_gw=1.0, energy_twh=2.0, mean_cf=0.2, eligible_km2=10, lang="pt")
    assert pt == "Total: 1.0 GW · 2.0 TWh/ano · FC médio 20.0% · área elegível 10 km²"


def test_the_source_line_follows_the_language():
    assert _map().texts["source"].get_text() == "Boundaries: GADM 4.1, illustrative"
    assert _map(lang="pt").texts["source"].get_text() == "Limites: GADM 4.1, ilustrativo"
    assert _map(lang="pt").texts["title"].get_text().startswith("Brasil · ")


def test_no_source_file_holds_a_known_label_typo():
    """The grep of the typos: none of the misspellings found in labels appears in any Python file of the sources."""
    pattern = re.compile(ms.TYPO_PATTERN)
    found = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        found += [
            f"{path.relative_to(SRC)}:{n}"
            for n, line in enumerate(text.splitlines(), 1)
            if pattern.search(line)
            and "LABEL_TYPOS" not in line
            and not line.strip().startswith('"')
        ]
    assert found == []
