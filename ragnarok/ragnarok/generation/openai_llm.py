# -*- coding: utf-8 -*-
"""
    ragnarok.generation.openai_llm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    OpenAI LLMs.
"""

from typing import Generator, Literal

from openai import NOT_GIVEN, NotGiven

from common.config import DF
from common.core.logger_utils import log_elapsed_time
from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from common.services.openai import get_client, get_gpt_version
from ragnarok.generation.base import LLMBase

T_REASONING_EFFORT = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] | NotGiven


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
            temperature: float = DF.TEMPERATURE,
    ) -> tuple[str, ModelUsage | None]:
        # noinspection PyTypeChecker
        completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self.reasoning_effort,
            temperature=self._validate_temperature(temperature),
            n=1,
        )

        return completion.choices[0].message.content, self._build_usage(completion.usage)

    def chat_completion_stream(
            self,
            messages: list[dict[str, str]],
            temperature: float = DF.TEMPERATURE,
    ) -> Generator[str, None, ModelUsage | None]:
        # noinspection PyTypeChecker
        completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
            reasoning_effort=self.reasoning_effort,
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

    def _validate_reasoning_effort(self, reasoning_effort: T_REASONING_EFFORT = NOT_GIVEN) -> T_REASONING_EFFORT:
        """
        Check if the given reasoning effort is valid for the selected model and set it accordingly.

        :param reasoning_effort: input reasoning effort, empty for default effort (model dependent)
        :return: valid reasoning effort
        """

        # We don't know the model restrictions -> use the provided value.
        if self.gpt_version is None:
            return reasoning_effort

        # Reasoning is not supported before GPT-5 -> use default value.
        if self.gpt_version < 5:
            return NOT_GIVEN

        # 'minimal' is only supported by GPT-5 -> use 'none' for other models.
        if reasoning_effort == "minimal":
            return reasoning_effort if self.gpt_version == 5 else "none"

        # 'max' is only supported starting GPT-5.6 -> use 'xhigh' for older models.
        if reasoning_effort == "max" and self.gpt_version < 5.6:
            reasoning_effort = "xhigh"

        # 'xhigh' is only supported starting GPT-5.2 -> use 'high' for older models.
        if reasoning_effort == "xhigh" and self.gpt_version < 5.2:
            reasoning_effort = "high"

        return reasoning_effort

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
