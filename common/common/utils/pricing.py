# -*- coding: utf-8 -*-
"""
    common.utils.pricing
    ~~~~~~~~~~~~~~~~~~~~

    Price lists of the supported AI/NLP models and cost computation utilities.
"""

import re
from typing import NamedTuple

from common.models.enums import ModelProvider


class ModelPrice(NamedTuple):
    """Model price in USD - per 1M input/output tokens, per 1K search units (rerank models)."""

    input: float = 0.0
    output: float = 0.0
    search: float = 0.0


# Price of the models running on our own infrastructure (no per-token/per-request API costs)
PRICE_FREE = ModelPrice()

# Providers of the models running on our own infrastructure
PROVIDERS_SELF_HOSTED = (ModelProvider.Triton, ModelProvider.vLLM)

# Suffix with the model release date, used by some providers (e.g. "gpt-4o-2024-08-06")
RE_MODEL_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# ToDo: Keep the price lists up to date with the providers' pricing pages.
PRICES: dict[ModelProvider, dict[str, ModelPrice]] = {
    ModelProvider.Cohere: {
        # Reranking models
        "rerank-english-v3.0": ModelPrice(search=2.00),
        "rerank-multilingual-v3.0": ModelPrice(search=2.00),
        "rerank-v3.5": ModelPrice(search=2.00),
        "rerank-v4.0-fast": ModelPrice(search=2.00),
        "rerank-v4.0-pro": ModelPrice(search=2.50),
    },
    ModelProvider.JinaAI: {
        # Reranking models
        "jina-reranker-m0": ModelPrice(input=0.05),
        "jina-reranker-v2-base-multilingual": ModelPrice(input=0.05),
        "jina-reranker-v3": ModelPrice(input=0.05),
        "jina-reranker-v3.5": ModelPrice(input=0.05),
    },
    ModelProvider.OpenAI: {
        # Embedding models
        "text-embedding-3-large": ModelPrice(input=0.13),
        "text-embedding-3-small": ModelPrice(input=0.02),
        "text-embedding-ada-002": ModelPrice(input=0.10),

        # Generative models
        "o3": ModelPrice(input=2.00, output=8.00),
        "o3-mini": ModelPrice(input=1.10, output=4.40),
        "o4-mini": ModelPrice(input=1.10, output=4.40),
        "gpt-4o": ModelPrice(input=2.50, output=10.00),
        "gpt-4o-mini": ModelPrice(input=0.15, output=0.60),
        "gpt-4.1": ModelPrice(input=2.00, output=8.00),
        "gpt-4.1-mini": ModelPrice(input=0.40, output=1.60),
        "gpt-4.1-nano": ModelPrice(input=0.10, output=0.40),
        "gpt-5": ModelPrice(input=1.25, output=10.00),
        "gpt-5-mini": ModelPrice(input=0.25, output=2.00),
        "gpt-5-nano": ModelPrice(input=0.05, output=0.40),
        "gpt-5.1": ModelPrice(input=1.25, output=10.00),
        "gpt-5.2": ModelPrice(input=1.75, output=14.00),
        "gpt-5.4": ModelPrice(input=2.50, output=15.00),
        "gpt-5.4-mini": ModelPrice(input=0.75, output=4.50),
        "gpt-5.4-nano": ModelPrice(input=0.20, output=1.25),
        "gpt-5.5": ModelPrice(input=5.00, output=30.00),
        "gpt-5.6-luna": ModelPrice(input=0.20, output=1.20),
        "gpt-5.6-terra": ModelPrice(input=2.00, output=12.00),
        "gpt-5.6-sol": ModelPrice(input=5.00, output=30.00),
    },
}


def get_model_price(provider: ModelProvider, model_name: str) -> ModelPrice | None:
    """
    Get the price list of a given model.

    :param provider: model provider
    :param model_name: model name
    :return: model price (None if the price of the model is not known)
    """

    if provider in PROVIDERS_SELF_HOSTED:
        return PRICE_FREE

    prices = PRICES.get(provider, {})

    if (price := prices.get(model_name)) is not None:
        return price

    # Some providers append the model release date to the model name -> try the base name as well.
    return prices.get(RE_MODEL_DATE_SUFFIX.sub("", model_name))


def get_cost(
        provider: ModelProvider,
        model_name: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        search_units: int | None = None,
) -> float | None:
    """
    Compute the cost of a model call in USD.

    :param provider: model provider
    :param model_name: model name
    :param input_tokens: number of consumed input/prompt tokens (None if not reported by the model)
    :param output_tokens: number of generated output/completion tokens (None if not reported by the model)
    :param search_units: number of billed search units (None if not reported by the model)
    :return: cost in USD (None if it cannot be determined)
    """

    # The price of the model is not known -> we cannot compute the cost.
    if (price := get_model_price(provider=provider, model_name=model_name)) is None:
        return None

    # The model runs on our own infrastructure -> there are no per-token API costs.
    if price == PRICE_FREE:
        return 0.0

    # The model does not report its usage -> we cannot compute the cost.
    if input_tokens is None and output_tokens is None and search_units is None:
        return None

    cost = (
            (input_tokens or 0) * price.input / 1_000_000
            + (output_tokens or 0) * price.output / 1_000_000
            + (search_units or 0) * price.search / 1_000
    )

    return round(cost, 10)
