# -*- coding: utf-8 -*-
"""
    ragnarok.utils.lc
    ~~~~~~~~~~~~~~~~~

    LangChain utilities.
"""

import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Iterator

from langchain.embeddings.base import Embeddings
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings

from common.config import CONFIG
from common.models.enums import ModelProvider, OpenAIType
from common.models.project import EmbeddingModelSettings
from common.models.usage import ModelUsage
from common.services.openai import AZURE_API_VERSION
from ragnarok.embeddings import EmbeddingFactory
from ragnarok.embeddings.openai_embeddings import MODEL_DIMS as OPENAI_EMB_DIMS
from ragnarok.embeddings.triton_embeddings import TritonEmbeddings

EF = EmbeddingFactory()


class UsageAwareEmbeddings(Embeddings, ABC):
    """
    LangChain embeddings interface extended with the token usage & cost reporting.

    The plain LangChain methods (`embed_query`, `embed_documents`) discard the usage information -
    use their `*_with_usage` variants to get it.
    """

    def __init__(self, provider: ModelProvider, model_name: str, dim: int):
        self.provider = provider
        self.model_name = model_name
        self.dim = dim

    @abstractmethod
    def embed_query_with_usage(self, text: str) -> tuple[list[float], ModelUsage | None]:
        """
        Embed a query.

        :param text: query text
        :return: embedding vector, token usage & cost of the call (None if not reported by the model)
        """
        raise NotImplementedError

    @abstractmethod
    def embed_documents_with_usage(self, texts: list[str]) -> tuple[list[list[float]], ModelUsage | None]:
        """
        Embed a list of documents.

        :param texts: document texts
        :return: embedding vectors, token usage & cost of the calls (None if not reported by the model)
        """
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_query_with_usage(text)[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents_with_usage(texts)[0]

    def __str__(self):
        return self.model_name


class InternalEmbeddings(UsageAwareEmbeddings):
    """LangChain wrapper of our own embedding model implementations."""

    def __init__(self, settings: EmbeddingModelSettings):
        self.model = EF.get_model(provider=settings.provider, name=settings.name, base_url=settings.base_url)

        super().__init__(
            provider=self.model.provider,
            model_name=self.model.model_name,
            dim=self.model.dim,
        )

    def embed_query_with_usage(self, text: str) -> tuple[list[float], ModelUsage | None]:
        vector, usage = self.model.vector(text)
        return vector.tolist(), usage

    def embed_documents_with_usage(self, texts: list[str]) -> tuple[list[list[float]], ModelUsage | None]:
        if isinstance(self.model, TritonEmbeddings):
            vectors, usage = self.model.vector_batch(texts, timeout=60.0)
        else:
            vectors, usage = self.model.vector_batch(texts)

        return vectors.tolist(), usage


class UsageRecordingClient:
    """
    Proxy of the OpenAI embeddings API client recording the usage of the performed calls.

    The LangChain embedding classes discard the usage data reported by the API - this proxy takes the
    place of their API client to collect it. The recorded usages are stored per thread, so that
    requests processed in parallel do not interfere with each other.
    """

    def __init__(self, client: Any):
        self._client = client
        self._local = threading.local()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def create(self, *args, **kwargs) -> Any:
        """Create embeddings and record the reported usage (if recording is active in this thread)."""

        res = self._client.create(*args, **kwargs)

        if (usages := getattr(self._local, "usages", None)) is not None:
            usages.append(res["usage"] if isinstance(res, dict) else res.usage)

        return res

    @contextmanager
    def record(self) -> Iterator[list[Any]]:
        """Record the usage of all the calls performed in this thread within the context."""

        usages: list[Any] = []
        previous = getattr(self._local, "usages", None)
        self._local.usages = usages

        try:
            yield usages
        finally:
            self._local.usages = previous


class LCOpenAIEmbeddings(UsageAwareEmbeddings):
    """LangChain (Azure) OpenAI embeddings with the token usage & cost reporting."""

    def __init__(self, settings: EmbeddingModelSettings, dim: int, dimensions: int | None = None):

        if CONFIG.OPENAI_TYPE == OpenAIType.AzureOpenAI:
            self.model = AzureOpenAIEmbeddings(
                model=settings.name,
                api_key=CONFIG.OPENAI_KEY.get_secret_value(),
                api_version=AZURE_API_VERSION,
                azure_endpoint=str(CONFIG.OPENAI_ENDPOINT),
                dimensions=dimensions,
            )
        else:
            self.model = OpenAIEmbeddings(
                model=settings.name,
                api_key=CONFIG.OPENAI_KEY.get_secret_value(),
                dimensions=dimensions,
            )

        # Replace the API client with a proxy collecting the usage data discarded by LangChain.
        self.client = UsageRecordingClient(self.model.client)
        self.model.client = self.client

        super().__init__(provider=ModelProvider.OpenAI, model_name=settings.name, dim=dim)

    def embed_query_with_usage(self, text: str) -> tuple[list[float], ModelUsage | None]:
        with self.client.record() as usages:
            vector = self.model.embed_query(text)
        return vector, self._build_usage(usages)

    def embed_documents_with_usage(self, texts: list[str]) -> tuple[list[list[float]], ModelUsage | None]:
        with self.client.record() as usages:
            vectors = self.model.embed_documents(texts)
        return vectors, self._build_usage(usages)

    def _build_usage(self, usages: list[Any]) -> ModelUsage | None:
        """
        Build a usage record from the usage objects collected by the API client proxy.

        :param usages: usage objects of the performed API calls
        :return: token usage & cost of the calls (None if not reported by the API)
        """

        if not (usages := [u for u in usages if u is not None]):
            return None

        def _get(usage: Any, attr: str) -> int | None:
            return usage.get(attr) if isinstance(usage, dict) else getattr(usage, attr, None)

        return ModelUsage.build(
            provider=self.provider,
            model_name=self.model_name,
            input_tokens=sum(_get(u, "prompt_tokens") or 0 for u in usages),
            total_tokens=sum(_get(u, "total_tokens") or 0 for u in usages),
        )


def get_embeddings(settings: EmbeddingModelSettings) -> tuple[UsageAwareEmbeddings, int]:
    """
    Get LangChain embeddings model.

    :param settings: embedding model settings
    :return: embedding model instance, embedding dimension
    """

    if settings.provider == ModelProvider.OpenAI:
        dimensions = CONFIG.ES_MAX_VECTOR_DIM if CONFIG.ES_MAX_VECTOR_DIM < OPENAI_EMB_DIMS[settings.name] else None
        dim = dimensions or OPENAI_EMB_DIMS[settings.name]
        return LCOpenAIEmbeddings(settings=settings, dim=dim, dimensions=dimensions), dim

    model = InternalEmbeddings(settings=settings)
    return model, model.dim
