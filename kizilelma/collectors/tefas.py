"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) collector.

TEFAS'ın resmi API'si için ``tefas-crawler`` paketini kullanıyoruz. Doğrudan
``https://www.tefas.gov.tr/api/DB/BindHistoryInfo`` çağrısı WAF tarafından
zaman zaman HTML hata sayfasıyla reddediliyor ("Request Rejected") ve bu da
"JSON parse hatası: Expecting value: line 1 column 1 (char 0)" şeklinde
karşımıza çıkıyordu.

``tefas-crawler`` paketi:
- Aynı verileri ``fundturkey.com.tr`` yansısı üzerinden çekiyor (WAF daha yumuşak)
- Bot/rate-limit tespitinde otomatik retry yapıyor
- Fiyat, portföy dağılımı, tedavül pay sayısı gibi alanları şemaya uyumlu döner

Not: TEFAS'ın BindComparisonFundReturns endpoint'i (getiri yüzdeleri) agresif
WAF koruması altında olduğu için şu an getiri alanları (``return_1d`` vb.)
boş bırakılıyor. İleride bu bilgi gerekirse başka bir kaynak eklenecek.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from decimal import Decimal
from typing import Any, Optional

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import FundData

logger = logging.getLogger(__name__)


# Fon adından basit kategori çıkarımı için anahtar kelimeler (öncelik sıralı).
# Türkçe upper() sorunları (İ/I) yüzünden anahtarlar normalize (noktasız I/i -> I)
# ve büyük harf olarak tutulur. Başlığı karşılaştırırken aynı normalizasyonu
# ``_normalize`` ile uygularız.
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    # Türkçe anahtarlar
    ("PARA PIYASASI", "Para Piyasası Fonu"),
    ("KISA VADELI BORCLANMA", "Kısa Vadeli Borçlanma Araçları Fonu"),
    ("BORCLANMA ARACLARI", "Borçlanma Araçları Fonu"),
    ("HISSE SENEDI", "Hisse Senedi Fonu"),
    ("KATILIM", "Katılım Fonu"),
    ("ALTIN", "Altın Fonu"),
    ("KIYMETLI MADEN", "Kıymetli Madenler Fonu"),
    ("FON SEPETI", "Fon Sepeti Fonu"),
    ("DEGISKEN", "Değişken Fon"),
    ("KARMA", "Karma Fon"),
    ("ENDEKS", "Endeks Fonu"),
    ("BYF", "Borsa Yatırım Fonu"),
    # İngilizce karşılıkları (TEFAS'taki bazı fon adları İngilizce'dir)
    ("MONEY MARKET", "Para Piyasası Fonu"),
    ("SHORT TERM DEBT", "Kısa Vadeli Borçlanma Araçları Fonu"),
    ("DEBT INSTRUMENT", "Borçlanma Araçları Fonu"),
    ("EQUITY", "Hisse Senedi Fonu"),
    ("STOCK FUND", "Hisse Senedi Fonu"),
    ("PARTICIPATION", "Katılım Fonu"),
    ("GOLD", "Altın Fonu"),
    ("PRECIOUS METAL", "Kıymetli Madenler Fonu"),
    ("FUND OF FUND", "Fon Sepeti Fonu"),
    ("MULTI-ASSET", "Değişken Fon"),
    ("VARIABLE", "Değişken Fon"),
    ("MIXED", "Karma Fon"),
    ("INDEX FUND", "Endeks Fonu"),
]


_TR_UPPER_MAP = str.maketrans(
    {
        "ç": "C", "Ç": "C",
        "ğ": "G", "Ğ": "G",
        "ı": "I", "İ": "I",
        "ö": "O", "Ö": "O",
        "ş": "S", "Ş": "S",
        "ü": "U", "Ü": "U",
    }
)


def _normalize(text: str) -> str:
    """Türkçe harfleri ASCII karşılıklarına çevirip büyük harfe getirir."""
    return text.translate(_TR_UPPER_MAP).upper()


