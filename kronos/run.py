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

from common.config import CONFIG
from common.core import get_component_logger
from common.core.middleware import RequestContextLogMiddleware
from common.utils.swagger import setup_descriptions
from kronos import COMPONENT_ID, COMPONENT_NAME
from kronos.api.router import api_router

logger = get_component_logger()


def create_app() -> FastAPI:
    app = FastAPI(
        title=COMPONENT_NAME,
        version=CONFIG.KRONOS_VERSION,
        lifespan=lifespan,
        swagger_ui_parameters={
            "operationsSorter": "alpha",
            "tagsSorter": "alpha",
        },
    )

    app.include_router(api_router)
    setup_descriptions(app)

    app.add_middleware(RequestContextLogMiddleware, logger=logger, router=app.router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "Content-Length",
            "Content-Type",
            "X-Response-Time",
            "X-Source-File",
        ],
    )

    return app


# noinspection PyUnusedLocal
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Service %s (component_id: %s) started on %s with logging level %s",
        COMPONENT_NAME, COMPONENT_ID, datetime.now(tz=tz.UTC), CONFIG.KRONOS_LOG_LEVEL,
    )
    yield
    logger.info("Service %s (component_id: %s) shutting down...", COMPONENT_NAME, COMPONENT_ID)


fast_app = create_app()

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        uvicorn.run(
            app=fast_app,
            host="0.0.0.0",
            port=CONFIG.KRONOS_PORT,
            log_level=CONFIG.KRONOS_LOG_LEVEL.lower(),
        )
