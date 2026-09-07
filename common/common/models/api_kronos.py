# -*- coding: utf-8 -*-
"""
    common.models.api_kronos
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in Kronos APIs.
"""

from pydantic import Field

from common.models import api_ragnarok as mar, elastic as me
from common.models.rag import AISettings


class KBMetadata(me.KBMetadata):
    name: str = ""
    description: str = ""


class KBSource(me.KBSource):
    metadata: KBMetadata


class KBEntry(me.KBEntry):
    source: KBSource = Field(alias="_source")


class RAGPayload(mar.RAGPayload):
    ai_settings: AISettings | None = None
    lang: str | None = None


class RAGResponse(mar.RAGResponse):
    matched_chunks: list[KBEntry] | None = None
