# -*- coding: utf-8 -*-
"""
    kronos.prestart
    ~~~~~~~~~~~~~~~

    Operations required to run before server start (e.g. migrations, default resource files).
"""

from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any

import pymongo
from dateutil import tz
from pymongo import ReplaceOne, UpdateOne
from pymongo.errors import DuplicateKeyError

from common.config import CONFIG, DIR_ROOT
from common.core import get_component_logger
from common.models.enums import Coll, ResourceType
from common.models.knowledge_base import KnowledgeBase, VER_KB
from common.models.project import Project, VER_PROJECTS
from common.models.session import Session, VER_SESSIONS
from common.models.turn import Turn, VER_TURNS
from common.utils import exceptions as exc, fsm as u_fsm
from common.utils.prompts import parse_prompts
from kronos.services.db.mongo.connection import get_db
from kronos.services.storage import get_storage
from kronos.services.storage.base import FN_PROMPTS, get_resource_paths

logger = get_component_logger()
db = get_db()
storage = get_storage()

LOCKS = db[Coll.LOCKS]
LOCK_NAME = "db_migration"

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

# Folder with the default resource files
# Copied next to the app in the Docker image, kept in the repository root during local development
DIR_RESOURCES_APP = Path(__file__).parent.parent / "resources"
DIR_RESOURCES = DIR_RESOURCES_APP if DIR_RESOURCES_APP.is_dir() else DIR_ROOT / "resources"

PATH_DEFAULT_IMAGE = DIR_RESOURCES / u_fsm.DEFAULT_QA_WELCOME_IMAGE
PATH_DEFAULT_PROMPTS = DIR_RESOURCES / FN_PROMPTS


###########
## MONGO ##
###########

def get_lock() -> bool:
    """Get migration lock."""

    logger.info("Getting migration lock...")
    has_lock = False

    while not has_lock:
        try:
            LOCKS.insert_one({"_id": LOCK_NAME, "created_at": datetime.now(tz=tz.UTC)})
            logger.info("Migration lock acquired")
            has_lock = True
        except DuplicateKeyError:
            logger.info("Waiting for migration lock...")
            sleep(5)

    return has_lock


def prepare_db():
    """Prepare collections and indexes."""

    logger.info("Initializing the MongoDB collections...")
    coll_names = db.list_collection_names()
    updated = False

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
                updated = True

    if not updated:
        logger.info("Collections already initialized --> skipping")


def migrate_mongo_data():
    """Migrate MongoDB data to the current version."""

    logger.info("Migrating data to the current version...")
    updated = False

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
            try:
                new.append(func(d))
            except Exception as e:
                logger.warning("Failed to migrate %s in coll %s: %s", d.get("_id"), c_name.value, e)

        if new:
            logger.info("Migrating %d document(s) in coll %s", len(new), c_name.value)
            operations = [ReplaceOne({"_id": d.id}, d.model_dump()) for d in new]
            updated = True

            try:
                coll.bulk_write(operations, ordered=False)
            except Exception as e:
                logger.error("Failed to replace migrated documents: %s", e)

    if not updated:
        logger.info("No migration needed --> skipping")


def _migrate_kb(old: dict[str, Any]) -> KnowledgeBase:
    """Migrate knowledge base data to the current version."""

    if old["model_version"] < 2:
        # Normalize language
        old["language"] = "cs-CZ" if old["language"] == "cs" else "en-US"

    old["model_version"] = VER_KB
    return KnowledgeBase.model_validate(old)


def _migrate_project(old: dict[str, Any]) -> Project:
    """Migrate project data to the current version."""

    if old["model_version"] < 4:
        # Set modified_at field to created_at
        old["modified_at"] = old["created_at"]

    if old["model_version"] < 5:
        # Update the default RAG settings for 'gpt-4o' models
        if old["ai_settings"]["generation"]["model"]["name"] == "gpt-4o":
            old["ai_settings"]["generation"]["model"]["name"] = "gpt-5.6-luna"
            old["ai_settings"]["retrieval"]["k_bm25"] = 10
            old["ai_settings"]["retrieval"]["k_emb"] = 10

    if old["model_version"] < 6:
        # Query rewrite settings split from the generation ones -> keep using the generation model for the rewrite
        # (the call parameters are filled with the defaults by the validation below)
        old["ai_settings"]["query_rewrite"] = {"model": old["ai_settings"]["generation"]["model"]}

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


