# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders.md
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Document loaders for Markdown documents.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator

import pypdfium2 as pdfium
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

# Chunking
MAX_CHARS = 1200  # soft character budget per chunk
HEADING_SEPARATOR = " > "  # joins the headings of a section's ancestors into its breadcrumb path
ROOT_SECTION_ID = "sec-root"  # ID of the implicit section wrapping the whole document

RE_PAGE_MARKER = re.compile(r"^\{(\d+)}-{10,}\s*$")
RE_PAGE_MARKER_ML = re.compile(r"^\{(\d+)}-{10,}\s*$", flags=re.MULTILINE)
RE_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_IMAGE_ONLY = re.compile(r"^\s*!\[[^]]*]\([^)]+\)\s*$")
RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Noise filter - headings of sections that carry no retrievable content
RE_EMPHASIS = re.compile(r"[*_`]+")

DEFAULT_NOISE_PATTERNS = [
    r"^(references|bibliography)$",
    r"^(table of contents|contents|toc)$",
    r"^about (this|the) (document|report)$",
    r"^acknowledge?ments?$",
    r"^executive summary$",
    r"^glossary$",
    r"^index$",
]

# Time estimation
UNITS = ("day", "month", "year")  # supported time units, finest first
COVER_CHARS = 3000  # length of the document prefix treated as the cover page
MIN_HEADING_FRACTION = 0.5  # fraction of headings that must carry a marker for the unit to win
MIN_TEXT_FRACTION = 0.3  # same for the raw-text density fallback
MIN_ANCHOR_CONFIDENCE = 0.7  # confidence at which a section-level anchor overrides the document-level one

RE_HEADING_SEGMENT = re.compile(r"\s*>\s*|\s*/\s*")
RE_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
RE_YEAR_ONLY = re.compile(r"^(?:19|20)\d{2}$")
RE_MONTH_NAMED = re.compile(
    r"\b(?P<month>january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(?P<year>(?:19|20)\d{2})\b",
    flags=re.IGNORECASE,
)
RE_MONTH_NUMERIC = re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])\b")
RE_DAY_ISO = re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])\b")

# Cover-page phrases carrying the document's reference year, e.g. "fiscal 2026", "year ended December 31, 2023"
RE_COVER_YEAR = [
    re.compile(r"\bannual\s+report\s+(?:for\s+)?(?:fiscal\s+)?(?P<year>(?:19|20)\d{2})\b", flags=re.IGNORECASE),
    re.compile(r"\bfiscal\s+(?:year\s+)?(?P<year>(?:19|20)\d{2})\b", flags=re.IGNORECASE),
    re.compile(
        r"\bfor\s+the\s+(?:fiscal\s+)?year\s+(?:ending|ended)[^,]*,?\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?"
        r"(?P<year>(?:19|20)\d{2})\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\byear\s+ended[^,]*,?\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?(?P<year>(?:19|20)\d{2})\b",
        flags=re.IGNORECASE,
    ),
]

MONTH_NAME_TO_NUM = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Section:
    """A node of the MD heading tree - a heading plus the range of lines it spans, descendants included."""

    id: str
    level: int
    heading: str
    parent_id: str | None
    children_ids: list[str] = field(default_factory=list)

    heading_line: int = 0  # 1-indexed line of the heading itself
    line_start: int = 0  # first line of the body (inclusive, 1-indexed)
    line_end: int = 0  # last line of the section including descendants (inclusive)

    filtered: bool = False  # heading matched a noise pattern - left out of the chunks

    @property
    def is_root(self) -> bool:
        return self.id == ROOT_SECTION_ID


@dataclass(frozen=True)
class TimeEstimate:
    """Result of a time estimation step."""

    # Either the chosen unit (`estimate_time_unit`) or a canonical anchor at that unit
    # (`estimate_time_anchor`, e.g. "2026" for a year, "2026-03" for a month, "2026-03-15" for a day).
    value: str

    # Rough calibration in [0.0, 1.0], not a probability - higher means more trustworthy
    confidence: float

    # Short explanation for logs
    reason: str


