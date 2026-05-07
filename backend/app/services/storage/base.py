from abc import ABC, abstractmethod


class StorageProvider(ABC):
    @abstractmethod
    def save_text(self, path: str, content: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, path: str) -> str:
        raise NotImplementedError
