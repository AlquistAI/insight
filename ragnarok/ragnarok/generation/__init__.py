# -*- coding: utf-8 -*-
"""
    ragnarok.generation
    ~~~~~~~~~~~~~~~~~~~

    Classes for generating and managing LLM instances.
"""

from typing import Any

from common.config import DF
from common.models.enums import ModelProvider
from common.utils import exceptions as exc
from common.utils.singleton import Singleton
from ragnarok.generation.base import LLMBase
from ragnarok.generation.openai_llm import OpenAILLM
from ragnarok.generation.vllm import NvidiaVLLM


class LLMFactory(metaclass=Singleton):

    def get_model(
            self,
            provider: ModelProvider = DF.PROVIDER_LLM,
            name: str = DF.MODEL_LLM,
            base_url: str | None = DF.BASE_URL_LLM,
    ) -> LLMBase:
        """
        Get or generate LLM instance.

        :param provider: model provider
        :param name: LLM name
        :param base_url: custom base URL to use
        :return: LLM instance
        """

        cls = self.get_model_class(provider=provider)
        args = self.get_model_args(provider=provider, name=name, base_url=base_url)
        return cls(**args)

    @staticmethod
    def get_model_class(provider: ModelProvider = DF.PROVIDER_LLM) -> type[LLMBase]:
        """Get LLM class based on provider."""

        if provider == ModelProvider.OpenAI:
            return OpenAILLM
        elif provider == ModelProvider.vLLM:
            return NvidiaVLLM

        raise exc.InvalidModelProvider(provider)

    @staticmethod
    def get_model_args(
            provider: ModelProvider = DF.PROVIDER_LLM,
            name: str = DF.MODEL_LLM,
            base_url: str | None = DF.BASE_URL_LLM,
    ) -> dict[str, Any]:
        """Get LLM class arguments."""

        args = {"model_name": name}
        if provider == ModelProvider.vLLM:
            args["base_url"] = base_url
        return args
