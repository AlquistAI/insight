# -*- coding: utf-8 -*-
"""
    kronos.services.db.mongo.connection
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    MongoDB connection class.
"""

from common.config import CONFIG
from common.models.enums import Coll
from common.services import mongo


def get_db():
    return mongo.get_client()[CONFIG.MONGO_DB_NAME_KRONOS]


def get_coll(coll: Coll):
    return get_db()[coll.value]
