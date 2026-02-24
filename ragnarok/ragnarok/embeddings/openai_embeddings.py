# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.openai_embeddings
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    OpenAI embedding algorithms.
"""

import numpy as np

from common.models.enums import ModelProvider
from common.services.openai import get_client
from common.utils.misc import generate_batches
from ragnarok.embeddings.base import EmbeddingBase

MODEL_DIMS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddings(EmbeddingBase):

    def __init__(self, model_name: str = "text-embedding-3-large"):
        self.client = get_client()

        super().__init__(
            provider=ModelProvider.OpenAI,
            model_name=model_name,
            dim=MODEL_DIMS.get(model_name, 0),
        )

    def vector(self, s: str, normalize: bool = True) -> np.ndarray:
        res = self.client.embeddings.create(input=s, model=self.model_name)
        return np.array(res.data[0].embedding)

    def vector_batch(self, batch: list[str], normalize: bool = True) -> np.ndarray:
        result = []

        for batch_slice in generate_batches(batch, 512):
            response = self.client.embeddings.create(input=batch_slice, model=self.model_name)
            embeddings = list(map(lambda x: x.embedding, response.data))
            result += embeddings

        # embeddings are already normalized
        return np.array(result).reshape(-1, self.dim)
