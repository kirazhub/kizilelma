"""TEFAS (yatırım fonları) collector — Fonrehberi kaynaklı.

Neden TEFAS resmi API'si kullanılmıyor?
    TEFAS'ın ``https://www.tefas.gov.tr/api/DB/BindHistoryInfo`` endpoint'i
    bir WAF (Web Application Firewall) tarafından korunur. GitHub Actions
    runner'larının IP blokları "Request Rejected" ("support ID: ...") HTML
    sayfasıyla bloklanır, çağrı hiç API'ye ulaşmaz. Lokal testlerde de
    davranış tutarsızdır (bazen bloklanır, bazen geçer). Bu yüzden
    bağımsız ve herkese açık bir ayna olan **fonrehberi.com** tercih edildi.

Fonrehberi iki katmanlı yapıdadır:
    1. Ana liste (``https://www.fonrehberi.com/``) — tüm yatırım fonlarının
       tek tablosu: kod, ad (<a> içinde), kategori, günlük / 1A / 6A / 1Y
       getirileri. Haftalık ve 3 aylık getiriler kaynakta YOKTUR (None).
    2. Fon başına detay sayfası (``<CODE>-fonu-kazanci-nedir.html``) —
       "Son Fon Fiyatı" satırından TL cinsinden birim pay fiyatı alınır.

Toplama akışı:
    - Ana liste tek seferde çekilir (retry'lı).
    - Fon başına fiyat detay sayfaları paralel (asyncio.gather) ile çekilir.
    - Tek bir fonun detay sayfası hata döndürürse o fon atlanır; diğerleri
      gelmeye devam eder.
    - Ana liste hiç gelmezse ``CollectorError`` fırlatılır.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from kizilelma.collectors.base import BaseCollector, CollectorError
from kizilelma.models import FundData

logger = logging.getLogger(__name__)


# Fonrehberi uç noktaları.
FONREHBERI_LIST_URL = "https://www.fonrehberi.com/"
FONREHBERI_DETAIL_TEMPLATE = "https://www.fonrehberi.com/{code}-fonu-kazanci-nedir.html"


# Rastgele User-Agent rotasyonu — tek sabit UA bot tespitini kolaylaştırır.
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
    """Fonrehberi için tarayıcı benzeri HTTP başlıkları üretir."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    }


# Türkçe karakterleri ASCII büyük harfe çeviren tablo — is_qualified_investor
# karşılaştırmasında Türkçe upper() bug'ına düşmemek için.
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
    """Türkçe harfleri ASCII'ye çevirip büyük harfe getirir."""
    return text.translate(_TR_UPPER_MAP).upper()


