"""TÜM fonların günlük fiyat geçmişini TEFAS'tan topla.

TEFAS 2026'da API'yi yeniledi. Eski ``BindHistoryInfo`` endpoint'i artık
çalışmıyor; bunun yerine ``/api/funds/fonFiyatBilgiGetir`` JSON endpoint'i
kullanılıyor. Bu endpoint **periyod** olarak ay sayısı alıyor (1, 3, 6,
12, 36, 60). Yani "365 gün" yerine "12 ay" deniyor.

KULLANIM:
    python scripts/collect_fund_history.py [PERIYOD]

PERIYOD: Ay cinsinden look-back (varsayılan 12). İzin verilen değerler:
    1, 3, 6, 12, 36, 60. Başka bir değer verilirse en yakın üst değere
    yuvarlanır (TEFAS başka değerleri kabul etmiyor).

NOT: 218 fon × 2 sn gecikme = ~7 dk minimum. 12 aylık veri için
toplam süre yaklaşık 10–15 dakika.
"""
import datetime as dt
import logging
import math
import sys
import time
from pathlib import Path

import httpx

# Path setup — kizilelma paketini import edebilmek için
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, SQLModel, select

from kizilelma.storage.db import get_engine, init_db
from kizilelma.storage.models import FundPriceRecord, FundRecord


# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# TEFAS API ayarları (2026 yeni API)
# ──────────────────────────────────────────────────────────────
TEFAS_PRICE_URL = "https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr,en-US;q=0.7,en;q=0.3",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/",
}

# TEFAS yalnızca bu periyod değerlerini kabul ediyor (ay)
VALID_PERIODS = (1, 3, 6, 12, 36, 60)

# Rate limit — TEFAS'ı yormamak için fonlar arası gecikme
DELAY_BETWEEN_FUNDS = 2.0  # saniye

# Hata sonrası bekleme
RETRY_BACKOFF = 5  # saniye (her retry'de × attempt)


# ──────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ──────────────────────────────────────────────────────────────
def snap_to_valid_period(months: int) -> int:
    """Verilen ay sayısını TEFAS'ın kabul ettiği en yakın üst değere yuvarla."""
    for p in VALID_PERIODS:
        if p >= months:
            return p
    return VALID_PERIODS[-1]


def get_fund_codes(engine) -> list[str]:
    """Mevcut DB'den tüm distinct fon kodlarını al."""
    with Session(engine) as session:
        codes = list(session.exec(select(FundRecord.code).distinct()))
    unique_codes = sorted(set(codes))
    logger.info("DB'de %d farklı fon kodu bulundu", len(unique_codes))
    return unique_codes


def get_fund_names(engine, codes: list[str]) -> dict[str, str]:
    """Fon kodlarına karşılık fon adlarını çıkar."""
    names: dict[str, str] = {}
    with Session(engine) as session:
        for code in codes:
            rec = session.exec(
                select(FundRecord).where(FundRecord.code == code).limit(1)
            ).first()
            names[code] = rec.name if rec else code
    return names


