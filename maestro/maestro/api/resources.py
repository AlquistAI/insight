# -*- coding: utf-8 -*-
"""
    maestro.api.resources
    ~~~~~~~~~~~~~~~~~~~~~

    Endpoints for fetching resources and general communication with Kronos.
"""

from typing import Any

from fastapi import status
from fastapi.responses import Response
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models.enums import ResourceType, SourceType
from common.models.project import Project
from common.utils.api import error_handler_async
from maestro.services import kronos

logger = get_component_logger()
router = APIRouter()


@router.get(
    "/projects/{project_id}/",
    response_model=Project,
    status_code=status.HTTP_200_OK,
    summary="Get project information",
)
@error_handler_async
async def get_project(project_id: str) -> Project:
    """
    Get project information.

    :param project_id: project ID
    :return: project info
    """

    logger.info("Fetching project info")
    return await kronos.get_project(project_id=project_id)


@router.get(
    "/projects/{project_id}/knowledge_base/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get knowledge base info for a project",
)
@error_handler_async
async def get_project_kb(project_id: str):
    """
    Get knowledge base info for a project.

    :param project_id: project ID
    :return: knowledge base info
    """

    logger.info("Fetching knowledge base")
    return {"data": await kronos.get_kb(project_id=project_id)}


@router.get(
    "/resources/{resource_type}/",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get resource file based on resource type",
)
@error_handler_async
async def get_resource(
        resource_type: ResourceType,
        resource_id: str = "",
        project_id: str = "",
        source_type: SourceType | None = None,

        # DEPRECATED! ToDo: Remove.
        kb_id: str = "",
        filename: str = "",
) -> Response:
    """
    Get resource file based on resource type.

    Available resource types:
      - chatbot_html - HTML source for chatbot
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

      - source_file - DEPRECATED! Use kb_source instead!

    The files are searched in the storage in this order:
      - resource specific (resource folder)
      - project specific (project folder)
      - default file (kronos folder)

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type (use None for original file)
    :param kb_id: DEPRECATED! Use resource_id instead!
    :param filename: DEPRECATED! Use resource_id instead!
    :return: content of the resource file
    """

    resource_type = ResourceType.SOURCE_KB if resource_type == ResourceType.SOURCE_FILE else resource_type
    resource_id = resource_id or kb_id or filename

    content, mimetype = await kronos.get_resource(
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        source_type=source_type,
    )

    return Response(content=content, media_type=mimetype, status_code=status.HTTP_200_OK)
