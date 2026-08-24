# -*- coding: utf-8 -*-
"""
    ragnarok.generation.base
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Base class for generative LLMs.
"""

from abc import ABC, abstractmethod
from typing import Generator

from common.config import DF
from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from common.utils.singleton import SingletonABC


class LLMBase(ABC, metaclass=SingletonABC):
    """Base class for generative LLMs."""

    def __init__(self, provider: ModelProvider, model_name: str, base_url: str | None = None):
        self.provider = provider
        self.model_name = model_name
        self.base_url = base_url.rstrip("/") if base_url else None

    @abstractmethod
    def chat_completion(
            self,
            messages: list[dict[str, str]],
            temperature: float = DF.TEMPERATURE,
    ) -> tuple[str, ModelUsage | None]:
        """
        Generate chat completion response based on the input messages.

        :param messages: chat messages
        :param temperature: generation temperature
        :return: response string, token usage & cost of the call (None if not reported by the model)
        """
        raise NotImplementedError

    @abstractmethod
    def chat_completion_stream(
            self,
            messages: list[dict[str, str]],
            temperature: float = DF.TEMPERATURE,
    ) -> Generator[str, None, ModelUsage | None]:
        """
        Stream chat completion response based on the input messages.

        The token usage & cost of the call (None if not reported by the model) is returned as the
        generator's return value, i.e. it is available in the `StopIteration.value` attribute after
        the generator is exhausted (see `common.utils.misc.consume_generator`).

        :param messages: chat messages
        :param temperature: generation temperature
        :return: response generator returning the token usage & cost of the call
        """
        raise NotImplementedError

    def _build_usage(self, usage) -> ModelUsage | None:
        """
        Build a usage record from the usage object returned by an OpenAI-compatible API.

        :param usage: usage object of the API response (None if the API does not report usage)
        :return: token usage & cost of the call (None if not reported by the model)
        """

        if usage is None:
            return None

        return ModelUsage.build(
            provider=self.provider,
            model_name=self.model_name,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
