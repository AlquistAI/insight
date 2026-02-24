# -*- coding: utf-8 -*-
"""
    common.api.security_apikey
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    API security utilities using API key.
"""

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

_API_KEY: SecretStr | None = None

header = APIKeyHeader(name="X-Api-Key", scheme_name="API Key", auto_error=False)
header_old = APIKeyHeader(name="Authorization", scheme_name="API Key", auto_error=False)


async def verify_apikey(key: str | None = Depends(header)):
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key missing")

    if key == _get_api_key():
        return True

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect API key")


async def verify_apikey_old(key: str | None = Depends(header_old)):
    # ToDo: Unify the header name across components and remove the old header.

    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key missing")

    if key == _get_api_key():
        return True

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect API key")


def _get_api_key() -> str:
    if _API_KEY is None:
        raise RuntimeError("API key not initialized")
    return _API_KEY.get_secret_value()


def set_api_key(key: SecretStr):
    global _API_KEY
    _API_KEY = key
