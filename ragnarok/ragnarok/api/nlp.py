# -*- coding: utf-8 -*-
"""
    ragnarok.api.nlp
    ~~~~~~~~~~~~~~~~

    NLP / text processing endpoints.
"""

import json
from typing import Generator

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api_ragnarok as mar, elastic as me
from common.utils.api import error_handler
from ragnarok.rag import rag
from ragnarok.vector_db import VectorStore

logger = get_component_logger()
router = APIRouter()

VS = VectorStore()


@router.post(
    "/rag/",
    response_model=mar.RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Run RAG pipeline and get response",
)
@error_handler
def rag_pipeline(project_id: str, payload: mar.RAGPayload) -> mar.RAGResponse:
    """
    Run RAG pipeline and get response.

    Payload parameters:
      - `query`: input user query
      - `context`: list of previous conversation turns
      - `ftr_custom`: list of custom ES filter clauses
      - `kb_ids`: knowledge base IDs to include (null/empty for all project documents)
      - `lang`: content language
      - `settings`: AI/NLP functionality settings
      - `return_highlights`: return data for source snippet highlighting
      - `return_matched_chunks`: return matched chunks/documents in the response

    Example of `ftr_custom`:
      [{"term": {"metadata.custom.page_title.keyword": "Awesome Title"}}]

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :return: RAG response
    """

    chunks, text = rag(
        project_id=project_id,
        query=payload.query,
        context=payload.context,
        kb_ids=payload.kb_ids,
        lang=payload.lang,
        settings=payload.settings,
        ftr_custom=payload.ftr_custom,
    )

    top = chunks[0]
    top_match = mar.RAGTopMatch(
        kb_id=top.source.metadata.kb_id,
        language=top.source.metadata.language,
        page=top.source.metadata.page,
        source_file=top.source.metadata.source_file,
        source_type=top.source.metadata.source_type,
    )

    highlights = [
        _build_highlight_group_for_hit(project_id=project_id, payload=payload, hit=hit)
        for hit in chunks
    ] if payload.return_highlights else None

    return mar.RAGResponse(
        generated_text=text,
        top_match=top_match,
        highlights=highlights,
        matched_chunks=chunks if payload.return_matched_chunks else None,
    )


@router.post(
    "/rag/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Run RAG pipeline and get streamed response",
)
@error_handler
def rag_pipeline_stream(project_id: str, payload: mar.RAGPayload) -> StreamingResponse:
    """
    Run RAG pipeline and get streamed response.

    Payload parameters:
      - `query`: input user query
      - `context`: list of previous conversation turns
      - `ftr_custom`: list of custom ES filter clauses
      - `kb_ids`: knowledge base IDs to include (null/empty for all project documents)
      - `lang`: content language
      - `settings`: AI/NLP functionality settings
      - `return_highlights`: return data for source snippet highlighting
      - `return_matched_chunks`: return matched chunks/documents in the response

    Example of `ftr_custom`:
      [{"term": {"metadata.custom.page_title.keyword": "Awesome Title"}}]

    The stream returns newline-delimited json-encoded objects with attributes:
      - `chunk_index`: (int) index of the current data chunk
      - `is_last_chunk`: (bool) whether the current chunk is the last chunk
      - `text`: (str) generated text chunk or empty string

    Additional response object attributes, sent as the first chunk with chunk_index -1:
      - `matched_chunks`: (list) list of matched document chunks using cosine similarity
      - `top_match`: (dict) data of the top matched document (see non-streamed version for details)

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :return: streamed RAG response (see description)
    """

    chunks, text_gen = rag(
        project_id=project_id,
        query=payload.query,
        context=payload.context,
        kb_ids=payload.kb_ids,
        lang=payload.lang,
        settings=payload.settings,
        ftr_custom=payload.ftr_custom,
        stream=True,
    )

    top = chunks[0]
    top_match = mar.RAGTopMatch(
        kb_id=top.source.metadata.kb_id,
        language=top.source.metadata.language,
        page=top.source.metadata.page,
        source_file=top.source.metadata.source_file,
        source_type=top.source.metadata.source_type,
    )

    top_highlight = _build_highlight_group_for_hit(
        project_id=project_id,
        payload=payload,
        hit=top,
    ) if payload.return_highlights else None

    response_gen = _streamed_rag_response(
        text_gen=text_gen,
        top_match=top_match,
        highlights=[top_highlight] if top_highlight else [],
        matched_chunks=chunks if payload.return_matched_chunks else None,
    )
    return StreamingResponse(response_gen, media_type="application/x-ndjson")


