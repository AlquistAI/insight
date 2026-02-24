# -*- coding: utf-8 -*-
"""
    kronos.api.router
    ~~~~~~~~~~~~~~~~~

    API router definition.
"""

from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from common.api import health
from common.api.security import verify_apikey_or_jwt
from kronos.api import default, deprecated, knowledge_base, nlp, projects, resources, sessions, turns

dep = [Depends(verify_apikey_or_jwt)]

api_router = APIRouter()
api_router.include_router(default.router, tags=["default"])
api_router.include_router(deprecated.router, dependencies=dep, deprecated=True)
api_router.include_router(health.router, tags=["default"])
api_router.include_router(knowledge_base.router, dependencies=dep, prefix="/knowledge_base", tags=["knowledge base"])
api_router.include_router(nlp.router, dependencies=dep, prefix="/projects/{project_id}/nlp", tags=["nlp"])
api_router.include_router(projects.router, dependencies=dep, prefix="/projects", tags=["projects"])
api_router.include_router(resources.router, dependencies=dep, prefix="/resources", tags=["resources"])
api_router.include_router(sessions.router, dependencies=dep, prefix="/sessions", tags=["sessions"])
api_router.include_router(turns.router, dependencies=dep, prefix="/turns", tags=["turns"])
