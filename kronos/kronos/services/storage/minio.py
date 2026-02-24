# -*- coding: utf-8 -*-
"""
    kronos.services.storage.minio
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    MinIO storage implementation.
"""

from io import BytesIO

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from common.config import CONFIG
from common.core import get_component_logger
from common.utils import exceptions as exc
from kronos.services.storage.base import StorageBase

logger = get_component_logger()


class MinioStorage(StorageBase):

    def __init__(self, bucket_name: str = CONFIG.STORAGE_CONTAINER_NAME):
        self.bucket_name = bucket_name
        self._prepare_bucket()

    @staticmethod
    def _get_client() -> Minio:
        # Refreshing the Minio client reduces memory consumption
        return Minio(
            endpoint=f"{CONFIG.MINIO_URL.host}:{CONFIG.MINIO_URL.port}",
            access_key=CONFIG.MINIO_ACCESS_KEY,
            secret_key=CONFIG.MINIO_SECRET_KEY.get_secret_value(),
            secure=CONFIG.MINIO_URL.scheme == "https",
        )

    def _prepare_bucket(self):
        client = self._get_client()
        if not client.bucket_exists(self.bucket_name):
            client.make_bucket(self.bucket_name)

    def _object_exists(self, file_path: str, client=None) -> bool:
        client = client or self._get_client()

        try:
            client.stat_object(self.bucket_name, file_path)
            return True
        except S3Error:
            return False

    def get_file(self, file_path: str) -> bytes:
        logger.debug("Downloading %s from bucket %s", file_path, self.bucket_name)
        client = self._get_client()
        response = None

        try:
            response = client.get_object(self.bucket_name, file_path)
            return response.data
        except S3Error:
            raise exc.ResourceNotFound(resource_id=file_path) from None
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def post_file(self, file_path: str, content: bytes):
        logger.debug("Uploading %s to bucket %s", file_path, self.bucket_name)
        client = self._get_client()
        client.put_object(self.bucket_name, file_path, BytesIO(content), len(content))

    def delete_file(self, file_path: str) -> int:
        logger.debug("Deleting %s from bucket %s", file_path, self.bucket_name)
        client = self._get_client()

        if not self._object_exists(file_path, client=client):
            return 0

        client.remove_object(self.bucket_name, file_path)
        return 1

    def delete_folder(self, folder_path: str) -> int:
        folder_path = f"{folder_path.rstrip('/')}/".lstrip("/")
        logger.debug("Deleting folder %s from bucket %s", folder_path, self.bucket_name)

        client = self._get_client()
        delete_object_list = [
            DeleteObject(x.object_name)
            for x in client.list_objects(self.bucket_name, prefix=folder_path, recursive=True)
        ]

        for error in (errors := list(client.remove_objects(self.bucket_name, delete_object_list))):
            logger.warning("Failed to delete object from bucket %s: %s", self.bucket_name, error)

        return len(delete_object_list) - len(errors)

    def list_files(self, prefix: str = f"{CONFIG.STORAGE_PREFIX}/") -> list[str]:
        prefix = f"{prefix.rstrip('/')}/".lstrip("/")
        logger.debug("Listing all files in bucket %s with prefix %s", self.bucket_name, prefix)

        client = self._get_client()
        object_names = [x.object_name for x in client.list_objects(self.bucket_name, prefix=prefix, recursive=True)]
        return sorted(object_names)
