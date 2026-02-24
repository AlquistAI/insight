# -*- coding: utf-8 -*-
"""
    kronos.api.sessions
    ~~~~~~~~~~~~~~~~~~~

    Session management endpoints.
"""

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from common.models import api as ma
from common.models.session import Session
from common.utils.api import error_handler
from kronos.services.db.mongo import sessions as db_sessions, turns as db_turns

router = APIRouter()


@router.get(
    "/",
    response_model=ma.PaginatedSessions,
    status_code=status.HTTP_200_OK,
    summary="List general info for sessions",
)
@error_handler
def list_sessions(
        document_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        language: str | None = None,
        fields: str = "",
        sort_by: str = "",
        page_no: int = 1,
        per_page: int = 10,
) -> ma.PaginatedSessions | JSONResponse:
    """
    List general info for sessions.

    :param document_id: document ID
    :param project_id: project ID
    :param user_id: user ID
    :param language: language code
    :param fields: field names in DB to include using projection (as CSV)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of sessions data
    """

    fields = {x.strip() for x in fields.split(",")} if fields else None

    data, total = db_sessions.list_sessions(
        document_id=document_id,
        project_id=project_id,
        user_id=user_id,
        language=language,
        fields=fields,
        sort_by=sort_by,
        page_no=page_no,
        per_page=per_page,
    )

    pagination = ma.Pagination(page_no=page_no, per_page=per_page, total=total) if per_page > 0 else None

    if fields:
        return JSONResponse(ma.PaginationBaseModel(data=data, pagination=pagination).model_dump(mode="json"))
    return ma.PaginatedSessions(data=data, pagination=pagination)


@router.get(
    "/{session_id}/",
    response_model=Session,
    status_code=status.HTTP_200_OK,
    summary="Get session data",
)
@error_handler
def get_session(session_id: str) -> Session:
    """
    Get session data.

    :param session_id: session ID
    :return: session data
    """

    return db_sessions.get_session(session_id=session_id)


@router.post(
    "/",
    response_model=Session,
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
)
@error_handler
def create_session(data: Session) -> Session:
    """
    Create a session.

    :param data: session data
    :return: created session data
    """

    session_id = db_sessions.create_session(data=data)
    return db_sessions.get_session(session_id=session_id)


@router.put(
    "/{session_id}/",
    response_model=Session,
    status_code=status.HTTP_200_OK,
    summary="Update an existing session",
)
@error_handler
def update_session(session_id: str, data: Session) -> Session:
    """
    Update an existing session.

    :param session_id: session ID
    :param data: session data for update
    :return: updated session data
    """

    data.id = session_id
    db_sessions.update_session(data=data)
    return db_sessions.get_session(session_id=session_id)


@router.delete(
    "/{session_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete session",
)
@error_handler
def delete_session(session_id: str) -> ma.DeletedCount:
    """
    Delete session and its turns.

    :param session_id: session ID
    :return: deleted count
    """

    return ma.DeletedCount(
        deleted_db_sessions=db_sessions.delete_session(session_id=session_id),
        deleted_db_turns=db_turns.delete_turns_for_session(session_id=session_id),
    )
