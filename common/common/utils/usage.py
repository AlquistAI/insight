# -*- coding: utf-8 -*-
"""
    common.utils.usage
    ~~~~~~~~~~~~~~~~~~

    Collector of the token usage and costs of the individual AI/NLP model calls.
"""

from common.models.enums import RAGStep
from common.models.usage import ModelUsage, UsageSummary


class UsageTracker:
    """
    Collector of the model calls made while processing a single request.

    Instances are *not* thread-safe - use one tracker per request.
    """

    def __init__(self):
        self.calls: list[ModelUsage] = []

    def add(self, usage: ModelUsage | None, step: RAGStep | None = None) -> ModelUsage | None:
        """
        Record usage of a single model call.

        The input record is not modified - a copy carrying the given step is recorded instead.

        :param usage: usage record of the call (ignored if None)
        :param step: RAG pipeline step this call belongs to (kept as is if None)
        :return: the recorded usage record
        """

        if usage is None:
            return None

        if step is not None:
            usage = usage.model_copy(update={"step": step})

        self.calls.append(usage)
        return usage

    def summary(self) -> UsageSummary:
        """Aggregate all recorded model calls into a usage summary."""

        return UsageSummary.from_calls(self.calls)
