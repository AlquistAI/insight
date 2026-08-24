# -*- coding: utf-8 -*-
"""
    common.models.fsm
    ~~~~~~~~~~~~~~~~~

    Models used for the FSM (Finite State Machine).
"""

from typing import Literal

from pydantic import Field

from common.config import DF
from common.models.base import CustomBaseModel
from common.models.validation import Language


class _CommandBase(CustomBaseModel):
    type: str
    next_state: int = -1


class ButtonsCommand(_CommandBase):
    type: Literal["buttons"] = "buttons"

    class ButtonCommand(CustomBaseModel):
        class_: str = Field(alias="class")
        text: str
        next_state: int

    buttons: list[ButtonCommand]


class DisplayTextCommand(_CommandBase):
    type: Literal["display_text"] = "display_text"
    text: str


class GetTextCommand(_CommandBase):
    type: Literal["get_text"] = "get_text"
    text: str


class ImageCommand(_CommandBase):
    type: Literal["image"] = "image"

    text: str
    link: str | None = "strada"


class RAGCommand(_CommandBase):
    type: Literal["get_rag", "get_top_n"] = "get_rag"

    text: str
    streaming: bool = True

    top_n_buttons_enabled: bool = True
    top_n_count: int = 5


class SelectIntentCommand(_CommandBase):
    type: Literal["select_intent"] = "select_intent"

    class AlternateSentence(CustomBaseModel):
        sentences: list[str]
        next_state: int

    alternate_sentences: list[AlternateSentence]


Command = ButtonsCommand | DisplayTextCommand | GetTextCommand | ImageCommand | RAGCommand | SelectIntentCommand


class DotCommand(CustomBaseModel):
    name: str
    state: int


class State(CustomBaseModel):
    state_id: int
    command: Command


class Dialogue(CustomBaseModel):
    dialogue_id: int
    dialogue_name: str
    dialogue_author: str = "UNKNOWN"
    dialogue_description: str = ""
    language: Language = DF.LANG

    editor_active: bool = False
    editor_initial_file: str = ""

    commands: list[DotCommand] = Field(default_factory=list)
    states: list[State]


class DialogueInit(CustomBaseModel):
    language: Language = DF.LANG
    query_prompt: str | None = None
    welcome_image: str | None = None
    welcome_message: str | None = None
