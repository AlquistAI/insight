# -*- coding: utf-8 -*-
"""
    maestro.services.ragnarok
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Ragnarok service utilities.
"""

from typing import Any

import httpx

from common.config import CONFIG
from common.models.api_maestro import QueryPayload

RAGNAROK_URL = str(CONFIG.RAGNAROK_URL).rstrip("/")

HEADERS = {
    "accept": "application/json",
    "Authorization": CONFIG.RAGNAROK_API_KEY.get_secret_value(),
}


async def get_highlights(project_id: str, payload: QueryPayload, hit: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch highlight group (L0 + L1) for a single matched hit.

    :param project_id: project ID
    :param payload: original RAG payload
    :param hit: matched KB entry
    :return: highlight group data
    """

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=f"{RAGNAROK_URL}/projects/{project_id}/nlp/rag/highlights",
            json={"payload": payload.model_dump(), "hit": hit},
            headers=HEADERS,
            timeout=httpx.Timeout(10, connect=5),
        )

    res.raise_for_status()
    return res.json()
