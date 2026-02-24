# -*- coding: utf-8 -*-
"""
    kronos.services.ragnarok
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Ragnarok service utilities.
"""

from typing import BinaryIO, Generator

import httpx
import requests

from common.config import CONFIG
from common.models import api as ma, api_ragnarok as mar, defaults as df, elastic as me
from common.models.enums import SourceType
from common.models.project import EmbeddingModelSettings

RAGNAROK_URL = str(CONFIG.RAGNAROK_URL).rstrip("/")

HEADERS = {
    "accept": "application/json",
    "Authorization": CONFIG.RAGNAROK_API_KEY.get_secret_value(),
}


def upload_file_kb(
        file: BinaryIO,
        kb_id: str,
        project_id: str = "",
        source_file: str = "",
        source_type: SourceType = SourceType.PDF,
        language: str = df.LANG,
        model_settings: EmbeddingModelSettings | None = None,
        custom_metadata: str = "",
        enable_highlights: bool = False,
) -> me.KBMetadata:
    """
    Upload file to Ragnarok as knowledge base.

    :param file: file to upload
    :param kb_id: knowledge base ID
    :param project_id: project ID
    :param source_file: source file name (path)
    :param source_type: type/format of the content (e.g. pdf)
    :param language: content language
    :param model_settings: embedding model settings
    :param custom_metadata: custom metadata (as JSON string)
    :param enable_highlights: build and index chunks required for the highlighting functionality
    :return: created knowledge base metadata
    """

    model_settings = model_settings or EmbeddingModelSettings()

    res = requests.post(
        url=f"{RAGNAROK_URL}/knowledge_base/file",
        params={
            "kb_id": kb_id,
            "project_id": project_id,
            "source_file": source_file,
            "source_type": source_type,
            "language": language,
            "model_provider": model_settings.provider,
            "model_name": model_settings.name,
            "model_base_url": model_settings.base_url,
            "custom_metadata": custom_metadata,
            "enable_highlights": enable_highlights,
        },
        files={"file": file},
        headers=HEADERS,
        timeout=(5, 600),
    )

    res.raise_for_status()
    return me.KBMetadata.model_validate(res.json())


def update_kb_metadata(kb_id: str, metadata: mar.KBMetadataUpdate):
    """
    Update knowledge base metadata in Ragnarok.

    :param kb_id: knowledge base ID
    :param metadata: metadata to be updated
    """

    requests.put(
        url=f"{RAGNAROK_URL}/knowledge_base/{kb_id}/metadata",
        json=metadata.model_dump(exclude_unset=True),
        headers=HEADERS,
        timeout=(5, 10),
    ).raise_for_status()


def delete_kb(kb_id: str) -> ma.DeletedCount:
    """
    Delete knowledge base data from Ragnarok.

    :param kb_id: knowledge base ID
    :return: deleted count
    """

    res = requests.delete(
        url=f"{RAGNAROK_URL}/knowledge_base/{kb_id}/",
        headers=HEADERS,
        timeout=(5, 10),
    )

    res.raise_for_status()
    return ma.DeletedCount.model_validate(res.json())


def delete_project(project_id: str) -> ma.DeletedCount:
    """
    Delete project data from Ragnarok.

    :param project_id: project ID
    :return: deleted count
    """

    res = requests.delete(
        url=f"{RAGNAROK_URL}/projects/{project_id}/",
        headers=HEADERS,
        timeout=(5, 10),
    )

    res.raise_for_status()
    return ma.DeletedCount.model_validate(res.json())


async def query_rag(project_id: str, payload: mar.RAGPayload) -> mar.RAGResponse:
    """
    Get RAG response from Ragnarok.

    :param project_id: project ID
    :param payload: RAG payload
    :return: RAG response dict
    """

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=f"{RAGNAROK_URL}/projects/{project_id}/nlp/rag/",
            json=payload.model_dump(mode="json"),
            headers=HEADERS,
            timeout=httpx.Timeout(60, connect=5),
        )

    res.raise_for_status()
    return mar.RAGResponse.model_validate(res.json())


def query_rag_stream(project_id: str, payload: mar.RAGPayload) -> Generator[str, None, None]:
    """
    Get streamed RAG response from Ragnarok.

    :param project_id: project ID
    :param payload: RAG payload
    :return: streamed RAG response
    """

    headers = HEADERS.copy()
    del headers["accept"]

    res = requests.post(
        url=f"{RAGNAROK_URL}/projects/{project_id}/nlp/rag/stream",
        json=payload.model_dump(mode="json"),
        headers=headers,
        timeout=(5, 60),
        stream=True,
    )

    res.raise_for_status()

    for line in res.iter_lines():
        yield line.decode()
