from pathlib import Path

from app.services.storage.base import StorageProvider


class LocalFilesystemStorageProvider(StorageProvider):
    """Storage no filesystem local. Estrutura recomendada: {org_id}/{project_id}/{evidence_id}.{ext}."""

    def __init__(self, base_path: str = "./storage") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        full = (self.base_path / path).resolve()
        # Defesa contra path traversal: garante que o caminho final cai dentro de base_path
        try:
            full.relative_to(self.base_path.resolve())
        except ValueError as e:
            raise ValueError(f"Caminho fora do diretório base: {path}") from e
        return full

    def save_text(self, path: str, content: str) -> str:
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    def read_text(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def save_bytes(self, path: str, content: bytes) -> str:
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(full_path)

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def delete(self, path: str) -> bool:
        full = self._resolve(path)
        if not full.exists():
            return False
        full.unlink()
        return True
