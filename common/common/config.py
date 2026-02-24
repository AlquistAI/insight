# -*- coding: utf-8 -*-
"""
    common.config
    ~~~~~~~~~~~~~

    App configuration.

    Contains default values generally safe to use for public (develop) Kubernetes deployment.
"""

from pathlib import Path

from pydantic import AnyUrl, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from common.models.enums import ClientName, LogFormat, OpenAIType, StorageType

DIR_ROOT = Path(__file__).parent.parent.parent
PATH_ES_CERT = Path("/etc/ssl/certs/es/ca.crt")


class Config(BaseSettings):
    DEPLOYMENT: str = "local"

    #############
    ## BACKEND ##
    #############

    KRONOS_URL: AnyUrl = "http://kronos"
    KRONOS_API_KEY: SecretStr
    KRONOS_LOG_FORMAT: LogFormat = LogFormat.plain
    KRONOS_LOG_LEVEL: str = "DEBUG"
    KRONOS_PORT: int = Field(9625, alias="KRONOS_CONTAINER_PORT")
    KRONOS_VERSION: str = "latest"

    MAESTRO_URL: AnyUrl = "http://maestro"
    MAESTRO_API_KEY: SecretStr
    MAESTRO_LOG_FORMAT: LogFormat = LogFormat.plain
    MAESTRO_LOG_LEVEL: str = "DEBUG"
    MAESTRO_PORT: int = Field(8020, alias="MAESTRO_CONTAINER_PORT")
    MAESTRO_VERSION: str = "latest"

    RAGNAROK_URL: AnyUrl = "http://ragnarok"
    RAGNAROK_API_KEY: SecretStr
    RAGNAROK_LOG_FORMAT: LogFormat = LogFormat.plain
    RAGNAROK_LOG_LEVEL: str = "DEBUG"
    RAGNAROK_PORT: int = Field(9696, alias="RAGNAROK_CONTAINER_PORT")
    RAGNAROK_VERSION: str = "latest"

    ##############
    ## FRONTEND ##
    ##############

    PACKAGE_REGISTRY_PROJECT_ID: int = 60777891
    PACKAGE_REGISTRY_TOKEN: SecretStr

    ADMIN_CONSOLE_PACKAGE_NAME: ClientName = ClientName.ADMIN
    ADMIN_CONSOLE_VERSION: str = "latest"

    INTERACTOR_PACKAGE_NAME: ClientName = ClientName.INTERACTOR
    INTERACTOR_VERSION: str = "latest"

    # Externally accessible backend/service URLs for use by the client apps
    KEYCLOAK_URL_EXTERNAL: AnyUrl = "http://localhost:8080"
    KRONOS_URL_EXTERNAL: AnyUrl = "http://localhost:9625"
    MAESTRO_URL_EXTERNAL: AnyUrl = "http://localhost:8020"
    RAGNAROK_URL_EXTERNAL: AnyUrl = "http://localhost:9696"

    # Settings for single-project clients (also used as defaults for multi-project clients)
    PROJECT_ID: str = "test"
    PROJECT_TITLE: str = "Test Project"

    ##############
    ## SERVICES ##
    ##############

    AZURE_BLOB_STORAGE_CONN_STR: SecretStr | None = None

    ES_URL: AnyUrl = "https://elasticsearch.elasticsearch.svc.cluster.local:9200"
    ES_USER: str = "elastic"
    ES_PASSWORD: SecretStr

    ES_INDEX_EMBEDDINGS: str = "ragnarok-develop-kb"
    ES_INDEX_HIGHLIGHT_CHUNKS: str = "ragnarok-develop-highlight-chunks"
    ES_INDEX_LOGS: str = "alquist-insight-develop-logs"
    ES_MAX_VECTOR_DIM: int = 4096

    KEYCLOAK_URL: AnyUrl | None = "http://keycloak.keycloak.svc.cluster.local:8080"
    KEYCLOAK_REALM: str = "alquist"
    KEYCLOAK_CLIENT_ID: str = "alquist-insight-development"

    MINIO_URL: AnyUrl = "http://minio.minio.svc.cluster.local:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: SecretStr | None = None

    MONGO_CONN_STR: SecretStr
    MONGO_DB_NAME_KRONOS: str = "kronos-develop"

    STORAGE_CONTAINER_NAME: str = "kronos-develop"
    STORAGE_PREFIX: str = ""
    STORAGE_TYPE: StorageType = Field(StorageType.MINIO, validate_default=True)

    TRITON_URL: AnyUrl | None = None

    # AI services
    COHERE_KEY: SecretStr | None = None
    JINAAI_KEY: SecretStr | None = None

    OPENAI_ENDPOINT: AnyUrl | None = None
    OPENAI_KEY: SecretStr | None = None
    OPENAI_TYPE: OpenAIType | None = None

    ##############################
    ## FEATURE FLAGS & SETTINGS ##
    ##############################

    # Flag to enable sending context (conversation history) to LLM
    CONTEXT_ENABLED: bool = True

    # Number of latest turns to use for context (0 for unlimited)
    CONTEXT_WINDOW_SIZE: int = 5

    # Flag for saving logs from all backend services to ElasticSearch
    ES_LOGGING_ENABLED: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(
            "/config/config.local.env",
            DIR_ROOT / "config.env",
            DIR_ROOT / "config.local.env",
        ),
        env_parse_none_str="None",
        extra="ignore",
        validate_assignment=True,
        validate_by_alias=True,
        validate_by_name=False,
    )

    @field_validator("KRONOS_LOG_LEVEL", "MAESTRO_LOG_LEVEL", "RAGNAROK_LOG_LEVEL")
    @classmethod
    def upper_str(cls, v: str) -> str:
        return v.upper()

    @field_validator("OPENAI_TYPE")
    @classmethod
    def check_openai_config(cls, openai_type: OpenAIType | None, info: ValidationInfo) -> OpenAIType | None:
        if openai_type == OpenAIType.AzureOpenAI:
            required = ("OPENAI_ENDPOINT", "OPENAI_KEY")
        elif openai_type == OpenAIType.OpenAI:
            required = ("OPENAI_KEY",)
        else:
            return None

        for v in required:
            if not info.data.get(v):
                raise ValueError(f"{v} is required for OpenAI type {openai_type.value}")

        return openai_type

    @field_validator("STORAGE_TYPE")
    @classmethod
    def check_storage_config(cls, storage_type: StorageType, info: ValidationInfo) -> StorageType:
        if storage_type == StorageType.AZURE_BLOB_STORAGE:
            required = ("AZURE_BLOB_STORAGE_CONN_STR",)
        elif storage_type == StorageType.MINIO:
            required = ("MINIO_URL", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
        else:
            raise ValueError(f"Unsupported storage type {storage_type.value}")

        for v in required:
            if not info.data.get(v):
                raise ValueError(f"{v} is required for storage type {storage_type.value}")

        return storage_type


# noinspection PyArgumentList
CONFIG = Config()
