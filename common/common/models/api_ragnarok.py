# -*- coding: utf-8 -*-
"""
    common.models.api_ragnarok
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in Ragnarok APIs.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from common.models import defaults as df, elastic as me
from common.models.base import CustomBaseModel
from common.models.enums import SourceType
from common.models.project import AISettings


####################
## KNOWLEDGE BASE ##
####################

class KBMetadataUpdate(CustomBaseModel):
    source_file: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)


#########
## NLP ##
#########

class ConversationTurn(CustomBaseModel):
    user_query: str
    system_response: str
    created_at: datetime


class RAGPayload(CustomBaseModel):
    query: str
    context: list[ConversationTurn] = Field(default_factory=list)

    ftr_custom: list[dict[str, Any]] | None = None
    kb_ids: list[str] | None = None
    lang: str = df.LANG
    settings: AISettings = Field(default_factory=AISettings)

    return_highlights: bool = False
    return_matched_chunks: bool = True


class RAGTopMatch(CustomBaseModel):
    kb_id: str
    language: str
    page: int
    source_file: str
    source_type: SourceType


class RAGHighlightSpan(CustomBaseModel):
    kb_id: str
    source_file: str
    page: int
    start: int
    end: int
    text: str

    score: float | None = None
    chunk_index: int | None = None
    chunk_level: str | None = None


class RAGHighlightGroup(CustomBaseModel):
    l0_chunk: RAGHighlightSpan | None
    l1_chunks: list[RAGHighlightSpan]


class RAGResponse(CustomBaseModel):
    generated_text: str | None = None
    top_match: RAGTopMatch

    highlights: list[RAGHighlightGroup] | None = None
    matched_chunks: list[me.KBEntry] | None = None


class HighlightRequest(CustomBaseModel):
    payload: RAGPayload
    hit: me.KBEntry
