# -*- coding: utf-8 -*-
"""
    ragnarok.utils.lc
    ~~~~~~~~~~~~~~~~~

    LangChain utilities.
"""

from langchain.embeddings.base import Embeddings
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings

from common.config import CONFIG
from common.models.enums import ModelProvider, OpenAIType
from common.models.project import EmbeddingModelSettings
from common.services.openai import AZURE_API_VERSION
from ragnarok.embeddings import EmbeddingFactory
from ragnarok.embeddings.openai_embeddings import MODEL_DIMS as OPENAI_EMB_DIMS
from ragnarok.embeddings.triton_embeddings import TritonEmbeddings

EF = EmbeddingFactory()


class InternalEmbeddings(Embeddings):

    def __init__(self, settings: EmbeddingModelSettings):
        self.model = EF.get_model(provider=settings.provider, name=settings.name, base_url=settings.base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if isinstance(self.model, TritonEmbeddings):
            return self.model.vector_batch(texts, timeout=60.0).tolist()
        return self.model.vector_batch(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.vector(text).tolist()

    def __str__(self):
        return self.model.model_name


def get_embeddings(settings: EmbeddingModelSettings) -> tuple[Embeddings, int]:
    """
    Get LangChain embeddings model.

    :param settings: embedding model settings
    :return: embedding model instance, embedding dimension
    """

    if settings.provider == ModelProvider.OpenAI:
        dimensions = CONFIG.ES_MAX_VECTOR_DIM if CONFIG.ES_MAX_VECTOR_DIM < OPENAI_EMB_DIMS[settings.name] else None
        dim = dimensions or OPENAI_EMB_DIMS[settings.name]

        if CONFIG.OPENAI_TYPE == OpenAIType.AzureOpenAI:
            model = AzureOpenAIEmbeddings(
                model=settings.name,
                api_key=CONFIG.OPENAI_KEY.get_secret_value(),
                api_version=AZURE_API_VERSION,
                azure_endpoint=str(CONFIG.OPENAI_ENDPOINT),
                dimensions=dimensions,
            )
        else:
            model = OpenAIEmbeddings(
                model=settings.name,
                api_key=CONFIG.OPENAI_KEY.get_secret_value(),
                dimensions=dimensions,
            )

        return model, dim

    model = InternalEmbeddings(settings=settings)
    return model, model.model.dim
