#!/usr/bin/env python3
"""Turn a paginated Markdown file (from pdf2md.py --paginate) plus its source
PDF into RAG preprocessing artifacts:

    <stem>.pages.json      per-page markdown keyed by physical page and printed label
    <stem>.sections.json   heading skeleton tree (pointer-based context)
    <stem>.chunks.jsonl    breadcrumb-prefixed chunks with page/line provenance
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from time_estimation import estimate_time_anchor, estimate_time_unit

PAGE_MARKER_RE = re.compile(r"^\{(\d+)\}-{10,}\s*$")
ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
IMAGE_ONLY_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

DEFAULT_NOISE_PATTERNS = [
    r"^(table of contents|contents|toc)$",
    r"^index$",
    r"^glossary$",
    r"^(references|bibliography)$",
    r"^executive summary$",
    r"^about (this|the) (document|report)$",
    r"^acknowledge?ments?$",
]


# ---------- CLI ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="md2chunks",
        description="Convert a paginated Markdown file + its source PDF into "
                    "pages.json, sections.json, and chunks.jsonl for a RAG index.",
    )
    parser.add_argument("md", type=Path,
                        help="Paginated .md produced by `pdf2md.py --paginate`.")
    parser.add_argument("pdf", type=Path,
                        help="Original PDF, used to resolve printed page labels.")
    parser.add_argument("-o", "--outdir", type=Path, default=None,
                        help="Directory for output files (default: next to the .md).")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Overwrite existing output files.")
    parser.add_argument("--max-chars", type=int, default=1200,
                        help="Soft character budget per chunk (default: 1200).")
    parser.add_argument("--filter", action="store_true",
                        help="Drop sections whose heading matches the noise patterns "
                             "from chunks.jsonl (they stay in sections.json).")
    parser.add_argument("--filter-heading", action="append", default=[], metavar="REGEX",
                        help="Additional case-insensitive heading regex to filter. "
                             "Repeatable. Implies --filter.")
    parser.add_argument("--no-default-filters", action="store_true",
                        help="Do not apply the built-in noise pattern list.")
    parser.add_argument("--source", default=None,
                        help="Value for the chunk `source` field (default: PDF file name).")
    return parser.parse_args()


# ---------- Data types --------------------------------------------------------


@dataclass
class Section:
    id: str
    level: int
    heading: str
    parent_id: str | None
    children_ids: list[str] = field(default_factory=list)
    heading_line: int = 0   # 1-indexed line of the heading itself
    line_start: int = 0     # first line of the body (inclusive, 1-indexed)
    line_end: int = 0       # last line of the section including descendants (inclusive)
    char_start: int = 0
    char_end: int = 0
    page_start: int = 1
    page_end: int = 1
    filtered: bool = False

    @property
    def is_root(self) -> bool:
        return self.id == "sec-root"


# ---------- Page handling -----------------------------------------------------


def build_page_line_index(lines: list[str]) -> list[int]:
    """Return a list where entry i = 1-indexed line number where physical page i starts.

    The paginated .md format from marker:
        "\n\n{<page_id>}" + 48 dashes + "\n\n"
    The marker appears BEFORE its page (see marker/renderers/markdown.py:77-82).
    Page 0 has no preceding marker — it begins at line 1.
    """
    starts: dict[int, int] = {0: 1}
    for i, line in enumerate(lines, start=1):
        m = PAGE_MARKER_RE.match(line)
        if m:
            page_id = int(m.group(1))
            # Body of that page starts on the first non-blank line after the marker.
            body_line = i + 1
            while body_line <= len(lines) and lines[body_line - 1].strip() == "":
                body_line += 1
            starts[page_id] = body_line
    if not starts:
        return [1]
    max_id = max(starts)
    return [starts.get(i, 1) for i in range(max_id + 1)]


def page_for_line(page_starts: list[int], line_no: int) -> int:
    """Return 0-indexed physical page containing `line_no` (1-indexed)."""
    # page_starts is ascending; find the largest start <= line_no.
    page = 0
    for idx, start in enumerate(page_starts):
        if start <= line_no:
            page = idx
        else:
            break
    return page


def get_page_labels(pdf_path: Path, n_pages: int) -> list[str]:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("error: pypdfium2 is not installed. Install it with: pip install pypdfium2",
              file=sys.stderr)
        raise SystemExit(1)
    doc = pdfium.PdfDocument(str(pdf_path))
    labels: list[str] = []
    for i in range(n_pages):
        try:
            label = doc.get_page_label(i)
        except Exception:
            label = ""
        labels.append(label if label else str(i + 1))
    return labels


def split_pages(lines: list[str], page_starts: list[int]) -> list[str]:
    """Return per-page markdown (strings). Page markers themselves are removed."""
    pages: list[str] = []
    for i, start in enumerate(page_starts):
        end = page_starts[i + 1] - 1 if i + 1 < len(page_starts) else len(lines)
        # Strip any page-marker line inside the page range (the marker for page i
        # sits just *before* page_starts[i], so normally this is a no-op; keep
        # the filter defensive).
        body_lines = [ln for ln in lines[start - 1:end]
                      if not PAGE_MARKER_RE.match(ln)]
        # Trim leading/trailing blank lines for readability.
        while body_lines and body_lines[0].strip() == "":
            body_lines.pop(0)
        while body_lines and body_lines[-1].strip() == "":
            body_lines.pop()
        pages.append("\n".join(body_lines))
    return pages


# ---------- Heading tree ------------------------------------------------------


def iter_heading_positions(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    """Yield (1-indexed line_no, level, heading_text) for real ATX headings,
    skipping anything inside fenced code blocks."""
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = ATX_HEADING_RE.match(line)
        if m:
            yield i, len(m.group(1)), m.group(2).strip()


def build_sections(
        lines: list[str], line_char_starts: list[int],
        page_starts: list[int],
) -> list[Section]:
    headings = list(iter_heading_positions(lines))
    sections: list[Section] = [
        Section(id="sec-root", level=0, heading="", parent_id=None,
                heading_line=0, line_start=1,
                line_end=len(lines), char_start=0,
                char_end=line_char_starts[-1], page_start=1,
                page_end=max(1, len(page_starts))),
    ]

    stack: list[Section] = [sections[0]]
    for idx, (line_no, level, heading) in enumerate(headings):
        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else sections[0]
        sec = Section(
            id=f"sec-{idx + 1:04d}",
            level=level,
            heading=heading,
            parent_id=parent.id,
            heading_line=line_no,
            line_start=line_no + 1,  # body begins after the heading line
        )
        parent.children_ids.append(sec.id)
        sections.append(sec)
        stack.append(sec)

    # Compute line_end: a section ends just before the next heading of same-or-higher
    # level, or at EOF.
    total_lines = len(lines)
    heading_by_index = [(h_line, level) for (h_line, level, _) in headings]
    for idx, sec in enumerate(sections):
        if sec.is_root:
            continue
        sec_idx = idx - 1  # index in `headings`
        end_line = total_lines
        for h_line, lvl in heading_by_index[sec_idx + 1:]:
            if lvl <= sec.level:
                end_line = h_line - 1
                break
        sec.line_end = end_line

    # char offsets + pages.
    for sec in sections:
        sec.char_start = line_char_starts[max(sec.line_start - 1, 0)]
        # char_end is the offset just past the last char of line_end.
        end_line_idx = min(sec.line_end, total_lines)
        sec.char_end = line_char_starts[end_line_idx]  # exclusive
        sec.page_start = page_for_line(page_starts, sec.line_start) + 1
        sec.page_end = page_for_line(page_starts, max(sec.line_end, sec.line_start)) + 1

    return sections


def heading_path_for(sec: Section, by_id: dict[str, Section]) -> str:
    parts: list[str] = []
    cur: Section | None = sec
    while cur is not None and not cur.is_root:
        parts.append(cur.heading)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return " > ".join(reversed(parts))


# ---------- Chunking ----------------------------------------------------------


def leaf_body_lines(sec: Section, sections_by_id: dict[str, Section]) -> list[int]:
    """Return the 1-indexed line numbers that belong to sec's *own* body,
    excluding lines taken by child sections."""
    body = set(range(sec.line_start, sec.line_end + 1))
    for child_id in sec.children_ids:
        child = sections_by_id[child_id]
        body -= set(range(child.heading_line, child.line_end + 1))
    return sorted(body)


def group_paragraphs(lines_with_no: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Turn (line_no, text) pairs into paragraph triples (line_start, line_end, text).
    Paragraphs split on blank lines; page markers and image-only lines are stripped
    from the paragraph text but we keep the surrounding line numbers."""
    paragraphs: list[tuple[int, int, str]] = []
    buf: list[tuple[int, str]] = []
    for line_no, text in lines_with_no:
        if text.strip() == "":
            if buf:
                _flush(buf, paragraphs)
                buf = []
        else:
            buf.append((line_no, text))
    if buf:
        _flush(buf, paragraphs)
    return paragraphs


