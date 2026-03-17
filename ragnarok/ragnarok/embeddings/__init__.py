# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings
    ~~~~~~~~~~~~~~~~~~~

    Classes for generating and managing text embeddings.
"""

from typing import Any

from common.config import DF
from common.models.enums import ModelProvider
from common.utils import exceptions as exc
from common.utils.singleton import Singleton
from ragnarok.embeddings.base import EmbeddingBase
from ragnarok.embeddings.openai_embeddings import OpenAIEmbeddings
from ragnarok.embeddings.triton_embeddings import TritonEmbeddings
from ragnarok.embeddings.vllm import VLLMEmbeddings


class EmbeddingFactory(metaclass=Singleton):

    def get_model(
            self,
            provider: ModelProvider = DF.PROVIDER_EMB,
            name: str = DF.MODEL_EMB,
            base_url: str | None = DF.BASE_URL_EMB,
    ) -> EmbeddingBase:
        """
        Get or generate embedding model instance.

        :param provider: model provider
        :param name: embedding model name
        :param base_url: custom base URL to use
        :return: embedding model instance
        """

        cls = self.get_model_class(provider=provider)
        args = self.get_model_args(provider=provider, name=name, base_url=base_url)
        return cls(**args)

    @staticmethod
    def get_model_class(provider: ModelProvider = DF.PROVIDER_EMB) -> type[EmbeddingBase]:
        """Get embedding model class based on provider."""

        if provider == ModelProvider.OpenAI:
            return OpenAIEmbeddings
        elif provider == ModelProvider.Triton:
            return TritonEmbeddings
        elif provider == ModelProvider.vLLM:
            return VLLMEmbeddings

        raise exc.InvalidModelProvider(provider)

    @staticmethod
    def get_model_args(
            provider: ModelProvider = DF.PROVIDER_EMB,
            name: str = DF.MODEL_EMB,
            base_url: str | None = DF.BASE_URL_EMB,
    ) -> dict[str, Any]:
        """Get embedding model class arguments."""

        args = {"model_name": name}
        if provider == ModelProvider.vLLM:
            args["base_url"] = base_url
        return args
