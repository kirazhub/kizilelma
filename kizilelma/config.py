"""Uygulama ayarları — env değişkenlerinden okunur."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Tüm yapılandırma değerlerini tutan sınıf."""

    def __init__(self) -> None:
        self.tcmb_api_key: str = self._require("TCMB_API_KEY")
        self.anthropic_api_key: str = self._require("ANTHROPIC_API_KEY")
        self.environment: str = os.getenv("ENVIRONMENT", "development")

    @staticmethod
    def _require(key: str) -> str:
        """Zorunlu env değişkenini oku, yoksa hata ver."""
        value = os.getenv(key)
        if not value:
            raise RuntimeError(
                f"Eksik ortam değişkeni: {key}. .env dosyasını kontrol et."
            )
        return value


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Singleton config nesnesi döner."""
    return Config()
