# -*- coding: utf-8 -*-
"""
    common.models.base
    ~~~~~~~~~~~~~~~~~~

    Custom Pydantic base model.
"""

from pydantic import BaseModel, ConfigDict


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        serialize_by_alias=True,
        validate_assignment=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
