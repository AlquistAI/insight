# -*- coding: utf-8 -*-
"""
    kronos.api.projects
    ~~~~~~~~~~~~~~~~~~~

    Project management endpoints.
"""

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from common.models import api as ma
from common.models.project import Project
from common.utils.api import error_handler
from kronos.services import ragnarok
from kronos.services.db.mongo import (
    knowledge_base as db_kb,
    projects as db_projects,
    sessions as db_sessions,
    turns as db_turns,
)
from kronos.services.storage import get_storage
from kronos.services.storage.base import DIR_PROJECT

router = APIRouter()
storage = get_storage()


@router.get(
    "/",
    response_model=ma.PaginatedProjects,
    status_code=status.HTTP_200_OK,
    summary="List general info for all available projects",
)
@error_handler
def list_projects(
        name: str | None = None,
        language: str | None = None,
        exact_match: bool = True,
        fields: str = "",
        sort_by: str = "",
        page_no: int = 1,
        per_page: int = 10,
) -> ma.PaginatedProjects | JSONResponse:
    """
    List general info for all available projects.

    The `exact_match` option currently only applies to the `name` field.

    :param name: project name
    :param language: project language
    :param exact_match: match the field values exactly (otherwise search for substrings)
    :param fields: field names in DB to include using projection (as CSV)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of projects
    """

    fields = {x.strip() for x in fields.split(",")} if fields else None

    data, total = db_projects.list_projects(
        name=name,
        language=language,
        exact_match=exact_match,
        fields=fields,
        sort_by=sort_by,
        page_no=page_no,
        per_page=per_page,
    )

    pagination = ma.Pagination(page_no=page_no, per_page=per_page, total=total) if per_page > 0 else None

    if fields:
        return JSONResponse(ma.PaginationBaseModel(data=data, pagination=pagination).model_dump(mode="json"))
    return ma.PaginatedProjects(data=data, pagination=pagination)


@router.get(
    "/{project_id}/",
    response_model=Project,
    status_code=status.HTTP_200_OK,
    summary="Get project data",
)
@error_handler
def get_project(project_id: str) -> Project:
    """
    Get project data.

    :param project_id: project ID
    :return: project data
    """

    return db_projects.get_project(project_id=project_id)


@router.post(
    "/",
    response_model=Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
@error_handler
def create_project(data: Project) -> Project:
    """
    Create a project.

    :param data: project data
    :return: created project data
    """

    project_id = db_projects.create_project(data=data)
    return db_projects.get_project(project_id=project_id)


@router.put(
    "/{project_id}/",
    response_model=Project,
    status_code=status.HTTP_200_OK,
    summary="Update an existing project",
)
@error_handler
def update_project(project_id: str, data: Project) -> Project:
    """
    Update an existing project.

    :param project_id: project ID
    :param data: project data for update
    :return: updated project data
    """

    data.id = project_id
    db_projects.update_project(data=data)
    return db_projects.get_project(project_id=project_id)


@router.delete(
    "/{project_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete a project",
)
@error_handler
def delete_project(project_id: str, delete_sessions: bool = False) -> ma.DeletedCount:
    """
    Delete a project and all its data.

    :param project_id: project ID
    :param delete_sessions: delete also session (and turn) data for the project
    :return: deleted count
    """

    deleted = ragnarok.delete_project(project_id=project_id)
    deleted.deleted_db_knowledge_base = db_kb.delete_kb_for_project(project_id=project_id)
    deleted.deleted_db_projects = db_projects.delete_project(project_id=project_id)
    deleted.deleted_storage_blobs = storage.delete_folder(folder_path=DIR_PROJECT.format(project_id=project_id))

    if delete_sessions:
        deleted.deleted_db_sessions = db_sessions.delete_sessions_for_project(project_id=project_id)
        deleted.deleted_db_turns = db_turns.delete_turns_for_project(project_id=project_id)

    return deleted