# ---------------------------------------------------------------------------
# Page handling
# ---------------------------------------------------------------------------


def build_page_line_index(lines: list[str]) -> list[int]:
    """
    Locate the physical pages of a paginated MD document.

    The page marker ("{<page_id>}" followed by at least 10 dashes) precedes the page it belongs to, so page 0 has
    no marker - it starts at line 1.

    :param lines: MD content split on newlines
    :return: list where entry 'i' is the 1-indexed line at which physical page 'i' starts
    """

    starts: dict[int, int] = {0: 1}

    for line_no, line in enumerate(lines, start=1):
        if not (match := RE_PAGE_MARKER.match(line)):
            continue

        # The page body starts on the first non-blank line after the marker
        body_line = line_no + 1
        while body_line <= len(lines) and not lines[body_line - 1].strip():
            body_line += 1

        starts[int(match.group(1))] = body_line

    return [starts.get(i, 1) for i in range(max(starts) + 1)]


def page_for_line(page_starts: list[int], line_no: int) -> int:
    """
    Resolve the physical page a line belongs to.

    :param page_starts: page line index (see `build_page_line_index`)
    :param line_no: 1-indexed line number
    :return: 0-indexed physical page containing the line
    """

    page = 0

    # page_starts is ascending - find the largest start <= line_no
    for idx, start in enumerate(page_starts):
        if start > line_no:
            break
        page = idx

    return page


def get_page_labels(pdf_path: str | Path, total_pages: int) -> list[str]:
    """
    Read the printed page labels (e.g. roman numerals of a preface) from a PDF file.

    :param pdf_path: path to the PDF file
    :param total_pages: number of pages to read labels for
    :return: page labels, 0-indexed by physical page; pages without a label fall back to their page number
    """

    doc = pdfium.PdfDocument(str(pdf_path))
    labels = []

    for page in range(total_pages):
        # noinspection PyBroadException
        try:
            label = doc.get_page_label(page)
        except Exception:
            label = ""

        labels.append(label or str(page + 1))

    return labels


def line_char_starts(lines: list[str]) -> list[int]:
    """
    Compute the character offset at which each line of the MD content starts.

    :param lines: MD content split on newlines
    :return: list where entry 'i' is the offset of the (i+1)-th line (lines being 1-indexed)
    """

    offsets = [0]
    running = 0

    for line in lines:
        running += len(line) + 1  # +1 for the "\n" the content was split on
        offsets.append(running)

    return offsets


# ---------------------------------------------------------------------------
# Heading tree
# ---------------------------------------------------------------------------


def iter_heading_positions(lines: list[str]) -> Iterator[tuple[int, int, str]]:
    """
    Find the ATX headings of an MD document, skipping anything inside fenced code blocks.

    :param lines: MD content split on newlines
    :return: generator of (1-indexed line number, heading level, heading text) tuples
    """

    in_fence = False

    for line_no, line in enumerate(lines, start=1):
        if RE_FENCE.match(line):
            in_fence = not in_fence
            continue

        if in_fence:
            continue

        if match := RE_ATX_HEADING.match(line):
            yield line_no, len(match.group(1)), match.group(2).strip()


def build_sections(lines: list[str]) -> list[Section]:
    """
    Build the heading tree of an MD document.

    The first section is the implicit root spanning the whole document; the rest follow in document order.

    :param lines: MD content split on newlines
    :return: document sections
    """

    headings = list(iter_heading_positions(lines))
    sections = [
        Section(
            id=ROOT_SECTION_ID,
            level=0,
            heading="",
            parent_id=None,
            line_start=1,
            line_end=len(lines),
        ),
    ]

    # Nest each heading under the closest preceding heading of a higher level
    stack = [sections[0]]

    for idx, (line_no, level, heading) in enumerate(headings):
        while stack and stack[-1].level >= level:
            stack.pop()

        parent = stack[-1] if stack else sections[0]
        section = Section(
            id=f"sec-{idx + 1:04d}",
            level=level,
            heading=heading,
            parent_id=parent.id,
            heading_line=line_no,
            line_start=line_no + 1,  # the body begins after the heading line
        )

        parent.children_ids.append(section.id)
        sections.append(section)
        stack.append(section)

    # A section ends just before the next heading of the same or a higher level, or at the end of the document
    for idx, section in enumerate(sections):
        if section.is_root:
            continue

        section.line_end = len(lines)

        for heading_line, level, _ in headings[idx:]:
            if level <= section.level:
                section.line_end = heading_line - 1
                break

    return sections


