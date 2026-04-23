"""Tüm veri toplayıcılarının ortak arayüzü."""
from abc import ABC, abstractmethod
from typing import Any


class CollectorError(Exception):
    """Veri toplama sırasında oluşan hatalar."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"[{source}] {message}")


class BaseCollector(ABC):
    """Tüm collector'ların türetildiği temel sınıf.

    Her collector bir `name` özelliği ve bir `fetch()` async metodu sağlar.
    fetch() metodu standart bir veri tipi döner (collector türüne göre değişir).
    """

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> Any:
        """Veri kaynağından veriyi çek ve döndür."""
        raise NotImplementedError
