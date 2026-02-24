# -*- coding: utf-8 -*-
"""
    common.models.project
    ~~~~~~~~~~~~~~~~~~~~~

    Project model specification.
"""

from datetime import datetime
from typing import Literal, get_args

from pydantic import Field

from common.models import defaults as df
from common.models.base import CustomBaseModel
from common.models.enums import ModelProvider
from common.models.validation import Language, MongoID, object_id_str, utc_now

_T_VER_PROJECTS = Literal[3]
VER_PROJECTS: int = get_args(_T_VER_PROJECTS)[0]


#################
## AI SETTINGS ##
#################

class EmbeddingModelSettings(CustomBaseModel):
    provider: ModelProvider = df.PROVIDER_EMB
    name: str = df.MODEL_EMB
    base_url: str | None = None


class RerankingModelSettings(CustomBaseModel):
    provider: ModelProvider = df.PROVIDER_RERANK
    name: str = df.MODEL_RERANK


class GenerativeModelSettings(CustomBaseModel):
    provider: ModelProvider = df.PROVIDER_LLM
    name: str = df.MODEL_LLM
    base_url: str | None = None


class RetrievalSettings(CustomBaseModel):
    model: EmbeddingModelSettings = Field(default_factory=EmbeddingModelSettings)

    k_bm25: int = df.K_BM25
    k_emb: int = df.K_EMB
    num_candidates: int = df.NUM_CANDIDATES


class RerankingSettings(CustomBaseModel):
    enabled: bool = False
    model: RerankingModelSettings = Field(default_factory=RerankingModelSettings)

    k: int = df.K_RERANK


class GenerationSettings(CustomBaseModel):
    enabled: bool = True
    model: GenerativeModelSettings = Field(default_factory=GenerativeModelSettings)

    temperature: float = df.TEMPERATURE


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
    language: Language = df.LANG

    ai_settings: AISettings = Field(default_factory=AISettings)

    created_at: datetime = Field(default_factory=utc_now)
    model_version: _T_VER_PROJECTS = VER_PROJECTS
