# -*- coding: utf-8 -*-
"""
    kronos.api.deprecated
    ~~~~~~~~~~~~~~~~~~~~~

    Deprecated / unused endpoints that should eventually be removed.
"""

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api as ma, defaults as df
from common.models.enums import ResourceType, SourceType
from common.models.knowledge_base import KnowledgeBase
from common.utils.api import error_handler
from kronos.api import knowledge_base as api_kb, resources as api_resources

logger = get_component_logger()
router = APIRouter()


@router.get(
    "/projects/{project_id}/knowledge_base/",
    response_model=ma.PaginatedKnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="List general info for project knowledge bases",
    tags=["knowledge base"],
)
@error_handler
def list_kb(
        project_id: str,
        embedding_model: str | None = None,
        language: str | None = None,
        source_type: SourceType | None = None,
        fields: str | None = None,
        sort_by: str = "",
        page_no: int = 1,
        per_page: int = 10,
) -> ma.PaginatedKnowledgeBase | JSONResponse:
    """
    List general info for project knowledge bases.

    DEPRECATED! Use `GET /knowledge_base/` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/", project_id)
    return api_kb.list_kb(
        project_id=project_id,
        embedding_model=embedding_model,
        language=language,
        source_type=source_type,
        fields=fields,
        sort_by=sort_by,
        page_no=page_no,
        per_page=per_page,
    )


@router.get(
    "/projects/{project_id}/knowledge_base/{kb_id}/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge base data",
    tags=["knowledge base"],
)
@error_handler
def get_kb(project_id: str, kb_id: str) -> KnowledgeBase:
    """
    Get knowledge base data.

    DEPRECATED! Use `GET /knowledge_base/{kb_id}/` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/%s/", project_id, kb_id)
    return api_kb.get_kb(kb_id=kb_id)


@router.get(
    "/projects/{project_id}/knowledge_base/{kb_id}/source",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get the KB source file",
    tags=["knowledge base"],
)
@error_handler
def get_kb_source(project_id: str, kb_id: str, source_type: SourceType | None = None) -> Response:
    """
    Get the KB source file.

    DEPRECATED! Use `GET /knowledge_base/{kb_id}/source` instead!
    """

    logger.warning("Deprecated endpoint called: GET /projects/%s/knowledge_base/%s/source", project_id, kb_id)
    return api_kb.get_kb_source(project_id=project_id, kb_id=kb_id, source_type=source_type)


@router.post(
    "/projects/{project_id}/knowledge_base/file/",
    response_model=KnowledgeBase,
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
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_name: str = df.MODEL_EMB,
        custom_metadata: str = "",
) -> KnowledgeBase:
    """
    Upload file as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    DEPRECATED! Use `POST /knowledge_base/{kb_id}/file/` instead!
    """

    logger.warning("Deprecated endpoint called: POST /projects/%s/knowledge_base/file/", project_id)
    return api_kb.upload_file_kb(
        file=file,
        project_id=project_id,
        kb_id=kb_id,
        source_file=source_file,
        source_type=source_type,
        name=name,
        description=description,
        language=language,
        model_name=model_name,
        custom_metadata=custom_metadata,
    )


@router.post(
    "/projects/{project_id}/knowledge_base/file/bulk",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_201_CREATED,
    summary="Upload files as knowledge base in bulk",
    tags=["knowledge base"],
)
@error_handler
def upload_file_kb_bulk(
        files: list[UploadFile],
        project_id: str,
        source_path: str = "",
        source_type: SourceType = SourceType.PDF,
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_name: str = df.MODEL_EMB,
        custom_metadata: str = "",
) -> list[KnowledgeBase]:
    """
    Upload files as knowledge base in bulk.

    DEPRECATED! Use `POST /knowledge_base/file/bulk` instead!
    """

    logger.warning("Deprecated endpoint called: POST /projects/%s/knowledge_base/file/bulk", project_id)
    return api_kb.upload_file_kb_bulk(
        files=files,
        project_id=project_id,
        source_path=source_path,
        source_type=source_type,
        name=name,
        description=description,
        language=language,
        model_name=model_name,
        custom_metadata=custom_metadata,
    )


@router.put(
    "/projects/{project_id}/knowledge_base/{kb_id}/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="Update an existing knowledge base",
    tags=["knowledge base"],
)
@error_handler
def update_kb(project_id: str, kb_id: str, data: KnowledgeBase) -> KnowledgeBase:
    """
    Update an existing knowledge base.

    DEPRECATED! Use `PUT /knowledge_base/{kb_id}/` instead!
    """

    logger.warning("Deprecated endpoint called: PUT /projects/%s/knowledge_base/%s/", project_id, kb_id)
    return api_kb.update_kb(kb_id=kb_id, data=data)


