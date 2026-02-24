# -*- coding: utf-8 -*-
"""
    common.models.api_kronos
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Models used as payloads/responses in Kronos APIs.
"""

from pydantic import Field

from common.models import api_ragnarok as mar, elastic as me
from common.models.base import CustomBaseModel
from common.models.project import AISettings


###############
## RESOURCES ##
###############

class ChatbotConfig(CustomBaseModel):
    app_background_color: str = Field("#F9F9F9", alias="appBackgroundColor")
    bot_icon_color: str = Field("#1A73E8", alias="botIconColor")
    panel_background_color: str = Field("white", alias="panelBackgroundColor")
    primary_color: str = Field("#1A73E8", alias="primaryColor")
    primary_font_color: str = Field("white", alias="primaryFontColor")
    scrollbar_color: str = Field("#bbb", alias="scrollbarColor")
    scrollbar_hover_color: str = Field("#999", alias="scrollbarHoverColor")
    secondary_color: str = Field("#F0F4F8", alias="secondaryColor")
    secondary_font_color: str = Field("black", alias="secondaryFontColor")
    title_text: str = Field("Classic Blue", alias="titleText")

    # DEPRECATED --> ToDo: Remove once it is not used anywhere.
    bot_message_color: str = Field("", alias="botMessageColor")
    bot_message_font_color: str = Field("", alias="botMessageFontColor")
    edit_field_background_color: str = Field("", alias="editFieldBackgroundColor")
    edit_field_border_color: str = Field("", alias="editFieldBorderColor")
    footer_background_color: str = Field("", alias="footerBackgroundColor")
    frame_border_color: str = Field("", alias="frameBorderColor")
    navbar_color: str = Field("", alias="navbarColor")
    send_button_color: str = Field("", alias="sendButtonColor")
    suggestion_button_color: str = Field("", alias="suggestionButtonColor")
    suggestion_button_font_color: str = Field("", alias="suggestionButtonFontColor")
    title_font_color: str = Field("", alias="titleFontColor")
    user_icon_color: str = Field("", alias="userIconColor")
    user_message_color: str = Field("", alias="userMessageColor")
    user_message_font_color: str = Field("", alias="userMessageFontColor")


class ResourceInit(CustomBaseModel):
    # dialogue_fsm
    chatbot: ChatbotConfig | None = None
    image_url: str | None = None
    image_url_state_id: int = 1
    message: str | None = None
    message_state_id: int = 2


#########
## NLP ##
#########

class KBMetadata(me.KBMetadata):
    name: str = ""
    description: str = ""


class KBSource(me.KBSource):
    metadata: KBMetadata


class KBEntry(me.KBEntry):
    source: KBSource = Field(alias="_source")


class RAGPayload(mar.RAGPayload):
    lang: str | None = None
    settings: AISettings | None = None


class RAGTopMatch(mar.RAGTopMatch):
    name: str = ""
    description: str = ""


class RAGResponse(mar.RAGResponse):
    matched_chunks: list[KBEntry] | None = None
    top_match: RAGTopMatch
