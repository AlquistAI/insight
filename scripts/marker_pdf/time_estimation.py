"""Heuristic estimation of a document's time granularity and anchor.

SYNC NOTE
---------
This file is a copy of
/Users/jansedivy/projects/alquist-lite/server/app/time_estimation.py.
Keep both copies in sync.

Exports
-------
TimeEstimate
    Result type carrying value + confidence + a short human-readable reason.
estimate_time_unit(text, heading_paths=None)
    Pick the most likely reporting granularity: "year", "month", or "day".
estimate_time_anchor(text, heading_paths=None, unit="year")
    Pick the most recent reference point at the given unit.

Design notes
------------
* Both functions are pure and have no I/O, so the same module can be used
  by the server (as an ingest-time fallback) and by an external converter.
* Confidence is a rough calibration (0.0-1.0), not a probability. The
  caller decides a threshold, e.g. auto-accept at >= 0.75 and prompt the
  user otherwise.
* Only year / month / day are supported in the first cut. Quarter, week
  and hour can be added later without changing the public shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

UNITS = ("year", "month", "day")
UnitName = str  # one of UNITS


@dataclass(frozen=True)
class TimeEstimate:
    """Result of an estimation step.

    `value` is the chosen unit string (for estimate_time_unit) or the
    canonical anchor string (for estimate_time_anchor, e.g. "2026" for year,
    "2026-03" for month, "2026-03-15" for day).
    `confidence` is in [0.0, 1.0]. Higher means more trustworthy.
    `reason` is a short explanation for logs / UI confirmation.
    """

    value: str
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# Regexes - defined once at module load
# ---------------------------------------------------------------------------
#
# A comment on scope:
#   - YEAR matches any four-digit year in 1900-2099. Narrow enough to avoid
#     matching dollar amounts like "$2026" cleanly most of the time (boundaries).
#   - MONTH matches both "January 2026" and "2026-03" (the numeric form is a
#     single capture so the unit detector can tell them apart from years).
#   - DAY matches ISO 8601 dates only - "2026-03-15" style. Day-month-year
#     variants are deferred; they are error-prone without locale information.

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_YEAR_ONLY_RE = re.compile(r"^(?:19|20)\d{2}$")

_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|"
    "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_MONTH_NAMED_RE = re.compile(
    rf"\b(?P<month>{_MONTH_NAMES})\s+(?P<year>(?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
_MONTH_NUMERIC_RE = re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])\b")

_DAY_ISO_RE = re.compile(
    r"\b(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])\b",
)

_MONTH_NAME_TO_NUM = {
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
# Unit estimation
# ---------------------------------------------------------------------------


def estimate_time_unit(
        text: str, heading_paths: Iterable[str] | None = None,
) -> TimeEstimate:
    """Pick the reporting granularity the document is organized by.

    Strategy (first match wins):

    1. If > 50% of heading paths contain a time marker at a given unit,
       that unit wins. "Heading-organized" is the strongest structural signal.
    2. Otherwise look at raw text density. Finest unit that matches in
       > 30% of the text sample wins.
    3. Fallback: "year" (safest default for business documents).

    Confidence reflects the strength of the winning signal.
    """
    # Normalize headings
    headings = list(heading_paths or [])
    total_headings = len(headings)

    if total_headings:
        counts = _count_headings_by_unit(headings)
        # Check finest-first (day, month, year) so a doc with daily structure
        # doesn't get labeled "year" just because dates contain year digits.
        for unit in ("day", "month", "year"):
            frac = counts[unit] / total_headings
            if frac > 0.5:
                conf = min(0.95, 0.6 + frac * 0.35)
                return TimeEstimate(
                    value=unit,
                    confidence=round(conf, 2),
                    reason=(
                        f"{counts[unit]}/{total_headings} heading segments contain a "
                        f"{unit}-level time marker ({frac:.0%})"
                    ),
                )

    # Text-density fallback
    text_counts = _count_text_by_unit(text)
    # Use number of non-blank lines as a denominator proxy. Avoids zero-div.
    denom = max(1, text.count("\n") + 1)
    for unit in ("day", "month", "year"):
        frac = text_counts[unit] / denom
        if frac > 0.3:
            conf = min(0.7, 0.4 + frac * 0.4)
            return TimeEstimate(
                value=unit,
                confidence=round(conf, 2),
                reason=(
                    f"{text_counts[unit]} {unit}-level markers across {denom} lines "
                    f"({frac:.0%})"
                ),
            )

    # Low-signal fallback
    any_year = text_counts["year"] > 0 or any(
        _YEAR_RE.search(h) for h in headings,
    )
    if any_year:
        return TimeEstimate(
            value="year",
            confidence=0.35,
            reason="weak signal: a few year tokens found, defaulting to year",
        )
    return TimeEstimate(
        value="year",
        confidence=0.1,
        reason="no time markers detected, defaulting to year",
    )


def _count_headings_by_unit(headings: Iterable[str]) -> dict[str, int]:
    counts = {"year": 0, "month": 0, "day": 0}
    for h in headings:
        # Walk segments so we catch "...> 2023" even when sibling segments
        # have non-time labels like "Revenue".
        segments = re.split(r"\s*>\s*|\s*/\s*", h)
        for seg in segments:
            seg = seg.strip().strip("*_#` ")
            if not seg:
                continue
            if _DAY_ISO_RE.search(seg):
                counts["day"] += 1
                break
            if _MONTH_NAMED_RE.search(seg) or _MONTH_NUMERIC_RE.search(seg):
                counts["month"] += 1
                break
            if _YEAR_ONLY_RE.match(seg) or _YEAR_RE.search(seg):
                counts["year"] += 1
                break
    return counts


def _count_text_by_unit(text: str) -> dict[str, int]:
    return {
        "day": len(_DAY_ISO_RE.findall(text)),
        "month": len(_MONTH_NAMED_RE.findall(text)) + len(_MONTH_NUMERIC_RE.findall(text)),
        "year": len(_YEAR_RE.findall(text)),
    }


# ---------------------------------------------------------------------------
# Anchor estimation
# ---------------------------------------------------------------------------


def estimate_time_anchor(
        text: str,
        heading_paths: Iterable[str] | None = None,
        unit: UnitName = "year",
) -> TimeEstimate:
    """Pick the most recent anchor at the given unit.

    Priority:
      1. Max marker found in heading paths (structural).
      2. Max marker in a cover-page phrase ("Fiscal 2026 ...", "year ended ...").
      3. Max marker anywhere in the text (weaker; many false positives).
    """
    if unit not in UNITS:
        raise ValueError(f"unsupported unit: {unit!r}")

    headings = list(heading_paths or [])

    # 1. Structural: pull markers out of headings
    struct_markers = _extract_markers_from_headings(headings, unit)
    if struct_markers:
        chosen = max(struct_markers)
        conf = 0.9 if len(struct_markers) >= 3 else 0.7
        return TimeEstimate(
            value=chosen,
            confidence=conf,
            reason=(
                f"max of {len(struct_markers)} {unit}-level markers found in "
                f"heading paths"
            ),
        )

    # 2. Cover-page phrases in the first ~3000 chars of the document.
    #    Typical patterns: "fiscal 2026", "for the fiscal year ended ...",
    #    "year ended December 31, 2023".
    cover = text[:3000]
    cover_markers = _extract_markers_from_cover(cover, unit)
    if cover_markers:
        chosen = max(cover_markers)
        return TimeEstimate(
            value=chosen,
            confidence=0.75,
            reason=f"cover-page phrase matched {unit}-level marker {chosen!r}",
        )

    # 3. Full-text scan as a last resort.
    all_markers = _extract_all_markers(text, unit)
    if all_markers:
        chosen = max(all_markers)
        return TimeEstimate(
            value=chosen,
            confidence=0.4,
            reason=(
                f"max of {len(all_markers)} {unit}-level markers in full text "
                f"(weak signal)"
            ),
        )

    # 4. Nothing found - return today's date at the requested unit, with low
    #    confidence so the caller knows to prompt.
    today = date.today()
    if unit == "year":
        fallback = f"{today.year}"
    elif unit == "month":
        fallback = f"{today.year:04d}-{today.month:02d}"
    else:
        fallback = today.isoformat()
    return TimeEstimate(
        value=fallback,
        confidence=0.1,
        reason="no time markers found; falling back to today's date",
    )


def _extract_markers_from_headings(
        headings: Iterable[str], unit: UnitName,
) -> list[str]:
    out: list[str] = []
    for h in headings:
        for seg in re.split(r"\s*>\s*|\s*/\s*", h):
            seg = seg.strip().strip("*_#` ")
            if not seg:
                continue
            m = _extract_marker_from_segment(seg, unit)
            if m:
                out.append(m)
                break
    return out


def _extract_markers_from_cover(cover: str, unit: UnitName) -> list[str]:
    out: list[str] = []
    # Narrow phrase-level regexes: "fiscal YEAR", "year ended ... YEAR",
    # "for ... ending ... YEAR", etc.
    phrase_patterns = [
        re.compile(r"\bfiscal\s+(?:year\s+)?(?P<y>(?:19|20)\d{2})\b", re.IGNORECASE),
        re.compile(r"\byear\s+ended[^,]*,?\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?(?P<y>(?:19|20)\d{2})\b", re.IGNORECASE),
        re.compile(
            r"\bfor\s+the\s+(?:fiscal\s+)?year\s+(?:ending|ended)[^,]*,?\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?(?P<y>(?:19|20)\d{2})\b",
            re.IGNORECASE),
        re.compile(r"\bannual\s+report\s+(?:for\s+)?(?:fiscal\s+)?(?P<y>(?:19|20)\d{2})\b", re.IGNORECASE),
    ]
    if unit == "year":
        for pat in phrase_patterns:
            for m in pat.finditer(cover):
                out.append(m.group("y"))
        return out

    # For month / day we reuse the generic extractor but restricted to the cover
    return _extract_all_markers(cover, unit)


def _extract_all_markers(text: str, unit: UnitName) -> list[str]:
    if unit == "year":
        return _YEAR_RE.findall(text)
    if unit == "month":
        out: list[str] = []
        for m in _MONTH_NAMED_RE.finditer(text):
            month = _MONTH_NAME_TO_NUM[m.group("month").lower()]
            out.append(f"{int(m.group('year')):04d}-{month:02d}")
        for m in _MONTH_NUMERIC_RE.finditer(text):
            out.append(f"{int(m.group('year')):04d}-{int(m.group('month')):02d}")
        return out
    if unit == "day":
        return [m.group(0) for m in _DAY_ISO_RE.finditer(text)]
    return []


def _extract_marker_from_segment(segment: str, unit: UnitName) -> str | None:
    if unit == "day":
        m = _DAY_ISO_RE.search(segment)
        return m.group(0) if m else None
    if unit == "month":
        m = _MONTH_NUMERIC_RE.search(segment)
        if m:
            return f"{int(m.group('year')):04d}-{int(m.group('month')):02d}"
        m = _MONTH_NAMED_RE.search(segment)
        if m:
            month = _MONTH_NAME_TO_NUM[m.group("month").lower()]
            return f"{int(m.group('year')):04d}-{month:02d}"
        return None
    if unit == "year":
        if _YEAR_ONLY_RE.match(segment):
            return segment
        m = _YEAR_RE.search(segment)
        return m.group(0) if m else None
    return None
