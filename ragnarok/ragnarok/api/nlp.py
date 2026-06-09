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
from ragnarok.rag import rag, rerank_by_answer
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

    hls = None
    text: str | None

    chunks, text = rag(
        project_id=project_id,
        query=payload.query,
        context=payload.context,
        kb_ids=payload.kb_ids,
        lang=payload.lang,
        settings=payload.settings,
        ftr_custom=payload.ftr_custom,
    )

    chunks = _process_matched_chunks(chunks=chunks, answer=text, payload=payload)
    if payload.return_highlights and chunks:
        hls = [_build_highlight_group_for_hit(project_id=project_id, payload=payload, hit=hit) for hit in chunks]

    return mar.RAGResponse(generated_text=text, highlights=hls, matched_chunks=chunks)


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

    Additional response object attributes, sent as the last chunk:
      - `highlights`: (list) data used for source snippet highlighting
      - `matched_chunks`: (list) matched document chunks
      - `text_full`: (str) full version of the streamed text

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :return: streamed RAG response (see description)
    """

    text_gen: Generator[str, None, None] | None
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

    response_gen = _streamed_rag_response(project_id=project_id, payload=payload, chunks=chunks, text_gen=text_gen)
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


def _process_matched_chunks(
        chunks: list[me.KBEntry],
        answer: str | None,
        payload: mar.RAGPayload,
) -> list[me.KBEntry] | None:
    """Process matched chunks based on RAG settings."""

    if not payload.return_matched_chunks:
        return None

    chunks = rerank_by_answer(matched_chunks=chunks, answer=answer, emb_settings=payload.settings.retrieval.model)
    for chunk in chunks:
        chunk.source.vector = None
    return chunks


def _streamed_rag_response(
        project_id: str,
        payload: mar.RAGPayload,
        chunks: list[me.KBEntry],
        text_gen: Generator[str, None, None] | None,
) -> Generator[str, None, None]:
    """Generate ndjson chunks for the streamed RAG response."""

    answer = ""
    hls = None
    idx = -1

    if text_gen is not None:
        for idx, text in enumerate(text_gen):
            answer += (text := text or "")
            yield json.dumps({"chunk_index": idx, "is_last_chunk": False, "text": text}) + "\n"

    chunks = _process_matched_chunks(chunks=chunks, answer=answer, payload=payload)
    if payload.return_highlights and chunks:
        # We are automatically building highlights only for the top chunk for performance reasons
        hls = [_build_highlight_group_for_hit(project_id=project_id, payload=payload, hit=chunks[0])]

    yield json.dumps({
        "chunk_index": idx + 1,
        "is_last_chunk": True,
        "highlights": jsonable_encoder(hls),
        "matched_chunks": jsonable_encoder(chunks),
        "text": "",
        "text_full": answer,
    }) + "\n"


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
