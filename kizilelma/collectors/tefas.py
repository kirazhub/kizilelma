"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) collector.

Bu collector, TEFAS'ın resmi JSON API'sine doğrudan bağlanır:
``POST https://www.tefas.gov.tr/api/DB/BindHistoryInfo``

Önceki sürüm ``tefas-crawler`` paketini (fundturkey.com.tr yansısını) kullanıyordu,
fakat GitHub Actions runner'larının IP'leri yansı tarafından bot olarak
algılanıp "Max attempt limit reached" hatasıyla bloklanıyordu. Resmi TEFAS
endpoint'i, doğru tarayıcı benzeri header'lar ile hem lokal hem GitHub
Actions'tan güvenilir şekilde çağrılabiliyor.

Koruma mekanizmaları:
- Her istekte rastgele bir modern tarayıcı User-Agent'ı seçilir.
- Ana sayfaya önce GET atılıp session cookie alınır (bazı WAF kuralları için).
- İstek başarısız olursa 2-4 saniye rastgele gecikme ile yeniden denenir.
- Hafta sonu / tatil günlerini atlamak için geriye doğru 7 iş günü denenir.

Not: ``BindHistoryInfo`` endpoint'i tarihsel fiyat, tedavül pay sayısı,
portföy büyüklüğü gibi alanları döner; ancak ``GETIRI1G``, ``GETIRI1H`` gibi
getiri alanlarını döndürmez. Bu alanlar ileride farklı bir endpoint ile
doldurulabilir; şimdilik ``None`` bırakılıyor (mevcut davranışla aynı).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import FundData

logger = logging.getLogger(__name__)


# TEFAS resmi endpoint'i — tarihsel fon bilgisi (fiyat, tedavül, portföy).
TEFAS_API_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
# Session cookie almak için ziyaret ettiğimiz ana sayfa.
TEFAS_HOME_URL = "https://www.tefas.gov.tr/TarihselVeriler.aspx"


# Rastgele User-Agent rotasyonu — tek bir sabit UA bot tespitini kolaylaştırır.
_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
)


