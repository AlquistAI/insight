# -*- coding: utf-8 -*-
"""
    alchemist.conversion.pdf2md
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PDF to Markdown converter using the Docling library.
"""

import logging
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Generator, Literal

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument, NodeItem, TableCell

from common.core import get_component_logger
from common.models.conversion import ConversionOptions
from common.utils.misc import consume_generator

logger = get_component_logger()

# Match marker-pdf's MarkdownRenderer pagination format exactly so the output can be fed into md2chunks.py:
# "\n\n{<physical_page_id>}" + 48 dashes + "\n\n", where <physical_page_id> is a 0-indexed integer.
PAGE_SEPARATOR = "-" * 48

DEVICE_MAP = {
    "auto": AcceleratorDevice.AUTO,
    "cpu": AcceleratorDevice.CPU,
    "cuda": AcceleratorDevice.CUDA,
    "mps": AcceleratorDevice.MPS,
}


def convert(input_content: bytes, opts: ConversionOptions | None = None) -> str:
    """
    Convert a PDF file to Markdown using Docling.

    :param input_content: input PDF file content
    :param opts: conversion options (see `ConversionOptions` for details)
    :return: Markdown string content
    """

    opts = opts or ConversionOptions()
    converter = build_converter(device=opts.device, ocr=opts.ocr)

    pdf_file = NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_file.write(input_content)
    pdf_file.close()

    # batches: list of (page_offset_0indexed, document); single-shot conversion is one batch at offset 0
    if opts.progress:
        _, batches = consume_generator(convert_with_progress(
            converter=converter,
            pdf_path=Path(pdf_file.name),
            batch_size=opts.progress_batch_size,
        ))
    else:
        batches = [(0, converter.convert(pdf_file.name).document)]

    os.remove(pdf_file.name)
    return _assemble_markdown(batches, opts)


def convert_streaming(input_content: bytes, opts: ConversionOptions | None = None) -> Generator[dict, None, None]:
    """
    Convert a PDF to Markdown in page batches, streaming progress as it goes.

    Forwards the per-batch progress emitted by `convert_with_progress` and, once conversion + assembly finish,
    yields a terminal dict carrying the assembled Markdown.

    :param input_content: input PDF file content
    :param opts: conversion options (see `ConversionOptions` for details)
    :return: generator of progress dicts ending with the converted content
    """

    opts = opts or ConversionOptions()
    converter = build_converter(device=opts.device, ocr=opts.ocr)

    pdf_file = NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_file.write(input_content)
    pdf_file.close()

    try:
        # `yield from` forwards every progress dict to the caller and binds the generator's return value (batches)
        batches = yield from convert_with_progress(
            converter=converter,
            pdf_path=Path(pdf_file.name),
            batch_size=opts.progress_batch_size,
        )

        yield {"stage": "convert", "done": True, "content": _assemble_markdown(batches, opts)}

    finally:
        os.remove(pdf_file.name)


def _assemble_markdown(batches: list[tuple[int, DoclingDocument]], opts: ConversionOptions) -> str:
    """
    Reconstruct heading levels (unless disabled) and export the batches to a single Markdown string.

    :param batches: list of (page_offset_0indexed, document) tuples in page order
    :param opts: conversion options controlling hierarchy recovery and pagination
    :return: Markdown string content
    """

    documents = [doc for _, doc in batches]

    if opts.hierarchy != "none":
        chosen, n_levels, detail = assign_levels(
            documents=documents,
            strategy=opts.hierarchy,
            threshold=opts.hierarchy_threshold,
            tolerance=opts.hierarchy_tolerance,
        )

        logger.debug("Hierarchy: requested=%s chosen=%s levels=%d (%s)", opts.hierarchy, chosen, n_levels, detail)

    if opts.paginate:
        return "".join(export_paginated(document=doc, page_offset=off) for off, doc in batches)
    return "\n\n".join(doc.export_to_markdown() for _, doc in batches)


