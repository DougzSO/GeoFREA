"""Download the sources of the solar capacity-factor basis (DC or AC) and the DC/AC ratio, and list where each one says something about them (COMMAND 161M).

usage: python scripts/fetch_solar_basis_sources.py [--out DIR] [--no-extract]

The values marked `\\vfy` in the solar rows of `tab:g4-cf` of `docs/thesis/methods/grupo4.tex` (fleet capacity factor on an AC basis, DC/AC ratio) and the note 4 of
the IRENA 2024 report (DEC-079, DEC-086, OQ-105, OQ-111) need a source the author can check. This script:

1. downloads each source listed in `SOURCES` with Python (`urllib`), trying its URLs in order: the first is the one the `.bib` or the report points to, the next
   ones are alternatives (an official host of the same document, or, when no official host answers, a copy that is marked as such);
2. writes `manifest.json` under `--out` (default `GeoFREA_data/external/solar_basis/`): for each source the URL asked for, the URL used, the access date, the
   SHA-256, the size, the file name, and every failed attempt with its error. A source no URL gives is listed with `status: "not_found"` and no file;
3. writes `extracts.json`: for each downloaded PDF, every page (1-based, the PDF page index, not the printed number) where one of its patterns matches, with a
   snippet. The patterns are words about the basis (AC, DC, inverter loading ratio, capacity factor, note 4) and the numbers of `tab:g4-cf` (21.5, 21, 17.2,
   1.37, 1.40, 1.29). A hit says the page is worth reading; it is not the value. The author or the reader of the output reads the page.

The downloaded files stay in `GeoFREA_data`; nothing here is a tracked artifact and no phase reads it. `pypdf` is needed for the extraction only (it is not a
dependency of the package); without it the script downloads and says the extraction was skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_OUT = Path("D:/Douglas/DOUTORADO/GeoFREA_data/external/solar_basis")
USER_AGENT = "Mozilla/5.0 (compatible; GeoFREA source check)"
TIMEOUT_S = 120

# patterns of the words about the basis and the numbers of tab:g4-cf (case-insensitive; the decimal separator is a point or a comma)
BASIS_PATTERNS: dict[str, str] = {
    "note 4": r"\bnote\s*4\b|\bnota\s*4\b",
    "inverter loading": r"inverter\s+loading|loading\s+ratio|ILR\b|DC\s*(?:-|/|to|:)\s*AC|AC\s*(?:-|/|:)\s*DC|CC\s*/\s*CA|CA\s*/\s*CC|rela[cç][aã]o\s+CC",
    "AC or DC capacity": r"\bkW\s*(?:ac|dc)\b|\bMW\s*(?:ac|dc)\b|\bkWp\b|\bMWp\b|\bDC\s+capacity|\bAC\s+capacity|capacidade\s+(?:em\s+)?(?:CC|CA|corrente)",
    "capacity factor": r"capacity\s+factor|fator\s+de\s+capacidade|capacity\s+utili[sz]ation|\bCUF\b|\bPLF\b|horas\s+equivalentes",
}
NUMBER_PATTERNS: dict[str, str] = {
    "21.5": r"\b21[.,]5\s*%?",
    "21": r"\b21\s*%",
    "17.2": r"\b17[.,]2\s*%?",
    "1.37": r"\b1[.,]37\b",
    "1.40": r"\b1[.,]40?\b",
    "1.29": r"\b1[.,]29\b",
}

# the sources of the solar rows of tab:g4-cf and the IRENA report of note 4; `urls[0]` is the one asked for, the next ones are alternatives
SOURCES: tuple[dict[str, Any], ...] = (
    {
        "id": "irena_rpgc_2024",
        "country": "all",
        "role": "note 4 and any declared inverter loading ratio; typical new-project solar CF",
        "bib_key": "irena2025costs24",
        "title": "Renewable Power Generation Costs in 2024 (IRENA)",
        "urls": (
            "https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2025/Jul/IRENA_TEC_RPGC_in_2024_2025.pdf",
        ),
    },
    {
        "id": "epe_nt_dados_de_entrada",
        "country": "BRA",
        "role": "fleet solar CF (21.5% AC) and DC/AC ratio (1.37)",
        "bib_key": "epe2024nt011",
        "title": "Dados de entrada para modelos elétricos e energéticos (EPE, NT EPE-DEE-NT-011/2021)",
        "urls": (
            "https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-637/Dados%20de%20entrada%20para%20modelos.pdf",
        ),
    },
    {
        "id": "ons_rt_dgl_0189_2025",
        "country": "BRA",
        "role": "solar fleet CF and curtailment (context of the net-of-curtailment fleet value)",
        "bib_key": "ons2025cortes",
        "title": "Diagnóstico e Perspectiva da Evolução dos Cortes de Geração no Brasil (ONS, RT DGL 0189/2025)",
        "urls": (
            "https://www.ons.org.br/AcervoDigitalDocumentosEPublicacoes/RT%20DGL-ONS%200189-2025%20-%20GT%20Curtailment%20rev1.pdf",
        ),
    },
    {
        "id": "cerc_order_517_mp_2024",
        "country": "IND",
        "role": "regulatory solar CUF (21% AC) and DC/AC ratio (1.40)",
        "bib_key": "cerc2026order517",
        "title": "Order in Petition No. 517/MP/2024 (CERC)",
        "urls": (
            "https://cercind.gov.in/2026/orders/517-MP-2024.pdf",
            # not an official host: a copy of the order kept by JMK Research, used only when no CERC URL answers
            "https://jmkresearch.com/wp-content/uploads/2026/02/CERC-order.pdf",
        ),
    },
    {
        "id": "mnre_re_statistics_2024_25",
        "country": "IND",
        "role": "solar capacity by mode and generation (fleet CF), if the report gives them",
        "bib_key": "mnre2026stats",
        "title": "Renewable Energy Statistics 2024-25 (MNRE)",
        "urls": ("https://cdnbbsr.s3waas.gov.in/s3716e1b8c6cd17b771da77391355749f3/uploads/2025/11/20251106791170361.pdf",),
    },
    {
        "id": "ren_dados_tecnicos_2024",
        "country": "PRT",
        "role": "fleet solar CF (17.2% AC) and DC/AC ratio (1.29)",
        "bib_key": "ren2025dados",
        "title": "Dados Técnicos 2024: Sistema Elétrico Nacional (REN)",
        "urls": ("https://datahub.ren.pt/media/vizdjf5o/dados-t%C3%A9cnicos-2024.pdf",),
    },
    {
        "id": "epe_nt_dee_re_004_2019",
        "country": "BRA",
        "role": "EPE note on the physical guarantee of solar plants (capacity factor and DC/AC ratio of its parameters); an alternative to the EPE note that answers 404",
        "bib_key": "not-in-bib-yet",
        "title": "Nota Técnica EPE-DEE-RE-004/2019-r0 (EPE), annexed to NT 94/2018/DPE/SPE (MME)",
        "urls": ("https://www.gov.br/mme/pt-br/arquivos/nota-t-cnica-epe-dee-re-004-2019-r0.pdf",),
    },
    {
        "id": "abeeolica_boletim_anual_2025",
        "country": "BRA",
        "role": "Brazilian wind fleet: capacity and generation by year (fleet CF) and the curtailment of 2024",
        "bib_key": "not-in-bib-yet",
        "title": "Boletim Anual de Geração Eólica 2025 (ABEEólica)",
        "urls": ("https://abeeolica.org.br/wp-content/uploads/2025/05/424_ABEEOLICA_BOLETIM-ANUAL-2025_PT_Final-Aprovado.pdf",),
    },
    {
        "id": "cstep_onshore_wind_potential_2016",
        "country": "IND",
        "role": "minimum CUF of the onshore wind potential at 100 m (an independent study, not a regulation)",
        "bib_key": "not-in-bib-yet",
        "title": "Re-assessment of India's On-shore Wind Power Potential (CSTEP, 2016)",
        "urls": ("https://cstep.in/drupal/sites/default/files/2019-07/CSTEP_PB_onshore_wind_power_potential_June2016.pdf",),
    },
)

Fetch = Callable[[str], bytes]


def http_fetch(url: str) -> bytes:
    """Read one URL with `urllib`; any error propagates to the caller, which records it."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_source(source: Mapping[str, Any], out_dir: Path, fetch: Fetch, accessed: str) -> dict[str, Any]:
    """Try the URLs of one source in order; write the first answer to `out_dir` and describe it (or the failure) in a manifest entry."""
    entry: dict[str, Any] = {
        "id": source["id"],
        "country": source["country"],
        "bib_key": source["bib_key"],
        "title": source["title"],
        "role": source["role"],
        "url_requested": source["urls"][0],
        "url_used": None,
        "accessed": accessed,
        "status": "not_found",
        "file": None,
        "sha256": None,
        "size_bytes": None,
        "attempts": [],
    }
    for url in source["urls"]:
        try:
            data = fetch(url)
        except Exception as error:  # noqa: BLE001 - any failure of the network layer is recorded and the next URL is tried
            entry["attempts"].append({"url": url, "error": f"{type(error).__name__}: {error}"})
            continue
        if not data:
            entry["attempts"].append({"url": url, "error": "empty answer"})
            continue
        suffix = ".pdf" if data[:5] == b"%PDF-" else ".bin"
        name = f"{source['id']}{suffix}"
        (out_dir / name).write_bytes(data)
        entry.update(url_used=url, status="downloaded", file=name, sha256=sha256_hex(data), size_bytes=len(data))
        entry["attempts"].append({"url": url, "error": None})
        break
    return entry


