# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.base
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Base class for embedding algorithms.
"""

from abc import ABC, abstractmethod

import numpy as np

from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from common.utils.singleton import SingletonABC


class EmbeddingBase(ABC, metaclass=SingletonABC):
    """Base class for embedding algorithms."""

    def __init__(self, provider: ModelProvider, model_name: str, dim: int, base_url: str | None = None):
        self.provider = provider
        self.model_name = model_name
        self.dim = dim or self._get_dim_by_sample()
        self.base_url = base_url.rstrip("/") if base_url else None

    def _get_dim_by_sample(self) -> int:
        """Get embedding dimension by generating a sample vector."""
        return self.vector("hello")[0].size

    @abstractmethod
    def vector(self, s: str, normalize: bool = True) -> tuple[np.ndarray, ModelUsage | None]:
        """
        Transform sentence into vector representation.

        :param s: sentence
        :param normalize: normalize output to unit length
        :return: transformed sentence, token usage & cost of the call (None if not reported by the model)
        """
        raise NotImplementedError

    def vector_batch(self, batch: list[str], normalize: bool = True) -> tuple[np.ndarray, ModelUsage | None]:
        """
        Transform a batch of sentences into vector representations.

        :param batch: sentences
        :param normalize: normalize output to unit length
        :return: transformed sentences, token usage & cost of the calls (None if not reported by the model)
        """

        results = [self.vector(x, normalize) for x in batch]
        vectors = np.asarray([v for v, _ in results]).reshape(-1, self.dim)
        return vectors, self._merge_usage([u for _, u in results])

    def _build_usage(self, usage) -> ModelUsage | None:
        """
        Build a usage record from the usage object returned by an OpenAI-compatible API.

        :param usage: usage object of the API response (None if the API does not report usage)
        :return: token usage & cost of the call (None if not reported by the model)
        """

        if usage is None:
            return None

        return ModelUsage.build(
            provider=self.provider,
            model_name=self.model_name,
            input_tokens=usage.prompt_tokens,
            total_tokens=usage.total_tokens,
        )

    def _merge_usage(self, usages: list[ModelUsage | None]) -> ModelUsage | None:
        """
        Merge usage records of several calls of this model into a single record.

        :param usages: usage records to merge (None values are ignored)
        :return: merged usage record (None if there is nothing to merge)
        """

        if not (usages := [u for u in usages if u is not None]):
            return None
        return ModelUsage.merge(usages=usages, provider=self.provider, model_name=self.model_name)
