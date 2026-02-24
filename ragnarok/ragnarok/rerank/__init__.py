# -*- coding: utf-8 -*-
"""
    ragnarok.rerank
    ~~~~~~~~~~~~~~~

    Classes for managing rerankers.
"""

from common.models import defaults as df
from common.models.enums import ModelProvider
from common.utils import exceptions as exc
from common.utils.singleton import Singleton
from ragnarok.rerank.base import RerankerBase
from ragnarok.rerank.cohere import CohereReranker
from ragnarok.rerank.jinaai import JinaReranker


class RerankFactory(metaclass=Singleton):

    def get_model(
            self,
            provider: ModelProvider = df.PROVIDER_RERANK,
            name: str = df.MODEL_RERANK,
    ) -> RerankerBase:
        """
        Get or generate reranking model instance.

        :param provider: model provider
        :param name: reranking model name
        :return: reranking model instance
        """

        cls = self.get_model_class(provider=provider)
        args = {"model_name": name}
        return cls(**args)

    @staticmethod
    def get_model_class(provider: ModelProvider = df.PROVIDER_RERANK) -> type[RerankerBase]:
        """Get reranking model class based on provider."""

        if provider == ModelProvider.Cohere:
            return CohereReranker
        elif provider == ModelProvider.JinaAI:
            return JinaReranker

        raise exc.InvalidModelProvider(provider)
