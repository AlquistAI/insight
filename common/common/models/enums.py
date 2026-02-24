# -*- coding: utf-8 -*-
"""
    common.models.enums
    ~~~~~~~~~~~~~~~~~~~

    Enums used throughout the project.
"""

from enum import Enum, unique


#############
## AI / ML ##
#############

@unique
class ModelProvider(str, Enum):
    """Supported AI/NLP model providers."""

    Cohere = "Cohere"
    # HuggingFace = "HuggingFace"
    JinaAI = "JinaAI"
    OpenAI = "OpenAI"
    Triton = "Triton"
    vLLM = "vLLM"


############
## CONFIG ##
############

@unique
class ClientName(str, Enum):
    """Frontend client (repository) names."""

    ADMIN = "admin"
    ADMIN_SIMPLE = "admin_simplified"
    INTERACTOR = "chatbot_js"
    INTERACTOR_UPV = "chatbot-upv"


@unique
class LogFormat(str, Enum):
    """Logging formats."""

    json = "json"
    plain = "plain"


@unique
class OpenAIType(str, Enum):
    """Supported OpenAI API providers/types."""

    AzureOpenAI = "AzureOpenAI"
    OpenAI = "OpenAI"


@unique
class StorageType(str, Enum):
    """Supported storage backend providers/types."""

    AZURE_BLOB_STORAGE = "AZURE_BLOB_STORAGE"
    MINIO = "MINIO"


###########
## MONGO ##
###########

@unique
class Coll(str, Enum):
    """Collection names in MongoDB."""

    KB = "knowledge_base"
    PROJECTS = "projects"
    SESSIONS = "sessions"
    TURNS = "turns"


#########################
## STORAGE / DOCUMENTS ##
#########################

@unique
class ResourceType(str, Enum):
    """Types of resources saved in the storage."""

    CHATBOT_HTML = "chatbot_html"
    DIALOGUE_FSM = "dialogue_fsm"
    IMAGE = "image"

    SOURCE_DOCUMENT = "document_source"
    SOURCE_KB = "kb_source"

    # ToDo: Replace source_file with kb_source in other components and remove this.
    SOURCE_FILE = "source_file"


@unique
class SourceType(str, Enum):
    """Supported source types of the uploaded documents."""

    DOCX = "docx"
    HTML = "html"
    PDF = "pdf"
    PPTX = "pptx"
    TXT = "txt"
    XLSX = "xlsx"


RESOURCE_TO_MIME = {
    ResourceType.CHATBOT_HTML: "text/html",
    ResourceType.DIALOGUE_FSM: "application/json",
    ResourceType.IMAGE: "application/octet-stream",
    ResourceType.SOURCE_DOCUMENT: None,
    ResourceType.SOURCE_KB: None,
}

SOURCE_TO_MIME = {
    SourceType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    SourceType.HTML: "text/html",
    SourceType.PDF: "application/pdf",
    SourceType.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    SourceType.TXT: "text/plain",
    SourceType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

MIME_TO_SOURCE = {v: k for k, v in SOURCE_TO_MIME.items()}
