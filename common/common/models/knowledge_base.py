# -*- coding: utf-8 -*-
"""
    common.models.knowledge_base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Knowledge base model specification.
"""

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import Field

from common.models import defaults as df
from common.models.base import CustomBaseModel
from common.models.enums import SourceType
from common.models.validation import Language, MongoID, object_id_str, utc_now

_T_VER_KB = Literal[3]
VER_KB: int = get_args(_T_VER_KB)[0]


class KnowledgeBase(CustomBaseModel):
    id: MongoID = Field(alias="_id", default_factory=object_id_str)
    project_id: str

    name: str = ""
    description: str = ""

    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_model: str = df.MODEL_EMB
    language: Language = df.LANG
    total_pages: int = 1

    source_file: str | None = None
    source_type: SourceType = SourceType.PDF

    enable_highlights: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_KB = VER_KB
