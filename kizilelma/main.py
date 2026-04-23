"""Kızılelma ana giriş noktası.

Komutlar:
    kizilelma run-now      → Şu an bir rapor üret ve gönder (test için)
    kizilelma start        → Zamanlayıcıyı başlat (her hafta içi 10:00)
    kizilelma test-telegram → Telegram bağlantısını test et
"""
import argparse
import asyncio
import logging
import sys

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kizilelma.config import get_config
from kizilelma.scheduler.daily_job import run_daily_job
from kizilelma.telegram_bot.bot import TelegramSender


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


async def async_main_test_telegram() -> None:
    """Telegram bağlantısını test et."""
    config = get_config()
    sender = TelegramSender(
        token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    await sender.send_test_message(
        "🌅 Kızılelma test mesajı\n\nBağlantı çalışıyor!"
    )
    logger.info("Test mesajı gönderildi.")


def cli() -> None:
    """Komut satırı arayüzü."""
    parser = argparse.ArgumentParser(prog="kizilelma")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-now", help="Şu an bir rapor üret ve gönder")
    sub.add_parser("start", help="Zamanlayıcıyı başlat (Pzt-Cum 10:00)")
    sub.add_parser("test-telegram", help="Telegram bağlantısını test et")

    args = parser.parse_args()

    if args.command == "run-now":
        result = asyncio.run(async_main_run_now())
        sys.exit(0 if result["status"] != "failed" else 1)
    elif args.command == "start":
        asyncio.run(async_main_start())
    elif args.command == "test-telegram":
        asyncio.run(async_main_test_telegram())


if __name__ == "__main__":
    cli()
