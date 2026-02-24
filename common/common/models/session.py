# -*- coding: utf-8 -*-
"""
    common.models.session
    ~~~~~~~~~~~~~~~~~~~~~

    Session model specification.
"""

from datetime import datetime
from typing import Literal, get_args

from pydantic import Field

from common.models.base import CustomBaseModel
from common.models.validation import Language, MongoID, object_id_str, utc_now

_T_VER_SESSIONS = Literal[1]
VER_SESSIONS: int = get_args(_T_VER_SESSIONS)[0]


class Session(CustomBaseModel):
    id: MongoID = Field(alias="_id", default_factory=object_id_str)

    project_id: str | None = None
    user_id: str | None = None

    name: str = ""
    description: str = ""
    language: Language | None = None

    document_id: str | None = None
    document_name: str = ""
    editor_content: str = ""

    created_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_SESSIONS = VER_SESSIONS
