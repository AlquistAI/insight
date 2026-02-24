# -*- coding: utf-8 -*-
"""
    kronos.api.default
    ~~~~~~~~~~~~~~~~~~

    Default/uncategorized endpoints.
"""

from fastapi import status
from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from common.api.security_apikey import verify_apikey
from common.api.security_jwt import verify_jwt
from common.config import CONFIG

router = APIRouter()


@router.get(
    "/authtest/apikey",
    status_code=status.HTTP_200_OK,
    summary="Authentication test (API key)",
)
def auth_test_apikey(res=Depends(verify_apikey)):
    return {"authtest": "OK", "result": res}


@router.get(
    "/authtest/jwt",
    status_code=status.HTTP_200_OK,
    summary="Authentication test (JWT)",
)
def auth_test_jwt(res=Depends(verify_jwt)):
    return {"authtest": "OK", "result": res}


@router.get(
    "/version/backend",
    status_code=status.HTTP_200_OK,
    summary="Get backend version",
)
def get_backend_version():
    return {"version": CONFIG.KRONOS_VERSION}
