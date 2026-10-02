# -*- coding: utf-8 -*-
"""
    ragnarok.rag
    ~~~~~~~~~~~~

    RAG (retrieval-augmented generation) functionality.
"""

from collections import defaultdict
from typing import Generator

import numpy as np

from common.models import elastic as me
from common.models.enums import RAGStep
from common.models.rag import ConversationTurn, EmbeddingModelSettings, RAGOptions
from common.models.usage import ModelUsage
from common.services import kronos
from common.utils.misc import yield_from_with_return
from common.utils.prompts import build_messages, build_prompt_rag
from common.utils.usage import UsageTracker
from ragnarok.generation import LLMFactory
from ragnarok.rerank import RerankFactory
from ragnarok.utils import lc
from ragnarok.utils.query_rewrite import process_context, rewrite_query
from ragnarok.vector_db import VectorStore

LF = LLMFactory()
RF = RerankFactory()
VS = VectorStore()


def rag(
        query: str,
        project_id: str,
        session_id: str = "",
        context: list[ConversationTurn] | None = None,
        opts: RAGOptions | None = None,
        usage: UsageTracker | None = None,
) -> tuple[list[me.KBEntry], str | Generator[str, None, ModelUsage | None] | None]:
    """
    Get answer for a user query using RAG pipeline.

    The token usage & costs of all the performed model calls are recorded in the given usage tracker.
    In the streaming mode, the usage of the generation call is only known once the returned generator
    is exhausted - it is added to the tracker automatically as its last step.

    :param query: user query
    :param project_id: project ID
    :param session_id: session ID (used for caching the project prompts)
    :param context: list of previous conversation turns
    :param opts: options for RAG pipeline
    :param usage: tracker collecting the token usage & costs of the model calls
    :return: matched documents (chunks), response text / text chunk generator
    """

    opts = opts or RAGOptions()
    usage = usage or UsageTracker()
    return_vectors = opts.ai_settings.generation.enabled

    # prompts (project-specific file with a fallback to the default one, fetched from Kronos)
    prompts = kronos.get_prompts(project_id=project_id, session_id=session_id)

    # query rewrite
    history_messages = process_context(context or [])
    rewritten_query, usage_rewrite = rewrite_query(
        query=query,
        history_messages=history_messages,
        prompt=prompts.query_rewrite,
        lang=opts.lang,
        settings=opts.ai_settings.query_rewrite,
    )

    usage.add(usage_rewrite, step=RAGStep.QUERY_REWRITE)

    # cosine similarity
    hits_cosine, usage_emb = VS.knn_search(
        query=rewritten_query,
        project_id=project_id,
        kb_ids=opts.kb_ids,
        settings=opts.ai_settings.retrieval,
        ftr_custom=opts.ftr_custom,
        return_vectors=return_vectors,
    )

    usage.add(usage_emb, step=RAGStep.RETRIEVAL)

    # BM25 (no model call -> no usage/costs)
    hits_bm25 = VS.bm25_search(
        query=rewritten_query,
        project_id=project_id,
        kb_ids=opts.kb_ids,
        settings=opts.ai_settings.retrieval,
        ftr_custom=opts.ftr_custom,
        return_vectors=return_vectors,
    )

    hits = reciprocal_rank_fusion(hits_cosine, hits_bm25)
    documents = [hit.source.text for hit in hits]

    # reranking
    if (sr := opts.ai_settings.reranking).enabled:
        reranker = RF.get_model(provider=sr.model.provider, name=sr.model.name)
        ids, usage_rerank = reranker.rerank(query=rewritten_query, documents=documents, k=sr.k)
        hits = [hits[idx] for idx in ids]
        documents = [hit.source.text for hit in hits]
        usage.add(usage_rerank, step=RAGStep.RERANKING)

    # generation
    if (sg := opts.ai_settings.generation).enabled:
        model = LF.get_model(provider=sg.model.provider, name=sg.model.name, base_url=sg.model.base_url)
        system_prompt = build_prompt_rag(prompt=prompts.rag, kb_documents=documents, lang=opts.lang)
        messages = build_messages(system_prompt=system_prompt, query=query, history=history_messages)

        if opts.stream:
            gen_res = yield_from_with_return(
                gen=model.chat_completion_stream(
                    messages=messages,
                    temperature=sg.temperature,
                    reasoning_effort=sg.reasoning_effort,
                ),
                on_return=lambda u: usage.add(u, step=RAGStep.GENERATION),
            )
        else:
            gen_res, usage_gen = model.chat_completion(
                messages=messages,
                temperature=sg.temperature,
                reasoning_effort=sg.reasoning_effort,
            )
            usage.add(usage_gen, step=RAGStep.GENERATION)
    else:
        gen_res = None

    return hits, gen_res


def rerank_by_answer(
        matched_chunks: list[me.KBEntry],
        answer: str | None,
        emb_settings: EmbeddingModelSettings | None = None,
        usage: UsageTracker | None = None,
) -> list[me.KBEntry]:
    """
    Rerank the matched chunks based on the cosine similarity to the answer.

    :param matched_chunks: matched chunks
    :param answer: full answer (reranking not performed if None/empty)
    :param emb_settings: embedding model settings
    :param usage: tracker collecting the token usage & costs of the model calls
    :return: chunks in reranked order with updated scores
    """

    if not answer:
        return matched_chunks

    emb_settings = emb_settings or EmbeddingModelSettings()
    model, _ = lc.get_embeddings(settings=emb_settings)
    emb_chunks = np.asarray([chunk.source.vector for chunk in matched_chunks])
    emb_answer, usage_emb = model.embed_query_with_usage(answer)
    sim = np.dot(emb_chunks, np.asarray(emb_answer)).tolist()

    if usage is not None:
        usage.add(usage_emb, step=RAGStep.ANSWER_RERANKING)

    for chunk, score in zip(matched_chunks, sim):
        chunk.score = score

    return sorted(matched_chunks, key=lambda x: x.score, reverse=True)


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
