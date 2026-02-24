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
@router.get("/admin/contact", include_in_schema=False)
@router.get("/admin/crawl", include_in_schema=False)
@router.get("/admin/dashboard", include_in_schema=False)
@router.get("/admin/new-project", include_in_schema=False)
@error_handler
def get_admin() -> FileResponse:
    # FixMe: Find a better way to handle "location" paths in React other than adding hidden endpoints.
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
