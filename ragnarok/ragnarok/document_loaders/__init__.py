# -*- coding: utf-8 -*-
"""
    ragnarok.document_loaders
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Custom document loaders implementing the LangChain loader interface.
"""

from ragnarok.document_loaders.docx import PyDOCXLoader
from ragnarok.document_loaders.pptx import PyPPTXLoader
from ragnarok.document_loaders.xlsx import OpenPyXLLoader
