# -*- coding: utf-8 -*-
"""
    common.utils.fsm
    ~~~~~~~~~~~~~~~~

    Utilities for the dialogue FSM (Finite State Machine).
"""

from common.models import fsm

DEFAULT_QA_STATE_WELCOME_IMAGE = 1
DEFAULT_QA_STATE_WELCOME_MESSAGE = 2
DEFAULT_QA_STATE_RAG_COMMAND = 3
DEFAULT_QA_STATE_TOP_N_COMMAND = 4

DEFAULT_QA_ID = 0
DEFAULT_QA_NAME = "default_qa"
DEFAULT_QA_AUTHOR = "ella.brichova@cvut.cz"
DEFAULT_QA_DESCRIPTION = "Default dialogue implementing simple question-answering from the uploaded knowledge base."
DEFAULT_QA_WELCOME_IMAGE = "default.png"

DEFAULTS_QA_CS = {
    "editor_initial_file": (
        "<ul><li>Nejste aktuálně připojeni k žádnému konkrétnímu systému.</li>"
        "<li>Nemám přímý přístup k internetu nebo vnějším databázím.</li>"
        "<li>Mám přístup pouze k poskytnutému kontextu a k obecným informacím do října 2023.</li>"
        "<li>Nemohu tedy zpracovávat informace mimo ty v poskytnutém kontextu nebo znalosti po říjnu 2023.</li></ul>"
    ),
    "query_prompt": "Zadej dotaz",
    "welcome_message": (
        "## Vítejte v aplikaci Alquist Insight!\n"
        "- Po otevření aplikace klikněte na ikonku 'ZDROJE' vpravo nahoře a vyberte soubory, ve kterých se bude "
        "vyhledávat.\n"
        "- Chatbot pro vás vygeneruje odpověď, přičemž v pravé části obrazovky se současně zobrazí zdrojové dokumenty, "
        "ze kterých čerpal.\n"
        "- Pod odpovědí naleznete tlačítka odkazující na související stránky/úseky dokumentů, ze kterých chatbot "
        "vycházel.\n"
        "- V zobrazeném dokumentu můžete ověřit správnost odpovědi nebo pomocí lupy dohledat další informace. "
        "**DÚLEŽITÉ - Chatbot se může mýlit, vždy si ověřte správnost odpovědi ve zdrojových dokumentech!**\n"
        "- Pro hodnocení odpovědi klikněte na ikonu palce nahoru nebo dolů."
    ),
}

DEFAULTS_QA_EN = {
    "editor_initial_file": (
        "<ul><li>You are currently not connected to any external system.</li>"
        "<li>I don't have access to the internet or any external databases.</li>"
        "<li>I have access only to the provided context.</li>"
        "<li>I cannot process information not provided in the context.</li></ul>"
    ),
    "query_prompt": "Submit your query",
    "welcome_message": (
        "## Welcome to the Alquist Insight bot!\n"
        "- After opening the app, you can click the 'KNOWLEDGE BASE' icon on the top right and choose the files that "
        "will be used for the search.\n"
        "- After you type a question, the bot will generate an answer for you, while at the same time showing "
        "the source documents it used on the right side of the screen.\n"
        "- Under the answer you can find buttons referencing the documents the bot used for generating the answer.\n"
        "- Use the document viewer to ensure the generated answer is correct. "
        "**REMEMBER - The bot can make mistakes, always check the answer against the source!**\n"
        "- You can give feedback by clicking thumbs up/down buttons below the answer."
    ),
}

DEFAULTS_QA = {
    "cs-CZ": DEFAULTS_QA_CS,
    "en-US": DEFAULTS_QA_EN,
}


def build_qa(data: fsm.DialogueInit | None = None) -> fsm.Dialogue:
    """
    Build a simple Q&A dialogue FSM.

    :param data: custom dialogue fields
    :return: dialogue FSM
    """

    data = data or fsm.DialogueInit()
    defaults = DEFAULTS_QA[data.language]

    commands = [
        fsm.DotCommand(name="help", state=DEFAULT_QA_STATE_WELCOME_MESSAGE),
        fsm.DotCommand(name="rag-mode", state=DEFAULT_QA_STATE_RAG_COMMAND),
        fsm.DotCommand(name="top-n-mode", state=DEFAULT_QA_STATE_TOP_N_COMMAND),
    ]

    s_welcome_image = fsm.State(
        state_id=DEFAULT_QA_STATE_WELCOME_IMAGE,
        command=fsm.ImageCommand(
            text=data.welcome_image or DEFAULT_QA_WELCOME_IMAGE,
            next_state=DEFAULT_QA_STATE_WELCOME_MESSAGE,
        ),
    )

    s_welcome_message = fsm.State(
        state_id=DEFAULT_QA_STATE_WELCOME_MESSAGE,
        command=fsm.DisplayTextCommand(
            text=data.welcome_message or defaults["welcome_message"],
            next_state=DEFAULT_QA_STATE_RAG_COMMAND,
        ),
    )

    s_rag = fsm.State(
        state_id=DEFAULT_QA_STATE_RAG_COMMAND,
        command=fsm.RAGCommand(
            type="get_rag",
            text=data.query_prompt or defaults["query_prompt"],
            next_state=DEFAULT_QA_STATE_RAG_COMMAND,
        ),
    )

    s_top_n = fsm.State(
        state_id=DEFAULT_QA_STATE_TOP_N_COMMAND,
        command=fsm.RAGCommand(
            type="get_top_n",
            text=data.query_prompt or defaults["query_prompt"],
            next_state=DEFAULT_QA_STATE_TOP_N_COMMAND,
        ),
    )

    return fsm.Dialogue(
        dialogue_id=DEFAULT_QA_ID,
        dialogue_name=DEFAULT_QA_NAME,
        dialogue_author=DEFAULT_QA_AUTHOR,
        dialogue_description=DEFAULT_QA_DESCRIPTION,
        language=data.language,
        editor_initial_file=defaults["editor_initial_file"],
        commands=commands,
        states=[s_welcome_image, s_welcome_message, s_rag, s_top_n],
    )
