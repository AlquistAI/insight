# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.base
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Base class for embedding algorithms.
"""

from abc import ABC, abstractmethod

import numpy as np

from common.models.enums import ModelProvider
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
        return self.vector("hello").size

    @abstractmethod
    def vector(self, s: str, normalize: bool = True) -> np.ndarray:
        """
        Transform sentence into vector representation.

        :param s: sentence
        :param normalize: normalize output to unit length
        :return: transformed sentence
        """
        raise NotImplementedError

    def vector_batch(self, batch: list[str], normalize: bool = True) -> np.ndarray:
        return np.asarray([self.vector(x, normalize) for x in batch]).reshape(-1, self.dim)
