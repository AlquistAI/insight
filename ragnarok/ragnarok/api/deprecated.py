# -*- coding: utf-8 -*-
"""
    ragnarok.api.deprecated
    ~~~~~~~~~~~~~~~~~~~~~~~

    Deprecated / unused endpoints that should eventually be removed.
"""

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api as ma, api_ragnarok as mar, defaults as df, elastic as me
from common.models.enums import SourceType
from common.utils.api import error_handler
from ragnarok.api import knowledge_base as api_kb

logger = get_component_logger()
router = APIRouter()


@router.get(
    "/projects/{project_id}/knowledge_base/",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List knowledge base IDs for a project",
    tags=["knowledge base"],
)
@error_handler
def list_kb_ids(project_id: str) -> list[str]:
    """
    List knowledge base IDs for a project.

    DEPRECATED! Use `GET /knowledge_base/` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/", project_id)
    return api_kb.list_kb_ids(project_id=project_id)


@router.get(
    "/projects/{project_id}/knowledge_base/{kb_id}/metadata",
    response_model=me.KBMetadata,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge base metadata",
    tags=["knowledge base"],
)
@error_handler
def get_kb_metadata(project_id: str, kb_id: str) -> me.KBMetadata:
    """
    Get knowledge base metadata.

    DEPRECATED! Use `GET /knowledge_base/{kb_id}/metadata` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/%s/metadata", project_id, kb_id)
    return api_kb.get_kb_metadata(kb_id=kb_id, project_id=project_id)


@router.put(
    "/projects/{project_id}/knowledge_base/{kb_id}/metadata",
    status_code=status.HTTP_200_OK,
    summary="Update knowledge base metadata",
    tags=["knowledge base"],
)
@error_handler
def update_kb_metadata(project_id: str, kb_id: str, metadata: mar.KBMetadataUpdate):
    """
    Update knowledge base metadata.

    Not all metadata fields can be safely updated.
    If you need to change anything else, delete & re-upload the knowledge with the new metadata.

    DEPRECATED! Use `PUT /knowledge_base/{kb_id}/metadata` instead!
    """

    logger.warning("Deprecated endpoint called: PUT /projects/%s/knowledge_base/%s/metadata", project_id, kb_id)
    return api_kb.update_kb_metadata(kb_id=kb_id, metadata=metadata, project_id=project_id)


@router.get(
    "/projects/{project_id}/knowledge_base/{kb_id}/page",
    response_model=me.KBEntry,
    status_code=status.HTTP_200_OK,
    summary="Get data for one page of a knowledge base",
    tags=["knowledge base"],
)
@error_handler
def get_kb_page(project_id: str, kb_id: str, page: int = 1) -> me.KBEntry:
    """
    Get data for one page of a knowledge base.

    DEPRECATED! Use `GET /knowledge_base/{kb_id}/page` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/%s/page", project_id, kb_id)
    return api_kb.get_kb_page(kb_id=kb_id, page=page, project_id=project_id)


@router.post(
    "/projects/{project_id}/knowledge_base/file",
    response_model=me.KBMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file as knowledge base",
    tags=["knowledge base"],
)
@error_handler
def upload_file_kb(
        file: UploadFile,
        project_id: str,
        kb_id: str = "",
        source_file: str = "",
        source_type: SourceType = SourceType.PDF,
        language: str = df.LANG,
        model_name: str = df.MODEL_EMB,
        custom_metadata: str = "",
) -> me.KBMetadata:
    """
    Upload file as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    DEPRECATED! Use `POST /knowledge_base/file` instead!
    """

    logger.warning("Deprecated endpoint called: POST /projects/%s/knowledge_base/file", project_id)
    return api_kb.upload_file_kb(
        file=file,
        kb_id=kb_id,
        project_id=project_id,
        source_file=source_file,
        source_type=source_type,
        language=language,
        model_name=model_name,
        custom_metadata=custom_metadata,
    )


@router.delete(
    "/projects/{project_id}/knowledge_base/{kb_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base data from vector DB",
    tags=["knowledge base"],
)
@error_handler
def delete_kb(project_id: str, kb_id: str) -> ma.DeletedCount:
    """
    Delete knowledge base data from vector DB.

    DEPRECATED! Use `DELETE /knowledge_base/{kb_id}/` instead!
    """

    logger.warning("Deprecated endpoint called: DELETE /projects/%s/knowledge_base/%s/", project_id, kb_id)
    return api_kb.delete_kb(kb_id=kb_id, project_id=project_id)
