"""Makro ekonomik veri collector.

Döviz kurları, altın, BIST endeksleri ve emtia verilerini toplar.
Kaynak: doviz.com (anahtarsız scraping).

Tasarım:
    - Tek bir HTTP isteği (ana sayfa) ile tüm temel veriler çekiliyor.
      Doviz.com ana sayfasında hem döviz, hem altın (gram-altin, ons),
      hem BIST, hem brent — hepsi aynı yerde, `data-socket-attr="s"`
      ('satış' / yatırımcının gördüğü anlık fiyat).
    - Emtia ve BIST 30 için ayrıca ek sayfalar deneniyor (opsiyonel).
    - Bir kategori başarısız olursa diğerleri etkilenmez.
    - Tüm scraping çökerse fallback (sabit değerler) döner.
    - Hiçbir durumda exception fırlatmaz.

Sayı parse: TR formatı '12.345,67' -> 12345.67. '$' ve '%' önekleri temizlenir.
"""
import datetime as dt
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx

from kizilelma.collectors.base import BaseCollector
from kizilelma.models import MacroData


logger = logging.getLogger(__name__)


# Doviz.com ana sayfası — tüm temel veriler burada bulunabilir.
DOVIZ_HOMEPAGE = "https://www.doviz.com/"
# Subdomain'ler (ek/yedek)
DOVIZ_GOLD_URL = "https://altin.doviz.com/"
DOVIZ_BIST_URL = "https://borsa.doviz.com/"
DOVIZ_COMMODITY_URL = "https://www.doviz.com/emtia"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Doğru attribute önceliği: 's' (satış) > 'last' > 'bid'
# 's' yatırımcının görsel olarak gördüğü "anlık fiyat" — doviz.com'un
# tüm sayfalarında tutarlı.
PRICE_ATTRS = ("s", "last", "bid")


def _build_patterns(socket_key: str, attr: str) -> list[re.Pattern[str]]:
    """Belirli sembol+attr için regex pattern listesi.

    HTML şablonları farklı sırada gelebilir; iki yönü de deneriz.
    """
    safe_key = re.escape(socket_key)
    safe_attr = re.escape(attr)
    return [
        re.compile(
            rf'data-socket-key="{safe_key}"[^>]*data-socket-attr="{safe_attr}"'
            rf'[^>]*>([^<]+)<',
            re.IGNORECASE,
        ),
        re.compile(
            rf'data-socket-attr="{safe_attr}"[^>]*data-socket-key="{safe_key}"'
            rf'[^>]*>([^<]+)<',
            re.IGNORECASE,
        ),
    ]


def _clean_number(raw: str) -> Optional[Decimal]:
    """Ham metni Decimal'e çevir.

    - '$', '%', '₺' gibi önekleri temizler
    - TR binlik nokta + ondalık virgül: '12.345,67' -> 12345.67
    - Sadece nokta varsa: zaten ondalık ('45.35')
    """
    if not raw:
        return None
    # Para birimi sembolleri ve boşlukları sil
    cleaned = re.sub(r'[^\d,.\-]', '', raw.strip())
    if not cleaned:
        return None

    # Hem nokta hem virgül varsa: nokta binlik, virgül ondalık (TR)
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Sadece virgül varsa ondalık ayracı
        cleaned = cleaned.replace(",", ".")

    try:
        value = Decimal(cleaned)
        if value > 0:
            return value
    except (InvalidOperation, ValueError):
        pass
    return None


def _extract_value(html: str, socket_key: str) -> Optional[Decimal]:
    """HTML'den verilen sembolün anlık değerini çek.

    Önce 's' (satış), bulamazsa 'last', bulamazsa 'bid' dener.
    """
    for attr in PRICE_ATTRS:
        for pattern in _build_patterns(socket_key, attr):
            match = pattern.search(html)
            if not match:
                continue
            value = _clean_number(match.group(1))
            if value is not None:
                return value
    return None


