# -*- coding: utf-8 -*-
"""
    ragnarok.rag
    ~~~~~~~~~~~~

    RAG (retrieval-augmented generation) functionality.
"""

from collections import defaultdict
from typing import Any, Generator

from common.models import defaults as df, elastic as me
from common.models.api_ragnarok import ConversationTurn
from common.models.project import AISettings
from common.utils.prompts import build_messages, build_prompt_general
from ragnarok.generation import LLMFactory
from ragnarok.rerank import RerankFactory
from ragnarok.utils.query_rewrite import process_context, rewrite_query
from ragnarok.vector_db import VectorStore

LF = LLMFactory()
RF = RerankFactory()
VS = VectorStore()


def rag(
        project_id: str,
        query: str,
        context: list[ConversationTurn] | None = None,
        kb_ids: list[str] | None = None,
        lang: str = df.LANG,
        settings: AISettings | None = None,
        ftr_custom: list[dict[str, Any]] | None = None,
        stream: bool = False,
) -> tuple[list[me.KBEntry], str | Generator[str, None, None] | None]:
    """
    Get answer for a user query using RAG pipeline.

    :param project_id: project ID
    :param query: user query
    :param context: list of previous conversation turns
    :param kb_ids: knowledge base IDs to include (None for all project documents)
    :param lang: content language
    :param settings: AI/NLP functionality settings
    :param ftr_custom: custom filters for getting KNN matches from VectorStore
    :param stream: stream the LLM response (return generator)
    :return: matched documents (chunks), response text / text chunk generator
    """

    settings = settings or AISettings()

    # query rewrite
    history_messages = process_context(context or [])
    rewritten_query = rewrite_query(
        query=query,
        history_messages=history_messages,
        lang=lang,
        settings=settings.generation.model,
    )

    # cosine similarity
    hits_cosine = VS.knn_search(
        query=rewritten_query,
        project_id=project_id,
        kb_ids=kb_ids,
        settings=settings.retrieval,
        ftr_custom=ftr_custom,
    )

    # BM25
    hits_bm25 = VS.bm25_search(
        query=rewritten_query,
        project_id=project_id,
        kb_ids=kb_ids,
        settings=settings.retrieval,
        ftr_custom=ftr_custom,
    )

    hits = reciprocal_rank_fusion(hits_cosine, hits_bm25)
    documents = [hit.source.text for hit in hits]

    # reranking
    if (sr := settings.reranking).enabled:
        reranker = RF.get_model(provider=sr.model.provider, name=sr.model.name)
        ids = reranker.rerank(query=rewritten_query, documents=documents, k=sr.k)
        hits = [hits[idx] for idx in ids]
        documents = [hit.source.text for hit in hits]

    # generation
    if (sg := settings.generation).enabled:
        model = LF.get_model(provider=sg.model.provider, name=sg.model.name, base_url=sg.model.base_url)
        system_prompt = build_prompt_general(kb_documents=documents, lang=lang)
        messages = build_messages(system_prompt=system_prompt, query=query, history=history_messages)

        gen_func = model.chat_completion_stream if stream else model.chat_completion
        # noinspection PyArgumentList
        gen_res = gen_func(messages=messages, temperature=sg.temperature)
    else:
        gen_res = None

    return hits, gen_res


def reciprocal_rank_fusion(
        cosine_results: list[me.KBEntry],
        bm25_results: list[me.KBEntry],
        c: int = 60,
) -> list[me.KBEntry]:
    # Create a dictionary to hold ranks
    ranks = defaultdict(lambda: [None, None])  # {doc_id: [cosine_rank, bm25_rank]}

    # Assign ranks for cosine results
    for rank, result in enumerate(cosine_results):
        # noinspection PyTypeChecker
        ranks[result.id][0] = rank + 1

    # Assign ranks for BM25 results
    for rank, result in enumerate(bm25_results):
        # noinspection PyTypeChecker
        ranks[result.id][1] = rank + 1

    # Calculate RRF scores
    rrf_scores = {}

    for doc_id, (cosine_rank, bm25_rank) in ranks.items():
        score = 0
        if cosine_rank is not None:
            score += 1 / (cosine_rank + c)
        if bm25_rank is not None:
            score += 1 / (bm25_rank + c)

        rrf_scores[doc_id] = score

    # Sort documents by RRF score
    reranked_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = cosine_results + bm25_results
    results = {r.id: r for r in results}

    out = []
    for doc_id, score in reranked_docs:
        res = results[doc_id]
        res.score = score
        out.append(res)

    return out
