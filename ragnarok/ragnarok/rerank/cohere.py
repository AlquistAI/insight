# -*- coding: utf-8 -*-
"""
    ragnarok.rerank.cohere
    ~~~~~~~~~~~~~~~~~~~~~~

    Cohere reranker class.
"""

import requests

from common.config import CONFIG
from common.models import defaults as df
from common.models.enums import ModelProvider
from ragnarok.rerank.base import RerankerBase


class CohereReranker(RerankerBase):

    def __init__(self, model_name: str = "rerank-v3.5"):
        self._headers = {
            "Authorization": f"BEARER {CONFIG.COHERE_KEY.get_secret_value()}",
            "accept": "application/json",
            "content-type": "application/json",
        }

        super().__init__(provider=ModelProvider.Cohere, model_name=model_name)

    def rerank(self, query: str, documents: list[str], k: int = df.K_RERANK) -> list[int]:
        res = requests.post(
            url="https://api.cohere.ai/v1/rerank",
            headers=self._headers,
            json={
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": k,
                "return_documents": False,
            },
            timeout=(5, 20),
        )

        if res is None:
            raise ConnectionError("Failed to get rerank results from Cohere AI")
        return [x["index"] for x in res.json()["results"]][:k]