def parse_iso_date(raw: str | None) -> dt.date | None:
    """Yeni TEFAS API'si tarihi ``YYYY-MM-DD`` formatında döner."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def fetch_fund_history(
    code: str,
    periyod: int,
    client: httpx.Client,
    max_retries: int = 3,
) -> list[dict]:
    """Bir fonun TEFAS'tan geçmiş fiyatlarını çek.

    Yeni API: POST + JSON body. ``periyod`` ay cinsinden look-back.
    """
    payload = {"fonKodu": code, "dil": "TR", "periyod": periyod}

    for attempt in range(max_retries):
        try:
            response = client.post(
                TEFAS_PRICE_URL,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("resultList") or []
        except httpx.HTTPError as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * RETRY_BACKOFF
                logger.warning(
                    "  %s: HTTP hatası, %dsn bekle (%s)", code, wait, e
                )
                time.sleep(wait)
            else:
                logger.error("  %s: TEFAS'tan veri alınamadı: %s", code, e)
        except (ValueError, KeyError) as e:
            logger.error("  %s: JSON parse hatası: %s", code, e)
            return []
    return []


def save_prices(
    records: list[dict],
    code: str,
    fallback_name: str,
    engine,
) -> tuple[int, int]:
    """Fiyatları DB'ye kaydet (duplicate kontrolü ile).

    Returns:
        (eklenen_kayit, atlanan_kayit)
    """
    if not records:
        return 0, 0

    added = 0
    skipped = 0

    with Session(engine) as session:
        # Önce mevcut tarihleri tek sorguda al — N+1 sorgudan kaçın
        existing_dates = set(
            session.exec(
                select(FundPriceRecord.date).where(
                    FundPriceRecord.code == code
                )
            )
        )

        for record in records:
            record_date = parse_iso_date(record.get("tarih"))
            if record_date is None:
                continue

            price_raw = record.get("fiyat", 0)
            try:
                price_f = float(price_raw)
            except (TypeError, ValueError):
                continue
            if price_f <= 0:
                continue

            if record_date in existing_dates:
                skipped += 1
                continue

            # API'den gelen fonUnvan varsa onu kullan, yoksa DB'deki ada düş
            name = record.get("fonUnvan") or fallback_name

            session.add(
                FundPriceRecord(
                    code=code,
                    name=name,
                    price=price_f,
                    date=record_date,
                )
            )
            existing_dates.add(record_date)
            added += 1

        session.commit()

    return added, skipped


# ──────────────────────────────────────────────────────────────
# Ana akış
# ──────────────────────────────────────────────────────────────
def main(periyod: int = 12) -> None:
    periyod = snap_to_valid_period(max(1, periyod))

    logger.info("=" * 60)
    logger.info("TEFAS GEÇMIŞ FİYAT TOPLAMA (yeni API)")
    logger.info("Periyod: %d ay (~%d gün)", periyod, periyod * 30)
    logger.info("=" * 60)

    # DB hazırla — yeni FundPriceRecord tablosu yaratılır
    engine = get_engine()
    init_db(engine)
    SQLModel.metadata.create_all(engine)

    # Fon kodlarını ve adlarını al
    fund_codes = get_fund_codes(engine)
    if not fund_codes:
        logger.error("DB'de hiç fon yok! Önce normal toplama çalıştırın.")
        return

    fund_names = get_fund_names(engine, fund_codes)

    # İstatistikler
    total_funds = len(fund_codes)
    total_added = 0
    total_skipped = 0
    successful_funds = 0
    failed_funds: list[str] = []

    # Tek bir HTTP client (cookie & connection-pool için)
    with httpx.Client(headers=HEADERS) as client:
        for idx, code in enumerate(fund_codes, 1):
            fallback_name = fund_names.get(code, code)
            logger.info("[%d/%d] %s: çekiliyor...", idx, total_funds, code)

            records = fetch_fund_history(code, periyod, client)

            if not records:
                failed_funds.append(code)
                logger.warning("  %s: veri alınamadı", code)
            else:
                added, skipped = save_prices(
                    records, code, fallback_name, engine
                )
                total_added += added
                total_skipped += skipped
                if added > 0 or skipped > 0:
                    successful_funds += 1
                logger.info(
                    "  %s: %d kayıt geldi → %d yeni, %d atlandı",
                    code,
                    len(records),
                    added,
                    skipped,
                )

            # Rate limit gecikme (son fonda gerek yok)
            if idx < total_funds:
                time.sleep(DELAY_BETWEEN_FUNDS)

            # Her 50 fonda durum raporu
            if idx % 50 == 0:
                logger.info(
                    "  📊 Durum: %d/%d fon işlendi, %d yeni kayıt eklendi",
                    idx,
                    total_funds,
                    total_added,
                )

    # Final rapor
    logger.info("=" * 60)
    logger.info("✅ TAMAMLANDI")
    logger.info("  Başarılı: %d/%d fon", successful_funds, total_funds)
    logger.info("  Yeni kayıt: %d", total_added)
    logger.info("  Atlanan (duplicate): %d", total_skipped)
    logger.info("  Başarısız fon sayısı: %d", len(failed_funds))
    if failed_funds:
        logger.info("  İlk 10 başarısız: %s", failed_funds[:10])
    logger.info("=" * 60)


if __name__ == "__main__":
    # Komut satırı argümanı: GÜN sayısı (geriye uyumluluk için).
    # 365 gün → 12 ay, 30 gün → 1 ay olarak yorumlanır.
    if len(sys.argv) > 1:
        days_or_months = int(sys.argv[1])
        # Eğer 60'tan büyükse "gün" varsay, küçükse "ay" varsay
        if days_or_months > 60:
            periyod_months = math.ceil(days_or_months / 30)
        else:
            periyod_months = days_or_months
    else:
        periyod_months = 12

    main(periyod_months)
