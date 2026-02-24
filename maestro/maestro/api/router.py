# -*- coding: utf-8 -*-
"""
    maestro.api.router
    ~~~~~~~~~~~~~~~~~~

    API router definition.
"""

from fastapi.routing import APIRouter

from common.api import health
from maestro.api import analytics, default, dialogue, frontend, nlp, resources

api_router = APIRouter()
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(default.router, tags=["default"])
api_router.include_router(dialogue.router, tags=["dialogue"])
api_router.include_router(frontend.router, tags=["frontend"])
api_router.include_router(health.router, tags=["default"])
api_router.include_router(nlp.router, tags=["nlp"])
api_router.include_router(resources.router, tags=["resources"])
