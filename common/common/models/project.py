# -*- coding: utf-8 -*-
"""
    common.models.project
    ~~~~~~~~~~~~~~~~~~~~~

    Project model specification.
"""

from datetime import datetime
from typing import Literal, get_args

from pydantic import Field

from common.config import DF
from common.models.base import CustomBaseModel
from common.models.rag import AISettings
from common.models.validation import Language, MongoID, object_id_str, utc_now

_T_VER_PROJECTS = Literal[4]
VER_PROJECTS = get_args(_T_VER_PROJECTS)[0]


class Project(CustomBaseModel):
    id: MongoID = Field(alias="_id", default_factory=object_id_str)

    author: str = ""
    description: str = ""
    language: Language = DF.LANG
    name: str = ""

    ai_settings: AISettings = Field(default_factory=AISettings)

    created_at: datetime = Field(default_factory=utc_now)
    modified_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_PROJECTS = VER_PROJECTS