class MacroCollector(BaseCollector):
    """Makro ekonomik verileri toplar (döviz, altın, BIST, emtia)."""

    name = "macro"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> list[MacroData]:
        """Tüm makro verileri topla.

        Önce ana sayfadan (tek istek) tüm verileri çekmeye çalışır; ana
        sayfada bulunmayan semboller için subdomain'lere ek istek atar.
        """
        results: list[MacroData] = []
        today = dt.date.today()
        seen: set[str] = set()

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                # 1. Ana sayfa — tek istekte ~6 sembol çekilir
                try:
                    homepage_html = await self._get(client, DOVIZ_HOMEPAGE)
                    results.extend(
                        self._parse_homepage(homepage_html, today, seen)
                    )
                except Exception as exc:
                    logger.warning(f"Macro: ana sayfa hatası: {exc}")

                # 2. BIST 30 ana sayfada genelde yok, BIST sayfasından dene
                if "BIST30" not in seen:
                    try:
                        bist_html = await self._get(client, DOVIZ_BIST_URL)
                        results.extend(
                            self._parse_bist_extras(bist_html, today, seen)
                        )
                    except Exception as exc:
                        logger.warning(f"Macro: BIST sayfası hatası: {exc}")

                # 3. Brent ana sayfada genelde olur ama yoksa emtia sayfasını dene
                if "BRENT" not in seen:
                    try:
                        emtia_html = await self._get(client, DOVIZ_COMMODITY_URL)
                        results.extend(
                            self._parse_commodity_extras(emtia_html, today, seen)
                        )
                    except Exception as exc:
                        logger.warning(f"Macro: emtia sayfası hatası: {exc}")
        except Exception as exc:
            logger.warning(f"Macro fetch genel hatası: {exc}")

        # Hiç veri yoksa fallback
        if not results:
            logger.info("Macro: tüm scraping başarısız, fallback verileri kullanılıyor")
            results = self._fallback_data(today)

        return results

    @staticmethod
    async def _get(client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_homepage(
        html: str,
        today: dt.date,
        seen: set[str],
    ) -> list[MacroData]:
        """Ana sayfadan tüm temel sembolleri çek."""
        # (socket_key, symbol, name, currency, category)
        spec: tuple[tuple[str, str, str, str, str], ...] = (
            ("USD", "USDTRY", "Dolar", "TRY", "currency"),
            ("EUR", "EURTRY", "Euro", "TRY", "currency"),
            ("gram-altin", "GOLD_GR", "Gram Altın", "TRY", "commodity"),
            ("ons", "GOLD_OZ", "Ons Altın", "USD", "commodity"),
            ("XU100", "BIST100", "BIST 100", "TRY", "index"),
            ("BRENT", "BRENT", "Brent Petrol", "USD", "commodity"),
        )
        results: list[MacroData] = []
        for socket_key, symbol, name, currency, category in spec:
            if symbol in seen:
                continue
            value = _extract_value(html, socket_key)
            if value is None:
                continue
            results.append(
                MacroData(
                    symbol=symbol,
                    name=name,
                    value=value,
                    currency=currency,
                    category=category,
                    date=today,
                )
            )
            seen.add(symbol)
        return results

    @staticmethod
    def _parse_bist_extras(
        html: str,
        today: dt.date,
        seen: set[str],
    ) -> list[MacroData]:
        """BIST sayfasından BIST 30 (ve eksikse BIST 100) çek."""
        results: list[MacroData] = []
        # BIST 30 — ana sayfada genelde yok
        if "BIST30" not in seen:
            value = _extract_value(html, "XU030")
            if value is not None:
                results.append(
                    MacroData(
                        symbol="BIST30",
                        name="BIST 30",
                        value=value,
                        currency="TRY",
                        category="index",
                        date=today,
                    )
                )
                seen.add("BIST30")
        # BIST 100 yedek — ana sayfada bulamadıysak
        if "BIST100" not in seen:
            value = _extract_value(html, "XU100")
            if value is not None:
                results.append(
                    MacroData(
                        symbol="BIST100",
                        name="BIST 100",
                        value=value,
                        currency="TRY",
                        category="index",
                        date=today,
                    )
                )
                seen.add("BIST100")
        return results

    @staticmethod
    def _parse_commodity_extras(
        html: str,
        today: dt.date,
        seen: set[str],
    ) -> list[MacroData]:
        """Emtia sayfasından Brent (yedek)."""
        results: list[MacroData] = []
        if "BRENT" not in seen:
            value = _extract_value(html, "BRENT")
            if value is not None:
                results.append(
                    MacroData(
                        symbol="BRENT",
                        name="Brent Petrol",
                        value=value,
                        currency="USD",
                        category="commodity",
                        date=today,
                    )
                )
                seen.add("BRENT")
        return results

    @staticmethod
    def _fallback_data(today: dt.date) -> list[MacroData]:
        """Tüm scraping başarısızsa kullanılacak sabit fallback değerler.

        Bu yalnızca 'hiç veri yok' durumunu önlemek içindir. Production'da
        scraping çalışmıyorsa bu değerler elle güncellenmelidir.
        """
        return [
            MacroData(
                symbol="USDTRY",
                name="Dolar",
                value=Decimal("45.00"),
                currency="TRY",
                category="currency",
                date=today,
            ),
            MacroData(
                symbol="EURTRY",
                name="Euro",
                value=Decimal("48.50"),
                currency="TRY",
                category="currency",
                date=today,
            ),
            MacroData(
                symbol="GOLD_GR",
                name="Gram Altın",
                value=Decimal("6800"),
                currency="TRY",
                category="commodity",
                date=today,
            ),
            MacroData(
                symbol="GOLD_OZ",
                name="Ons Altın",
                value=Decimal("4700"),
                currency="USD",
                category="commodity",
                date=today,
            ),
            MacroData(
                symbol="BIST100",
                name="BIST 100",
                value=Decimal("15000"),
                currency="TRY",
                category="index",
                date=today,
            ),
        ]
