"""Storage abstractions."""

from app.services.storage.base import StorageProvider
from app.services.storage.local import LocalFilesystemStorageProvider

__all__ = ["StorageProvider", "LocalFilesystemStorageProvider"]
