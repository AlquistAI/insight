# -*- coding: utf-8 -*-
"""
    ragnarok.generation
    ~~~~~~~~~~~~~~~~~~~

    Classes for generating and managing LLM instances.
"""

from typing import Any

from common.models import defaults as df
from common.models.enums import ModelProvider
from common.utils import exceptions as exc
from common.utils.singleton import Singleton
from ragnarok.generation.base import LLMBase
from ragnarok.generation.openai_llm import OpenAILLM
from ragnarok.generation.vllm import NvidiaVLLM


class LLMFactory(metaclass=Singleton):

    def get_model(
            self,
            provider: ModelProvider = df.PROVIDER_LLM,
            name: str = df.MODEL_LLM,
            base_url: str | None = None,
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
    def get_model_class(provider: ModelProvider = df.PROVIDER_LLM) -> type[LLMBase]:
        """Get LLM class based on provider."""

        if provider == ModelProvider.OpenAI:
            return OpenAILLM
        elif provider == ModelProvider.vLLM:
            return NvidiaVLLM

        raise exc.InvalidModelProvider(provider)

    @staticmethod
    def get_model_args(
            provider: ModelProvider = df.PROVIDER_LLM,
            name: str = df.MODEL_LLM,
            base_url: str | None = None,
    ) -> dict[str, Any]:
        """Get LLM class arguments."""

        args = {"model_name": name}
        if provider == ModelProvider.vLLM:
            args["base_url"] = base_url
        return args