def build_converter(
        device: Literal["auto", "cpu", "cuda", "mps"] = "auto",
        ocr: Literal["auto", "off", "force"] = "auto",
) -> DocumentConverter:
    """
    Create a DocumentConverter whose PDF pipeline uses the chosen accelerator and OCR mode.

    :param device: accelerator for Docling layout/table models
    :param ocr: OCR mode
    :return: Docling document converter
    """

    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(device=DEVICE_MAP[device])
    pipeline_options.do_ocr = ocr != "off"

    if ocr == "force":
        pipeline_options.ocr_options.force_full_page_ocr = True

    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})


def _get_pdf_page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium
    return len(pdfium.PdfDocument(str(pdf_path)))


def convert_with_progress(
        converter: DocumentConverter,
        pdf_path: Path,
        batch_size: int,
) -> Generator[dict, None, list[tuple[int, DoclingDocument]]]:
    """
    Convert the PDF in page batches, yielding (and debug-logging) progress + ETA after each batch.

    Reuses one converter so models stay loaded. This is the single batching engine: `convert` drains it via
    `consume_generator` for the batches, while `convert_streaming` re-emits its progress via `yield from`.

    :param converter: document converter instance
    :param pdf_path: input PDF path
    :param batch_size: pages per batch
    :yield: progress dict {"stage", "current_page", "total_pages", "percent", "eta_seconds"} after each batch
    :return: list of (start_page, document) tuples in page order — one document per batch, each carrying its
        pages' global page numbers
    """

    # Docling page_range is 1-indexed, inclusive
    start = 1
    total = _get_pdf_page_count(pdf_path)

    results = []  # (start_page_0indexed, document)
    t0 = time.perf_counter()

    while start <= total:
        end = min(start + batch_size - 1, total)
        res = converter.convert(str(pdf_path), page_range=(start, end))
        results.append((start - 1, res.document))

        elapsed = time.perf_counter() - t0
        rate = end / elapsed if elapsed > 0 else 0
        eta = (total - end) / rate if rate > 0 else 0

        logger.debug(
            "--- pages %d-%d/%d done (%d%%), %.0fs elapsed, ~%.0fs left",
            start, end, total, end * 100 // total, elapsed, eta,
        )

        yield {
            "stage": "convert",
            "current_page": end,
            "total_pages": total,
            "percent": end * 100 // total,
            "eta_seconds": round(eta),
        }

        start = end + 1

    return results


def export_paginated(document: DoclingDocument, page_offset: int = 0) -> str:
    """
    Export Markdown one physical page at a time, inserting a marker before each page.

    The marker for page i (0-indexed) is "{i}" + 48 dashes, matching marker-pdf's format. A marker is emitted for
    every page including empty ones so physical page numbers stay aligned with pypdfium2 page labels downstream.

    :param document: parsed Docling document
    :param page_offset: added to each batch page index to produce the global index
    :return: Markdown document content
    """

    parts: list[str] = []

    for local_idx in range(document.num_pages()):
        physical_id = page_offset + local_idx

        # Docling page_no is 1-indexed and global in batched mode
        body = document.export_to_markdown(page_no=physical_id + 1)

        parts.append(f"\n\n{{{physical_id}}}{PAGE_SEPARATOR}\n\n")
        parts.append(body.strip("\n"))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Hierarchy reconstruction
#
# Docling labels every heading at level 1, so the Markdown export is flat.
# We recover real heading levels before export using, in order of preference:
#   1. the table of contents (author-declared structure)        -- strongest
#   2. heading numbering schemes (PART/Item, ARTICLE, 1.2.3)
#   3. font size (heading bbox height)                          -- geometry fallback
# Each strategy maps a heading to a level integer; `assign_levels` picks one.
# ---------------------------------------------------------------------------

_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    """Normalize heading text for fuzzy matching: lowercase, strip punctuation."""
    return _NORM_RE.sub(" ", text.lower()).strip()


