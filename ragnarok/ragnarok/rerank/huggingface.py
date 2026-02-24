# -*- coding: utf-8 -*-
"""
    ragnarok.rerank.huggingface
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    HuggingFace - transformers rerankers.
"""

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from common.models import defaults as df
from common.models.enums import ModelProvider
from ragnarok.rerank.base import RerankerBase


class BGEReranker(RerankerBase):

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

        super().__init__(provider=ModelProvider.HuggingFace, model_name=model_name)

    def rerank(self, query: str, documents: list[str], k: int = df.K_RERANK) -> list[int]:
        pairs = [[query, d] for d in documents]

        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
            scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()

        scores = scores.detach().numpy()
        res = list(np.argsort(scores))
        res.reverse()
        return res[:k]


class JinaReranker(RerankerBase):

    def __init__(self, model_name: str = "jinaai/jina-reranker-v2-base-multilingual"):
        self.model = AutoModelForSequenceClassification.from_pretrained(
            pretrained_model_name_or_path=model_name,
            torch_dtype="auto",
            trust_remote_code=True,
        )

        self.model.to("cpu")
        self.model.eval()

        super().__init__(provider=ModelProvider.HuggingFace, model_name=model_name)

    def rerank(self, query: str, documents: list[str], k: int = df.K_RERANK) -> list[int]:
        pairs = [[query, d] for d in documents]
        scores = self.model.compute_score(pairs, max_length=1024)
        res = list(np.argsort(scores))
        res.reverse()
        return res[:k]
