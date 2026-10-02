# -*- coding: utf-8 -*-
"""
    kronos.api.resources
    ~~~~~~~~~~~~~~~~~~~~

    Endpoints for managing resources (files) in the storage.
"""

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from fastapi.routing import APIRouter

from common.core import get_component_logger
from common.models import api as ma
from common.models.enums import RESOURCE_TO_MIME, ResourceType, SOURCE_TO_MIME, SourceType
from common.models.fsm import DialogueInit
from common.utils import exceptions as exc, fsm as u_fsm
from common.utils.api import error_handler
from common.utils.prompts import parse_prompts
from kronos.api import knowledge_base as kb_api
from kronos.services.db.mongo import projects as db_projects
from kronos.services.storage import base as s_base, get_storage

logger = get_component_logger()
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
        # Images are in a separate folder - project-specific one if a project ID is passed, the default one otherwise
        dir_images = s_base.get_resource_dir(resource_type=ResourceType.IMAGE, project_id=project_id)
        return storage.list_files(prefix=dir_images or s_base.DIR_IMAGES)

    if resource_id and not project_id:
        # All resources with ID are part of a project
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You need to pass project_id together with resource_id")

    if resource_id and project_id:
        # Only documents and KB have their own ID -> check their locations
        dir_doc = s_base.get_resource_dir(ResourceType.SOURCE_DOCUMENT, resource_id=resource_id, project_id=project_id)
        dir_kb = s_base.get_resource_dir(ResourceType.SOURCE_KB, resource_id=resource_id, project_id=project_id)
        res = storage.list_files(prefix=dir_kb) or storage.list_files(prefix=dir_doc)

    elif project_id:
        # Check all project resources
        res = storage.list_files(prefix=s_base.DIR_PROJECT.format(project_id=project_id))

    else:
        # Check all resources
        res = storage.list_files()

    if resource_type is None:
        # No specific resource type requested -> return everything found
        return res

    fn = s_base.get_resource_fn(resource_type=resource_type, resource_id=resource_id, source_type=SourceType.PDF)

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
        version: int | None = None,
) -> Response:
    """
    Get resource file based on resource type.

    Available resource types:
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource
      - prompts - Markdown file with the LLM prompts used in the project

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The files are searched in the storage in this order:
      - resource specific (resource folder)
      - project specific (project folder, `images` subfolder for images)
      - default file (kronos folder, `images` subfolder for images)

    A `version` can be requested for the versioned project resources (`dialogue_fsm`, `prompts`) - it returns
    an older version of the project-specific file instead of the live one, without any fallback.

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type (use None for original file)
    :param version: version of the resource file (use None for the live file)
    :return: content of the resource file
    """

    if resource_type == ResourceType.SOURCE_KB:
        return kb_api.get_kb_source(project_id=project_id, kb_id=resource_id, source_type=source_type)

    if version is not None:
        # Older versions live in the project folder under a versioned filename - no default fallback
        paths = [_get_version_path(resource_type=resource_type, project_id=project_id, version=version)]
    else:
        paths = s_base.get_resource_paths(
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
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource
      - prompts - Markdown file with the LLM prompts used in the project

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The file is placed based on the passed IDs:
      - project_id & resource_id passed -> placed in resource-specific location
      - project_id passed -> placed in project-specific location
      - no ID passed -> replaces the default file

    An `image` always requires resource_id (the image filename) - it is stored in the project-specific
    images folder if project_id is passed, otherwise it becomes a default (project independent) image.

    The content of a `prompts` file is validated before it is stored - it has to be parsable and define
    all the required prompts using exactly the template variables filled in during runtime.

    The project-specific `dialogue_fsm` and `prompts` files are versioned - the currently stored file is
    kept under a versioned filename (e.g. `dialogue-v5.json`) before it is replaced with the uploaded one.
    Uploading a file identical to the stored one is a no-op.

    :param file: file to upload
    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type
    :return: storage file path
    """

    file_path = s_base.get_resource_paths(
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        source_type=source_type,
    )[0]

    content = file.file.read()

    # Step 1: Validate the uploaded content
    if resource_type == ResourceType.PROMPTS:
        # Ensure that the uploaded prompts file can be parsed and defines all the required prompts
        parse_prompts(content=content)

    # Step 2: Keep the current version of a versioned resource, skip the upload if nothing changed
    if not _version_current_file(resource_type=resource_type, project_id=project_id, content=content):
        logger.info("The uploaded file is identical to the stored one: %s --> skipping", file_path)
        return file_path

    # Step 3: Store the uploaded file as the live version of the resource
    db_projects.touch_project(project_id=project_id)
    storage.post_file(file_path=file_path, content=content)
    return file_path


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
        version: int | None = None,
) -> ma.DeletedCount:
    """
    Remove a resource file from storage.

    Available resource types:
      - dialogue_fsm - FSM file specifying the dialogue
      - image - image file used as a static resource
      - prompts - Markdown file with the LLM prompts used in the project

      - document_source - source file for a document (requires project_id and resource_id)
      - kb_source - source file for a knowledge base (requires project_id and resource_id)

    The file to remove is chosen based on the passed IDs:
      - project_id & resource_id passed -> file in resource-specific location
      - project_id passed -> project-specific resource
      - no ID passed -> removes the default resource file

    An `image` always requires resource_id (the image filename) - the image is removed from the
    project-specific images folder if project_id is passed, from the default one otherwise.

    A `version` can be passed for the versioned project resources (`dialogue_fsm`, `prompts`) to remove
    an older version of the project-specific file instead of the live one. Removing the live file keeps
    its older versions in the storage - use the `history` endpoint to remove those.

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID
    :param source_type: source file type
    :param version: version of the resource file (use None for the live file)
    :return: deleted count
    """

    if version is not None:
        file_path = _get_version_path(resource_type=resource_type, project_id=project_id, version=version)
    else:
        file_path = s_base.get_resource_paths(
            resource_type=resource_type,
            resource_id=resource_id,
            project_id=project_id,
            source_type=source_type,
        )[0]

    db_projects.touch_project(project_id=project_id)
    return ma.DeletedCount(deleted_storage_blobs=storage.delete_file(file_path=file_path))


@router.get(
    "/{resource_type}/history",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="Get a list of the stored older versions of a project resource",
)
@error_handler
def list_resource_history(resource_type: ResourceType, project_id: str) -> list[str]:
    """
    Get a list of the stored older versions of a project resource.

    Only the project-specific `dialogue_fsm` and `prompts` files are versioned - the live file is not
    included in the listing, only its older versions (e.g. `dialogue-v5.json`), ordered by version.

    :param resource_type: type of the resource
    :param project_id: project ID
    :return: list of versioned resource paths
    """

    _check_versioning_supported(resource_type=resource_type, project_id=project_id)
    versions = _get_resource_versions(resource_type=resource_type, project_id=project_id)
    return [path for _, path in sorted(versions.items())]


@router.delete(
    "/{resource_type}/history",
    response_model=ma.DeletedCount,
    status_code=status.HTTP_200_OK,
    summary="Remove all the stored older versions of a project resource",
)
@error_handler
def delete_resource_history(resource_type: ResourceType, project_id: str) -> ma.DeletedCount:
    """
    Remove all the stored older versions of a project resource.

    Only the project-specific `dialogue_fsm` and `prompts` files are versioned - the live file is kept,
    only its older versions (e.g. `dialogue-v5.json`) are removed.

    :param resource_type: type of the resource
    :param project_id: project ID
    :return: deleted count
    """

    _check_versioning_supported(resource_type=resource_type, project_id=project_id)
    versions = _get_resource_versions(resource_type=resource_type, project_id=project_id)

    db_projects.touch_project(project_id=project_id)
    deleted = sum(storage.delete_file(file_path=path) for path in versions.values())
    return ma.DeletedCount(deleted_storage_blobs=deleted)


@router.post(
    f"/{ResourceType.DIALOGUE_FSM.value}/init",
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a dialogue FSM JSON",
)
@error_handler
def init_dialogue_fsm(project_id: str = "", payload: DialogueInit | None = None) -> str:
    """
    Initialize a dialogue FSM JSON.

    The currently stored project dialogue is kept under a versioned filename before it is replaced,
    the initialization is skipped if it results in exactly the same dialogue.

    :param project_id: project ID (overwrites default dialogue if empty)
    :param payload: payload with custom dialogue fields
    :return: storage file path
    """

    dialogue = u_fsm.build_qa(data=payload)
    dialogue = dialogue.model_dump_json(indent=2).encode("utf-8")

    file_path = s_base.get_resource_paths(resource_type=ResourceType.DIALOGUE_FSM, project_id=project_id)[0]

    if not _version_current_file(
            resource_type=ResourceType.DIALOGUE_FSM,
            project_id=project_id,
            content=dialogue,
    ):
        logger.info("The initialized dialogue is identical to the stored one: %s --> skipping", file_path)
        return file_path

    db_projects.touch_project(project_id=project_id)
    storage.post_file(file_path=file_path, content=dialogue)
    return file_path


def _version_current_file(resource_type: ResourceType, project_id: str | None, content: bytes) -> bool:
    """
    Keep the currently stored version of a project-specific resource file under a versioned filename.

    Only the resource types listed in `RESOURCES_VERSIONED` are versioned and only when they belong to
    a project - changes of the default (project independent) resource files are tracked in git. Nothing
    is stored when the resource has no live file yet or when its content did not change.

    :param resource_type: type of the resource
    :param project_id: project ID (default resource files are not versioned)
    :param content: content of the file that is being uploaded
    :return: whether the uploaded content differs from the currently stored one
    """

    if not project_id or resource_type not in s_base.RESOURCES_VERSIONED:
        return True

    file_path = s_base.get_resource_paths(resource_type=resource_type, project_id=project_id)[0]

    try:
        content_stored = storage.get_file(file_path=file_path)
    except exc.ResourceNotFound:
        return True  # there is no live file to keep yet

    if content_stored == content:
        return False

    versions = _get_resource_versions(resource_type=resource_type, project_id=project_id)
    version = max(versions, default=0) + 1

    path_versioned = s_base.get_resource_version_path(
        resource_type=resource_type,
        project_id=project_id,
        version=version,
    )

    storage.post_file(file_path=path_versioned, content=content_stored)
    logger.info("Previous version of %s stored as %s", file_path, path_versioned)
    return True


def _get_resource_versions(resource_type: ResourceType, project_id: str) -> dict[int, str]:
    """
    Get the older versions of a project-specific resource file stored in the project folder.

    The listing prefix already pins the project folder and the versioned filename stem, so only the
    version has to be parsed out of the matched filenames.

    :param resource_type: type of the resource (one of `RESOURCES_VERSIONED`)
    :param project_id: project ID
    :return: storage paths of the versioned resource files mapped to their versions
    """

    r_dir = s_base.get_resource_dir(resource_type=resource_type, project_id=project_id)
    prefix = s_base.get_resource_version_prefix(resource_type=resource_type, project_id=project_id)

    versions = {}
    for path in storage.list_files(prefix=prefix, as_folder=False):
        f_dir, _, f_name = path.rpartition("/")
        if f_dir != r_dir:
            continue  # skip anything nested deeper in the project folder

        if (version := s_base.parse_versioned_fn(filename=f_name)[1]) is not None:
            versions[version] = path

    return versions


def _get_version_path(resource_type: ResourceType, project_id: str | None, version: int) -> str:
    """
    Get the validated storage path of a specific older version of a project-specific resource file.

    :param resource_type: type of the resource
    :param project_id: project ID
    :param version: version of the resource file
    :return: path of the versioned resource file in the storage
    """

    if version < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The resource version has to be a positive integer")

    _check_versioning_supported(resource_type=resource_type, project_id=project_id)
    return s_base.get_resource_version_path(resource_type=resource_type, project_id=project_id, version=version)


def _check_versioning_supported(resource_type: ResourceType, project_id: str | None):
    """
    Ensure that the resource can be versioned - it has a versioned type and belongs to a project.

    :param resource_type: type of the resource
    :param project_id: project ID
    """

    if resource_type not in s_base.RESOURCES_VERSIONED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Resource type '{resource_type.value}' is not versioned - versioning is supported for: "
            f"{', '.join(x.value for x in s_base.RESOURCES_VERSIONED)}",
        )

    if not project_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"You need to pass project_id - the default '{resource_type.value}' file is not versioned",
        )
