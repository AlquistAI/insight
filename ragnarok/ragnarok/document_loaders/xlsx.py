# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders.xlsx
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Microsoft Excel (xlsx) document loader.
"""

import csv
import io
from pathlib import Path

import openpyxl
from langchain_core.documents import Document
from langchain_text_splitters import TextSplitter

DOC_FORMAT = (
    "SHEET NAME: {sheet_name}\n\n"
    "The following text is an Excel sheet content converted to the CSV format:\n\n"
    "<csv>\n{csv_content}\n<\csv>"
)


class OpenPyXLLoader:

    def __init__(self, file_path: str | Path):
        self.file_path = file_path

    def load(self) -> list[Document]:

        documents = []
        wb = openpyxl.load_workbook(self.file_path)

        for ws in wb.worksheets:
            output = io.StringIO()
            writer = csv.writer(output)

            for row in ws.rows:
                writer.writerow([cell.value for cell in row])

            content = DOC_FORMAT.format(sheet_name=ws.title, csv_content=output.getvalue())
            documents.append(Document(page_content=content, metadata={"title": ws.title}))

        return documents

    def load_and_split(self, text_splitter: TextSplitter) -> list[Document]:
        return text_splitter.split_documents(self.load())