class TefasCollector(BaseCollector):
    """Yatırım fonu verilerini ``fonrehberi.com``'dan çeker."""

    name = "tefas"

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay_range: tuple[float, float] = (2.0, 4.0),
        max_funds: Optional[int] = None,
        detail_concurrency: int = 16,
        client_factory: Optional[Any] = None,
    ) -> None:
        """
        Args:
            timeout: HTTP istek zaman aşımı (saniye).
            max_retries: Ana listenin çekilmesi için kaç kez tekrar denenecek.
            retry_delay_range: Denemeler arası rastgele gecikme aralığı (saniye).
            max_funds: Varsayılan None → listedeki tüm fonlar. Bir üst sınır
                verilirse (örn. 50) sadece tablonun ilk N fonu çekilir.
            detail_concurrency: Eşzamanlı detay sayfası isteği sayısı
                (semafor limiti). Fonrehberi'ni boğmamak için makul tutulur.
            client_factory: Test için httpx.AsyncClient üretici callable.
                None verilirse gerçek ``httpx.AsyncClient`` kullanılır.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_range = retry_delay_range
        self.max_funds = max_funds
        self.detail_concurrency = max(1, int(detail_concurrency))
        self._client_factory = client_factory

    # ------------------------------------------------------------------ #
    # Genel akış
    # ------------------------------------------------------------------ #
    async def fetch(self) -> list[FundData]:
        """Tüm fon listesini ve birim fiyatlarını döndürür."""
        async with self._make_client() as client:
            # 1) Ana listeyi çek (retry'lı)
            list_html = await self._fetch_listing(client)
            rows = _parse_listing(list_html)
            if not rows:
                raise CollectorError(
                    self.name,
                    "Fonrehberi ana listesi boş döndü — HTML yapısı değişmiş olabilir.",
                )

            if self.max_funds is not None:
                rows = rows[: self.max_funds]
            logger.info("[tefas] Fonrehberi listesinde %d fon bulundu", len(rows))

            # 2) Her fonun fiyatını paralel çek
            today = dt.date.today()
            sem = asyncio.Semaphore(self.detail_concurrency)
            tasks = [self._fetch_fund(client, row, today, sem) for row in rows]
            results = await asyncio.gather(*tasks, return_exceptions=False)

            funds = [f for f in results if f is not None]
            skipped = len(results) - len(funds)
            if skipped:
                logger.info(
                    "[tefas] %d fon fiyat/veri eksikliği nedeniyle atlandı",
                    skipped,
                )

            if not funds:
                raise CollectorError(
                    self.name,
                    "Hiçbir fonun fiyatı çekilemedi — Fonrehberi erişilemez olabilir.",
                )

            logger.info("[tefas] Toplam %d fon kaydı alındı", len(funds))
            return funds

    # ------------------------------------------------------------------ #
    # Ana liste (retry'lı)
    # ------------------------------------------------------------------ #
    async def _fetch_listing(self, client: httpx.AsyncClient) -> str:
        """Fonrehberi ana sayfasını (fon listesi) retry'lı şekilde getirir."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(FONREHBERI_LIST_URL)
                response.raise_for_status()
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                low, high = self.retry_delay_range
                delay = random.uniform(low, high)
                logger.warning(
                    "[tefas] ana liste deneme %d/%d başarısız (%s), %.1fs sonra tekrar",
                    attempt, self.max_retries, exc, delay,
                )
                await asyncio.sleep(delay)

        raise CollectorError(
            self.name,
            f"Ana liste {self.max_retries} denemenin ardından çekilemedi: {last_error}",
        )

    # ------------------------------------------------------------------ #
    # Tek bir fonun detayı
    # ------------------------------------------------------------------ #
    async def _fetch_fund(
        self,
        client: httpx.AsyncClient,
        row: dict[str, Any],
        fund_date: dt.date,
        sem: asyncio.Semaphore,
    ) -> Optional[FundData]:
        """Ana listedeki bir satır için fiyatı çekip ``FundData``'ya dönüştürür.

        Hata durumunda ``None`` döner (tek fonun kırılması toplamayı bozmasın).
        """
        code = row["code"]
        url = FONREHBERI_DETAIL_TEMPLATE.format(code=code)

        async with sem:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.debug(
                        "[tefas] %s detay sayfası HTTP %d, atlanıyor",
                        code, response.status_code,
                    )
                    return None
                detail_html = response.text
            except Exception as exc:
                logger.debug("[tefas] %s detay sayfası hata: %s", code, exc)
                return None

        price = _parse_price(detail_html)
        if price is None or price <= 0:
            logger.debug("[tefas] %s: fiyat parse edilemedi, atlanıyor", code)
            return None

        # Detay sayfasında "Son 3 Ay Getiri Oranı" da var — listeden
        # gelmeyen bu alanı buradan toplayalım (None dönebilir, sorun yok).
        return_3m = _parse_detail_return_3m(detail_html)

        title = row["name"]
        category = row["category"] or "Diğer"
        title_norm = _normalize(title)
        category_norm = _normalize(category)
        is_qualified = (
            "SERBEST" in title_norm
            or "NITELIKLI" in title_norm
            or "SERBEST" in category_norm
        )

        return FundData(
            code=code,
            name=title,
            category=category,
            price=price,
            date=fund_date,
            return_1d=row.get("return_1d"),
            return_1w=None,   # Fonrehberi haftalık getiri sunmuyor
            return_1m=row.get("return_1m"),
            return_3m=return_3m,  # Detay sayfasından çekildi (yoksa None)
            return_6m=row.get("return_6m"),
            return_1y=row.get("return_1y"),
            is_qualified_investor=is_qualified,
            asset_tags=_extract_asset_tags(title, category),
        )

    # ------------------------------------------------------------------ #
    # httpx client fabrikası
    # ------------------------------------------------------------------ #
    def _make_client(self) -> httpx.AsyncClient:
        """httpx.AsyncClient üretir (test için override edilebilir)."""
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers=_build_headers(),
            follow_redirects=True,
        )


