# -*- coding: utf-8 -*-
"""
    common.models.turn
    ~~~~~~~~~~~~~~~~~~

    Turn model specification.
"""

from datetime import datetime
from typing import Literal, get_args

from pydantic import Field

from common.models.base import CustomBaseModel
from common.models.validation import MongoID, object_id_str, utc_now

_T_VER_TURNS = Literal[1]
VER_TURNS: int = get_args(_T_VER_TURNS)[0]


class Turn(CustomBaseModel):
    id: MongoID = Field(alias="_id", default_factory=object_id_str)
    session_id: str

    project_id: str | None = None
    user_id: str | None = None

    user_query: str = ""
    system_response: str = ""

    matched_kb_ids: list[str] = Field(default_factory=list)
    matched_pages: list[int] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_TURNS = VER_TURNS
