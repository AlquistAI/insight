# pdf2md

A two-step CLI that turns a PDF into RAG-ready artifacts, plus an optional uploader to Kronos.

1. **`pdf2md.py`** — PDF → Markdown via [marker-pdf](https://github.com/VikParuchuri/marker).
2. **`md2chunks.py`** — paginated Markdown + source PDF → per-page JSON, section tree, and breadcrumb-prefixed chunks
   JSONL.
3. **`upload_to_kronos.py`** — paginated Markdown + source PDF → knowledge base in a Kronos project.

The two scripts are deliberately separated: step 1 is slow (ML models) and rarely re-run; step 2 is fast pure Python and
gets re-run every time you tweak chunking, filtering, or time-estimation logic.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first run of `pdf2md.py` downloads Marker's models (~260 MB) into `~/Library/Caches/datalab/` (macOS) or the
equivalent on Linux. Subsequent runs reuse the cache.

---

## `pdf2md.py` — PDF → Markdown

```
python pdf2md.py <input.pdf> [options]
```

| Flag                  | Description                                                                                   |
|-----------------------|-----------------------------------------------------------------------------------------------|
| `-o`, `--output PATH` | Output `.md` path (default: input path with `.md` extension).                                 |
| `-f`, `--force`       | Overwrite existing output file and image folder.                                              |
| `-p`, `--paginate`    | Insert page markers between pages. **Required if you plan to run `md2chunks.py`** afterwards. |
| `-h`, `--help`        | Show help.                                                                                    |

### Outputs

- `<stem>.md` — the rendered Markdown. With `--paginate`, pages are separated by:
  ```
  \n\n{<physical_page_id>}------------------------------------------------\n\n
  ```
  where `<physical_page_id>` is a 0-indexed integer.
- `<stem>/` — sibling folder containing every image Marker extracted, named by Marker's internal IDs and referenced from
  the `.md` by relative path. The folder is created only if the PDF actually contains images.

### Behavior notes

- Marker chooses per-line whether to OCR. Digital PDFs with a clean text layer skip OCR entirely; scanned PDFs OCR
  everything; mixed PDFs OCR only the broken lines (detected by Marker's "OCR error detection" stage).
- On Apple Silicon, Marker uses the MPS (Metal) backend automatically. One sub-model (table recognizer) falls back to
  CPU — this is harmless.
- To force CPU: `TORCH_DEVICE=cpu python pdf2md.py paper.pdf`.
- For long conversions, keep the Mac awake: `caffeinate -i -s -w $(pgrep -f pdf2md.py) &`.

### Example

```bash
python pdf2md.py paper.pdf                       # paper.md (+ paper/ for images)
python pdf2md.py paper.pdf -o notes/paper.md     # custom location
python pdf2md.py paper.pdf --paginate --force    # paginated, overwrite
```

---

## `md2chunks.py` — Markdown → RAG artifacts

```
python md2chunks.py <paginated.md> <source.pdf> [options]
```

The `.md` must be the paginated output of `pdf2md.py --paginate`. The original PDF is needed to resolve printed page
labels (e.g. `i`, `A-3`, `12`) via `pypdfium2`.

| Flag                     | Description                                                                                                                                |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `-o`, `--outdir DIR`     | Directory for output files (default: same directory as the `.md`).                                                                         |
| `-f`, `--force`          | Overwrite existing output files.                                                                                                           |
| `--max-chars N`          | Soft character budget per chunk (default: 1200).                                                                                           |
| `--filter`               | Drop sections whose heading matches built-in noise patterns (TOC, Glossary, References, Index, Executive Summary, Acknowledgments, About). |
| `--filter-heading REGEX` | Additional case-insensitive heading regex to filter. Repeatable. Implies `--filter`.                                                       |
| `--no-default-filters`   | Skip the built-in noise list (useful when combined with `--filter-heading`).                                                               |
| `--source NAME`          | Override the `source` field on every chunk record (default: PDF file name).                                                                |

### Outputs

For an input named `paper.md` + `paper.pdf`, three files are written next to the `.md`:

- `paper.pages.json` — per-page markdown with printed page labels.
- `paper.sections.json` — heading skeleton tree, document-wide time estimates.
- `paper.chunks.jsonl` — one chunk per line, ready for embedding.

### Pipeline (what the script does)

1. **Page index.** Reads the page-marker line format above to map every line of the `.md` to a physical page; records
   `pypdfium2.PdfDocument.get_page_label(i)` for each.
2. **Skeleton tree.** Walks ATX headings (skipping fenced code blocks), builds a `sec-NNNN` tree with parent/child
   links, line/char/page ranges. A synthetic `sec-root` wraps everything.
3. **Chunking.** For each section, takes only the lines that belong to its own body (excluding child-section lines),
   groups paragraphs (split on blank lines, with page markers and image-only lines stripped from text but line numbers
   preserved), and packs paragraphs greedily up to `--max-chars`. Oversized paragraphs are split on sentence
   boundaries (`re.split(r'(?<=[.!?])\s+', …)`); if still too large, hard-split. **Chunks never cross a heading.**
4. **Breadcrumb injection.** Every chunk's `text` is prefixed with its heading path (`A > B > C\n\n<body>`), so
   embeddings carry structural context.
5. **Noise filter.** If `--filter` (or `--filter-heading`) is passed, sections matching a regex are marked
   `filtered: true` and their chunks are excluded from `chunks.jsonl`. Filtered sections stay in `sections.json` so a
   pointer-based synthesizer can still load them intentionally.
6. **Time estimation.** Calls `time_estimation.estimate_time_unit(...)` and `estimate_time_anchor(...)` over the
   document text and all heading paths. The result lands at the top of `sections.json` with full
   `{value, confidence, reason}`. Each chunk gets `time_unit` (doc-wide) and `time_anchor` (refined from the section's
   own heading path when that gives a confident result ≥0.7; otherwise the document anchor).

### Output schema reference

#### `<stem>.pages.json`

```json
{
  "document": "paper.pdf",
  "pages": [
    {"page": 1, "page_label": "i", "markdown": "# Title\n\n..."},
    {"page": 2, "page_label": "1", "markdown": "## Introduction\n\n..."}
  ]
}
```

| Field                 | Type   | Meaning                                                                                   |
|-----------------------|--------|-------------------------------------------------------------------------------------------|
| `document`            | string | `--source` value or PDF file name.                                                        |
| `pages[i].page`       | int    | 1-indexed physical page.                                                                  |
| `pages[i].page_label` | string | Printed label (`pypdfium2.get_page_label`); falls back to `str(i+1)`.                     |
| `pages[i].markdown`   | string | Markdown for just that page; page markers stripped, leading/trailing blank lines trimmed. |

#### `<stem>.sections.json`

```json
{
  "document": "paper.pdf",
  "root_id": "sec-root",
  "sections": {
    "sec-root": {...},
    "sec-0001": {...},
    "sec-0002": {...}
  },
  "time_unit": {"value": "year", "confidence": 0.88, "reason": "..."},
  "time_anchor": {"value": "2026", "confidence": 0.90, "reason": "..."}
}
```

Per-section fields:

| Field          | Type         | Meaning                                                                                           |
|----------------|--------------|---------------------------------------------------------------------------------------------------|
| `id`           | string       | `sec-NNNN`, or `sec-root` for the document wrapper. Matches `chunks.jsonl.section_id`.            |
| `level`        | int          | ATX heading level 1–6; `0` only for `sec-root`.                                                   |
| `heading`      | string       | Raw heading text as it appears in the `.md` (may include markdown emphasis).                      |
| `heading_path` | string       | Full breadcrumb from root, joined with `" > "`. Empty for root.                                   |
| `parent_id`    | string\|null | Parent section ID; `null` only for root.                                                          |
| `children_ids` | string[]     | Direct children in document order.                                                                |
| `heading_line` | int          | 1-indexed line of the heading in the `.md`; `0` for root.                                         |
| `line_start`   | int          | 1-indexed first body line (line after the heading).                                               |
| `line_end`     | int          | 1-indexed inclusive last line, including all descendant subsections.                              |
| `char_start`   | int          | 0-indexed offset in the `.md` where the body begins.                                              |
| `char_end`     | int          | Exclusive end offset. `md_text[char_start:char_end]` returns the section verbatim.                |
| `page_start`   | int          | 1-indexed physical page containing `line_start`.                                                  |
| `page_end`     | int          | 1-indexed physical page containing `line_end`.                                                    |
| `filtered`     | bool         | Present and `true` only when `--filter`/`--filter-heading` matched this section (or an ancestor). |

`time_unit` / `time_anchor` are produced by `time_estimation.py`; see [Time estimation](#time-estimation) below.

#### `<stem>.chunks.jsonl`

One JSON object per line.

```json
{
  "id": "paper-0007",
  "text": "Solar System > Inner Planets > Mercury\n\nMercury is...",
  "heading_path": "Solar System > Inner Planets > Mercury",
  "section_id": "sec-0023",
  "page": 2,
  "page_label": "1",
  "page_physical": 2,
  "line_start": 12,
  "line_end": 18,
  "source": "paper.pdf",
  "time_unit": "year",
  "time_anchor": "2026"
}
```

| Field                    | Type   | Meaning                                                                                                                                       |
|--------------------------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                     | string | Per-document chunk ID, `<md_stem>-NNNN`, 1-indexed, zero-padded to 4.                                                                         |
| `text`                   | string | What you embed: `heading_path + "\n\n" + body`.                                                                                               |
| `heading_path`           | string | Same string the `text` starts with; for citation display in your UI.                                                                          |
| `section_id`             | string | Pointer into `sections.json` for pointer-based context retrieval.                                                                             |
| `page`, `page_physical`  | int    | 1-indexed physical page where the chunk starts. Identical; `page` is the convenience alias.                                                   |
| `page_label`             | string | Printed label from the PDF (use this when displaying citations to humans).                                                                    |
| `line_start`, `line_end` | int    | 1-indexed inclusive line range in the combined `.md` file.                                                                                    |
| `source`                 | string | Originating document; `--source` value or PDF file name.                                                                                      |
| `time_unit`              | string | One of `"year"`, `"month"`, `"day"` — the document's reporting granularity.                                                                   |
| `time_anchor`            | string | Most recent reference point: `"2026"`, `"2026-03"`, or `"2026-03-15"`. Refined per section when its heading path contains a confident marker. |

**Invariants.** A chunk lives entirely inside one section — its line range never crosses a heading. Chunks are emitted
in document order. Chunk size respects `--max-chars` as a soft budget; a single paragraph that cannot be split further
may exceed it.

### Time estimation

`md2chunks.py` calls `time_estimation.estimate_time_unit(text, heading_paths)` and
`estimate_time_anchor(text, heading_paths, unit=...)`. Both return `TimeEstimate(value, confidence, reason)`.

- **Unit** is the document's reporting granularity. The detector prefers structural signals (heading paths organized by
  date) over text density, with `"year"` as the safe fallback.
- **Anchor** is the most recent marker at that unit, in this priority order: max marker found in heading paths →
  cover-page phrases like `"Fiscal 2026"` / `"year ended ..."` → max marker anywhere in the text → today's date (
  low-confidence fallback).
- The doc-wide `{value, confidence, reason}` triples land in `sections.json`. Per-chunk fields carry only the values; if
  a section's own heading path yields an anchor with confidence ≥ 0.7, the chunks under that section use the section
  anchor instead of the doc anchor.

`time_estimation.py` is a copy of the same-named module in the `alquist-lite` server (`server/app/time_estimation.py`).
**Keep the two copies in sync** — the contract relied on by both ingest paths must match.

### Example

```bash
python pdf2md.py paper.pdf --paginate --force
python md2chunks.py paper.md paper.pdf --filter --force
# -> paper.pages.json, paper.sections.json, paper.chunks.jsonl
```

```bash
# Override the source name and add a custom heading filter
python md2chunks.py paper.md paper.pdf \
    --source "ACME 2026 Annual Report" \
    --filter \
    --filter-heading "^safe harbor" \
    --max-chars 800 \
    --force
```

---

## `upload_to_kronos.py` — upload to Kronos

```
python upload_to_kronos.py <paginated.md> <source.pdf> -p PROJECT_ID [options]
```

Uploads the paginated Markdown (output of `pdf2md.py --paginate`) together with its source PDF to the Kronos
`POST /knowledge_base/file/marker` endpoint, which ingests them as a knowledge base in the given project.

| Flag                    | Description                                                             |
|-------------------------|-------------------------------------------------------------------------|
| `-p`, `--project-id ID` | **Required.** ID of the Kronos project to create the knowledge base in. |
| `-u`, `--url URL`       | Base URL of the Kronos API (default: `https://kronos-dev.alquist.ai`).  |
| `-k`, `--api-key KEY`   | Kronos API key (default: the `KRONOS_API_KEY` environment variable).    |
| `-h`, `--help`          | Show help.                                                              |

The created knowledge base (as JSON) is printed to stdout. The script exits non-zero if the upload fails.

### Example

```bash
python3 upload_to_kronos.py paper.md paper.pdf -p 6a159dffea23f137f05f2980 -k "sk-..."
```

---

## Troubleshooting

- **`error: <file>.pages.json already exists`** — pass `--force`, or write to a different `--outdir`.
- **`md2chunks.py` produces a single page** — your `.md` wasn't paginated. Re-run `pdf2md.py` with `--paginate`.
- **Empty/garbled chunks for a section** — Marker may have rendered the heading at an unexpected ATX level (e.g. `###`
  for what looks like a top-level title). Inspect `sections.json` to see the actual hierarchy; chunk boundaries follow
  the rendered headings, not the visual hierarchy in the PDF.
- **Time estimate is the wrong year** — the heuristic prefers heading paths over body text. If your headings don't carry
  years (or carry historical years like `"2015–2026"` ranges), `estimate_time_anchor` picks the max year found, which is
  usually correct; if not, run with `--filter-heading "^historical comparison"` (or similar) to drop noisy sections, or
  use the lower-confidence value as a hint and override downstream.
- **Marker prints `MallocStackLogging` warning** — harmless macOS noise, unset `MallocStackLogging` in your shell
  environment.
- **`Recognizing Layout` is taking forever** — that's CPU-bound on layout detection. Per-page time on Apple Silicon with
  MPS is ~5–15 s; on CPU it can be 4–10× slower. There's nothing wrong; it's just slow on long PDFs.

---

## Architecture summary

The bridge between the two scripts is the paginated Markdown format (`{<id>}` + 48 dashes between pages). `md2chunks.py`
parses that format with a single regex (`PAGE_MARKER_RE` in `md2chunks.py`). If you change `pdf2md.py`'s pagination
output, `md2chunks.py` will silently treat the file as one page — keep the format stable.

`md2chunks.py` is pure Python. It does not import Marker, PyTorch, or any ML library — only `pypdfium2` (for page
labels) and standard library. This keeps step 2 fast and lets you iterate on chunking/filtering/time logic without
re-running step 1.
