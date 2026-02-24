# -*- coding: utf-8 -*-
"""
    ragnarok.api.projects
    ~~~~~~~~~~~~~~~~~~~~~

    Project management endpoints.
"""

from fastapi import status
from fastapi.routing import APIRouter

from common.models import api as ma
from common.utils.api import error_handler
from ragnarok.vector_db import VectorStore

router = APIRouter()
VS = VectorStore()


@router.get(
    "/",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List available project IDs",
)
@error_handler
def list_project_ids() -> list[str]:
    """
    List available project IDs.

    :return: list of project IDs
    """

    return sorted(VS.get_project_ids())


@router.delete(
    "/{project_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete project data from vector DB",
)
@error_handler
def delete_project_data(project_id: str) -> ma.DeletedCount:
    """
    Delete project data from vector DB.

    :param project_id: project ID
    :return: deleted count
    """

    deleted, deleted_hl = VS.delete_project(project_id=project_id, raise_not_found=False)
    return ma.DeletedCount(deleted_es_chunks=deleted, deleted_es_chunks_highlight=deleted_hl)
