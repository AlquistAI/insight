# -*- coding: utf-8 -*-
"""
    common.models.conversion
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Document conversion models.
"""

from typing import Literal

from common.models.base import CustomBaseModel


class ConversionOptions(CustomBaseModel):
    # Accelerator for Docling layout/table models:
    # - 'auto': selects the best available device (checks for CUDA, then MPS, otherwise falls back to CPU)
    # - 'cpu': runs on CPU
    # - 'cuda': runs on CUDA-enabled GPU
    # - 'mps': forces Apple Metal
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"

    # OCR mode:
    # - 'auto': reads the PDF text layer and only OCRs embedded bitmaps/figures (safe for digital and mixed PDFs)
    # - 'off': disables OCR entirely (fastest; use only for pure-digital PDFs with no text inside images)
    # - 'force': OCRs every page (for scanned PDFs or an untrusted text layer)
    ocr: Literal["auto", "off", "force"] = "off"

    # Recover heading levels before export (Docling labels every heading the same level by default):
    # - 'auto': tries ToC, then heading numbering, then font size, picking the first that covers enough of the document
    # - 'none': leaves levels untouched
    hierarchy: Literal["auto", "toc", "numbering", "font-size", "none"] = "auto"

    # Minimum fraction of detected headings a stronger signal must cover before it is preferred over font size
    hierarchy_threshold: float = 0.6

    # Heading heights within this many points are treated as the same level in the font-size strategy
    hierarchy_tolerance: float = 0.75

    # Insert page markers in the Markdown output; one per physical PDF page
    paginate: bool = True

    # Convert in page batches and log progress + ETA (useful for long PDFs, which otherwise run silently)
    # Reuses one converter so models stay loaded
    progress: bool = True

    # Pages per batch when "progress" is enabled
    progress_batch_size: int = 10
