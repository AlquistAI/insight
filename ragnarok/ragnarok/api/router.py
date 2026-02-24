# -*- coding: utf-8 -*-
"""
    ragnarok.api.router
    ~~~~~~~~~~~~~~~~~~~

    API router definition.
"""

from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from common.api import health
from common.api.security_apikey import verify_apikey_old
from ragnarok.api import default, deprecated, knowledge_base, nlp, projects

dep = [Depends(verify_apikey_old)]

api_router = APIRouter()
api_router.include_router(default.router, tags=["default"])
api_router.include_router(deprecated.router, dependencies=dep, deprecated=True)
api_router.include_router(health.router, tags=["default"])
api_router.include_router(knowledge_base.router, dependencies=dep, prefix="/knowledge_base", tags=["knowledge base"])
api_router.include_router(nlp.router, dependencies=dep, prefix="/projects/{project_id}/nlp", tags=["nlp"])
api_router.include_router(projects.router, dependencies=dep, prefix="/projects", tags=["projects"])
