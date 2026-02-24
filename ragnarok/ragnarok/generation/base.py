# -*- coding: utf-8 -*-
"""
    ragnarok.generation.base
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Base class for generative LLMs.
"""

from abc import ABC, abstractmethod
from typing import Generator

from common.models import defaults as df
from common.models.enums import ModelProvider
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
            temperature: float = df.TEMPERATURE,
    ) -> str:
        """
        Generate chat completion response based on the input messages.

        :param messages: chat messages
        :param temperature: generation temperature
        :return: response string
        """
        raise NotImplementedError

    @abstractmethod
    def chat_completion_stream(
            self,
            messages: list[dict[str, str]],
            temperature: float = df.TEMPERATURE,
    ) -> Generator[str, None, None]:
        """
        Stream chat completion response based on the input messages.

        :param messages: chat messages
        :param temperature: generation temperature
        :return: response generator
        """
        raise NotImplementedError
