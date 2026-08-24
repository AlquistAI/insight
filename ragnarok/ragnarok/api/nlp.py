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
from common.models.enums import RAGStep
from common.models.usage import ModelUsage
from common.utils.api import error_handler
from common.utils.usage import UsageTracker
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

    The `usage` attribute of the response contains the aggregated token usage and costs (in USD) of
    all the model calls performed during the pipeline run, together with the individual calls. Usage
    values not reported by the model APIs are counted as zero and the `cost_complete` flag is set to
    false if the cost of any call could not be determined.

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :return: RAG response
    """

    hls = None
    usage = UsageTracker()

    chunks, text = rag(
        project_id=project_id,
        query=payload.query,
        context=payload.context,
        kb_ids=payload.kb_ids,
        lang=payload.lang,
        settings=payload.settings,
        ftr_custom=payload.ftr_custom,
        usage=usage,
    )

    chunks = _process_matched_chunks(chunks=chunks, answer=text, payload=payload, usage=usage)
    if payload.return_highlights and chunks:
        hls = [
            _build_highlight_group_for_hit(project_id=project_id, payload=payload, hit=hit, usage=usage)
            for hit in chunks
        ]

    return mar.RAGResponse(
        generated_text=text,
        highlights=hls,
        matched_chunks=chunks,
        usage=usage.summary(),
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

    Additional response object attributes, sent as the last chunk:
      - `highlights`: (list) data used for source snippet highlighting
      - `matched_chunks`: (list) matched document chunks
      - `text_full`: (str) full version of the streamed text
      - `usage`: (object) token usage & costs of the performed model calls

    :param project_id: project ID
    :param payload: payload with user query and additional settings (see description)
    :return: streamed RAG response (see description)
    """

    usage = UsageTracker()

    chunks, text_gen = rag(
        project_id=project_id,
        query=payload.query,
        context=payload.context,
        kb_ids=payload.kb_ids,
        lang=payload.lang,
        settings=payload.settings,
        ftr_custom=payload.ftr_custom,
        stream=True,
        usage=usage,
    )

    response_gen = _streamed_rag_response(
        project_id=project_id,
        payload=payload,
        chunks=chunks,
        text_gen=text_gen,
        usage=usage,
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


def _process_matched_chunks(
        chunks: list[me.KBEntry],
        answer: str | None,
        payload: mar.RAGPayload,
        usage: UsageTracker | None = None,
) -> list[me.KBEntry] | None:
    """Process matched chunks based on RAG settings."""

    if not payload.return_matched_chunks:
        return None

    chunks = rerank_by_answer(
        matched_chunks=chunks,
        answer=answer,
        emb_settings=payload.settings.retrieval.model,
        usage=usage,
    )

    for chunk in chunks:
        chunk.source.vector = None
    return chunks


def _streamed_rag_response(
        project_id: str,
        payload: mar.RAGPayload,
        chunks: list[me.KBEntry],
        text_gen: Generator[str, None, ModelUsage | None] | None,
        usage: UsageTracker,
) -> Generator[str, None, None]:
    """Generate ndjson chunks for the streamed RAG response."""

    answer = ""
    hls = None
    idx = -1

    # The usage of the generation call is added to the tracker once the generator is exhausted.
    if text_gen is not None:
        for idx, text in enumerate(text_gen):
            answer += (text := text or "")
            yield json.dumps({"chunk_index": idx, "is_last_chunk": False, "text": text}) + "\n"

    chunks = _process_matched_chunks(chunks=chunks, answer=answer, payload=payload, usage=usage)
    if payload.return_highlights and chunks:
        # We are automatically building highlights only for the top chunk for performance reasons
        hls = [_build_highlight_group_for_hit(project_id=project_id, payload=payload, hit=chunks[0], usage=usage)]

    yield json.dumps({
        "chunk_index": idx + 1,
        "is_last_chunk": True,
        "highlights": jsonable_encoder(hls),
        "matched_chunks": jsonable_encoder(chunks),
        "text": "",
        "text_full": answer,
        "usage": jsonable_encoder(usage.summary()),
    }) + "\n"


def _build_highlight_group_for_hit(
        project_id: str,
        payload: mar.RAGPayload,
        hit: me.KBEntry,
        usage: UsageTracker | None = None,
) -> mar.RAGHighlightGroup:
    """Compute highlights for exactly one matched hit (top-1)."""

    try:
        spans, usage_emb = VS.fetch_highlight_spans(
            kb_id=hit.source.metadata.kb_id,
            project_id=project_id,
            source_file=hit.source.metadata.source_file,
            page=hit.source.metadata.page,
            emb_settings=payload.settings.retrieval.model,
            query=payload.query,
            k=10,
        )

        if usage is not None:
            usage.add(usage_emb, step=RAGStep.RETRIEVAL)

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