def heading_path_for(section: Section, sections_by_id: dict[str, Section]) -> str:
    """
    Build the breadcrumb path of a section from the headings of all its ancestors.

    :param section: section to build the path for
    :param sections_by_id: all document sections keyed by ID
    :return: heading path (empty for the root section)
    """

    headings = []
    current = section

    while current is not None and not current.is_root:
        headings.append(current.heading)
        current = sections_by_id.get(current.parent_id) if current.parent_id else None

    return HEADING_SEPARATOR.join(reversed(headings))


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def leaf_body_lines(section: Section, sections_by_id: dict[str, Section]) -> list[int]:
    """
    Collect the lines belonging to a section's own body, excluding those taken by its subsections.

    :param section: section to collect the lines of
    :param sections_by_id: all document sections keyed by ID
    :return: sorted 1-indexed line numbers
    """

    body = set(range(section.line_start, section.line_end + 1))

    for child_id in section.children_ids:
        child = sections_by_id[child_id]
        body -= set(range(child.heading_line, child.line_end + 1))

    return sorted(body)


def group_paragraphs(lines: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """
    Group lines into paragraphs, splitting on blank lines.

    Page markers and image-only lines are dropped from the paragraph text but keep contributing their line numbers.

    :param lines: (1-indexed line number, line text) tuples
    :return: (first line, last line, text) paragraph tuples
    """

    paragraphs = []
    buffer: list[tuple[int, str]] = []

    for line_no, text in lines:
        if text.strip():
            buffer.append((line_no, text))
        else:
            _flush_paragraph(buffer, paragraphs)
            buffer = []

    _flush_paragraph(buffer, paragraphs)
    return paragraphs


def _flush_paragraph(buffer: list[tuple[int, str]], paragraphs: list[tuple[int, int, str]]):
    """
    Append the buffered lines to the paragraphs as a single paragraph, unless they hold no text.

    :param buffer: buffered (1-indexed line number, line text) tuples
    :param paragraphs: paragraphs collected so far (updated in place)
    """

    kept = [(no, text) for no, text in buffer if not RE_PAGE_MARKER.match(text) and not RE_IMAGE_ONLY.match(text)]
    if kept and (text := "\n".join(t for _, t in kept).strip()):
        paragraphs.append((kept[0][0], kept[-1][0], text))


def pack_chunks(paragraphs: list[tuple[int, int, str]], max_chars: int) -> list[tuple[int, int, str]]:
    """
    Greedily pack paragraphs into chunks of up to `max_chars` characters.

    Oversized paragraphs are split by sentence, and hard-split as a last resort.

    :param paragraphs: (first line, last line, text) paragraph tuples
    :param max_chars: soft character budget per chunk
    :return: (first line, last line, text) chunk tuples
    """

    chunks: list[tuple[int, int, str]] = []
    current: tuple[int, int, str] | None = None

    for line_start, line_end, text in paragraphs:
        # Oversized paragraph - flush what is buffered and emit the pieces on their own
        if len(text) > max_chars:
            if current:
                chunks.append(current)
                current = None

            chunks.extend((line_start, line_end, piece) for piece in _split_oversize(text, max_chars))

        # Paragraph fits into the buffered chunk
        elif current and len(current[2]) + 2 + len(text) <= max_chars:
            current = (current[0], line_end, f"{current[2]}\n\n{text}")

        # Paragraph starts a new chunk
        else:
            if current:
                chunks.append(current)
            current = (line_start, line_end, text)

    if current:
        chunks.append(current)

    return chunks


def _split_oversize(text: str, max_chars: int) -> list[str]:
    """
    Split a text longer than `max_chars` into pieces, preferring sentence boundaries.

    :param text: text to split
    :param max_chars: soft character budget per piece
    :return: text pieces
    """

    pieces = []
    current = ""

    for sentence in RE_SENTENCE_SPLIT.split(text):
        # Oversized sentence - hard-split it into max_chars-long pieces
        if len(sentence) > max_chars:
            if current.strip():
                pieces.append(current.strip())
            current = ""

            pieces.extend(sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars))

        elif not current:
            current = sentence

        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"

        else:
            pieces.append(current.strip())
            current = sentence

    if current.strip():
        pieces.append(current.strip())

    return pieces


