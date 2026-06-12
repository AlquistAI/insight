# -*- coding: utf-8 -*-
"""
    kronos.api.nlp
    ~~~~~~~~~~~~~~

    NLP / text processing endpoints.
"""

import json
from typing import Any, Generator

from fastapi import status
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from common.config import CONFIG
from common.models import api_kronos as mak, api_ragnarok as mar, elastic as me
from common.utils.api import error_handler, error_handler_async
from kronos.services import ragnarok
from kronos.services.db.mongo.knowledge_base import get_kb_bulk
from kronos.services.db.mongo.projects import get_project_cached
from kronos.services.db.mongo.turns import list_turns

router = APIRouter()


@router.post(
    "/rag/",
    response_model=mak.RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Run RAG pipeline and get response",
)
@error_handler_async
async def rag_pipeline(project_id: str, payload: mak.RAGPayload, session_id: str = "") -> mak.RAGResponse:
    """
    Run RAG pipeline and get response.

    Payload parameters:
      - `query`: input user query
      - `context`: list of previous conversation turns (fetched automatically by session ID if not provided)
      - `ftr_custom`: list of custom ES filter clauses
      - `kb_ids`: knowledge base IDs to include (null/empty for all project documents)
      - `lang`: content language (uses project language if None)
      - `settings`: AI/NLP functionality settings (uses project AI settings if None)
      - `return_highlights`: return data for source snippet highlighting
      - `return_matched_chunks`: return matched chunks/documents in the response

    Example of `ftr_custom`:
      [{"term": {"metadata.custom.page_title.keyword": "Awesome Title"}}]

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :param session_id: session ID (for fetching conversation history)
    :return: RAG response
    """

    _fill_default_settings(project_id=project_id, payload=payload)

    if CONFIG.CONTEXT_ENABLED and not payload.context and session_id:
        turns, _ = list_turns(
            session_id=session_id,
            project_id=project_id,
            fields={"created_at", "system_response", "user_query"},
            sort_by="created_at",
            per_page=CONFIG.CONTEXT_WINDOW_SIZE,
        )

        payload.context = [mar.ConversationTurn.model_validate(t) for t in turns]

    res = await ragnarok.query_rag(project_id=project_id, payload=payload)

    return mak.RAGResponse(
        generated_text=res.generated_text,
        highlights=res.highlights,
        matched_chunks=_update_matched_chunks(res.matched_chunks),
    )


@router.post(
    "/rag/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Run RAG pipeline and get streamed response",
)
@error_handler
def rag_pipeline_stream(project_id: str, payload: mak.RAGPayload, session_id: str = "") -> StreamingResponse:
    """
    Run RAG pipeline and get streamed response.

    Payload parameters:
      - `query`: input user query
      - `context`: list of previous conversation turns (fetched automatically by session ID if not provided)
      - `ftr_custom`: list of custom ES filter clauses
      - `kb_ids`: knowledge base IDs to include (null/empty for all project documents)
      - `lang`: content language (uses project language if None)
      - `settings`: AI/NLP functionality settings (uses project AI settings if None)
      - `return_highlights`: return data for source snippet highlighting
      - `return_matched_chunks`: return matched chunks/documents in the response

    Example of `ftr_custom`:
      [{"term": {"metadata.custom.page_title.keyword": "Awesome Title"}}]

    The stream returns newline-delimited json-encoded objects with attributes:
      - `chunk_index`: (int) index of the current data chunk
      - `is_last_chunk`: (bool) whether the current chunk is the last chunk
      - `text`: (str) generated text chunk or empty string

    Additional response object attributes, sent as the last chunk:
      - `highlights`: (list) data used for source snippet highlighting
      - `matched_chunks`: (list) matched document chunks
      - `text_full`: (str) full version of the streamed text

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :param session_id: session ID (for fetching conversation history)
    :return: streamed RAG response (see description)
    """

    _fill_default_settings(project_id=project_id, payload=payload)

    if CONFIG.CONTEXT_ENABLED and not payload.context and session_id:
        turns, _ = list_turns(
            session_id=session_id,
            project_id=project_id,
            fields={"created_at", "system_response", "user_query"},
            sort_by="created_at",
            per_page=CONFIG.CONTEXT_WINDOW_SIZE,
        )

        payload.context = [mar.ConversationTurn.model_validate(t) for t in turns]

    res = ragnarok.query_rag_stream(project_id=project_id, payload=payload)
    return StreamingResponse(_streamed_rag_response(text_gen=res), media_type="application/x-ndjson")


def _fill_default_settings(project_id: str, payload: mak.RAGPayload):
    """Fill missing/empty values in the payload with default project settings."""

    project = get_project_cached(project_id=project_id)

    if not payload.lang:
        payload.lang = project.language

    if not payload.settings:
        payload.settings = project.ai_settings


def _update_matched_chunks(
        matched_chunks: list[me.KBEntry] | list[dict[str, Any]] | None,
) -> list[mak.KBEntry] | list[dict[str, Any]] | None:
    """Update matched chunks metadata with data from DB."""

    if not matched_chunks:
        return matched_chunks

    if not (dict_input := isinstance(matched_chunks[0], dict)):
        matched_chunks = [x.model_dump() for x in matched_chunks]
    matched_chunks = [mak.KBEntry.model_validate(x) for x in matched_chunks]

    ids = [x.source.metadata.kb_id for x in matched_chunks]
    data = get_kb_bulk(kb_ids=ids, fields={"name", "description", "source_file", "source_type"})

    for chunk, d in zip(matched_chunks, data):
        chunk.source.metadata.name = d["name"]
        chunk.source.metadata.description = d["description"]
        chunk.source.metadata.source_file = d["source_file"]
        chunk.source.metadata.source_type = d["source_type"]

    return [x.model_dump(mode="json") for x in matched_chunks] if dict_input else matched_chunks


def _streamed_rag_response(text_gen: Generator[str, None, None]) -> Generator[str, None, None]:
    """Generate ndjson chunks for the streamed RAG response."""

    for chunk in text_gen:
        if not (decoded_chunk := json.loads(chunk))["is_last_chunk"]:
            yield f"{chunk}\n"
            continue

        decoded_chunk["matched_chunks"] = _update_matched_chunks(decoded_chunk.get("matched_chunks"))
        yield f"{json.dumps(decoded_chunk)}\n"
