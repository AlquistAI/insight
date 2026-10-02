# -*- coding: utf-8 -*-
"""
    common.services.kronos
    ~~~~~~~~~~~~~~~~~~~~~~

    Kronos service utilities.
"""

import json
from typing import Any, AsyncGenerator

import httpx
import requests
from cachetools.func import ttl_cache
from fastapi import status
from fastapi.exceptions import HTTPException

from common.config import CONFIG
from common.core import get_component_logger
from common.models.enums import ResourceType, SourceType
from common.models.project import Project
from common.models.prompts import Prompts
from common.utils.prompts import parse_prompts

logger = get_component_logger()

KRONOS_URL = str(CONFIG.KRONOS_URL).rstrip("/")

HEADERS = {
    "accept": "application/json",
    "X-Api-Key": CONFIG.KRONOS_API_KEY.get_secret_value(),
}

# Used for the endpoints returning raw file content (resources)
HEADERS_FILE = HEADERS | {"accept": "*/*"}

PROMPTS_CACHE_SIZE = 1024
PROMPTS_CACHE_TTL = 3600


# ---------------------------------------------------------------------------
# Projects & knowledge base
# ---------------------------------------------------------------------------


async def get_project(project_id: str) -> Project:
    """
    Get project information.

    :param project_id: project ID
    :return: project information
    """

    async with httpx.AsyncClient() as client:
        res = await client.get(
            url=f"{KRONOS_URL}/projects/{project_id}/",
            headers=HEADERS,
            timeout=httpx.Timeout(10, connect=5),
        )

    res.raise_for_status()
    return Project.model_validate(res.json())