# ---------------------------------------------------------------------------
# Noise filter
# ---------------------------------------------------------------------------


def compile_filter_patterns(use_default: bool, extra: list[str]) -> list[re.Pattern]:
    """
    Compile the heading patterns of the sections to be left out of the chunks.

    :param use_default: include the built-in noise patterns
    :param extra: additional heading regexes
    :return: compiled case-insensitive patterns
    """

    patterns = (DEFAULT_NOISE_PATTERNS if use_default else []) + extra
    return [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns]


def mark_filtered(sections: list[Section], patterns: list[re.Pattern]):
    """
    Flag the sections whose heading matches one of the patterns, subsections included.

    :param sections: document sections (updated in place)
    :param patterns: compiled heading patterns
    """

    if not patterns:
        return

    sections_by_id = {section.id: section for section in sections}

    for section in sections:
        if section.is_root or section.filtered:
            continue

        # Strip MD emphasis markers so the patterns match regardless of **bold** and the like
        heading = RE_EMPHASIS.sub("", section.heading).strip()

        if any(pattern.search(heading) for pattern in patterns):
            _mark_subtree_filtered(section, sections_by_id)


def _mark_subtree_filtered(section: Section, sections_by_id: dict[str, Section]):
    """
    Flag a section and all its descendants as filtered.

    :param section: root of the subtree to flag (updated in place)
    :param sections_by_id: all document sections keyed by ID
    """

    section.filtered = True
    for child_id in section.children_ids:
        _mark_subtree_filtered(sections_by_id[child_id], sections_by_id)


# ---------------------------------------------------------------------------
# Time estimation
#
# Heuristics recovering the period a document reports on, so that retrieval can tell apart chunks of otherwise
# similar documents issued at different times. Both estimators are pure and rely on time markers found in the
# heading paths (the strongest signal, as time-organized documents put the period in the headings), in the cover
# page, or anywhere in the text (weakest). Only year/month/day granularity is supported.
# ---------------------------------------------------------------------------


def estimate_time_unit(text: str, heading_paths: Iterable[str] | None = None) -> TimeEstimate:
    """
    Estimate the time granularity a document is organized by.

    First match wins: heading markers carried by more than half of the heading paths, then the finest unit whose
    raw-text density exceeds `MIN_TEXT_FRACTION`, then "year" as the safest default for business documents.

    :param text: MD content
    :param heading_paths: heading paths of all document sections
    :return: estimated unit, one of `UNITS`
    """

    headings = list(heading_paths or [])

    # 1. Structural: headings organized by a time unit
    if headings:
        counts = _count_headings_by_unit(headings)

        # Check the finest unit first so a document with a daily structure is not labeled "year" just because
        # its dates contain year digits
        for unit in UNITS:
            if (fraction := counts[unit] / len(headings)) > MIN_HEADING_FRACTION:
                return TimeEstimate(
                    value=unit,
                    confidence=round(min(0.95, 0.6 + fraction * 0.35), 2),
                    reason=(
                        f"{counts[unit]}/{len(headings)} heading segments contain a {unit}-level time marker "
                        f"({fraction:.0%})"
                    ),
                )

    # 2. Text density, using the number of lines as a denominator proxy
    counts = _count_text_by_unit(text)
    lines = max(1, text.count("\n") + 1)

    for unit in UNITS:
        if (fraction := counts[unit] / lines) > MIN_TEXT_FRACTION:
            return TimeEstimate(
                value=unit,
                confidence=round(min(0.7, 0.4 + fraction * 0.4), 2),
                reason=f"{counts[unit]} {unit}-level markers across {lines} lines ({fraction:.0%})",
            )

    # 3. Low-signal fallback
    if counts["year"] or any(RE_YEAR.search(heading) for heading in headings):
        return TimeEstimate(
            value="year",
            confidence=0.35,
            reason="weak signal: a few year tokens found, defaulting to year",
        )

    return TimeEstimate(value="year", confidence=0.1, reason="no time markers detected, defaulting to year")


