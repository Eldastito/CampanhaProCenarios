from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstração de storage. Implementações: local filesystem (atual), S3/MinIO (futuro)."""

    @abstractmethod
    def save_text(self, path: str, content: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def save_bytes(self, path: str, content: bytes) -> str:
        """Persiste conteúdo binário. Retorna a URI/caminho efetivo gravado."""
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, path: str) -> bytes:
        """Lê conteúdo binário gravado anteriormente."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Remove o arquivo. Retorna True se removido, False se não existia."""
        raise NotImplementedError