async def get_kb(project_id: str) -> list[dict[str, Any]]:
    """
    Get knowledge base entries for a project.

    :param project_id: project ID
    :return: list of knowledge base
    """

    async with httpx.AsyncClient() as client:
        res = await client.get(
            url=f"{KRONOS_URL}/knowledge_base/",
            params={
                "project_id": project_id,
                "fields": "name,source_file,source_type,enable_highlights",
                "sort_by": "source_file",
                "per_page": 0,
            },
            headers=HEADERS,
            timeout=httpx.Timeout(10, connect=5),
        )

    res.raise_for_status()
    res = res.json()

    if not (data := res.get("data")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No knowledge base found for project {project_id}")
    return data


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


async def get_resource(
        resource_type: ResourceType,
        resource_id: str = "",
        project_id: str = "",
        source_type: SourceType | None = None,
        as_json: bool = False,
) -> tuple[bytes | dict[str, Any], str]:
    """
    Get resource file based on resource type.

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: file source type (use None for original file)
    :param as_json: [dialogue_fsm] return as json object
    :return: content of the resource file, content type
    """

    params = {
        "resource_id": resource_id,
        "project_id": project_id,
        "source_type": source_type.value if source_type else None,
    }

    # It is impossible to send None as a query param, we need to use default values
    params = {k: v for k, v in params.items() if v}

    async with httpx.AsyncClient() as client:
        res = await client.get(
            url=f"{KRONOS_URL}/resources/{resource_type.value}/",
            params=params,
            headers=HEADERS_FILE,
            timeout=httpx.Timeout(30, connect=5),
        )

    res.raise_for_status()
    content_type = res.headers.get("Content-Type", "")

    if as_json and resource_type == ResourceType.DIALOGUE_FSM:
        return res.json(), content_type
    return res.content, content_type


@ttl_cache(maxsize=PROMPTS_CACHE_SIZE, ttl=PROMPTS_CACHE_TTL)
def get_prompts(project_id: str, session_id: str = "") -> Prompts:  # noqa
    """
    Get the LLM prompts of a project from Kronos (cached by project & session ID for an hour).

    Kronos returns the project-specific "prompts.md" resource file if the project has one,
    the default (project independent) prompts file otherwise.

    :param project_id: project ID
    :param session_id: session ID (used only as a part of the cache key)
    :return: parsed project prompts
    """

    res = requests.get(
        url=f"{KRONOS_URL}/resources/{ResourceType.PROMPTS.value}/",
        params={"project_id": project_id},
        headers=HEADERS_FILE,
        timeout=(5, 10),
    )

    res.raise_for_status()
    return parse_prompts(content=res.content)


# ---------------------------------------------------------------------------
# NLP / RAG
# ---------------------------------------------------------------------------


def query_rag(
        project_id: str,
        query: str,
        kb_ids: list[str] | None = None,
        lang: str | None = None,
        return_highlights: bool = False,
        return_matched_chunks: bool = True,
        session_id: str | None = None,
        user_id: str | None = None,
) -> AsyncGenerator[str, Any]:
    """
    Get RAG response for a user query.

    :param project_id: project ID
    :param query: user query
    :param kb_ids: knowledge base IDs to include (null/empty for all project documents)
    :param lang: language to use (uses project language if None)
    :param return_highlights: return data for source snippet highlighting
    :param return_matched_chunks: return matched chunks/documents in the response
    :param session_id: session ID used for turn logging
    :param user_id: user ID used for turn logging
    :return: streamed RAG response generator
    """

    data = {
        "query": query,
        "kb_ids": kb_ids,
        "lang": lang,
        "return_highlights": return_highlights,
        "return_matched_chunks": return_matched_chunks,
    }

    headers = HEADERS.copy()
    del headers["accept"]

    async def response_generator() -> AsyncGenerator[str, Any]:
        last_chunk = {}

        async with httpx.AsyncClient() as client:
            async with client.stream(
                    method="POST",
                    url=f"{KRONOS_URL}/projects/{project_id}/nlp/rag/stream",
                    params={"session_id": session_id},
                    json=data,
                    headers=headers,
                    timeout=httpx.Timeout(60, connect=5),
            ) as res:
                res.raise_for_status()

                async for line in res.aiter_lines():
                    if not line:
                        continue

                    if (decoded_line := json.loads(line))["is_last_chunk"]:
                        last_chunk = decoded_line

                    yield f"{line}\n"

        matched_chunks = last_chunk.get("matched_chunks") or []
        text_full = last_chunk.get("text_full", "")
        top_match = matched_chunks[0] if matched_chunks else {}
        logger.debug("top_kb_id: %s, top_page: %s", top_match.get("kb_id"), top_match.get("page"))
        logger.info("answer", extra={"answer": text_full})

        await create_turn(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            user_query=query,
            system_response=text_full,
            matched_kb_ids=[x["_source"]["metadata"]["kb_id"] for x in matched_chunks],
            matched_pages=[x["_source"]["metadata"]["page"] for x in matched_chunks],
            usage=last_chunk.get("usage"),
        )

    return response_generator()


async def query_rag_top_n(
        project_id: str,
        query: str,
        lang: str | None = None,
        return_highlights: bool = False,
        return_matched_chunks: bool = True,
        session_id: str | None = None,
        user_id: str | None = None,
) -> dict[str, Any]:
    """
    Get top-N matched chunks for a user query.

    :param project_id: project ID
    :param query: user query
    :param lang: language to use (uses project language if None)
    :param return_highlights: return data for source snippet highlighting
    :param return_matched_chunks: return matched chunks/documents in the response
    :param session_id: session ID used for turn logging
    :param user_id: user ID used for turn logging
    :return: response with top-N chunks
    """

    data = {
        "query": query,
        "lang": lang,
        "return_highlights": return_highlights,
        "return_matched_chunks": return_matched_chunks,
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=f"{KRONOS_URL}/projects/{project_id}/nlp/rag/",
            json=data,
            headers=HEADERS,
            timeout=httpx.Timeout(60, connect=5),
        )

    res.raise_for_status()
    res = res.json()
    matched_chunks = res["matched_chunks"] if return_matched_chunks else []

    await create_turn(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        user_query=query,
        matched_kb_ids=[x["_source"]["metadata"]["kb_id"] for x in matched_chunks],
        matched_pages=[x["_source"]["metadata"]["page"] for x in matched_chunks],
        usage=res.get("usage"),
    )

    return res


# ---------------------------------------------------------------------------
# Sessions & turns
# ---------------------------------------------------------------------------


async def create_session(
        project_id: str | None = None,
        user_id: str | None = None,
        name: str = "",
        description: str = "",
        language: str | None = None,
) -> dict[str, Any]:
    """
    Create a session in Kronos.

    :param project_id: project ID
    :param user_id: user ID
    :param name: optional session name
    :param description: optional session description
    :param language: session language
    :return: created session data
    """

    data = {
        "project_id": project_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "language": language,
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=f"{KRONOS_URL}/sessions/",
            json=data,
            headers=HEADERS,
            timeout=httpx.Timeout(10, connect=5),
        )

    res.raise_for_status()
    return res.json()


async def create_turn(
        session_id: str | None,
        project_id: str | None = None,
        user_id: str | None = None,
        user_query: str = "",
        system_response: str = "",
        matched_kb_ids: list[str] | None = None,
        matched_pages: list[int] | None = None,
        usage: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Create a turn in Kronos.

    The turn is not created if the session_id is empty.

    :param session_id: session ID
    :param project_id: project ID
    :param user_id: user ID
    :param user_query: query of the user
    :param system_response: system response to the user's query
    :param matched_kb_ids: list of matched knowledge base IDs
    :param matched_pages: list of matched pages
    :param usage: token usage & costs of the model calls performed for the turn
    :return: created turn data or None if not created
    """

    if not session_id:
        return None

    data = {
        "session_id": session_id,
        "project_id": project_id,
        "user_id": user_id,
        "user_query": user_query,
        "system_response": system_response,
        "matched_kb_ids": matched_kb_ids or [],
        "matched_pages": matched_pages or [],
        "usage": usage,
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=f"{KRONOS_URL}/turns/",
            json=data,
            headers=HEADERS,
            timeout=httpx.Timeout(10, connect=5),
        )

    res.raise_for_status()
    return res.json()