def _count_headings_by_unit(headings: Iterable[str]) -> dict[str, int]:
    """
    Count the heading paths carrying a time marker, by unit.

    :param headings: heading paths
    :return: number of heading paths per unit
    """

    counts = {unit: 0 for unit in UNITS}

    for heading in headings:
        # Walk the segments so that markers are caught even when sibling segments carry non-time labels
        for segment in RE_HEADING_SEGMENT.split(heading):
            if not (segment := segment.strip().strip("*_#` ")):
                continue

            if RE_DAY_ISO.search(segment):
                counts["day"] += 1
                break

            if RE_MONTH_NAMED.search(segment) or RE_MONTH_NUMERIC.search(segment):
                counts["month"] += 1
                break

            if RE_YEAR.search(segment):
                counts["year"] += 1
                break

    return counts


def _count_text_by_unit(text: str) -> dict[str, int]:
    """
    Count the time markers in a text, by unit.

    :param text: text to search
    :return: number of markers per unit
    """

    return {
        "day": len(RE_DAY_ISO.findall(text)),
        "month": len(RE_MONTH_NAMED.findall(text)) + len(RE_MONTH_NUMERIC.findall(text)),
        "year": len(RE_YEAR.findall(text)),
    }


def estimate_time_anchor(text: str, heading_paths: Iterable[str] | None = None, unit: str = "year") -> TimeEstimate:
    """
    Estimate the most recent reference point of a document at a given time unit.

    First match wins: the latest marker found in the heading paths, then in the cover page, then anywhere in
    the text, then today's date.

    :param text: MD content
    :param heading_paths: heading paths of all document sections
    :param unit: time unit to estimate the anchor at, one of `UNITS`
    :return: estimated anchor at the given unit
    """

    if unit not in UNITS:
        raise ValueError(f"Unsupported time unit: {unit}")

    headings = list(heading_paths or [])

    # 1. Structural: markers carried by the headings
    if markers := _markers_from_headings(headings, unit):
        return TimeEstimate(
            value=max(markers),
            confidence=0.9 if len(markers) >= 3 else 0.7,
            reason=f"max of {len(markers)} {unit}-level markers found in heading paths",
        )

    # 2. Cover-page phrases
    if markers := _markers_from_cover(text[:COVER_CHARS], unit):
        return TimeEstimate(
            value=(anchor := max(markers)),
            confidence=0.75,
            reason=f"cover-page phrase matched {unit}-level marker {anchor}",
        )

    # 3. Full-text scan as a last resort
    if markers := _markers_from_text(text, unit):
        return TimeEstimate(
            value=max(markers),
            confidence=0.4,
            reason=f"max of {len(markers)} {unit}-level markers in full text (weak signal)",
        )

    # 4. Nothing found - fall back to today's date with a low confidence
    today = date.today()
    fallbacks = {
        "day": today.isoformat(),
        "month": f"{today.year:04d}-{today.month:02d}",
        "year": f"{today.year}",
    }

    return TimeEstimate(
        value=fallbacks[unit],
        confidence=0.1,
        reason="no time markers found, falling back to today's date",
    )


