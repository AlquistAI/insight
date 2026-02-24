# -*- coding: utf-8 -*-
"""
    run
    ~~~

    FastAPI server run script.
"""

from contextlib import asynccontextmanager, suppress
from datetime import datetime

import uvicorn
from dateutil import tz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from common.config import CONFIG
from common.core import get_component_logger
from common.core.middleware import ParamToContext, RequestContextLogMiddleware
from common.utils.swagger import setup_descriptions
from maestro import COMPONENT_ID, COMPONENT_NAME
from maestro.api.router import api_router
from maestro.utils.frontend import DIR_ADMIN, DIR_INTERACTOR, prepare_clients

logger = get_component_logger()

COMPONENT_DESCRIPTION = (
    "This is the Maestro FastAPI server. "
    "It provides APIs for the Interactor client. "
    "It reads Finite State Machine JSON containing the dialogue flow. "
    "It uses Kronos knowledge base and Ragnarok to run RAG."
)

p2c = [
    ParamToContext("kb_id"),
    ParamToContext("project_id"),
    ParamToContext("session_id"),
    ParamToContext("user_id"),
]


def create_app() -> FastAPI:
    app = FastAPI(
        title=COMPONENT_NAME,
        description=COMPONENT_DESCRIPTION,
        version=CONFIG.MAESTRO_VERSION,
        lifespan=lifespan,
        swagger_ui_parameters={
            "operationsSorter": "alpha",
            "tagsSorter": "alpha",
        },
    )

    app.include_router(api_router)
    setup_descriptions(app)

    app.add_middleware(RequestContextLogMiddleware, logger=logger, router=app.router, extractors=p2c)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Length"],
    )

    return app


# noinspection PyUnusedLocal
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Service %s (component_id: %s) started on %s with logging level %s",
        COMPONENT_NAME, COMPONENT_ID, datetime.now(tz=tz.UTC), CONFIG.MAESTRO_LOG_LEVEL,
    )

    prepare_clients()
    app.mount("/admin", StaticFiles(directory=DIR_ADMIN / "dist"), name="admin")
    app.mount("/interactor", StaticFiles(directory=DIR_INTERACTOR / "dist"), name="interactor")

    yield

    logger.info("Service %s (component_id: %s) shutting down...", COMPONENT_NAME, COMPONENT_ID)


fast_app = create_app()

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        uvicorn.run(
            app=fast_app,
            host="0.0.0.0",
            port=CONFIG.MAESTRO_PORT,
            log_level=CONFIG.MAESTRO_LOG_LEVEL.lower(),
        )
