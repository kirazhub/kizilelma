"""TCMB EVDS API collector.

EVDS = Elektronik Veri Dağıtım Sistemi
Resmi API: https://evds2.tcmb.gov.tr
TCMB politika faizi, repo ve ters repo oranlarını çeker.
"""
import datetime as dt
from decimal import Decimal

import httpx

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import RepoRate


EVDS_BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

# İzlenecek seriler
# TP_KTF12   = TCMB Politika Faizi (1 hafta repo ihale faizi)
# TP_APIFON4 = Gecelik borçlanma faizi (ters repo)
# TP_APIFON6 = Gecelik borç verme faizi (repo)
SERIES = {
    "TP_KTF12": ("repo", "1w"),
    "TP_APIFON4": ("ters_repo", "overnight"),
    "TP_APIFON6": ("repo", "overnight"),
}


class TcmbCollector(BaseCollector):
    """TCMB EVDS verilerini çeker."""

    name = "tcmb"

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def fetch(self) -> list[RepoRate]:
        """Son 7 günün TCMB repo verilerini çekip listele."""
        end = dt.date.today()
        start = end - dt.timedelta(days=7)

        series_str = "-".join(SERIES.keys())
        url = (
            f"{EVDS_BASE_URL}/series={series_str}"
            f"&startDate={start.strftime('%d-%m-%Y')}"
            f"&endDate={end.strftime('%d-%m-%Y')}"
            f"&type=json&aggregationTypes=last"
        )
        headers = {"key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise CollectorError(self.name, f"HTTP hatası: {exc}") from exc
        except ValueError as exc:
            raise CollectorError(self.name, f"JSON parse hatası: {exc}") from exc

        return self._parse_rates(data)

    @staticmethod
    def _parse_rates(data: dict) -> list[RepoRate]:
        """EVDS yanıtını RepoRate listesine dönüştür."""
        rates: list[RepoRate] = []
        for item in data.get("items", []):
            tarih_str = item.get("Tarih", "")
            try:
                rate_date = dt.datetime.strptime(tarih_str, "%d-%m-%Y").date()
            except ValueError:
                continue

            for series_key, (rate_type, maturity) in SERIES.items():
                value = item.get(series_key)
                if value is None or value == "":
                    continue
                try:
                    rate_value = Decimal(str(value))
                except (ValueError, ArithmeticError):
                    continue
                rates.append(
                    RepoRate(
                        type=rate_type,
                        maturity=maturity,
                        rate=rate_value,
                        date=rate_date,
                    )
                )
        return rates
