# -*- coding: utf-8 -*-
"""
    kronos.services.db.mongo.knowledge_base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the "knowledge_base" collection.
"""

from typing import Any

from cachetools.func import ttl_cache
from pymongo.errors import DuplicateKeyError

from common.models.enums import Coll, SourceType
from common.models.knowledge_base import KnowledgeBase
from common.services.mongo import prepare_projection, process_filter
from common.utils import exceptions as exc
from kronos.services.db.mongo.connection import get_coll

COLL_KB = get_coll(Coll.KB)


def get_kb(kb_id: str, fields: set[str] | None = None) -> KnowledgeBase | dict[str, Any]:
    """
    Find a knowledge base entry in the DB.

    :param kb_id: knowledge base ID
    :param fields: set of fields to include using projection (returns data as dict)
    :return: knowledge base data
    """

    projection = prepare_projection(fields)
    if (res := COLL_KB.find_one({"_id": kb_id}, projection)) is None:
        raise exc.DBRecordNotFound(_id=kb_id) from None
    return res if projection else KnowledgeBase.model_validate(res)


@ttl_cache(ttl=300)
def get_kb_cached(kb_id: str) -> KnowledgeBase:
    """
    Find a knowledge base entry in the DB (cached with a TTL cache).

    :param kb_id: knowledge base ID
    :return: knowledge base data
    """

    return get_kb(kb_id=kb_id)


def get_kb_bulk(kb_ids: list[str], fields: set[str] | None = None) -> list[KnowledgeBase | dict[str, Any]]:
    """
    Find knowledge base entries in the DB in bulk.

    :param kb_ids: list of knowledge base IDs
    :param fields: set of fields to include using projection (returns data as dict)
    :return: list of knowledge base data
    """

    kb_ids_unique = set(kb_ids)
    projection = prepare_projection(fields)
    res = COLL_KB.find({"_id": {"$in": list(kb_ids_unique)}}, projection).to_list()

    if len(kb_ids_unique) != len(res):
        found = {x["_id"] for x in res}
        missing = kb_ids_unique - found
        raise exc.DBRecordNotFound(_id=missing) from None

    # Mongo returns the docs in pseudo-random order.
    res_by_id = {x["_id"]: x for x in res}
    res = [res_by_id[_id] for _id in kb_ids]

    return res if projection else [KnowledgeBase.model_validate(x) for x in res]


def create_kb(data: KnowledgeBase) -> str:
    """
    Create a new knowledge base record in the DB.

    :param data: knowledge base data
    :return: created knowledge base ID
    """

    try:
        res = COLL_KB.insert_one(data.model_dump())
        return res.inserted_id
    except DuplicateKeyError:
        raise exc.DBRecordAlreadyExists(_id=data.id) from None


def update_kb(data: KnowledgeBase):
    """
    Update an already existing knowledge base entry in the DB.

    :param data: knowledge base data
    """

    res = COLL_KB.update_one({"_id": data.id}, {"$set": data.model_dump(exclude_unset=True)})
    if not res.acknowledged or res.matched_count != 1:
        raise exc.DBRecordNotFound(_id=data.id) from None


def delete_kb(kb_id: str, raise_not_found: bool = False) -> int:
    """
    Delete knowledge base entry from the DB.

    :param kb_id: knowledge base ID
    :param raise_not_found: raise exception if not found
    :return: deleted count
    """

    res = COLL_KB.delete_one({"_id": kb_id})
    if raise_not_found and res.deleted_count != 1:
        raise exc.DBRecordNotFound(_id=kb_id) from None
    return res.deleted_count


def delete_kb_for_project(project_id: str) -> int:
    """
    Delete all knowledge base entries for a project.

    :param project_id: project ID
    :return: deleted count
    """

    res = COLL_KB.delete_many({"project_id": project_id})
    return res.deleted_count


def list_kb(
        project_id: str | None = None,
        embedding_model: str | None = None,
        language: str | None = None,
        source_type: SourceType | None = None,
        fields: set[str] | None = None,
        sort_by: str | None = None,
        page_no: int = 1,
        per_page: int = 10,
) -> tuple[list[KnowledgeBase], int]:
    """
    List knowledge base for project with optional filters.

    :param project_id: project ID
    :param embedding_model: embedding model name
    :param language: content language
    :param source_type: source type
    :param fields: set of fields to include using projection (returns data as dict)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of knowledge base data, total count
    """

    ftr = {
        "project_id": project_id,
        "embedding_model": embedding_model,
        "language": language,
        "source_type": source_type,
    }

    ftr = process_filter(ftr)
    projection = prepare_projection(fields)
    total = COLL_KB.count_documents(ftr)
    res = COLL_KB.find(ftr, projection)

    if sort_by:
        sort_order = -1 if sort_by.startswith("-") else 1
        res.sort([(sort_by.lstrip("-"), sort_order), "_id"])

    if per_page > 0:
        res = res.skip(per_page * (page_no - 1)).limit(per_page)

    res = list(res) if projection else [KnowledgeBase.model_validate(x) for x in res]
    return res, total
