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

    config = {
        "DEPLOYMENT": CONFIG.DEPLOYMENT,
        "ENVIRONMENT": "PRODUCTION" if CONFIG.DEPLOYMENT.startswith("production") else "DEVELOPMENT",
        "KRONOS_URL": str(CONFIG.KRONOS_URL_EXTERNAL).rstrip("/"),
        "MAESTRO_URL": str(CONFIG.MAESTRO_URL_EXTERNAL).rstrip("/"),
        "KEYCLOAK_URL": str(CONFIG.KEYCLOAK_URL_EXTERNAL).rstrip("/"),
        "KEYCLOAK_REALM": CONFIG.KEYCLOAK_REALM,
        "KEYCLOAK_CLIENT_ID": CONFIG.KEYCLOAK_CLIENT_ID,
        "PROJECT_ID": CONFIG.PROJECT_ID,
        "PROJECT_TITLE": CONFIG.PROJECT_TITLE,
    }

    # Handle different names for same things in different clients.
    # ToDo: Unify the names in clients and get rid of this.
    config["KEYCLOAK_CLIENT_ID_LOCAL"] = config["KEYCLOAK_CLIENT_ID"]
    config["MAESTRO_API_URL"] = config["MAESTRO_URL"]

    if client_name in (ClientName.ADMIN, ClientName.ADMIN_SIMPLE):
        # FixMe: Get rid of the API key from client apps!
        config["KRONOS_API_KEY"] = CONFIG.KRONOS_API_KEY.get_secret_value()
        config["VERSION"] = CONFIG.ADMIN_CONSOLE_VERSION
    elif client_name in (ClientName.INTERACTOR, ClientName.INTERACTOR_UPV):
        config["VERSION"] = CONFIG.INTERACTOR_VERSION

    config_path = CLIENT_NAME_TO_DIR[client_name] / "dist" / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)


def prepare_clients():
    """Prepare all required client files based on config."""

    fetch_client(client_name=CONFIG.ADMIN_CONSOLE_PACKAGE_NAME, version=CONFIG.ADMIN_CONSOLE_VERSION)
    create_client_config(client_name=CONFIG.ADMIN_CONSOLE_PACKAGE_NAME)

    fetch_client(client_name=CONFIG.INTERACTOR_PACKAGE_NAME, version=CONFIG.INTERACTOR_VERSION)
    create_client_config(client_name=CONFIG.INTERACTOR_PACKAGE_NAME)
