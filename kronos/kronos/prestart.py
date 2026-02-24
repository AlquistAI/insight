# -*- coding: utf-8 -*-
"""
    kronos.prestart
    ~~~~~~~~~~~~~~~

    Operations required to run before server start (e.g. migrations).
"""

import copy
from typing import Any

import pymongo

from common.core import get_component_logger
from common.models.enums import Coll
from common.models.knowledge_base import KnowledgeBase, VER_KB
from common.models.project import Project, VER_PROJECTS
from common.models.session import Session, VER_SESSIONS
from common.models.turn import Turn, VER_TURNS
from kronos.services.db.mongo.connection import get_db

logger = get_component_logger()
db = get_db()

INDEXES = {
    Coll.KB: [
        (("project_id", pymongo.ASCENDING), {"background": True}),
    ],
    Coll.SESSIONS: [
        (("document_id", pymongo.ASCENDING), {"background": True}),
        (("project_id", pymongo.ASCENDING), {"background": True}),
        (("user_id", pymongo.ASCENDING), {"background": True}),
    ],
    Coll.TURNS: [
        (("project_id", pymongo.ASCENDING), {"background": True}),
        (("session_id", pymongo.ASCENDING), {"background": True}),
        (("user_id", pymongo.ASCENDING), {"background": True}),
    ],
}

MODEL_VERSIONS = {
    Coll.KB: VER_KB,
    Coll.PROJECTS: VER_PROJECTS,
    Coll.SESSIONS: VER_SESSIONS,
    Coll.TURNS: VER_TURNS,
}


def prepare_db():
    """Prepare collections and indexes."""

    logger.info("Preparing the MongoDB collections...")
    coll_names = db.list_collection_names()

    for coll_name, indexes in INDEXES.items():
        coll = db[coll_name]

        if coll_name in coll_names:
            index_names = {x["key"][0][0] for x in coll.index_information().values()}
        else:
            index_names = set()

        for index, kwargs in indexes:
            if index[0] not in index_names:
                logger.info("Creating index %s for coll %s", index, coll_name.value)
                coll.create_index([index], **kwargs)


def migrate_mongo_data():
    """Migrate MongoDB data to the current version."""

    logger.info("Migrating data to the current version...")

    for c_name, ver in MODEL_VERSIONS.items():
        if c_name == Coll.KB:
            func = _migrate_kb
        elif c_name == Coll.PROJECTS:
            func = _migrate_project
        elif c_name == Coll.SESSIONS:
            func = _migrate_session
        elif c_name == Coll.TURNS:
            func = _migrate_turn
        else:
            continue

        coll = db[c_name]
        old = list(coll.find({"model_version": {"$lt": ver}}))
        new = []

        for d in old:
            # preserve the original copy in case rollback is needed
            d = copy.deepcopy(d)

            try:
                new.append(func(d))
            except Exception as e:
                logger.warning("Failed to migrate %s in coll %s: %s", d.get("_id"), c_name.value, e)

        if new:
            logger.info("Migrating %d document(s) in coll %s", len(new), c_name.value)
            ids = [x.id for x in new]
            new = [x.model_dump() for x in new]

            try:
                # ToDo: Do bulk update instead of deleting and re-inserting the documents.
                coll.delete_many({"_id": {"$in": ids}})
                coll.insert_many(new, ordered=False)
            except Exception as e:
                logger.error("Failed to insert migrated documents: %s", e)
                coll.insert_many(old, ordered=False)


def _migrate_kb(old: dict[str, Any]) -> KnowledgeBase:
    """Migrate knowledge base data to the current version."""

    # version 2 changes
    if old["model_version"] < 2:
        # normalize language
        old["language"] = "cs-CZ" if old["language"] == "cs" else "en-US"

    old["model_version"] = VER_KB
    return KnowledgeBase.model_validate(old)


def _migrate_project(old: dict[str, Any]) -> Project:
    """Migrate project data to the current version."""

    old["model_version"] = VER_PROJECTS
    return Project.model_validate(old)


def _migrate_session(old: dict[str, Any]) -> Session:
    """Migrate session data to the current version."""

    old["model_version"] = VER_SESSIONS
    return Session.model_validate(old)


def _migrate_turn(old: dict[str, Any]) -> Turn:
    """Migrate turn data to the current version."""

    old["model_version"] = VER_TURNS
    return Turn.model_validate(old)


if __name__ == "__main__":
    prepare_db()
    migrate_mongo_data()