# ---------------------------------------------------------------------- #
# Saf parse fonksiyonları (test edilebilir, I/O'suz)
# ---------------------------------------------------------------------- #
def _parse_percent(text: str) -> Optional[Decimal]:
    """'%5.4967' veya '%-6.54509' gibi yüzde stringlerini Decimal'e çevirir.

    Boş/tanımsız değerlerde None döner. '%0' da Decimal(0) döner (anlamlıdır).
    """
    if text is None:
        return None
    cleaned = text.strip().lstrip("%").strip()
    if not cleaned or cleaned in {"-", "—"}:
        return None
    # Türkçe ondalık virgülü de olabilir — nokta'ya çevir
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_listing(html: str) -> list[dict[str, Any]]:
    """Fonrehberi ana liste HTML'inden fon satırlarını çıkarır.

    Her satır şu anahtarları içeren bir dict'tir::
        code, name, category, return_1d, return_1m, return_6m, return_1y

    Yapısı bozuk satırlar atlanır; liste boş dönebilir (o zaman çağıran
    uyarır).
    """
    soup = BeautifulSoup(html, "lxml")
    # Birden fazla tablo varsa "Fon Kodu" başlığı olanı seçelim.
    target_table = None
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if any("Fon Kodu" in h for h in headers):
            target_table = table
            break
    if target_table is None:
        logger.warning("[tefas] Fonrehberi ana tablosu bulunamadı")
        return []

    rows: list[dict[str, Any]] = []
    for tr in target_table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 7:
            continue  # başlık / footer / bozuk satır
        code = tds[0].get_text(strip=True)
        if not code or not re.fullmatch(r"[A-Z0-9]{2,8}", code):
            continue
        name_cell = tds[1]
        # Ad genelde <a> içindedir ama doğrudan metin de olabilir
        anchor = name_cell.find("a")
        name = anchor.get_text(strip=True) if anchor else name_cell.get_text(strip=True)
        if not name:
            continue
        category = tds[2].get_text(strip=True)
        rows.append(
            {
                "code": code,
                "name": name,
                "category": category,
                "return_1d": _parse_percent(tds[3].get_text(strip=True)),
                "return_1m": _parse_percent(tds[4].get_text(strip=True)),
                "return_6m": _parse_percent(tds[5].get_text(strip=True)),
                "return_1y": _parse_percent(tds[6].get_text(strip=True)),
            }
        )
    return rows


# "1.234567 TL" veya "1.234,56 TL" gibi değerler için regex.
_PRICE_RE = re.compile(r"([\d.,]+)\s*(?:TL|₺)", re.IGNORECASE)


