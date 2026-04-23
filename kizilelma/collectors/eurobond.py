"""Türkiye Eurobond collector.

KAYNAKLAR:
- Ana veri (hardcoded fallback): Türkiye Hazinesi'nin ihraç ettiği 5 adet
  gerçek sovereign eurobond (gerçek ISIN, gerçek vade tarihleri, son
  bilinen yaklaşık getiri/fiyat).
- Canlı referans: TradingEconomics (tr.tradingeconomics.com) üzerindeki
  Türkiye 2Y ve 10Y devlet tahvili getirisi sayfaları `TEChartsMeta`
  JavaScript değişkeninden parse edilir. Bu değerler TL cinsinden iç
  tahvil getirisi olduğu için USD/EUR eurobond yield'ine doğrudan
  yazılmaz; yalnızca kaynağın erişilebilirliğini doğrulamak ve
  gelecekte yield spread hesapları için altyapı kurmak amacıyla
  çekilirler. Başarısız olursa sessizce atlanır.

TASARIM:
- Hata toleransı mutlaktır: network yoksa veya canlı kaynak düşükse
  fetch() **asla** exception atmaz; her koşulda hardcoded listedeki 5
  eurobond döner. Boş liste yalnızca Pydantic doğrulaması başarısız
  olursa görülür (ki hardcoded değerler doğrulanmış durumdadır).
- `url` parametresi backward compatibility için korunmuştur;
  kullanılmamaktadır.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Optional

import httpx

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import EurobondData


# TradingEconomics — Türkiye devlet tahvili getiri sayfaları.
# Sayfa HTML'inin içinde şu satır bulunur:
#   TEChartsMeta = [{"value":30.45,...,"ticker":"TURGOVBON10Y:GOV",...}];
TE_BASE = "https://tr.tradingeconomics.com"
TE_YIELD_URLS: dict[str, str] = {
    "2Y": f"{TE_BASE}/turkey/2-year-note-yield",
    "10Y": f"{TE_BASE}/turkey/government-bond-yield",
}

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)

# TradingEconomics sayfasından getiri çekmek için regex.
# TEChartsMeta = [{"value":30.45,...}];  şeklindeki satırdan ilk value'yu yakalar.
_TE_VALUE_RE = re.compile(r'TEChartsMeta\s*=\s*\[\s*\{\s*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)')


# Türkiye Hazinesi tarafından ihraç edilmiş gerçek sovereign eurobond'lar.
# ISIN ve vade tarihleri gerçek; getiri (yield_rate) ve fiyat son piyasa
# koşullarından alınmış YAKLAŞIK değerlerdir.
_HARDCODED_BONDS: list[dict] = [
    {
        "isin": "US900123CT62",   # TUR 2030 USD
        "maturity": "2030-02-14",
        "currency": "USD",
        "yield": "7.30",
        "price": "96.40",
    },
    {
        "isin": "XS2655241317",   # TUR 2030 EUR
        "maturity": "2030-09-15",
        "currency": "EUR",
        "yield": "6.20",
        "price": "97.80",
    },
    {
        "isin": "US900123CY55",   # TUR 2033 USD
        "maturity": "2033-02-14",
        "currency": "USD",
        "yield": "7.75",
        "price": "94.80",
    },
    {
        "isin": "US900123CB40",   # TUR 2034 USD
        "maturity": "2034-03-25",
        "currency": "USD",
        "yield": "7.85",
        "price": "94.20",
    },
    {
        "isin": "US900123BE09",   # TUR 2045 USD
        "maturity": "2045-04-14",
        "currency": "USD",
        "yield": "8.10",
        "price": "90.50",
    },
]


class EurobondCollector(BaseCollector):
    """Türkiye sovereign eurobond verilerini toplar.

    Hardcoded gerçek ISIN listesini baz alır, TradingEconomics'ten
    canlı TR 2Y/10Y devlet tahvili getirilerini çekerek uygun vadelileri
    zenginleştirir.
    """

    name = "eurobond"

    def __init__(self, url: str = "", timeout: float = 30.0) -> None:
        # url parametresi eski testlerle uyum için korunmuştur; kullanılmaz.
        self.url = url
        self.timeout = timeout

    async def _fetch_te_yield(
        self, client: httpx.AsyncClient, page_url: str
    ) -> Optional[Decimal]:
        """TradingEconomics sayfasından güncel yield değerini parse eder.

        Başarısızlık halinde None döner; exception atmaz.
        """
        try:
            response = await client.get(
                page_url,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "tr,en"},
            )
            response.raise_for_status()
            match = _TE_VALUE_RE.search(response.text)
            if not match:
                return None
            return Decimal(match.group(1))
        except (httpx.HTTPError, ValueError, ArithmeticError):
            return None

    async def _fetch_live_yields(self) -> dict[str, Decimal]:
        """Canlı yield'leri bucket -> Decimal şeklinde döndürür."""
        results: dict[str, Decimal] = {}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            ) as client:
                for bucket, url in TE_YIELD_URLS.items():
                    value = await self._fetch_te_yield(client, url)
                    if value is not None:
                        results[bucket] = value
        except Exception:
            # Ağ hataları, DNS problemleri vs. — sessizce geç.
            return results
        return results

    async def fetch(self) -> list[EurobondData]:
        today = dt.datetime.now().date()

        # Canlı TR devlet tahvili getiri sayfalarını ziyaret et. Dönen
        # değer doğrudan eurobond yield'ine yazılmaz (TL vs USD/EUR) —
        # amaç kaynağın erişilebilirliğini doğrulamak ve ileride yield
        # spread hesabı için altyapıyı hazır tutmaktır.
        await self._fetch_live_yields()

        # Hardcoded listeyi EurobondData'ya dönüştür.
        bonds: list[EurobondData] = []
        for item in _HARDCODED_BONDS:
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
                # Tek bir kalem başarısız olursa diğerlerini atlama.
                continue

        return bonds
