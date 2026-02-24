# -*- coding: utf-8 -*-
"""
    ragnarok.generation.openai_llm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    OpenAI LLMs.
"""

from typing import Generator

from openai import NOT_GIVEN, NotGiven

from common.core.logger_utils import log_elapsed_time
from common.models import defaults as df
from common.models.enums import ModelProvider
from common.services.openai import get_client, get_gpt_version
from ragnarok.generation.base import LLMBase


class OpenAILLM(LLMBase):

    def __init__(self, model_name: str = "gpt-4o"):
        self.client = get_client()
        super().__init__(provider=ModelProvider.OpenAI, model_name=model_name)

        self.gpt_version = get_gpt_version(self.model_name)
        self.reasoning_effort = self._validate_reasoning_effort()

    @log_elapsed_time
    def chat_completion(
            self,
            messages: list[dict[str, str]],
            temperature: float = df.TEMPERATURE,
    ) -> str:
        # noinspection PyTypeChecker
        return self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self.reasoning_effort,
            temperature=self._validate_temperature(temperature),
            n=1,
        ).choices[0].message.content

    def chat_completion_stream(
            self,
            messages: list[dict[str, str]],
            temperature: float = df.TEMPERATURE,
    ) -> Generator[str, None, None]:
        # noinspection PyTypeChecker
        completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self.reasoning_effort,
            temperature=self._validate_temperature(temperature),
            n=1,
            stream=True,
        )

        for chunk in completion:
            if chunk.choices:
                yield chunk.choices[0].delta.content

    def _validate_reasoning_effort(self, reasoning_effort: str | None = "none") -> str | NotGiven:
        """
        Check if the given reasoning effort is valid for the selected model and set it accordingly.

        :param reasoning_effort: input reasoning effort
        :return: valid reasoning effort
        """

        # We don't know the model restrictions -> use the provided value.
        if self.gpt_version is None:
            return reasoning_effort

        # Reasoning is not supported before GPT-5 -> use default value.
        if self.gpt_version < 5:
            return NOT_GIVEN

        # GPT models do not support None, but some of them support "none".
        if reasoning_effort is None:
            reasoning_effort = "none"

        # GPT-5 models do not support "none" -> use "minimal" (lowest value) instead.
        if self.gpt_version == 5 and reasoning_effort == "none":
            return "minimal"

        # GPT-5.1 and newer models do not support "minimal" -> use "none" instead.
        if self.gpt_version > 5 and reasoning_effort == "minimal":
            return "none"

        # Use the provided value in all other cases.
        return reasoning_effort

    def _validate_temperature(self, temperature: float = df.TEMPERATURE) -> float | NotGiven:
        """
        Check if the given temperature is valid for the selected model and set it accordingly.

        :param temperature: input temperature
        :return: valid temperature
        """

        # We don't know the model restrictions -> use the provided value.
        if self.gpt_version is None:
            return temperature

        # GPT-5 models do not support changing temperature -> use default value.
        if self.gpt_version == 5:
            return NOT_GIVEN

        # Temperature must be in the range [0, 2].
        if temperature < 0:
            return 0.0
        if temperature > 2:
            return 2.0

        # Use the provided value in all other cases.
        return temperature
