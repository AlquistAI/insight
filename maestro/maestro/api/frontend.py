# -*- coding: utf-8 -*-
"""
    maestro.api.frontend
    ~~~~~~~~~~~~~~~~~~~~

    Frontend serving endpoints.
"""

from fastapi import status
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from common.utils.api import error_handler
from maestro.utils.frontend import DIR_ADMIN, DIR_INTERACTOR

router = APIRouter()


@router.get(
    "/admin/",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Load the Admin Console client app",
)
@error_handler
def get_admin() -> FileResponse:
    # Deep client-side routes are served by the SPAStaticFiles mount, which falls back to index.html on 404.
    return FileResponse(DIR_ADMIN / "dist" / "index.html")


@router.get(
    "/interactor/",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Load the Interactor client app",
)
@router.get("/", include_in_schema=False)
@error_handler
def get_interactor() -> FileResponse:
    return FileResponse(DIR_INTERACTOR / "dist" / "index.html")