def _flush(buf: list[tuple[int, str]], out: list[tuple[int, int, str]]) -> None:
    kept = [
        (ln, t) for (ln, t) in buf
        if not PAGE_MARKER_RE.match(t) and not IMAGE_ONLY_RE.match(t)
    ]
    if not kept:
        return
    line_start = kept[0][0]
    line_end = kept[-1][0]
    text = "\n".join(t for _, t in kept).strip()
    if text:
        out.append((line_start, line_end, text))


def pack_chunks(
        paragraphs: list[tuple[int, int, str]],
        max_chars: int,
) -> list[tuple[int, int, str]]:
    """Greedy paragraph packing up to max_chars. Oversized paragraphs are split
    by sentence, then hard-split as a last resort. Returns triples
    (line_start, line_end, text)."""
    chunks: list[tuple[int, int, str]] = []
    cur_lines: tuple[int, int] | None = None
    cur_text = ""

    def flush() -> None:
        nonlocal cur_lines, cur_text
        if cur_lines is not None and cur_text.strip():
            chunks.append((cur_lines[0], cur_lines[1], cur_text.strip()))
        cur_lines = None
        cur_text = ""

    for ls, le, ptext in paragraphs:
        if len(ptext) > max_chars:
            flush()
            for piece in _split_oversize(ptext, max_chars):
                chunks.append((ls, le, piece))
            continue
        if cur_lines is None:
            cur_lines = (ls, le)
            cur_text = ptext
            continue
        if len(cur_text) + 2 + len(ptext) <= max_chars:
            cur_lines = (cur_lines[0], le)
            cur_text = cur_text + "\n\n" + ptext
        else:
            flush()
            cur_lines = (ls, le)
            cur_text = ptext
    flush()
    return chunks