class TefasCollector(BaseCollector):
    """TEFAS fonlarının günlük verilerini çeker."""

    name = "tefas"

    def __init__(
        self,
        timeout: float = 30.0,
        max_lookback_days: int = 7,
        crawler_factory: Optional[Any] = None,
    ) -> None:
        """
        Args:
            timeout: Kullanılmıyor (tefas-crawler requests'in kendi timeout'unu
                kullanıyor). Geriye dönük uyumluluk için tutuluyor.
            max_lookback_days: Bugünden geriye doğru en fazla kaç gün veri
                aranacak. TEFAS yalnızca iş günü verisi yayınladığından hafta
                sonu ve tatil günlerinde birkaç gün geri gitmemiz gerekir.
            crawler_factory: Test ve DI için ``tefas.Crawler`` benzeri bir
                callable. None verilirse gerçek ``tefas.Crawler`` kullanılır.
        """
        self.timeout = timeout
        self.max_lookback_days = max_lookback_days
        self._crawler_factory = crawler_factory

    async def fetch(self) -> list[FundData]:
        """Bugüne en yakın iş gününe ait tüm fonların verisini döndürür."""
        try:
            return await asyncio.to_thread(self._fetch_sync)
        except CollectorError:
            raise
        except Exception as exc:  # pragma: no cover - savunma amaçlı
            logger.exception("[tefas] Beklenmeyen hata")
            raise CollectorError(self.name, f"Beklenmeyen hata: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Senkron yardımcılar (thread içinde çalıştırılır)
    # ------------------------------------------------------------------ #
    def _fetch_sync(self) -> list[FundData]:
        crawler = self._build_crawler()

        today = dt.date.today()
        last_error: Optional[Exception] = None

        # Hafta sonu/tatil ihtimaline karşı birkaç gün geri giderek dene.
        for days_back in range(0, self.max_lookback_days + 1):
            candidate = today - dt.timedelta(days=days_back)
            if candidate.weekday() >= 5:  # Cumartesi/Pazar
                continue

            date_str = candidate.strftime("%Y-%m-%d")
            try:
                df = crawler.fetch(
                    start=date_str,
                    end=date_str,
                    columns=["date", "code", "title", "price", "market_cap"],
                )
            except Exception as exc:
                # tefas-crawler ağ/WAF hatalarını çoğunlukla kendi retry eder,
                # yine de son savunma olarak yakalıyoruz.
                logger.warning(
                    "[tefas] %s için veri çekilemedi: %s", date_str, exc
                )
                last_error = exc
                continue

            if df is None or len(df) == 0:
                logger.info(
                    "[tefas] %s günü için veri yok, bir önceki iş gününü deniyorum",
                    date_str,
                )
                continue

            logger.info(
                "[tefas] %s için %d fon kaydı alındı", date_str, len(df)
            )
            funds: list[FundData] = []
            skipped = 0
            for row in df.to_dict(orient="records"):
                fund = self._row_to_fund(row)
                if fund is None:
                    skipped += 1
                    continue
                funds.append(fund)
            if skipped:
                logger.info(
                    "[tefas] %d fon geçersiz fiyat/veri nedeniyle atlandı",
                    skipped,
                )
            return funds

        if last_error is not None:
            raise CollectorError(
                self.name,
                f"Son {self.max_lookback_days} iş gününde veri çekilemedi: {last_error}",
            )
        raise CollectorError(
            self.name,
            f"Son {self.max_lookback_days} iş gününde TEFAS boş döndü",
        )

    def _build_crawler(self) -> Any:
        if self._crawler_factory is not None:
            return self._crawler_factory()
        # Gerçek crawler'ı sadece ihtiyaç olunca import et (test izolasyonu için).
        from tefas import Crawler  # type: ignore[import-not-found]

        return Crawler()

    # ------------------------------------------------------------------ #
    # Satır dönüştürme
    # ------------------------------------------------------------------ #
    @classmethod
    def _row_to_fund(cls, row: dict[str, Any]) -> Optional[FundData]:
        """Bir DataFrame satırını ``FundData``'ya dönüştürür.

        TEFAS bazen kapalı veya yeni kurulan fonlar için ``price=0`` döner;
        bu satırlar sessizce atlanır (``None`` döndürülür). Tek bir bozuk satır
        tüm toplama işini kırmamalıdır.
        """
        code = str(row["code"]).strip()
        title = str(row["title"]).strip()
        price_raw = row["price"]
        date_raw = row["date"]

        try:
            price = Decimal(str(price_raw))
        except (ArithmeticError, ValueError):
            logger.debug("[tefas] %s: fiyat parse edilemedi (%r)", code, price_raw)
            return None
        if price <= 0:
            # TEFAS kapalı/yeni kurulmuş fonlar için 0 dönebilir.
            logger.debug("[tefas] %s: fiyat 0 veya negatif, atlanıyor", code)
            return None

        date = _coerce_date(date_raw)
        title_norm = _normalize(title)
        is_qualified = "SERBEST" in title_norm or "NITELIKLI" in title_norm

        return FundData(
            code=code,
            name=title,
            category=_infer_category(title_norm, is_qualified),
            price=price,
            date=date,
            return_1d=None,
            return_1w=None,
            return_1m=None,
            return_3m=None,
            return_6m=None,
            return_1y=None,
            is_qualified_investor=is_qualified,
        )


# ---------------------------------------------------------------------- #
# Yardımcı saf fonksiyonlar
# ---------------------------------------------------------------------- #
def _coerce_date(value: Any) -> dt.date:
    """Çeşitli tarih temsillerini ``datetime.date``'e dönüştürür."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        # tefas-crawler "YYYY-MM-DD" döndürür; TEFAS'ın eski formatı "dd.MM.yyyy".
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return dt.datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    raise CollectorError("tefas", f"Tanınmayan tarih formatı: {value!r}")


def _infer_category(title_norm: str, is_qualified: bool) -> str:
    """Fon adından (normalize edilmiş başlıktan) kaba bir kategori çıkarır."""
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in title_norm:
            if is_qualified and "SERBEST" not in _normalize(category):
                return f"{category} (Serbest)"
            return category
    return "Serbest Fon" if is_qualified else "Diğer"
