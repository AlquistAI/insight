# -*- coding: utf-8 -*-
"""
    common.models.api
    ~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in APIs.
"""

from typing import Any

from pydantic import ValidationInfo, field_validator

from common.models.base import CustomBaseModel
from common.models.knowledge_base import KnowledgeBase
from common.models.project import Project
from common.models.session import Session
from common.models.turn import Turn


class DeletedCount(CustomBaseModel):
    deleted_db_knowledge_base: int = 0
    deleted_db_projects: int = 0
    deleted_db_sessions: int = 0
    deleted_db_turns: int = 0
    deleted_es_chunks: int = 0
    deleted_es_chunks_highlight: int = 0
    deleted_storage_blobs: int = 0


class Pagination(CustomBaseModel):
    page_no: int
    per_page: int
    total: int


class PaginationBaseModel(CustomBaseModel):
    data: list[Any]
    pagination: Pagination | None

    @field_validator("pagination")
    @classmethod
    def empty_pagination(cls, v: Pagination | None, info: ValidationInfo) -> Pagination:
        if v:
            return v

        data_len = len(info.data["data"])
        return Pagination(page_no=1, per_page=data_len, total=data_len)


class PaginatedKnowledgeBase(PaginationBaseModel):
    data: list[KnowledgeBase]


class PaginatedProjects(PaginationBaseModel):
    data: list[Project]


class PaginatedSessions(PaginationBaseModel):
    data: list[Session]


class PaginatedTurns(PaginationBaseModel):
    data: list[Turn]
