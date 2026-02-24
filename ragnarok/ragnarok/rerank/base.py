# -*- coding: utf-8 -*-
"""
    ragnarok.rerank.base
    ~~~~~~~~~~~~~~~~~~~~

    Base class for reranking algorithms.
"""

from abc import ABC, abstractmethod

from common.models import defaults as df
from common.models.enums import ModelProvider
from common.utils.singleton import SingletonABC


class RerankerBase(ABC, metaclass=SingletonABC):
    """Base class for reranking algorithms."""

    def __init__(self, provider: ModelProvider, model_name: str):
        self.provider = provider
        self.model_name = model_name

    @abstractmethod
    def rerank(self, query: str, documents: list[str], k: int = df.K_RERANK) -> list[int]:
        """
        Rerank documents.

        :param query: user query
        :param documents: list of documents to rerank
        :param k: top-K results to return
        :return: doc indices in the re-ranked order
        """
        raise NotImplementedError
