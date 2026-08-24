# -*- coding: utf-8 -*-
"""
    alchemist.api.router
    ~~~~~~~~~~~~~~~~~~~~

    API router definition.
"""

from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from alchemist.api import conversion, default
from common.api import health
from common.api.security_apikey import verify_apikey

dep = [Depends(verify_apikey)]

api_router = APIRouter()
api_router.include_router(conversion.router, dependencies=dep, prefix="/conversion", tags=["conversion"])
api_router.include_router(default.router, tags=["default"])
api_router.include_router(health.router, tags=["default"])
