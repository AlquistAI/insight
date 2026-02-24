# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.huggingface
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    HuggingFace - (sentence) transformers embeddings.
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize as sk_normalize
from transformers import AutoConfig, AutoModel, AutoTokenizer

from common.models.enums import ModelProvider
from common.utils.misc import generate_batches
from ragnarok.embeddings.base import EmbeddingBase


class HFTransformer(EmbeddingBase):

    def __init__(self, model_name: str = "sentence-transformers/distiluse-base-multilingual-cased-v2"):
        self.model = AutoModel.from_pretrained(model_name)
        self.model_config = AutoConfig.from_pretrained(model_name)
        self.model_tokenizer = AutoTokenizer.from_pretrained(model_name)

        # ToDo: Different models save this info in different places. Make sure it works for all used models.
        self.max_seq_len = self.model_config.max_position_embeddings or self.model_tokenizer.model_max_length

        super().__init__(
            provider=ModelProvider.HuggingFace,
            model_name=model_name,
            dim=self.model_config.hidden_size,
        )

    def vector(self, s: str, normalize: bool = True) -> np.ndarray:
        return self.vector_batch([s], normalize=normalize)[0]

    def vector_batch(self, batch: list[str], normalize: bool = True) -> np.ndarray:
        result = None

        for batch_slice in generate_batches(batch, n=16):
            res = self._vector_batch(batch_slice)
            result = res if result is None else np.append(result, res, axis=0)

        result = np.array([]) if result is None else result
        return sk_normalize(result) if normalize else result

    def _vector_batch(self, batch: list[str]) -> np.ndarray:

        # encode sentences
        tokens = {"input_ids": [], "attention_mask": []}

        for s in batch:
            tokens_new = self.model_tokenizer.encode_plus(
                text=s,
                max_length=self.max_seq_len,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )

            tokens["input_ids"].append(tokens_new["input_ids"][0])
            tokens["attention_mask"].append(tokens_new["attention_mask"][0])

        # convert to tensors
        tokens["input_ids"] = torch.stack(tokens["input_ids"])
        tokens["attention_mask"] = torch.stack(tokens["attention_mask"])

        # compute embeddings
        outputs = self.model(**tokens)
        result = self._mean_pooling(outputs.last_hidden_state, tokens["attention_mask"])
        return self._tensor_to_np(result)

    @staticmethod
    def _mean_pooling(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        attention_mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.shape)
        summed = torch.sum(last_hidden_state * attention_mask, 1)
        counts = torch.clamp(attention_mask.sum(1), min=1e-9)
        return summed / counts

    @staticmethod
    def _tensor_to_np(tensor: torch.Tensor) -> np.ndarray:
        return tensor.detach().numpy()


class HFSentenceTransformer(EmbeddingBase):

    def __init__(self, model_name: str = "sentence-transformers/distiluse-base-multilingual-cased-v2"):
        self.model = SentenceTransformer(model_name)

        super().__init__(
            provider=ModelProvider.HuggingFace,
            model_name=model_name,
            dim=self.model.get_sentence_embedding_dimension(),
        )

    def vector(self, s: str, normalize: bool = True) -> np.ndarray:
        return self.vector_batch([s], normalize=normalize)[0]

    def vector_batch(self, batch: list[str], normalize: bool = True) -> np.ndarray:
        return self.model.encode(batch, normalize_embeddings=normalize)