def download_all(
    out_dir: Path, sources: Sequence[Mapping[str, Any]] = SOURCES, fetch: Fetch = http_fetch, now: Callable[[], datetime] | None = None
) -> dict[str, Any]:
    """Download every source into `out_dir` and write `manifest.json`; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or (lambda: datetime.now(UTC)))().date().isoformat()
    manifest = {"accessed": stamp, "sources": [download_source(s, out_dir, fetch, stamp) for s in sources]}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def search_pages(pages: Sequence[str], patterns: Mapping[str, str], context: int = 110) -> list[dict[str, Any]]:
    """Every page (1-based) where a pattern matches, with one snippet per pattern and page; `pages` are the texts of the pages in order."""
    hits: list[dict[str, Any]] = []
    compiled = {label: re.compile(rx, re.IGNORECASE) for label, rx in patterns.items()}
    for number, text in enumerate(pages, start=1):
        flat = re.sub(r"\s+", " ", text)
        for label, rx in compiled.items():
            match = rx.search(flat)
            if match:
                start, end = max(0, match.start() - context), min(len(flat), match.end() + context)
                hits.append({"page": number, "pattern": label, "match": match.group(0), "snippet": flat[start:end]})
    return hits


def pdf_pages(path: Path) -> list[str]:
    """The text of each page of a PDF, with `pypdf`; a page whose text cannot be read is an empty string."""
    try:
        from pypdf import PdfReader  # not a dependency of the package: imported where it is needed
    except ImportError as error:
        raise ImportError("pypdf is required to read the pages of the downloaded PDFs (pip install pypdf)") from error

    pages = []
    for page in PdfReader(str(path)).pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a page with an unreadable stream is skipped, and the manifest shows the page count
            pages.append("")
    return pages


def extract_all(out_dir: Path, manifest: Mapping[str, Any], read_pages: Callable[[Path], list[str]] = pdf_pages) -> dict[str, Any]:
    """Search each downloaded PDF for the patterns and write `extracts.json`; return what it wrote."""
    patterns = {**BASIS_PATTERNS, **NUMBER_PATTERNS}
    result: dict[str, Any] = {}
    for entry in manifest["sources"]:
        if entry["status"] != "downloaded" or not str(entry["file"]).endswith(".pdf"):
            continue
        pages = read_pages(out_dir / entry["file"])
        result[entry["id"]] = {"file": entry["file"], "pages": len(pages), "hits": search_pages(pages, patterns)}
    (out_dir / "extracts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory of the downloads, the manifest and the extracts")
    parser.add_argument("--no-extract", action="store_true", help="download only")
    args = parser.parse_args(argv)
    manifest = download_all(args.out)
    for entry in manifest["sources"]:
        where = entry["url_used"] or "NOT FOUND"
        print(f"{entry['id']:<30} {entry['status']:<11} {entry['size_bytes'] or 0:>10} bytes  {where}")
        for attempt in entry["attempts"]:
            if attempt["error"]:
                print(f"    failed: {attempt['url']}: {attempt['error']}")
    if args.no_extract:
        return 0
    try:
        result = extract_all(args.out, manifest)
    except ImportError:
        print("extraction skipped: pypdf is not installed")
        return 0
    for source_id, info in result.items():
        print(f"{source_id}: {info['pages']} pages, {len(info['hits'])} hits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
