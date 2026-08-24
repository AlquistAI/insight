# -*- coding: utf-8 -*-
"""
    ragnarok.rerank.jinaai
    ~~~~~~~~~~~~~~~~~~~~~~

    JinaAI reranker class.
"""

import requests

from common.config import CONFIG, DF
from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from ragnarok.rerank.base import RerankerBase


class JinaReranker(RerankerBase):

    def __init__(self, model_name: str = "jina-reranker-v2-base-multilingual"):
        self._headers = {
            "Authorization": f"Bearer {CONFIG.JINAAI_KEY.get_secret_value()}",
            "Content-Type": "application/json",
        }

        super().__init__(provider=ModelProvider.JinaAI, model_name=model_name)

    def rerank(
            self,
            query: str,
            documents: list[str],
            k: int = DF.K_RERANK,
    ) -> tuple[list[int], ModelUsage | None]:
        res = requests.post(
            url="https://api.jina.ai/v1/rerank",
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
            raise ConnectionError("Failed to get rerank results from JinaAI")

        res = res.json()
        ids = [x["index"] for x in res["results"]][:k]
        return ids, self._build_usage(res)

    def _build_usage(self, res: dict) -> ModelUsage | None:
        """
        Build a usage record from the JinaAI API response.

        JinaAI bills reranking by the total number of processed (query + document) tokens, which the
        API reports in the response `usage` object.

        :param res: JSON body of the API response
        :return: token usage & cost of the call (None if not reported by the API)
        """

        usage = res.get("usage") or {}

        if (tokens := usage.get("total_tokens")) is None:
            return None

        return ModelUsage.build(
            provider=self.provider,
            model_name=self.model_name,
            input_tokens=tokens,
        )
