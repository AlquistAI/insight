# -*- coding: utf-8 -*-
"""
    ragnarok.utils.query_rewrite
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the CQR (Conversational Query Reformulation).
"""

from common.core import get_component_logger
from common.models import defaults as df
from common.models.api_ragnarok import ConversationTurn
from common.models.project import GenerativeModelSettings
from common.utils.prompts import build_messages, build_prompt_rewrite
from ragnarok.generation import LLMFactory

logger = get_component_logger()

LF = LLMFactory()


def process_context(context: list[ConversationTurn]) -> list[dict[str, str]]:
    """
    Convert a list of turns into a list of messages for LLM.

    :param context: input list of turns
    :return: list of messages
    """

    msgs: list[dict[str, str]] = []

    for turn in context:
        if uq := turn.user_query.strip():
            msgs.append({"role": "user", "content": uq})
        if sr := turn.system_response.strip():
            msgs.append({"role": "assistant", "content": sr})

    return msgs


def rewrite_query(
        query: str,
        history_messages: list[dict[str, str]],
        lang: str = df.LANG,
        settings: GenerativeModelSettings | None = None,
) -> str:
    """
    Rewrite a query for retrieval based on the message history.

    :param query: input user query
    :param history_messages: list of context messages
    :param lang: conversation language
    :param settings: LLM settings
    :return: rewritten query
    """

    if not history_messages:
        return query

    settings = settings or GenerativeModelSettings()

    try:
        system_prompt = build_prompt_rewrite(lang=lang)
        messages = build_messages(system_prompt=system_prompt, query=query, history=history_messages)
        model = LF.get_model(provider=settings.provider, name=settings.name, base_url=settings.base_url)
        rewritten_query = model.chat_completion(messages=messages, temperature=0.0)
        logger.debug('User query "%s" rewritten to "%s"', query, rewritten_query)
        return rewritten_query

    except Exception as e:
        logger.error("Failed to rewrite query: %s", e)
        return query
