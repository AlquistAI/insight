# -*- coding: utf-8 -*-
"""
    common.services.alchemist
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Alchemist service utilities.
"""

import json
from typing import BinaryIO, Generator, Literal

import requests

from common.config import CONFIG

ALCHEMIST_URL = str(CONFIG.ALCHEMIST_URL).rstrip("/")

HEADERS = {
    "accept": "application/json",
    "X-Api-Key": CONFIG.ALCHEMIST_API_KEY.get_secret_value(),
}


def convert_pdf2md(
        file: BinaryIO,
        ocr: Literal["auto", "off", "force"] = "off",
        hierarchy: Literal["auto", "toc", "numbering", "font-size", "none"] = "auto",
        hierarchy_threshold: float = 0.6,
        hierarchy_tolerance: float = 0.75,
) -> Generator[dict, None, None]:
    """
    Convert a PDF file to Markdown using Alchemist, streaming conversion progress.

    Yields the parsed NDJSON events emitted by Alchemist: a progress dict after each page batch and a terminal
    dict carrying {"done": true, "content": <Markdown>}.

    :param file: PDF file to convert
    :param ocr: OCR mode
    :param hierarchy: recover heading levels before export
    :param hierarchy_threshold: minimum fraction of detected headings a signal must cover before it is considered
    :param hierarchy_tolerance: heading heights within this many points are treated as the same level (font-size)
    :return: generator of conversion progress events
    """

    res = requests.post(
        url=f"{ALCHEMIST_URL}/conversion/pdf2md",
        params={
            "ocr": ocr,
            "hierarchy": hierarchy,
            "hierarchy_threshold": hierarchy_threshold,
            "hierarchy_tolerance": hierarchy_tolerance,
        },
        files={"file": file},
        headers=HEADERS,
        timeout=(5, 3600),  # The conversion is CPU-bound and can take hours for long PDFs
        stream=True,
    )

    res.raise_for_status()

    for line in res.iter_lines():
        if line:
            yield json.loads(line.decode())
