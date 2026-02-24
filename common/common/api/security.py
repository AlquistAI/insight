# -*- coding: utf-8 -*-
"""
    common.api.security
    ~~~~~~~~~~~~~~~~~~~

    API security utilities.
"""

from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends

from common.api.security_apikey import header as header_apikey, verify_apikey
from common.api.security_jwt import header as header_jwt, verify_jwt


async def verify_apikey_or_jwt(key: str | None = Depends(header_apikey), token: str | None = Depends(header_jwt)):
    try:
        return await verify_apikey(key=key)
    except HTTPException:
        return await verify_jwt(token=token)
