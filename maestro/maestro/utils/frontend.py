# -*- coding: utf-8 -*-
"""
    maestro.utils.frontend
    ~~~~~~~~~~~~~~~~~~~~~~

    Utility functions for serving frontend apps.
"""

import json
import tarfile
from io import BytesIO
from pathlib import Path

import requests
from fastapi import status
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

from common.config import CONFIG
from common.core import get_component_logger
from common.models.enums import ClientName

logger = get_component_logger()

DIR_FE = Path(__file__).parent.parent.parent / "frontend"
DIR_ADMIN = DIR_FE / "admin"
DIR_INTERACTOR = DIR_FE / "interactor"

URL_PACKAGE_REGISTRY = f"https://gitlab.com/api/v4/projects/{CONFIG.PACKAGE_REGISTRY_PROJECT_ID}/packages/generic"

CLIENT_NAME_TO_DIR = {
    ClientName.ADMIN: DIR_ADMIN,
    ClientName.ADMIN_SIMPLE: DIR_ADMIN,
    ClientName.INTERACTOR: DIR_INTERACTOR,
    ClientName.INTERACTOR_UPV: DIR_INTERACTOR,
}


class SPAStaticFiles(StaticFiles):
    """
    Serve a single-page-app build with client-side-routing fallback.

    The client apps use in-browser routing (e.g. `/admin/<project_id>`). On a full page load / refresh the browser
    asks the server for that path directly, but no such file exists on disk. Plain `StaticFiles` would return 404.
    Instead, we fall back to `index.html` so the SPA boots and its router renders the requested route.

    Requests under `assets/` are intentionally NOT rewritten: a genuinely missing JS/CSS bundle should keep
    returning 404 rather than be masked by an HTML response.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as ex:
            if ex.status_code == status.HTTP_404_NOT_FOUND and not path.startswith("assets/"):
                return await super().get_response("index.html", scope)
            raise


def fetch_client(client_name: ClientName, version: str):
    """
    Fetch and extract the client static files into the frontend directory.

    Does not fetch if the client directory already exists.

    :param client_name: client name
    :param version: client version
    """

    c_dir = CLIENT_NAME_TO_DIR[client_name]
    index_path = c_dir / "dist" / "index.html"

    if index_path.exists():
        logger.info("Directory %s already exists -> not fetching client %s", c_dir, client_name.value)
        return

    logger.info("Fetching client %s (%s)", client_name.value, version)

    try:
        res = requests.get(
            url=f"{URL_PACKAGE_REGISTRY}/{client_name.value}/{version}/dist.tar.gz",
            headers={"DEPLOY-TOKEN": CONFIG.PACKAGE_REGISTRY_TOKEN.get_secret_value()},
            timeout=(10, 30),
        )
        res.raise_for_status()
    except Exception as e:
        logger.error("Failed to fetch client %s (%s): %s", client_name.value, version, e)
        raise e from None

    with tarfile.open(fileobj=BytesIO(res.content), mode="r:gz") as tar:
        tar.extractall(path=CLIENT_NAME_TO_DIR[client_name])


def create_client_config(client_name: ClientName):
    """Create a config file for a given client."""

    logger.info("Creating config for client %s", client_name.value)
    client_type = "ADMIN" if client_name.name.startswith("ADMIN") else "INTERACTOR"

    config = {
        "DEPLOYMENT": CONFIG.DEPLOYMENT,
        "ENVIRONMENT": "PRODUCTION" if CONFIG.DEPLOYMENT.startswith("production") else "DEVELOPMENT",
        "KEYCLOAK_CLIENT_ID": CONFIG.KEYCLOAK_CLIENT_ID,
        "KEYCLOAK_REALM": CONFIG.KEYCLOAK_REALM,
        "KEYCLOAK_URL": str(CONFIG.KEYCLOAK_URL_EXTERNAL).rstrip("/"),
        "KRONOS_URL": str(CONFIG.KRONOS_URL_EXTERNAL).rstrip("/"),
        "MAESTRO_URL": str(CONFIG.MAESTRO_URL_EXTERNAL).rstrip("/"),
        "PROJECT_ID": CONFIG.PROJECT_ID,
        "PROJECT_TITLE": CONFIG.PROJECT_TITLE,
        "VERSION": CONFIG.ADMIN_CONSOLE_VERSION if client_type == "ADMIN" else CONFIG.INTERACTOR_VERSION,
    }

    # Handle different names for same things in different clients
    # ToDo: Unify the names in clients and get rid of this.
    config["KEYCLOAK_CLIENT_ID_LOCAL"] = config["KEYCLOAK_CLIENT_ID"]
    config["MAESTRO_API_URL"] = config["MAESTRO_URL"]

    if client_name == ClientName.ADMIN_SIMPLE:
        # FixMe: Get rid of the API key from the simplified Admin client!
        config["KRONOS_API_KEY"] = CONFIG.KRONOS_API_KEY.get_secret_value()

    config_path = CLIENT_NAME_TO_DIR[client_name] / "dist" / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)


def prepare_clients():
    """Prepare all required client files based on config."""

    fetch_client(client_name=CONFIG.ADMIN_CONSOLE_PACKAGE_NAME, version=CONFIG.ADMIN_CONSOLE_VERSION)
    create_client_config(client_name=CONFIG.ADMIN_CONSOLE_PACKAGE_NAME)

    fetch_client(client_name=CONFIG.INTERACTOR_PACKAGE_NAME, version=CONFIG.INTERACTOR_VERSION)
    create_client_config(client_name=CONFIG.INTERACTOR_PACKAGE_NAME)
