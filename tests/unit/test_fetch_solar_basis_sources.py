"""The download of the sources of the solar CF basis and the search of their pages (COMMAND 161M); no real network is used."""

import hashlib
import importlib.util
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_solar_basis_sources.py"
PDF = b"%PDF-1.4 fake body"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("fetch_solar_basis_sources", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """A test that reaches for the real network fails loudly."""

    def refuse(*_args, **_kwargs):
        raise AssertionError("a test opened a real network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)


def _source(source_id="a", urls=("https://x.test/a.pdf",)):
    return {"id": source_id, "country": "BRA", "bib_key": "k", "title": "T", "role": "r", "urls": urls}


def _fetch(answers):
    """A stub of the network: URL -> bytes, or an exception to raise."""

    def fetch(url):
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return fetch


@pytest.mark.unit
def test_a_download_is_written_with_its_hash_size_url_and_date(mod, tmp_path):
    now = lambda: datetime(2026, 11, 16, tzinfo=UTC)
    manifest = mod.download_all(tmp_path, [_source()], _fetch({"https://x.test/a.pdf": PDF}), now)
    entry = manifest["sources"][0]
    assert entry["status"] == "downloaded" and entry["file"] == "a.pdf"
    assert entry["sha256"] == hashlib.sha256(PDF).hexdigest() and entry["size_bytes"] == len(PDF)
    assert entry["url_requested"] == entry["url_used"] == "https://x.test/a.pdf" and entry["accessed"] == "2026-11-16"
    assert (tmp_path / "a.pdf").read_bytes() == PDF
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == manifest


@pytest.mark.unit
def test_a_failed_url_falls_to_the_alternative_and_the_manifest_keeps_both_attempts(mod, tmp_path):
    urls = ("https://official.test/a.pdf", "https://alternative.test/a.pdf")
    answers = {urls[0]: OSError("timed out"), urls[1]: PDF}
    entry = mod.download_all(tmp_path, [_source(urls=urls)], _fetch(answers))["sources"][0]
    assert entry["url_requested"] == urls[0] and entry["url_used"] == urls[1] and entry["status"] == "downloaded"
    assert [a["url"] for a in entry["attempts"]] == list(urls)
    assert entry["attempts"][0]["error"] == "OSError: timed out" and entry["attempts"][1]["error"] is None


@pytest.mark.unit
def test_a_source_that_no_url_gives_is_listed_as_not_found_with_no_file_and_the_others_still_run(mod, tmp_path):
    sources = [_source("lost", ("https://x.test/lost.pdf",)), _source("found", ("https://x.test/found.pdf",))]
    answers = {"https://x.test/lost.pdf": OSError("404"), "https://x.test/found.pdf": PDF}
    manifest = mod.download_all(tmp_path, sources, _fetch(answers))
    lost, found = manifest["sources"]
    assert lost["status"] == "not_found" and lost["file"] is None and lost["sha256"] is None and lost["url_used"] is None
    assert found["status"] == "downloaded"
    assert not (tmp_path / "lost.pdf").exists()


@pytest.mark.unit
def test_an_empty_answer_counts_as_a_failed_attempt(mod, tmp_path):
    entry = mod.download_all(tmp_path, [_source()], _fetch({"https://x.test/a.pdf": b""}))["sources"][0]
    assert entry["status"] == "not_found" and entry["attempts"][0]["error"] == "empty answer"


@pytest.mark.unit
def test_every_listed_source_has_a_bib_key_an_official_first_url_and_a_marked_copy_when_one_is_used(mod):
    ids = [s["id"] for s in mod.SOURCES]
    assert len(ids) == len(set(ids)) >= 6
    for source in mod.SOURCES:
        assert source["bib_key"] and source["urls"] and all(u.startswith("https://") for u in source["urls"])
    cerc = next(s for s in mod.SOURCES if s["id"].startswith("cerc"))
    assert "cercind.gov.in" in cerc["urls"][0] and "jmkresearch.com" in cerc["urls"][-1]


@pytest.mark.unit
def test_the_page_search_gives_the_one_based_page_the_pattern_and_a_snippet(mod):
    pages = ["intro without anything", "the fleet capacity factor was 21,5 % on an AC basis", "DC/AC ratio of 1.37 for the plants"]
    patterns = {**mod.BASIS_PATTERNS, **mod.NUMBER_PATTERNS}
    hits = mod.search_pages(pages, patterns)
    by = {(h["page"], h["pattern"]) for h in hits}
    assert (2, "capacity factor") in by and (2, "21.5") in by and (3, "inverter loading") in by and (3, "1.37") in by
    assert not [h for h in hits if h["page"] == 1]
    assert "21,5" in next(h for h in hits if h["pattern"] == "21.5")["snippet"]


@pytest.mark.unit
def test_the_extraction_writes_the_hits_of_the_downloaded_pdfs_only(mod, tmp_path):
    answers = {"https://x.test/a.pdf": PDF, "https://x.test/b.pdf": OSError("down")}
    manifest = mod.download_all(tmp_path, [_source("a"), _source("b", ("https://x.test/b.pdf",))], _fetch(answers))
    result = mod.extract_all(tmp_path, manifest, read_pages=lambda _path: ["note 4 says the inverter loading ratio", "nothing"])
    assert list(result) == ["a"] and result["a"]["pages"] == 2
    assert {h["pattern"] for h in result["a"]["hits"]} >= {"note 4", "inverter loading"}
    assert json.loads((tmp_path / "extracts.json").read_text(encoding="utf-8")) == result