def _build_headers() -> dict[str, str]:
    """TEFAS API için tarayıcı benzeri istek başlıkları üretir."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": TEFAS_HOME_URL,
        "Origin": "https://www.tefas.gov.tr",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }


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
    """TEFAS fonlarının günlük verilerini çeker (resmi API + retry)."""

    name = "tefas"

    def __init__(
        self,
        timeout: float = 60.0,
        max_lookback_days: int = 7,
        max_retries: int = 3,
        retry_delay_range: tuple[float, float] = (2.0, 4.0),
        client_factory: Optional[Any] = None,
    ) -> None:
        """
        Args:
            timeout: HTTP istek zaman aşımı (saniye).
            max_lookback_days: Bugünden geriye doğru en fazla kaç gün veri
                aranacak. TEFAS yalnızca iş günü verisi yayınladığından hafta
                sonu ve tatil günlerinde birkaç gün geri gitmemiz gerekir.
            max_retries: Tek bir gün için kaç kez tekrar denenecek.
            retry_delay_range: Denemeler arası rastgele gecikme aralığı (saniye).
            client_factory: Test için httpx.AsyncClient üretici callable.
                None verilirse gerçek ``httpx.AsyncClient`` kullanılır.
        """
        self.timeout = timeout
        self.max_lookback_days = max_lookback_days
        self.max_retries = max_retries
        self.retry_delay_range = retry_delay_range
        self._client_factory = client_factory

    async def fetch(self) -> list[FundData]:
        """Bugüne en yakın iş gününe ait tüm fonların verisini döndürür."""
        today = dt.date.today()
        last_error: Optional[Exception] = None

        for days_back in range(0, self.max_lookback_days + 1):
            candidate = today - dt.timedelta(days=days_back)
            if candidate.weekday() >= 5:  # Cumartesi/Pazar
                continue

            try:
                funds = await self._fetch_for_date(candidate)
            except Exception as exc:
                logger.warning(
                    "[tefas] %s için veri çekilemedi: %s",
                    candidate.isoformat(),
                    exc,
                )
                last_error = exc
                continue

            if not funds:
                logger.info(
                    "[tefas] %s günü için veri yok, bir önceki iş gününü deniyorum",
                    candidate.isoformat(),
                )
                continue

            logger.info(
                "[tefas] %s için %d fon kaydı alındı",
                candidate.isoformat(),
                len(funds),
            )
            return funds

        if last_error is not None:
            raise CollectorError(
                self.name,
                f"Son {self.max_lookback_days} iş gününde veri çekilemedi: "
                f"{last_error}",
            )
        raise CollectorError(
            self.name,
            f"Son {self.max_lookback_days} iş gününde TEFAS boş döndü",
        )

    # ------------------------------------------------------------------ #
    # Tek bir gün için retry'lı API çağrısı
    # ------------------------------------------------------------------ #
    async def _fetch_for_date(self, target: dt.date) -> list[FundData]:
        """Belirli bir gün için TEFAS API'sinden veri çeker (retry ile)."""
        payload = {
            "fontip": "YAT",
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

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                data = await self._request(payload)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                low, high = self.retry_delay_range
                delay = random.uniform(low, high)
                logger.warning(
                    "[tefas] %s deneme %d/%d başarısız (%s), %.1fs sonra tekrar",
                    target.isoformat(),
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            rows = data.get("data") or []
            if not rows:
                # API geçerli ama veri boş — geriye düşsün.
                return []

            funds: list[FundData] = []
            skipped = 0
            for item in rows:
                fund = self._row_to_fund(item)
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

        raise CollectorError(
            self.name,
            f"{target.isoformat()} için {self.max_retries} deneme başarısız: "
            f"{last_error}",
        )

    async def _request(self, payload: dict[str, str]) -> dict[str, Any]:
        """TEFAS API'sine tek bir POST isteği atar, JSON döner."""
        async with self._make_client() as client:
            # Bazı WAF kuralları önce ana sayfanın ziyaret edilmesini bekler.
            # Cookie kritik olmasa bile bu istek "gerçek tarayıcı" sinyali verir.
            try:
                await client.get(TEFAS_HOME_URL)
            except Exception as exc:  # pragma: no cover - cookie kritik değil
                logger.debug("[tefas] ana sayfa isinmadi: %s", exc)

            response = await client.post(TEFAS_API_URL, data=payload)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                # WAF HTML hata sayfası döndürdüyse JSON parse başarısız olur.
                preview = response.text[:200].replace("\n", " ")
                raise CollectorError(
                    self.name,
                    f"JSON çözümlenemedi, cevabın başı: {preview!r}",
                ) from exc

    def _make_client(self) -> httpx.AsyncClient:
        """httpx.AsyncClient üretir (test için override edilebilir)."""
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers=_build_headers(),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    # Satır dönüştürme
    # ------------------------------------------------------------------ #
    @classmethod
    def _row_to_fund(cls, row: dict[str, Any]) -> Optional[FundData]:
        """Tek bir TEFAS JSON kaydını ``FundData``'ya dönüştürür.

        TEFAS bazen kapalı veya yeni kurulan fonlar için ``FIYAT=0`` döner;
        bu satırlar sessizce atlanır (``None`` döndürülür). Tek bir bozuk satır
        tüm toplama işini kırmamalıdır.
        """
        code = str(row.get("FONKODU", "")).strip()
        title = str(row.get("FONUNVAN", "")).strip()
        if not code or not title:
            logger.debug("[tefas] eksik kod/ad, satır atlanıyor: %r", row)
            return None

        price_raw = row.get("FIYAT")
        try:
            price = Decimal(str(price_raw))
        except (InvalidOperation, ValueError, TypeError):
            logger.debug("[tefas] %s: fiyat parse edilemedi (%r)", code, price_raw)
            return None
        if price <= 0:
            logger.debug("[tefas] %s: fiyat 0 veya negatif, atlanıyor", code)
            return None

        try:
            date = _coerce_date(row.get("TARIH"))
        except CollectorError:
            logger.debug("[tefas] %s: tarih parse edilemedi (%r)", code, row.get("TARIH"))
            return None

        title_norm = _normalize(title)
        is_qualified = "SERBEST" in title_norm or "NITELIKLI" in title_norm

        # Bazı TEFAS yanıtlarında "FONTUR" / "FONTURACIKLAMA" bulunur; varsa
        # onu tercih et, yoksa addan çıkar.
        category_raw = row.get("FONTURACIKLAMA") or row.get("FONTUR")
        if category_raw:
            category = str(category_raw).strip()
            if is_qualified and "SERBEST" not in _normalize(category):
                category = f"{category} (Serbest)"
        else:
            category = _infer_category(title_norm, is_qualified)

        return FundData(
            code=code,
            name=title,
            category=category,
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
    """Çeşitli tarih temsillerini ``datetime.date``'e dönüştürür.

    TEFAS resmi API'si tarihi milisaniye cinsinden Unix timestamp string'i
    olarak döndürür (örn. ``"1776816000000"``). Eski tefas-crawler ise
    ``"YYYY-MM-DD"`` / ``"dd.MM.yyyy"`` döndürebilir. Her üçünü de destekliyoruz.
    """
    if value is None:
        raise CollectorError("tefas", "Tarih alanı boş")
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(
                float(value) / 1000, tz=dt.timezone.utc
            ).date()
        except (OverflowError, OSError, ValueError) as exc:
            raise CollectorError(
                "tefas", f"Tarih timestamp'i çözümlenemedi: {value!r}"
            ) from exc
    if isinstance(value, str):
        stripped = value.strip()
        # 1) Sayısal timestamp (milisaniye) — TEFAS resmi API formatı
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            try:
                return dt.datetime.fromtimestamp(
                    int(stripped) / 1000, tz=dt.timezone.utc
                ).date()
            except (OverflowError, OSError, ValueError) as exc:
                raise CollectorError(
                    "tefas", f"Tarih timestamp'i çözümlenemedi: {value!r}"
                ) from exc
        # 2) ISO / Türkçe nokta formatı
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return dt.datetime.strptime(stripped, fmt).date()
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
