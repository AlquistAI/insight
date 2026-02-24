# -*- coding: utf-8 -*-
"""
    kronos.services.db.mongo.turns
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the "turns" collection.
"""

from pymongo.errors import DuplicateKeyError

from common.models.enums import Coll
from common.models.turn import Turn
from common.services.mongo import prepare_projection, process_filter
from common.utils import exceptions as exc
from kronos.services.db.mongo.connection import get_coll

COLL_TURNS = get_coll(Coll.TURNS)


def get_turn(turn_id: str) -> Turn:
    """
    Find a turn in the DB.

    :param turn_id: turn ID
    :return: turn data
    """

    if (res := COLL_TURNS.find_one({"_id": turn_id})) is None:
        raise exc.DBRecordNotFound(_id=turn_id) from None
    return Turn.model_validate(res)


def create_turn(data: Turn) -> str:
    """
    Create a new turn record in the DB.

    :param data: turn data
    :return: created turn ID
    """

    try:
        res = COLL_TURNS.insert_one(data.model_dump())
        return res.inserted_id
    except DuplicateKeyError:
        raise exc.DBRecordAlreadyExists(_id=data.id) from None


def delete_turn(turn_id: str, raise_not_found: bool = False) -> int:
    """
    Delete turn from the DB.

    :param turn_id: turn ID
    :param raise_not_found: raise exception if not found
    :return: deleted count
    """

    res = COLL_TURNS.delete_one({"_id": turn_id})
    if raise_not_found and res.deleted_count != 1:
        raise exc.DBRecordNotFound(_id=turn_id) from None
    return res.deleted_count


def delete_turns_for_project(project_id: str) -> int:
    """
    Delete all turn entries for a project.

    :param project_id: project ID
    :return: deleted count
    """

    res = COLL_TURNS.delete_many({"project_id": project_id})
    return res.deleted_count


def delete_turns_for_session(session_id: str) -> int:
    """
    Delete all turn entries for a session.

    :param session_id: session ID
    :return: deleted count
    """

    res = COLL_TURNS.delete_many({"session_id": session_id})
    return res.deleted_count


def list_turns(
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        fields: set[str] | None = None,
        sort_by: str | None = None,
        page_no: int = 1,
        per_page: int = 10,
) -> tuple[list[Turn], int]:
    """
    List all turns with optional filters.

    :param session_id: session ID
    :param project_id: project ID
    :param user_id: user ID
    :param fields: set of fields to include using projection (returns data as dict)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of turns data, total count
    """

    ftr = {
        "session_id": session_id,
        "project_id": project_id,
        "user_id": user_id,
    }

    ftr = process_filter(ftr)
    projection = prepare_projection(fields)
    total = COLL_TURNS.count_documents(ftr)
    res = COLL_TURNS.find(ftr, projection)

    if sort_by:
        sort_order = -1 if sort_by.startswith("-") else 1
        res.sort([(sort_by.lstrip("-"), sort_order), "_id"])

    if per_page > 0:
        res = res.skip(per_page * (page_no - 1)).limit(per_page)

    res = list(res) if projection else [Turn.model_validate(x) for x in res]
    return res, total
