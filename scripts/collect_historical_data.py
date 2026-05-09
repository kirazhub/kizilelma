"""1 yıllık geçmiş makro/endeks veri toplayıcı.

yfinance ile Yahoo Finance'tan geçmiş veri çeker:
- USD/TRY, EUR/TRY (kur)
- Ons altın
- BIST 100
- Brent petrol
- Türkiye 10 büyük hisse

Her sembol için her bir günü ayrı SnapshotRecord + MacroRecord olarak DB'ye yazar.
Aynı tarih için snapshot zaten varsa onu yeniden kullanır; aynı sembol+snapshot
ikilisi için MacroRecord zaten varsa atlanır (idempotent).
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

# Path setup: bu script projenin kökünden çağrılabilsin
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select  # noqa: E402

from kizilelma.storage.db import get_engine, init_db  # noqa: E402
from kizilelma.storage.models import MacroRecord, SnapshotRecord  # noqa: E402


# Logging — Türkçe ve okunaklı format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# yfinance sembolleri:
#   key  -> (yahoo_symbol, görünür_isim, currency, category)
YF_SYMBOLS: dict[str, tuple[str, str, str, str]] = {
    # Kurlar
    "USDTRY": ("USDTRY=X", "Dolar", "TRY", "currency"),
    "EURTRY": ("EURTRY=X", "Euro", "TRY", "currency"),
    # Emtia
    "GOLD_OZ": ("GC=F", "Ons Altın", "USD", "commodity"),
    "BRENT": ("BZ=F", "Brent Petrol", "USD", "commodity"),
    # Endeks
    "BIST100": ("XU100.IS", "BIST 100", "TRY", "index"),
    # Türkiye 10 büyük hisse (BIST)
    "AKBNK": ("AKBNK.IS", "Akbank", "TRY", "stock"),
    "GARAN": ("GARAN.IS", "Garanti BBVA", "TRY", "stock"),
    "ISCTR": ("ISCTR.IS", "İş Bankası", "TRY", "stock"),
    "THYAO": ("THYAO.IS", "Türk Hava Yolları", "TRY", "stock"),
    "ASELS": ("ASELS.IS", "Aselsan", "TRY", "stock"),
    "BIMAS": ("BIMAS.IS", "BIM", "TRY", "stock"),
    "TUPRS": ("TUPRS.IS", "Tüpraş", "TRY", "stock"),
    "EREGL": ("EREGL.IS", "Ereğli Demir Çelik", "TRY", "stock"),
    "KCHOL": ("KCHOL.IS", "Koç Holding", "TRY", "stock"),
    "SAHOL": ("SAHOL.IS", "Sabancı Holding", "TRY", "stock"),
}


def _get_or_create_snapshot(
    session: Session, record_date: dt.date
) -> SnapshotRecord:
    """Verilen tarihte bir SnapshotRecord varsa döndür, yoksa oluştur.

    Tarihsel veri yüklerken her takvim günü için tek bir snapshot kullanılır;
    böylece aynı günün farklı sembolleri ortak snapshot altında toplanır.
    """
    day_start = dt.datetime.combine(record_date, dt.time.min)
    day_end = dt.datetime.combine(
        record_date + dt.timedelta(days=1), dt.time.min
    )

    stmt = (
        select(SnapshotRecord)
        .where(SnapshotRecord.timestamp >= day_start)
        .where(SnapshotRecord.timestamp < day_end)
        .order_by(SnapshotRecord.timestamp.asc())
        .limit(1)
    )
    snap = session.exec(stmt).first()
    if snap is not None:
        return snap

    # Yoksa, gün ortasında (saat 10:00) sabit bir snapshot oluştur
    snap = SnapshotRecord(
        timestamp=dt.datetime.combine(record_date, dt.time(10, 0)),
        fund_count=0,
        bond_count=0,
        sukuk_count=0,
        repo_count=0,
        eurobond_count=0,
        news_count=0,
        errors_json="{}",
    )
    session.add(snap)
    session.flush()  # ID al
    return snap


def collect_historical_data(days_back: int = 365) -> None:
    """Son ``days_back`` günün geçmiş verisini topla ve DB'ye kaydet."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance kurulu değil! pip install yfinance")
        return

    engine = get_engine()
    init_db(engine)

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days_back)

    logger.info("Geçmiş veri toplama başlıyor: %s → %s", start_date, end_date)
    logger.info("Toplanacak sembol sayısı: %d", len(YF_SYMBOLS))

    total_added = 0
    failed_symbols: list[str] = []

    for symbol_key, (yf_symbol, name, currency, category) in YF_SYMBOLS.items():
        try:
            logger.info("📥 %s (%s) çekiliyor...", symbol_key, yf_symbol)

            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(
                start=start_date,
                end=end_date,
                auto_adjust=False,
            )

            if hist is None or hist.empty:
                logger.warning("⚠️  %s: veri bulunamadı, atlanıyor", symbol_key)
                failed_symbols.append(symbol_key)
                continue

            logger.info("   %d günlük veri bulundu", len(hist))

            with Session(engine) as session:
                added = 0
                for date_idx, row in hist.iterrows():
                    # date_idx Timestamp olabilir — date()'e çevir
                    record_date = (
                        date_idx.date() if hasattr(date_idx, "date") else date_idx
                    )

                    close_price = row.get("Close")
                    if close_price is None:
                        continue
                    try:
                        close_price = float(close_price)
                    except (TypeError, ValueError):
                        continue
                    if close_price <= 0:
                        continue

                    # Bu güne ait snapshot var mı? Yoksa oluştur
                    snap = _get_or_create_snapshot(session, record_date)

                    # Aynı snapshot+symbol için duplicate yazma
                    macro_stmt = (
                        select(MacroRecord)
                        .where(MacroRecord.snapshot_id == snap.id)
                        .where(MacroRecord.symbol == symbol_key)
                        .limit(1)
                    )
                    if session.exec(macro_stmt).first() is not None:
                        continue

                    # change_pct: bir önceki günün kapanışına göre yüzde değişim
                    change_pct: float | None = None
                    # pandas index'i sıralı; basit bir yöntemle önceki satırı bul
                    # (yfinance index'i tarih sıralı geldiği için satır sırası yeterli)

                    macro = MacroRecord(
                        snapshot_id=snap.id,
                        symbol=symbol_key,
                        name=name,
                        value=close_price,
                        currency=currency,
                        change_pct=change_pct,
                        category=category,
                        date=record_date,
                    )
                    session.add(macro)
                    added += 1

                session.commit()
                logger.info("   ✅ %s: %d yeni kayıt eklendi", symbol_key, added)
                total_added += added

        except Exception as exc:  # noqa: BLE001 — bir sembol hata verse de devam
            logger.error("❌ %s hatası: %s", symbol_key, exc)
            failed_symbols.append(symbol_key)
            continue

    logger.info("")
    logger.info("🎉 TAMAMLANDI: Toplam %d yeni kayıt eklendi", total_added)
    if failed_symbols:
        logger.warning(
            "⚠️  Veri alınamayan semboller: %s", ", ".join(failed_symbols)
        )

    # Genel özet
    with Session(engine) as session:
        total_macros = len(list(session.exec(select(MacroRecord))))
        total_snapshots = len(list(session.exec(select(SnapshotRecord))))
        logger.info(
            "   DB'de toplam: %d macro kayıt, %d snapshot",
            total_macros,
            total_snapshots,
        )


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    collect_historical_data(days)
