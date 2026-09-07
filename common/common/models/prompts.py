# -*- coding: utf-8 -*-
"""
    common.models.prompts
    ~~~~~~~~~~~~~~~~~~~~~

    Models used for the LLM prompts defined in the "prompts.md" resource file.
"""

from string import Formatter

from pydantic import model_validator

from common.models.base import CustomBaseModel

# Template variables that have to be present in each prompt (filled in during runtime).
# The keys have to match the field names of the Prompts model.
PROMPT_VARIABLES = {
    "query_rewrite": {"language"},
    "rag": {"context", "language"},
}


def get_prompt_variables(prompt: str) -> set[str]:
    """
    Get names of the template variables (placeholders) used in a prompt.

    :param prompt: prompt template
    :return: set of the used variable names
    :raise ValueError: the prompt is not a valid template (e.g. it contains unbalanced braces)
    """

    return {name for _, name, _, _ in Formatter().parse(prompt) if name is not None}


def _fmt_variables(variables: set[str]) -> str:
    """Format a set of variable names for an error message."""

    return ", ".join(sorted(f"{{{v}}}" for v in variables))


class Prompts(CustomBaseModel):
    """LLM prompts of a single project, parsed from its "prompts.md" resource file."""

    query_rewrite: str
    rag: str

    @model_validator(mode="after")
    def validate_prompt_variables(self) -> "Prompts":
        """Check that each prompt is a valid template using exactly the variables filled in during runtime."""

        for name, required in PROMPT_VARIABLES.items():
            if not (prompt := getattr(self, name).strip()):
                raise ValueError(f"the '{name}' prompt is empty")

            try:
                found = get_prompt_variables(prompt)
            except ValueError as e:
                raise ValueError(f"the '{name}' prompt is not a valid template: {e}") from None

            if found != required:
                raise ValueError(
                    f"the '{name}' prompt has to use exactly these variables: {_fmt_variables(required)} "
                    f"(found: {_fmt_variables(found) or 'none'})",
                )

        return self
