# -*- coding: utf-8 -*-
"""
    maestro.services.kronos
    ~~~~~~~~~~~~~~~~~~~~~~~

    Kronos service utilities.
"""

import json
from typing import Any, AsyncGenerator

import httpx
from fastapi import status
from fastapi.exceptions import HTTPException

from common.config import CONFIG
from common.core import get_component_logger
from common.models.enums import ResourceType, SourceType
from common.models.project import Project

logger = get_component_logger()

KRONOS_URL = str(CONFIG.KRONOS_URL).rstrip("/")

HEADERS = {
    "accept": "application/json",
    "X-Api-Key": CONFIG.KRONOS_API_KEY.get_secret_value(),
}


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

    headers = HEADERS.copy()
    headers["accept"] = "*/*"

    async with httpx.AsyncClient() as client:
        res = await client.get(
            url=f"{KRONOS_URL}/resources/{resource_type.value}/",
            params=params,
            headers=HEADERS,
            timeout=httpx.Timeout(30, connect=5),
        )

    res.raise_for_status()
    content_type = res.headers.get("Content-Type", "")

    if as_json and resource_type == ResourceType.DIALOGUE_FSM:
        return res.json(), content_type
    return res.content, content_type


def query_rag(
        project_id: str,
        query: str,
        kb_ids: list[str] | None = None,
        k_emb: int = 5,
        k_bm25: int = 5,
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
    :param k_emb: number of matches to get using the cosine similarity
    :param k_bm25: number of matches using the text/BM25 search
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
        # FixMe: This can be re-enabled after it is implemented in Kronos.
        # "k_emb": k_emb,
        # "k_bm25": k_bm25,
        "lang": lang,
        "return_highlights": return_highlights,
        "return_matched_chunks": return_matched_chunks,
    }

    headers = HEADERS.copy()
    del headers["accept"]

    async def response_generator() -> AsyncGenerator[str, Any]:
        full_text = ""
        matched_chunks = []

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

                    decoded_line: dict = json.loads(line)
                    full_text += decoded_line.get("text", "")

                    if not matched_chunks and decoded_line.get("chunk_index") == -1:
                        matched_chunks, top_match = decoded_line["matched_chunks"], decoded_line["top_match"]
                        logger.debug("top_kb_id: %s, top_page: %s", top_match["kb_id"], top_match["page"])

                    yield f"{line}\n"

        logger.info("answer", extra={"answer": full_text})
        await create_turn(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            user_query=query,
            system_response=full_text,
            matched_kb_ids=[x["_source"]["metadata"]["kb_id"] for x in matched_chunks],
            matched_pages=[x["_source"]["metadata"]["page"] for x in matched_chunks],
        )

    return response_generator()


async def query_rag_top_n(
        project_id: str,
        query: str,
        k_emb: int = 20,
        k_bm25: int = 20,
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
    :param k_emb: number of matches to get using the cosine similarity
    :param k_bm25: number of matches using the text/BM25 search
    :param lang: language to use (uses project language if None)
    :param return_highlights: return data for source snippet highlighting
    :param return_matched_chunks: return matched chunks/documents in the response
    :param session_id: session ID used for turn logging
    :param user_id: user ID used for turn logging
    :return: response with top-N chunks
    """

    data = {
        "query": query,
        "model_name_llm": None,
        # FixMe: This can be re-enabled after it is implemented in Kronos.
        # "k_emb": k_emb,
        # "k_bm25": k_bm25,
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

    await create_turn(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        user_query=query,
        matched_kb_ids=[x["_source"]["metadata"]["kb_id"] for x in res["matched_chunks"]],
        matched_pages=[x["_source"]["metadata"]["page"] for x in res["matched_chunks"]],
    )

    return res


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
        session_id: str,
        project_id: str | None = None,
        user_id: str | None = None,
        user_query: str = "",
        system_response: str = "",
        matched_kb_ids: list[str] | None = None,
        matched_pages: list[int] | None = None,
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
