"""BIST (Borsa İstanbul) collector.

DİBS (Devlet İç Borçlanma Senetleri) ve kira sertifikası (sukuk) verilerini
public web sayfalarından scraping ile çeker.

NOT: Scraping kırılgandır; sayfa yapısı değişirse bu modülün güncellenmesi
gerekir. Bu yüzden hata durumunda boş liste döner, exception fırlatmaz.
"""
import datetime as dt
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import BondData, SukukData


BOND_URL = "https://www.borsaistanbul.com/tr/sayfa/3037/bond-data"
SUKUK_URL = "https://www.borsaistanbul.com/tr/sayfa/3038/sukuk-data"


class BistCollector(BaseCollector):
    """BIST tahvil ve sukuk verilerini çeker."""

    name = "bist"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> tuple[list[BondData], list[SukukData]]:
        """DİBS ve sukuk verilerini paralel çek."""
        bonds = await self._fetch_bonds()
        sukuks = await self._fetch_sukuks()
        return bonds, sukuks

    async def _fetch_bonds(self) -> list[BondData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(BOND_URL)
                response.raise_for_status()
                return self._parse_bonds(response.text)
        except (httpx.HTTPError, ValueError):
            return []

    async def _fetch_sukuks(self) -> list[SukukData]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(SUKUK_URL)
                response.raise_for_status()
                return self._parse_sukuks(response.text)
        except (httpx.HTTPError, ValueError):
            return []

    @staticmethod
    def _parse_bonds(html: str) -> list[BondData]:
        """HTML tablosundan tahvil verilerini ayrıştır."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "bondTable"}) or soup.find("table")
        if table is None:
            return []

        bonds: list[BondData] = []
        today = dt.datetime.now().date()
        for row in table.find_all("tr")[1:]:  # başlığı atla
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 5:
                continue
            try:
                bonds.append(
                    BondData(
                        isin=cells[0],
                        maturity_date=dt.datetime.strptime(
                            cells[1], "%d.%m.%Y"
                        ).date(),
                        coupon_rate=Decimal(cells[2]),
                        yield_rate=Decimal(cells[3]),
                        price=Decimal(cells[4]),
                        date=today,
                    )
                )
            except (ValueError, ArithmeticError):
                continue
        return bonds

    @staticmethod
    def _parse_sukuks(html: str) -> list[SukukData]:
        """HTML tablosundan sukuk verilerini ayrıştır."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "sukukTable"}) or soup.find("table")
        if table is None:
            return []

        sukuks: list[SukukData] = []
        today = dt.datetime.now().date()
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 5:
                continue
            try:
                sukuks.append(
                    SukukData(
                        isin=cells[0],
                        issuer="Hazine",
                        maturity_date=dt.datetime.strptime(
                            cells[1], "%d.%m.%Y"
                        ).date(),
                        yield_rate=Decimal(cells[3]),
                        price=Decimal(cells[4]),
                        date=today,
                    )
                )
            except (ValueError, ArithmeticError):
                continue
        return sukuks
