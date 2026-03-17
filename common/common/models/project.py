# -*- coding: utf-8 -*-
"""
    common.models.project
    ~~~~~~~~~~~~~~~~~~~~~

    Project model specification.
"""

from datetime import datetime
from typing import Literal, get_args

from pydantic import Field

from common.config import DF
from common.models.base import CustomBaseModel
from common.models.enums import ModelProvider
from common.models.validation import Language, MongoID, object_id_str, utc_now

_T_VER_PROJECTS = Literal[3]
VER_PROJECTS: int = get_args(_T_VER_PROJECTS)[0]


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

    temperature: float = DF.TEMPERATURE


class AISettings(CustomBaseModel):
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    reranking: RerankingSettings = Field(default_factory=RerankingSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)


#############
## PROJECT ##
#############

class Project(CustomBaseModel):
    id: MongoID = Field(alias="_id", default_factory=object_id_str)

    name: str = ""
    description: str = ""
    language: Language = DF.LANG

    ai_settings: AISettings = Field(default_factory=AISettings)

    created_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_PROJECTS = VER_PROJECTS