@router.post(
    "/rag/highlights",
    response_model=mar.RAGHighlightGroup,
    status_code=status.HTTP_200_OK,
    summary="Fetch highlight group for a single matched hit",
)
@error_handler
def fetch_highlights(project_id: str, request: mar.HighlightRequest) -> mar.RAGHighlightGroup:
    """
    Fetch highlight group (L0 + L1) for a single matched hit.

    :param project_id: project ID
    :param request: original RAG payload & matched KB entry
    :return: highlight group data
    """

    return _build_highlight_group_for_hit(project_id=project_id, payload=request.payload, hit=request.hit)


def _streamed_rag_response(
        text_gen: Generator[str, None, None] | None,
        top_match: mar.RAGTopMatch,
        highlights: list[mar.RAGHighlightGroup] | None,
        matched_chunks: list[me.KBEntry] | None,
) -> Generator[str, None, None]:
    """Generate ndjson chunks for the streamed RAG response."""

    yield json.dumps({
        "chunk_index": -1,
        "is_last_chunk": False,
        "text": "",
        "top_match": top_match.model_dump(),
        "highlights": jsonable_encoder(highlights),
        "matched_chunks": jsonable_encoder(matched_chunks),
    }) + "\n"

    if text_gen is None:
        return

    for idx, text in enumerate(text_gen):
        yield json.dumps({"chunk_index": idx, "is_last_chunk": text is None, "text": text or ""}) + "\n"


def _build_highlight_group_for_hit(project_id: str, payload: mar.RAGPayload, hit: me.KBEntry) -> mar.RAGHighlightGroup:
    """Compute highlights for exactly one matched hit (top-1)."""

    try:
        spans = VS.fetch_highlight_spans(
            kb_id=hit.source.metadata.kb_id,
            project_id=project_id,
            source_file=hit.source.metadata.source_file,
            page=hit.source.metadata.page,
            emb_settings=payload.settings.retrieval.model,
            query=payload.query,
            k=10,
        )
    except Exception as e:
        logger.error("Failed to fetch highlight spans: %s", e)
        spans = None

    header_len = len(f"SOURCE FILE: {hit.source.metadata.source_file}\n\n")
    l0_obj: mar.RAGHighlightSpan | None = None
    l1_list: list[mar.RAGHighlightSpan] = []

    for s in (spans or []):
        s_local = dict(s)
        s_local["start"] = (s_local.get("start") or 0) + header_len
        s_local["end"] = (s_local.get("end") or 0) + header_len

        span = mar.RAGHighlightSpan(
            kb_id=s_local.get("kb_id"),
            source_file=s_local.get("source_file"),
            page=s_local.get("page"),
            start=s_local.get("start"),
            end=s_local.get("end"),
            text=s_local.get("text"),
            score=s_local.get("score"),
            chunk_index=s_local.get("chunk_index"),
            chunk_level=s_local.get("chunk_level"),
        )

        if span.chunk_level == "L0" and l0_obj is None:
            l0_obj = span
        elif span.chunk_level == "L1":
            l1_list.append(span)

    l1_list.sort(key=lambda x: (x.score or 0.0), reverse=True)
    return mar.RAGHighlightGroup(l0_chunk=l0_obj, l1_chunks=l1_list)
