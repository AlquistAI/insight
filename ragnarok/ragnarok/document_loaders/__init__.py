# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Custom document loaders implementing the LangChain loader interface.
"""

import os
from tempfile import NamedTemporaryFile

from langchain_community.document_loaders import BSHTMLLoader, PyMuPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.models.enums import SourceType
from common.utils import exceptions as exc
from ragnarok.document_loaders.docx import PyDOCXLoader
from ragnarok.document_loaders.pptx import PyPPTXLoader
from ragnarok.document_loaders.xlsx import OpenPyXLLoader


def parse_file(content: bytes, source_type: SourceType) -> list[Document]:
    """
    Parse file contents into LangChain documents.

    :param content: binary file content
    :param source_type: type/format of the content (e.g. PDF)
    :return: parsed documents
    """

    tmp_file = NamedTemporaryFile(delete=False, suffix=f".{source_type.value}")
    tmp_file.write(content)
    tmp_file.close()

    if source_type == SourceType.DOCX:
        func = parse_docx
    elif source_type == SourceType.HTML:
        func = parse_html
    elif source_type == SourceType.PDF:
        func = parse_pdf
    elif source_type == SourceType.PPTX:
        func = parse_pptx
    elif source_type == SourceType.TXT:
        func = parse_txt
    elif source_type == SourceType.XLSX:
        func = parse_xlsx
    else:
        raise ValueError(f"Unsupported source type: {source_type.value}")

    documents = func(tmp_file.name)
    os.remove(tmp_file.name)

    if not documents:
        raise exc.DocumentParsingError("Document loader did not return any documents")

    # Normalize page numbers and fill chunk indices
    # ToDo: Per-page chunk indices in case the pages are also split into multiple chunks.
    for idx, document in enumerate(documents):
        document.metadata["chunk_idx"] = idx
        document.metadata["page"] = document.metadata.get("page", 0) + 1

    return documents


def parse_docx(path: str, chunk_size: int = 2500, chunk_overlap: int = 200) -> list[Document]:
    return _load_and_split(loader=PyDOCXLoader(path), chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def parse_html(path: str, chunk_size: int = 2500, chunk_overlap: int = 200) -> list[Document]:
    return _load_and_split(loader=BSHTMLLoader(path), chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def parse_pdf(path: str) -> list[Document]:
    return PyMuPDFLoader(path).load()


def parse_pptx(path: str) -> list[Document]:
    return PyPPTXLoader(path).load()


def parse_txt(path: str, chunk_size: int = 2500, chunk_overlap: int = 200) -> list[Document]:
    return _load_and_split(loader=TextLoader(path), chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def parse_xlsx(path: str) -> list[Document]:
    return OpenPyXLLoader(path).load()


def _load_and_split(loader, chunk_size: int, chunk_overlap: int) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    documents = loader.load_and_split(text_splitter)

    for document in documents:
        document.metadata.update({"chunk_size": chunk_size, "chunk_overlap": chunk_overlap})

    return documents