def _markers_from_headings(headings: Iterable[str], unit: str) -> list[str]:
    """
    Extract the time markers carried by heading paths, at most one per path.

    :param headings: heading paths
    :param unit: time unit to extract the markers at
    :return: canonical marker values
    """

    markers = []

    for heading in headings:
        for segment in RE_HEADING_SEGMENT.split(heading):
            if not (segment := segment.strip().strip("*_#` ")):
                continue

            if marker := _marker_from_segment(segment, unit):
                markers.append(marker)
                break

    return markers


def _marker_from_segment(segment: str, unit: str) -> str | None:
    """
    Extract the time marker of a single heading segment.

    :param segment: heading segment
    :param unit: time unit to extract the marker at
    :return: canonical marker value, or None if the segment carries no marker at that unit
    """

    if unit == "day":
        match = RE_DAY_ISO.search(segment)
        return match.group(0) if match else None

    if unit == "month":
        if match := RE_MONTH_NUMERIC.search(segment):
            return f"{int(match.group('year')):04d}-{int(match.group('month')):02d}"

        if match := RE_MONTH_NAMED.search(segment):
            return f"{int(match.group('year')):04d}-{MONTH_NAME_TO_NUM[match.group('month').lower()]:02d}"

        return None

    if RE_YEAR_ONLY.match(segment):
        return segment

    match = RE_YEAR.search(segment)
    return match.group(0) if match else None


def _markers_from_cover(cover: str, unit: str) -> list[str]:
    """
    Extract the time markers of a document's cover page.

    Years are only taken from the narrow cover-page phrases, months and days from the whole cover.

    :param cover: cover page text
    :param unit: time unit to extract the markers at
    :return: canonical marker values
    """

    if unit != "year":
        return _markers_from_text(cover, unit)
    return [match.group("year") for pattern in RE_COVER_YEAR for match in pattern.finditer(cover)]


def _markers_from_text(text: str, unit: str) -> list[str]:
    """
    Extract all time markers of a text.

    :param text: text to search
    :param unit: time unit to extract the markers at
    :return: canonical marker values
    """

    if unit == "day":
        return [match.group(0) for match in RE_DAY_ISO.finditer(text)]

    if unit == "month":
        m_named = [
            f"{int(match.group('year')):04d}-{MONTH_NAME_TO_NUM[match.group('month').lower()]:02d}"
            for match in RE_MONTH_NAMED.finditer(text)
        ]

        m_numeric = [
            f"{int(match.group('year')):04d}-{int(match.group('month')):02d}"
            for match in RE_MONTH_NUMERIC.finditer(text)
        ]

        return m_named + m_numeric

    return RE_YEAR.findall(text)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


class MDPageLoader(BaseLoader):
    """Simple loader that splits a paginated MD file into one chunk per page."""

    def __init__(self, file_path: str | Path):
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        with open(self.file_path, "r") as f:
            content = f.read()

        matches = list(RE_PAGE_MARKER_ML.finditer(content))
        for i, match in enumerate(matches):
            page_id = int(match.group(1))
            page_start = match.end()
            page_end = (matches[i + 1].start() if i + 1 < len(matches) else len(content))
            page_content = content[page_start:page_end].strip()
            yield Document(page_content=page_content, metadata={"page": page_id})

    def load(self) -> list[Document]:
        documents = super().load()
        total_pages = len(documents)

        for document in documents:
            document.metadata["total_pages"] = total_pages

        return documents


