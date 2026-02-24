# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders.docx
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Microsoft Word (docx) document loader.
"""

from pathlib import Path

from docx import Document
from docx.document import Document as Doc
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import TextSplitter

STYLE_MAP = {
    "Title": "title",
    # "Heading 1": "h1",
    # "Heading 2": "h2",
    # "Heading 3": "h3",
    # "Heading 4": "h4",
    # "Normal": "normal",
}


def iter_block_items(parent):
    """
    Yield each block item (paragraph/table) within <parent> in document order.

    :param parent: Document or _Cell object
    :return: generator of block items
    """

    if isinstance(parent, Doc):
        parent_elm = parent.element.body
    # elif isinstance(parent, _Cell):
    #     parent_elm = parent._tc
    else:
        raise ValueError("parent is neither Doc or Cell instance")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def iter_unique_cells(row):
    """
    Yield unique cells from a table row. Skips duplicates caused by cell merging.

    :param row: table row object
    :return: unique cells generator
    """

    tmp = None

    for cell in row.cells:
        if cell is tmp:
            continue

        tmp = cell
        yield cell


def table_text(table) -> list[str]:
    """
    Retrieve text from a table object.

    :param table: table object
    :return: list of table row texts
    """

    out = []
    for row in table.rows:
        text = [c.text.strip() for c in iter_unique_cells(row)]
        text = [" ".join(t.split()) for t in text if t]
        out.append("\n".join(text))

    return [t for t in out if t]


def paragraph_text(paragraph) -> str:
    """
    Retrieve text from a paragraph object.

    :param paragraph: paragraph object
    :return: processed paragraph text
    """

    text = paragraph.text.strip()
    text = " ".join(text.split())
    return text


class PyDOCXLoader:

    def __init__(self, file_path: str | Path):
        self.file_path = file_path

    def load(self) -> list[LCDocument]:

        content, metadata = [], {}
        doc = Document(self.file_path)

        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                txt = paragraph_text(block)
                content.append(txt)

                if hasattr(block, "style") and getattr(block.style, "name") in STYLE_MAP:
                    if (key := f"content_{STYLE_MAP[block.style.name]}") not in metadata:
                        metadata[key] = []
                    metadata[key].append(txt)
            else:
                content.extend(table_text(block))

        content = [c for c in content if c]
        content = "\n".join(content)
        metadata = {k: "\n".join(set(v)) for k, v in metadata.items()}

        return [LCDocument(page_content=content, metadata=metadata)]

    def load_and_split(self, text_splitter: TextSplitter) -> list[LCDocument]:
        return text_splitter.split_documents(self.load())
