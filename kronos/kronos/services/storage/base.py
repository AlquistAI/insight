# -*- coding: utf-8 -*-
"""
    kronos.services.storage.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Storage interface definition.
"""

from abc import ABC, abstractmethod

from common.config import CONFIG
from common.models.enums import ResourceType, SourceType
from common.utils.singleton import SingletonABC

DIR_IMAGES = f"{CONFIG.STORAGE_PREFIX}/images".lstrip("/")
DIR_PROJECTS = f"{CONFIG.STORAGE_PREFIX}/projects".lstrip("/")

DIR_PROJECT = f"{DIR_PROJECTS}/{{project_id}}"
DIR_DOCUMENTS = f"{DIR_PROJECT}/documents/{{document_id}}"
DIR_KB = f"{DIR_PROJECT}/knowledge_base/{{kb_id}}"

FN_CHATBOT_HTML = "chatbot.html"
FN_DIALOGUE_FSM = "dialogue.json"
FN_IMAGE = "{image_name}"
FN_SOURCE = "source.{source_type}"


def get_resource_fn(
        resource_type: ResourceType,
        resource_id: str | None = None,
        source_type: SourceType | None = None,
) -> str:
    """Get resource filename based on resource type."""

    if resource_type == ResourceType.IMAGE and not resource_id:
        raise ValueError(f"You need to pass resource_id for {resource_type.value}")
    if resource_type in (ResourceType.SOURCE_DOCUMENT, ResourceType.SOURCE_KB) and not source_type:
        raise ValueError(f"You need to pass source_type for {resource_type.value}")

    match resource_type:
        case ResourceType.CHATBOT_HTML:
            return FN_CHATBOT_HTML
        case ResourceType.DIALOGUE_FSM:
            return FN_DIALOGUE_FSM
        case ResourceType.IMAGE:
            return FN_IMAGE.format(image_name=resource_id)

        case ResourceType.SOURCE_DOCUMENT:
            return FN_SOURCE.format(source_type=source_type.value)
        case ResourceType.SOURCE_KB:
            return FN_SOURCE.format(source_type=source_type.value)

    raise ValueError(f"Invalid resource type passed: {resource_type}")


def get_resource_dir(
        resource_type: ResourceType,
        resource_id: str | None = None,
        project_id: str | None = None,
) -> str | None:
    """Get directory path for a resource based on resource type."""

    if resource_type in (ResourceType.SOURCE_DOCUMENT, ResourceType.SOURCE_KB) and not (resource_id and project_id):
        raise ValueError(f"You need to pass both resource_id and project_id for {resource_type.value}")

    match resource_type:
        case ResourceType.CHATBOT_HTML:
            return DIR_PROJECT.format(project_id=project_id) if project_id else None
        case ResourceType.DIALOGUE_FSM:
            return DIR_PROJECT.format(project_id=project_id) if project_id else None
        case ResourceType.IMAGE:
            return DIR_IMAGES

        case ResourceType.SOURCE_DOCUMENT:
            return DIR_DOCUMENTS.format(project_id=project_id, document_id=resource_id)
        case ResourceType.SOURCE_KB:
            return DIR_KB.format(project_id=project_id, kb_id=resource_id)

    raise ValueError(f"Invalid resource type passed: {resource_type}")


def get_resource_paths(
        resource_type: ResourceType,
        resource_id: str | None = None,
        project_id: str | None = None,
        source_type: SourceType = SourceType.PDF,
) -> list[str]:
    """
    Get a list of possible resource paths in order of priority.

    :param resource_type: type of the resource
    :param resource_id: ID or (file)name of the resource
    :param project_id: project ID for project-specific resources
    :param source_type: source file type (extension)
    :return: list of resource paths in order of priority
    """

    r_dir = get_resource_dir(resource_type=resource_type, resource_id=resource_id, project_id=project_id)
    r_fn = get_resource_fn(resource_type=resource_type, resource_id=resource_id, source_type=source_type)

    paths = [f"{r_dir}/{r_fn}"] if r_dir else []
    if resource_type in (ResourceType.CHATBOT_HTML, ResourceType.DIALOGUE_FSM):
        paths.append(f"{CONFIG.STORAGE_PREFIX}/{r_fn}".lstrip("/"))

    return paths


class StorageBase(ABC, metaclass=SingletonABC):

    @abstractmethod
    def get_file(self, file_path: str) -> bytes:
        """
        Get file content from the storage.

        :param file_path: path to the file in the storage
        :return: file content
        """

        raise NotImplementedError

    @abstractmethod
    def post_file(self, file_path: str, content: bytes):
        """
        Upload a file to the storage. Overwrite if it already exists.

        :param file_path: file path in the storage
        :param content: file content
        """

        raise NotImplementedError

    @abstractmethod
    def delete_file(self, file_path: str) -> int:
        """
        Remove a file from the storage.

        :param file_path: path to the file in the storage
        :return: number of deleted files/blobs (1 if deleted, 0 if not found)
        """

        raise NotImplementedError

    @abstractmethod
    def delete_folder(self, folder_path: str) -> int:
        """
        Remove a folder from the storage.

        :param folder_path: path of the folder in the storage
        :return: number of deleted files/blobs
        """

        raise NotImplementedError

    @abstractmethod
    def list_files(self, prefix: str = f"{CONFIG.STORAGE_PREFIX}/") -> list[str]:
        """
        List stored files.

        :param prefix: optional search prefix
        :return: list of file paths
        """

        raise NotImplementedError