@router.put(
    "/projects/{project_id}/knowledge_base/bulk",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_200_OK,
    summary="Update existing knowledge base in bulk",
    tags=["knowledge base"],
)
@error_handler
def update_kb_bulk(project_id: str, data: list[KnowledgeBase]) -> list[KnowledgeBase]:
    """
    Update existing knowledge base in bulk.

    DEPRECATED! Use `PUT /knowledge_base/bulk` instead!
    """

    logger.warning("Deprecated endpoint called: PUT /projects/%s/knowledge_base/bulk", project_id)
    return api_kb.update_kb_bulk(data=data)


@router.delete(
    "/projects/{project_id}/knowledge_base/{kb_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base",
    tags=["knowledge base"],
)
@error_handler
def delete_kb(project_id: str, kb_id: str) -> ma.DeletedCount:
    """
    Delete knowledge base and all its data.

    DEPRECATED! Use `DELETE /knowledge_base/{kb_id}/` instead!
    """

    logger.warning("Deprecated endpoint called: DELETE /projects/%s/knowledge_base/%s/", project_id, kb_id)
    return api_kb.delete_kb(project_id=project_id, kb_id=kb_id)


@router.delete(
    "/projects/{project_id}/knowledge_base/bulk",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base in bulk",
    tags=["knowledge base"],
)
@error_handler
def delete_kb_bulk(project_id: str, kb_ids: list[str]) -> ma.DeletedCount:
    """
    Delete knowledge base and all its data in bulk.

    DEPRECATED! Use `DELETE /knowledge_base/bulk` instead!
    """

    logger.warning("Deprecated endpoint called: DELETE /projects/%s/knowledge_base/bulk", project_id)
    return api_kb.delete_kb_bulk(project_id=project_id, kb_ids=kb_ids)


@router.get(
    "/resources/{resource_type}",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get resource file based on resource type",
    tags=["resources"],
)
@error_handler
def get_resource(
        resource_type: ResourceType,
        project_id: str | None = None,
        kb_id: str | None = None,
        filename: str = "",
        source_type: SourceType | None = None,
) -> Response:
    """
    Get resource file based on resource type.

    DEPRECATED! Use `GET /resources/{resource_type}/` instead!
    """

    logger.warning("Deprecated endpoint called: GET /resources/%s", resource_type.value)
    return api_resources.get_resource(
        resource_type=ResourceType.SOURCE_KB if resource_type == ResourceType.SOURCE_FILE else resource_type,
        resource_id=kb_id or filename,
        project_id=project_id,
        source_type=source_type,
    )


@router.post(
    "/resources/{resource_type}",
    status_code=status.HTTP_201_CREATED,
    summary="Create/replace a resource file in storage",
    tags=["resources"],
)
@error_handler
def post_resource(
        file: UploadFile,
        resource_type: ResourceType,
        project_id: str | None = None,
        kb_id: str | None = None,
        source_type: SourceType | None = None,
) -> str:
    """
    Create/replace a resource file in storage.

    DEPRECATED! Use `POST /resources/{resource_type}/` instead!
    """

    logger.warning("Deprecated endpoint called: POST /resources/{resource_type}", resource_type.value)
    return api_resources.post_resource(
        file=file,
        resource_type=ResourceType.SOURCE_KB if resource_type == ResourceType.SOURCE_FILE else resource_type,
        resource_id=kb_id or file.filename,
        project_id=project_id,
        source_type=source_type,
    )


@router.delete(
    "/resources/{resource_type}",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Remove a resource file from storage",
    tags=["resources"],
)
@error_handler
def delete_resource(
        resource_type: ResourceType,
        project_id: str | None = None,
        kb_id: str | None = None,
        filename: str = "",
        source_type: SourceType = SourceType.PDF,
) -> ma.DeletedCount:
    """
    Remove a resource file from storage.

    DEPRECATED! Use `DELETE /resources/{resource_type}/` instead!
    """

    logger.warning("Deprecated endpoint called: DELETE /resources/{resource_type}", resource_type.value)
    return api_resources.delete_resource(
        resource_type=ResourceType.SOURCE_KB if resource_type == ResourceType.SOURCE_FILE else resource_type,
        resource_id=kb_id or filename,
        project_id=project_id,
        source_type=source_type,
    )
