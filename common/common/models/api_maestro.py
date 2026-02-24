# -*- coding: utf-8 -*-
"""
    common.models.api_maestro
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in Maestro APIs.
"""

from typing import Any, Literal

from pydantic import Field

from common.models.base import CustomBaseModel
from common.models.fsm import DotCommand, State


class FeedbackPayload(CustomBaseModel):
    top_kb_id: str
    top_page: int

    feedback: Literal[1, -1] | None = None
    feedback_text: str = ""

    program: str | None = None


class QueryPayload(CustomBaseModel):
    # ToDo: Use the payload defined for Kronos (unify payloads).

    query: str
    kb_ids: list[str] = Field(default_factory=list)

    lang: str | None = None
    top_n_count: int = 5

    return_highlights: bool = False
    return_matched_chunks: bool = True


class HighlightRequest(CustomBaseModel):
    # ToDo: Use the payload defined for Ragnarok (unify payloads).

    payload: QueryPayload
    hit: dict[str, Any]


class SessionStartResponse(CustomBaseModel):
    session_id: str
    state_id: int
    state: State

    commands: list[DotCommand] = Field(default_factory=list)
    language: str
