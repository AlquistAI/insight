# -*- coding: utf-8 -*-
"""
    ragnarok.utils.query_rewrite
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the CQR (Conversational Query Reformulation).
"""

import re

from common.config import DF
from common.core import get_component_logger
from common.models.rag import ConversationTurn, QueryRewriteSettings
from common.models.usage import ModelUsage
from common.utils.prompts import build_messages, build_prompt_rewrite
from ragnarok.generation import LLMFactory

logger = get_component_logger()

LF = LLMFactory()

# Label the model may prefix the rewritten query with, despite the prompt asking for the query only.
RE_QUERY_LABEL = re.compile(
    r"^(?:(?:final|new|reformulated|rewritten|search|standalone)[ \t]+)?(?:query|question)[ \t]*:[ \t]*",
    re.IGNORECASE,
)

# Characters the model may wrap the rewritten query in (Markdown emphasis, quotes of several locales).
CHARS_MARKUP = "*_`"
CHARS_QUOTE = "\"'‚‘’„“”«»"

# Word count above which the model output is not considered a search query anymore, but an answer to the user's
# question or a query with added commentary. Well above the limit required by the prompt - discarding a valid query
# is cheap (the original user query is used instead), using an answer as the search query is not.
MAX_QUERY_WORDS = 40


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
        prompt: str,
        lang: str = DF.LANG,
        settings: QueryRewriteSettings | None = None,
) -> tuple[str, ModelUsage | None]:
    """
    Rewrite a query for retrieval based on the message history.

    :param query: input user query
    :param history_messages: list of context messages
    :param prompt: query rewrite prompt template
    :param lang: conversation language
    :param settings: query rewrite settings (LLM & its call parameters)
    :return: rewritten query, token usage & cost of the call (None if there was no/failed call)
    """

    if not history_messages:
        return query, None

    settings = settings or QueryRewriteSettings()
    s_model = settings.model

    try:
        system_prompt = build_prompt_rewrite(prompt=prompt, lang=lang)
        messages = build_messages(system_prompt=system_prompt, query=query, history=history_messages)
        model = LF.get_model(provider=s_model.provider, name=s_model.name, base_url=s_model.base_url)
        completion, usage = model.chat_completion(
            messages=messages,
            temperature=settings.temperature,
            reasoning_effort=settings.reasoning_effort,
        )

        rewritten_query = sanitize_rewritten_query(completion=completion, query=query)
        logger.debug('User query "%s" rewritten to "%s"', query, rewritten_query)
        return rewritten_query, usage

    except Exception as e:
        logger.error("Failed to rewrite query: %s", e)
        return query, None


def sanitize_rewritten_query(completion: str | None, query: str) -> str:
    """
    Extract the search query from the raw output of the query rewrite call.

    The prompt asks for a single line holding the rewritten query only, but the models do not always
    comply - they label the query, wrap it in quotes, add commentary or ignore the task and answer the
    user's question instead. The query is used as an ElasticSearch query, so such an output degrades the
    retrieval instead of improving it. Fixable deviations are stripped here, while an output that does
    not look like a search query at all is discarded in favor of the original user query.

    :param completion: raw output of the query rewrite call
    :param query: original user query (used as a fallback)
    :return: query to be used for the knowledge base search
    """

    # Strip a leading label ("Query:", "Rewritten query:", ...), which may be on a line of its own
    text = RE_QUERY_LABEL.sub("", (completion or "").strip().lstrip("-*•> \t"))

    # Keep the first non-empty line only - whatever the model added below it is not part of the query
    lines = (line.strip() for line in text.splitlines())
    text = next((line for line in lines if line), "")

    # Strip the remaining decorations the model may have wrapped the query in
    text = text.lstrip("-*•> \t").strip(CHARS_MARKUP).strip()

    if len(text) > 1 and text[0] in CHARS_QUOTE and text[-1] in CHARS_QUOTE:
        text = text[1:-1].strip()

    # Fall back to the original query if the result is not usable as a search query
    if not any(char.isalnum() for char in text):
        logger.warning('Query rewrite returned no usable query ("%s") --> using the original query', text)
        return query

    if (words := len(text.split())) > MAX_QUERY_WORDS:
        logger.warning("Query rewrite returned %d words instead of a query --> using the original query", words)
        return query

    return text