def migrate_first_user_query():
    """Migrate old sessions to include first user query."""

    logger.info("Migrating first user query...")
    coll_sessions = db[Coll.SESSIONS]
    coll_turns = db[Coll.TURNS]

    sessions = coll_sessions.find(
        {
            "model_version": {"$lt": 3},
            "$or": [
                {"first_user_query": {"$exists": False}},
                {"first_user_query": ""},
            ],
        },
        {"_id": 1},
    )

    if not (session_ids := [x["_id"] for x in sessions]):
        logger.info("No sessions to migrate --> skipping")
        return

    turns = coll_turns.find(
        {"session_id": {"$in": session_ids}},
        {"session_id": 1, "user_query": 1, "created_at": 1},
    )

    first_turns = {}
    for turn in turns:
        sid = turn["session_id"]
        if sid not in first_turns or turn["created_at"] < first_turns[sid]["created_at"]:
            first_turns[sid] = turn

    operations = [
        UpdateOne({"_id": sid}, {"$set": {"first_user_query": query}})
        for sid, turn in first_turns.items() if (query := turn.get("user_query"))
    ]

    if not operations:
        logger.info("Remaining sessions have no turns --> skipping")
        return

    logger.info("Adding first user query to %d session(s)", len(operations))

    try:
        coll_sessions.bulk_write(operations, ordered=False)
    except Exception as e:
        logger.error("Failed to update sessions: %s", e)


#######################
## DEFAULT RESOURCES ##
#######################

def create_default_resources():
    """
    Create the default (project independent) resource files in the storage.

    The default dialogue FSM and prompts files are replaced with the current version on every start if
    `CONFIG.OVERWRITE_DEFAULT_RESOURCES` is set, otherwise they are only created when missing. The default
    image is always uploaded only once, so that it can be replaced by the user.
    """

    logger.info("Creating the default resource files...")

    # Step 1: Dialogue FSM - the default Q&A dialogue built for the default language
    path = get_resource_paths(resource_type=ResourceType.DIALOGUE_FSM)[0]

    if CONFIG.OVERWRITE_DEFAULT_RESOURCES or not _resource_exists(file_path=path):
        dialogue = u_fsm.build_qa().model_dump_json(indent=2).encode("utf-8")
        storage.post_file(file_path=path, content=dialogue)
        logger.info("Default dialogue FSM file uploaded: %s", path)
    else:
        logger.info("Default dialogue FSM file already exists --> skipping")

    # Step 2: Image - the static image shown in the welcome state of the default dialogue
    path = get_resource_paths(
        resource_type=ResourceType.IMAGE,
        resource_id=u_fsm.DEFAULT_QA_WELCOME_IMAGE,
    )[0]

    if not _resource_exists(file_path=path):
        storage.post_file(file_path=path, content=PATH_DEFAULT_IMAGE.read_bytes())
        logger.info("Default image file uploaded: %s", path)
    else:
        logger.info("Default image file already exists --> skipping")

    # Step 3: Prompts - the LLM prompts used for projects without their own prompts file
    path = get_resource_paths(resource_type=ResourceType.PROMPTS)[0]

    if CONFIG.OVERWRITE_DEFAULT_RESOURCES or not _resource_exists(file_path=path):
        prompts = PATH_DEFAULT_PROMPTS.read_bytes()
        parse_prompts(content=prompts)  # ensure the default prompts file is valid before it is stored
        storage.post_file(file_path=path, content=prompts)
        logger.info("Default prompts file uploaded: %s", path)
    else:
        logger.info("Default prompts file already exists --> skipping")


def _resource_exists(file_path: str) -> bool:
    """Check whether a resource file is already present in the storage."""

    try:
        return bool(storage.get_file(file_path=file_path))
    except exc.ResourceNotFound:
        return False


if __name__ == "__main__":
    if get_lock():
        try:
            prepare_db()
            migrate_first_user_query()
            migrate_mongo_data()
            create_default_resources()
        finally:
            LOCKS.delete_one({"_id": LOCK_NAME})