def collect_headers(documents: list[DoclingDocument]) -> list[tuple[NodeItem, float]]:
    """
    Return a list of (item, height) for every detected section header that carries geometry.

    Computed across one or more documents (batched conversion produces several).
    Order matches document/reading order.
    """

    headers = []

    for document in documents:
        for item, _ in document.iterate_items():
            if getattr(getattr(item, "label", None), "value", None) != "section_header":
                continue

            if not (prov := getattr(item, "prov", None)):
                continue

            if (bbox := getattr(prov[0], "bbox", None)) is None:
                continue

            headers.append((item, float(bbox.height)))

    return headers


# ---- numbering schemes ----------------------------------------------------

# First match wins. The level function maps a regex match to a 1-based heading level.
_NUMBERING_SCHEMES = [
    # SEC filing: PART I/II... -> 1, Item 1./1A. -> 2 (handled below by family)
    ("part", re.compile(r"^\s*part\s+[ivxlc]+\b", re.IGNORECASE), lambda m: 1),
    ("item", re.compile(r"^\s*item\s+\d+[a-z]?\.", re.IGNORECASE),
     lambda m: 3 if re.match(r"^\s*item\s+\d+[a-z]\.", m.string, re.IGNORECASE) else 2),
    # Legal/contract: ARTICLE I -> 1, Section 2.1 -> 2
    ("article", re.compile(r"^\s*article\s+[ivxlc]+\b", re.IGNORECASE), lambda m: 1),
    ("section", re.compile(r"^\s*section\s+\d+(\.\d+)*\b", re.IGNORECASE), lambda m: 1 + m.group(0).count(".")),
    # Appendix / Annex -> top-level peer
    ("appendix", re.compile(r"^\s*(appendix|annex)\s+[a-z0-9]+\b", re.IGNORECASE), lambda m: 1),
    # Dotted decimal: 1 / 1.2 / 1.2.3 -> depth = number of components
    ("decimal", re.compile(r"^\s*\d+(\.\d+)*\.?\s+\S"), lambda m: m.group(0).strip().rstrip(".").count(".") + 1),
]

_FAMILY_OF = {
    "part": "sec",
    "item": "sec",
    "article": "legal",
    "section": "legal",
    "appendix": "appendix",
    "decimal": "decimal",
}


def _numbering_level(text: str) -> tuple[str, int] | None:
    """Return (scheme_name, level) if the heading text matches a numbering scheme, else None."""

    for name, pat, level_fn in _NUMBERING_SCHEMES:
        if not (m := pat.match(text)):
            continue

        # noinspection PyBroadException
        try:
            return name, max(1, min(level_fn(m), 6))
        except Exception:
            return name, 1

    return None


def numbering_coverage(headers: list[tuple[NodeItem, float]]) -> dict[str, Any]:
    """
    Analyze the numbering signal among detected headers.

    Returns a dict:
      fraction   -- numbered headers / all detected headers
      dominant   -- most common numbering family name (or None)
      dom_count  -- absolute count of headers in the dominant family
      dom_share  -- dominant family count / numbered headers (consistency)

    The selector uses dom_count + dom_share rather than `fraction`, because Docling over-detects headers
    (short UI labels, captions) that dilute the raw fraction even when a real, consistent numbering scheme is present.
    """

    if not headers:
        return {"fraction": 0.0, "dominant": None, "dom_count": 0, "dom_share": 0.0}

    fam = Counter()
    matched = 0

    for item, _ in headers:
        if res := _numbering_level(getattr(item, "text", "")):
            matched += 1
            fam[_FAMILY_OF[res[0]]] += 1

    if matched == 0:
        return {"fraction": 0.0, "dominant": None, "dom_count": 0, "dom_share": 0.0}

    dominant, dom_count = fam.most_common(1)[0]
    return {
        "fraction": matched / len(headers),
        "dominant": dominant,
        "dom_count": dom_count,
        "dom_share": dom_count / matched,
    }


def level_by_numbering(headers: list[tuple[NodeItem, float]]) -> int:
    """
    Assign levels from numbering.

    Headings without a recognized number are placed one level below the most recent numbered heading
    (so unnumbered subheadings nest sensibly).

    Returns the number of distinct levels used.
    """

    used = set()
    last_numbered_level = 1

    for item, _ in headers:
        if res := _numbering_level(getattr(item, "text", "")):
            last_numbered_level = lvl = res[1]
        else:
            lvl = min(last_numbered_level + 1, 6)

        item.level = lvl
        used.add(lvl)

    return len(used)


