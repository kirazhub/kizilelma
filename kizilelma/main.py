"""Kızılelma ana giriş noktası.

Komutlar:
    kizilelma run-now      → Şu an veri topla, AI raporu üret ve DB'ye kaydet
    kizilelma start        → Zamanlayıcıyı başlat (her hafta içi 10:00)
"""
import argparse
import asyncio
import logging
import sys

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kizilelma.scheduler.daily_job import run_daily_job


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("kizilelma")


TIMEZONE = pytz.timezone("Europe/Istanbul")


async def async_main_run_now() -> dict:
    """Şu an bir rapor üret (manuel test için)."""
    logger.info("Manuel rapor başlatılıyor...")
    result = await run_daily_job()
    logger.info(f"Sonuç: {result}")
    return result


async def async_main_start() -> None:
    """Zamanlayıcıyı başlat: hafta içi her gün 10:00."""
    logger.info("Zamanlayıcı başlatılıyor (Pzt-Cum 10:00 İstanbul saati)")

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_daily_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=10,
            minute=0,
            timezone=TIMEZONE,
        ),
        id="daily_report",
        name="Kızılelma Günlük Rapor",
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Zamanlayıcı çalışıyor. CTRL+C ile durdurabilirsin.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def cli() -> None:
    """Komut satırı arayüzü."""
    parser = argparse.ArgumentParser(prog="kizilelma")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-now", help="Şu an bir rapor üret ve DB'ye kaydet")
    sub.add_parser("start", help="Zamanlayıcıyı başlat (Pzt-Cum 10:00)")

    args = parser.parse_args()

    if args.command == "run-now":
        result = asyncio.run(async_main_run_now())
        sys.exit(0 if result["status"] != "failed" else 1)
    elif args.command == "start":
        asyncio.run(async_main_start())


if __name__ == "__main__":
    cli()
