# -*- coding: utf-8 -*-
"""
    maestro.api.nlp
    ~~~~~~~~~~~~~~~

    NLP endpoints generally used for communication with Ragnarok (mostly through Kronos).
"""

from typing import Any

from fastapi import status
from fastapi.param_functions import Depends
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from common.api.security_apikey import verify_apikey
from common.core import get_component_logger
from common.models import api_maestro as mam
from common.services import kronos, ragnarok
from common.utils.api import error_handler_async

logger = get_component_logger()
router = APIRouter()
dep = [Depends(verify_apikey)]


@router.post(
    "/projects/{project_id}/query/chunks",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get top-N matched chunks for a query",
)
@error_handler_async
async def ask_question_top_n(
        project_id: str,
        payload: mam.QueryPayload,
        session_id: str | None = None,
        user_id: str | None = None,
) -> dict[str, Any]:
    """
    Get top-N matched chunks for a query.

    :param project_id: project ID
    :param payload: request payload containing user query
    :param session_id: current session ID
    :param user_id: user ID for user tracking
    :return: response with top-N chunks
    """

    logger.info("query", extra={"query": payload.query})
    return await kronos.query_rag_top_n(
        project_id=project_id,
        session_id=session_id,
        user_id=user_id,
        query=payload.query,
        lang=payload.lang,
        return_highlights=payload.return_highlights,
        return_matched_chunks=payload.return_matched_chunks,
    )


@router.post(
    "/projects/{project_id}/query/rag",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get RAG response for a query",
)
@error_handler_async
async def ask_question(
        project_id: str,
        payload: mam.QueryPayload,
        session_id: str | None = None,
        user_id: str | None = None,
) -> StreamingResponse:
    """
    Get RAG response for a query. Stream the response.

    :param project_id: project ID
    :param payload: request payload containing user query
    :param session_id: current session ID
    :param user_id: user ID for user tracking
    :return: streamed RAG response
    """

    logger.info("query", extra={"query": payload.query})
    return StreamingResponse(
        content=kronos.query_rag(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
            query=payload.query,
            kb_ids=payload.kb_ids,
            lang=payload.lang,
            return_highlights=payload.return_highlights,
            return_matched_chunks=payload.return_matched_chunks,
        ),
        media_type="application/x-ndjson",
    )


@router.post(
    "/projects/{project_id}/query/rag/highlights",
    dependencies=dep,
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Fetch highlight group for a single matched hit",
)
@error_handler_async
async def fetch_highlights(project_id: str, request: mam.HighlightRequest) -> dict[str, Any]:
    """
    Fetch highlight group (L0 + L1) for a single matched hit.

    :param project_id: project ID
    :param request: original RAG payload & matched KB entry
    :return: highlight group data
    """

    return await ragnarok.get_highlights(project_id=project_id, payload=request.payload, hit=request.hit)