# ---- table of contents ----------------------------------------------------


def parse_toc(documents: list[DoclingDocument]) -> list[tuple[str, int]]:
    """
    Parse Docling `document_index` (ToC) items into a list of (normalized_title, level) entries.

    Computed across one or more documents.
    Level comes from the entry's column offset in the ToC table (col 0 = level 1, col 1 = level 2, ...),
    which is how filings indent nested items.

    Returns empty list if no usable ToC is found.
    """

    entries = []
    items = ((it, doc) for doc in documents for it, _ in doc.iterate_items())

    for item, _doc in items:
        if getattr(getattr(item, "label", None), "value", None) != "document_index":
            continue

        data = getattr(item, "data", None)
        cells: list[TableCell] | None = getattr(data, "table_cells", None) if data else None
        if not cells:
            continue

        # Group cells into rows.
        # Within a row, the left-most text cell is the title and its column offset encodes depth.
        # A trailing pure-number cell is the page anchor (ignored for leveling).
        rows = defaultdict(list)
        for cell in cells:
            rows[cell.start_row_offset_idx].append(cell)

        for r in sorted(rows):
            row_cells = sorted(rows[r], key=lambda c: c.start_col_offset_idx)
            text_cells = [
                c for c in row_cells if c.text.strip() and not c.text.strip().isdigit() and _norm(c.text) != "page"
            ]

            if not text_cells:
                continue

            # title = concatenation of non-numeric text cells (e.g. "Item 1." + "Business")
            # level = column offset of the first text cell
            title = " ".join(c.text.strip() for c in text_cells)
            level = min(text_cells[0].start_col_offset_idx + 1, 6)
            entries.append((_norm(title), level))

    return entries


def _toc_matches_header(toc_norm: str, header_norm: str) -> bool:
    """True if a ToC entry and a header text reconcile (equality, prefix, or containment after normalization)."""

    if not toc_norm or not header_norm:
        return False

    return (
            toc_norm == header_norm
            or header_norm.startswith(toc_norm)
            or toc_norm.startswith(header_norm)
            or toc_norm in header_norm
    )


def toc_coverage(headers: list[tuple[NodeItem, float]], toc_entries: list[tuple[str, int]]) -> float:
    """
    Trustworthiness of the ToC; the fraction of ToC entries that actually appear in the document body.

    This measures whether the ToC reconciles with the document (the right gate),
    rather than how many of the (often noisy, over-detected) headers happen to be in the ToC.
    """

    if not headers or not toc_entries:
        return 0.0

    header_norms = [_norm(getattr(item, "text", "")) for item, _ in headers]
    found = 0

    for toc_norm, _ in toc_entries:
        if any(_toc_matches_header(toc_norm, h) for h in header_norms):
            found += 1

    return found / len(toc_entries)


def level_by_toc(headers: list[tuple[NodeItem, float]], toc_entries: list[tuple[str, int]], tolerance: float) -> int:
    """
    Use the ToC as a level oracle.

    Each detected heading that matches a ToC entry takes the ToC level; unmatched headings fall back to font size.
    Returns the number of distinct levels used.
    """

    fs_levels = _font_size_levels(headers, tolerance)
    used = set()

    for item, height in headers:
        h = _norm(getattr(item, "text", ""))
        toc_level = None

        for t, lvl in toc_entries:
            if _toc_matches_header(t, h):
                toc_level = lvl
                break

        item.level = toc_level if toc_level is not None else fs_levels.get(id(item), 1)
        used.add(item.level)

    return len(used)


# ---- font size ------------------------------------------------------------


def _font_size_levels(headers: list[tuple[NodeItem, float]], tolerance: float) -> dict[int, int]:
    """Map each header to a level by clustering bbox heights (largest = level 1). Returns {id(item): level}."""

    if not headers:
        return {}

    distinct = sorted({h for _, h in headers}, reverse=True)
    clusters: list[float] = []

    for h in distinct:
        if clusters and abs(clusters[-1] - h) <= tolerance:
            continue
        clusters.append(h)

    def level_for(height: float) -> int:
        best = min(range(len(clusters)), key=lambda i: abs(clusters[i] - height))
        return min(best + 1, 6)

    return {id(item): level_for(height) for item, height in headers}


