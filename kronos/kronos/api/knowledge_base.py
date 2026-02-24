# -*- coding: utf-8 -*-
"""
    kronos.api.knowledge_base
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Knowledge base / data management endpoints.
"""

import hashlib
import io
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import status
from fastapi.datastructures import Headers, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api as ma, api_ragnarok as mar, defaults as df
from common.models.enums import MIME_TO_SOURCE, ModelProvider, ResourceType, SOURCE_TO_MIME, SourceType
from common.models.knowledge_base import KnowledgeBase
from common.models.project import EmbeddingModelSettings
from common.utils.api import encode_header_string, error_handler
from kronos.services import ragnarok
from kronos.services.crawler import CrawlOptions, Crawler
from kronos.services.db.mongo import knowledge_base as db_kb, projects as db_projects
from kronos.services.storage import get_storage
from kronos.services.storage.base import get_resource_dir, get_resource_paths

logger = get_component_logger()
router = APIRouter()
storage = get_storage()


@router.get(
    "/",
    response_model=ma.PaginatedKnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="List general info for knowledge bases",
)
@error_handler
def list_kb(
        project_id: str | None = None,
        embedding_model: str | None = None,
        language: str | None = None,
        source_type: SourceType | None = None,
        fields: str = "",
        sort_by: str = "",
        page_no: int = 1,
        per_page: int = 10,
) -> ma.PaginatedKnowledgeBase | JSONResponse:
    """
    List general info for knowledge bases.

    :param project_id: project ID
    :param embedding_model: embedding model name
    :param language: content language
    :param source_type: source type
    :param fields: field names in DB to include using projection (as CSV)
    :param sort_by: field name to sort by (for descending order user prefix "-")
    :param page_no: [pagination] page number
    :param per_page: [pagination] results per page (use 0 for no pagination)
    :return: list of knowledge base data
    """

    fields = {x.strip() for x in fields.split(",")} if fields else None

    data, total = db_kb.list_kb(
        project_id=project_id,
        embedding_model=embedding_model,
        language=language,
        source_type=source_type,
        fields=fields,
        sort_by=sort_by,
        page_no=page_no,
        per_page=per_page,
    )

    pagination = ma.Pagination(page_no=page_no, per_page=per_page, total=total) if per_page > 0 else None

    if fields:
        return JSONResponse(ma.PaginationBaseModel(data=data, pagination=pagination).model_dump(mode="json"))
    return ma.PaginatedKnowledgeBase(data=data, pagination=pagination)


@router.get(
    "/{kb_id}/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge base data",
)
@error_handler
def get_kb(kb_id: str) -> KnowledgeBase:
    """
    Get knowledge base data.

    :param kb_id: knowledge base ID
    :return: knowledge base data
    """

    return db_kb.get_kb(kb_id=kb_id)


@router.get(
    "/{kb_id}/source",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get the KB source file",
)
@error_handler
def get_kb_source(kb_id: str, project_id: str, source_type: SourceType | None = None) -> Response:
    """
    Get the KB source file.

    :param kb_id: knowledge base ID
    :param project_id: project ID
    :param source_type: file source type (use None for original file)
    :return: knowledge base source content
    """

    kb_data = db_kb.get_kb(kb_id=kb_id, fields={"source_file", "source_type"})
    source_type = source_type or SourceType(kb_data["source_type"])

    file_path = get_resource_paths(
        resource_type=ResourceType.SOURCE_KB,
        resource_id=kb_id,
        project_id=project_id,
        source_type=source_type,
    )[0]

    return Response(
        content=storage.get_file(file_path=file_path),
        status_code=status.HTTP_200_OK,
        media_type=SOURCE_TO_MIME[source_type],
        headers={"X-Source-File": encode_header_string(kb_data["source_file"])},
    )


