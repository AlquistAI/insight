# -*- coding: utf-8 -*-
"""
    kronos.api.turns
    ~~~~~~~~~~~~~~~~

    Turn management endpoints.
"""

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from common.models import api as ma
from common.models.turn import Turn
from common.utils.api import error_handler
from kronos.services.db.mongo import turns as db_turns

router = APIRouter()


@router.get(
    "/",
    response_model=ma.PaginatedTurns,
    status_code=status.HTTP_200_OK,
    summary="List general info for turns",
)
@error_handler
def list_turns(
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        fields: str = "",
        sort_by: str = "",
        page_no: int = 1,
        per_page: int = 10,
) -> ma.PaginatedTurns | JSONResponse:
    """
    List general info for turns.

    :param session_id: session ID
    :param project_id: project ID
    :param user_id: user ID
    :param fields: field names in DB to include using projection (as CSV)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of turns data
    """

    fields = {x.strip() for x in fields.split(",")} if fields else None

    data, total = db_turns.list_turns(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        fields=fields,
        sort_by=sort_by,
        page_no=page_no,
        per_page=per_page,
    )

    pagination = ma.Pagination(page_no=page_no, per_page=per_page, total=total) if per_page > 0 else None

    if fields:
        return JSONResponse(ma.PaginationBaseModel(data=data, pagination=pagination).model_dump(mode="json"))
    return ma.PaginatedTurns(data=data, pagination=pagination)


@router.get(
    "/{turn_id}/",
    response_model=Turn,
    status_code=status.HTTP_200_OK,
    summary="Get turn data",
)
@error_handler
def get_turn(turn_id: str) -> Turn:
    """
    Get turn data.

    :param turn_id: turn ID
    :return: turn data
    """

    return db_turns.get_turn(turn_id=turn_id)


@router.post(
    "/",
    response_model=Turn,
    status_code=status.HTTP_201_CREATED,
    summary="Create a turn",
)
@error_handler
def create_turn(data: Turn) -> Turn:
    """
    Create a turn.

    :param data: turn data
    :return: created turn data
    """

    turn_id = db_turns.create_turn(data=data)
    return db_turns.get_turn(turn_id=turn_id)


@router.delete(
    "/{turn_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete turn",
)
@error_handler
def delete_turn(turn_id: str) -> ma.DeletedCount:
    """
    Delete turn.

    :param turn_id: turn ID
    :return: deleted count
    """

    return ma.DeletedCount(deleted_db_turns=db_turns.delete_turn(turn_id=turn_id))