class MDHierarchyLoader(BaseLoader):
    """
    Loader turning a paginated MD file into breadcrumb-prefixed chunks.

    The MD file is expected to carry page markers (output of Alchemist's `conversion.pdf2md` with pagination, or of
    marker-pdf). Chunks respect the MD heading hierarchy: each section's own body (excluding the bodies of its
    subsections) is packed into chunks of up to `max_chars` characters, prefixed with the section's heading path.

    The source PDF is optional and only read to resolve the printed page labels; without it, chunks carry no
    `page_label` metadata.
    """

    def __init__(
            self,
            file_path: str | Path,
            pdf_path: str | Path | None = None,
            max_chars: int = MAX_CHARS,
            filter_noise: bool = False,
            filter_headings: list[str] | None = None,
            default_filters: bool = True,
    ):
        """
        :param file_path: path to the paginated MD file
        :param pdf_path: path to the source PDF file (used to resolve the printed page labels)
        :param max_chars: soft character budget per chunk
        :param filter_noise: skip the sections whose heading matches one of the filter patterns, subsections
            included; implied by a non-empty `filter_headings`
        :param filter_headings: additional case-insensitive heading regexes to filter
        :param default_filters: apply the built-in noise patterns (table of contents, index, glossary, ...)
        """

        self.file_path = Path(file_path)
        self.pdf_path = Path(pdf_path) if pdf_path else None

        self.max_chars = max_chars

        self.filter_noise = filter_noise or bool(filter_headings)
        self.filter_headings = filter_headings or []
        self.default_filters = default_filters

    def lazy_load(self) -> Iterator[Document]:
        content = self.file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        char_starts = line_char_starts(lines)

        # Resolve the physical pages from the MD page markers, and their printed labels from the PDF if available
        page_starts = build_page_line_index(lines)
        total_pages = len(page_starts)
        page_labels = get_page_labels(self.pdf_path, total_pages) if self.pdf_path else None

        # Build the heading tree and flag the noise sections, which are left out of the chunks
        sections = build_sections(lines)
        sections_by_id = {section.id: section for section in sections}
        mark_filtered(sections, self._filter_patterns())

        # Estimate the document-level time granularity and anchor from all heading paths
        heading_paths = {section.id: heading_path_for(section, sections_by_id) for section in sections}
        doc_paths = [heading_paths[section.id] for section in sections if not section.is_root]
        unit = estimate_time_unit(content, heading_paths=doc_paths)
        anchor = estimate_time_anchor(content, heading_paths=doc_paths, unit=unit.value)

        # Pack the body of every section into chunks
        for section in sections:
            if section.is_root or section.filtered:
                continue

            if not (body_lines := leaf_body_lines(section, sections_by_id)):
                continue

            paragraphs = group_paragraphs([(line_no, lines[line_no - 1]) for line_no in body_lines])
            if not (chunks := pack_chunks(paragraphs, self.max_chars)):
                continue

            heading_path = heading_paths[section.id]
            time_anchor = self._section_anchor(heading_path=heading_path, unit=unit.value, fallback=anchor)

            for line_start, line_end, body in chunks:
                page = page_for_line(page_starts, line_start)

                metadata = {
                    "title": heading_path,
                    "heading_path": heading_path,
                    "section_id": section.id,

                    "page": page,
                    "total_pages": total_pages,

                    "chunk_offset": char_starts[line_start - 1],
                    "line_start": line_start,
                    "line_end": line_end,

                    "time_anchor": time_anchor,
                    "time_unit": unit.value,
                }

                if page_labels:
                    metadata["page_label"] = page_labels[page]

                yield Document(
                    page_content=f"{heading_path}\n\n{body}" if heading_path else body,
                    metadata=metadata,
                )

    def _filter_patterns(self) -> list[re.Pattern]:
        """
        Compile the heading patterns of the sections to be left out of the chunks.

        :return: compiled patterns (empty if filtering is disabled)
        """

        if not self.filter_noise:
            return []
        return compile_filter_patterns(use_default=self.default_filters, extra=self.filter_headings)

    @staticmethod
    def _section_anchor(heading_path: str, unit: str, fallback: TimeEstimate) -> str:
        """
        Resolve the time anchor of a single section.

        Prefers a time marker embedded in the section's own heading path over the document-level anchor.

        :param heading_path: heading path of the section
        :param unit: document-level time unit
        :param fallback: document-level anchor
        :return: time anchor value at the given unit
        """

        anchor = estimate_time_anchor("", heading_paths=[heading_path], unit=unit)
        return anchor.value if anchor.confidence >= MIN_ANCHOR_CONFIDENCE else fallback.value
