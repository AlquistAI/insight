# -*- coding: utf-8 -*-
"""
    alchemist.api.conversion
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Document conversion endpoints.
"""

import json
from typing import Generator, Literal

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from alchemist.conversion.pdf2md import convert_streaming as convert_pdf2md_streaming
from common.models.conversion import ConversionOptions
from common.utils.api import error_handler

router = APIRouter()


@router.post(
    "/pdf2md",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert PDF to Markdown, streaming conversion progress",
)
@error_handler
def pdf2md(
        file: UploadFile,
        ocr: Literal["auto", "off", "force"] = "off",
        hierarchy: Literal["auto", "toc", "numbering", "font-size", "none"] = "auto",
        hierarchy_threshold: float = 0.6,
        hierarchy_tolerance: float = 0.75,
) -> StreamingResponse:
    """
    Convert PDF to Markdown, streaming NDJSON progress events while the (CPU-bound) conversion runs.

    Each line is one JSON object. Progress lines look like {"stage": "convert", "percent": ...}; the final
    line carries the result: {"stage": "convert", "done": true, "content": <Markdown>}.

    :param file: input PDF file
    :param ocr: OCR mode
    :param hierarchy: recover heading levels before export
    :param hierarchy_threshold: minimum fraction of detected headings a signal must cover before it is considered
    :param hierarchy_tolerance: heading heights within this many points are treated as the same level (font-size)
    :return: NDJSON stream of conversion progress ending with the Markdown content
    """

    opts = ConversionOptions(
        ocr=ocr,
        hierarchy=hierarchy,
        hierarchy_threshold=hierarchy_threshold,
        hierarchy_tolerance=hierarchy_tolerance,
    )

    content = file.file.read()

    def event_stream() -> Generator[str, None, None]:
        for event in convert_pdf2md_streaming(content, opts):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
