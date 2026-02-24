# -*- coding: utf-8 -*-
"""
    common.utils.prompts
    ~~~~~~~~~~~~~~~~~~~~

    Utilities for building LLM prompts.
"""

from common.models import defaults as df

LANG_CODE_TO_NAME = {
    "cs": "Czech",
    "cs-CZ": "Czech",
    "en": "English",
    "en-US": "English",
}

PROMPT_GENERAL = (
    "Use the knowledge base context to answer the user's question. "
    "Always answer in {language}, unless specifically prompted otherwise. "
    "Ground your answer strictly in the provided knowledge base context. "
    "If the answer is not present in that context, say you don't know - do not invent facts. "
    "Be extremely precise. Do not include links or references; put the information directly in the answer. "
    "If there are multiple valid procedures/paths, list them with clear descriptions. "
    "Use the conversation history (if provided) only to resolve references. "
    "Do not copy facts from the history unless they also appear in the retrieved context. "
    "\n\nKNOWLEDGE BASE CONTEXT (authoritative): <CONTEXT>\n{context}\n</CONTEXT>"
)

PROMPT_REWRITE = (
    "You will receive a conversation history and the user's latest question.\n"
    "Rewrite ONLY the latest question into a single standalone query that is fully self-contained, "
    "resolving pronouns, ellipsis, and references using the conversation. "
    "Output ONLY the rewritten query text, nothing else. "
    "Write the query in {language}."
)


def build_prompt_general(kb_documents: list[str], lang: str = df.LANG) -> str:
    """
    Build LLM prompt for general RAG.

    :param kb_documents: list of retrieved knowledge base documents
    :param lang: conversation language
    :return: general LLM prompt
    """

    return PROMPT_GENERAL.format(
        context="\n\n".join(kb_documents),
        language=LANG_CODE_TO_NAME.get(lang) or LANG_CODE_TO_NAME[df.LANG],
    )


def build_prompt_rewrite(lang: str = df.LANG) -> str:
    """
    Build LLM prompt for query rewrite.

    :param lang: conversation language
    :return: query rewrite LLM prompt
    """

    return PROMPT_REWRITE.format(language=LANG_CODE_TO_NAME.get(lang) or LANG_CODE_TO_NAME[df.LANG])


def build_messages(system_prompt: str, query: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Build messages using system prompt, user's query and conversation history.

    :param system_prompt: system prompt
    :param query: user's query
    :param history: history messages
    :return: list of messages ready to be sent to LLM
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})
    return messages
