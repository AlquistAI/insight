# -*- coding: utf-8 -*-
"""
    kronos.services.db.mongo.projects
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the "projects" collection.
"""

import re

from cachetools.func import ttl_cache
from pymongo.errors import DuplicateKeyError

from common.models.enums import Coll
from common.models.project import Project
from common.services.mongo import prepare_projection, process_filter
from common.utils import exceptions as exc
from kronos.services.db.mongo.connection import get_coll

COLL_PROJECTS = get_coll(Coll.PROJECTS)


def get_project(project_id: str) -> Project:
    """
    Find a project in the DB.

    :param project_id: project ID
    :return: project data
    """

    if (res := COLL_PROJECTS.find_one({"_id": project_id})) is None:
        raise exc.DBRecordNotFound(_id=project_id) from None
    return Project.model_validate(res)


@ttl_cache(ttl=300)
def get_project_cached(project_id: str) -> Project:
    """
    Find a project in the DB (cached with a TTL cache).

    :param project_id: project ID
    :return: project data
    """

    return get_project(project_id=project_id)


def create_project(data: Project) -> str:
    """
    Create a new project record in the DB.

    :param data: project data
    :return: created project ID
    """

    try:
        res = COLL_PROJECTS.insert_one(data.model_dump())
        return res.inserted_id
    except DuplicateKeyError:
        raise exc.DBRecordAlreadyExists(_id=data.id) from None


def update_project(data: Project):
    """
    Update an already existing project in the DB.

    :param data: project data
    """

    res = COLL_PROJECTS.update_one({"_id": data.id}, {"$set": data.model_dump(exclude_unset=True)})
    if not res.acknowledged or res.matched_count != 1:
        raise exc.DBRecordNotFound(_id=data.id) from None


def delete_project(project_id: str, raise_not_found: bool = False) -> int:
    """
    Delete project from the DB.

    :param project_id: project ID
    :param raise_not_found: raise exception if not found
    :return: deleted count
    """

    res = COLL_PROJECTS.delete_one({"_id": project_id})
    if raise_not_found and res.deleted_count != 1:
        raise exc.DBRecordNotFound(_id=project_id) from None
    return res.deleted_count


def list_projects(
        name: str | None = None,
        language: str | None = None,
        exact_match: bool = True,
        fields: set[str] | None = None,
        sort_by: str | None = None,
        page_no: int = 1,
        per_page: int = 10,
) -> tuple[list[Project], int]:
    """
    List all projects.

    The `exact_match` option currently only applies to the `name` field.

    :param name: project name
    :param language: project language
    :param exact_match: match the field values exactly (otherwise search for substrings)
    :param fields: set of fields to include using projection (returns data as dict)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of projects data, total count
    """

    ftr = {"name": name, "language": language}
    ftr = process_filter(ftr)

    if not exact_match:
        match_fields = ("name",)

        # Perform a "LIKE" match
        ftr.update({
            fld: re.compile(f".*{re.escape(val)}.*", re.IGNORECASE)
            for fld in match_fields if (val := ftr.get(fld))
        })

    projection = prepare_projection(fields)
    total = COLL_PROJECTS.count_documents(ftr)
    res = COLL_PROJECTS.find(ftr, projection)

    if sort_by:
        sort_order = -1 if sort_by.startswith("-") else 1
        res.sort([(sort_by.lstrip("-"), sort_order), "_id"])

    if per_page > 0:
        res = res.skip(per_page * (page_no - 1)).limit(per_page)

    res = list(res) if projection else [Project.model_validate(x) for x in res]
    return res, total


def check_project_exists(project_id: str):
    """Raise error when project does not exist in the DB."""
    if not COLL_PROJECTS.count_documents({"_id": project_id}, limit=1):
        raise exc.DBRecordNotFound(_id=project_id) from None
