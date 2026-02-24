# -*- coding: utf-8 -*-
"""
    kronos.api.resources
    ~~~~~~~~~~~~~~~~~~~~

    Endpoints for managing resources (files) in the storage.
"""

import json

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from fastapi.routing import APIRouter

from common.models import api as ma, api_kronos as mak
from common.models.enums import RESOURCE_TO_MIME, ResourceType, SOURCE_TO_MIME, SourceType
from common.utils import exceptions as exc
from common.utils.api import error_handler
from kronos.api import knowledge_base as kb_api
from kronos.services.storage import get_storage
from kronos.services.storage.base import DIR_PROJECT, get_resource_dir, get_resource_fn, get_resource_paths

router = APIRouter()
storage = get_storage()


@router.get(
    "/",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="Get a list of stored resources",
)
@error_handler
def list_resources(
        resource_type: ResourceType | None = None,
        resource_id: str | None = None,
        project_id: str | None = None,
) -> list[str]:
    """
    Get a list of stored resources.

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID -> return project-specific resources
    :return: list of resource paths
    """

    if resource_type == ResourceType.IMAGE:
        # Images are in a single folder and are not project specific -> return
        return storage.list_files(prefix=get_resource_dir(resource_type=ResourceType.IMAGE))

    if resource_id and not project_id:
        # All resources with ID are part of a project
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You need to pass project_id together with resource_id")

    if resource_id and project_id:
        # Only documents and KB have their own ID -> check their locations
        dir_doc = get_resource_dir(ResourceType.SOURCE_DOCUMENT, resource_id=resource_id, project_id=project_id)
        dir_kb = get_resource_dir(ResourceType.SOURCE_KB, resource_id=resource_id, project_id=project_id)
        res = storage.list_files(prefix=dir_kb) or storage.list_files(prefix=dir_doc)

    elif project_id:
        # Check all project resources
        res = storage.list_files(prefix=DIR_PROJECT.format(project_id=project_id))

    else:
        # Check all resources
        res = storage.list_files()

    if resource_type is None:
        # No specific resource type requested -> return everything found
        return res

    fn = get_resource_fn(resource_type=resource_type, resource_id=resource_id, source_type=SourceType.PDF)

    if resource_type in (ResourceType.SOURCE_DOCUMENT, ResourceType.SOURCE_KB):
        # Source files can be in different locations and have various extensions
        fn = fn.removesuffix(f".{SourceType.PDF.value}")
        substring = "/documents/" if resource_type == ResourceType.SOURCE_DOCUMENT else "/knowledge_base/"
        return [x for x in res if substring in x and x.rsplit(".", 1)[0].endswith(fn)]

    # Filter based on filename
    return [x for x in res if x.endswith(fn)]


@router.get(
    "/{resource_type}/",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get resource file based on resource type",
)
@error_handler
def get_resource(
        resource_type: ResourceType,
        resource_id: str | None = None,
        project_id: str | None = None,
        source_type: SourceType | None = None,
) -> Response:
    """
    Get resource file based on resource type.

    Available resource types:
      - chatbot_html - HTML source for chatbot
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The files are searched in the storage in this order:
      - resource specific (resource folder)
      - project specific (project folder)
      - default file (kronos folder)

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type (use None for original file)
    :return: content of the resource file
    """

    if resource_type == ResourceType.SOURCE_KB:
        return kb_api.get_kb_source(project_id=project_id, kb_id=resource_id, source_type=source_type)

    paths = get_resource_paths(
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        source_type=source_type,
    )

    content = None
    for path in paths:
        try:
            content = storage.get_file(file_path=path)
            break
        except exc.ResourceNotFound:
            continue

    if not content:
        raise exc.ResourceNotFound(resource_id=paths[-1])

    mimetype = RESOURCE_TO_MIME[resource_type] or SOURCE_TO_MIME.get(source_type) or "application/octet-stream"
    return Response(content=content, status_code=status.HTTP_200_OK, media_type=mimetype)


@router.post(
    "/{resource_type}/",
    status_code=status.HTTP_201_CREATED,
    summary="Create/replace a resource file in storage",
)
@error_handler
def post_resource(
        file: UploadFile,
        resource_type: ResourceType,
        resource_id: str | None = None,
        project_id: str | None = None,
        source_type: SourceType | None = None,
) -> str:
    """
    Create/replace a resource file in storage.

    Available resource types:
      - chatbot_html - HTML source for chatbot
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The file is placed based on the passed IDs:
      - project_id & resource_id passed -> placed in resource-specific location
      - project_id passed -> placed in project-specific location
      - no ID passed -> replaces the default file

    :param file: file to upload
    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type
    :return: storage file path
    """

    file_path = get_resource_paths(
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        source_type=source_type,
    )[0]

    storage.post_file(file_path=file_path, content=file.file.read())
    return file_path


@router.post(
    "/{resource_type}/init",
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a project resource based on the default one",
)
@error_handler
def init_resource(
        resource_type: ResourceType,
        project_id: str,
        payload: mak.ResourceInit,
) -> str:
    """
    Initialize a project resource based on the default one.

    Uses the parameters defined in payload to update the default resource.
    If there are no changes defined, the resource will not be created and the default one will be used instead.

    Currently only supports the `dialogue_fsm` resource type.

    :param resource_type: resource type
    :param project_id: project ID
    :param payload: payload with parameters to update in the default resource
    :return: storage file path
    """

    if resource_type != ResourceType.DIALOGUE_FSM:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Resource type {resource_type.value} not supported")

    path_default = get_resource_paths(resource_type=resource_type)[0]
    content = storage.get_file(file_path=path_default)

    if updated := _init_dialogue_fsm(content=content, updates=payload):
        file_path = get_resource_paths(resource_type=resource_type, project_id=project_id)[0]
        storage.post_file(file_path=file_path, content=updated)
        return file_path

    return path_default


@router.delete(
    "/{resource_type}/",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Remove a resource file from storage",
)
@error_handler
def delete_resource(
        resource_type: ResourceType,
        resource_id: str | None = None,
        project_id: str | None = None,
        source_type: SourceType = SourceType.PDF,
) -> ma.DeletedCount:
    """
    Remove a resource file from storage.

    Available resource types:
      - chatbot_html - HTML source for chatbot
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The file to remove is chosen based on the passed IDs:
      - project_id & resource_id passed -> file in resource-specific location
      - project_id passed -> project-specific resource
      - no ID passed -> removes the default resource file

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type
    :return: deleted count
    """

    file_path = get_resource_paths(
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        source_type=source_type,
    )[0]

    return ma.DeletedCount(deleted_storage_blobs=storage.delete_file(file_path=file_path))


def _init_dialogue_fsm(content: bytes, updates: mak.ResourceInit) -> bytes | None:
    """Initialize default FSM JSON with the provided values."""

    data = json.loads(content)
    states = data.get("states", [])
    updated = False

    if updates.chatbot:
        data["chatbot"] = updates.chatbot.model_dump()
        updated = True

    if updates.image_url and (state := next((s for s in states if s["state_id"] == updates.image_url_state_id), None)):
        state["command"]["text"] = updates.image_url
        updated = True

    if updates.message and (state := next((s for s in states if s["state_id"] == updates.message_state_id), None)):
        state["command"]["text"] = updates.message
        updated = True

    return json.dumps(data, indent=2).encode("utf-8") if updated else None
