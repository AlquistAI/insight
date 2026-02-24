# -*- coding: utf-8 -*-
"""
    common.models.validation
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Helper functions and type definitions used for validation of pydantic models.
"""

from datetime import datetime
from typing import Annotated

from bson import ObjectId
from dateutil import tz
from pydantic import AfterValidator


#######################
## DEFAULT FACTORIES ##
#######################

def object_id_str() -> str:
    return str(ObjectId())


def utc_now() -> datetime:
    return datetime.now(tz=tz.UTC)


######################
## FIELD VALIDATORS ##
######################

def fill_id(v: str | None) -> str:
    return v or object_id_str()


def validate_lang_format(v: str | None) -> str | None:
    if isinstance(v, str) and len(v.split("-")) != 2:
        raise ValueError("language needs to be in a '<lang>-<locale>' format")
    return v


######################
## TYPE DEFINITIONS ##
######################

Language = Annotated[str, AfterValidator(validate_lang_format)]
MongoID = Annotated[str, AfterValidator(fill_id)]
