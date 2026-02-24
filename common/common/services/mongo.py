# -*- coding: utf-8 -*-
"""
    common.services.mongo
    ~~~~~~~~~~~~~~~~~~~~~

    MongoDB service utilities.
"""

from typing import Any

from cachetools.func import ttl_cache
from pymongo import MongoClient

from common.config import CONFIG


@ttl_cache(ttl=600)
def get_client(conn_str: str | None = None) -> MongoClient:
    return MongoClient(conn_str or CONFIG.MONGO_CONN_STR.get_secret_value())


def prepare_projection(fields: set[str] | None) -> dict[str, int] | None:
    """Prepare MongoDB projection for a set of included fields."""
    return {field: 1 for field in fields} if fields else None


def process_filter(ftr: dict[str, Any] | None) -> dict[str, Any] | None:
    """Process filter dict as MongoDB query filter."""

    if not ftr:
        return None

    return {
        k: {"$in": v} if isinstance(v, list) else v
        for k, v in ftr.items()
        if v is not None
    }
