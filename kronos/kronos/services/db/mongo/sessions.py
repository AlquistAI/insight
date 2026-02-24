# -*- coding: utf-8 -*-
"""
    kronos.services.db.mongo.sessions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the "sessions" collection.
"""

from pymongo.errors import DuplicateKeyError

from common.models.enums import Coll
from common.models.session import Session
from common.services.mongo import prepare_projection, process_filter
from common.utils import exceptions as exc
from kronos.services.db.mongo.connection import get_coll

COLL_SESSIONS = get_coll(Coll.SESSIONS)


def get_session(session_id: str) -> Session:
    """
    Find a session in the DB.

    :param session_id: session ID
    :return: session data
    """

    if (res := COLL_SESSIONS.find_one({"_id": session_id})) is None:
        raise exc.DBRecordNotFound(_id=session_id) from None
    return Session.model_validate(res)


def create_session(data: Session) -> str:
    """
    Create a new session record in the DB.

    :param data: session data
    :return: created session ID
    """

    try:
        res = COLL_SESSIONS.insert_one(data.model_dump())
        return res.inserted_id
    except DuplicateKeyError:
        raise exc.DBRecordAlreadyExists(_id=data.id) from None


def update_session(data: Session):
    """
    Update an already existing session in the DB.

    :param data: session data
    """

    res = COLL_SESSIONS.update_one({"_id": data.id}, {"$set": data.model_dump(exclude_unset=True)})
    if not res.acknowledged or res.matched_count != 1:
        raise exc.DBRecordNotFound(_id=data.id) from None


def delete_session(session_id: str, raise_not_found: bool = False) -> int:
    """
    Delete session from the DB.

    :param session_id: session ID
    :param raise_not_found: raise exception if not found
    :return: deleted count
    """

    res = COLL_SESSIONS.delete_one({"_id": session_id})
    if raise_not_found and res.deleted_count != 1:
        raise exc.DBRecordNotFound(_id=session_id) from None
    return res.deleted_count


def delete_sessions_for_project(project_id: str) -> int:
    """
    Delete all session entries for a project.

    :param project_id: project ID
    :return: deleted count
    """

    res = COLL_SESSIONS.delete_many({"project_id": project_id})
    return res.deleted_count


def list_sessions(
        document_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        language: str | None = None,
        fields: set[str] | None = None,
        sort_by: str | None = None,
        page_no: int = 1,
        per_page: int = 10,
) -> tuple[list[Session], int]:
    """
    List all sessions with optional filters.

    :param document_id: document ID
    :param project_id: project ID
    :param user_id: user ID
    :param language: language code
    :param fields: set of fields to include using projection (returns data as dict)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of sessions data, total count
    """

    ftr = {
        "document_id": document_id,
        "project_id": project_id,
        "user_id": user_id,
        "language": language,
    }

    ftr = process_filter(ftr)
    projection = prepare_projection(fields)
    total = COLL_SESSIONS.count_documents(ftr)
    res = COLL_SESSIONS.find(ftr, projection)

    if sort_by:
        sort_order = -1 if sort_by.startswith("-") else 1
        res.sort([(sort_by.lstrip("-"), sort_order), "_id"])

    if per_page > 0:
        res = res.skip(per_page * (page_no - 1)).limit(per_page)

    res = list(res) if projection else [Session.model_validate(x) for x in res]
    return res, total
