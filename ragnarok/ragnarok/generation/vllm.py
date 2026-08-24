# -*- coding: utf-8 -*-
"""
    ragnarok.generation.vllm
    ~~~~~~~~~~~~~~~~~~~~~~~~

    LLMs served using Nvidia's vLLM interface.
"""

from typing import Generator

from openai import OpenAI

from common.config import DF
from common.core.logger_utils import log_elapsed_time
from common.models.enums import ModelProvider
from common.models.usage import ModelUsage
from ragnarok.generation.base import LLMBase


class NvidiaVLLM(LLMBase):

    def __init__(self, model_name: str = "Qwen/Qwen3-30B-A3B", base_url: str | None = None):
        self.client = OpenAI(api_key="vllm", base_url=base_url)

        if model_name == "Qwen/Qwen3-30B-A3B":
            self.extra_body = {"chat_template_kwargs": {"enable_thinking": False}}
        else:
            self.extra_body = None

        super().__init__(
            provider=ModelProvider.vLLM,
            model_name=model_name,
            base_url=base_url,
        )

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
            temperature=temperature,
            n=1,
            extra_body=self.extra_body,
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
            temperature=temperature,
            n=1,
            extra_body=self.extra_body,
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
