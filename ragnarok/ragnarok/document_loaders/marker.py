# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders.marker
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Document loader for MD file output from the marker-pdf package.
"""

import re
from pathlib import Path
from typing import Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

RE_PAGES = re.compile(r"^\{(\d+)}-{48}\s*$", flags=re.MULTILINE)


class MarkerMDLoader(BaseLoader):

    def __init__(self, file_path: str | Path):
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        with open(self.file_path, "r") as f:
            content = f.read()

        matches = list(RE_PAGES.finditer(content))
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
