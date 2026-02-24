# -*- coding: utf-8 -*-
"""
    kronos.services.storage
    ~~~~~~~~~~~~~~~~~~~~~~~

    Storage integration.
"""

from common.config import CONFIG
from common.models.enums import StorageType


def get_storage(storage_type: StorageType = CONFIG.STORAGE_TYPE):
    if storage_type == StorageType.AZURE_BLOB_STORAGE:
        from kronos.services.storage.azure import AzureStorage
        return AzureStorage()
    elif storage_type == StorageType.MINIO:
        from kronos.services.storage.minio import MinioStorage
        return MinioStorage()
    else:
        raise ValueError(f"Invalid storage type: {storage_type.value}")
