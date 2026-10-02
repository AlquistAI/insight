# -*- coding: utf-8 -*-
"""
    kronos.services.storage.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Storage interface definition.
"""

import re
from abc import ABC, abstractmethod

from common.config import CONFIG
from common.models.enums import ResourceType, SourceType
from common.utils.singleton import SingletonABC

DIR_ROOT = CONFIG.STORAGE_PREFIX.strip("/")
DIR_IMAGES = f"{DIR_ROOT}/images".lstrip("/")
DIR_PROJECTS = f"{DIR_ROOT}/projects".lstrip("/")

DIR_PROJECT = f"{DIR_PROJECTS}/{{project_id}}"
DIR_PROJECT_DOCUMENTS = f"{DIR_PROJECT}/documents"
DIR_PROJECT_KB = f"{DIR_PROJECT}/knowledge_base"
DIR_PROJECT_IMAGES = f"{DIR_PROJECT}/images"

DIR_DOCUMENT = f"{DIR_PROJECT_DOCUMENTS}/{{document_id}}"
DIR_KB = f"{DIR_PROJECT_KB}/{{kb_id}}"

FN_DIALOGUE_FSM = "dialogue.json"
FN_IMAGE = "{image_name}"
FN_PROMPTS = "prompts.md"
FN_SOURCE = "source.{source_type}"

# Filename of an older version of a resource file, e.g. "dialogue-v5.json"
FN_VERSION_INFIX = "-v"
FN_VERSIONED = f"{{stem}}{FN_VERSION_INFIX}{{version}}.{{suffix}}"
RE_FN_VERSIONED = re.compile(rf"(?P<stem>.+){FN_VERSION_INFIX}(?P<version>\d+)\.(?P<suffix>[^.]+)$")

# Resource types that are project specific with a fallback to a default (project independent) file,
# mapped to the storage directory holding the default file
RESOURCES_WITH_DEFAULT = {
    ResourceType.DIALOGUE_FSM: DIR_ROOT,
    ResourceType.IMAGE: DIR_IMAGES,
    ResourceType.PROMPTS: DIR_ROOT,
}

# Resource types keeping the previous versions of their project-specific files in the storage
# (changes of the default files are tracked in git)
RESOURCES_VERSIONED = (ResourceType.DIALOGUE_FSM, ResourceType.PROMPTS)


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
        case ResourceType.DIALOGUE_FSM:
            return FN_DIALOGUE_FSM
        case ResourceType.IMAGE:
            return FN_IMAGE.format(image_name=resource_id)
        case ResourceType.PROMPTS:
            return FN_PROMPTS

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
    """
    Get directory path for a resource based on resource type.

    Returns `None` for project-specific resource types when no `project_id` is passed - the location of
    their default (project independent) file is defined by `RESOURCES_WITH_DEFAULT`.
    """

    if resource_type in (ResourceType.SOURCE_DOCUMENT, ResourceType.SOURCE_KB) and not (resource_id and project_id):
        raise ValueError(f"You need to pass both resource_id and project_id for {resource_type.value}")

    match resource_type:
        case ResourceType.DIALOGUE_FSM:
            return DIR_PROJECT.format(project_id=project_id) if project_id else None
        case ResourceType.IMAGE:
            return DIR_PROJECT_IMAGES.format(project_id=project_id) if project_id else None
        case ResourceType.PROMPTS:
            return DIR_PROJECT.format(project_id=project_id) if project_id else None

        case ResourceType.SOURCE_DOCUMENT:
            return DIR_DOCUMENT.format(project_id=project_id, document_id=resource_id)
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
    if (r_dir_default := RESOURCES_WITH_DEFAULT.get(resource_type)) is not None:
        paths.append(f"{r_dir_default}/{r_fn}")

    return paths


def get_resource_version_path(resource_type: ResourceType, project_id: str, version: int) -> str:
    """
    Get the storage path of an older version of a project-specific resource file.

    :param resource_type: type of the resource (one of `RESOURCES_VERSIONED`)
    :param project_id: project ID
    :param version: version of the resource file
    :return: path of the versioned resource file in the storage
    """

    r_dir = get_resource_dir(resource_type=resource_type, project_id=project_id)
    r_fn = get_versioned_fn(filename=get_resource_fn(resource_type=resource_type), version=version)
    return f"{r_dir}/{r_fn}"


def get_resource_version_prefix(resource_type: ResourceType, project_id: str) -> str:
    """
    Get the storage path prefix shared by all the older versions of a project-specific resource file.

    The prefix pins the project folder and the versioned filename stem (e.g. ".../projects/foo/prompts-v"),
    so that a listing with it matches the older versions of the resource only - neither its live file nor
    any other resource of the project.

    :param resource_type: type of the resource (one of `RESOURCES_VERSIONED`)
    :param project_id: project ID
    :return: path prefix of the versioned resource files in the storage
    """

    r_dir = get_resource_dir(resource_type=resource_type, project_id=project_id)
    r_stem = get_resource_fn(resource_type=resource_type).rpartition(".")[0]
    return f"{r_dir}/{r_stem}{FN_VERSION_INFIX}"


def get_versioned_fn(filename: str, version: int) -> str:
    """
    Build the filename of an older version of a resource file, e.g. "dialogue.json" -> "dialogue-v5.json".

    :param filename: filename of the live (most up-to-date) resource file
    :param version: version of the resource file
    :return: versioned filename
    """

    stem, _, suffix = filename.rpartition(".")
    if not stem:
        raise ValueError(f"Cannot version a filename without a suffix: {filename}")
    return FN_VERSIONED.format(stem=stem, version=version, suffix=suffix)


def parse_versioned_fn(filename: str) -> tuple[str, int | None]:
    """
    Parse the version out of a resource filename, e.g. "dialogue-v5.json" -> ("dialogue.json", 5).

    :param filename: resource filename string
    :return: filename of the live resource file and the parsed version (`None` for the live file itself)
    """

    if (match := RE_FN_VERSIONED.match(filename)) is None:
        return filename, None
    return f"{match['stem']}.{match['suffix']}", int(match["version"])


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
    def list_files(self, prefix: str = f"{CONFIG.STORAGE_PREFIX}/", as_folder: bool = True) -> list[str]:
        """
        List stored files.

        :param prefix: optional search prefix
        :param as_folder: treat the prefix as a folder path (list its content), match it verbatim otherwise
        :return: list of file paths
        """

        raise NotImplementedError