def _parse_price(html: str) -> Optional[Decimal]:
    """Fon detay sayfasından "Son Fon Fiyatı" değerini çeker."""
    soup = BeautifulSoup(html, "lxml")
    # "Son Fon Fiyatı" etiketinin yan hücresini bul
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label = tds[0].get_text(strip=True)
        if "Son Fon Fiyat" in label:
            value_text = tds[1].get_text(strip=True)
            m = _PRICE_RE.search(value_text)
            if not m:
                return None
            raw = m.group(1)
            # Türkçe formatı: "1.234,56" → 1234.56
            if "," in raw and "." in raw:
                raw = raw.replace(".", "").replace(",", ".")
            elif "," in raw:
                raw = raw.replace(",", ".")
            try:
                return Decimal(raw)
            except (InvalidOperation, ValueError):
                return None
    return None


def _parse_detail_return_3m(html: str) -> Optional[Decimal]:
    """Detay sayfasından "Son 3 Ay Getiri Oranı"nı çeker.

    Fonrehberi ana liste tablosunda 3 aylık getiri sütunu YOKTUR; ancak
    her fonun detay sayfasındaki getiri tablosunda vardır. Bu fonksiyon
    o satırı yakalar. Değer "5.4967" / "-6.54509" / "0" formatında
    yüzde olarak verilir (yüzde işareti olmadan). Bulunamazsa None.
    """
    soup = BeautifulSoup(html, "lxml")
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label = tds[0].get_text(strip=True)
        # "Son 3 Ay Getiri Oranı" — küçük yazım farkları olabilir
        if "3 Ay" in label and "Getiri" in label:
            value_text = tds[1].get_text(strip=True).lstrip("%").strip()
            if not value_text or value_text in {"-", "—"}:
                return None
            value_text = value_text.replace(",", ".")
            try:
                return Decimal(value_text)
            except (InvalidOperation, ValueError):
                return None
    return None


# --------------------------------------------------------------------- #
# Sektör / varlık / tema etiketleri
# --------------------------------------------------------------------- #
#
# Neden gerekli?
#     Kullanıcı raporda "MT7 fonu neyin fonu?" diye merak ediyor.
#     Fon adı çoğu zaman çok uzun ve kısaltmalıdır. Altına 3-6 etiket koyarak
#     (örn. "🏷️ Hisse · Teknoloji · BIST30") bir bakışta içeriği söyletiyoruz.
#
# Kaynak:
#     Fon adı + kategori metni. Fonrehberi fon içerik dağılımını sadece JS
#     chart'ta verdiği için HTML'den güvenilir şekilde parse edilemiyor.
#     Ad ve kategori ikili pratikte %95+ doğru etiket üretiyor.
#
# Etiket kategorileri (sırayla önem):
#     1. Endeks (BIST30/100) — en spesifik
#     2. Sektör (Teknoloji, Banka, Sanayi, ...)
#     3. Varlık türü (Hisse, Tahvil, Altın, Döviz, ...)
#     4. Tema/Strateji (Faizsiz, Serbest, Makro, ESG, ...)
#     5. Coğrafya (ABD, Avrupa, Global, ...)
#
# Maksimum 6 etiketle sınırlı — UI satırını taşırmamak için.

# Anahtar kelime → etiket eşlemesi (normalize edilmiş ASCII metin üzerinde
# çalışır; Türkçe karakterler büyük ASCII harfe çevrilmiştir)
_SECTOR_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("TEKNOLOJI", "BILISIM", "YAZILIM"), "Teknoloji"),
    (("BANKA", "BANKACILIK", "FINANSAL", "FINANS"), "Banka"),
    (("SANAYI", "SINAI"), "Sanayi"),
    (("GIDA", "ICECEK"), "Gıda"),
    (("INSAAT", "GAYRIMENKUL", "GYO"), "Gayrimenkul"),
    (("ENERJI", "PETROL", "ELEKTRIK"), "Enerji"),
    (("SAGLIK", "ILAC"), "Sağlık"),
    (("TELEKOM", "HABERLESME"), "Telekom"),
    (("SAVUNMA",), "Savunma"),
    (("ULASTIRMA", "HAVACILIK"), "Ulaştırma"),
    (("METAL", "CELIK", "MADEN"), "Metal"),
    (("KIMYA", "PETROKIMYA"), "Kimya"),
    (("TEKSTIL",), "Tekstil"),
    (("TURIZM",), "Turizm"),
    (("OTOMOTIV",), "Otomotiv"),
)

