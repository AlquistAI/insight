# -*- coding: utf-8 -*-
"""
    ragnarok.rerank.cohere
    ~~~~~~~~~~~~~~~~~~~~~~

    Cohere reranker class.
"""

import requests

from common.config import CONFIG, DF
from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from ragnarok.rerank.base import RerankerBase


class CohereReranker(RerankerBase):

    def __init__(self, model_name: str = "rerank-v3.5"):
        self._headers = {
            "Authorization": f"BEARER {CONFIG.COHERE_KEY.get_secret_value()}",
            "accept": "application/json",
            "content-type": "application/json",
        }

        super().__init__(provider=ModelProvider.Cohere, model_name=model_name)

    def rerank(
            self,
            query: str,
            documents: list[str],
            k: int = DF.K_RERANK,
    ) -> tuple[list[int], ModelUsage | None]:
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

        res = res.json()
        ids = [x["index"] for x in res["results"]][:k]
        return ids, self._build_usage(res)

    def _build_usage(self, res: dict) -> ModelUsage | None:
        """
        Build a usage record from the Cohere API response.

        Cohere bills reranking by search units - the API reports the number of billed units in the
        response metadata (one unit is a query with up to 100 documents).

        :param res: JSON body of the API response
        :return: token usage & cost of the call (None if not reported by the API)
        """

        billed = (res.get("meta") or {}).get("billed_units") or {}

        if (search_units := billed.get("search_units")) is None:
            return None

        return ModelUsage.build(
            provider=self.provider,
            model_name=self.model_name,
            search_units=search_units,
        )