def _split_oversize(text: str, max_chars: int) -> list[str]:
    sentences = SENTENCE_SPLIT_RE.split(text)
    out: list[str] = []
    cur = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if cur:
                out.append(cur.strip())
                cur = ""
            for i in range(0, len(sent), max_chars):
                out.append(sent[i:i + max_chars])
            continue
        if not cur:
            cur = sent
        elif len(cur) + 1 + len(sent) <= max_chars:
            cur = cur + " " + sent
        else:
            out.append(cur.strip())
            cur = sent
    if cur.strip():
        out.append(cur.strip())
    return out


# ---------- Noise filter ------------------------------------------------------


def compile_filter_patterns(use_default: bool, extra: list[str]) -> list[re.Pattern]:
    patterns: list[str] = []
    if use_default:
        patterns.extend(DEFAULT_NOISE_PATTERNS)
    patterns.extend(extra)
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_EMPHASIS_RE = re.compile(r"[*_`]+")


def _normalize_heading(h: str) -> str:
    # Strip markdown emphasis markers so patterns match regardless of **bold** etc.
    return _EMPHASIS_RE.sub("", h).strip()


def mark_filtered(sections: list[Section], patterns: list[re.Pattern]) -> None:
    if not patterns:
        return
    by_id = {s.id: s for s in sections}
    for sec in sections:
        if sec.is_root or sec.filtered:
            continue
        heading_norm = _normalize_heading(sec.heading)
        if any(p.search(heading_norm) for p in patterns):
            _mark_subtree_filtered(sec, by_id)


def _mark_subtree_filtered(sec: Section, by_id: dict[str, Section]) -> None:
    sec.filtered = True
    for cid in sec.children_ids:
        _mark_subtree_filtered(by_id[cid], by_id)


# ---------- Main --------------------------------------------------------------


