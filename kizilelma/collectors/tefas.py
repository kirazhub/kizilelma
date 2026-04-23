"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) collector.

TEFAS'ın resmi API'si: https://www.tefas.gov.tr
Hem standart hem de serbest fonların verilerini çeker.
"""
import datetime as dt
from decimal import Decimal
from typing import Any, Optional

import httpx

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import FundData


TEFAS_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"


class TefasCollector(BaseCollector):
    """TEFAS fonlarının günlük verilerini çeker."""

    name = "tefas"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> list[FundData]:
        """Bugüne ait tüm fonların verisini döndürür."""
        today = dt.date.today()
        target = self._previous_weekday(today)

        payload = {
            "fontip": "YAT",  # Yatırım fonu
            "sfontur": "",
            "fonkod": "",
            "fongrup": "",
            "bastarih": target.strftime("%d.%m.%Y"),
            "bittarih": target.strftime("%d.%m.%Y"),
            "fonturkod": "",
            "fonunvantip": "",
            "strperiod": "1,1,1,1,1,1,1",
            "islemdurum": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(TEFAS_URL, data=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CollectorError(self.name, f"HTTP hatası: {exc}") from exc
        except ValueError as exc:
            raise CollectorError(self.name, f"JSON parse hatası: {exc}") from exc

        return [self._parse_fund(item) for item in data.get("data", [])]

    @staticmethod
    def _previous_weekday(d: dt.date) -> dt.date:
        """En yakın hafta içi günü döndürür."""
        while d.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
            d -= dt.timedelta(days=1)
        return d

    @staticmethod
    def _parse_fund(item: dict[str, Any]) -> FundData:
        """TEFAS API yanıtındaki tek bir fon kaydını FundData'ya dönüştür."""
        category = item.get("FONTUR", "Bilinmiyor")
        is_qualified = "Serbest" in category or "Nitelikli" in (
            item.get("FONUNVAN") or ""
        )
        return FundData(
            code=item["FONKODU"],
            name=item["FONUNVAN"],
            category=category,
            price=Decimal(str(item["FIYAT"])),
            date=dt.datetime.strptime(item["TARIH"], "%d.%m.%Y").date(),
            return_1d=_safe_decimal(item.get("GETIRI1G")),
            return_1w=_safe_decimal(item.get("GETIRI1H")),
            return_1m=_safe_decimal(item.get("GETIRI1A")),
            return_3m=_safe_decimal(item.get("GETIRI3A")),
            return_6m=_safe_decimal(item.get("GETIRI6A")),
            return_1y=_safe_decimal(item.get("GETIRI1Y")),
            is_qualified_investor=is_qualified,
        )


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """None veya boş değerse None, aksi halde Decimal döner."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None
