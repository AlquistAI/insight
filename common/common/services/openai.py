# -*- coding: utf-8 -*-
"""
    common.services.openai
    ~~~~~~~~~~~~~~~~~~~~~~

    (Azure) OpenAI service utilities.
"""

import re

from cachetools.func import ttl_cache
from openai import OpenAI
from openai.lib.azure import AzureOpenAI

from common.config import CONFIG, OpenAIType

AZURE_API_VERSION = "2024-12-01-preview"


@ttl_cache(ttl=600)
def get_client() -> AzureOpenAI | OpenAI:
    """Get (Azure) OpenAI client based on OpenAI type config."""

    if CONFIG.OPENAI_TYPE == OpenAIType.AzureOpenAI:
        return AzureOpenAI(
            api_key=CONFIG.OPENAI_KEY.get_secret_value(),
            api_version=AZURE_API_VERSION,
            azure_endpoint=str(CONFIG.OPENAI_ENDPOINT),
        )

    return OpenAI(api_key=CONFIG.OPENAI_KEY.get_secret_value())


def get_gpt_version(model_name: str) -> float | None:
    """Get GPT model version from the model name string."""

    if "gpt" not in model_name:
        return None

    try:
        return float(re.sub("[^0-9.]", "", model_name))
    except ValueError:
        return None
