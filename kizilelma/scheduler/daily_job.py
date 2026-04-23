"""Günlük rapor işi — tüm akışın orchestration'ı.

Akış:
    1. collect_all_data()  → tüm collector'ları paralel çalıştır
    2. AIAdvisor             → metrikleri hesapla + AI yorum üret
    3. TelegramSender       → rapor mesajlarını gönder

Hata toleransı:
    - Bir collector çökerse snapshot.errors'a not düşülür
    - AI çökerse rapor yine de ham veri olarak gönderilir
    - Telegram tek tek mesajlar başarısız olabilir
"""
import asyncio
import datetime as dt
import logging
from typing import Any

from kizilelma.config import get_config
from kizilelma.models import MarketSnapshot
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.collectors.tcmb import TcmbCollector
from kizilelma.collectors.bist import BistCollector
from kizilelma.collectors.eurobond import EurobondCollector
from kizilelma.collectors.news import NewsCollector
from kizilelma.ai_advisor.advisor import AIAdvisor
from kizilelma.telegram_bot.bot import TelegramSender


logger = logging.getLogger(__name__)


async def collect_all_data() -> MarketSnapshot:
    """Tüm veri kaynaklarını paralel olarak topla."""
    config = get_config()

    tefas = TefasCollector()
    tcmb = TcmbCollector(api_key=config.tcmb_api_key)
    bist = BistCollector()
    eurobond = EurobondCollector()
    news = NewsCollector()

    # Paralel çalıştır
    results = await asyncio.gather(
        _safe(tefas.fetch, "tefas"),
        _safe(tcmb.fetch, "tcmb"),
        _safe(bist.fetch, "bist"),
        _safe(eurobond.fetch, "eurobond"),
        _safe(news.fetch, "news"),
    )

    funds_result, repo_result, bist_result, eurobond_result, news_result = results

    # BIST tuple döner (bonds, sukuks)
    if bist_result.get("error"):
        bonds, sukuks = [], []
    else:
        data = bist_result.get("data", ([], []))
        bonds, sukuks = data if isinstance(data, tuple) else ([], [])

    snapshot = MarketSnapshot(
        timestamp=dt.datetime.now(),
        funds=funds_result.get("data") or [],
        repo_rates=repo_result.get("data") or [],
        bonds=bonds,
        sukuks=sukuks,
        eurobonds=eurobond_result.get("data") or [],
        news=news_result.get("data") or [],
    )

    # Hataları topla
    for r, name in [
        (funds_result, "tefas"),
        (repo_result, "tcmb"),
        (bist_result, "bist"),
        (eurobond_result, "eurobond"),
        (news_result, "news"),
    ]:
        if r.get("error"):
            snapshot.errors[name] = r["error"]

    return snapshot


async def _safe(coro_fn, name: str) -> dict:
    """Bir collector çağrısını güvenli yap, hata varsa yakala."""
    try:
        data = await coro_fn()
        return {"data": data, "error": None}
    except Exception as exc:
        logger.warning(f"Collector '{name}' başarısız: {exc}")
        return {"data": None, "error": str(exc)}


async def run_daily_job() -> dict[str, Any]:
    """Tüm günlük akışı tek seferde çalıştır."""
    from kizilelma.storage.db import init_db, save_snapshot, save_report

    config = get_config()
    logger.info("=== Kızılelma günlük rapor başladı ===")

    # 0. DB hazırla
    try:
        init_db()
    except Exception as exc:
        logger.warning(f"DB init başarısız: {exc}")

    # 1. Veri topla
    snapshot = await collect_all_data()
    logger.info(
        f"Veri toplandı: {len(snapshot.funds)} fon, {len(snapshot.news)} haber, "
        f"hatalar: {list(snapshot.errors.keys())}"
    )

    # 2. AI yorum üret
    advisor = AIAdvisor(api_key=config.anthropic_api_key)
    report = await advisor.generate_report(snapshot)
    logger.info(f"Rapor üretildi: errors={report.errors}")

    # 3. Telegram'a gönder
    sender = TelegramSender(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    sent = await sender.send_report(report)
    logger.info(f"{sent} mesaj gönderildi")

    # 4. DB'ye kaydet
    snapshot_id = None
    try:
        snapshot_id = save_snapshot(snapshot)
        save_report(
            report, snapshot_id=snapshot_id,
            sent_messages=sent,
            status="success" if sent > 0 and not snapshot.errors else "partial",
        )
        logger.info(f"DB'ye kaydedildi: snapshot_id={snapshot_id}")
    except Exception as exc:
        logger.warning(f"DB kayıt başarısız: {exc}")

    # Sonuç
    if sent == 0:
        status = "failed"
    elif snapshot.errors or report.errors:
        status = "partial"
    else:
        status = "success"

    return {
        "status": status,
        "sent_messages": sent,
        "snapshot_errors": snapshot.errors,
        "report_errors": report.errors,
        "snapshot_id": snapshot_id,
        "timestamp": snapshot.timestamp.isoformat(),
    }