def level_by_font_size(headers: list[tuple[NodeItem, float]], tolerance: float) -> int:
    """Assign levels from font size in place. Returns distinct level count."""

    levels = _font_size_levels(headers, tolerance)
    used = set()

    for item, _ in headers:
        item.level = levels.get(id(item), 1)
        used.add(item.level)

    return len(used)


# ---- selector -------------------------------------------------------------

# A numbering scheme needs at least this many headings in its dominant family before we trust it
# (guards against a stray "1. " match), and the family must be this self-consistent among numbered headings.
_MIN_NUMBERED = 5
_MIN_DOM_SHARE = 0.8


def assign_levels(
        documents: list[DoclingDocument],
        strategy: str,
        threshold: float,
        tolerance: float,
) -> tuple[str, int, str]:
    """
    Recover heading levels using the requested strategy.

    Computed across one or more documents (batched conversion produces several).
    For 'auto', try ToC -> numbering -> font size and use the first that covers >= threshold of detected headings.

    Returns (chosen_strategy, n_levels, detail_str).
    """

    if not (headers := collect_headers(documents)):
        return "none", 0, "no detected headings"

    def do(strategy_name: str):
        if strategy_name == "toc":
            toc_ = parse_toc(documents)
            cov_ = toc_coverage(headers, toc_)
            detail_ = f"{len(toc_)} ToC entries, {cov_:.0%} reconciled with body"
            return cov_, (lambda: level_by_toc(headers, toc_, tolerance)), detail_

        if strategy_name == "numbering":
            info = numbering_coverage(headers)
            # Gate on dominant-family consistency + absolute count, NOT the raw numbered fraction:
            # Docling over-detects headers (UI labels, captions) that dilute the fraction even when a real,
            # consistent scheme is present (see kap4: 31% fraction but a clean decimal outline).
            # Pass if the dominant family is self-consistent and covers enough headings in absolute terms.
            passes = (info["dom_count"] >= _MIN_NUMBERED and info["dom_share"] >= _MIN_DOM_SHARE)
            score = threshold if passes else 0.0
            detail_ = (
                f"{info['dom_count']} headings numbered (family={info['dominant']}, {info['dom_share']:.0%} "
                f"consistent, {info['fraction']:.0%} of all detected)"
            )
            return score, (lambda: level_by_numbering(headers)), detail_

        # font-size always "covers" everything
        return 1.0, (lambda: level_by_font_size(headers, tolerance)), "font-size clustering"

    if strategy in ("toc", "numbering", "font-size"):
        cov, apply, detail = do(strategy)
        n = apply()
        return strategy, n, detail

    # auto: ladder
    for name in ("toc", "numbering"):
        cov, apply, detail = do(name)
        if cov >= threshold:
            n = apply()
            return name, n, detail

    cov, apply, detail = do("font-size")
    n = apply()
    return "font-size", n, detail


# ---------------------------------------------------------------------------


def quiet_ocr_logging():
    """
    Silence RapidOCR's chatty INFO/empty-result logging.

    In 'auto' OCR mode on a mostly-digital PDF, RapidOCR logs an empty-result line per bitmap region it can't read.
    That's expected noise, not an error.

    RapidOCR attaches its own StreamHandler and resets its logger level from its config on each init (rapidocr/main.py),
    so a plain setLevel() doesn't stick. We raise the level, mute any attached handlers, and stop propagation.
    A logging.Filter on the logger drops records below ERROR even if the level is reset again later.
    """

    class _MinLevel(logging.Filter):

        def filter(self, record):
            return record.levelno >= logging.ERROR

    for name in ("RapidOCR", "rapidocr"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False
        lg.addFilter(_MinLevel())
        for h in lg.handlers:
            h.setLevel(logging.ERROR)


quiet_ocr_logging()
