# -*- coding: utf-8 -*-
"""
    common.models.rag
    ~~~~~~~~~~~~~~~~~

    Models used for the RAG functionality.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from common.config import DF
from common.models.base import CustomBaseModel
from common.models.enums import ModelProvider, ReasoningEffort


#################
## AI SETTINGS ##
#################

class EmbeddingModelSettings(CustomBaseModel):
    provider: ModelProvider = DF.PROVIDER_EMB
    name: str = DF.MODEL_EMB
    base_url: str | None = DF.BASE_URL_EMB


class RerankingModelSettings(CustomBaseModel):
    provider: ModelProvider = DF.PROVIDER_RERANK
    name: str = DF.MODEL_RERANK


class GenerativeModelSettings(CustomBaseModel):
    provider: ModelProvider = DF.PROVIDER_LLM
    name: str = DF.MODEL_LLM
    base_url: str | None = DF.BASE_URL_LLM


class QueryRewriteSettings(CustomBaseModel):
    model: GenerativeModelSettings = Field(default_factory=GenerativeModelSettings)

    reasoning_effort: ReasoningEffort = DF.REASONING_EFFORT_REWRITE
    temperature: float = DF.TEMPERATURE_REWRITE


class RetrievalSettings(CustomBaseModel):
    model: EmbeddingModelSettings = Field(default_factory=EmbeddingModelSettings)

    k_bm25: int = DF.K_BM25
    k_emb: int = DF.K_EMB
    num_candidates: int = DF.NUM_CANDIDATES


class RerankingSettings(CustomBaseModel):
    enabled: bool = False
    model: RerankingModelSettings = Field(default_factory=RerankingModelSettings)

    k: int = DF.K_RERANK


class GenerationSettings(CustomBaseModel):
    enabled: bool = True
    model: GenerativeModelSettings = Field(default_factory=GenerativeModelSettings)

    reasoning_effort: ReasoningEffort = DF.REASONING_EFFORT
    temperature: float = DF.TEMPERATURE


class AISettings(CustomBaseModel):
    query_rewrite: QueryRewriteSettings = Field(default_factory=QueryRewriteSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    reranking: RerankingSettings = Field(default_factory=RerankingSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)


#########
## RAG ##
#########

class ConversationTurn(CustomBaseModel):
    user_query: str
    system_response: str
    created_at: datetime


class RAGOptions(CustomBaseModel):
    # AI/NLP functionality settings
    ai_settings: AISettings = Field(default_factory=AISettings)

    # Custom filters for getting KNN matches from VectorStore
    ftr_custom: list[dict[str, Any]] | None = None

    # Knowledge base IDs to include (None for all project documents)
    kb_ids: list[str] | None = None

    # Preferred conversation language
    lang: str = DF.LANG

    # Stream the LLM response (return generator)
    stream: bool = False
