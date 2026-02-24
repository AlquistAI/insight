# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.vllm
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Embeddings served using Nvidia's vLLM interface.
"""

import numpy as np
from openai import OpenAI

from common.models.enums import ModelProvider
from common.utils.misc import generate_batches
from ragnarok.embeddings.base import EmbeddingBase

MODEL_DIMS = {
    "google/embeddinggemma-300m": 768,
}


class VLLMEmbeddings(EmbeddingBase):

    def __init__(self, model_name: str = "google/embeddinggemma-300m", base_url: str | None = None):
        self.client = OpenAI(api_key="vllm", base_url=base_url)

        super().__init__(
            provider=ModelProvider.vLLM,
            model_name=model_name,
            dim=MODEL_DIMS.get(model_name, 0),
            base_url=base_url,
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