def main() -> int:
    args = parse_args()

    if not args.md.is_file():
        print(f"error: MD not found: {args.md}", file=sys.stderr)
        return 1
    if not args.pdf.is_file():
        print(f"error: PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    outdir = args.outdir if args.outdir is not None else args.md.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stem = args.md.stem
    pages_path = outdir / f"{stem}.pages.json"
    sections_path = outdir / f"{stem}.sections.json"
    chunks_path = outdir / f"{stem}.chunks.jsonl"

    for p in (pages_path, sections_path, chunks_path):
        if p.exists() and not args.force:
            print(f"error: {p} already exists (use --force to overwrite)", file=sys.stderr)
            return 1

    md_text = args.md.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    # Pre-compute a char offset for the start of each 1-indexed line so sections
    # can expose char ranges against the .md file.
    line_char_starts: list[int] = [0]
    running = 0
    for ln in lines:
        running += len(ln) + 1  # +1 for the "\n" we split on
        line_char_starts.append(running)

    # Pages.
    page_starts = build_page_line_index(lines)
    n_pages = len(page_starts)
    page_labels = get_page_labels(args.pdf, n_pages)
    page_bodies = split_pages(lines, page_starts)

    source_name = args.source or args.pdf.name
    pages_json = {
        "document": source_name,
        "pages": [
            {"page": i + 1, "page_label": page_labels[i], "markdown": page_bodies[i]}
            for i in range(n_pages)
        ],
    }
    pages_path.write_text(json.dumps(pages_json, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    # Sections.
    sections = build_sections(lines, line_char_starts, page_starts)
    sections_by_id = {s.id: s for s in sections}

    filter_patterns: list[re.Pattern] = []
    if args.filter or args.filter_heading:
        filter_patterns = compile_filter_patterns(
            use_default=not args.no_default_filters, extra=args.filter_heading,
        )
    mark_filtered(sections, filter_patterns)

    def section_dict(s: Section) -> dict:
        d = {
            "id": s.id,
            "level": s.level,
            "heading": s.heading,
            "heading_path": heading_path_for(s, sections_by_id),
            "parent_id": s.parent_id,
            "children_ids": list(s.children_ids),
            "heading_line": s.heading_line,
            "line_start": s.line_start,
            "line_end": s.line_end,
            "char_start": s.char_start,
            "char_end": s.char_end,
            "page_start": s.page_start,
            "page_end": s.page_end,
        }
        if s.filtered:
            d["filtered"] = True
        return d

    # Document-level time estimates over all non-root heading paths.
    all_heading_paths = [
        heading_path_for(s, sections_by_id) for s in sections if not s.is_root
    ]
    doc_unit = estimate_time_unit(md_text, heading_paths=all_heading_paths)
    doc_anchor = estimate_time_anchor(
        md_text, heading_paths=all_heading_paths, unit=doc_unit.value,
    )

    sections_json = {
        "document": source_name,
        "sections": {s.id: section_dict(s) for s in sections},
        "root_id": "sec-root",
        "time_unit": {
            "value": doc_unit.value,
            "confidence": doc_unit.confidence,
            "reason": doc_unit.reason,
        },
        "time_anchor": {
            "value": doc_anchor.value,
            "confidence": doc_anchor.confidence,
            "reason": doc_anchor.reason,
        },
    }
    sections_path.write_text(json.dumps(sections_json, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # Chunks.
    chunk_id = 0
    n_chunks_written = 0
    with chunks_path.open("w", encoding="utf-8") as fh:
        for sec in sections:
            if sec.is_root or sec.filtered:
                continue
            body_lines = leaf_body_lines(sec, sections_by_id)
            if not body_lines:
                continue
            lines_with_no = [(ln, lines[ln - 1]) for ln in body_lines]
            paragraphs = group_paragraphs(lines_with_no)
            if not paragraphs:
                continue
            chunks = pack_chunks(paragraphs, args.max_chars)
            heading_path = heading_path_for(sec, sections_by_id)
            # Per-section anchor refinement: prefer a marker embedded in the
            # section's own heading path; fall back to the document anchor.
            sec_anchor = estimate_time_anchor(
                "", heading_paths=[heading_path], unit=doc_unit.value,
            )
            chunk_anchor = (
                sec_anchor.value if sec_anchor.confidence >= 0.7 else doc_anchor.value
            )
            for (ls, le, body) in chunks:
                chunk_id += 1
                physical_page = page_for_line(page_starts, ls)
                record = {
                    "id": f"{stem}-{chunk_id:04d}",
                    "text": f"{heading_path}\n\n{body}" if heading_path else body,
                    "heading_path": heading_path,
                    "section_id": sec.id,
                    "page": physical_page + 1,
                    "page_label": page_labels[physical_page],
                    "page_physical": physical_page + 1,
                    "line_start": ls,
                    "line_end": le,
                    "source": source_name,
                    "time_unit": doc_unit.value,
                    "time_anchor": chunk_anchor,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_chunks_written += 1

    print(f"wrote {pages_path} ({n_pages} page(s))")
    print(f"wrote {sections_path} ({len(sections) - 1} section(s))")
    print(f"wrote {chunks_path} ({n_chunks_written} chunk(s))")
    print(
        f"time: unit={doc_unit.value} ({doc_unit.confidence:.2f}) "
        f"anchor={doc_anchor.value} ({doc_anchor.confidence:.2f})",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
