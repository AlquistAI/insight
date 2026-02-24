# -*- coding: utf-8 -*-
"""
    kronos.services.storage.azure
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Azure storage implementation.
"""

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from common.config import CONFIG
from common.core import get_component_logger
from common.utils import exceptions as exc
from common.utils.misc import generate_batches
from kronos.services.storage.base import StorageBase

logger = get_component_logger()


class AzureStorage(StorageBase):

    def __init__(self, container_name: str = CONFIG.STORAGE_CONTAINER_NAME):
        self.container_name = container_name
        self.max_batch_size = 256

        self.blob_service_client = BlobServiceClient.from_connection_string(
            conn_str=CONFIG.AZURE_BLOB_STORAGE_CONN_STR.get_secret_value(),
        )

        self.container_client = self.blob_service_client.get_container_client(container=self.container_name)

    def _get_blob_client(self, blob_name: str):
        return self.container_client.get_blob_client(blob=blob_name)

    def get_file(self, file_path: str) -> bytes:
        logger.debug("Downloading %s from container %s", file_path, self.container_name)
        blob_client = self._get_blob_client(blob_name=file_path)

        try:
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            raise exc.ResourceNotFound(resource_id=file_path) from None

    def post_file(self, file_path: str, content: bytes):
        logger.debug("Uploading %s to container %s", file_path, self.container_name)
        blob_client = self._get_blob_client(blob_name=file_path)
        blob_client.upload_blob(content, overwrite=True)

    def delete_file(self, file_path: str) -> int:
        logger.debug("Deleting %s from container %s", file_path, self.container_name)
        blob_client = self._get_blob_client(blob_name=file_path)

        try:
            blob_client.delete_blob()
            return 1
        except ResourceNotFoundError:
            return 0

    def delete_folder(self, folder_path: str) -> int:
        folder_path = f"{folder_path.rstrip('/')}/".lstrip("/")
        logger.debug("Deleting folder %s from container %s", folder_path, self.container_name)
        blob_names = [x["name"] for x in self.container_client.list_blobs(name_starts_with=folder_path)]

        for blob_names_batch in generate_batches(blob_names, self.max_batch_size):
            self.container_client.delete_blobs(*blob_names_batch)

        return len(blob_names)

    def list_files(self, prefix: str = f"{CONFIG.STORAGE_PREFIX}/") -> list[str]:
        prefix = f"{prefix.rstrip('/')}/".lstrip("/")
        logger.debug("Listing all files in container %s with prefix %s", self.container_name, prefix)
        blob_names = [x["name"] for x in self.container_client.list_blobs(name_starts_with=prefix)]
        return sorted(blob_names)
