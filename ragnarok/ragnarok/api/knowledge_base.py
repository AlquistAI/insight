# -*- coding: utf-8 -*-
"""
    ragnarok.api.knowledge_base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Knowledge base / data management endpoints.
"""

import json
import uuid

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.routing import APIRouter

from common.models import api as ma, api_ragnarok as mar, defaults as df, elastic as me
from common.models.enums import ModelProvider, SourceType
from common.models.project import EmbeddingModelSettings
from common.utils.api import error_handler
from ragnarok.vector_db import VectorStore

router = APIRouter()
VS = VectorStore()


@router.get(
    "/",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List knowledge base IDs",
)
@error_handler
def list_kb_ids(project_id: str = "") -> list[str]:
    """
    List knowledge base IDs.

    :param project_id: project ID
    :return: list of knowledge base IDs
    """

    return VS.get_kb_ids(project_id=project_id)


@router.get(
    "/{kb_id}/metadata",
    response_model=me.KBMetadata,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge base metadata",
)
@error_handler
def get_kb_metadata(kb_id: str, project_id: str = "") -> me.KBMetadata:
    """
    Get knowledge base metadata.

    :param kb_id: knowledge base ID
    :param project_id: project ID
    :return: knowledge base metadata
    """

    return VS.get_kb_metadata(kb_id=kb_id, project_id=project_id)


@router.put(
    "/{kb_id}/metadata",
    status_code=status.HTTP_200_OK,
    summary="Update knowledge base metadata",
)
@error_handler
def update_kb_metadata(kb_id: str, metadata: mar.KBMetadataUpdate, project_id: str = ""):
    """
    Update knowledge base metadata.

    Not all metadata fields can be safely updated.
    If you need to change anything else, delete & re-upload the knowledge with the new metadata.

    :param kb_id: knowledge base ID
    :param metadata: metadata to be updated
    :param project_id: project ID
    """

    VS.update_kb_metadata(kb_id=kb_id, metadata=metadata.model_dump(exclude_unset=True), project_id=project_id)


@router.get(
    "/{kb_id}/page",
    response_model=me.KBEntry,
    status_code=status.HTTP_200_OK,
    summary="Get data for one page of a knowledge base",
)
@error_handler
def get_kb_page(kb_id: str, page: int = 1, project_id: str = "") -> me.KBEntry:
    """
    Get data for one page of a knowledge base.

    :param kb_id: knowledge base ID
    :param page: page number
    :param project_id: project ID
    :return: data for one page
    """

    return VS.get_kb_page(kb_id=kb_id, page=page, project_id=project_id)


@router.post(
    "/file",
    response_model=me.KBMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file as knowledge base",
)
@error_handler
def upload_file_kb(
        file: UploadFile,
        kb_id: str = "",
        project_id: str = "",
        source_file: str = "",
        source_type: SourceType = SourceType.PDF,
        language: str = df.LANG,
        model_provider: ModelProvider = df.PROVIDER_EMB,
        model_name: str = df.MODEL_EMB,
        model_base_url: str = "",
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> me.KBMetadata:
    """
    Upload file as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    :param file: uploaded file
    :param kb_id: knowledge base ID (random generated if empty)
    :param project_id: project ID
    :param source_file: source file name (path)
    :param source_type: type/format of the content (e.g. pdf)
    :param language: text language
    :param model_provider: embedding model provider
    :param model_name: embedding model name
    :param model_base_url: custom base URL to use for the embedding model
    :param custom_metadata: custom metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base metadata
    """

    model_settings = EmbeddingModelSettings(
        provider=model_provider,
        name=model_name,
        base_url=model_base_url,
    )

    kb_id = kb_id or str(uuid.uuid4())
    content = file.file.read()

    if custom_metadata:
        custom_metadata = json.loads(custom_metadata)

    return VS.upload_file(
        content=content,
        kb_id=kb_id,
        project_id=project_id,
        source_file=source_file,
        source_type=source_type,
        language=language,
        emb_settings=model_settings,
        custom_metadata=custom_metadata,
        enable_highlights=enable_highlights,
    )


@router.post(
    "/url",
    response_model=me.KBMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload URL contents as knowledge base",
)
@error_handler
def upload_url_kb(
        url: str,
        kb_id: str = "",
        project_id: str = "",
        language: str = df.LANG,
        model_settings: EmbeddingModelSettings | None = None,
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> me.KBMetadata:
    """
    Upload URL contents as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    :param url: input URL
    :param kb_id: knowledge base ID (random generated if empty)
    :param project_id: project ID
    :param language: text language
    :param model_settings: embedding model settings
    :param custom_metadata: custom metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base metadata
    """

    kb_id = kb_id or str(uuid.uuid4())
    model_settings = model_settings or EmbeddingModelSettings()

    if custom_metadata:
        custom_metadata = json.loads(custom_metadata)

    return VS.upload_url(
        url=url,
        kb_id=kb_id,
        project_id=project_id,
        language=language,
        emb_settings=model_settings,
        custom_metadata=custom_metadata,
        enable_highlights=enable_highlights,
    )


@router.delete(
    "/{kb_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base data from vector DB",
)
@error_handler
def delete_kb(kb_id: str, project_id: str = "") -> ma.DeletedCount:
    """
    Delete knowledge base data from vector DB.

    :param kb_id: knowledge base ID
    :param project_id: project ID
    :return: deleted count
    """

    deleted, deleted_hl = VS.delete_kb(kb_id=kb_id, project_id=project_id, raise_not_found=False)
    return ma.DeletedCount(deleted_es_chunks=deleted, deleted_es_chunks_highlight=deleted_hl)