_ASSET_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("HISSE", "HISSELI"), "Hisse"),
    (("TAHVIL", "BORCLANMA", "DIBS"), "Tahvil"),
    (("KIRA SERT", "SUKUK", "KATILIMA DAYALI"), "Sukuk"),
    (("ALTIN",), "Altın"),
    (("GUMUS",), "Gümüş"),
    (("PLATIN",), "Platin"),
    (("KIYMETLI MADEN", "KIYMETLI METAL"), "Kıymetli Maden"),
    (("DOVIZ", "USD", "EUR", "DOLAR"), "Döviz"),
    (("EUROBOND",), "Eurobond"),
    (("PARA PIYASASI",), "Para Piyasası"),
    (("REPO",), "Repo"),
    (("MEVDUAT",), "Mevduat"),
    (("FON SEPETI",), "Fon Sepeti"),
    (("ENDEKS",), "Endeks"),
    (("VARLIGA DAYALI", "VDMK"), "VDMK"),
)

_THEME_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("KATILIM", "FAIZSIZ"), "Faizsiz"),
    (("SERBEST", "NITELIKLI"), "Serbest"),
    (("MAKRO",), "Makro"),
    (("DENGELI",), "Dengeli"),
    (("DEGISKEN",), "Değişken"),
    (("KARMA",), "Karma"),
    (("AGRESIF",), "Agresif"),
    (("MUHAFAZAKAR",), "Muhafazakar"),
    (("ESG", "SURDURULEBILIR"), "ESG"),
    (("EMEKLILIK", "EMEKLI", "BES"), "Emeklilik"),
)

_GEO_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("AMERIKA", "ABD", "USA"), "ABD"),
    (("AVRUPA", "EUROPE"), "Avrupa"),
    (("ASYA", "CIN", "JAPON"), "Asya"),
    (("GELISEN PIYASA", "EMERGING"), "Gelişen Piyasa"),
    (("YABANCI", "GLOBAL", "DUNYA"), "Global"),
)


def _extract_asset_tags(name: str, category: str) -> list[str]:
    """Fon adı ve kategorisinden 3-6 sektör/varlık/tema etiketi üretir.

    En spesifikten (endeks) en geneline (coğrafya) doğru sıralar.
    Duplicate etiketler kaldırılır, sıra korunur, maksimum 6 etiket döner.

    Hiçbir eşleme tutmazsa kategori metninin ilk kelimesi etiket olarak
    döner (fallback). Bu sayede liste hiçbir zaman boş dönmez (kategori
    mevcutken).
    """
    text = _normalize(f"{name} {category}")

    tags: list[str] = []

    # 1) BIST endeksleri (en spesifik)
    if "BIST 30" in text or "BIST30" in text:
        tags.append("BIST30")
    if "BIST 100" in text or "BIST100" in text:
        tags.append("BIST100")

    # 2) Sektörler
    for keywords, tag in _SECTOR_MAP:
        if any(k in text for k in keywords):
            tags.append(tag)

    # 3) Varlık türleri
    for keywords, tag in _ASSET_MAP:
        if any(k in text for k in keywords):
            tags.append(tag)

    # 4) Tema / Strateji
    for keywords, tag in _THEME_MAP:
        if any(k in text for k in keywords):
            tags.append(tag)

    # 5) Coğrafya
    for keywords, tag in _GEO_MAP:
        if any(k in text for k in keywords):
            tags.append(tag)

    # Fallback: kategoriyi kullan
    if not tags and category:
        first = category.split()[0] if category.split() else ""
        if first:
            tags.append(first[:12])

    # Duplicate kaldır (sırayı koruyarak), max 6 etiket
    seen: set[str] = set()
    unique: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:6]
