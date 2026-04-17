# -*- coding: utf-8 -*-
"""
    common.models.elastic
    ~~~~~~~~~~~~~~~~~~~~~

    ElasticSearch models.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from common.models.base import CustomBaseModel
from common.models.enums import SourceType
from common.models.validation import Language, utc_now


class DocumentLoaderMetadata(CustomBaseModel):
    author: str = ""
    keywords: str = ""
    subject: str = ""
    title: str = ""

    chunk_idx: int = 0
    chunk_size: int | None = None
    chunk_overlap: int | None = None

    page: int = 1
    total_pages: int = 1

    creationdate: datetime | None = None
    moddate: datetime | None = None


class KBMetadata(DocumentLoaderMetadata):
    kb_id: str
    project_id: str | None = None

    embedding_model: str
    language: Language
    source_file: str | None = None
    source_type: SourceType = SourceType.PDF

    batch_id: str = ""
    retries: int = 0

    custom: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class KBSource(CustomBaseModel):
    metadata: KBMetadata
    text: str
    vector: list[float] | None = None


class KBEntry(CustomBaseModel):
    id: str = Field(alias="_id")
    index: str = Field(alias="_index")
    score: float = Field(alias="_score")
    source: KBSource = Field(alias="_source")
