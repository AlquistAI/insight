# -*- coding: utf-8 -*-
"""
    common.models.crawling
    ~~~~~~~~~~~~~~~~~~~~~~

    Web crawling models.
"""

from pydantic import Field, field_validator

from common.models.base import CustomBaseModel


class CrawlOptions(CustomBaseModel):
    delay: float = 1.0
    max_pages: int = 1000
    timeout: float | tuple[float, float] = (10.0, 30.0)

    exclude_mimetypes: set[str] = Field(default_factory=set)
    exclude_query_params: set[str] = Field(default_factory=set)
    exclude_substrings: set[str] = Field(default_factory=set)
    exclude_suffixes: set[str] = Field(default_factory=set)

    same_host_only: bool = True

    @field_validator("exclude_mimetypes", "exclude_query_params", "exclude_substrings", "exclude_suffixes")
    @classmethod
    def clean_exclude_set(cls, v: set[str]) -> set[str]:
        return {xs.lower() for x in v if (xs := x.strip())}

    @field_validator("exclude_mimetypes", "exclude_query_params", "exclude_suffixes")
    @classmethod
    def strip_exclude_set(cls, v: set[str]) -> set[str]:
        return {x.strip("/").strip() for x in v}
