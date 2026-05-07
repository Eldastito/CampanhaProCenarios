from pathlib import Path

from app.services.storage.base import StorageProvider


class LocalFilesystemStorageProvider(StorageProvider):
    def __init__(self, base_path: str = "./storage") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_text(self, path: str, content: str) -> str:
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    def read_text(self, path: str) -> str:
        full_path = self.base_path / path
        return full_path.read_text(encoding="utf-8")
