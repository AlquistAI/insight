# -*- coding: utf-8 -*-
"""
    common.models.usage
    ~~~~~~~~~~~~~~~~~~~

    Models describing the token usage and costs of the AI/NLP model calls.
"""

from pydantic import Field

from common.models.base import CustomBaseModel
from common.models.enums import ModelProvider, RAGStep
from common.utils.pricing import get_cost


class ModelUsage(CustomBaseModel):
    """
    Token usage and cost of a single AI/NLP model call.

    All usage/cost attributes are None when the model API does not report the given value.
    """

    provider: ModelProvider
    model_name: str
    step: RAGStep | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    search_units: int | None = None

    cost: float | None = None

    @classmethod
    def build(
            cls,
            provider: ModelProvider,
            model_name: str,
            input_tokens: int | None = None,
            output_tokens: int | None = None,
            total_tokens: int | None = None,
            search_units: int | None = None,
            step: RAGStep | None = None,
    ) -> "ModelUsage":
        """
        Create a usage record with the total token count and the cost computed automatically.

        :param provider: model provider
        :param model_name: model name
        :param input_tokens: number of consumed input/prompt tokens
        :param output_tokens: number of generated output/completion tokens
        :param total_tokens: total number of tokens (computed from input/output tokens if None)
        :param search_units: number of billed search units (rerank models)
        :param step: RAG pipeline step this call belongs to
        :return: usage record
        """

        if total_tokens is None and (input_tokens is not None or output_tokens is not None):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        return cls(
            provider=provider,
            model_name=model_name,
            step=step,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            search_units=search_units,
            cost=get_cost(
                provider=provider,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                search_units=search_units,
            ),
        )

    @classmethod
    def merge(
            cls,
            usages: list["ModelUsage"],
            provider: ModelProvider,
            model_name: str,
            step: RAGStep | None = None,
    ) -> "ModelUsage":
        """
        Merge usage records of several calls of the same model into a single record.

        Attributes not reported by any of the calls stay None (i.e. they are not counted as zero).

        :param usages: usage records to merge
        :param provider: model provider
        :param model_name: model name
        :param step: RAG pipeline step these calls belong to
        :return: merged usage record
        """

        def _sum(attr: str) -> int | None:
            values = [v for u in usages if (v := getattr(u, attr)) is not None]
            return sum(values) if values else None

        return cls.build(
            provider=provider,
            model_name=model_name,
            step=step,
            input_tokens=_sum("input_tokens"),
            output_tokens=_sum("output_tokens"),
            total_tokens=_sum("total_tokens"),
            search_units=_sum("search_units"),
        )


class UsageSummary(CustomBaseModel):
    """Aggregated token usage and costs of all AI/NLP model calls made within one RAG pipeline run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    search_units: int = 0

    cost: float = 0.0
    cost_complete: bool = True

    calls: list[ModelUsage] = Field(default_factory=list)

    @classmethod
    def from_calls(cls, calls: list[ModelUsage | None]) -> "UsageSummary":
        """
        Aggregate a list of individual model calls into a usage summary.

        Unknown (None) usage values are counted as zero; `cost_complete` is False if the cost
        of at least one of the calls could not be determined.

        :param calls: individual model call usage records (None values are ignored)
        :return: usage summary
        """

        calls = [c for c in calls if c is not None]

        return cls(
            input_tokens=sum(c.input_tokens or 0 for c in calls),
            output_tokens=sum(c.output_tokens or 0 for c in calls),
            total_tokens=sum(c.total_tokens or 0 for c in calls),
            search_units=sum(c.search_units or 0 for c in calls),
            cost=round(sum(c.cost or 0.0 for c in calls), 10),
            cost_complete=all(c.cost is not None for c in calls),
            calls=calls,
        )
