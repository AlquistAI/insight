# -*- coding: utf-8 -*-
"""
    common.models.fsm
    ~~~~~~~~~~~~~~~~~

    Models used for the FSM (Finite State Machine).
"""

from typing import Literal

from pydantic import Field

from common.models import defaults as df
from common.models.base import CustomBaseModel
from common.models.validation import Language


class _CommandBase(CustomBaseModel):
    type: str
    next_state: int = -1


class ButtonsCommand(_CommandBase):
    type: Literal["buttons"]

    class ButtonCommand(CustomBaseModel):
        class_: str = Field(alias="class")
        text: str
        next_state: int

    buttons: list[ButtonCommand]


class DisplayTextCommand(_CommandBase):
    type: Literal["display_text"]
    text: str


class GetTextCommand(_CommandBase):
    type: Literal["get_text"]
    text: str


class ImageCommand(_CommandBase):
    type: Literal["image"]

    text: str
    link: str | None = None


class RAGCommand(_CommandBase):
    type: Literal["get_rag", "get_top_n"]

    text: str
    streaming: bool = False

    top_n_buttons_enabled: bool = True
    top_n_count: int = 5


class SelectIntentCommand(_CommandBase):
    type: Literal["select_intent"]

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

    unique_user_id: str = ""
    unique_session_token: str = ""


class Dialogue(CustomBaseModel):
    dialogue_id: int
    dialogue_name: str
    dialogue_author: str = "UNKNOWN"
    dialogue_description: str = ""

    commands: list[DotCommand] = Field(default_factory=list)
    states: list[State]

    editor_active: bool = True
    editor_initial_file: str = ""
    language: Language = df.LANG
