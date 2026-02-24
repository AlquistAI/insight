# -*- coding: utf-8 -*-
"""
    common.utils.exceptions
    ~~~~~~~~~~~~~~~~~~~~~~~

    Custom exceptions used throughout the project.
"""

from enum import Enum
from typing import Iterable


class CustomException(Exception):

    def __init__(self):
        self.detail = "Unknown exception occurred"

    def __str__(self):
        return self.detail


class DBRecordAlreadyExists(CustomException):
    def __init__(self, _id: str):
        self.detail = f"Data record with ID {_id} already exists in the database"


class DBRecordNotFound(CustomException):
    def __init__(self, _id: str | Iterable[str]):
        self.detail = f"Data record(s) with ID(s) {_id} not found in the database"


class InvalidModelProvider(CustomException):
    def __init__(self, provider: Enum):
        self.detail = f"Invalid model provider: {provider.value}"


class ResourceNotFound(CustomException):
    def __init__(self, resource_id: str):
        self.detail = f"Resource {resource_id} not found"


class ResourceNotFoundURL(CustomException):
    def __init__(self, url: str):
        self.detail = f"Resource for URL {url} not found (HTTP_404)"


class UnsupportedContentType(CustomException):
    def __init__(self, url: str, content_type: str):
        self.detail = f"Unsupported content type '{content_type}' for URL {url}"
