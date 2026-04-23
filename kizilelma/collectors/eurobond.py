"""Eurobond collector.

v1 IMPLEMENTATION NOTU:
Türkiye Eurobond verisi için resmi/ücretsiz API yok. Olası kaynaklar:
- İş Yatırım (https://www.isyatirim.com.tr/.../eurobond)
- Investing.com (scraping, kırılgan)
- Yahoo Finance (yfinance kütüphanesi)

Bu modül şu an basit bir HTTP GET ile JSON döndüren bir kaynaktan beslenecek
şekilde yazıldı. Kademe 4'te gerçek entegrasyon (yfinance) yapılacak.
Hata toleranslı: scraping başarısız olursa boş liste döner.
"""
import datetime as dt
from decimal import Decimal

import httpx

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import EurobondData


# Geçici endpoint — gerçek entegrasyon Kademe 4'te
EUROBOND_URL = "https://api.example.com/eurobond"


class EurobondCollector(BaseCollector):
    """Türkiye Eurobond verilerini çeker."""

    name = "eurobond"

    def __init__(self, url: str = EUROBOND_URL, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout

    async def fetch(self) -> list[EurobondData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        today = dt.datetime.now().date()
        bonds: list[EurobondData] = []
        for item in payload.get("bonds", []):
            try:
                bonds.append(
                    EurobondData(
                        isin=item["isin"],
                        maturity_date=dt.datetime.strptime(
                            item["maturity"], "%Y-%m-%d"
                        ).date(),
                        currency=item["currency"],
                        yield_rate=Decimal(str(item["yield"])),
                        price=Decimal(str(item["price"])),
                        date=today,
                    )
                )
            except (KeyError, ValueError, ArithmeticError):
                continue
        return bonds
