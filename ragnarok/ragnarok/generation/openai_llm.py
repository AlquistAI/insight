# -*- coding: utf-8 -*-
"""
    ragnarok.generation.openai_llm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    OpenAI LLMs.
"""

from typing import Generator

from openai import NOT_GIVEN, NotGiven

from common.config import DF
from common.core.logger_utils import log_elapsed_time, log_elapsed_time_stream
from common.models.enums import ModelProvider, ReasoningEffort
from common.models.usage import ModelUsage
from common.services.openai import get_client, get_gpt_version
from ragnarok.generation.base import LLMBase


class OpenAILLM(LLMBase):

    def __init__(self, model_name: str = "gpt-5.6-luna"):
        super().__init__(provider=ModelProvider.OpenAI, model_name=model_name)
        self.client = get_client()
        self.gpt_version = get_gpt_version(self.model_name)

    @log_elapsed_time
    def chat_completion(
            self,
            messages: list[dict[str, str]],
            temperature: float = DF.TEMPERATURE,
            reasoning_effort: ReasoningEffort | None = None,
    ) -> tuple[str, ModelUsage | None]:
        # noinspection PyTypeChecker
        completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self._validate_reasoning_effort(reasoning_effort),
            temperature=self._validate_temperature(temperature),
            n=1,
        )

        return completion.choices[0].message.content, self._build_usage(completion.usage)

    @log_elapsed_time_stream
    def chat_completion_stream(
            self,
            messages: list[dict[str, str]],
            temperature: float = DF.TEMPERATURE,
            reasoning_effort: ReasoningEffort | None = None,
    ) -> Generator[str, None, ModelUsage | None]:
        # noinspection PyTypeChecker
        completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self._validate_reasoning_effort(reasoning_effort),
            temperature=self._validate_temperature(temperature),
            n=1,
            stream=True,
            stream_options={"include_usage": True},
        )

        usage = None

        for chunk in completion:
            # Usage is reported in a separate final chunk (with an empty `choices` list).
            if chunk.usage is not None:
                usage = chunk.usage
            if chunk.choices:
                yield chunk.choices[0].delta.content

        return self._build_usage(usage)

    def _validate_reasoning_effort(self, reasoning_effort: ReasoningEffort | None = None) -> str | NotGiven:
        """
        Check if the given reasoning effort is valid for the selected model and set it accordingly.

        :param reasoning_effort: input reasoning effort, None for default effort (model dependent)
        :return: valid reasoning effort value (`NOT_GIVEN` for the model default)
        """

        # No effort requested / we don't know the model restrictions / reasoning not supported before GPT-5
        #   -> use the default effort
        if reasoning_effort is None or self.gpt_version is None or self.gpt_version < 5:
            return NOT_GIVEN

        # 'minimal' is only supported by GPT-5 -> use 'none' for other models
        if reasoning_effort == ReasoningEffort.MINIMAL and self.gpt_version != 5:
            reasoning_effort = ReasoningEffort.NONE

        # 'none' is not supported by GPT-5 -> use 'minimal', the lowest effort it supports
        if reasoning_effort == ReasoningEffort.NONE and self.gpt_version == 5:
            reasoning_effort = ReasoningEffort.MINIMAL

        # 'none' is not supported starting GPT-6 -> use 'low', the lowest effort these models support
        if reasoning_effort == ReasoningEffort.NONE and self.gpt_version >= 6:
            reasoning_effort = ReasoningEffort.LOW

        # 'max' is only supported starting GPT-5.6 -> use 'xhigh' for older models
        if reasoning_effort == ReasoningEffort.MAX and self.gpt_version < 5.6:
            reasoning_effort = ReasoningEffort.XHIGH

        # 'xhigh' is only supported starting GPT-5.2 -> use 'high' for older models
        if reasoning_effort == ReasoningEffort.XHIGH and self.gpt_version < 5.2:
            reasoning_effort = ReasoningEffort.HIGH

        return reasoning_effort.value

    def _validate_temperature(self, temperature: float = DF.TEMPERATURE) -> float | NotGiven:
        """
        Check if the given temperature is valid for the selected model and set it accordingly.

        :param temperature: input temperature
        :return: valid temperature
        """

        # We don't know the model restrictions -> use the provided value.
        if self.gpt_version is None:
            return temperature

        # GPT-5 models and newer do not support changing temperature -> use default value.
        if self.gpt_version >= 5:
            return NOT_GIVEN

        # Temperature must be in the range [0, 2].
        if temperature < 0:
            return 0.0
        if temperature > 2:
            return 2.0

        return temperature
