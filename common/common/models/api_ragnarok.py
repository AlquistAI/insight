# -*- coding: utf-8 -*-
"""
    common.models.api_ragnarok
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in Ragnarok APIs.
"""

from typing import Any

from pydantic import Field

from common.models import elastic as me
from common.models.base import CustomBaseModel
from common.models.rag import ConversationTurn, RAGOptions
from common.models.usage import UsageSummary


####################
## KNOWLEDGE BASE ##
####################

class KBMetadataUpdate(CustomBaseModel):
    source_file: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)


#########
## NLP ##
#########

class RAGPayload(RAGOptions):
    query: str
    context: list[ConversationTurn] = Field(default_factory=list)

    return_highlights: bool = False
    return_matched_chunks: bool = True


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
    highlights: list[RAGHighlightGroup] | None = None
    matched_chunks: list[me.KBEntry] | None = None
    usage: UsageSummary | None = None


class HighlightRequest(CustomBaseModel):
    payload: RAGPayload
    hit: me.KBEntry