@router.post(
    "/file/",
    response_model=KnowledgeBase,
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
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_provider: ModelProvider = df.PROVIDER_EMB,
        model_name: str = df.MODEL_EMB,
        model_base_url: str = "",
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> KnowledgeBase:
    """
    Upload file as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    :param file: uploaded file
    :param kb_id: knowledge base ID (random generated if empty)
    :param project_id: project ID
    :param source_file: source file name (path)
    :param source_type: input file source type
    :param name: knowledge base name
    :param description: knowledge base description
    :param language: text language
    :param model_provider: embedding model provider
    :param model_name: embedding model name
    :param model_base_url: custom base URL to use for the embedding model
    :param custom_metadata: custom metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base data
    """

    db_projects.check_project_exists(project_id=project_id)

    data = KnowledgeBase(
        _id=kb_id,
        project_id=project_id,
        name=name,
        description=description,
        language=language,
        source_file=source_file or file.filename,
        source_type=source_type,
        enable_highlights=enable_highlights,
    )

    model_settings = EmbeddingModelSettings(
        provider=model_provider,
        name=model_name,
        base_url=model_base_url,
    )

    metadata = ragnarok.upload_file_kb(
        file=file.file,
        kb_id=data.id,
        project_id=project_id,
        source_file=data.source_file,
        source_type=data.source_type,
        language=language,
        model_settings=model_settings,
        custom_metadata=custom_metadata,
        enable_highlights=enable_highlights,
    )

    data.custom_metadata = metadata.custom
    data.embedding_model = metadata.embedding_model
    data.total_pages = metadata.total_pages

    file.file.seek(0)
    file_path = get_resource_paths(
        resource_type=ResourceType.SOURCE_KB,
        resource_id=data.id,
        project_id=project_id,
        source_type=source_type,
    )[0]
    storage.post_file(file_path=file_path, content=file.file.read())

    db_kb.delete_kb(kb_id=data.id, raise_not_found=False)
    db_kb.create_kb(data=data)
    return db_kb.get_kb(kb_id=data.id)


@router.post(
    "/file/bulk",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_201_CREATED,
    summary="Upload files as knowledge base in bulk",
)
@error_handler
def upload_file_kb_bulk(
        files: list[UploadFile],
        project_id: str = "",
        source_path: str = "",
        source_type: SourceType = SourceType.PDF,
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_provider: ModelProvider = df.PROVIDER_EMB,
        model_name: str = df.MODEL_EMB,
        model_base_url: str = "",
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> list[KnowledgeBase]:
    """
    Upload files as knowledge base in bulk.

    :param files: uploaded files
    :param project_id: project ID
    :param source_path: used as a prefix for source_file - source_file = 'source_path/filename'
    :param source_type: input files source type
    :param name: knowledge base name
    :param description: knowledge base description
    :param language: text language
    :param model_provider: embedding model provider
    :param model_name: embedding model name
    :param model_base_url: custom base URL to use for the embedding model
    :param custom_metadata: custom metadata used to update the default metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base data
    """

    source_path = Path(source_path) if source_path else None

    return [
        upload_file_kb(
            file=file,
            project_id=project_id,
            source_file=str(source_path / file.filename) if source_path else None,
            source_type=source_type,
            name=name,
            description=description,
            language=language,
            model_provider=model_provider,
            model_name=model_name,
            model_base_url=model_base_url,
            custom_metadata=custom_metadata,
            enable_highlights=enable_highlights,
        )
        for file in files
    ]


@router.post(
    "/url/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_201_CREATED,
    summary="Upload URL content as knowledge base",
)
@error_handler
def upload_url_kb(
        url: str,
        kb_id: str = "",
        project_id: str = "",
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_settings: EmbeddingModelSettings | None = None,
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> KnowledgeBase:
    """
    Upload URL content as knowledge base.

    If a knowledge base with the same ID exists, it gets overwritten.

    :param url: input URL
    :param kb_id: knowledge base ID (random generated if empty)
    :param project_id: project ID
    :param name: knowledge base name
    :param description: knowledge base description
    :param language: text language
    :param model_settings: embedding model settings
    :param custom_metadata: custom metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base data
    """

    model_settings = model_settings or EmbeddingModelSettings()
    content = io.BytesIO(requests.get(url, timeout=(10, 30)).content)
    headers = Headers({"Content-Type": SOURCE_TO_MIME[SourceType.HTML]})
    file = UploadFile(file=content, filename="from_url.html", headers=headers)

    return upload_file_kb(
        file=file,
        kb_id=kb_id,
        project_id=project_id,
        source_file=url,
        source_type=SourceType.HTML,
        name=name,
        description=description,
        language=language,
        model_provider=model_settings.provider,
        model_name=model_settings.name,
        model_base_url=model_settings.base_url,
        custom_metadata=custom_metadata,
        enable_highlights=enable_highlights,
    )


@router.post(
    "/url/bulk",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_201_CREATED,
    summary="Upload URLs content as knowledge base in bulk",
)
@error_handler
def upload_url_kb_bulk(
        urls: list[str],
        project_id: str = "",
        name: str = "",
        description: str = "",
        language: str = df.LANG,
        model_provider: ModelProvider = df.PROVIDER_EMB,
        model_name: str = df.MODEL_EMB,
        model_base_url: str = "",
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> list[KnowledgeBase]:
    """
    Upload URLs content as knowledge base in bulk.

    :param urls: input URLs
    :param project_id: project ID
    :param name: knowledge base name
    :param description: knowledge base description
    :param language: text language
    :param model_provider: embedding model provider
    :param model_name: embedding model name
    :param model_base_url: custom base URL to use for the embedding model
    :param custom_metadata: custom metadata (as json string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base data
    """

    model_settings = EmbeddingModelSettings(
        provider=model_provider,
        name=model_name,
        base_url=model_base_url,
    )

    return [
        upload_url_kb(
            url=url,
            project_id=project_id,
            name=name,
            description=description,
            language=language,
            model_settings=model_settings,
            custom_metadata=custom_metadata,
            enable_highlights=enable_highlights,
        )
        for url in urls
    ]


@router.post(
    "/url/crawl",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_201_CREATED,
    summary="Crawl URL and upload all discovered links as KB",
)
@error_handler
def upload_url_kb_crawl(
        url: str,
        project_id: str = "",
        language: str = df.LANG,
        model_provider: ModelProvider = df.PROVIDER_EMB,
        model_name: str = df.MODEL_EMB,
        model_base_url: str = "",
        enable_highlights: bool = False,
        idempotent_ids: bool = True,
        dry_run: bool = False,
        opts: CrawlOptions | None = None,
) -> list[KnowledgeBase]:
    """
    Crawl URL and upload all discovered websites/files as knowledge base.

    :param url: input URL (crawling seed URL)
    :param project_id: project ID
    :param language: text language
    :param model_provider: embedding model provider
    :param model_name: embedding model name
    :param model_base_url: custom base URL to use for the embedding model
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :param idempotent_ids: use deterministic KB IDs based on discovered URLs
    :param dry_run: skip saving anything as knowledge base - only output discovered links
    :param opts: crawling options payload
    :return: created knowledge base data
    """

    if not dry_run:
        db_projects.check_project_exists(project_id=project_id)

    crawler = Crawler(start_url=url, opts=opts)
    out: list[KnowledgeBase] = []

    for s in crawler.crawl():
        try:
            kb_id = _stable_kb_id_for_url(project_id=project_id, url=s.url_final) if idempotent_ids else ""

            if dry_run:
                out.append(
                    KnowledgeBase(
                        _id=kb_id,
                        project_id=project_id,
                        name=s.title or os.path.basename(urlparse(s.url_final).path),
                        embedding_model=model_name,
                        language=language,
                        source_file=s.url_final,
                        source_type=MIME_TO_SOURCE[s.mimetype],
                        enable_highlights=enable_highlights,
                    ),
                )
                continue

            content = io.BytesIO(s.content)
            headers = Headers({"Content-Type": s.mimetype})
            file = UploadFile(file=content, filename="from_url.bin", headers=headers)

            out.append(
                upload_file_kb(
                    file=file,
                    kb_id=kb_id,
                    project_id=project_id,
                    source_file=s.url_final,
                    source_type=MIME_TO_SOURCE[s.mimetype],
                    name=s.title or os.path.basename(urlparse(s.url_final).path),
                    language=language,
                    model_provider=model_provider,
                    model_name=model_name,
                    model_base_url=model_base_url,
                    enable_highlights=enable_highlights,
                ),
            )

        except Exception as e:
            logger.error("Failed to upload scraped KB -> skipping URL %s: %s", s.url_final, e)
            continue

    return out


@router.put(
    "/{kb_id}/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_200_OK,
    summary="Update an existing knowledge base",
)
@error_handler
def update_kb(kb_id: str, data: KnowledgeBase) -> KnowledgeBase:
    """
    Update an existing knowledge base.

    :param kb_id: knowledge base ID
    :param data: knowledge base data for update
    :return: updated knowledge base data
    """

    data_updated = data.model_dump(exclude_unset=True)
    data_updated["custom"] = data_updated.pop("custom_metadata", {})
    ragnarok.update_kb_metadata(kb_id=kb_id, metadata=mar.KBMetadataUpdate.model_validate(data_updated))

    data.id = kb_id
    db_kb.update_kb(data=data)
    return db_kb.get_kb(kb_id=kb_id)


@router.put(
    "/bulk",
    response_model=list[KnowledgeBase],
    status_code=status.HTTP_200_OK,
    summary="Update existing knowledge base in bulk",
)
@error_handler
def update_kb_bulk(data: list[KnowledgeBase]) -> list[KnowledgeBase]:
    """
    Update existing knowledge base in bulk.

    ToDo: Use bulk update in DB instead of a for cycle.

    :param data: list of knowledge base data for update
    :return: updated knowledge base data
    """

    return [update_kb(kb_id=d.id, data=d) for d in data]


@router.delete(
    "/{kb_id}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base",
)
@error_handler
def delete_kb(kb_id: str, project_id: str) -> ma.DeletedCount:
    """
    Delete knowledge base and all its data.

    :param kb_id: knowledge base ID
    :param project_id: project ID
    :return: deleted count
    """

    deleted = ragnarok.delete_kb(kb_id=kb_id)
    deleted.deleted_db_knowledge_base = db_kb.delete_kb(kb_id=kb_id)
    deleted.deleted_storage_blobs = storage.delete_folder(
        folder_path=get_resource_dir(resource_type=ResourceType.SOURCE_KB, resource_id=kb_id, project_id=project_id),
    )
    return deleted


@router.delete(
    "/bulk",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Delete knowledge base in bulk",
)
@error_handler
def delete_kb_bulk(kb_ids: list[str], project_id: str) -> ma.DeletedCount:
    """
    Delete knowledge base and all its data in bulk.

    ToDo: Use bulk delete wherever possible instead of a for cycle.

    :param kb_ids: knowledge base IDs to delete
    :param project_id: project ID
    :return: deleted count
    """

    deleted = ma.DeletedCount()

    for kb_id in kb_ids:
        deleted_tmp = delete_kb(kb_id=kb_id, project_id=project_id)
        deleted.deleted_db_knowledge_base += deleted_tmp.deleted_db_knowledge_base
        deleted.deleted_es_chunks += deleted_tmp.deleted_es_chunks
        deleted.deleted_es_chunks_highlight += deleted_tmp.deleted_es_chunks_highlight
        deleted.deleted_storage_blobs += deleted_tmp.deleted_storage_blobs

    return deleted


def _stable_kb_id_for_url(project_id: str, url: str) -> str:
    """
    Get a stable knowledge base ID for a given URL.

    :param project_id: project ID (so that the KB ID differs per project)
    :param url: input URL
    :return: stable knowledge base ID
    """

    inp = f"{project_id}_{url}"
    return hashlib.sha1(inp.encode("utf-8", errors="ignore")).hexdigest()
