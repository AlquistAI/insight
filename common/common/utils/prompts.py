# -*- coding: utf-8 -*-
"""
    common.utils.prompts
    ~~~~~~~~~~~~~~~~~~~~

    Utilities for parsing and building LLM prompts.
"""

import re

from pydantic import ValidationError

from common.config import DF
from common.models.enums import ResourceType
from common.models.prompts import PROMPT_VARIABLES, Prompts
from common.utils import exceptions as exc

LANG_CODE_TO_NAME = {
    "cs": "Czech",
    "cs-CZ": "Czech",
    "en": "English",
    "en-US": "English",
}

# Prompt definitions in the "prompts.md" resource file: a level-2 Markdown heading holding the prompt name, followed by
# a fenced code block with the prompt template. Sections of the headings that do not hold a known prompt name are
# human-readable comments and are ignored.
RE_HEADING = re.compile(r"^##[ \t]+(?P<name>[^\n]+?)[ \t]*$", re.MULTILINE)
RE_PROMPT_TEMPLATE = re.compile(r"^```[^\n]*\n(?P<template>.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)

# Tag wrapping a single retrieved document (chunk) in the context of the RAG prompt, so that the model can tell where
# one document ends and the next one starts. Deliberately not numbered - the answer must not reference the documents.
TAG_DOCUMENT = "DOCUMENT"


#############
## PARSING ##
#############

def parse_prompts(content: str | bytes) -> Prompts:
    """
    Parse the LLM prompts from the content of a "prompts.md" resource file.

    Each prompt is defined by a level-2 Markdown heading holding the prompt name, followed by a fenced
    code block with the prompt template. Any other content of the file is ignored, i.e. it can be freely
    used for human-readable comments and guidelines.

    :param content: content of the prompts Markdown file
    :return: parsed prompts
    :raise InvalidResourceContent: the file cannot be parsed or the parsed prompts are not valid
    """

    text = content.decode("utf-8") if isinstance(content, bytes) else content
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # normalize the line endings of edited files
    headings = list(RE_HEADING.finditer(text))

    if not headings:
        raise _invalid_prompts("no prompt definition ('## <prompt_name>' heading) found in the file")

    # Extract the prompt templates - the section of each heading ends where the next heading starts
    prompts = {}

    for idx, heading in enumerate(headings):
        if (name := heading.group("name").lower()) not in PROMPT_VARIABLES:
            continue

        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)

        if (template := RE_PROMPT_TEMPLATE.search(text, heading.end(), end)) is None:
            raise _invalid_prompts(f"the '{name}' prompt definition does not contain a fenced code block")

        prompts[name] = template.group("template").strip()

    # Validate the parsed prompts (all prompts present, valid templates with the required variables)
    try:
        return Prompts.model_validate(prompts)
    except ValidationError as e:
        raise _invalid_prompts("; ".join(_format_validation_error(err) for err in e.errors())) from None


def _invalid_prompts(reason: str) -> exc.InvalidResourceContent:
    """Build an exception reporting an invalid prompts file."""

    return exc.InvalidResourceContent(resource_type=ResourceType.PROMPTS, reason=reason)


def _format_validation_error(error: dict) -> str:
    """Format a single pydantic validation error of the parsed prompts."""

    msg = error["msg"].removeprefix("Value error, ")
    return f"{loc}: {msg}" if (loc := ".".join(str(x) for x in error["loc"])) else msg


##############
## BUILDING ##
##############

def build_prompt_rag(prompt: str, kb_documents: list[str], lang: str = DF.LANG) -> str:
    """
    Build LLM prompt for general RAG.

    Each document is wrapped in a `TAG_DOCUMENT` tag to keep the individual documents separated -
    the retrieved chunks are independent excerpts of several files, not one continuous text.

    :param prompt: RAG prompt template
    :param kb_documents: list of retrieved knowledge base documents
    :param lang: conversation language
    :return: general LLM prompt
    """

    context = "\n\n".join(f"<{TAG_DOCUMENT}>\n{doc.strip()}\n</{TAG_DOCUMENT}>" for doc in kb_documents)
    return prompt.format(context=context, language=get_language_name(lang))


def build_prompt_rewrite(prompt: str, lang: str = DF.LANG) -> str:
    """
    Build LLM prompt for query rewrite.

    :param prompt: query rewrite prompt template
    :param lang: conversation language
    :return: query rewrite LLM prompt
    """

    return prompt.format(language=get_language_name(lang))


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


def get_language_name(lang: str = DF.LANG) -> str:
    """
    Get the English name of a language to be used in a prompt.

    :param lang: language code
    :return: language name
    """

    return LANG_CODE_TO_NAME.get(lang) or LANG_CODE_TO_NAME[DF.LANG]
